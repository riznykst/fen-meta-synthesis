# FEN Web Interface — REST contract (v1)

The web-interface layer (widget + portal) talks only to HTTP APIs. In local
dev the **mock FEN API** (`mock_fen_api`, port 8100) and the **Status API**
(`services/status_api`, port 8082) implement this contract; in production the
real FEN backend (Agentic Scaffolding + DAO, external per ADR-002) must
implement the *same* contract — that is what keeps the UI backend-agnostic.

## Base URLs

| Service | Local dev | Production |
|---|---|---|
| DAO / candidates API | `http://localhost:8100` (mock) | real FEN backend (TBD with consortium) |
| Status API (read) | `http://localhost:8082` | federation-node read endpoint |

Both enable CORS (`FEN_CORS_ORIGINS`, default `*`) so the widget can be
embedded cross-origin.

## 1. Submit candidates — `POST /candidates`

Body (same shape as the Kafka contract `EntityCandidate`):

```json
{ "candidates": [ { "annotation_id": "annotation_a1", "document_id": "d12345", "entity_label": "Sokolowizna", "entity_type": "schema:DefinedTerm" } ] }
```

→ `200 {"accepted": 1}`. Candidates are published with `gfen:pending` and the
pipeline never blocks (D2.2 §4.1).

## 2. List candidates — `GET /candidates`

→ `200 {"candidates": [ {annotation_id, document_id, entity_label, status,
votes, quorum: {votes, required, reached}, decision}]}`

`status`: `pending` | `deciding` | `validated` | `disputed` | `rejected`.

## 3. Cast a community vote — `POST /candidates/{annotation_id}/vote`

```json
{ "outcome": "validated" }
```

- `200` — vote recorded: `{"votes": {...}, "quorum": {votes, required, reached}}`;
  when the quorum is reached the response also carries
  `{"outcome": "<majority>", "note": "quorum reached — decision being delivered"}`.
- `404` — unknown annotation id.
- `409` — community voting disabled (`FEN_MOCK_VOTING=auto`) or candidate already decided.
- `422` — `outcome` not in `validated | disputed | rejected`.

> Real Quadratic Voting is external (ADR-002); this endpoint is the demo
> implementation of the same interface. The LLM judge is decision-support
> only and never counts as a vote (ADR-004).

## 3b. Agentic Scaffolding (Phase 1) — `POST /scaffold`

```json
{ "text": "In the local oral tradition, the hill Koshary marks the old trade route" }
```

→ `200`: `{schema_hints, relationships, ambiguities, triple: {subject,
predicate, object, context, language_or_domain, evidence_type}, source:
"llm" | "rule_fallback"}` — decision-support only (ADR-004): the agent
structures knowledge, it never votes. Generic for any dataset type. Uses the
configured OpenAI-compatible LLM (`FEN_LLM_*`); rule fallback offline.

## 3c. Provenance-aware analysis — `POST /analyze` (T3, SPEC section 6)

```json
{ "documents": [ { "document_id": "d1", "title": "...", "text": "The hill Koshary marks the old trade route." } ] }
```

→ `200`: `{analysis_id, status: "proposed", model: {provider, requested,
returned}, prompt_hash, created_at, latency_ms, analysis: {claims:
[{claim_id, quote, statement, interpretation, document_id, ambiguities,
uncertainty, review_recommendation, quote_verified, provenance_status}],
contradictions: [{contradiction_id, claim_ids, kind, explanation,
alternative_interpretations, quotes_verified}], summary},
provenance_check: {claims_total, quotes_verified, problems, ok}}` —
decision-support only (ADR-004): `status` stays `proposed` until a human
decision is recorded (T4); a successful analysis is **never** approval or
verified truth. `quote` (evidence in the source) and `interpretation`
(model reading) are separate fields. Provenance checks traceability and
evidence location against the documents in *this* request — not truth.

- `422` — invalid input: no/duplicate documents, or more than 30 000
  characters of document text in total (rejected before any provider call).
- `502` — provider failed/not configured, or the model response failed the
  structured contract after the single format-retry
  (`detail.code = "invalid_analysis"`). No fallback to a prepared answer.
  Logic: `services/common/analyze.py` over `services/common/analysis.py`
  and `services/common/llm.py`. Contract schema:
  `schemas/analysis/document-analysis.schema.json`.

## 3d. Human review decision — `POST /decisions` (T4, SPEC section 6)

```json
{ "analysis_id": "an_01...", "item_id": "c1", "item_type": "claim", "verdict": "accept", "comment": "", "reviewer": "reviewer-1" }
```

→ `201 {"decision_id", "recorded_at", "event_published"}`. This is the
**only** way an item leaves `proposed`: `accept → accepted`,
`reject → rejected`, `dispute → disputed` (latest decision wins; records
are immutable and append-only — a repeat decision creates a new record).
Publishes a `review-decision` event
(`schemas/analysis/review-decision.schema.json`; the Kafka
`governance-decision` schema is unchanged and deliberately not reused).

- `404` — unknown `analysis_id` or `item_id`. `409` — `accept` on an item
  whose quote is not verified (reject/dispute still allowed). `422` —
  invalid verdict/body. Demo registry is in-memory (see HACKATHON.md).

## 3e. Provenance chain — `GET /provenance/{item_id}` (T5)

→ `200 {item_id, item_type, analysis_id, status, document, documents,
quotes: [{document_id, quote}], model_proposal: {model, prompt_hash,
created_at, item}, decisions: [{decision_id, reviewer, verdict, status,
comment, recorded_at}], chain_complete}` — the full chain
document → quote → model proposal → human decisions. `?analysis_id=`
disambiguates reused item ids. `404` — unknown item.

## 3f. Voting modes — `POST /candidates/{annotation_id}/vote`

| Mode (`FEN_MOCK_VOTING`) | Semantics |
|---|---|
| `auto` | simulated DAO decides after a delay (no votes) |
| `community` | vote count quorum (`FEN_MOCK_QUORUM`), majority outcome |
| `qv` | Quadratic Voting: vote = `{outcome, intensity (1..5, default 1, cost = intensity²), voter?, comment?}`; decided when an outcome weighted score reaches `FEN_MOCK_QV_THRESHOLD` (default 10) |

The `200` response carries `qv: {votes, scores, threshold}` and `cost`.
Contributor +2 and winning-outcome voters +1 reputation (ADR-005 incentives,
demo) are returned via `GET /candidates` (`reputation` map).

## 4. Validation status (read, widget) — `GET /api/v1/status/{annotation_id}`

Resolved live from the RDF store via SPARQL (named graphs):

- `200` — `{"annotation_id", "found": true, "validation_status",
  "validation_method", "governance_decision_id", "reputation_snapshot",
  "ledger_anchor", "provenance": [...]}` — values are the `gfen:` URIs,
  status as short fragment (`validated`, …).
- `200 {"found": false, "validation_status": "unknown"}` — no governance
  record yet (never extracted or still pending without gfen: triples).
- `503` — RDF store unreachable.

## 4b. Live validation status (SSE, widget) — `GET /api/v1/events/{annotation_id}`

Server-Sent Events stream for one annotation's governance record. Read-only
(ADR-001): the Status API never consumes Kafka — it re-polls the RDF store
every `STATUS_POLL_INTERVAL_S` (default 5s) per connected client and pushes
only **changed** records; a Kafka-fed event bus is a future production
option.

Frames (`text/event-stream`, `Cache-Control: no-cache`):

| Frame | Meaning |
|---|---|
| `event: status` | payload is byte-for-byte the `GET /api/v1/status/{id}` body — sent on connect and whenever the record changes; records that do not exist yet arrive as `{"found": false, "validation_status": "unknown"}` and flip to `validated`/… live |
| `event: error` | RDF store unreachable — retried on the next poll tick (the stream itself stays open) |
| `: ping` | heartbeat comment every `STATUS_SSE_HEARTBEAT_S` (default 15s) so proxies do not kill idle connections |

Consumed by the Flow 2 widget (`<fen-status>`) via `EventSource`, with a 15s
polling fallback over the REST endpoint while the stream is down.

## Notes

- All endpoints are JSON; errors use FastAPI's default `{"detail": ...}`.
- Auth: the webhook (`POST /webhook/decision`) is a *server-to-server*
  callback and requires `FEN_WEBHOOK_TOKEN` outside dev; the read/vote APIs
  are unauthenticated in the demo — production adds OIDC/DAO identity.
- Versioning: contract version `v1`; breaking changes bump the path.
