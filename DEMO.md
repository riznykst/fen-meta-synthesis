# Demo — Human-Governed AI Synthesis (3 minutes)

An independent person can run this scenario without any explanation beyond
this file. It shows what was built during the hackathon: a Meta model
extracts claims and a contradiction from two documents, the system checks
every quote automatically, a human decides, and the decision is recorded
with its full provenance. The model never decides anything.

## 0. Start (30 seconds)

Prerequisite: a Meta Model API key in `.env` (copy `.env.example`, set
`FEN_LLM_BASE_URL=https://api.meta.ai/v1`, `FEN_LLM_MODEL=muse-spark-1.3`,
and your key — never commit `.env`).

```bash
python scripts/start_demo.py        # Windows PowerShell: same command
# or: bash scripts/demo_seed.sh
```

Open **http://127.0.0.1:8082/web/portal/demo.html** — the simplified
one-screen demo (the full Review screen remains at `/web/portal/review.html`).

The pre-filled documents are a *synthetic demo example* (an invented
trade-route story). The dataset switcher also offers **Sumerian dictionary
entries (ePSD2)** — short verified dictionary excerpts for `lu`, `bahar`
and `me`, labelled as excerpts, not corpus records and not gold data — and
**EU AI Act — public texts (not legal advice)**: Articles 11 and 18 from
Regulation (EU) 2024/1689 (EUR-Lex) plus one clearly **SYNTHETIC**
commentary paragraph that repeats a common misattribution (a ten-year
retention rule attributed to Article 11, while it actually belongs to
Article 18). Replace the documents with any real sources to repeat the
scenario on your own material — the workflow is dataset-agnostic.

## The wrong-attribution case (EU AI Act preset, ~60 seconds)

1. Click **EU AI Act — public texts (not legal advice)**. The banner says
   exactly that, and the third document is titled *Industry commentary —
   SYNTHETIC*.
2. Analyse. The model proposes, among others, a claim from Article 18 (the
   real ten-year rule) and a claim from the synthetic commentary that
   attributes that rule to Article 11.
3. The commentary claim carries a red **SYNTHETIC source** badge: its quote
   *is* verified — the words really are in that document — but the document
   is illustrative, not a primary source. This distinction is the point:
   quote verification proves location, not truth or authority.
4. The model usually also flags the **contradiction** between the Article 18
   claim and the commentary claim. **Dispute** it with a comment: the
   attribution is wrong, the retention rule is Article 18.
5. Open the Registry: nothing accepted lands there unless a human accepted
   it. Article 11/18 material only enters accepted knowledge if you accept
   the correct claim.

## 1. Analyse (45 seconds)

1. Leave the reviewer name or set your own. Optionally add a third,
   conflicting source with **+ Add third document**.
2. Click **Analyse documents →** and wait for the model.
3. Observe: every item is labelled **“Proposal — awaiting human decision”**.
   The model has approved nothing.
4. Each proposal shows its exact quote from the source, the model's
   interpretation *separate from the claim*, uncertainty, and whether the
   quote was verified in the document. Click **Show in source** on a
   proposal to see that quote highlighted in the source document.
5. Find the contradiction card: two claims side by side (use until 1903 vs
   a closure reported in 1901), its type (`temporal_mismatch`) and the
   alternative interpretations the model offered.

If the model service is unreachable you instead get a plain-language error
(502) and nothing is created — there is no canned answer behind the button.

## 2. The caught unverified quote (30 seconds, offline fixture)

A live model may happen to quote perfectly, so the catch is demonstrated
deterministically with the labelled SYNTHETIC fixture (never presented as
live output):

```bash
python eval/run_eval.py --provider fixture
```

The fixture response contains one invented quote (“a toll of exactly fifty
silver coins”). The run reports `quote_verified_rate 0.75` and the **B0**
baseline in `eval/REPORT.md`: 25% of proposals would have looked
trustworthy without `verify_provenance`. In the Review screen such a
proposal is a red card with **Accept disabled** (covered by
`web/tests/review.test.js`).

## 3. Decide as a human (45 seconds)

1. On a verified proposal, optionally add a comment and click **Accept**.
   The card now reads “Accepted by a human reviewer” — this status exists
   only because you just recorded it (`POST /decisions`, 201).
2. On the contradiction card, click **Dispute** (“dates need expert check”).
3. Scroll to **Decisions in this session**: reviewer, verdict, comment and
   time are listed. Decisions are append-only — deciding again adds a new
   record, the old one stays.
4. The accepted item also appears under **Registry — where accepted
   knowledge lands**, with a **Download record (JSON-LD)** export carrying
   the claim, quote, source, model, prompt hash and your decision. That
   record is where validated knowledge goes in this demo: the launcher
   persists analyses and decisions to `artifacts/store.jsonl`, so
   restarting `scripts/start_demo.py` keeps them (try it: stop, restart,
   reload — the registry still shows your accepted record). Writing into
   the Kafka/RDF governance pipeline of the baseline system is
   deliberately not claimed here.

Try it: typing a quote the source does not contain cannot be accepted —
the API returns 409 for an accept on an unverified quote (the button is
disabled in the UI; the server enforces the same rule).

## 4. Provenance and one metric (30 seconds)

1. Click **Provenance** on the accepted proposal: document → exact quote →
   model proposal (model name, prompt hash, time) → your decision. That
   chain is `GET /provenance/{item_id}`.
2. One metric to take away (synthetic smoke run, 2026-10-28, live Meta):
   on the demo documents the model reached **claim recall 1.00 / precision
   0.75** with **100% of its quotes verified** — and the fixture run shows
   the gate catching 1 of 4 proposals when a quote is invented. Corpus
   numbers await the human-supplied dataset (T8): see `eval/REPORT.md`,
   which labels every run honestly.

## Stop

Ctrl-C in the launcher terminal stops both services.

## Without a Meta key (offline check)

```bash
python -m pytest -q          # backend + workflow tests
node --test web/tests/*.test.js   # UI pure-function tests (35)
python eval/validate_dataset.py   # dataset format gate (T8)
```

Everything in this offline path is real code with mocked providers; model
answers in tests/fixtures are marked SYNTHETIC or RECORDED, never live.
