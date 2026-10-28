"""Dataset format validator (T8).

The human supplies the real corpus and gold standards; this validator is
the agent-made gate that keeps the format honest before any data is
published or measured:

- required fields and types per example;
- unique example_id / document_id;
- every gold claim quote locatable (whitespace-normalised) in some
  supplied document — a gold standard may not quote text that is not there;
- every contradiction references exactly two locatable quotes;
- non-synthetic, non-template examples must declare a checked source
  licence (``source.license`` not a placeholder) — licences are verified by
  the human before publication (SPEC T8).

Usage: python eval/validate_dataset.py [dataset-dir-or-file]
Exit 0 when valid (TEMPLATE files are reported as skipped), 1 on errors.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _normalize(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _is_synthetic(example: dict, source_name: str) -> bool:
    kind = str(example.get("_kind", ""))
    return "SYNTHETIC" in kind.upper() or source_name.lower().startswith("synthetic")


def validate_example(example: dict, source_name: str = "") -> list:
    errors = []
    label = example.get("example_id") or "<no example_id>"
    if not isinstance(example, dict):
        return [f"{source_name}: example is not a JSON object"]
    if not example.get("example_id"):
        errors.append(f"{source_name}: missing example_id")

    documents = example.get("documents")
    if not isinstance(documents, list) or not documents:
        errors.append(f"{label}: documents must be a non-empty list")
        documents = []
    doc_ids = set()
    doc_texts = []
    for doc in documents:
        if not isinstance(doc, dict) or not doc.get("document_id") or not doc.get("text"):
            errors.append(f"{label}: every document needs document_id and non-empty text")
            continue
        if doc["document_id"] in doc_ids:
            errors.append(f"{label}: duplicate document_id {doc['document_id']!r}")
        doc_ids.add(doc["document_id"])
        doc_texts.append(_normalize(doc["text"]))

    def locatable(quote) -> bool:
        needle = _normalize(quote)
        return bool(needle) and any(needle in text for text in doc_texts)

    gold_claims = example.get("gold_claims")
    if not isinstance(gold_claims, list) or not gold_claims:
        errors.append(f"{label}: gold_claims must be a non-empty list")
        gold_claims = []
    for claim in gold_claims:
        quote = claim.get("quote") if isinstance(claim, dict) else None
        if not quote:
            errors.append(f"{label}: every gold claim needs a quote")
        elif not locatable(quote):
            errors.append(f"{label}: gold quote not locatable in documents: {quote[:60]!r}")

    gold_contras = example.get("gold_contradictions", [])
    if not isinstance(gold_contras, list):
        errors.append(f"{label}: gold_contradictions must be a list")
        gold_contras = []
    for contra in gold_contras:
        quotes = contra.get("claim_quotes") if isinstance(contra, dict) else None
        if not isinstance(quotes, list) or len(quotes) != 2:
            errors.append(f"{label}: contradiction needs exactly two claim_quotes")
            continue
        for quote in quotes:
            if not locatable(quote):
                errors.append(
                    f"{label}: contradiction quote not locatable in documents: {str(quote)[:60]!r}"
                )
        if not contra.get("kind"):
            errors.append(f"{label}: contradiction needs a kind")

    if not _is_synthetic(example, source_name):
        source = example.get("source") or {}
        license_text = str(source.get("license", ""))
        if not license_text or "<" in license_text:
            errors.append(
                f"{label}: source.license must name the checked licence "
                "(human verifies licences before publication; placeholders are not publishable)"
            )
        if not source.get("corpus"):
            errors.append(f"{label}: source.corpus is required for real data")
    return errors


def load_examples(path: Path):
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    for file in files:
        if file.name.startswith("TEMPLATE"):
            print(f"SKIP {file.name} (template — filled in by the human)")
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        examples = data if isinstance(data, list) else [data]
        for example in examples:
            yield file.name, example


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = Path(argv[0]) if argv else Path(__file__).parent / "dataset"
    errors = []
    seen_ids = set()
    count = 0
    for source_name, example in load_examples(path):
        count += 1
        example_id = example.get("example_id")
        if example_id and example_id in seen_ids:
            errors.append(f"duplicate example_id across dataset: {example_id}")
        seen_ids.add(example_id)
        errors.extend(validate_example(example, source_name))
    if errors:
        print(f"INVALID ({len(errors)} error(s) in {count} example(s)):")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"VALID: {count} example(s) checked, 0 errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
