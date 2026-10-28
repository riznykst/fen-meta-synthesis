"""Human review decisions (T4) — the only writer of accepted status.

The existing Kafka contract ``schemas/kafka-events/governance-decision.schema.json``
cannot carry a per-claim human verdict without being changed (its outcomes
are DAO ``validated|disputed|rejected`` with quorum/reputation fields), and
SPEC forbids changing it. Human decisions therefore use a separate event
contract, ``schemas/analysis/review-decision.schema.json`` (generated from
``ReviewDecisionEvent`` here), published by ``POST /decisions``.

Rules (SPEC T4 + section 0.8):
- Verdicts: ``accept`` | ``reject`` | ``dispute`` -> item status
  ``accepted`` | ``rejected`` | ``disputed``. Before any decision an item's
  status is ``proposed``; no model code can change that.
- ``accept`` on an item whose quote is NOT verified returns 409 — a human
  cannot accept an unverified citation through this API (reject/dispute
  remain possible).
- Decisions are immutable and append-only: a repeat decision creates a new
  record; the old record is never modified. The current status is the
  latest decision for the item.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Verdict(str, Enum):
    accept = "accept"
    reject = "reject"
    dispute = "dispute"


STATUS_BY_VERDICT = {
    Verdict.accept: "accepted",
    Verdict.reject: "rejected",
    Verdict.dispute: "disputed",
}


class ReviewDecisionBody(BaseModel):
    """POST /decisions request body (SPEC section 6)."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    item_type: str = Field(pattern="^(claim|contradiction)$")
    verdict: Verdict
    comment: str = ""
    reviewer: str = Field(min_length=1)


class ReviewDecisionEvent(BaseModel):
    """The recorded decision + published event (schema source of truth)."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = "review-decision"
    decision_id: str
    analysis_id: str
    item_id: str
    item_type: str
    verdict: Verdict
    status: str = Field(description="accepted | rejected | disputed")
    reviewer: str
    comment: str = ""
    recorded_at: str


def find_item(analysis: dict, item_type: str, item_id: str) -> Optional[dict]:
    """Find a claim or contradiction by id inside a stored analysis result."""
    bucket = "claims" if item_type == "claim" else "contradictions"
    id_field = "claim_id" if item_type == "claim" else "contradiction_id"
    for item in analysis.get("analysis", {}).get(bucket, []):
        if item.get(id_field) == item_id:
            return item
    return None


def item_is_verified(item: dict, item_type: str) -> bool:
    """Whether the item's quote(s) were verified by provenance checking."""
    if item_type == "claim":
        return bool(item.get("quote_verified"))
    return bool(item.get("quotes_verified"))


def new_decision_id() -> str:
    return f"dec_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_event(body: ReviewDecisionBody) -> ReviewDecisionEvent:
    return ReviewDecisionEvent(
        decision_id=new_decision_id(),
        analysis_id=body.analysis_id,
        item_id=body.item_id,
        item_type=body.item_type,
        verdict=body.verdict,
        status=STATUS_BY_VERDICT[body.verdict],
        reviewer=body.reviewer,
        comment=body.comment,
        recorded_at=now_iso(),
    )


def current_status(decisions: list, analysis_id: str, item_id: str) -> str:
    """Item status for the UI: proposed until a human decides; afterwards
    the latest recorded decision wins (records themselves never change)."""
    status = "proposed"
    for record in decisions:
        if record.get("analysis_id") == analysis_id and record.get("item_id") == item_id:
            status = record["status"]
    return status
