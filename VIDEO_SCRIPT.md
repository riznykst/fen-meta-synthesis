# Demo Video Script — 3:00 (Meta Global AI Developer Hackathon)

Companion to DEMO.md (click-path) and SUBMISSION.md (form texts).
The video must work for a judge who never runs anything: problem → live
analysis → caught fabrication → human decision → provenance → metrics.
Record at 1080p, captions on, cursor highlighted, browser zoom 110–125%.
No terminal with secrets in frame; `.env` is never opened on camera.

**Before recording:** `python scripts/start_demo.py`, open
http://127.0.0.1:8082/web/portal/review.html, run the scenario once
off-camera (primes the flow, proves the stack), reset, then record.
Prepare the offline B0 segment (section 2) as pre-recorded frames in
case the live API is slow on recording day — label it on screen as
"SYNTHETIC fixture, recorded".

---

## 0:00–0:25 — Problem (talking head or title card + source documents)

**On screen:** Review screen with the two pre-filled documents.
**Say:**
> "Researchers who reconcile conflicting sources — dictionaries,
> archives, low-resource language data — do it by hand, because a
> chatbot hides where each statement came from, and can invent quotes.
> This is FEN: the AI proposes, a deterministic check verifies every
> quote, and a human decides. Nothing becomes knowledge on the model's
> word alone."

## 0:25–1:15 — Live analysis (the "it works" segment)

**On screen:** set reviewer name → click **Analyse documents →** → wait
(spinner is fine; if the wait exceeds ~10 s in the final cut, trim it
and keep the latency value visible in the result).
**Say (over the result appearing):**
> "Muse Spark 1.3, through the Meta Model API, read both documents
> with schema-constrained structured output. Every proposal is labelled
> 'awaiting human decision' — the model has approved nothing. Each
> claim shows its exact quote, and its interpretation in a separate
> field, so I can see what the source said versus what the model made
> of it."

**Do:** click **Show in source** on one proposal; the quote highlights
in the document.
> "The quote is highlighted in the source. That location was checked
> by code, not by the model."

## 1:15–1:45 — Contradiction (technical ambition, cross-document reasoning)

**On screen:** the contradiction card (use until 1903 vs closure in
1901, `temporal_mismatch`, alternative interpretations).
**Say:**
> "The model also caught a conflict between the sources — a crossing
> used until 1903, closed according to a 1901 note — and offered
> readings that could resolve it. I don't have to accept its reading;
> I have to decide."

## 1:45–2:15 — The catch (the memorable frame; offline fixture segment)

**On screen:** switch to the labelled SYNTHETIC fixture result
(`python eval/run_eval.py --provider fixture` output or the red card in
the Review screen tests): the invented quote "a toll of exactly fifty
silver coins", red card, **Accept disabled**.
**Say:**
> "And this is why the gate exists. Here the model invented a quote.
> The verifier could not locate it in the source, so the proposal is
> red — and it cannot be accepted. The button is disabled, and the API
> itself returns 409. On this fixture, one in four proposals would have
> looked trustworthy without the check. With it, none can be accepted
> unverified."

## 2:15–2:45 — Human decision + provenance (impact close)

**On screen:** back to the live result. Accept one verified proposal
(with a comment), Dispute the contradiction. Scroll to **Decisions in
this session**, then click **Provenance** on the accepted item.
**Say:**
> "Now I decide — accept this one, dispute the dates for an expert.
> Every decision is recorded with who, when, and why, and the
> provenance chain shows the whole path: document, exact quote, the
> model proposal with its prompt hash, and my verdict. If this feeds a
> knowledge graph later, anyone can audit how the claim got there."

## 2:45–3:00 — Metrics + one-line close (title card)

**On screen:** small table (from eval/REPORT.md, labelled synthetic
smoke): live run quote verification 100%, claim recall 1.00 /
precision 0.75; fixture B0 catch 1 of 4; test suite green. Plus the
repository URL (hackathon branch).
**Say:**
> "AI proposes. Humans decide. Every decision keeps its provenance.
> FEN, built on Muse Spark for the Meta Global AI Developer
> Hackathon — code and demo are open at the link."

---

## Fallbacks and rules

- **API slow/down on recording day:** record sections 0, 2, 4, 5 with
  the fixture/offline material (all labelled), and re-record only
  section 1 when the API answers. Never fake a live result.
- **Never say** "verified true" about a claim: quotes are *located*,
  claims are *human-accepted*. The video follows the same honesty rules
  as HACKATHON.md.
- **Length discipline:** if a take runs over 3:00, cut from section 1's
  waiting time first, never from the catch (1:45–2:15).
- **Upload checklist:** YouTube unlisted/public link opens without
  login; title "FEN — Human-Governed AI Synthesis (Meta AI Hackathon)";
  description carries the repository branch URL and the one-line pitch
  from SUBMISSION.md.
