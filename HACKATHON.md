# FEN × Meta — Hackathon Boundary Record

Project: FEN Triadic Synthesis — Human-Governed AI Synthesis
(Meta Global AI Developer Hackathon; submission deadline 4 November, 21:00 ET)
Branch: `hackathon/meta-ai-synthesis` (never `main`)

This file separates what existed before the hackathon from what is built
during it. It is updated by every task commit that moves that boundary
(SPEC section 4). Nothing is called "implemented" here without a test or a
reproducible run behind it (SPEC section 0.7).

## Baseline (before the hackathon)

- Baseline tag: `baseline-pre-hackathon`
  -> `8c1164da2ac209c1f325f16c8bebbf4dabae82d0`
  (= `v0.2.8`; also the result of `git log --before="2026-10-27" -1` on `main`,
  verified 2026-10-28. A commit timestamp does not by itself prove when code
  was authored.)
- Test baseline on that commit: **125 pytest passed, 18 Node tests passed**
  (`python -m pytest -q`; `node --test web/tests/*.test.js`).
- Already in `main` (research MVP, audited 2026-10-27/28): Kafka -> Fuseki
  (RDF) -> PID pipeline; `services/common/llm.py` OpenAI-compatible client
  (`FEN_LLM_BASE_URL` / `FEN_LLM_API_KEY` / `FEN_LLM_MODEL`);
  `mock_fen_api/` demo DAO + `scaffold.py` (one statement -> triple, SHACL
  check); Kafka contracts in `schemas/kafka-events/`; web portal and widget.

### Honest discrepancy (do not rewrite)

The hackathon SPEC (section 3) states that a patch `fen-analysis-contract.patch`
(`services/common/analysis.py`, `schemas/analysis/document-analysis.schema.json`,
`tests/test_analysis.py`, +12 tests = 137, Review mock-up) was prepared before
the hackathon. **That patch and those files do not exist in this repository**
(verified by audit 2026-10-28: no `*.patch` file, none of the listed paths,
baseline is 125 tests, not 137). They are therefore NOT claimed as
pre-hackathon work. The analysis contract is implemented *during* the
hackathon (tasks T2/T3). See `docs/OPEN_QUESTIONS.md` Q1.

## Implemented during the hackathon

Each line names the task commit that introduced it.

- T1 — Meta Model API client: `services/common/llm.py` extended without
  breaking its API (`chat_completion_detailed` returns text +
  `model_returned`/`usage`/`finish_reason`; one retry on network errors
  only; configurable `system` role; opt-in JSON mode), `docs/PROVIDERS.md`,
  `scripts/live_smoke.py`. Live verification 2026-10-28: real calls to
  `https://api.meta.ai/v1` (`muse-spark-1.3`) returned `FEN_META_OK`
  (`model_returned=muse-spark-1.3`, usage recorded); sanitized evidence in
  `artifacts/meta/first_live_response.json` (artifacts are not committed
  without human review — SPEC section 0.6).
- T2 — Analysis service: canonical contract in `services/common/analysis.py`
  (claims with exact `quote` + separate `interpretation`, contradictions,
  JSON Schema in `schemas/analysis/document-analysis.schema.json`) and
  `services/common/analyze.py` (`analyze_documents` -> section 6 result with
  `analysis_id`, `prompt_hash`, requested/returned model, `latency_ms`,
  `provenance_check`; exactly one format-retry, raw failures preserved
  under `artifacts/`). An earlier working implementation
  (`mock_fen_api/analysis.py`, live 200 with 4 claims on `muse-spark-1.3`,
  2026-10-28) informed this contract; its legacy field aliases remain
  parseable.
- T3 — `POST /analyze` endpoint in `mock_fen_api/main.py` on the canonical
  service: section 6 request/response, 422 on invalid input (including the
  30 000-character total limit, checked before any provider call), 502 on
  provider/contract failure, no prepared-answer fallback; results stored
  in the in-memory `_analyses` registry for T4/T5. Live-verified
  2026-10-28 on `muse-spark-1.3` (4 claims, all quotes verified, one
  `temporal_mismatch` contradiction with alternative interpretations).

## Simulated / planned (never presented as production)

- The DAO / Quadratic Voting behind `mock_fen_api/` is a **simulation**
  (ADR-002); no real DAO, token, or blockchain anchoring exists here
  (`0xMOCK` ledger anchors).
- Human-review registry for hackathon decisions (T4/T5): demo-scope store
  unless a task explicitly wires a persistent backend.
- T4 — Human decisions: `POST /decisions` (separate `review-decision`
  event schema in `schemas/analysis/review-decision.schema.json`; the Kafka
  governance schema is unchanged). Accept on an unverified quote -> 409;
  decisions are immutable/append-only. Registry and default event log are
  in-memory demo scope (process lifetime), as recorded in OPEN_QUESTIONS Q7.
- Quality measurements (T7) and the second-provider comparison (Baseten,
  `muse-spark-open-1026`) are **planned** until a real dataset (T8, supplied
  by the human) and provider access exist.
- Real Sumerian corpus and gold standards: supplied by the human only (T8);
  the agent never generates them.

## Rule that never moves

The model only *proposes*. No code path assigns a claim the status
`accepted` without a recorded human decision (SPEC section 0.8;
ADR-004).
