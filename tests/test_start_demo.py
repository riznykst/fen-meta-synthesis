"""Tests for the demo launcher's provider-config check (scripts/start_demo.py)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_launcher():
    spec = importlib.util.spec_from_file_location(
        "fen_start_demo", REPO / "scripts" / "start_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_llm_config_lists_every_absent_key():
    launcher = _load_launcher()
    assert launcher.missing_llm_config({}) == [
        "FEN_LLM_BASE_URL",
        "FEN_LLM_API_KEY",
        "FEN_LLM_MODEL",
    ]
    assert launcher.missing_llm_config({"FEN_LLM_BASE_URL": "x"}) == [
        "FEN_LLM_API_KEY",
        "FEN_LLM_MODEL",
    ]
    full = {
        "FEN_LLM_BASE_URL": "https://api.meta.ai/v1",
        "FEN_LLM_API_KEY": "k",
        "FEN_LLM_MODEL": "muse-spark-1.3",
    }
    assert launcher.missing_llm_config(full) == []
