"""Tests for the canonical analysis service (services/common, T2).

All offline. Model responses are SYNTHETIC fixtures written for these tests
(neutral trade-route example), never recorded provider output and never
real corpus data (SPEC 0.4/0.5, T8). The ``chat_completion_detailed``
client is mocked — call counting verifies the single format-retry policy.
"""
from __future__ import annotations

import json
from unittest import mock

import pytest

from services.common import analyze as analyze_svc
from services.common import analysis
from services.common.llm import LLMResult

DOCS = [
    analysis.SourceDocument(
        document_id="d1",
        title="Oral tradition",
        text="The hill Koshary marks the old trade route. The river crossing at Sokolowizna was used by traders until 1903.",
    ),
    analysis.SourceDocument(
        document_id="d2",
        title="Archive note",
        text="A 1901 archive note states that the Sokolowizna crossing closed after the bridge was built downstream.",
    ),
]

_QUOTE_1 = "The hill Koshary marks the old trade route"
_QUOTE_3 = "The river crossing at Sokolowizna was used by traders until 1903"
_QUOTE_4 = "A 1901 archive note states that the Sokolowizna crossing closed after the bridge was built downstream"


def _claim(claim_id, quote, document_id, **overrides):
    claim = {
        "claim_id": claim_id,
        "quote": quote,
        "statement": quote.rstrip("."),
        "interpretation": f"interpretation of {claim_id}",
        "document_id": document_id,
        "ambiguities": [],
        "uncertainty": "low",
        "review_recommendation": "proceed_to_human_review",
    }
    claim.update(overrides)
    return claim


# SYNTHETIC model response (written for tests — not recorded, not real data).
SYNTHETIC_RESPONSE = json.dumps(
    {
        "claims": [
            _claim("c1", _QUOTE_1, "d1"),
            _claim("c3", _QUOTE_3, "d1", uncertainty="high",
                   review_recommendation="needs_expert_review"),
            _claim("c4", _QUOTE_4, "d2",
                   review_recommendation="needs_expert_review"),
        ],
        "contradictions": [
            {
                "contradiction_id": "x1",
                "claim_ids": ["c3", "c4"],
                "kind": "temporal_mismatch",
                "explanation": "1903 use vs 1901 closure note",
                "alternative_interpretations": ["closure may have taken effect later"],
            }
        ],
        "summary": "SYNTHETIC fixture",
    }
)


class _FakeConfig:
    enabled = True
    model = "muse-spark-1.3"
    base_url = "https://api.meta.ai/v1"
    api_key = "secret-must-never-leak"
    timeout_s = 5.0
    system_role = "system"
    json_mode = False


def _result(text):
    return LLMResult(text=text, model_returned="muse-spark-1.3",
                     usage={"total_tokens": 42}, finish_reason="stop")


# ---------------------------------------------------------------- prompts ---
def test_prompts_carry_contract_and_only_supplied_documents():
    system = analysis.build_system_prompt()
    assert "never approve" in system.lower()
    assert "quote" in system and "interpretation" in system
    payload = json.loads(analysis.build_user_prompt(DOCS, focus="routes"))
    assert [d["document_id"] for d in payload["documents"]] == ["d1", "d2"]


# ----------------------------------------------------------------- parser ---
def test_parse_synthetic_response():
    draft = analysis.parse_analysis(SYNTHETIC_RESPONSE)
    assert [c.claim_id for c in draft.claims] == ["c1", "c3", "c4"]
    assert draft.contradictions[0].kind is analysis.ContradictionKind.temporal_mismatch
    assert draft.claims[0].statement != draft.claims[0].interpretation


def test_parse_rejects_invalid_json():
    with pytest.raises(analysis.AnalysisParseError):
        analysis.parse_analysis("{not json")


def test_parse_rejects_missing_quote_and_bad_enum():
    bad = _claim("c1", _QUOTE_1, "d1")
    del bad["quote"]
    with pytest.raises(analysis.AnalysisParseError):
        analysis.parse_analysis(json.dumps({"claims": [bad]}))
    bad2 = _claim("c1", _QUOTE_1, "d1", uncertainty="certain")
    with pytest.raises(analysis.AnalysisParseError):
        analysis.parse_analysis(json.dumps({"claims": [bad2]}))


def test_parse_accepts_legacy_field_aliases():
    """Responses recorded with the first (2026-10-28) contract stay parseable."""
    legacy = {
        "claims": [
            {
                "claim_id": "c1",
                "claim_text": _QUOTE_1,
                "evidence_span": _QUOTE_1,
                "interpretation": "legacy reading",
                "source_id": "d1",
                "uncertainty": "low",
                "review_recommendation": "proceed_to_human_review",
                "contradiction_with": [],
            }
        ]
    }
    draft = analysis.parse_analysis(json.dumps(legacy))
    assert draft.claims[0].document_id == "d1"
    assert draft.claims[0].quote == _QUOTE_1


def test_parse_rejects_external_verification_claims():
    bad = _claim("c1", _QUOTE_1, "d1", interpretation="This is externally verified.")
    with pytest.raises(analysis.AnalysisParseError):
        analysis.parse_analysis(json.dumps({"claims": [bad]}))


# ------------------------------------------------------------- provenance ---
def test_verify_provenance_all_quotes_located():
    checked = analysis.verify_provenance(analysis.parse_analysis(SYNTHETIC_RESPONSE), DOCS)
    assert checked["provenance_check"] == {
        "claims_total": 3,
        "quotes_verified": 3,
        "problems": [],
        "ok": True,
    }
    by_id = {c["claim_id"]: c for c in checked["claims"]}
    assert by_id["c1"]["provenance_status"] == "traced_supported"
    assert by_id["c3"]["provenance_status"] == "traced_uncertain"  # high uncertainty
    assert checked["contradictions"][0]["quotes_verified"] is True


def test_verify_provenance_fabricated_quote_is_caught():
    """A made-up quote (the B0 hallucination case) must not pass."""
    fabricated = _claim("c9", "Traders paid a toll of exactly fifty silver coins", "d1")
    draft = analysis.parse_analysis(json.dumps({"claims": [fabricated]}))
    checked = analysis.verify_provenance(draft, DOCS)
    assert checked["provenance_check"]["ok"] is False
    assert checked["provenance_check"]["quotes_verified"] == 0
    problem = checked["provenance_check"]["problems"][0]
    assert problem["problem"] == "quote_not_located" and problem["item_id"] == "c9"
    assert checked["claims"][0]["provenance_status"] == "unsupported"


def test_verify_provenance_unknown_document_and_dangling_contradiction():
    draft = analysis.parse_analysis(
        json.dumps(
            {
                "claims": [_claim("c1", _QUOTE_1, "ghost")],
                "contradictions": [
                    {"contradiction_id": "x1", "claim_ids": ["c1", "c99"]}
                ],
            }
        )
    )
    checked = analysis.verify_provenance(draft, DOCS)
    kinds = {p["problem"] for p in checked["provenance_check"]["problems"]}
    assert kinds == {"unknown_document", "unknown_claim_reference"}


# ---------------------------------------------------------------- service ---
def test_analyze_documents_result_shape_and_hash():
    with mock.patch.object(
        analyze_svc, "chat_completion_detailed", return_value=_result(SYNTHETIC_RESPONSE)
    ) as call:
        result = analyze_svc.analyze_documents(DOCS, _FakeConfig())
    assert call.call_count == 1
    assert result["status"] == "proposed"  # model proposes; never accepted
    assert result["analysis_id"].startswith("an_")
    assert result["prompt_hash"].startswith("sha256:")
    assert result["model"] == {
        "provider": "meta",
        "requested": "muse-spark-1.3",
        "returned": "muse-spark-1.3",
    }
    assert result["usage"] == {"total_tokens": 42}
    assert result["latency_ms"] >= 0 and result["created_at"].endswith("Z")
    assert result["provenance_check"]["ok"] is True
    assert "secret-must-never-leak" not in json.dumps(result)


def test_analyze_documents_one_format_retry_then_success():
    with mock.patch.object(
        analyze_svc,
        "chat_completion_detailed",
        side_effect=[_result("{broken"), _result(SYNTHETIC_RESPONSE)],
    ) as call:
        result = analyze_svc.analyze_documents(DOCS, _FakeConfig())
    assert call.call_count == 2
    assert result["provenance_check"]["claims_total"] == 3
    # second call carries the format reminder
    assert "Reminder:" in call.call_args_list[1].args[2]


def test_analyze_documents_parse_failure_preserves_raw_and_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(analyze_svc, "_FAILURES_DIR", tmp_path)
    with mock.patch.object(
        analyze_svc,
        "chat_completion_detailed",
        side_effect=[_result("{broken"), _result("still not json")],
    ) as call:
        with pytest.raises(analysis.AnalysisParseError):
            analyze_svc.analyze_documents(DOCS, _FakeConfig())
    assert call.call_count == 2  # exactly one retry
    saved = list(tmp_path.glob("an_*.json"))
    assert len(saved) == 1
    payload = json.loads(saved[0].read_text(encoding="utf-8"))
    assert payload["raw_answers"] == ["{broken", "still not json"]
    assert "secret-must-never-leak" not in saved[0].read_text(encoding="utf-8")


def test_analyze_documents_provider_down_raises_unavailable_no_retry():
    with mock.patch.object(
        analyze_svc, "chat_completion_detailed", return_value=None
    ) as call:
        with pytest.raises(analyze_svc.AnalysisUnavailable):
            analyze_svc.analyze_documents(DOCS, _FakeConfig())
    assert call.call_count == 1


def test_analyze_documents_not_configured():
    class _Off:
        enabled = False
        model = "m"
        base_url = None

    with pytest.raises(analyze_svc.AnalysisUnavailable):
        analyze_svc.analyze_documents(DOCS, _Off())
