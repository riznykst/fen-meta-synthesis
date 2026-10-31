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


def build_provenance(analyses: dict, decisions: list, item_id: str,
                     analysis_id: Optional[str] = None) -> Optional[dict]:
    """Full provenance chain for one item (T5), or None when unknown.

    document -> quote -> model proposal (model, prompt_hash, time) ->
    human decisions (reviewer, verdict, comment, time). Searches claims
    and contradictions across stored analyses; ``analysis_id`` disambiguates
    when the same item id appears in several analyses."""
    candidates = []
    for stored_id, analysis in analyses.items():
        if analysis_id and stored_id != analysis_id:
            continue
        for item_type in ("claim", "contradiction"):
            item = find_item(analysis, item_type, item_id)
            if item is not None:
                candidates.append((stored_id, analysis, item_type, item))
    if not candidates:
        return None
    stored_id, analysis, item_type, item = candidates[0]
    documents_by_id = {d["document_id"]: d for d in analysis.get("_documents", [])}
    item_decisions = [
        {
            "decision_id": r["decision_id"],
            "reviewer": r["reviewer"],
            "verdict": r["verdict"],
            "status": r["status"],
            "comment": r.get("comment", ""),
            "recorded_at": r["recorded_at"],
        }
        for r in decisions
        if r.get("analysis_id") == stored_id and r.get("item_id") == item_id
    ]
    proposal = {
        "analysis_id": stored_id,
        "status": "proposed",
        "model": analysis.get("model"),
        "prompt_hash": analysis.get("prompt_hash"),
        "created_at": analysis.get("created_at"),
        "item": item,
    }
    if item_type == "claim":
        document = documents_by_id.get(item.get("document_id"))
        quotes = [{"document_id": item.get("document_id"), "quote": item.get("quote")}]
    else:
        claims_by_id = {
            c["claim_id"]: c for c in analysis.get("analysis", {}).get("claims", [])
        }
        document = None
        quotes = [
            {
                "document_id": claims_by_id[ref].get("document_id"),
                "quote": claims_by_id[ref].get("quote"),
            }
            for ref in item.get("claim_ids", [])
            if ref in claims_by_id
        ]
    return {
        "item_id": item_id,
        "item_type": item_type,
        "analysis_id": stored_id,
        "status": current_status(decisions, stored_id, item_id),
        "document": document,
        "documents": [
            documents_by_id[doc_id]
            for doc_id in dict.fromkeys(
                q["document_id"] for q in quotes if q["document_id"] in documents_by_id
            )
        ],
        "quotes": quotes,
        "model_proposal": proposal,
        "decisions": item_decisions,
        "chain_complete": bool(document or quotes) and bool(item_decisions),
    }


def build_record(analyses: dict, decisions: list, item_id: str,
                 analysis_id: Optional[str] = None) -> Optional[dict]:
    """Exportable JSON-LD record for one DECIDED item, or None.

    Returns None when the item is unknown; raises ValueError when the item
    exists but no human decision has been recorded yet — a record is a
    decision artefact, and a model proposal alone must never be exportable
    as one. The record carries the full chain so it can later be ingested
    into a knowledge graph without rework: claim, quote, source document,
    model + prompt hash, and every human decision in order."""
    chain = build_provenance(analyses, decisions, item_id, analysis_id)
    if chain is None:
        return None
    if not chain["decisions"]:
        raise ValueError("no human decision recorded for this item yet")
    proposal = chain["model_proposal"]
    item = proposal["item"]
    record = {
        "@context": {
            "schema": "https://schema.org/",
            "gfen": "https://w3id.org/got/fen/ontology#",
        },
        "@id": f"urn:fen:record:{chain['analysis_id']}:{item_id}",
        "@type": "gfen:ValidationRecord",
        "item_id": item_id,
        "item_type": chain["item_type"],
        "status": chain["status"],
        "analysis_id": chain["analysis_id"],
        "source_documents": chain["documents"],
        "quotes": chain["quotes"],
        "claim": item,
        "model_proposal": {
            "model": proposal.get("model"),
            "prompt_hash": proposal.get("prompt_hash"),
            "created_at": proposal.get("created_at"),
        },
        "decisions": chain["decisions"],
        "exported_from": "FEN x Meta demo registry (in-memory + JSONL store when configured)",
    }
    return record


def accepted_records(analyses: dict, decisions: list) -> list:
    """Registry showcase: every item whose CURRENT status is accepted
    (latest human decision wins), newest decision first. Each record also
    carries the full vote trail (who voted how, in recording order) and the
    number of distinct voters, so the registry shows the community, not just
    the last accepting reviewer."""
    latest = {}
    for record in decisions:
        latest[(record.get("analysis_id"), record.get("item_id"))] = record
    out = []
    for (analysis_id, item_id), record in latest.items():
        if record.get("status") != "accepted":
            continue
        analysis = analyses.get(analysis_id) or {}
        item = None
        for item_type in ("claim", "contradiction"):
            item = find_item(analysis, item_type, item_id)
            if item is not None:
                break
        votes = [
            {
                "reviewer": d.get("reviewer"),
                "verdict": d.get("verdict"),
                "status": d.get("status"),
                "comment": d.get("comment", ""),
                "recorded_at": d.get("recorded_at"),
            }
            for d in decisions
            if d.get("analysis_id") == analysis_id and d.get("item_id") == item_id
        ]
        voters = {}
        for v in votes:
            if v["reviewer"]:
                voters[v["reviewer"]] = True
        out.append({
            "analysis_id": analysis_id,
            "item_id": item_id,
            "item_type": record.get("item_type"),
            "status": "accepted",
            "statement": (item or {}).get("statement") or (item or {}).get("quote") or "",
            "quote": (item or {}).get("quote") or "",
            "document_id": (item or {}).get("document_id") or "",
            "reviewer": record.get("reviewer"),
            "verdict": record.get("verdict"),
            "comment": record.get("comment", ""),
            "recorded_at": record.get("recorded_at"),
            "decision_id": record.get("decision_id"),
            "voter_count": len(voters),
            "votes": votes,
            "export_path": f"/records/{item_id}?analysis_id={analysis_id}",
        })
    out.sort(key=lambda r: r.get("recorded_at") or "", reverse=True)
    return out
