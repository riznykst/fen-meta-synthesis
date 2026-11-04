# Submission — Meta Global AI Developer Hackathon (Cerebral Valley portal)

Copy-paste source for the submission form at
https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit
**Deadline: 4 November, 21:00 ET (= 5 November, 03:00 Berlin).**
Submit on this repository's `main` state (migrated 2026-10-31 from the
hackathon branch of the original FEN repository, history preserved); do
not edit the texts below to claim more than HACKATHON.md records. Fields
marked `<...>` must be filled by the owner before submitting.

---

## Team Name

FEN — Human-Governed AI Synthesis

## Team Members

Vadym Riznyk (GitHub: rezon99) — Representative, sole team member.
<Confirm in the portal that "rezon99" and "Vadym Riznyk" are one person,
not two team members.>

## Which track are you submitting to?

Indie Developer track

## Which problem statement did you build towards?

Build for Your World

## Most Viral Track — X post link (optional bonus category)

https://x.com/rezon99/status/2117905589074293035

Posted 2026-11-04 by @rezon99 with the demo video attached. Opening line:
"Your AI can invent a quote that looks real. The sentence built on it will read
perfectly. The only thing between that and 'accepted knowledge' is a check almost
nobody ships. We shipped it. 12 claims. 0 approved by AI." The first reply states
the scope honestly: the video shows the verified path, while the caught-fabrication
path is covered by tests and the deterministic SYNTHETIC fixture.

## Project Description

AI systems increasingly extract knowledge from documents into databases
and knowledge graphs — but a fluent model can invent a quote, merge its
own interpretation into a claim, and leave a human reviewer with no way
to tell what the source actually said. For researchers who reconcile
conflicting sources by hand — curators of low-resource-language data,
ancient-text scholars, dataset owners — that makes AI assistance risky
exactly where it would help most.

FEN × Meta is a human-governed validation layer for AI-extracted
knowledge. Muse Spark 1.3 reads several source documents and proposes
structured claims: every claim carries a verbatim quote from its source,
the claim as stated, and the model's interpretation kept in a separate
field, plus ambiguities, an uncertainty level, and contradictions
between sources with alternative readings. Before any human sees the
result, a deterministic verifier (no model involved) checks that every
quote can actually be located in the supplied document, that every
contradiction references real claims, and that identifiers are unique.
A proposal whose quote cannot be verified is shown red and **cannot be
accepted** — the UI disables the button and the API returns 409. Only a
recorded human decision can accept, dispute, or reject an item, and
every decision keeps its full provenance chain: document → exact quote →
model proposal (model, prompt hash, timestamp) → human verdict.

The workflow runs end to end today: documents in, verified proposals,
human decisions, provenance out — with an evaluation harness that
measures quote-verification, claim recall/precision and contradiction
detection, including a B0 baseline showing how many fabricated quotes
would pass *without* the provenance gate (25% on the labelled synthetic
fixture; 0% can be accepted with it).

**How this differs.** Citation-verification tools *check* quotes. FEN ×
Meta makes that check a **gate**: an unverified quote cannot be accepted
(the UI disables the button, the API returns 409), no final status exists
without a recorded human decision, and every decision carries the full
provenance chain — document, exact quote, model and prompt hash, human
verdict — in a workflow built for *conflicting primary sources*
(dictionaries, archives, low-resource-language records), not generic
fact-checking. The individual techniques (quote checking, human review,
provenance, contradiction detection) are known; the contribution is
their assembly into one enforced rule — the model only proposes — on top
of an existing open-source research prototype, with the pre-hackathon /
hackathon boundary kept verifiable in the repository history. We do not
claim a fundamentally new technique, and the submission texts and demo
are written to that standard.

## Public GitHub Repository

https://github.com/riznykst/fen-meta-synthesis

(This repository is the hackathon submission; it was migrated with full
history from the hackathon branch of the original FEN repository on
2026-10-31. The boundary between pre-existing work and hackathon work is
the `baseline-pre-hackathon` tag in this repository
(`git log baseline-pre-hackathon..main`) and HACKATHON.md.)

## 2-Minute Demo Video

https://youtu.be/f77s4HoNH9M

Public on YouTube (checked 2026-11-04: oEmbed returns 200, `lengthSeconds: 109`,
`isPrivate: false`). 1:49 running time. Narration in the author's own cloned voice.
The video shows, in order: the problem (one Sumerian form, two dictionary entries),
Muse Spark 1.3 proposing claims with verbatim quotes, the code-only quote check
(12/12 located, nothing approved by the model), the provenance chain
(document → quote → model + prompt hash), a human Accept as reviewer 1, a second
reviewer accepting the same claim to produce community consensus, and the accepted
record landing in the registry with its vote trail.

Scope note, so the video is not over-read: it demonstrates the *verified* path
(real quotes located in the real sources). The caught-fabrication path — a quote that
cannot be located, red card, Accept disabled, API 409 — is covered by the automated
tests and the deterministic SYNTHETIC fixture (`python eval/run_eval.py
--provider fixture`: `quote_verified_rate 0.75`, `B0 0.25`), not by a frame in this
video.

## Describe your use of Meta products to build the submitted project

All model calls go through FEN's existing OpenAI-compatible client
(`services/common/llm.py`) to the Meta Model API
(`https://api.meta.ai/v1`, model `muse-spark-1.3`, chat completions,
temperature 0, `system` role — confirmed live on 2026-10-28). On top of
that client the hackathon build adds:

- **Structured output with schema-constrained decoding**: `POST /analyze`
  sends `response_format={"type": "json_schema"}` carrying the canonical
  analysis contract (`services/common/analysis.py`, generated JSON Schema
  in `schemas/analysis/document-analysis.schema.json`), so decoding
  itself — not post-hoc cleanup — produces contract-shaped JSON. The
  response is still validated by our own parser; the provider guarantee
  never replaces the contract check.
- **Detailed response capture**: returned model id, token usage and
  finish reason are recorded per analysis (sanitized artifacts, never
  credentials), together with a SHA-256 prompt hash, so every proposal is
  reproducible and auditable.
- **Controlled failure behaviour**: exactly one retry on network errors
  in the client, exactly one format-reminder retry in the analysis
  service, raw failed outputs preserved for human inspection, and no
  fallback to prepared answers — a provider failure surfaces as an
  honest 502.

The deterministic half of the system (quote verification, contradiction
integrity, the 409 accept-lock, append-only human decisions in
`POST /decisions`, and the `GET /provenance/{item_id}` chain) uses no
model at all: provenance must not depend on trusting the model.

Verified live during the hackathon: a real `POST /analyze` against
`muse-spark-1.3` returned structured claims with all quotes verified,
including a temporal-mismatch contradiction between two sources; a
schema-constrained run on 2026-10-28 returned 2 claims, both quotes
verified. Offline, 218 pytest tests and 116 Node UI tests cover the
workflow with synthetic fixtures (labelled as such).

What was built during the hackathon (vs the pre-existing open-source
prototype) is listed task-by-task in HACKATHON.md on the submitted
branch, against the `baseline-pre-hackathon` tag.

## Why are Meta's models important to your solution?

The analysis step needs a model that can read several full documents at
once, reason across them (the contradiction between a 1901 closure note
and a claim of use until 1903 is a cross-document inference, not an
extraction), work with low-resource and historical material, and return
machine-checkable structured output rather than prose. Muse Spark 1.3
provides exactly that combination through the Meta Model API: long
context, multilingual extraction with verbatim evidence spans in a
single pass, and schema-constrained decoding that makes claim-level
extraction auditable. Without a model of this class the workflow
collapses back to manual reconciliation; without the governance layer
around it, the model's output cannot be trusted. FEN supplies the
second half — Meta's model supplies the first.

That division is also the differentiation: existing citation checkers
verify text after the fact, and generic human-in-the-loop tools leave
acceptance to convention. Here the Meta model's structured output is
fed into a deterministic gate it cannot pass on its own — schema
validation, quote location, the 409 accept-lock — and the *only* path
from proposal to accepted knowledge is a recorded human decision with
its provenance chain. The model is used at full strength (long
documents, cross-source reasoning, verbatim spans) precisely because
the system around it assumes it can be wrong.

## Provide feedback from your experience using Meta products

What worked well: the `system` role was accepted on the chat-completions
surface exactly as documented, JSON mode and then schema-constrained
structured output both behaved as documented (our full analysis schema,
including `$defs` references and enums, was accepted without changes),
and the response envelope's returned-model and usage fields made
per-call auditing straightforward. Reasoning tokens appearing in usage
was useful for cost transparency.

What could be better: (1) the relationship between the recommended
Responses API and the chat-completions surface took some digging — a
single "which surface for which job" table early in the docs would help;
(2) when a structured-output schema is rejected, a machine-readable
error pointing at the offending schema path would speed up debugging;
(3) a documented way to request the returned prompt hash / request id
for audit trails would serve governance-style applications like ours.

## Provide feedback from your experience using partner technologies

Fireworks / Modal / Baseten: not used in the submitted build. The Baseten
open-weights comparison (our planned B1 baseline in `eval/`) is still
pending access verification and is recorded as an open question in
`docs/OPEN_QUESTIONS.md` (Q4) rather than claimed. If access is granted
before the deadline and a real comparison run exists, replace this text
with its measured results.

---

## Owner checklist before pressing Submit

- [ ] Application was accepted (rules: participation requires acceptance).
- [ ] One track only (Indie); Representative = Vadym Riznyk; no duplicate
      team member entries.
- [ ] Sumerian corpus files committed only after licence check (Q5), or
      left out — submission texts above do not depend on them.
- [ ] `artifacts/` (live responses) stay uncommitted unless explicitly
      approved (Q8); repository and video contain no API key.
- [ ] Video link opens without login; repository link opens the
      hackathon branch; README first screen matches the video story.
- [ ] Full offline check green on the submitted commit:
      `python -m pytest -q` and the Review demo dry-run (DEMO.md).
- [ ] Submitted several hours before 21:00 ET, not at the deadline.
