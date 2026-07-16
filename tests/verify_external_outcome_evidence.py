#!/usr/bin/env python3
"""Evaluate only real consented external outcome evidence (PE5-008)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "evidence" / "external-outcomes" / "INDEX.json"
SCRIPT = ROOT / "scripts" / "itd_external_outcomes.py"

result = subprocess.run(
    [sys.executable, str(SCRIPT), "evaluate", "--index", str(INDEX)],
    cwd=str(ROOT), text=True, encoding="utf-8", errors="replace",
)
raise SystemExit(result.returncode)
