#!/usr/bin/env bash
# One-command demo preparation (T9). The real launcher is cross-platform
# Python; this wrapper exists for bash environments (CI/Linux/macOS).
# Windows: run  python scripts/start_demo.py  in PowerShell instead.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/start_demo.py
