"""Shared proof-chain fixture for review/cache integration tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "skills" / "_shared" / "itd_verification_loop.py"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LOOP), *args], cwd=str(root),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"}, timeout=30)


def _path(result: subprocess.CompletedProcess[str]) -> Path:
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return Path(result.stdout.strip().splitlines()[-1])


def make_review_receipt(root: Path, *, unit_id: str, risk_tier: str,
                        kind: str = "general", command: str = "true") -> Path:
    claim_id = f"{unit_id}:{kind}-review"
    safe = claim_id.replace(":", "-")
    base = root / ".itd-memory" / "verification-loop"
    prompt = base / "prompts" / f"{safe}.md"
    report = base / "reports" / f"{safe}.md"
    prompt.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text(
        f"Independently check the exact {kind} claim for {claim_id}.\n",
        encoding="utf-8")
    report.write_text(
        "# Independent checker\n\n```json\n"
        + json.dumps({"verdict": "PASSED", "findings": [], "unverified": []})
        + "\n```\n", encoding="utf-8")
    machine = _path(_run(
        root, "machine", "--root", str(root), "--unit-id", claim_id,
        "--risk-tier", risk_tier, "--command", "oracle=" + command))
    checker: Path | None = None
    if risk_tier != "low":
        mode = "targeted" if risk_tier == "medium" else "full"
        checker = _path(_run(
            root, "checker", "--root", str(root), "--unit-id", claim_id,
            "--risk-tier", risk_tier, "--mode", mode,
            "--report", str(report), "--prompt-file", str(prompt),
            "--maker-provider", "openai", "--maker-model", "maker-model",
            "--maker-session", "maker-session",
            "--checker-provider", "openai", "--checker-model", "checker-model",
            "--checker-session", "checker-session"))
    args = [
        "adjudicate", "--root", str(root), "--unit-id", claim_id,
        "--risk-tier", risk_tier, "--machine", str(machine),
    ]
    if checker is not None:
        args += ["--checker", str(checker)]
    return _path(_run(root, *args))
