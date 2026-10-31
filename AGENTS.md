# Working Repository — Fixed 2026-10-31

**All work on FEN × Meta happens only in this repository:**
`riznykst/fen-meta-synthesis` (this repo, branch `main`).
Live demo: https://fen-meta-synthesis.vercel.app/review

## Frozen original — do not work there

`riznykst/fen-triadic-synthesis` is frozen at commit `8c1164d`
(`main` = `v0.2.8` = tag `baseline-pre-hackathon`). It is the reference
state for the whitepaper v4, `CITATION.cff`, and the future Prototype Fund
application.

- Do not commit or push hackathon work to `fen-triadic-synthesis`.
- Do not merge hackathon work into its `main`.
- Do not move or delete its `baseline-pre-hackathon` / `v0.2.x` tags.
- The old remote branch `hackathon/meta-ai-synthesis` there is archival;
  its deletion is a separate, owner-confirmed step — never delete it as
  part of routine work.

## Local checkout mapping

The local directory was originally a checkout of the old repository, so
remote names are historical:

| Remote | Points to | Role |
|---|---|---|
| `hackathon` | `riznykst/fen-meta-synthesis` | **Primary — push here** (`hackathon/meta-ai-synthesis:main`) |
| `origin` | `riznykst/fen-triadic-synthesis` | Frozen reference — fetch only, never push hackathon work |

## Rules that stay in force

- The model only proposes; `accepted` exists only after a recorded human
  decision (SPEC §0.8, ADR-004).
- No invented data, quotes, sources, or metrics. Real corpus and gold
  standards are human-supplied (SPEC T8); agent-made material is labelled
  SYNTHETIC or RECORDED.
- Secrets only from environment variables. Never commit `.env`,
  `artifacts/`, or model responses without explicit human review.
- Boundary record: `HACKATHON.md`; open questions:
  `docs/OPEN_QUESTIONS.md`; submission texts: `SUBMISSION.md`.
