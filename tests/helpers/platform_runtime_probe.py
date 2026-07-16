#!/usr/bin/env python3
"""Focused production-path probe launched by each supported host shell."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "check-tool-skill.sh"
DISPATCH = ROOT / "hooks" / "codex-dispatch.py"
ADOPT = ROOT / "skills" / "adopt" / "scripts" / "itd_adopt.py"


def decision(output: str) -> str:
    try:
        value = json.loads(output or "{}")
    except json.JSONDecodeError:
        return ""
    specific = value.get("hookSpecificOutput") or {}
    return str(specific.get("permissionDecision") or value.get("decision") or "")


def invoke(command: list[str], payload: dict, env: dict[str, str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return result.returncode, decision(result.stdout)


def main() -> int:
    session = "platform-" + uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix="itd-platform-probe-") as td:
        env = os.environ.copy()
        env.update({
            "HOME": td,
            "USERPROFILE": td,
            "TMPDIR": td,
            "TEMP": td,
            "TMP": td,
            "PYTHONUTF8": "1",
            "CLAUDE_SESSION_ID": session,
            "PLUGIN_ROOT": str(ROOT),
        })
        payload = {
            "hook_event_name": "PreToolUse",
            "session_id": session,
            "cwd": str(ROOT),
            "tool_name": "Bash",
            "tool_input": {"command": "git status --short", "description": "portable read-only probe"},
        }
        direct = invoke([sys.executable, str(HOOK)], payload, dict(env, ITD_HOST="claude"))
        codex = invoke([sys.executable, str(DISPATCH), "--script", HOOK.name], payload, env)
        help_run = subprocess.run(
            [sys.executable, str(ADOPT), "--help"], cwd=str(ROOT), env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        passed = (
            direct[0] == 0 and direct[1] not in {"deny", "block"}
            and codex[0] == 0 and codex[1] not in {"deny", "block"}
            and direct[1] == codex[1]
            and help_run.returncode == 0
            and "--approved" in help_run.stdout
        )
        report = {
            "status": "pass" if passed else "fail",
            "python": sys.executable,
            "pythonVersion": platform.python_version(),
            "platform": platform.platform(),
            "direct": {"exit": direct[0], "decision": direct[1]},
            "codex": {"exit": codex[0], "decision": codex[1]},
            "adoptHelp": help_run.returncode,
            "manualRepairs": 0,
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
