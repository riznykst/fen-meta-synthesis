"""Tests for the evaluation harness metrics (eval/run_eval.py, T7).

All offline and SYNTHETIC: matching/math only, no provider calls, no real
corpus data (that arrives with T8 from the human).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_eval", REPO / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)


def test_normalize_and_token_overlap():
    assert run_eval.normalize_quote("  The Hill,  marks! ") == "the hill marks"
    assert run_eval.token_overlap("a b c d", "a b c d") == 1.0
    assert run_eval.token_overlap("a b c d", "a b x y") == 0.5
    assert run_eval.quote_match("The hill marks the route.", "the hill marks the route")


def test_quote_match_threshold_boundary():
    # 4 of 5 gold tokens covered -> overlap coefficient 4/5 = 0.8 -> match
    assert run_eval.quote_match("hill marks old route", "hill marks old trade route")
    # 2 of 5 -> no match
    assert not run_eval.quote_match("hill banana", "hill marks old trade route")


def _pred(claims, contras=None):
    return {"analysis": {"claims": claims, "contradictions": contras or []}}


def test_compute_metrics_matched_claim_and_contradiction():
    example = {
        "example_id": "e1",
        "gold_claims": [{"quote": "q one here"}, {"quote": "q two here"}],
        "gold_contradictions": [{"claim_quotes": ["q one here", "q two here"], "kind": "other"}],
    }
    predicted = _pred(
        [
            {"claim_id": "c1", "quote": "q one here", "quote_verified": True},
            {"claim_id": "c2", "quote": "q two here", "quote_verified": True},
            {"claim_id": "c3", "quote": "fabricated claim text", "quote_verified": False},
        ],
        [{"contradiction_id": "x1", "claim_ids": ["c1", "c2"]}],
    )
    m = run_eval.compute_example_metrics(example, predicted, True)
    assert m["matched_claims"] == 2 and m["predicted_claims"] == 3
    assert m["quotes_verified"] == 2
    assert m["matched_contradictions"] == 1 and m["false_positive_contradictions"] == 0
    agg = run_eval.aggregate_metrics([m])
    assert agg["claim_recall"] == 1.0
    assert agg["claim_precision"] == 2 / 3
    assert agg["quote_verified_rate"] == 2 / 3
    # B0: one of three proposals was a fabrication that verification caught
    assert agg["b0_unverified_share_without_check"] == 1 / 3
    assert agg["contradiction_recall"] == 1.0


def test_compute_metrics_false_positive_contradiction_and_invalid_json():
    example = {
        "example_id": "e1",
        "gold_claims": [{"quote": "q one"}],
        "gold_contradictions": [],
    }
    predicted = _pred(
        [{"claim_id": "c1", "quote": "q one", "quote_verified": True}],
        [{"contradiction_id": "x9", "claim_ids": ["c1", "c1"]}],
    )
    m = run_eval.compute_example_metrics(example, predicted, True)
    assert m["false_positive_contradictions"] == 1
    invalid = run_eval.compute_example_metrics(example, None, False)
    assert invalid["json_valid"] is False and invalid["predicted_claims"] == 0
    agg = run_eval.aggregate_metrics([m, invalid])
    assert agg["json_valid_rate"] == 0.5


def test_load_dataset_skips_nothing_and_reads_synthetic_smoke():
    examples = run_eval.load_dataset(REPO / "eval" / "dataset")
    smoke = [e for e in examples if e["example_id"] == "synthetic-smoke-1"]
    assert len(smoke) == 1
    assert len(smoke[0]["gold_claims"]) == 3
    assert smoke[0]["gold_contradictions"][0]["kind"] == "temporal_mismatch"
