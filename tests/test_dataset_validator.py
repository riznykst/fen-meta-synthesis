"""Tests for the T8 dataset validator. SYNTHETIC examples only — the real
corpus and gold standards are supplied by the human and never generated."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "validate_dataset", REPO / "eval" / "validate_dataset.py"
)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)


def _example(**overrides):
    example = {
        "_kind": "SYNTHETIC test example",
        "example_id": "synthetic-1",
        "documents": [
            {"document_id": "d1", "text": "The hill marks the old route. It was used until 1903."},
            {"document_id": "d2", "text": "A note says the crossing closed in 1901."},
        ],
        "gold_claims": [{"quote": "The hill marks the old route"}],
        "gold_contradictions": [
            {
                "claim_quotes": ["It was used until 1903", "A note says the crossing closed in 1901"],
                "kind": "temporal_mismatch",
            }
        ],
    }
    example.update(overrides)
    return example


def test_valid_synthetic_example_passes():
    assert validator.validate_example(_example(), "synthetic-1.json") == []


def test_unlocatable_gold_quote_fails():
    example = _example(gold_claims=[{"quote": "a quote that is nowhere in the text"}])
    errors = validator.validate_example(example, "synthetic-1.json")
    assert any("not locatable" in e for e in errors)


def test_duplicate_document_and_missing_fields_fail():
    example = _example()
    example["documents"].append({"document_id": "d1", "text": "duplicate"})
    del example["example_id"]
    errors = validator.validate_example(example, "x.json")
    assert any("duplicate document_id" in e for e in errors)
    assert any("missing example_id" in e for e in errors)


def test_contradiction_needs_two_locatable_quotes_and_kind():
    example = _example(gold_contradictions=[{"claim_quotes": ["only one"], "kind": ""}])
    errors = validator.validate_example(example, "synthetic-1.json")
    assert any("exactly two" in e for e in errors)


def test_real_example_without_checked_license_fails():
    example = _example()
    del example["_kind"]
    example["source"] = {"corpus": "ePSD2", "license": "<TO CHECK>"}
    errors = validator.validate_example(example, "lemma-real.json")
    assert any("license" in e for e in errors)


def test_real_example_with_license_and_corpus_passes():
    example = _example()
    del example["_kind"]
    example["source"] = {"corpus": "ePSD2", "license": "CC BY-SA (checked by human)"}
    assert validator.validate_example(example, "lemma-real.json") == []


def test_cli_on_repo_dataset_is_valid(capsys):
    assert validator.main([str(REPO / "eval" / "dataset")]) == 0
    out = capsys.readouterr().out
    assert "SKIP TEMPLATE.json" in out and "VALID" in out
