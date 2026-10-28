"""Analysis service (T2): documents -> Meta model -> validated proposals.

Uses ``build_system_prompt`` / ``build_user_prompt`` / ``parse_analysis`` /
``verify_provenance`` from :mod:`services.common.analysis` and the provider
client from :mod:`services.common.llm` (``chat_completion_detailed``).

Failure policy (SPEC T2/T3) — no prepared answers, no silent substitution:

- Provider not configured / provider failure -> :class:`AnalysisUnavailable`
  (the endpoint maps this to 502; "not configured" stays distinguishable in
  the message).
- Unparseable model output -> exactly ONE retry with a short format
  reminder; if that also fails, :class:`AnalysisParseError` is raised and
  the raw answers are preserved under ``artifacts/analysis-failures/``
  (model output only — never credentials) for human inspection.
- A result is always ``status="proposed"``: the model recommends, a human
  decides (T4). Nothing here can mark a claim accepted.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from services.common.analysis import (
    AnalysisParseError,
    SourceDocument,
    build_system_prompt,
    build_user_prompt,
    parse_analysis,
    verify_provenance,
)
from services.common.llm import LLMConfig, chat_completion_detailed

logger = logging.getLogger(__name__)

# Dict-shaped result (SPEC section 6 response body).
AnalysisResult = dict

_FAILURES_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "analysis-failures"

_FORMAT_REMINDER = (
    "\n\nReminder: reply with ONLY valid JSON matching the contract from the "
    "system prompt — no markdown, no code fences, no extra fields."
)


class AnalysisUnavailable(RuntimeError):
    """LLM provider not configured or returned nothing usable."""


def _prompt_hash(system: str, user: str) -> str:
    digest = hashlib.sha256(f"{system}\n{user}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _preserve_raw(analysis_id: str, answers: List[Optional[str]], errors: List[str]) -> None:
    """Save raw model answers for a failed analysis under artifacts/.

    Best-effort: a write failure is logged and never masks the parse error.
    Contains model output and parse errors only — no credentials, no request
    headers."""
    try:
        _FAILURES_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "analysis_id": analysis_id,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "errors": errors,
            "raw_answers": answers,
        }
        (_FAILURES_DIR / f"{analysis_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001 - preservation must not mask the real error
        logger.exception("could not preserve raw analysis answers for %s", analysis_id)


def analyze_documents(
    documents: List[SourceDocument],
    config: Optional[LLMConfig] = None,
    focus: Optional[str] = None,
) -> AnalysisResult:
    """Run the full workflow once (plus the single format-retry on bad JSON).

    Returns the SPEC section 6 response body: ``{analysis_id, status,
    model, prompt_hash, created_at, latency_ms, analysis, provenance_check}``
    plus provider ``usage`` when the envelope carried it."""
    config = config or LLMConfig()
    if not config.enabled:
        raise AnalysisUnavailable(
            "LLM not configured (set FEN_LLM_BASE_URL / FEN_LLM_API_KEY / FEN_LLM_MODEL)"
        )

    analysis_id = f"an_{uuid.uuid4().hex[:12]}"
    system = build_system_prompt()
    user = build_user_prompt(documents, focus)
    prompt_hash = _prompt_hash(system, user)
    started = time.perf_counter()

    result = chat_completion_detailed(config, system, user, json_mode=True)
    if result is None:
        raise AnalysisUnavailable("LLM provider unavailable or returned an unusable response")

    try:
        draft = parse_analysis(result.text)
    except AnalysisParseError as first_error:
        logger.warning(
            "analysis %s: first response failed the contract (%s); one format retry",
            analysis_id,
            first_error.errors[:2],
        )
        retry = chat_completion_detailed(config, system, user + _FORMAT_REMINDER, json_mode=True)
        if retry is None:
            _preserve_raw(analysis_id, [result.text], first_error.errors)
            raise AnalysisUnavailable(
                "LLM provider unavailable on the format-retry call"
            ) from first_error
        try:
            draft = parse_analysis(retry.text)
        except AnalysisParseError as second_error:
            _preserve_raw(analysis_id, [result.text, retry.text], second_error.errors)
            raise
        result = retry

    verified = verify_provenance(draft, documents)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "analysis_id": analysis_id,
        "status": "proposed",
        "model": {
            "provider": "meta" if "api.meta.ai" in (config.base_url or "") else "openai-compatible",
            "requested": config.model,
            "returned": result.model_returned,
        },
        "usage": result.usage,
        "prompt_hash": prompt_hash,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "latency_ms": latency_ms,
        "analysis": {
            "claims": verified["claims"],
            "contradictions": verified["contradictions"],
            "summary": draft.summary,
        },
        "provenance_check": verified["provenance_check"],
    }
