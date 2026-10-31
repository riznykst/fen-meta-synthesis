"""Mock FEN API — stands in for the real Agentic Scaffolding + DAO
Quadratic Voting system, for local development and consortium demos only.

Accepts batches of EntityCandidate on POST /candidates and delivers a
synthetic GovernanceDecision to the FEN Bridge webhook. Two decision modes
(FEN_MOCK_VOTING):

- "auto" (default): after a configurable delay the simulated DAO quorum
  adopts the LLM/rule recommendation (see ADR-004) and the decision is
  delivered.
- "community": the UI-facing demo mode — candidates stay gfen:pending until
  community votes arrive via POST /candidates/{id}/vote; when the quorum
  (FEN_MOCK_QUORUM) is reached, the majority outcome is delivered.
- "qv": Quadratic Voting demo — intensity-weighted votes
  (FEN_MOCK_QV_THRESHOLD), delegation (liquid democracy, ADR-005 d.2).

Decision logic (in priority order):
1. If an OpenAI-compatible LLM endpoint is configured (FEN_LLM_BASE_URL —
   OpenAI, DeepSeek, local vLLM/Ollama, or GRAPHIA services such as
   LLM4SSH/Quagga exposing such an API), the LLM *recommends* an outcome.
   Decision-support only (ADR-004): it never votes and never decides.
2. Otherwise a deterministic placeholder rule applies (non-empty
   entity_label -> validated, else rejected).

This MUST NOT be mistaken for real DAO/Quadratic Voting governance, which
lives entirely outside this repository (see ADR-002). The REST contract
served here (see web/api.md) is the same contract the real FEN backend is
expected to implement.

Module layout (testability): pure QV math in mock_fen_api/qv_voting.py,
delegation logic in mock_fen_api/delegation.py, the Scaffold agents in
mock_fen_api/scaffold.py — this file keeps only the FastAPI app, the
in-memory state and the decision delivery.

Runs as the `mock-fen-api` container (see docker-compose.yml).
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Optional

import asyncio
import queue

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from services.common.llm import LLMConfig, chat_completion, parse_outcome
from services.common.logging_config import log_level_from_env, setup_logging
from services.common.metrics import (
    MOCK_CANDIDATES_ACCEPTED,
    MOCK_DECISIONS_DELIVERED,
    MOCK_DELIVERY_FAILURES,
    MOCK_DELIVERY_SECONDS,
    MOCK_LLM_JUDGE_CALLS,
    metrics_response,
)

from mock_fen_api.delegation import DelegationError, apply_delegation
from mock_fen_api.qv_voting import (
    MAX_INTENSITY,
    OUTCOMES,
    majority_outcome,
    quorum_total,
    qv_cost,
    qv_decide,
    qv_scores,
)
from pydantic import BaseModel, Field

from services.common.analysis import AnalysisParseError, SourceDocument
from services.common.analyze import AnalysisUnavailable, analyze_documents

from fastapi.responses import JSONResponse

from mock_fen_api.decisions import (
    ReviewDecisionBody,
    accepted_records,
    build_event,
    build_provenance,
    build_record,
    find_item,
    item_is_verified,
)
from mock_fen_api.scaffold import run_scaffold
from mock_fen_api.store import store_from_env
from mock_fen_api.supabase_registry import SupabaseRegistry

setup_logging("mock-fen-api", level=log_level_from_env())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Graceful shutdown: on SIGTERM/SIGINT uvicorn runs this teardown, which
    stops the delivery pool from accepting new work and waits for in-flight
    deliveries (``executor.shutdown(wait=True)``). TestClient used without the
    ``with`` block never triggers the lifespan, so tests keep the pool alive.
    """
    yield
    _shutdown_executor()


app = FastAPI(title="Mock FEN API (demo DAO stand-in — not production governance)", lifespan=lifespan)

# CORS for the web-interface layer (Flow 1 portal calls this service from a
# browser). Server-to-server callers (FEN Bridge) are unaffected.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("FEN_CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

WEBHOOK_URL = os.getenv("FEN_BRIDGE_WEBHOOK_URL", "http://localhost:8101/webhook/decision")
DECISION_DELAY_S = float(os.getenv("MOCK_FEN_DECISION_DELAY_S", "3"))
MAX_WORKERS = int(os.getenv("MOCK_FEN_MAX_WORKERS", "8"))
WEBHOOK_MAX_RETRIES = int(os.getenv("MOCK_FEN_WEBHOOK_RETRIES", "3"))
VOTING_MODE = os.getenv("FEN_MOCK_VOTING", "auto")  # "auto" | "community" | "qv"
QUORUM_REQUIRED = int(os.getenv("FEN_MOCK_QUORUM", "3"))     # classic count quorum
QV_THRESHOLD = int(os.getenv("FEN_MOCK_QV_THRESHOLD", "10"))  # QV weighted-score threshold

_decision_counter = itertools.count(1)
_reputation_counter = itertools.count(1)

# In-flight candidate state (UI demo): annotation_id -> record.
_candidates: Dict[str, dict] = {}
# Completed analyses (T3): analysis_id -> section-6 result. In-memory
# demo registry — T4 decisions and T5 provenance read from here; lifetime
# is the process lifetime (labelled simulated/demo in HACKATHON.md).
_analyses: Dict[str, dict] = {}
MAX_ANALYZE_CHARS = 30_000  # total document text limit for POST /analyze (T3)
# Human review decisions (T4): append-only, immutable records. The demo
# event publication appends to _decision_events (in-memory event log,
# labelled simulated); tests inject app.state.decision_publisher instead.
_decisions: list = []
_decision_events: list = []

# Persistence (owner-requested): when FEN_STORE_PATH is set (start_demo.py
# sets artifacts/store.jsonl), analyses + decisions are appended to a JSONL
# log and replayed here on startup, so a restart no longer loses human
# verdicts. Unset (tests, plain uvicorn) = purely in-memory.
_store = store_from_env()


def _reload_store() -> None:
    analyses, decisions = _store.load()
    with _state_lock:
        _analyses.update(analyses)
        _decisions.extend(decisions)
    if analyses or decisions:
        logger.info(
            "store replayed: %d analyses, %d decisions", len(analyses), len(decisions)
        )


class AnalyzeBody(BaseModel):
    """POST /analyze request body (SPEC section 6)."""

    documents: list[SourceDocument] = Field(min_length=1)
    focus: Optional[str] = None
_reputation_history: list = []
# Voter/contributor reputation (demo QV mode): name -> points.
_reputation: Dict[str, int] = {}
_state_lock = threading.Lock()

_reload_store()

# ---- Durable registry (Supabase) -------------------------------------------
# When SUPABASE_DB_URL is set, analyses and human decisions are also written to
# the Supabase database, and GET /registry reads the accepted knowledge from
# there. Unset (offline tests, plain uvicorn) = local JSONL/in-memory only.
_supabase = SupabaseRegistry.from_env()


def get_supabase():
    """Active Supabase writer, or None. Tests inject via app.state.supabase."""
    injected = getattr(app.state, "supabase", None)
    if injected is not None:
        return injected
    return _supabase


def _sync_analysis(stored: dict, documents: list) -> bool:
    """Persist one analysis to Supabase. Never breaks the request."""
    registry = get_supabase()
    if registry is None:
        return False
    try:
        registry.save_analysis(stored, [d.model_dump(mode="json") for d in documents])
        logger.info("supabase: persisted analysis %s", stored.get("analysis_id"))
        return True
    except Exception:  # noqa: BLE001 - durability must not fail the request
        logger.exception("supabase: could not persist analysis %s", stored.get("analysis_id"))
        return False


def _sync_decision(record: dict) -> bool:
    """Record one human decision through the governed Supabase function."""
    registry = get_supabase()
    if registry is None:
        return False
    try:
        registry.record_decision(
            analysis_id=record["analysis_id"],
            item_id=record["item_id"],
            verdict=record["verdict"],
            reviewer=record["reviewer"],
            comment=record.get("comment", ""),
        )
        logger.info("supabase: persisted decision %s", record.get("decision_id"))
        return True
    except Exception:  # noqa: BLE001 - the local record still stands
        logger.exception("supabase: could not persist decision %s", record.get("decision_id"))
        return False

# ---- SSE event bus (real-time UI updates — replaces 3s polling) ------------
_event_subscribers: set = set()
_event_lock = threading.Lock()


def _broadcast(event: str, data: dict) -> None:
    """Fan out an event to all /events subscribers (best-effort, never
    raises — a slow consumer just misses events, the UI re-polls/refreshes).
    A full per-subscriber queue is logged and the stale subscriber evicted so
    it stops being a silent black hole for other clients (TECH-DEBT P2)."""
    payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    with _event_lock:
        for subscriber in list(_event_subscribers):
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                logger.warning("dropping SSE event %r for a slow subscriber (queue full); evicting it", event)
                _event_subscribers.discard(subscriber)


def _subscribe():
    subscriber = queue.Queue(maxsize=100)
    with _event_lock:
        _event_subscribers.add(subscriber)
    return subscriber


def _unsubscribe(subscriber) -> None:
    with _event_lock:
        _event_subscribers.discard(subscriber)

# Bounded pool instead of an unbounded daemon thread per candidate
# (audit finding: daemon threads + sleep can pile up without a limit).
# Lazily created and re-creatable so a graceful shutdown of the pool
# (FastAPI lifespan -> _shutdown_executor) never bricks the process.
_executor: Optional[ThreadPoolExecutor] = None
_executor_shutdown = False


def _get_executor() -> ThreadPoolExecutor:
    global _executor, _executor_shutdown
    if _executor is None or _executor_shutdown:
        _executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="mock-fen")
        _executor_shutdown = False
    return _executor


def _shutdown_executor() -> None:
    """Wait for in-flight deliveries to finish (graceful shutdown)."""
    global _executor_shutdown
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor_shutdown = True

# Optional OpenAI-compatible LLM judge (any provider; DeepSeek by example).
_llm_config = LLMConfig()

_LLM_SYSTEM = (
    "You are a strict validator for a community data-governance layer. "
    "Review the candidate record for factual quality and cultural sensitivity. "
    "Reply with exactly one word: validated, disputed, or rejected."
)


def _record_candidate(candidate: dict) -> None:
    annotation_id = candidate["annotation_id"]
    with _state_lock:
        if annotation_id not in _candidates:
            # LLM/rule recommendation computed ONCE at submission, display-only
            # (ADR-004: the LLM recommends, the community decides; it never
            # votes and its suggestion is not part of the quorum).
            recommendation = _reviewer_recommendation(candidate)
            _candidates[annotation_id] = {
                "annotation_id": annotation_id,
                "document_id": candidate.get("document_id"),
                "entity_label": candidate.get("entity_label"),
                "status": "pending",
                "votes": {"validated": 0, "disputed": 0, "rejected": 0},
                "qv_votes": [],
                "qv_voters": set(),
                "delegations": {},
                "llm_recommendation": recommendation,
                "candidate": dict(candidate),
                "decision": None,
            }


def _set_status(annotation_id: str, status: str, decision: Optional[dict] = None) -> None:
    with _state_lock:
        if annotation_id in _candidates:
            _candidates[annotation_id]["status"] = status
            if decision is not None:
                _candidates[annotation_id]["decision"] = decision


def _apply_reputation(annotation_id: str, outcome: str) -> None:
    """Demo reputation (ADR-005 incentives): ONLY an approved (validated)
    entry rewards its contributor (+2) and the voters of the winning outcome
    (+1). Rejected/disputed proposals award nothing — incentives must not
    reward failed outcomes. Classic-mode votes carry no voter names, so only
    QV-mode votes contribute."""
    if outcome != "validated":
        return
    with _state_lock:
        record = _candidates.get(annotation_id)
        if record is None:
            return
        submitter = record.get("candidate", {}).get("submitter") or "contributor_1"
        _reputation[submitter] = _reputation.get(submitter, 0) + 2
        _reputation_history.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "annotation_id": annotation_id,
            "actor": submitter,
            "delta": 2,
            "reason": "contributor: validated",
        })
        for vote in record.get("qv_votes", []):
            if vote.get("outcome") == outcome and vote.get("voter"):
                voter = vote["voter"]
                _reputation[voter] = _reputation.get(voter, 0) + 1
                _reputation_history.append({
                    "at": datetime.now(timezone.utc).isoformat(),
                    "annotation_id": annotation_id,
                    "actor": voter,
                    "delta": 1,
                    "reason": f"voter: {outcome}",
                })


def _public_state() -> list:
    with _state_lock:
        out = []
        for record in _candidates.values():
            out.append({
                "annotation_id": record["annotation_id"],
                "document_id": record["document_id"],
                "entity_label": record["entity_label"],
                "status": record["status"],
                "votes": dict(record["votes"]),
                "llm_recommendation": record.get("llm_recommendation"),
                "quorum": {
                    "votes": quorum_total(record["votes"]),
                    "required": QUORUM_REQUIRED,
                    "reached": quorum_total(record["votes"]) >= QUORUM_REQUIRED,
                },
                "qv": {
                    "votes": list(record["qv_votes"]),
                    "scores": qv_scores(record["qv_votes"], record["delegations"]),
                    "delegations": dict(record["delegations"]),
                    "threshold": QV_THRESHOLD,
                    "reached": qv_decide(qv_scores(record["qv_votes"], record["delegations"]), QV_THRESHOLD) is not None,
                },
                "decision": record["decision"],
            })
        return out


# ------------------------------------------------------------ decision logic
def _reviewer_recommendation(candidate: dict) -> str:
    """Decision-SUPPORT only (ADR-004): the LLM judge may *recommend* an
    outcome for the DAO to consider — it never votes, never renders a
    governance verdict and never writes gfen:validationStatus. The
    deterministic rule below stands in for the simulated DAO quorum when no
    LLM is configured (demo keeps working without an API key). Generic —
    works for any dataset payload, not just linguistic entities.
    """
    if _llm_config.enabled:
        answer = chat_completion(
            _llm_config,
            _LLM_SYSTEM,
            json.dumps(candidate, ensure_ascii=False),
        )
        recommendation = parse_outcome(answer, OUTCOMES)
        if recommendation:
            MOCK_LLM_JUDGE_CALLS.labels(outcome="success").inc()
            logger.info(
                "LLM judge (decision-support, ADR-004) recommends %r for %s",
                recommendation,
                candidate.get("annotation_id"),
            )
            return recommendation
        MOCK_LLM_JUDGE_CALLS.labels(outcome="fallback").inc()
        logger.warning(
            "LLM judge unavailable/indecisive for %s; falling back to rule",
            candidate.get("annotation_id"),
        )
    # Simulated DAO quorum rule (stands in for real Quadratic Voting).
    # Replace only this branch when wiring up a real DAO backend (ADR-002).
    return "validated" if candidate.get("entity_label") else "rejected"


def _fake_decide(
    candidate: dict, outcome: Optional[str] = None, recommendation: Optional[str] = None
) -> dict:
    """Build a GovernanceDecision-shaped payload. When ``outcome`` is None
    the simulated DAO quorum adopts the reviewer recommendation (auto mode);
    ``recommendation`` may carry the one computed at submission time to avoid
    a second LLM call (ADR-004: recommendation is display-only anyway).
    """
    decision_seq = next(_decision_counter)
    reputation_seq = next(_reputation_counter)
    if outcome is None:
        outcome = recommendation or _reviewer_recommendation(candidate)
        logger.info(
            "simulated DAO quorum adopted %r for %s",
            outcome,
            candidate.get("annotation_id"),
        )
    return {
        "annotation_id": candidate["annotation_id"],
        "document_id": candidate.get("document_id"),
        "decision_id": f"g{decision_seq:05d}",
        "outcome": outcome,
        "method": "quadratic_voting",
        "quorum_reached": True,
        "reputation_snapshot_id": f"r{reputation_seq:05d}",
        "ledger_anchor": f"0xMOCK{decision_seq:08x}",
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }


def _deliver_decision_after_delay(
    candidate: dict, forced_outcome: Optional[str] = None, recommendation: Optional[str] = None
) -> None:
    """Wait the configured delay, then deliver the decision to the webhook
    with a few retries. A lost demo decision is logged, not fatal.
    """
    time.sleep(DECISION_DELAY_S)
    decision = _fake_decide(candidate, outcome=forced_outcome, recommendation=recommendation)
    start = time.perf_counter()
    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            resp = requests.post(WEBHOOK_URL, json=decision, timeout=10)
            resp.raise_for_status()
            MOCK_DELIVERY_SECONDS.observe(time.perf_counter() - start)
            MOCK_DECISIONS_DELIVERED.inc()
            logger.info(
                "delivered mock decision for %s -> %s",
                candidate["annotation_id"],
                decision["outcome"],
            )
            _set_status(candidate["annotation_id"], decision["outcome"], decision)
            _apply_reputation(candidate["annotation_id"], decision["outcome"])
            _broadcast("decision", {"annotation_id": candidate["annotation_id"], "outcome": decision["outcome"]})
            return
        except requests.RequestException:
            logger.exception(
                "failed to deliver mock decision for %s (attempt %d/%d)",
                candidate.get("annotation_id"),
                attempt + 1,
                WEBHOOK_MAX_RETRIES,
            )
            if attempt < WEBHOOK_MAX_RETRIES - 1:
                time.sleep(0.5 * (attempt + 1))
    MOCK_DELIVERY_FAILURES.inc()


# ------------------------------------------------------------------- routes
@app.post("/candidates")
def submit_candidates(payload: dict):
    candidates = payload.get("candidates", [])
    for candidate in candidates:
        _record_candidate(candidate)
        if VOTING_MODE in ("community", "qv"):
            # UI demo modes: wait for votes (POST .../vote).
            logger.info("candidate %s queued for %s voting", candidate["annotation_id"], VOTING_MODE)
        else:
            with _state_lock:
                rec = _candidates.get(candidate["annotation_id"])
                recommendation = rec.get("llm_recommendation") if rec else None
            _get_executor().submit(
                _deliver_decision_after_delay, candidate, None, recommendation
            )
    MOCK_CANDIDATES_ACCEPTED.inc(len(candidates))
    _broadcast("candidates", {"accepted": len(candidates)})
    return {"accepted": len(candidates)}


@app.get("/candidates")
def list_candidates():
    """All in-flight candidates with vote/quorum/QV state + reputation,
    reputation history (ADR-005 incentives) and LLM-judge accuracy over the
    decided ones (recommendation vs community outcome — ADR-004 display-only
    quality signal)."""
    candidates = _public_state()
    with _state_lock:
        reputation = dict(_reputation)
        history = list(reversed(_reputation_history[-50:]))
    decided = [c for c in candidates if c.get("decision")]
    agreements = sum(
        1 for c in decided
        if c.get("llm_recommendation") and c["llm_recommendation"] == c["decision"].get("outcome")
    )
    return {
        "candidates": candidates,
        "mode": VOTING_MODE,
        "qv_threshold": QV_THRESHOLD,
        "reputation": reputation,
        "reputation_history": history,
        "llm_accuracy": {
            "agreements": agreements,
            "total": len(decided),
            "accuracy": (agreements / len(decided)) if decided else None,
        },
    }


@app.post("/candidates/{annotation_id}/vote")
def cast_vote(annotation_id: str, payload: dict):
    """Cast one vote. Two demo modes (web/api.md):

    - ``community`` (classic): one vote per call; quorum = vote count
      (``FEN_MOCK_QUORUM``), outcome = majority.
    - ``qv`` (Quadratic Voting): vote carries an optional ``intensity``
      (1..5, default 1, cost = intensity^2) and optional ``voter``/
      ``comment``; the proposal is decided when an outcome weighted score
      reaches ``FEN_MOCK_QV_THRESHOLD`` (default 10).

    When decided, the outcome is delivered once (claim inside the lock, so a
    concurrent vote sees status != pending and gets 409).
    """
    outcome = payload.get("outcome")
    if outcome not in OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {OUTCOMES}")

    try:
        intensity = int(payload.get("intensity", 1))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"intensity must be an integer 1..{MAX_INTENSITY}") from exc
    if not 1 <= intensity <= MAX_INTENSITY:
        raise HTTPException(status_code=422, detail=f"intensity must be 1..{MAX_INTENSITY}")

    with _state_lock:
        record = _candidates.get(annotation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown annotation_id")
        if record["status"] != "pending":
            raise HTTPException(status_code=409, detail=f"candidate already decided: {record['status']}")
        if VOTING_MODE not in ("community", "qv"):
            raise HTTPException(status_code=409, detail="voting is disabled (FEN_MOCK_VOTING=auto)")

        if VOTING_MODE == "qv":
            voter = payload.get("voter") or f"validator_{len(record['qv_votes']) + 1}"
            if voter in record["qv_voters"]:
                # ADR-005 distinct-identity hint: one person, one vote.
                raise HTTPException(
                    status_code=409,
                    detail=f"voter {voter} has already voted on this proposal",
                )
            record["qv_voters"].add(voter)
            record["qv_votes"].append({
                "outcome": outcome,
                "intensity": intensity,
                "voter": voter,
                "comment": payload.get("comment") or "",
            })
            scores = qv_scores(record["qv_votes"], record["delegations"])
            reached = qv_decide(scores, QV_THRESHOLD) is not None
            final = qv_decide(scores, QV_THRESHOLD) if reached else None
        else:
            record["votes"][outcome] += 1
            scores = None
            total = quorum_total(record["votes"])
            reached = total >= QUORUM_REQUIRED
            final = majority_outcome(record["votes"]) if reached else None

        votes = dict(record["votes"])
        if reached:
            record["status"] = "deciding"

    _broadcast("vote", {"annotation_id": annotation_id, "outcome": outcome, "reached": reached})

    if reached:
        # Deliver with the FULL candidate record (not just the annotation id):
        # the decision must carry document_id so the validation consumer scopes
        # the SPARQL update to the document's named graph
        # (urn:graphia:document:{document_id}:graph).
        _get_executor().submit(_deliver_decision_after_delay, dict(record["candidate"]), final)
        return {
            "annotation_id": annotation_id,
            "votes": votes,
            "qv": {
                "votes": list(record["qv_votes"]),
                "scores": scores,
                "threshold": QV_THRESHOLD,
            },
            "quorum": {"votes": quorum_total(votes), "required": QUORUM_REQUIRED, "reached": True},
            "cost": qv_cost(intensity) if VOTING_MODE == "qv" else 1,
            "outcome": final,
            "note": "decision threshold reached — decision being delivered",
        }
    return {
        "annotation_id": annotation_id,
        "votes": votes,
        "qv": {
            "votes": list(record["qv_votes"]),
            "scores": scores,
            "threshold": QV_THRESHOLD,
        },
        "quorum": {"votes": quorum_total(votes), "required": QUORUM_REQUIRED, "reached": False},
        "cost": qv_cost(intensity) if VOTING_MODE == "qv" else 1,
    }


@app.post("/candidates/{annotation_id}/delegate")
def delegate_vote(annotation_id: str, payload: dict):
    """Liquid democracy (ADR-005 decision 2): a voter who has NOT voted yet
    on this proposal can delegate their weight to another voter. Delegated
    weight follows the delegate's outcome choice in qv_scores. One active
    delegation per voter per proposal (re-delegation replaces it)."""
    voter = (payload.get("voter") or "").strip()
    delegate = (payload.get("delegate") or "").strip()
    with _state_lock:
        record = _candidates.get(annotation_id)
        try:
            apply_delegation(record, voter, delegate, VOTING_MODE)
        except DelegationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    _broadcast("vote", {"annotation_id": annotation_id, "delegation": True, "voter": voter})
    return {
        "annotation_id": annotation_id,
        "delegations": dict(record["delegations"]),
        "note": f"{voter} delegates to {delegate}",
    }


@app.post("/scaffold")
def scaffold(payload: dict):
    """Agentic Scaffolding (Phase 1) — decision-support only (ADR-004).

    Uses the configured OpenAI-compatible LLM (FEN_LLM_*) to structure a
    natural-language statement into a semantic triple with schema hints,
    relationships and ambiguity flags (agents: extractor -> ontology matcher
    -> disambiguator, SHACL check at the end). Generic — works for ANY
    dataset type (framework, not language-specific). Falls back to a
    deterministic rule when no LLM is configured, so the demo works offline.
    Logic lives in mock_fen_api/scaffold.py.
    """
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    with _state_lock:
        registry = [dict(r) for r in _candidates.values()]
    return run_scaffold(text, _llm_config, registry)


@app.post("/analyze")
def analyze(payload: AnalyzeBody):
    """Provenance-aware claim analysis (T3, SPEC section 6) — the model
    proposes, a human decides (ADR-004). The result is stored in the
    in-memory ``_analyses`` registry so T4 decisions and T5 provenance can
    reference its items; its status is always ``proposed``.

    Errors: 422 — invalid input (no/duplicate documents, or more than
    30 000 characters of document text in total); 502 — the model provider
    failed or its response failed the structured contract (after the single
    format-retry inside the service). There is NO fallback to a prepared
    answer. Logic: services/common/analyze.py over
    services/common/analysis.py."""
    document_ids = [d.document_id for d in payload.documents]
    if len(set(document_ids)) != len(document_ids):
        raise HTTPException(status_code=422, detail="duplicate document_id in documents")
    total_chars = sum(len(d.text) for d in payload.documents)
    if total_chars > MAX_ANALYZE_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"documents exceed {MAX_ANALYZE_CHARS} characters in total ({total_chars})",
        )
    try:
        result = analyze_documents(payload.documents, _llm_config, focus=payload.focus)
    except AnalysisUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AnalysisParseError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "invalid_analysis", "errors": exc.errors},
        ) from exc
    stored = {
        **result,
        "_documents": [d.model_dump(mode="json") for d in payload.documents],
    }
    with _state_lock:
        # The stored copy also keeps the source documents so T5 provenance
        # can show document -> quote; the response body stays section-6.
        _analyses[result["analysis_id"]] = stored
    _store.append("analysis", stored)
    _sync_analysis(stored, payload.documents)
    return result


@app.get("/analyses")
def list_analyses():
    """Shared thread for multi-reviewer work: every analysis run on this
    server (newest first), so a second participant opening the Review or
    Demo screen in another tab can join the SAME proposals instead of
    starting from an empty screen. Summaries only; full bodies via
    GET /analyses/{analysis_id}."""
    with _state_lock:
        stored = list(_analyses.values())
    out = []
    for result in reversed(stored):
        pc = result.get("provenance_check") or {}
        out.append({
            "analysis_id": result.get("analysis_id"),
            "created_at": result.get("created_at"),
            "status": result.get("status"),
            "model": result.get("model"),
            "claims_total": pc.get("claims_total"),
            "documents": [
                {"document_id": d.get("document_id"), "title": d.get("title")}
                for d in result.get("_documents", [])
            ],
        })
    return {"analyses": out, "count": len(out)}


@app.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    """One stored analysis in the response shape of POST /analyze, plus
    its source ``documents`` (needed by a joining participant for
    Show-in-source). 404 for an unknown id."""
    with _state_lock:
        stored = _analyses.get(analysis_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="unknown analysis_id")
        body = {k: v for k, v in stored.items() if not k.startswith("_")}
        body["documents"] = stored.get("_documents", [])
    return body


@app.get("/decisions")
def list_decisions(analysis_id: Optional[str] = None):
    """All recorded human decisions (optionally for one analysis), in
    recording order — the shared vote thread every participant sees."""
    with _state_lock:
        records = list(_decisions)
    if analysis_id:
        records = [r for r in records if r.get("analysis_id") == analysis_id]
    return {"decisions": records, "count": len(records)}


@app.post("/decisions", status_code=201)
def create_decision(payload: ReviewDecisionBody):
    """Record a HUMAN decision on one proposed item (T4, SPEC section 6).

    This is the only endpoint that can move an item out of ``proposed``:
    accept -> accepted, reject -> rejected, dispute -> disputed. Rules:
    accept on an unverified quote -> 409; decisions are immutable — a
    repeat decision appends a new record and the old one stays untouched.
    Publishes a ``review-decision`` event (schema:
    schemas/analysis/review-decision.schema.json) via
    ``app.state.decision_publisher`` when injected, otherwise to the
    in-memory demo event log + SSE broadcast.
    """
    with _state_lock:
        analysis = _analyses.get(payload.analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="unknown analysis_id")
    item = find_item(analysis, payload.item_type, payload.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="unknown item_id for this analysis")
    if payload.verdict.value == "accept" and not item_is_verified(item, payload.item_type):
        raise HTTPException(
            status_code=409,
            detail="cannot accept an item with an unverified quote",
        )

    event = build_event(payload)
    record = event.model_dump(mode="json")
    with _state_lock:
        _decisions.append(record)
    _store.append("decision", record)
    supabase_persisted = _sync_decision(record)

    publisher = getattr(app.state, "decision_publisher", None)
    try:
        if callable(publisher):
            publisher(record)
        else:
            with _state_lock:
                _decision_events.append(record)
            _broadcast("decision", record)
        event_published = True
    except Exception:  # noqa: BLE001 - record stands; publication is reported honestly
        logger.exception("decision event publication failed for %s", record["decision_id"])
        event_published = False
    return {
        "decision_id": record["decision_id"],
        "recorded_at": record["recorded_at"],
        "event_published": event_published,
        "supabase_persisted": supabase_persisted,
    }


@app.get("/registry")
def get_registry():
    """Registry showcase: items whose CURRENT status is accepted (latest
    human decision wins), newest first. This is where validated knowledge
    lands in the demo — each entry links to its exportable record.

    With Supabase configured the durable database is the source of truth;
    otherwise the local store answers. `source` says which one answered."""
    registry = get_supabase()
    if registry is not None:
        try:
            records = registry.load_registry()
            return {"records": records, "count": len(records), "source": "supabase"}
        except Exception:  # noqa: BLE001 - keep the demo readable on an outage
            logger.exception("supabase registry read failed; falling back to the local store")
    with _state_lock:
        records = accepted_records(_analyses, list(_decisions))
    return {"records": records, "count": len(records), "source": "local"}


@app.get("/records/{item_id}")
def get_record(item_id: str, analysis_id: Optional[str] = None):
    """Export one DECIDED item as a JSON-LD validation record (claim,
    quote, source documents, model + prompt hash, all human decisions).
    404 — unknown item; 409 — item exists but no human decision yet (a
    model proposal alone is never exportable as a record)."""
    with _state_lock:
        try:
            record = build_record(_analyses, list(_decisions), item_id, analysis_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="unknown item_id")
    return JSONResponse(
        content=record,
        media_type="application/ld+json",
        headers={
            "Content-Disposition": f'attachment; filename="record-{item_id}.jsonld"'
        },
    )


@app.get("/provenance/{item_id}")
def get_provenance(item_id: str, analysis_id: Optional[str] = None):
    """Full provenance chain for one proposed/decided item (T5):
    document -> quote -> model proposal (model, prompt_hash, created_at)
    -> every human decision (reviewer, verdict, comment, recorded_at).
    ``?analysis_id=`` disambiguates reused item ids. 404 when unknown."""
    with _state_lock:
        chain = build_provenance(_analyses, list(_decisions), item_id, analysis_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="unknown item_id")
    return chain


@app.get("/events")
async def events():
    """Server-Sent Events stream: candidates/vote/decision updates for the
    portal and triadic views (replaces 3s polling)."""
    subscriber = _subscribe()

    async def stream():
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                try:
                    yield subscriber.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(1)
        finally:
            _unsubscribe(subscriber)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "note": "this is a DEMO stand-in for FEN's real DAO — see ADR-002"}


@app.get("/readyz")
def readyz():
    """Readiness: the mock depends on nothing external, so it is ready as
    soon as the process serves requests. Its only outbound dependency — the
    FEN Bridge webhook — is probed at delivery time (with retries), not at
    startup, so it must not gate readiness.
    """
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics in text exposition format
    (services/common/metrics.py)."""
    return metrics_response()