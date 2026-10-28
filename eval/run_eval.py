"""Evaluation harness (T7): run the analysis workflow over a dataset and
compute quality metrics against human gold standards.

Dataset format (per example, SPEC T7/T8):
    {"example_id": "...", "documents": [{"document_id", "title", "text"}],
     "gold_claims": [{"quote": "..."}],
     "gold_contradictions": [{"claim_quotes": ["...", "..."], "kind": "..."}]}

Matching rule (SPEC T7): a claim is found when the normalised quote is
identical OR the token overlap (overlap coefficient
|A∩B| / min(|A|,|B|)) is >= 0.8. A contradiction is found when both of its
gold quotes are matched to predicted claims that a predicted contradiction
also pairs up.

Metrics: json_valid_rate, quote_verified_rate, claim_recall,
claim_precision, contradiction_recall, contradiction_false_positive_rate.
Baseline B0: the share of predicted claims whose quotes are NOT located in
the sources — i.e. how many fabrications would have passed as trustworthy
without verify_provenance. B1: the same run on a second provider
(--provider baseten), reported only after a real run exists.

Honesty rules: prompts are never tuned after the first run on a dataset
(the prompt_hash of every run is recorded); temperature is the client's
fixed 0 and is recorded; runs over synthetic smoke data are labelled
SYNTHETIC and are never presented as corpus measurements. The real corpus
and gold standards come from the human (T8).

Usage:
    python eval/run_eval.py --provider meta [--dataset eval/dataset]
    python eval/run_eval.py --provider fixture   # offline SYNTHETIC smoke
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from services.common import analyze as analyze_svc  # noqa: E402
from services.common.analysis import AnalysisParseError, SourceDocument  # noqa: E402
from services.common.analyze import AnalysisUnavailable  # noqa: E402
from services.common.llm import LLMConfig, LLMResult  # noqa: E402

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
MATCH_THRESHOLD = 0.8


# ------------------------------------------------------------- matching -----
def normalize_quote(text: str) -> str:
    return " ".join(TOKEN_RE.findall((text or "").lower()))


def token_set(text: str) -> set:
    return set(normalize_quote(text).split())


def token_overlap(a: str, b: str) -> float:
    tokens_a, tokens_b = token_set(a), token_set(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def quote_match(predicted: str, gold: str) -> bool:
    return normalize_quote(predicted) == normalize_quote(gold) or token_overlap(
        predicted, gold
    ) >= MATCH_THRESHOLD


def match_claims(predicted_claims: list, gold_claims: list):
    """Greedy one-to-one matching by best token overlap.

    Returns (pairs, matched_predicted_idx, matched_gold_idx) where pairs are
    (predicted_idx, gold_idx)."""
    scored = []
    for p_idx, pred in enumerate(predicted_claims):
        for g_idx, gold in enumerate(gold_claims):
            overlap = token_overlap(pred.get("quote", ""), gold.get("quote", ""))
            if normalize_quote(pred.get("quote", "")) == normalize_quote(gold.get("quote", "")):
                overlap = 1.0
            if overlap >= MATCH_THRESHOLD:
                scored.append((overlap, p_idx, g_idx))
    scored.sort(reverse=True)
    pairs, used_p, used_g = [], set(), set()
    for _overlap, p_idx, g_idx in scored:
        if p_idx in used_p or g_idx in used_g:
            continue
        used_p.add(p_idx)
        used_g.add(g_idx)
        pairs.append((p_idx, g_idx))
    return pairs, used_p, used_g


def compute_example_metrics(example: dict, predicted: Optional[dict], json_valid: bool) -> dict:
    """Per-example metrics from one analysis result (None when invalid)."""
    gold_claims = example.get("gold_claims", [])
    gold_contras = example.get("gold_contradictions", [])
    if predicted is None:
        return {
            "example_id": example.get("example_id"),
            "json_valid": False,
            "predicted_claims": 0,
            "gold_claims": len(gold_claims),
            "matched_claims": 0,
            "quotes_verified": 0,
            "gold_contradictions": len(gold_contras),
            "matched_contradictions": 0,
            "predicted_contradictions": 0,
            "false_positive_contradictions": 0,
        }
    pred_claims = predicted.get("analysis", {}).get("claims", [])
    pred_contras = predicted.get("analysis", {}).get("contradictions", [])
    pairs, _used_p, matched_gold = match_claims(pred_claims, gold_claims)
    pred_by_id = {c.get("claim_id"): c for c in pred_claims}

    matched_contras = 0
    false_positive_contras = 0
    gold_contra_matched = [False] * len(gold_contras)
    for pred_contra in pred_contras:
        pred_quotes = [
            pred_by_id[ref].get("quote", "")
            for ref in pred_contra.get("claim_ids", [])
            if ref in pred_by_id
        ]
        hit = None
        for g_idx, gold_contra in enumerate(gold_contras):
            gold_quotes = gold_contra.get("claim_quotes", [])
            if len(gold_quotes) != 2 or len(pred_quotes) != 2:
                continue
            if (
                quote_match(pred_quotes[0], gold_quotes[0])
                and quote_match(pred_quotes[1], gold_quotes[1])
            ) or (
                quote_match(pred_quotes[0], gold_quotes[1])
                and quote_match(pred_quotes[1], gold_quotes[0])
            ):
                hit = g_idx
                break
        if hit is None:
            false_positive_contras += 1
        else:
            gold_contra_matched[hit] = True
    matched_contras = sum(gold_contra_matched)

    return {
        "example_id": example.get("example_id"),
        "json_valid": json_valid,
        "predicted_claims": len(pred_claims),
        "gold_claims": len(gold_claims),
        "matched_claims": len(matched_gold),
        "quotes_verified": sum(1 for c in pred_claims if c.get("quote_verified")),
        "gold_contradictions": len(gold_contras),
        "matched_contradictions": matched_contras,
        "predicted_contradictions": len(pred_contras),
        "false_positive_contradictions": false_positive_contras,
    }


def aggregate_metrics(per_example: list) -> dict:
    total = len(per_example) or 1
    pred_claims = sum(e["predicted_claims"] for e in per_example)
    gold_claims = sum(e["gold_claims"] for e in per_example)
    matched = sum(e["matched_claims"] for e in per_example)
    verified = sum(e["quotes_verified"] for e in per_example)
    gold_contras = sum(e["gold_contradictions"] for e in per_example)
    matched_contras = sum(e["matched_contradictions"] for e in per_example)
    pred_contras = sum(e["predicted_contradictions"] for e in per_example)
    fp_contras = sum(e["false_positive_contradictions"] for e in per_example)

    def ratio(num, den):
        return (num / den) if den else None

    return {
        "examples": len(per_example),
        "json_valid_rate": ratio(sum(1 for e in per_example if e["json_valid"]), total),
        "quote_verified_rate": ratio(verified, pred_claims),
        "claim_recall": ratio(matched, gold_claims),
        "claim_precision": ratio(matched, pred_claims),
        "contradiction_recall": ratio(matched_contras, gold_contras),
        "contradiction_false_positive_rate": ratio(fp_contras, pred_contras),
        # B0: fabrications that would pass without verify_provenance.
        "b0_unverified_share_without_check": ratio(pred_claims - verified, pred_claims),
    }


# ----------------------------------------------------------------- runs -----
def load_dataset(path: Path) -> list:
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    examples = []
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        for example in data:
            example.setdefault("_source_file", file.name)
            examples.append(example)
    return examples


def provider_config(provider: str) -> LLMConfig:
    config = LLMConfig()
    if provider == "meta":
        return config
    if provider == "baseten":
        config.base_url = os.getenv("BASETEN_BASE_URL") or None
        config.api_key = os.getenv("BASETEN_API_KEY") or None
        config.model = os.getenv("BASETEN_MODEL", "muse-spark-open-1026")
        return config
    raise ValueError(f"unknown provider: {provider}")


def analyze_example(example: dict, config: LLMConfig, fixture_text: Optional[str]) -> tuple:
    documents = [SourceDocument(**doc) for doc in example["documents"]]
    if fixture_text is not None:
        fake = LLMResult(text=fixture_text, model_returned="SYNTHETIC-fixture",
                         usage=None, finish_reason="stop")
        with mock.patch.object(analyze_svc, "chat_completion_detailed", return_value=fake):
            return analyze_svc.analyze_documents(documents, config), True
    return analyze_svc.analyze_documents(documents, config), True


def write_report(results_dir: Path, report_path: Path) -> None:
    runs = []
    for file in sorted(results_dir.glob("*.json")):
        try:
            runs.append(json.loads(file.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    lines = [
        "# Evaluation Report (T7)",
        "",
        "Method: `python eval/run_eval.py --provider <meta|baseten|fixture>`.",
        "Matching: normalised quote equality or token overlap >= 0.8 "
        "(overlap coefficient). Temperature is the client's fixed 0; the "
        "prompt hash of each run is stored in its results file. Prompts are "
        "not tuned after the first run on a dataset.",
        "",
        "Baselines: **B0** = share of predicted claims with unverified quotes "
        "(fabrications that would pass without `verify_provenance`). **B1** = "
        "the second-provider comparison (Baseten `muse-spark-open-1026`) — "
        "reported only when a real Baseten run exists (OPEN_QUESTIONS Q4).",
        "",
        "The real corpus and gold standards are supplied by the human (T8). "
        "Runs labelled SYNTHETIC use the neutral smoke example and are NOT "
        "corpus quality measurements.",
        "",
        "| Date (UTC) | Provider | Model | Examples | Mode | json_valid | quote_verified | claim_recall | claim_precision | contra_recall | contra_FP | B0 unverified |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        m = run["metrics"]
        def fmt(value):
            return "n/a" if value is None else f"{value:.2f}"
        mode = run["mode"]
        dataset_files = run.get("dataset_files") or []
        if dataset_files and all(str(f).startswith("synthetic") for f in dataset_files):
            mode += " · SYNTHETIC dataset"
        lines.append(
            "| {date} | {provider} | {model} | {n} | {mode} | {jv} | {qv} | {cr} | {cp} | {xr} | {xfp} | {b0} |".format(
                date=run["run_at"][:10], provider=run["provider"],
                model=run["model_requested"], n=m["examples"], mode=mode,
                jv=fmt(m["json_valid_rate"]), qv=fmt(m["quote_verified_rate"]),
                cr=fmt(m["claim_recall"]), cp=fmt(m["claim_precision"]),
                xr=fmt(m["contradiction_recall"]),
                xfp=fmt(m["contradiction_false_positive_rate"]),
                b0=fmt(m["b0_unverified_share_without_check"]),
            )
        )
    if not runs:
        lines.append("| — | — | — | 0 | — | — | — | — | — | — | — | — |")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FEN analysis evaluation (T7)")
    parser.add_argument("--provider", default="meta", choices=("meta", "baseten", "fixture"))
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "dataset"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "results"))
    parser.add_argument(
        "--fixture",
        default=str(Path(__file__).parent / "fixtures" / "synthetic_response.json"),
        help="fixture response used by --provider fixture (SYNTHETIC)",
    )
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset)
    examples = [
        e for e in load_dataset(dataset_path)
        if not e.get("_source_file", "").startswith("TEMPLATE")
    ]
    if not examples:
        print("FAIL: no dataset examples found (real dataset is supplied by the human, T8).")
        return 2

    fixture_text = None
    mode = "live"
    if args.provider == "fixture":
        fixture_text = Path(args.fixture).read_text(encoding="utf-8")
        mode = "SYNTHETIC-fixture"
        config = LLMConfig()
        config.base_url = "https://api.meta.ai/v1"
        config.model = "muse-spark-1.3"
    else:
        config = provider_config(args.provider)
        if not config.enabled or not config.api_key:
            print(
                f"FAIL: provider {args.provider} not configured "
                "(set its base URL / API key env vars; see docs/PROVIDERS.md). "
                "No results were fabricated."
            )
            return 2

    per_example = []
    prompt_hashes = []
    for example in examples:
        try:
            result, valid = analyze_example(example, config, fixture_text)
            prompt_hashes.append(result.get("prompt_hash"))
            per_example.append(compute_example_metrics(example, result, valid))
        except (AnalysisParseError, AnalysisUnavailable) as exc:
            print(f"example {example.get('example_id')}: analysis failed: {exc}")
            per_example.append(compute_example_metrics(example, None, False))

    metrics = aggregate_metrics(per_example)
    run = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "provider": args.provider,
        "mode": mode,
        "model_requested": config.model,
        "temperature": 0,
        "prompt_hashes": prompt_hashes,
        "dataset_files": sorted({e.get("_source_file") for e in examples}),
        "metrics": metrics,
        "per_example": per_example,
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_file = out_dir / f"{args.provider}-{stamp}.json"
    result_file.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out_dir, Path(__file__).parent / "REPORT.md")
    print(f"OK: {result_file} — metrics: {json.dumps(metrics)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
