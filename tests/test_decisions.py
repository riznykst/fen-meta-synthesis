"""Tests for POST /decisions (T4) — human decisions only.

All offline; the event publisher is a mock injected via app.state.
Stored analyses are SYNTHETIC fixtures inserted into the in-memory
registry (the shape services/common/analyze.py produces).
"""
from __future__ import annotations

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main
from mock_fen_api.decisions import current_status


def _analysis():
    return {
        "analysis_id": "an_test1",
        "status": "proposed",
        "model": {"provider": "meta", "requested": "muse-spark-1.3", "returned": "muse-spark-1.3"},
        "prompt_hash": "sha256:abc",
        "created_at": "2026-10-28T12:00:00Z",
        "latency_ms": 1,
        "analysis": {
            "claims": [
                {"claim_id": "c1", "quote": "q1", "document_id": "d1",
                 "quote_verified": True, "provenance_status": "traced_supported"},
                {"claim_id": "c2", "quote": "fabricated", "document_id": "d1",
                 "quote_verified": False, "provenance_status": "unsupported"},
            ],
            "contradictions": [
                {"contradiction_id": "x1", "claim_ids": ["c1", "c2"],
                 "quotes_verified": False},
            ],
            "summary": None,
        },
        "provenance_check": {"claims_total": 2, "quotes_verified": 1, "problems": [], "ok": False},
        "_documents": [{"document_id": "d1", "title": None, "text": "q1 and more"}],
    }


@pytest.fixture(autouse=True)
def _clean():
    with mock_main._state_lock:
        mock_main._analyses.clear()
        mock_main._decisions.clear()
        mock_main._decision_events.clear()
        mock_main._analyses["an_test1"] = _analysis()
    if hasattr(mock_main.app.state, "decision_publisher"):
        delattr(mock_main.app.state, "decision_publisher")
    yield
    with mock_main._state_lock:
        mock_main._analyses.clear()
        mock_main._decisions.clear()
        mock_main._decision_events.clear()


def _decide(client, **overrides):
    body = {
        "analysis_id": "an_test1",
        "item_id": "c1",
        "item_type": "claim",
        "verdict": "accept",
        "comment": "",
        "reviewer": "reviewer-1",
    }
    body.update(overrides)
    return client.post("/decisions", json=body)


def test_accept_verified_claim_201_and_publishes_event():
    publisher = mock.Mock()
    mock_main.app.state.decision_publisher = publisher
    resp = _decide(TestClient(mock_main.app))
    assert resp.status_code == 201
    body = resp.json()
    assert body["decision_id"].startswith("dec_") and body["event_published"] is True
    publisher.assert_called_once()
    event = publisher.call_args.args[0]
    assert event["verdict"] == "accept" and event["status"] == "accepted"
    assert event["reviewer"] == "reviewer-1" and event["item_id"] == "c1"
    with mock_main._state_lock:
        assert current_status(mock_main._decisions, "an_test1", "c1") == "accepted"


@pytest.mark.parametrize(
    "verdict,status", [("reject", "rejected"), ("dispute", "disputed")]
)
def test_reject_and_dispute_verdicts(verdict, status):
    resp = _decide(TestClient(mock_main.app), verdict=verdict, comment="checked")
    assert resp.status_code == 201
    with mock_main._state_lock:
        assert current_status(mock_main._decisions, "an_test1", "c1") == status
        assert mock_main._decisions[0]["comment"] == "checked"


def test_accept_unverified_quote_409_no_record_no_event():
    publisher = mock.Mock()
    mock_main.app.state.decision_publisher = publisher
    resp = _decide(TestClient(mock_main.app), item_id="c2", verdict="accept")
    assert resp.status_code == 409
    publisher.assert_not_called()
    with mock_main._state_lock:
        assert mock_main._decisions == []


def test_reject_unverified_quote_is_allowed():
    resp = _decide(TestClient(mock_main.app), item_id="c2", verdict="reject")
    assert resp.status_code == 201


def test_accept_unverified_contradiction_409():
    resp = _decide(
        TestClient(mock_main.app), item_id="x1", item_type="contradiction", verdict="accept"
    )
    assert resp.status_code == 409


def test_repeat_decision_appends_immutable_records():
    client = TestClient(mock_main.app)
    first = _decide(client, verdict="dispute", comment="unsure")
    assert first.status_code == 201
    with mock_main._state_lock:
        snapshot = dict(mock_main._decisions[0])
    second = _decide(client, verdict="accept", comment="resolved")
    assert second.status_code == 201
    assert second.json()["decision_id"] != first.json()["decision_id"]
    with mock_main._state_lock:
        assert len(mock_main._decisions) == 2
        assert mock_main._decisions[0] == snapshot  # old record untouched
        # latest decision determines current status
        assert current_status(mock_main._decisions, "an_test1", "c1") == "accepted"


def test_unknown_analysis_and_item_404():
    client = TestClient(mock_main.app)
    assert _decide(client, analysis_id="an_nope").status_code == 404
    assert _decide(client, item_id="c99").status_code == 404
    assert _decide(client, item_id="x1").status_code == 404  # wrong item_type


def test_invalid_verdict_422():
    resp = _decide(TestClient(mock_main.app), verdict="approve")
    assert resp.status_code == 422


def test_default_publisher_writes_demo_event_log():
    resp = _decide(TestClient(mock_main.app))
    assert resp.status_code == 201 and resp.json()["event_published"] is True
    with mock_main._state_lock:
        assert len(mock_main._decision_events) == 1
        assert mock_main._decision_events[0]["event_type"] == "review-decision"


def test_publisher_failure_reports_not_published_but_keeps_record():
    mock_main.app.state.decision_publisher = mock.Mock(side_effect=RuntimeError("bus down"))
    resp = _decide(TestClient(mock_main.app))
    assert resp.status_code == 201
    assert resp.json()["event_published"] is False
    with mock_main._state_lock:
        assert len(mock_main._decisions) == 1
