# Dataset Sources and Licences

Required by the README ("Data and licensing") before any dataset material
is published in this repository. The agent supplies this register and the
validator; **real corpus data and gold standards are supplied and
licence-checked by the human (T8)** — nothing below is itself corpus data.

| Source | What it is used for here | Licence / terms | Rules for this repo |
|---|---|---|---|
| ePSD2 / Oracc (via the eme-gir mirror/MCP route) | Dictionary verification of candidate lemmas: `lu [person]`, `bahar [potter]`, `me [Being]`, `me [be]` — see `eval/candidates/sumerian-video-candidates.json` | **CC BY-SA 3.0** (Oracc licensing statement). Canonical attribution, carried in every candidate record: *ePSD2 / Oracc: electronic Pennsylvania Sumerian Dictionary, 2nd edition (oracc.museum.upenn.edu/epsd2), prepared by Steve Tinney and the Oracc team at the University of Pennsylvania. Data licensed under Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0). Attribution is required; substantial reuses must propagate the ShareAlike license.* | Short glosses and entry metadata may be recorded with attribution. Do not bundle bulk Oracc data or derived indexes. Cite Oracc, not the eme-gir mirror (the mirror's own instruction). |
| eme-gir (jenova-marie/eme-gir) | Lookup infrastructure over ePSD2/Oracc/ETCSL/CDLI; code MIT. Public MCP endpoints attempted 2026-10-28 returned HTTP 502, so canonical ePSD2 pages were used for the same entries | Code: MIT. Data: as per upstream (row above; ETCSL and CDLI below), documented in the project's `LICENSE-DATA.md` | Use as a lookup route only; do not vendor the repository or its generated SQLite indexes into FEN |
| ETCSL (Oxford) | Not used | **No Creative Commons licence** — academic copyright, citation requested | Do not republish ETCSL texts in this repository; link or cite only |
| CDLI | Not used | Catalogue text freely reusable with citation; imagery non-commercial only | Metadata may be cited; never copy tablet imagery |
| Lecture transcripts ("Sumerian language" 1–2, DownSub auto-subtitles) | Provenance for *why* a lemma was proposed (human's lecture analysis) | Auto-generated subtitles of third-party videos; rights with the video authors/platforms | Provenance notes only, marked as ASR. Never gold evidence, never republished as dataset texts |
| Modern Sumerian (modernsumerian.org / OCaml repo) | Human learning reference for grammar background | No licence file found in the repository (checked 2026-10-28) | Read-only reference for the human; copy nothing into this repository |

Dataset gate: `python eval/validate_dataset.py` refuses examples without
a named, human-checked source licence. Synthetic examples must be marked
SYNTHETIC; recorded model responses must be marked RECORDED.
