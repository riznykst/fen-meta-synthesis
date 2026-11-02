"""Structured claim-analysis contract (T2) — decision-support only (ADR-004).

Canonical contract for the FEN x Meta workflow, per SPEC section 6:

- Input documents: ``{document_id, title, text}``.
- Model output: ``{claims[], contradictions[], summary?}`` where every claim
  carries an exact ``quote`` (evidence span), a ``statement`` of the claim,
  and a separate ``interpretation`` — the extracted claim and the model's
  reading of it are never merged into one field.
- ``parse_analysis`` validates structure only; ``verify_provenance`` checks
  quotes against the documents supplied in the current request.

Legacy field aliases (``source_id`` / ``evidence_span`` / ``claim_text`` and
per-claim ``contradiction_with``) are accepted by the parser so responses
recorded during the 2026-10-28 session with the first working contract
remain parseable; new prompts always emit the canonical names.

A provenance check is not proof of truth and never approval: results stay
``status="proposed"`` until a human decision is recorded (T4).
"""
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import List, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

logger = logging.getLogger(__name__)


class AnalysisParseError(ValueError):
    """Model response failed the structured contract (carries ``errors``)."""

    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class Uncertainty(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    insufficient_evidence = "insufficient_evidence"


class ReviewRecommendation(str, Enum):
    proceed_to_human_review = "proceed_to_human_review"
    needs_expert_review = "needs_expert_review"
    more_evidence_required = "more_evidence_required"


class ContradictionKind(str, Enum):
    direct_negation = "direct_negation"
    temporal_mismatch = "temporal_mismatch"
    value_mismatch = "value_mismatch"
    other = "other"


class SourceDocument(BaseModel):
    """One source document supplied in the analysis request (SPEC section 6).

    ``provenance`` classifies the document itself (primary source, secondary
    commentary, or synthetic illustration). It is metadata about the source,
    not about the model's claim, and it is echoed on every claim drawn from
    that document so the reviewer can see when evidence is synthetic."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    document_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("document_id", "source_id"),
        serialization_alias="document_id",
    )
    text: str = Field(min_length=1)
    title: Optional[str] = None
    provenance: str = Field(default="primary", description="primary | secondary | synthetic")

    @model_validator(mode="after")
    def _known_provenance(self) -> "SourceDocument":
        allowed = {"primary", "secondary", "synthetic"}
        if self.provenance not in allowed:
            raise ValueError(
                f"provenance must be one of {sorted(allowed)}, got {self.provenance!r}"
            )
        return self


class ClaimDraft(BaseModel):
    """One extracted claim as returned by the model (pre-provenance-check)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    claim_id: str = Field(min_length=1)
    quote: str = Field(
        min_length=1,
        validation_alias=AliasChoices("quote", "evidence_span"),
        serialization_alias="quote",
        description="Exact span copied verbatim from the referenced document",
    )
    statement: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("statement", "claim_text"),
        serialization_alias="statement",
        description="The claim as asserted, distinct from interpretation",
    )
    interpretation: str = Field(min_length=1)
    document_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("document_id", "source_id"),
        serialization_alias="document_id",
    )
    ambiguities: List[str] = Field(default_factory=list)
    uncertainty: Uncertainty
    review_recommendation: ReviewRecommendation
    # Legacy (2026-10-28 first contract): per-claim contradiction pointers.
    contradiction_with: List[str] = Field(default_factory=list, exclude=True)


class ContradictionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contradiction_id: str = Field(min_length=1)
    claim_ids: List[str] = Field(min_length=2)
    kind: ContradictionKind = ContradictionKind.other
    explanation: str = ""
    alternative_interpretations: List[str] = Field(default_factory=list)


class AnalysisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: List[ClaimDraft] = Field(min_length=1)
    contradictions: List[ContradictionDraft] = Field(default_factory=list)
    summary: Optional[str] = None

    @model_validator(mode="after")
    def _unique_ids_and_legacy_contradictions(self) -> "AnalysisDraft":
        claim_ids = set()
        for claim in self.claims:
            if claim.claim_id in claim_ids:
                raise ValueError(f"duplicate claim_id: {claim.claim_id}")
            claim_ids.add(claim.claim_id)
        seen_pairs = set()
        for contra in self.contradictions:
            if contra.contradiction_id in seen_pairs:
                raise ValueError(f"duplicate contradiction_id: {contra.contradiction_id}")
            seen_pairs.add(contra.contradiction_id)
        # Synthesize canonical contradictions from legacy per-claim pointers.
        pairs = set()
        for claim in self.claims:
            for other in claim.contradiction_with:
                if other in claim_ids and other != claim.claim_id:
                    pairs.add(tuple(sorted((claim.claim_id, other))))
        existing = {tuple(sorted(c.claim_ids)) for c in self.contradictions}
        for index, pair in enumerate(sorted(pairs - existing), start=1):
            self.contradictions.append(
                ContradictionDraft(
                    contradiction_id=f"x-legacy-{index}",
                    claim_ids=list(pair),
                    kind=ContradictionKind.other,
                    explanation="Synthesized from legacy per-claim contradiction_with pointers.",
                )
            )
        return self


_FORBIDDEN_ASSERTIONS = (
    "externally verified",
    "verified externally",
    "verified truth",
    "community approved",
    "community-approved",
    "governance approved",
    "governance-approved",
    "approved by the community",
    "proven truth",
    "confirmed true",
)


def analysis_json_schema() -> dict:
    """JSON Schema for the model's structured output (provider-side).

    Derived from the same :class:`AnalysisDraft` Pydantic contract the parser
    validates (identical to ``schemas/analysis/document-analysis.schema.json``),
    minus the legacy ``contradiction_with`` input alias: recorded legacy
    responses stay parseable, but schema-constrained decoding is asked for
    the canonical field names only."""
    schema = json.loads(json.dumps(AnalysisDraft.model_json_schema()))
    claim_props = schema.get("$defs", {}).get("ClaimDraft", {}).get("properties", {})
    claim_props.pop("contradiction_with", None)
    return schema


def analysis_response_format(name: str = "DocumentAnalysis") -> dict:
    """``response_format`` value asking the provider (Meta Model API
    structured output) to constrain decoding to :func:`analysis_json_schema`.
    No ``strict`` flag: Meta constrains output to the schema either way, and
    omitting it accepts schemas outside the strict subset (HTTP 400 guard)."""
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "schema": analysis_json_schema()},
    }


def build_system_prompt() -> str:
    """System prompt carrying the output contract (model proposes only)."""
    return (
        "You are a claim-analysis assistant for a community data-governance "
        "framework. You extract claims from the supplied source documents and "
        "structure them for HUMAN review. You never approve knowledge, never "
        "decide governance outcomes, and never claim external verification.\n"
        "Return ONLY this JSON (no markdown, no code fences): "
        '{"claims": [{"claim_id": "c1", "quote": "<exact span copied verbatim from the document>", '
        '"statement": "<the claim as asserted, in concise wording>", '
        '"interpretation": "<your interpretation, kept separate from the claim itself>", '
        '"document_id": "<id of one supplied document>", '
        '"ambiguities": ["<ambiguity or missing context, [] if none>"], '
        '"uncertainty": "low | medium | high | insufficient_evidence", '
        '"review_recommendation": "proceed_to_human_review | needs_expert_review | more_evidence_required"}], '
        '"contradictions": [{"contradiction_id": "x1", "claim_ids": ["c1", "c2"], '
        '"kind": "direct_negation | temporal_mismatch | value_mismatch | other", '
        '"explanation": "<why the claims may contradict>", '
        '"alternative_interpretations": ["<reading that would resolve it, [] if none>"]}], '
        '"summary": "<optional one-line summary>"}.\n'
        "Rules: use only the supplied document_id values; copy quote verbatim "
        "so it can be located in the source; report contradictions between "
        "claims whenever dates, values or assertions may conflict; set "
        "uncertainty to insufficient_evidence when evidence is weak; every "
        "claim goes to human review — none is approved by you."
    )


def build_user_prompt(documents: List[SourceDocument], focus: Optional[str] = None) -> str:
    payload = {
        "focus": focus,
        "documents": [
            {"document_id": d.document_id, "title": d.title, "text": d.text}
            for d in documents
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_analysis(answer: Optional[str]) -> AnalysisDraft:
    """Parse and structurally validate the model's analysis response.

    Rejects (raises :class:`AnalysisParseError`): empty/malformed JSON,
    missing required fields, invalid types, unsupported enum values, unknown
    fields (including any field claiming external verification), duplicate
    ids, and free-text assertions of external verification or approval.
    Tolerates markdown code fences."""
    if not answer:
        raise AnalysisParseError(["empty model response"])
    cleaned = answer.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AnalysisParseError([f"malformed JSON: {exc}"]) from exc
    if not isinstance(data, dict):
        raise AnalysisParseError(["top-level analysis must be a JSON object"])

    lowered = json.dumps(data, ensure_ascii=False).lower()
    for phrase in _FORBIDDEN_ASSERTIONS:
        if phrase in lowered:
            raise AnalysisParseError(
                [f"unsupported claim of external verification/approval: {phrase!r}"]
            )
    try:
        return AnalysisDraft.model_validate(data)
    except ValidationError as exc:
        errors = [
            "{}: {}".format(".".join(str(p) for p in err["loc"]), err["msg"])
            for err in exc.errors()
        ]
        raise AnalysisParseError(errors) from exc


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def verify_provenance(draft: AnalysisDraft, documents: List[SourceDocument]) -> dict:
    """Verify quotes against the documents supplied in this request.

    Distinguishes per claim: document exists / not; quote locatable (exact or
    whitespace-normalised) / not; interpretation backed by located evidence
    (``traced_supported``), declared uncertain (``traced_uncertain``), or
    ``unsupported``. Contradiction references are checked against claim ids.

    Returns ``{claims, contradictions, provenance_check}`` where
    ``provenance_check = {claims_total, quotes_verified, problems, ok}`` —
    traceability and evidence-location validity only, never proof of truth.
    """
    sources = {d.document_id: d.text for d in documents}
    normalized = {key: _normalize_ws(text) for key, text in sources.items()}
    provenance = {d.document_id: d.provenance for d in documents}
    claim_ids = {c.claim_id for c in draft.claims}
    claims_out = []
    problems: List[dict] = []
    quotes_verified = 0
    by_id = {}

    for claim in draft.claims:
        document_exists = claim.document_id in sources
        quote_verified = bool(
            document_exists
            and _normalize_ws(claim.quote) in normalized[claim.document_id]
        )
        if not document_exists:
            status = "unsupported"
            problems.append(
                {
                    "item_id": claim.claim_id,
                    "problem": "unknown_document",
                    "detail": f"document_id {claim.document_id!r} not in supplied documents",
                }
            )
        elif not quote_verified:
            status = "unsupported"
            problems.append(
                {
                    "item_id": claim.claim_id,
                    "problem": "quote_not_located",
                    "detail": f"quote not located in document {claim.document_id!r}",
                }
            )
        elif claim.uncertainty in (Uncertainty.high, Uncertainty.insufficient_evidence):
            status = "traced_uncertain"
        else:
            status = "traced_supported"
        if quote_verified:
            quotes_verified += 1
        record = claim.model_dump(mode="json", by_alias=True)
        record["quote_verified"] = quote_verified
        record["provenance_status"] = status
        # Provenance of the SOURCE document (primary / secondary / synthetic),
        # so the reviewer can see when a verified quote comes from an
        # illustrative source rather than from a primary text.
        record["provenance"] = provenance.get(claim.document_id, "unknown")
        claims_out.append(record)
        by_id[claim.claim_id] = record

    contradictions_out = []
    for contra in draft.contradictions:
        dangling = [ref for ref in contra.claim_ids if ref not in claim_ids]
        if dangling:
            problems.append(
                {
                    "item_id": contra.contradiction_id,
                    "problem": "unknown_claim_reference",
                    "detail": f"contradiction references unknown claim(s) {dangling}",
                }
            )
        record = contra.model_dump(mode="json")
        record["quotes_verified"] = bool(
            not dangling
            and all(by_id[ref]["quote_verified"] for ref in contra.claim_ids)
        )
        contradictions_out.append(record)

    return {
        "claims": claims_out,
        "contradictions": contradictions_out,
        "provenance_check": {
            "claims_total": len(claims_out),
            "quotes_verified": quotes_verified,
            "problems": problems,
            "ok": not problems,
        },
    }
