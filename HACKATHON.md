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
- T5 — Provenance: `GET /provenance/{item_id}` returns the full chain
  (document, quotes, model proposal with `prompt_hash` and time, all human
  decisions in order); unknown id -> 404.
- T6 — Review screen: `web/portal/review.html` + `review.js` (zero-build,
  triadic style): document input, model-waiting state, proposal cards,
  contradiction cards (both claims, kind, alternative interpretations),
  red unverified-quote cards with Accept disabled, decision history +
  provenance panel, plain-language 502 text. Buttons >= 44 px, responsive
  at 390 px. 10 Node tests on the pure render/status functions.
- T7 — Measurements: `eval/run_eval.py` computes json_valid_rate,
  quote_verified_rate, claim recall/precision, contradiction recall and
  false-positive rate (quote matching: normalised equality or token
  overlap >= 0.8), plus the B0 baseline (unverified share that would pass
  without provenance checking). First runs exist on the SYNTHETIC smoke
  example only (fixture + one live Meta run, 2026-10-28) — harness proof,
  not corpus quality; see `eval/REPORT.md`. Real measurements await the
  human-supplied dataset (T8); the B1 Baseten comparison awaits access
  (OPEN_QUESTIONS Q4).
- Real Sumerian corpus and gold standards: supplied by the human only (T8);
  the agent never generates them. Agent-made T8 artefacts are only
  `eval/dataset/TEMPLATE.json` and `eval/validate_dataset.py` (the gate
  also refuses examples without a human-checked source licence).
- T9 — Demo & docs: `DEMO.md` (3-minute independent scenario, including the
  offline SYNTHETIC fixture segment for the caught unverified quote),
  one-command launcher `scripts/start_demo.py` (+ `scripts/demo_seed.sh`
  wrapper; verified end-to-end live 2026-10-28), and the README
  "Hackathon Scope" section.
- T10 — Hygiene: `.gitignore` covers `.env`, key material and `artifacts/`
  (live responses stay local until human-approved, Q8). Secret scan
  2026-10-28: gitleaks is not installed in this environment, so the
  equivalent manual scan was run — the owner's actual API key string and
  long Bearer-token patterns were searched across all 216 commits of git
  history and both local artifacts: **0 hits**. `LICENSE` (Apache-2.0) is
  in place; data-licence gating lives in the T8 validator. A clean-export
  test run (committed tree only) passes the full suites — see the T10
  commit verification.

- Post-T10 frontend improvements (owner-requested): portal navigation now
  links the Review screen as the hackathon demo entry; the Review screen
  highlights a proposal's quote inside its source document
  (`findQuoteRange`/`highlightQuoteHtml`, whitespace-tolerant, escaped);
  an optional third source document can be added; Playwright e2e covers
  the Review flow with an intercepted (SYNTHETIC) API.

## Rule that never moves

The model only *proposes*. No code path assigns a claim the status
`accepted` without a recorded human decision (SPEC section 0.8;
ADR-004).
