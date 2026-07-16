#!/usr/bin/env python3
"""Fixed behavioural metric for the soft completion-stop component.

Prints one JSON metric and always exits zero.  The ablation runner compares the
score with the normal environment and with ITD_COMPLETION_STOP=0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "completion-stop.sh"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-ablate-completion-stop-") as td:
        repo = Path(td)
        run(["git", "init", "-q"], repo)
        run(["git", "config", "user.email", "benchmark@example.com"], repo)
        run(["git", "config", "user.name", "Benchmark"], repo)
        source = repo / "app.py"
        source.write_text("VALUE = 1\n", encoding="utf-8")
        run(["git", "add", "app.py"], repo)
        run(["git", "commit", "-qm", "fixture"], repo)
        source.write_text("VALUE = 2\n", encoding="utf-8")
        payload = json.dumps({"session_id": "ablation", "cwd": str(repo)})
        proc = subprocess.run([sys.executable, str(HOOK)], input=payload,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=os.environ.copy())
        try:
            out = json.loads(proc.stdout or "{}")
        except Exception:
            out = {}
        message = str(out.get("systemMessage") or "")
        score = 1 if "[COMPLETION-STOP]" in message else 0
        print(json.dumps({"score": score}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
