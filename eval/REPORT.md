# Evaluation Report (T7)

Method: `python eval/run_eval.py --provider <meta|baseten|fixture>`.
Matching: normalised quote equality or token overlap >= 0.8 (overlap coefficient). Temperature is the client's fixed 0; the prompt hash of each run is stored in its results file. Prompts are not tuned after the first run on a dataset.

Baselines: **B0** = share of predicted claims with unverified quotes (fabrications that would pass without `verify_provenance`). **B1** = the second-provider comparison (Baseten `muse-spark-open-1026`) — reported only when a real Baseten run exists (OPEN_QUESTIONS Q4).

The real corpus and gold standards are supplied by the human (T8). Runs labelled SYNTHETIC use the neutral smoke example and are NOT corpus quality measurements.

| Date (UTC) | Provider | Model | Examples | Mode | json_valid | quote_verified | claim_recall | claim_precision | contra_recall | contra_FP | B0 unverified |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-28 | fixture | muse-spark-1.3 | 1 | SYNTHETIC-fixture · SYNTHETIC dataset | 1.00 | 0.75 | 1.00 | 0.75 | 1.00 | 0.00 | 0.25 |
| 2026-10-28 | meta | muse-spark-1.3 | 1 | live · SYNTHETIC dataset | 1.00 | 1.00 | 1.00 | 0.75 | 1.00 | 0.00 | 0.00 |
