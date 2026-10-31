"""Tests for persistence, registry showcase and JSON-LD record export.

All offline. The store is a JSONL file under tmp_path; analyses/decisions
are SYNTHETIC fixtures in the shape services/common/analyze.py produces.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main
from mock_fen_api.decisions import accepted_records, build_record
from mock_fen_api.store import JsonlStore


def _analysis():
    return {
        "analysis_id": "an_test1",
        "status": "proposed",
        "model": {"provider": "meta", "requested": "muse-spark-1.3", "returned": "muse-spark-1.3"},
        "prompt_hash": "sha256:abc",
        "created_at": "2026-10-31T12:00:00Z",
        "latency_ms": 1,
        "analysis": {
            "claims": [
                {"claim_id": "c1", "quote": "q1 text", "statement": "A claim",
                 "interpretation": "A reading", "document_id": "d1",
                 "quote_verified": True, "provenance_status": "traced_supported"},
                {"claim_id": "c2", "quote": "q2 text", "statement": "Another",
                 "interpretation": "A reading", "document_id": "d1",
                 "quote_verified": True, "provenance_status": "traced_supported"},
            ],
            "contradictions": [],
            "summary": None,
        },
        "provenance_check": {"claims_total": 2, "quotes_verified": 2, "problems": [], "ok": True},
        "_documents": [{"document_id": "d1", "title": "Doc", "text": "q1 text. q2 text."}],
    }


@pytest.fixture(autouse=True)
def _clean():
    with mock_main._state_lock:
        mock_main._analyses.clear()
        mock_main._decisions.clear()
        mock_main._analyses["an_test1"] = _analysis()
    yield
    with mock_main._state_lock:
        mock_main._analyses.clear()
        mock_main._decisions.clear()


def _decide(client, item="c1", verdict="accept"):
    return client.post(
        "/decisions",
        json={
            "analysis_id": "an_test1", "item_id": item, "item_type": "claim",
            "verdict": verdict, "comment": "checked", "reviewer": "reviewer-1",
        },
    )


# ------------------------------------------------------------------ store ---
def test_jsonl_store_roundtrip(tmp_path):
    store = JsonlStore(str(tmp_path / "store.jsonl"))
    store.append("analysis", _analysis())
    store.append("decision", {"decision_id": "dec_1", "analysis_id": "an_test1",
                              "item_id": "c1", "status": "accepted"})
    analyses, decisions = store.load()
    assert list(analyses) == ["an_test1"]
    assert decisions[0]["decision_id"] == "dec_1"


def test_jsonl_store_disabled_without_path(tmp_path):
    store = JsonlStore(None)
    assert store.enabled is False
    store.append("decision", {"decision_id": "x"})  # no-op, never raises
    assert store.load() == ({}, [])


def test_store_replay_restores_provenance_after_restart(tmp_path, monkeypatch):
    store = JsonlStore(str(tmp_path / "store.jsonl"))
    monkeypatch.setattr(mock_main, "_store", store)
    client = TestClient(mock_main.app)
    assert _decide(client).status_code == 201
    # the decision event landed in the file
    lines = (tmp_path / "store.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(l)["type"] == "decision" for l in lines)
    # also persist the analysis the way POST /analyze does
    store.append("analysis", _analysis())
    # simulate restart: wipe in-memory state, replay from disk
    with mock_main._state_lock:
        mock_main._analyses.clear()
        mock_main._decisions.clear()
    mock_main._reload_store()
    chain = TestClient(mock_main.app).get("/provenance/c1").json()
    assert chain["status"] == "accepted"
    assert chain["chain_complete"] is True


# --------------------------------------------------------------- registry ---
def test_registry_lists_only_currently_accepted():
    client = TestClient(mock_main.app)
    assert _decide(client, "c1", "accept").status_code == 201
    assert _decide(client, "c2", "reject").status_code == 201
    body = client.get("/registry").json()
    assert body["count"] == 1
    record = body["records"][0]
    assert record["item_id"] == "c1" and record["status"] == "accepted"
    assert record["statement"] == "A claim"
    assert record["export_path"].startswith("/records/c1")


def test_registry_latest_decision_wins():
    client = TestClient(mock_main.app)
    _decide(client, "c1", "accept")
    _decide(client, "c1", "dispute")
    assert client.get("/registry").json()["count"] == 0


def test_accepted_records_pure_function():
    decisions = [
        {"decision_id": "d1", "analysis_id": "an_test1", "item_id": "c1",
         "item_type": "claim", "status": "accepted", "verdict": "accept",
         "reviewer": "r", "comment": "", "recorded_at": "2026-10-31T12:00:00Z"},
    ]
    out = accepted_records({"an_test1": _analysis()}, decisions)
    assert len(out) == 1 and out[0]["quote"] == "q1 text"


# ----------------------------------------------------------------- export ---
def test_record_export_jsonld_for_accepted_item():
    client = TestClient(mock_main.app)
    _decide(client, "c1", "accept")
    resp = client.get("/records/c1")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/ld+json")
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.json()
    assert body["@type"] == "gfen:ValidationRecord"
    assert body["status"] == "accepted"
    assert body["claim"]["quote"] == "q1 text"
    assert body["source_documents"][0]["document_id"] == "d1"
    assert body["model_proposal"]["prompt_hash"] == "sha256:abc"
    assert body["decisions"][0]["reviewer"] == "reviewer-1"


def test_record_export_409_without_decision_and_404_unknown():
    client = TestClient(mock_main.app)
    assert client.get("/records/c1").status_code == 409
    assert client.get("/records/ghost").status_code == 404


def test_build_record_raises_without_decision():
    with pytest.raises(ValueError):
        build_record({"an_test1": _analysis()}, [], "c1")
    assert build_record({"an_test1": _analysis()}, [], "ghost") is None
