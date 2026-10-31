"""Append-only JSONL persistence for analyses and human decisions.

Demo-scope store (OPEN_QUESTIONS Q7): without it, decisions lived only in
process memory and a restart silently lost every human verdict. Events are
appended as one JSON object per line and replayed on startup:

    {"type": "analysis", "record": {...section-6 result + _documents}}
    {"type": "decision", "record": {...review-decision record}}

Append-only matches the decision rules (records are immutable; a repeat
decision is a new record). Enabled only when a path is configured —
``FEN_STORE_PATH`` (scripts/start_demo.py sets
``artifacts/store.jsonl``); with no path the service stays purely
in-memory, which is what the offline test-suite uses.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class JsonlStore:
    def __init__(self, path: Optional[str]):
        self._path = Path(path) if path else None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._path is not None

    def append(self, event_type: str, record: dict) -> None:
        """Append one event; best-effort — a write failure is logged loudly
        but never breaks the request that produced the record."""
        if not self.enabled:
            return
        try:
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"type": event_type, "record": record}, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("could not persist %s event to %s", event_type, self._path)

    def load(self) -> tuple:
        """Replay the log -> (analyses by id, decisions in record order)."""
        analyses: dict = {}
        decisions: list = []
        if not self.enabled or not self._path.is_file():
            return analyses, decisions
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skipping corrupt store line in %s", self._path)
                continue
            record = event.get("record") or {}
            if event.get("type") == "analysis" and record.get("analysis_id"):
                analyses[record["analysis_id"]] = record
            elif event.get("type") == "decision" and record.get("decision_id"):
                decisions.append(record)
        return analyses, decisions


def store_from_env() -> JsonlStore:
    return JsonlStore(os.getenv("FEN_STORE_PATH") or None)
