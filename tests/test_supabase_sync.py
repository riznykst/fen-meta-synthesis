"""Tests for the Supabase write-through in the demo API.

All offline: a fake registry object is injected via app.state.supabase, so no
network or database is touched. Fixtures are SYNTHETIC.
"""
from __future__ import annotations

import json
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main
from services.common import analyze as analyze_svc
from services.common.llm import LLMResult

DOCS = {"documents": [{"document_id": "d1", "title": "Doc", "text": "The hill marks the old route."}]}

ANALYSIS_JSON = json.dumps({
    "claims": [{
        "claim_id": "c1",
        "quote": "The hill marks the old route",
        "statement": "Hill as route marker",
        "interpretation": "A landmark claim",
        "document_id": "d1",
        "ambiguities": [],
        "uncertainty": "low",
        "review_recommendation": "proceed_to_human_review",
    }],
    "contradictions": [{
        "contradiction_id": "x1",
        "claim_ids": ["c1", "c2"],
        "kind": "temporal_mismatch",
        "explanation": "dates disagree",
        "alternative_interpretations": ["different events"],
    }],
    "summary": "SYNTHETIC",
})


class FakeSupabase:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.saved = []
        self.decisions = []
        self.registry_calls = 0

    def save_analysis(self, result, documents):
        if self.fail:
            raise RuntimeError("db down")
        self.saved.append({"analysis_id": result.get("analysis_id"), "documents": list(documents)})

    def record_decision(self, analysis_id, item_id, verdict, reviewer, comment=""):
        if self.fail:
            raise RuntimeError("db down")
        self.decisions.append({
            "analysis_id": analysis_id, "item_id": item_id,
            "verdict": verdict, "reviewer": reviewer, "comment": comment,
        })
        return {"decision_id": "dec_supabase", "recorded_at": "2026-10-31T20:00:00Z", "status": "accepted"}

    def load_registry(self, limit=100):
        self.registry_calls += 1
        if self.fail:
            raise RuntimeError("db down")
        return [{
            "item_id": "c1", "status": "accepted", "statement": "from supabase",
            "reviewer": "reviewer-1", "recorded_at": "2026-10-31T20:00:00Z",
            "source": "supabase",
        }]


class _FakeConfig:
    enabled = True
    model = "muse-spark-1.3"
    base_url = "https://api.meta.ai/v1"
    api_key = "k"
    timeout_s = 5.0
    system_role = "system"
    json_mode = False


@pytest.fixture(autouse=True)
def _clean():
    with mock_main._state_lock:
        mock_main._analyses.clear()
        mock_main._decisions.clear()
    if hasattr(mock_main.app.state, "supabase"):
        delattr(mock_main.app.state, "supabase")
    yield
    with mock_main._state_lock:
        mock_main._analyses.clear()
        mock_main._decisions.clear()
    if hasattr(mock_main.app.state, "supabase"):
        delattr(mock_main.app.state, "supabase")


def _client(monkeypatch, fake):
    monkeypatch.setattr(mock_main, "_llm_config", _FakeConfig())
    mock_main.app.state.supabase = fake
    return TestClient(mock_main.app)


def _run_analysis(client):
    with mock.patch.object(
        analyze_svc, "chat_completion_detailed",
        return_value=LLMResult(text=ANALYSIS_JSON, model_returned="muse-spark-1.3",
                               usage=None, finish_reason="stop"),
    ):
        return client.post("/analyze", json=DOCS)


def test_analyze_writes_analysis_to_supabase(monkeypatch):
    fake = FakeSupabase()
    client = _client(monkeypatch, fake)
    resp = _run_analysis(client)
    assert resp.status_code == 200
    assert len(fake.saved) == 1
    assert fake.saved[0]["analysis_id"] == resp.json()["analysis_id"]
    assert fake.saved[0]["documents"][0]["document_id"] == "d1"


def test_decision_goes_through_supabase_rpc(monkeypatch):
    fake = FakeSupabase()
    client = _client(monkeypatch, fake)
    analysis = _run_analysis(client).json()
    resp = client.post("/decisions", json={
        "analysis_id": analysis["analysis_id"], "item_id": "c1", "item_type": "claim",
        "verdict": "accept", "comment": "checked", "reviewer": "reviewer-1",
    })
    assert resp.status_code == 201
    assert resp.json()["supabase_persisted"] is True
    assert fake.decisions == [{
        "analysis_id": analysis["analysis_id"], "item_id": "c1",
        "verdict": "accept", "reviewer": "reviewer-1", "comment": "checked",
    }]


def test_accept_lock_still_refuses_before_touching_supabase(monkeypatch):
    fake = FakeSupabase()
    client = _client(monkeypatch, fake)
    with mock.patch.object(
        analyze_svc, "chat_completion_detailed",
        return_value=LLMResult(
            text=json.dumps({"claims": [{
                "claim_id": "c1", "quote": "words not in the document",
                "statement": "invented", "interpretation": "i",
                "document_id": "d1", "ambiguities": [],
                "uncertainty": "high",
                "review_recommendation": "more_evidence_required",
            }]}),
            model_returned="muse-spark-1.3", usage=None, finish_reason="stop",
        ),
    ):
        analysis = client.post("/analyze", json=DOCS).json()
    resp = client.post("/decisions", json={
        "analysis_id": analysis["analysis_id"], "item_id": "c1", "item_type": "claim",
        "verdict": "accept", "reviewer": "r",
    })
    assert resp.status_code == 409
    assert fake.decisions == []


def test_supabase_failure_does_not_break_the_request(monkeypatch):
    fake = FakeSupabase(fail=True)
    client = _client(monkeypatch, fake)
    resp = _run_analysis(client)
    assert resp.status_code == 200  # analysis still returned

    analysis = resp.json()
    decision = client.post("/decisions", json={
        "analysis_id": analysis["analysis_id"], "item_id": "c1", "item_type": "claim",
        "verdict": "reject", "reviewer": "r",
    })
    assert decision.status_code == 201
    assert decision.json()["supabase_persisted"] is False


def test_registry_reads_from_supabase_when_configured(monkeypatch):
    fake = FakeSupabase()
    client = _client(monkeypatch, fake)
    body = client.get("/registry").json()
    assert body["source"] == "supabase"
    assert body["count"] == 1
    assert body["records"][0]["statement"] == "from supabase"
    assert fake.registry_calls == 1


def test_registry_falls_back_to_local_on_supabase_error(monkeypatch):
    fake = FakeSupabase(fail=True)
    client = _client(monkeypatch, fake)
    body = client.get("/registry").json()
    assert body["source"] == "local"
    assert body["count"] == 0


def test_registry_local_when_supabase_not_configured():
    client = TestClient(mock_main.app)
    body = client.get("/registry").json()
    assert body["source"] == "local"


def test_supabase_registry_from_env_is_none_without_url(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    from mock_fen_api.supabase_registry import SupabaseRegistry

    assert SupabaseRegistry.from_env() is None
