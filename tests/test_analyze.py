"""Endpoint tests for POST /analyze (T3, SPEC section 6).

All offline: the provider client (``chat_completion_detailed`` in
services/common/analyze.py) is mocked. Model responses are SYNTHETIC
fixtures. Covered: section-6 response shape + registry storage, 422 on
invalid input (empty / duplicate / >30 000 chars), 502 on provider failure
and on contract failure, and NO fallback to a prepared answer.
"""
from __future__ import annotations

import json
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main
from services.common import analyze as analyze_svc
from services.common.llm import LLMResult

DOCS_PAYLOAD = {
    "documents": [
        {
            "document_id": "d1",
            "title": "Oral tradition",
            "text": "The hill Koshary marks the old trade route. It was used by traders until 1903.",
        }
    ]
}

# SYNTHETIC model response (not recorded, not real data).
SYNTHETIC_RESPONSE = json.dumps(
    {
        "claims": [
            {
                "claim_id": "c1",
                "quote": "The hill Koshary marks the old trade route",
                "statement": "The hill Koshary marks the old trade route",
                "interpretation": "The hill was a route landmark.",
                "document_id": "d1",
                "ambiguities": [],
                "uncertainty": "low",
                "review_recommendation": "proceed_to_human_review",
            }
        ],
        "contradictions": [],
        "summary": "SYNTHETIC fixture",
    }
)


class _FakeConfig:
    enabled = True
    model = "muse-spark-1.3"
    base_url = "https://api.meta.ai/v1"
    api_key = "secret-must-never-leak"
    timeout_s = 5.0
    system_role = "system"
    json_mode = False


def _result(text):
    return LLMResult(text=text, model_returned="muse-spark-1.3",
                     usage={"total_tokens": 7}, finish_reason="stop")


@pytest.fixture(autouse=True)
def _clean_analyses():
    with mock_main._state_lock:
        mock_main._analyses.clear()
    yield
    with mock_main._state_lock:
        mock_main._analyses.clear()


def _client(monkeypatch):
    monkeypatch.setattr(mock_main, "_llm_config", _FakeConfig())
    return TestClient(mock_main.app)


def test_analyze_success_section6_shape_and_stored(monkeypatch):
    client = _client(monkeypatch)
    with mock.patch.object(
        analyze_svc, "chat_completion_detailed", return_value=_result(SYNTHETIC_RESPONSE)
    ):
        resp = client.post("/analyze", json=DOCS_PAYLOAD)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["status"] == "proposed"  # never accepted without a human
    assert body["analysis_id"].startswith("an_")
    assert body["model"]["requested"] == "muse-spark-1.3"
    assert body["model"]["returned"] == "muse-spark-1.3"
    assert body["prompt_hash"].startswith("sha256:")
    claim = body["analysis"]["claims"][0]
    assert claim["quote_verified"] is True
    assert body["provenance_check"]["ok"] is True
    assert "secret-must-never-leak" not in resp.text
    # stored for T4 decisions / T5 provenance
    with mock_main._state_lock:
        assert body["analysis_id"] in mock_main._analyses


def test_analyze_422_on_empty_documents(monkeypatch):
    resp = _client(monkeypatch).post("/analyze", json={"documents": []})
    assert resp.status_code == 422


def test_analyze_422_on_duplicate_document_id(monkeypatch):
    payload = {"documents": DOCS_PAYLOAD["documents"] * 2}
    resp = _client(monkeypatch).post("/analyze", json=payload)
    assert resp.status_code == 422


def test_analyze_422_over_30000_chars(monkeypatch):
    payload = {"documents": [{"document_id": "d1", "text": "x" * 30_001}]}
    with mock.patch.object(analyze_svc, "chat_completion_detailed") as call:
        resp = _client(monkeypatch).post("/analyze", json=payload)
    assert resp.status_code == 422
    call.assert_not_called()  # rejected before any provider call


def test_analyze_502_when_provider_down_no_fallback(monkeypatch):
    with mock.patch.object(
        analyze_svc, "chat_completion_detailed", return_value=None
    ):
        resp = _client(monkeypatch).post("/analyze", json=DOCS_PAYLOAD)
    assert resp.status_code == 502
    assert "claims" not in resp.text  # no prepared answer substituted


def test_analyze_502_when_contract_fails_after_one_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(analyze_svc, "_FAILURES_DIR", tmp_path)
    with mock.patch.object(
        analyze_svc,
        "chat_completion_detailed",
        side_effect=[_result("{broken"), _result("nope")],
    ) as call:
        resp = _client(monkeypatch).post("/analyze", json=DOCS_PAYLOAD)
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "invalid_analysis"
    assert call.call_count == 2


def test_shared_thread_second_participant_can_join(monkeypatch):
    """A second tab/user must see the same proposals and votes: the thread
    lives on the server (GET /analyses, /analyses/{id}, /decisions), not in
    the first tab's memory."""
    client = _client(monkeypatch)
    with mock.patch.object(
        analyze_svc, "chat_completion_detailed", return_value=_result(SYNTHETIC_RESPONSE)
    ):
        created = client.post("/analyze", json=DOCS_PAYLOAD)
    assert created.status_code == 200
    analysis_id = created.json()["analysis_id"]

    listed = client.get("/analyses")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["analyses"][0]["analysis_id"] == analysis_id

    fetched = client.get(f"/analyses/{analysis_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["analysis"]["claims"][0]["claim_id"] == "c1"
    assert body["documents"][0]["document_id"] == "d1"  # for Show-in-source
    assert client.get("/analyses/nope").status_code == 404

    # two distinct reviewers vote on the shared proposal
    for reviewer in ("ana", "boris"):
        resp = client.post("/decisions", json={
            "analysis_id": analysis_id, "item_id": "c1", "item_type": "claim",
            "verdict": "accept", "reviewer": reviewer, "comment": "",
        })
        assert resp.status_code == 201

    votes = client.get("/decisions", params={"analysis_id": analysis_id})
    assert votes.status_code == 200
    assert [d["reviewer"] for d in votes.json()["decisions"]] == ["ana", "boris"]
    assert votes.json()["count"] == 2


def test_analyze_502_when_not_configured(monkeypatch):
    class _Off:
        enabled = False
        model = "m"
        base_url = None

    monkeypatch.setattr(mock_main, "_llm_config", _Off())
    resp = TestClient(mock_main.app).post("/analyze", json=DOCS_PAYLOAD)
    assert resp.status_code == 502
