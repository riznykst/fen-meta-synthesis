"""Durable registry in Supabase for the demo API.

When `SUPABASE_DB_URL` is set, analyses and human decisions are written through
to the Supabase Postgres database (schema: `supabase/migrations/`), and the
public registry is read from the same place. Without it the demo keeps its
local JSONL store and this module is inert — the offline test suite never
touches the network.

Write path (deliberately the governed one):
  * `save_analysis` inserts analyses / analysis_documents / items as they were
    produced — a fresh analysis is `proposed` by construction;
  * `record_decision` calls the `record_decision()` SQL function, so the
    accept-lock on unverified quotes is enforced by the database as well.

The connection uses the Postgres connection string (server-side secret). The
publishable key is for the read-only frontend and is never used here.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional
from urllib.parse import unquote, urlsplit

logger = logging.getLogger(__name__)

VERDICT_TO_STATUS = {
    "accept": "accepted",
    "reject": "rejected",
    "dispute": "disputed",
}


class SupabaseError(RuntimeError):
    """A write or read against Supabase failed."""


class SupabaseRegistry:
    def __init__(self, db_url: str, connect_timeout_s: float = 10.0):
        parts = urlsplit(db_url)
        if parts.scheme not in ("postgres", "postgresql"):
            raise SupabaseError("SUPABASE_DB_URL must start with postgresql://")
        self._user = unquote(parts.username or "")
        self._password = unquote(parts.password or "")
        self._host = parts.hostname or ""
        self._port = parts.port or 5432
        self._database = (parts.path or "/postgres").lstrip("/") or "postgres"
        self._connect_timeout_s = connect_timeout_s

    @property
    def target(self) -> str:
        return f"{self._host}/{self._database}"

    @classmethod
    def from_env(cls) -> Optional["SupabaseRegistry"]:
        url = os.getenv("SUPABASE_DB_URL") or ""
        if not url:
            return None
        try:
            return cls(url)
        except SupabaseError:
            logger.exception("SUPABASE_DB_URL is set but invalid; Supabase sync disabled")
            return None

    # ---------------------------------------------------------- connection --
    def _connect(self):
        try:
            import pg8000.dbapi as dbapi  # noqa: PLC0415 - optional dependency
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise SupabaseError(
                "pg8000 is required for Supabase writes: pip install pg8000"
            ) from exc
        return dbapi.connect(
            user=self._user,
            password=self._password,
            host=self._host,
            port=self._port,
            database=self._database,
            ssl_context=True,
            timeout=self._connect_timeout_s,
        )

    # ------------------------------------------------------------- writes ---
    def save_analysis(self, result: dict, documents: list) -> None:
        """Persist one analysis with its documents and proposed items."""
        analysis = result or {}
        model = analysis.get("model") or {}
        claims = (analysis.get("analysis") or {}).get("claims") or []
        contradictions = (analysis.get("analysis") or {}).get("contradictions") or []

        conn = self._connect()
        try:
            conn.autocommit = False
            cur = conn.cursor()
            cur.execute(
                """
                insert into public.analyses
                  (analysis_id, status, model_provider, model_requested,
                   model_returned, prompt_hash, created_at, latency_ms, usage,
                   provenance_check)
                values (%s, 'proposed', %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                on conflict (analysis_id) do nothing
                returning id
                """,
                (
                    analysis.get("analysis_id"),
                    model.get("provider"),
                    model.get("requested"),
                    model.get("returned"),
                    analysis.get("prompt_hash"),
                    analysis.get("created_at"),
                    analysis.get("latency_ms"),
                    json.dumps(analysis.get("usage")),
                    json.dumps(analysis.get("provenance_check") or {}),
                ),
            )
            row = cur.fetchone()
            if row is None:  # already stored (idempotent re-sync)
                conn.rollback()
                return
            analysis_fk = row[0]

            for doc in documents or []:
                cur.execute(
                    """
                    insert into public.analysis_documents
                      (analysis_fk, document_id, title, content, provenance)
                    values (%s, %s, %s, %s, %s)
                    on conflict (analysis_fk, document_id) do nothing
                    """,
                    (
                        analysis_fk,
                        doc.get("document_id"),
                        doc.get("title"),
                        doc.get("text") or "",
                        doc.get("provenance") or "primary",
                    ),
                )

            for claim in claims:
                cur.execute(
                    """
                    insert into public.items
                      (analysis_fk, item_id, item_type, statement, quote,
                       interpretation, document_id, uncertainty,
                       review_recommendation, ambiguities, quote_verified,
                       provenance_status, provenance)
                    values (%s, %s, 'claim', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (analysis_fk, item_id) do nothing
                    """,
                    (
                        analysis_fk,
                        claim.get("claim_id"),
                        claim.get("statement"),
                        claim.get("quote"),
                        claim.get("interpretation"),
                        claim.get("document_id"),
                        claim.get("uncertainty"),
                        claim.get("review_recommendation"),
                        claim.get("ambiguities") or [],
                        bool(claim.get("quote_verified")),
                        claim.get("provenance_status"),
                        claim.get("provenance") or "primary",
                    ),
                )

            claim_provenance = {
                c.get("claim_id"): (c.get("provenance") or "primary") for c in claims
            }
            for contra in contradictions:
                # A contradiction inherits the weakest provenance of the claims
                # it links, so a synthetic source never looks authoritative.
                refs = contra.get("claim_ids") or []
                if "synthetic" in {claim_provenance.get(c) for c in refs}:
                    contra_prov = "synthetic"
                elif "secondary" in {claim_provenance.get(c) for c in refs}:
                    contra_prov = "secondary"
                else:
                    contra_prov = "primary"
                cur.execute(
                    """
                    insert into public.items
                      (analysis_fk, item_id, item_type, contradiction_kind,
                       explanation, alternative_interpretations, claim_ids,
                       quote_verified, provenance)
                    values (%s, %s, 'contradiction', %s, %s, %s, %s, %s, %s)
                    on conflict (analysis_fk, item_id) do nothing
                    """,
                    (
                        analysis_fk,
                        contra.get("contradiction_id"),
                        contra.get("kind"),
                        contra.get("explanation") or "",
                        contra.get("alternative_interpretations") or [],
                        contra.get("claim_ids") or [],
                        bool(contra.get("quotes_verified")),
                        contra_prov,
                    ),
                )
            conn.commit()
        except Exception as exc:  # noqa: BLE001 - caller decides how loud to be
            conn.rollback()
            raise SupabaseError(f"could not persist analysis: {exc}") from exc
        finally:
            conn.close()

    def record_decision(
        self,
        analysis_id: str,
        item_id: str,
        verdict: str,
        reviewer: str,
        comment: str = "",
    ) -> dict:
        """Record a human verdict through the governed SQL function."""
        if verdict not in VERDICT_TO_STATUS:
            raise SupabaseError(f"unsupported verdict: {verdict}")
        conn = self._connect()
        try:
            conn.autocommit = False
            cur = conn.cursor()
            cur.execute(
                "select public.record_decision(%s, %s, %s::public.verdict, %s, %s)",
                (analysis_id, item_id, verdict, reviewer, comment or ""),
            )
            cur.execute(
                """
                select d.decision_id, d.recorded_at, d.status
                from public.decisions d
                join public.items i on i.id = d.item_fk
                join public.analyses a on a.id = i.analysis_fk
                where a.analysis_id = %s and i.item_id = %s
                order by d.recorded_at desc
                limit 1
                """,
                (analysis_id, item_id),
            )
            row = cur.fetchone()
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            raise SupabaseError(f"could not record decision: {exc}") from exc
        finally:
            conn.close()
        if row is None:
            raise SupabaseError("decision was accepted by the database but not found on read-back")
        return {
            "decision_id": row[0],
            "recorded_at": row[1].isoformat().replace("+00:00", "Z") if hasattr(row[1], "isoformat") else str(row[1]),
            "status": row[2],
        }

    # -------------------------------------------------------------- reads ---
    def load_registry(self, limit: int = 100) -> list:
        """Accepted knowledge, newest first (same shape as GET /registry)."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                select item_id, item_type, status, statement, quote, document_id,
                       reviewer, verdict, comment, recorded_at, decision_id,
                       analysis_id, model_returned, prompt_hash, quote_verified,
                       provenance
                from public.registry_public
                order by recorded_at desc
                limit %s
                """,
                (int(limit),),
            )
            rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            raise SupabaseError(f"could not read registry: {exc}") from exc
        finally:
            conn.close()
        out = []
        for row in rows:
            out.append({
                "item_id": row[0],
                "item_type": row[1],
                "status": row[2],
                "statement": row[3] or "",
                "quote": row[4] or "",
                "document_id": row[5] or "",
                "reviewer": row[6],
                "verdict": row[7],
                "comment": row[8] or "",
                "recorded_at": row[9].isoformat().replace("+00:00", "Z") if hasattr(row[9], "isoformat") else str(row[9]),
                "decision_id": row[10],
                "analysis_id": row[11],
                "model_returned": row[12],
                "prompt_hash": row[13],
                "quote_verified": bool(row[14]),
                "provenance": row[15] or "primary",
                "source": "supabase",
            })
        return out
