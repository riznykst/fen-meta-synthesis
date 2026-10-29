# LLM Providers — FEN × Meta (T1)

All providers are reached through the single existing client,
`services/common/llm.py` (OpenAI-compatible chat completions). No
provider-specific SDK is used. Credentials come only from environment
variables and are never logged or returned (`chat_completion_detailed`
returns text, `model_returned`, `usage`, `finish_reason` — never headers).

| Setting | Value |
|---|---|
| `FEN_LLM_BASE_URL` | provider base URL (see below) |
| `FEN_LLM_API_KEY` | secret; Bearer auth when present |
| `FEN_LLM_MODEL` | requested model id |
| `FEN_LLM_TIMEOUT_S` | per-call timeout, default 30 |
| `FEN_LLM_SYSTEM_ROLE` | first-message role, default `system` |
| `FEN_LLM_JSON_MODE` | `1`/`true` → send `response_format={"type":"json_object"}` by default |
| `FEN_LLM_STRUCTURED_OUTPUT` | `1`/`true` → allow `response_format={"type":"json_schema"}` (schema-constrained decoding); `POST /analyze` enables it automatically for `api.meta.ai` |

Behaviour: temperature 0; **exactly one retry on network errors**
(connection error / timeout); HTTP errors and malformed envelopes are not
retried; the client never raises — it returns `None` and the caller decides
(no silent fallback to prepared answers in the analysis workflow).

## Meta Model API — primary provider (hackathon)

- Base URL: `https://api.meta.ai/v1`; model: `muse-spark-1.3`.
- **Confirmed live on 2026-10-28** through this client (chat completions,
  `system` role accepted): minimal smoke returned the expected token, and a
  structured `/analyze` call returned valid JSON claims. Official docs list
  chat completions as a supported surface and recommend the Responses API
  as the full-feature surface; FEN keeps the chat surface because the
  existing client and ADR-004 reviewer flows already speak it.
- JSON mode: supported by the provider; FEN sends it only when enabled
  (`FEN_LLM_JSON_MODE=1` or per-call), so other providers are unaffected.
- **Structured output (schema-constrained decoding): `POST /analyze`
  sends `response_format={"type":"json_schema"}` with the canonical
  analysis contract (`services/common/analysis.py::analysis_json_schema`,
  the same schema as `schemas/analysis/document-analysis.schema.json`,
  minus the legacy input alias) for Meta endpoints — decoding itself is
  constrained to the contract, per Meta's structured-output docs
  (https://dev.meta.ai/docs/structured-output). Verified live 2026-10-28:
  `muse-spark-1.3` accepted the schema and returned 2 claims, both quotes
  verified, `response_format: "json_schema"` recorded in the result.
  Other providers keep `json_object`; `parse_analysis` still validates
  every response regardless of provider guarantees. Deliberately no silent
  fallback: if a provider rejects the schema (HTTP 400), the analysis
  fails with 502 rather than quietly downgrading to `json_object` — a
  schema change must be a visible event, not a hidden behaviour change.
- Smoke: `python scripts/live_smoke.py` (loads `FEN_LLM_*` from the
  process env or a repo-root `.env`) writes the sanitized artifact
  `artifacts/meta/first_live_response.json` — request, response, requested
  and returned model, usage. Artifacts are committed only after human
  review (SPEC 0.6).

## Other OpenAI-compatible endpoints (pre-existing capability)

OpenAI, DeepSeek, local vLLM/Ollama, or GRAPHIA services (LLM4SSH/Quagga)
work unchanged by setting the three `FEN_LLM_*` variables — this predates
the hackathon and is covered by `tests/test_llm.py`.

## Baseten (`muse-spark-open-1026`) — planned, not verified

Intended only as the B1 comparison provider in the T7 evaluation. Access
and the exact model id are **not yet verified** (OPEN_QUESTIONS Q4); nothing
in the codebase claims it works until a live call through this same client
succeeds and is recorded.
