# Open Questions — FEN × Meta Hackathon

Questions that block or constrain a task are recorded here instead of being
silently decided (SPEC section 0.3). Status is updated as the human answers.

## Q1. Missing pre-hackathon analysis-contract patch — SPEC section 3
SPEC states `fen-analysis-contract.patch` (with `services/common/analysis.py`,
`schemas/analysis/document-analysis.schema.json`, `tests/test_analysis.py`,
+12 tests = 137, and a Review mock-up) was prepared before the hackathon.
Audit of this repository on 2026-10-28 found: no `*.patch` file anywhere in
the tree, none of the listed files, and a test baseline of 125 pytest
(not 137). **Decision taken (reversible):** the contract is implemented
during the hackathon under T2/T3 and is not claimed as pre-hackathon work;
`HACKATHON.md` records the discrepancy. If the patch exists outside the
repo, the human can supply it and the boundary record will be corrected.

## Q2. Organisers' answer on existing projects (indie category)
SPEC section 9.1. Unresolved; external to the codebase. Does not block
engineering, may block submission wording. Owner: human.

## Q3. Meta Model API confirmed values — PARTIALLY RESOLVED
Candidates in SPEC: base URL `https://api.meta.ai/v1`, model
`muse-spark-1.3`, `system` role. Resolution evidence (2026-10-28): a live
call through `services/common/llm.py` with exactly these values returned the
expected response (`FEN_META_OK`), and a live `POST /analyze` returned
structured JSON claims. So base URL, model name and the `system` role are
confirmed by actual API behaviour; Meta's docs also list chat completions
as a supported surface. Open remainder: whether Meta recommends a
`developer` role for this use — T1 keeps `system` default and makes the
role configurable rather than switching silently.

## Q4. Baseten access and open-model name (T7 / B1)
Is Baseten available, and is the model id exactly `muse-spark-open-1026`?
Blocks only the B1 comparison; T7 metrics must run on Meta first.
Owner: human (access), agent (verification once access exists).

## Q5. Corpus, gold standards, licences (T8)
The human supplies 3–5 lemmas (ePSD2/ORACC, 2–3 records each) and 15–20
gold examples, and licences are checked before any data is published in
the repo. Until then `eval/` contains only an agent-made TEMPLATE and a
format validator with SYNTHETIC neutral examples. Blocks T7 real numbers.

## Q6. Review screen location — RESOLVED by inspection
SPEC T6 said "clarify by existing structure". The portal lives in
`web/portal/` (`index.html`, `triadic.html`, `triadic.js`); the Review
screen is added there in the same zero-build style (T6).

## Q7. Decision registry persistence (T4/T5)
The existing Kafka -> RDF governance pipeline is asynchronous and writes
only `gfen:` governance provenance via the Validation Result Consumer; it
has no synchronous per-claim human-review record. T4 therefore needs a
demo-scope registry (in-memory store + published event, labelled
simulated/demo in docs) unless the human wants the SPARQL write path
extended. Default if unanswered: demo-scope store, clearly labelled;
persistence beyond process lifetime is out of scope for the demo.

## Q8. Committing live artifacts
`artifacts/meta/*.json` contain real model responses. SPEC section 0.6:
they may be committed only after human review. The two artifacts produced
on 2026-10-28 were shown to the human; explicit "commit them" approval is
still required before they enter git. Status at T10: `artifacts/` is
gitignored, both files were verified to contain no API key, and they stay
local until the human approves committing them.
