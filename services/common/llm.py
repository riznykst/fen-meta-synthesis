"""Pluggable LLM provider — OpenAI-compatible chat API.

Lets the demo/validation layer talk to ANY OpenAI-compatible endpoint for
testing: OpenAI, DeepSeek, local vLLM/Ollama, Meta Model API
(https://api.meta.ai/v1, e.g. muse-spark-1.3 — confirmed live through this
client on 2026-10-28), or GRAPHIA's own services (LLM4SSH / Quagga) if they
expose such an API. Configured purely via env:

    FEN_LLM_BASE_URL     e.g. https://api.meta.ai/v1 (Meta) or https://api.deepseek.com/v1
    FEN_LLM_API_KEY      secret token (never logged, never returned)
    FEN_LLM_MODEL        e.g. muse-spark-1.3, deepseek-chat, gpt-4o-mini
    FEN_LLM_TIMEOUT_S    default 30
    FEN_LLM_SYSTEM_ROLE  first-message role, default "system" (Meta accepts
                         "system" — confirmed live; switch only if a
                         provider's documented interface requires it)
    FEN_LLM_JSON_MODE    "1"/"true" to request response_format=json_object
                         by default where the provider supports it
    FEN_LLM_STRUCTURED_OUTPUT
                         "1"/"true" to allow callers to request
                         response_format=json_schema (schema-constrained
                         decoding, Meta Model API) — used by the analysis
                         service; enabled automatically for api.meta.ai

The provider never raises: callers get ``None`` on any failure so the
pipeline can fall back to a deterministic rule (no blocking points).
Network errors (connection error / timeout) are retried exactly once;
HTTP errors and malformed responses are not retried (T1 requirement —
retries must be predictable and must not multiply spending silently).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    """Detailed result of one successful chat completion (T1).

    ``text`` is the assistant message; ``model_returned`` / ``usage`` /
    ``finish_reason`` are whatever the provider envelope carried (``None``
    when the provider did not expose them). Never contains credentials."""

    text: str
    model_returned: Optional[str] = None
    usage: Optional[dict] = None
    finish_reason: Optional[str] = None


class LLMConfig:
    """Env-driven LLM settings; ``enabled`` is True only when a base URL is set."""

    def __init__(self) -> None:
        self.base_url: Optional[str] = os.getenv("FEN_LLM_BASE_URL") or None
        self.api_key: Optional[str] = os.getenv("FEN_LLM_API_KEY") or None
        self.model: str = os.getenv("FEN_LLM_MODEL", "deepseek-chat")
        self.timeout_s: float = float(os.getenv("FEN_LLM_TIMEOUT_S", "30"))
        self.system_role: str = os.getenv("FEN_LLM_SYSTEM_ROLE", "system") or "system"
        self.json_mode: bool = (os.getenv("FEN_LLM_JSON_MODE", "") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        self.structured_output: bool = (
            os.getenv("FEN_LLM_STRUCTURED_OUTPUT", "") or ""
        ).lower() in ("1", "true", "yes")
        # Meta's API accepts reasoning_effort; "low" cuts the hidden reasoning
        # tokens substantially, which is what makes a 3-document analysis fit
        # inside a 60 s serverless invocation. Unset means provider default.
        self.reasoning_effort: Optional[str] = os.getenv("FEN_LLM_REASONING_EFFORT") or None

    @property
    def enabled(self) -> bool:
        return self.base_url is not None


def chat_completion_detailed(
    config: LLMConfig,
    system: str,
    user: str,
    json_mode: Optional[bool] = None,
    json_schema: Optional[dict] = None,
    schema_name: str = "StructuredOutput",
) -> Optional[LLMResult]:
    """Call POST {base_url}/chat/completions with a single-turn prompt.

    Returns an :class:`LLMResult` (text + provider metadata), or None on
    any failure/irregular response — callers must handle None (fallback
    path). Exactly one retry, and only after a network error
    (connection error / timeout).

    Output shaping: when ``json_schema`` (a JSON Schema dict) is given, the
    request carries ``response_format={"type": "json_schema", ...}`` so the
    provider constrains decoding to the schema (Meta Model API structured
    output); this takes precedence over the weaker ``json_mode``
    (``json_object``), kept for providers without schema support. The schema
    is sent without ``strict`` (Meta treats output as schema-constrained
    either way; omitting it accepts schemas outside the strict subset)."""
    if not config.enabled:
        return None
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload = {
        "model": config.model,
        "messages": [
            {"role": config.system_role, "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }
    if config.reasoning_effort:
        payload["reasoning_effort"] = config.reasoning_effort
    if json_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": json_schema},
        }
    else:
        effective_json_mode = config.json_mode if json_mode is None else json_mode
        if effective_json_mode:
            # JSON mode where the provider supports it (Meta chat completions
            # supports structured/JSON output); opt-in so providers without it
            # are never broken by default.
            payload["response_format"] = {"type": "json_object"}

    for attempt in range(2):  # initial call + exactly one network retry
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=config.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return LLMResult(
                text=choice["message"]["content"],
                model_returned=data.get("model"),
                usage=data.get("usage"),
                finish_reason=choice.get("finish_reason"),
            )
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 0:
                logger.warning("LLM call to %s failed (network); retrying once", url)
                continue
            logger.exception("LLM call to %s failed after one retry", url)
            return None
        except Exception:  # noqa: BLE001 - the provider must never raise (fail-open contract)
            logger.exception("LLM call to %s failed", url)
            return None
    return None


def chat_completion(
    config: LLMConfig,
    system: str,
    user: str,
    json_mode: Optional[bool] = None,
    json_schema: Optional[dict] = None,
    schema_name: str = "StructuredOutput",
) -> Optional[str]:
    """Backward-compatible text-only wrapper around
    :func:`chat_completion_detailed` (existing callers keep working)."""
    result = chat_completion_detailed(
        config, system, user, json_mode=json_mode, json_schema=json_schema, schema_name=schema_name
    )
    return result.text if result is not None else None


def parse_outcome(text: Optional[str], allowed: tuple) -> Optional[str]:
    """Extract one of ``allowed`` outcomes from a free-form LLM answer.

    Accepts the bare word or a line containing it (case-insensitive).
    """
    if not text:
        return None
    lowered = text.lower()
    for candidate in allowed:
        if candidate in lowered:
            return candidate
    return None
