#!/usr/bin/env python3
"""Acceptance probe of the INSTALLED pii-egress-guard hook (plan session 1, recorded in session 2).

Feeds three PreToolUse payloads to the hook command registered in a Claude settings.json and prints
the decision of each: a built-in desktop UI tool, a local scan whose path contains a transport word,
and an HTTP POST with a data flag to an external URL. Expected: local, local, ask/deny.

Usage (the hook runs with the interpreter the settings name; on WSL run it twice):
  python3 egress_acceptance_probe.py ~/.claude/settings.json /tmp
  python3 egress_acceptance_probe.py /mnt/c/Users/<user>/.claude/settings.json /mnt/c/Users/<user>
Read-only: the hook only previews; nothing is executed or sent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

CASES = (
    ("host-ui-tool", "mcp__ccd_turn__update_plan", {"items": [{"content": "probe", "status": "pending"}]}),
    ("ssh-path-scan", "Bash", {"command": "ls -la /tmp/ssh-d2719c3f/agent.1", "description": "probe"}),
    ("http-post-external", "Bash", {"command": "curl -d 'a=1' https://example.com/api", "description": "probe"}),
)


def egress_command(settings: Path) -> str:
    data = json.loads(settings.read_text(encoding="utf-8"))
    for matcher in data.get("hooks", {}).get("PreToolUse", []):
        for hook in matcher.get("hooks", []):
            if "pii-egress-guard" in hook.get("command", ""):
                return hook["command"]
    raise SystemExit(f"pii-egress-guard is not registered in {settings}")


def to_wsl(command: str) -> str:
    # A Windows settings file names "C:/.../python.exe" ...; from WSL only the interpreter is reached
    # under /mnt/c (interop), its arguments stay Windows paths for the Windows process.
    if os.name == "nt" or not command.startswith('"C:/'):
        return command
    return '"/mnt/c/' + command[len('"C:/'):]


def decision(stdout: str) -> str:
    try:
        payload = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
    except ValueError:
        return "unparsed"
    return payload.get("hookSpecificOutput", {}).get("permissionDecision", "none")


def main() -> int:
    settings, cwd = Path(sys.argv[1]).expanduser(), sys.argv[2]
    command = to_wsl(egress_command(settings))
    print(json.dumps({"settings": str(settings), "command": command}, ensure_ascii=False))
    for name, tool, tool_input in CASES:
        payload = {"session_id": "itd-baseline-probe", "transcript_path": "", "cwd": cwd,
                   "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
        start = time.perf_counter()
        done = subprocess.run(command, shell=True, input=json.dumps(payload), capture_output=True,
                              text=True, encoding="utf-8", cwd=cwd, timeout=120)
        print(json.dumps({"case": name, "exit": done.returncode, "decision": decision(done.stdout),
                          "ms": round((time.perf_counter() - start) * 1000)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
