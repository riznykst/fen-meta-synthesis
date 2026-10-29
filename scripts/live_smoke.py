"""Meta Model API live smoke test through FEN's LLM client (T1).

Sends ONE minimal prompt via ``services.common.llm.chat_completion_detailed``
(the detailed form of ``chat_completion``; no separate SDK) and writes the
sanitized result to ``artifacts/meta/first_live_response.json`` — request,
response, requested/returned model, usage, finish_reason — never the API
key or any authorization header.

Configuration comes from the process environment (``FEN_LLM_BASE_URL``,
``FEN_LLM_API_KEY``, ``FEN_LLM_MODEL``, ``FEN_LLM_TIMEOUT_S``). For
convenience this script first loads a repo-root ``.env`` file if present
(only ``FEN_LLM_*`` keys; existing environment values win) — note that
``services/common/llm.py`` itself reads the environment only, so services
started with uvicorn still need the variables exported in their shell.

Exit codes: 0 — real provider response saved; 2 — LLM not configured;
1 — provider call failed (chat_completion returned None; the underlying
exception is logged by services.common.llm, which never raises).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

ARTIFACT = REPO_ROOT / "artifacts" / "meta" / "first_live_response.json"
ENV_KEYS = (
    "FEN_LLM_BASE_URL",
    "FEN_LLM_API_KEY",
    "FEN_LLM_MODEL",
    "FEN_LLM_TIMEOUT_S",
    "FEN_LLM_SYSTEM_ROLE",
    "FEN_LLM_JSON_MODE",
    "FEN_LLM_STRUCTURED_OUTPUT",
)

SYSTEM_PROMPT = "You are a connectivity test assistant. Reply with exactly: FEN_META_OK"
USER_PROMPT = "Reply with FEN_META_OK"


def load_dotenv(path: Path) -> None:
    """Load FEN_LLM_* values from a simple KEY=VALUE .env file.

    Existing environment variables are never overwritten; values are never
    printed."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in ENV_KEYS and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")

    from services.common.llm import LLMConfig, chat_completion_detailed

    config = LLMConfig()
    print(f"FEN_LLM_BASE_URL: {config.base_url or '(not set)'}")
    print(f"FEN_LLM_MODEL: {config.model}")
    print(f"FEN_LLM_API_KEY: {'set (len=' + str(len(config.api_key)) + ')' if config.api_key else '(not set)'}")
    if not config.enabled:
        print("FAIL: LLM not configured — set FEN_LLM_BASE_URL (and FEN_LLM_API_KEY) first.")
        return 2

    result = chat_completion_detailed(config, SYSTEM_PROMPT, USER_PROMPT)
    if result is None:
        print(
            "FAIL: chat_completion returned None — provider unreachable, "
            "rejected the request, or returned a malformed envelope. "
            "See the logged exception above for the underlying error."
        )
        return 1

    artifact = {
        "provider": "meta",
        "provider_base_url": config.base_url,
        "model_requested": config.model,
        "model_returned": result.model_returned,
        "usage": result.usage,
        "finish_reason": result.finish_reason,
        "api_key_present": bool(config.api_key),
        "via": "services.common.llm.chat_completion_detailed",
        "endpoint": f"{config.base_url.rstrip('/')}/chat/completions",
        "request": {"system": SYSTEM_PROMPT, "user": USER_PROMPT},
        "response_text": result.text,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "note": "Sanitized live-response artifact: no API key or authorization header included.",
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: real provider response saved to {ARTIFACT.relative_to(REPO_ROOT)}")
    print(f"Response: {result.text[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
