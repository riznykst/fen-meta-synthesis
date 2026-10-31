"""One-command local demo launcher (T9 analog of demo_seed.sh).

Loads FEN_LLM_* from a repo-root .env when present (values never printed),
then starts the two demo processes as children:

- mock FEN API (with POST /analyze, /decisions, /provenance) on :8100
- Status API serving the web portal (Review screen) on :8082

and waits until both answer /healthz. Ctrl-C stops both children.
No Kafka/Fuseki/Docker required for the hackathon Review scenario; the
full research stack still runs via docker compose (see README).

Usage: python scripts/start_demo.py
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = (
    "FEN_LLM_BASE_URL",
    "FEN_LLM_API_KEY",
    "FEN_LLM_MODEL",
    "FEN_LLM_TIMEOUT_S",
    "FEN_LLM_SYSTEM_ROLE",
    "FEN_LLM_JSON_MODE",
    "FEN_LLM_STRUCTURED_OUTPUT",
    # Durable registry (optional): analyses + decisions are written to Supabase
    # when SUPABASE_DB_URL is present; GET /registry then reads from there.
    "SUPABASE_DB_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
)


def load_dotenv() -> None:
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in ENV_KEYS and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def wait_health(url: str, timeout_s: float = 30.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001 - service may still be starting
            time.sleep(0.5)
    return False


def _already_serving(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001 - not serving is the expected case
        return False


def main() -> int:
    load_dotenv()
    # Persist analyses + human decisions across restarts (JSONL store,
    # artifacts/ is gitignored). Children inherit this environment.
    os.environ.setdefault(
        "FEN_STORE_PATH", str(REPO_ROOT / "artifacts" / "store.jsonl")
    )
    for port, url in ((8100, "http://127.0.0.1:8100/healthz"),
                      (8082, "http://127.0.0.1:8082/healthz")):
        if _already_serving(url):
            print(f"ERROR: something already serves :{port} ({url} answers).")
            print("Stop that instance first, then run the demo launcher again.")
            return 2
    if not os.environ.get("FEN_LLM_BASE_URL"):
        print("NOTE: FEN_LLM_BASE_URL is not set — the Review screen will open,")
        print("but Analyse will return 502 until you configure a provider")
        print("(copy .env.example to .env and fill in your Meta key).")
    python = sys.executable
    children = [
        subprocess.Popen(
            [python, "-m", "uvicorn", "mock_fen_api.main:app",
             "--host", "127.0.0.1", "--port", "8100"],
            cwd=REPO_ROOT,
        ),
        subprocess.Popen(
            [python, "-m", "uvicorn", "services.status_api.main:app",
             "--host", "127.0.0.1", "--port", "8082"],
            cwd=REPO_ROOT,
        ),
    ]
    try:
        ok_mock = wait_health("http://127.0.0.1:8100/healthz")
        ok_status = wait_health("http://127.0.0.1:8082/healthz")
        print(f"mock-fen-api :8100 health: {'ok' if ok_mock else 'FAILED'}")
        print(f"status-api   :8082 health: {'ok' if ok_status else 'FAILED'}")
        if not (ok_mock and ok_status):
            return 1
        print()
        print("Open the Review screen:  http://127.0.0.1:8082/web/portal/review.html")
        print("Then follow DEMO.md (3 minutes). Ctrl-C stops the demo.")
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return 1
    except KeyboardInterrupt:
        print("\nstopping demo…")
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
