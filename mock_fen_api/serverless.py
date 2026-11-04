"""Serverless demo API for the hosted MVP (Vercel Python function).

The local demo keeps state in process memory; a serverless function does not,
so every endpoint here is backed by Supabase (`SUPABASE_DB_URL`). Behaviour and
response shapes match `mock_fen_api.main` and web/api.md, so the same frontend
works against both.

Mounted by `api/index.py` under `/api/index`, which strips that prefix.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from mock_fen_api.decisions import ReviewDecisionBody, build_provenance
from mock_fen_api.supabase_registry import SupabaseError, SupabaseRegistry
from services.common.analysis import AnalysisParseError, SourceDocument
from services.common.analyze import analyze_documents

logger = logging.getLogger("fen_serverless")

MAX_ANALYZE_CHARS = 30_000


class AnalyzeBody(BaseModel):
    documents: list[SourceDocument] = Field(min_length=1)
    focus: Optional[str] = None


app = FastAPI(title="FEN demo API (serverless, Supabase-backed)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("FEN_CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def registry() -> SupabaseRegistry:
    reg = SupabaseRegistry.from_env()
    if reg is None:
        raise HTTPException(
            status_code=503,
            detail="registry not configured: set SUPABASE_DB_URL on the deployment",
        )
    return reg


@app.get("/healthz")
def healthz():
    return {"status": "ok", "mode": "serverless", "storage": "supabase" if os.getenv("SUPABASE_DB_URL") else "none"}


@app.get("/readyz")
def readyz():
    configured = bool(os.getenv("SUPABASE_DB_URL")) and bool(os.getenv("FEN_LLM_BASE_URL"))
    return {
        "status": "ok" if configured else "degraded",
        "llm": "configured" if os.getenv("FEN_LLM_BASE_URL") else "missing FEN_LLM_BASE_URL",
        "database": "configured" if os.getenv("SUPABASE_DB_URL") else "missing SUPABASE_DB_URL",
    }


@app.post("/analyze")
def analyze(payload: AnalyzeBody):
    ids = [d.document_id for d in payload.documents]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="duplicate document_id in documents")
    total = sum(len(d.text) for d in payload.documents)
    if total > MAX_ANALYZE_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"documents exceed {MAX_ANALYZE_CHARS} characters in total ({total})",
        )
    try:
        result = analyze_documents(payload.documents, None, focus=payload.focus)
    except Exception as exc:  # AnalysisUnavailable / AnalysisParseError and friends
        name = type(exc).__name__
        status = 502
        detail = {"code": "invalid_analysis", "errors": getattr(exc, "errors", [str(exc)])} \
            if name == "AnalysisParseError" else str(exc)
        raise HTTPException(status_code=status, detail=detail) from exc

    try:
        registry().save_analysis(
            result, [d.model_dump(mode="json") for d in payload.documents]
        )
    except SupabaseError as exc:
        # The analysis itself is valid; failing to persist must not fake success.
        logger.exception("analysis %s was produced but not persisted", result.get("analysis_id"))
        raise HTTPException(status_code=503, detail=f"analysis produced but not stored: {exc}") from exc
    return result


@app.get("/analyses")
def list_analyses():
    try:
        items = registry().list_analyses(limit=20)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"analyses": items, "count": len(items)}


@app.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    try:
        body = registry().load_analysis(analysis_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if body is None:
        raise HTTPException(status_code=404, detail="unknown analysis_id")
    return body


@app.get("/decisions")
def list_decisions(analysis_id: Optional[str] = None):
    try:
        records = registry().list_decisions(analysis_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"decisions": records, "count": len(records)}


@app.post("/decisions", status_code=201)
def create_decision(payload: ReviewDecisionBody):
    reg = registry()
    try:
        body = reg.load_analysis(payload.analysis_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if body is None:
        raise HTTPException(status_code=404, detail="unknown analysis_id")

    bucket = body["analysis"]["claims"] if payload.item_type == "claim" else body["analysis"]["contradictions"]
    item = next((i for i in bucket if (i.get("claim_id") or i.get("contradiction_id")) == payload.item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="unknown item_id for this analysis")

    verified = item.get("quote_verified") if payload.item_type == "claim" else item.get("quotes_verified")
    if payload.verdict.value == "accept" and not verified:
        raise HTTPException(status_code=409, detail="cannot accept an item with an unverified quote")

    try:
        recorded = reg.record_decision(
            payload.analysis_id,
            payload.item_id,
            payload.verdict.value,
            payload.reviewer,
            payload.comment,
        )
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "decision_id": recorded["decision_id"],
        "recorded_at": recorded["recorded_at"],
        "event_published": False,
    }


@app.get("/provenance/{item_id}")
def provenance(item_id: str, analysis_id: Optional[str] = None):
    reg = registry()
    try:
        if analysis_id:
            body = reg.load_analysis(analysis_id)
            if body is None:
                raise HTTPException(status_code=404, detail="unknown analysis_id")
            analyses = {analysis_id: {**body, "_documents": body.get("documents", [])}}
        else:
            analyses = {}
            for summary in reg.list_analyses(limit=20):
                loaded = reg.load_analysis(summary["analysis_id"])
                if loaded:
                    analyses[summary["analysis_id"]] = {
                        **loaded,
                        "_documents": loaded.get("documents", []),
                    }
        decisions = reg.list_decisions(analysis_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    chain = build_provenance(analyses, decisions, item_id, analysis_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="unknown item_id")
    return chain


@app.get("/registry")
def list_registry():
    reg = registry()
    try:
        records = reg.load_registry()
        decisions = reg.list_decisions()
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # The local API attaches votes to every registry record; the SQL view does
    # not, so rebuild them here — the UI must not claim "decided by 0 reviewers"
    # for an item that a human actually accepted.
    by_item: dict[tuple[str, str], list] = {}
    for decision in decisions:
        by_item.setdefault((decision["analysis_id"], decision["item_id"]), []).append(decision)
    for record in records:
        votes = by_item.get((record.get("analysis_id"), record.get("item_id")), [])
        record["votes"] = [
            {
                "reviewer": v["reviewer"],
                "verdict": v["verdict"],
                "recorded_at": v["recorded_at"],
            }
            for v in votes
        ]
        record["voter_count"] = len({v["reviewer"] for v in votes})
    return {"records": records, "count": len(records)}


@app.get("/records/{item_id}")
def export_record(item_id: str, analysis_id: Optional[str] = None):
    chain = provenance(item_id, analysis_id)
    if chain.get("status") not in ("accepted", "rejected", "disputed"):
        raise HTTPException(status_code=409, detail="no human decision recorded for this item yet")
    return JSONResponse(
        content=chain,
        media_type="application/ld+json",
        headers={"Content-Disposition": f'attachment; filename="record-{item_id}.jsonld"'},
    )
