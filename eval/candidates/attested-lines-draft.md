# Attested Material — DRAFT for Human Verification

Status: **HUMAN_VERIFIED (owner, 2026-10-31) — attested material, still
not gold data and not dataset examples.** Assembled by the agent on
2026-10-31 at the owner's request ("select attested lines from ePSD2
yourself, I will check"). Agent pre-check against the canonical ePSD2
entry pages (lu o0033207, bahar o0024835, me [BEING] o0034101,
me [BE] o0034109) confirmed instance counts, senses, writings and cited
lines; the owner confirmed all four blocks usable on 2026-10-31 (one
citation corrected during verification: `me = parṣu` is listed under
OB Nippur **Ea** 71, not Aa 71:1). Only after running source texts are
selected may this material become `eval/dataset/` examples via
`TEMPLATE.json`.

Selection route: canonical ePSD2 entry pages (the eme-gir MCP endpoints
returned HTTP 502 again on 2026-10-31, so the mirror route was unavailable;
eme-gir itself instructs to cite Oracc, not the mirror). Licence for all
ePSD2 material below: **CC BY-SA 3.0**, attribution in
`eval/dataset/SOURCES.md`.

**What "attested lines" means here — read before verifying.** ePSD2 entry
pages provide (a) attested writings with per-period instance counts and
(b) cited lexical-list lines (ancient dictionary equations, with text IDs).
They do **not** provide running corpus lines on the entry page. Lines of
type (b) prove the form existed and how ancient scribes equated it; they
are not prose attestations. If the dataset needs running text, the next
step after verification is pulling the cited texts (or ORACC corpus lines)
themselves — also human-checked.

---

## lu [PERSON] (N) — ePSD2 o0033207

Citation: http://oracc.org/epsd2/o0033207 · 18,895 instances total.
Senses: person 18,745 (99%) · man 124 · who/which 18 · of · ruler 8.
Akkadian: amēlu; ša.

Attested writings (selection):

| Writing | Period profile (from the entry's forms table) |
|---|---|
| `lu₂` | ED IIIb 3,047 · Old Akkadian 1,037 · Ur III 8,857 · Old Babylonian 4,893 |
| `lu` | ED IIIb 1 · Old Babylonian 21 (rare beside `lu₂`) |
| `lu₂-lu₂` | ED IIIa 1 · Old Akkadian 2 · Old Babylonian 11 — the reduplicated writing is attested as a writing of this lemma |

Cited lexical lines (selection):

| Line (as cited on the entry page) | Source text |
|---|---|
| `lu₂ = awīlum` | Ea 07 65; OB Nippur Ea 625 |
| `lu₂ = amēlu` | AJSL 36.2, 158-160 r iii 21' |
| `lu₂ gidim` (in a compound list) | Ebla Sign List 97 |

Human check: ☑ entry/senses correct ☑ writings correct ☑ lines usable (owner, 2026-10-31)

## bahar [POTTER] (N) — ePSD2 o0024835

Citation: http://oracc.org/epsd2/o0024835 · 613 instances.
Sense: potter 613 (100%). Akkadian: pahāru.

Attested writings (selection):

| Writing | Period profile |
|---|---|
| `baḫar₂` | ED IIIb 123 · Old Akkadian 31 · Ur III 125 · Old Babylonian 31 |
| `baḫar₃` | Ur III 227 (period-concentrated writing) |
| `baḫar₄` | ED IIIa 14 · ED IIIb 6 |

Cited lexical lines (selection):

| Line | Source text |
|---|---|
| `baḫar₂ = pahārum` | Ea 05 34; MSL 14, 393 6'; RA 13, 190-191, K 02055 o i 21' |
| `baḫar₂` (list attestations) | ED Lu E 40; SF 048 26; SF 070 o ii 6 |
| `udun baḫar₂` (kiln + potter compound) | OB Nippur Ura 2 322 |

Note for the dataset: only the gloss "potter" is verified. The lecture's
substrate-etymology discussion is a disputed hypothesis and is **not**
attested by this entry.

Human check: ☑ entry/sense correct ☑ writings correct ☑ lines usable (owner, 2026-10-31)

## me [BEING] (N) — ePSD2 o0034101

Citation: http://oracc.org/epsd2/o0034101 · 1,174 instances.
Senses: Being / divine properties enabling cosmic activity, rites 1,136
(97%) · (cultic) ordinance 29 · prayer 8 · office 1.

Attested writings: `me` (Old Babylonian 982 of the total) · `me-me` ·
`me-e`.

Cited lexical lines (selection):

| Line | Source text |
|---|---|
| `me` | HS 1777 o ii 5; OB Nippur Ea 71 |
| `me = parṣu` | Ea 01 241; OB Nippur Ea 71 |
| `me = šamû` (as cited) | OB Nippur Aa 71:7 |

Human check: ☑ entry/senses correct ☑ writings correct ☑ lines usable (owner, 2026-10-31)

## me [BE] (V/i) — ePSD2 o0034109

Citation: http://oracc.org/epsd2/o0034109 · 3,919 instances.
Sense: to be 3,919 (100%). Separate headword from `me [BEING]` — the two
must stay separate dataset entries (the lecture makes the same split).

Attested writings (selection): `me` (Old Babylonian 1,757) · `men₃` ·
`nam` · `am₃` · `me-en`.

Cited lexical lines (selection):

| Line | Source text |
|---|---|
| `i₃-me-en = anāku` | MSL 04, 130 o ii 34 |
| `me-en = anāku` | MSL 04, 130 o ii 33 |
| `me = kīma` | Ea 01 244 |

Human check: ☑ entry/sense correct ☑ writings correct ☑ lines usable (owner, 2026-10-31)

---

## What happens after your verification

1. You mark each block usable / not usable and correct any gloss.
2. Only then: running source texts are selected (the cited texts above or
   ORACC corpus lines), placed into `eval/dataset/` via `TEMPLATE.json`
   (2–3 records per lemma, 15–20 examples total per SPEC T8), with gold
   quotes copied exactly from those texts.
3. `python eval/validate_dataset.py` must pass, then
   `python eval/run_eval.py --provider meta` produces the first real
   (non-synthetic) metrics row in `eval/REPORT.md`.

Nothing in this draft is gold, and no metric may be computed against it
until step 2 exists and you have verified it.
