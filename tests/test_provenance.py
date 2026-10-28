"""Tests for GET /provenance/{item_id} (T5).

All offline; stored analyses/decisions are SYNTHETIC fixtures.
Criterion: for an accepted claim the chain is complete (document, quote,
model proposal with prompt_hash/time, human decision); unknown id -> 404.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main


def _analysis():
    return {
        "analysis_id": "an_test1",
        "status": "proposed",
        "model": {"provider": "meta", "requested": "muse-spark-1.3", "returned": "muse-spark-1.3"},
        "prompt_hash": "sha256:deadbeef",
        "created_at": "2026-10-28T12:00:00Z",
        "latency_ms": 5,
        "analysis": {
            "claims": [
                {"claim_id": "c1", "quote": "The hill marks the route",
                 "statement": "Hill as route marker",
                 "interpretation": "A landmark claim", "document_id": "d1",
                 "quote_verified": True, "provenance_status": "traced_supported"},
                {"claim_id": "c2", "quote": "Used until 1903",
                 "statement": "Use until 1903", "interpretation": "A dating claim",
                 "document_id": "d1", "quote_verified": True,
                 "provenance_status": "traced_uncertain"},
            ],
            "contradictions": [
                {"contradiction_id": "x1", "claim_ids": ["c1", "c2"],
                 "kind": "temporal_mismatch", "quotes_verified": True},
            ],
            "summary": None,
        },
        "provenance_check": {"claims_total": 2, "quotes_verified": 2, "problems": [], "ok": True},
        "_documents": [
            {"document_id": "d1", "title": "Oral tradition",
             "text": "The hill marks the route. Used until 1903."}
        ],
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


def _decide(client, item_id="c1", item_type="claim", verdict="accept"):
    return client.post(
        "/decisions",
        json={
            "analysis_id": "an_test1",
            "item_id": item_id,
            "item_type": item_type,
            "verdict": verdict,
            "comment": "checked against source",
            "reviewer": "reviewer-1",
        },
    )


def test_provenance_complete_chain_for_accepted_claim():
    client = TestClient(mock_main.app)
    assert _decide(client).status_code == 201
    resp = client.get("/provenance/c1")
    assert resp.status_code == 200
    body = resp.json()
    # document -> quote
    assert body["document"]["document_id"] == "d1"
    assert "The hill marks the route" in body["document"]["text"]
    assert body["quotes"] == [{"document_id": "d1", "quote": "The hill marks the route"}]
    # model proposal
    proposal = body["model_proposal"]
    assert proposal["model"]["returned"] == "muse-spark-1.3"
    assert proposal["prompt_hash"] == "sha256:deadbeef"
    assert proposal["created_at"] == "2026-10-28T12:00:00Z"
    assert proposal["item"]["interpretation"] == "A landmark claim"
    # human decisions
    assert body["status"] == "accepted"
    assert len(body["decisions"]) == 1
    decision = body["decisions"][0]
    assert decision["reviewer"] == "reviewer-1"
    assert decision["verdict"] == "accept"
    assert decision["comment"] == "checked against source"
    assert decision["recorded_at"]
    assert body["chain_complete"] is True


def test_provenance_proposed_item_has_empty_decisions():
    resp = TestClient(mock_main.app).get("/provenance/c2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "proposed"
    assert body["decisions"] == []
    assert body["chain_complete"] is False  # no human decision yet


def test_provenance_unknown_item_404():
    assert TestClient(mock_main.app).get("/provenance/nope").status_code == 404


def test_provenance_contradiction_chain_lists_both_quotes():
    client = TestClient(mock_main.app)
    assert _decide(client, item_id="x1", item_type="contradiction", verdict="dispute").status_code == 201
    body = client.get("/provenance/x1").json()
    assert body["item_type"] == "contradiction"
    assert [q["quote"] for q in body["quotes"]] == [
        "The hill marks the route",
        "Used until 1903",
    ]
    assert body["status"] == "disputed"
    assert len(body["documents"]) == 1


def test_provenance_history_keeps_all_decisions_in_order():
    client = TestClient(mock_main.app)
    _decide(client, verdict="dispute")
    _decide(client, verdict="accept")
    body = client.get("/provenance/c1").json()
    assert [d["verdict"] for d in body["decisions"]] == ["dispute", "accept"]
    assert body["status"] == "accepted"


def test_provenance_analysis_id_disambiguates():
    with mock_main._state_lock:
        other = _analysis()
        other["analysis_id"] = "an_other"
        mock_main._analyses["an_other"] = other
    resp = TestClient(mock_main.app).get("/provenance/c1?analysis_id=an_other")
    assert resp.status_code == 200
    assert resp.json()["analysis_id"] == "an_other"
    resp404 = TestClient(mock_main.app).get("/provenance/c1?analysis_id=an_missing")
    assert resp404.status_code == 404
