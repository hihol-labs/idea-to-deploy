#!/usr/bin/env python3
"""Cold-session reconstruction from durable local state, with no transcript."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
passed = failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    print(f"{'PASS' if condition else 'FAIL'}  {name}"
          + (f" [{detail}]" if detail and not condition else ""))
    if condition:
        passed += 1
    else:
        failed += 1


def load_hook(filename: str, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(HOOKS / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run_hook(path: Path, cwd: Path, home: Path, session: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update({
        "HOME": str(home), "USERPROFILE": str(home),
        "CLAUDE_SESSION_ID": session,
        "TMPDIR": str(home / "tmp"), "TMP": str(home / "tmp"),
        "TEMP": str(home / "tmp"),
    })
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, str(path)], input=json.dumps({"session_id": session}),
        capture_output=True, text=True, cwd=cwd, env=env, timeout=30)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="itd-fresh-resume-"))
    project = tmp / "project"
    mem = project / ".itd-memory"
    home = tmp / "empty-host-home"
    mem.mkdir(parents=True)
    home.mkdir()

    state = {
        "currentUnit": {
            "id": "HE5-003", "goal": "host-neutral continuity",
            "status": "in_progress"},
        "nextAction": "implement local continuity",
        "blockers": ["legacy mirror conflict"],
        "gateResults": {"review": "pending", "tests": "passed"},
    }
    goal = {
        "version": 1, "goal": "reach harness 5/5", "status": "active",
        "createdAt": "2026-07-15T00:00:00Z",
        "updatedAt": "2026-07-15T01:00:00Z",
        "currentUnitId": "HE5-003",
        "units": [
            {"id": "HE5-002", "criterion": "host parity",
             "verificationCommand": "verify parity", "status": "verified",
             "evidence": "H1 parity 87/87"},
            {"id": "HE5-003", "criterion": "host-neutral continuity",
             "verificationCommand": "verify resume", "status": "in_progress",
             "evidence": "", "blockedReason": ""},
        ],
    }
    (mem / "STATE.json").write_text(json.dumps(state), encoding="utf-8")
    (mem / "GOAL.json").write_text(json.dumps(goal), encoding="utf-8")
    (mem / "events.jsonl").write_text(
        json.dumps({"type": "unit", "name": "HE5-002", "decision": "verified"})
        + "\n", encoding="utf-8")
    (mem / "session_2026-07-15.md").write_text(
        "DURABLE-LOCAL-SESSION\nNext action: implement local continuity\n",
        encoding="utf-8")
    (mem / "MEMORY.md").write_text(
        "- [next session](session_2026-07-15.md) — resume H2\n",
        encoding="utf-8")

    old_home = os.environ.get("HOME")
    old_profile = os.environ.get("USERPROFILE")
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    try:
        preflight = load_hook("pre-flight-check.sh", "itd_h2_resume_preflight")
        context = preflight.itd_state_context(project)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
        if old_profile is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = old_profile

    check("cold context identifies the active unit",
          "HE5-003" in context and "host-neutral continuity" in context)
    check("cold context carries the last verified evidence",
          "HE5-002" in context and "H1 parity 87/87" in context)
    check("cold context carries blockers", "legacy mirror conflict" in context)
    check("cold context carries the exact next action",
          "implement local continuity" in context)
    check("cold context preserves WIP=1 and pending gates",
          "WIP=1" in context and "review" in context)

    sid = "fresh-" + uuid.uuid4().hex
    preflight_run = run_hook(HOOKS / "pre-flight-check.sh", project, home, sid)
    check("real pre-flight hook succeeds with an empty host home",
          preflight_run.returncode == 0, preflight_run.stderr)
    check("real pre-flight output reconstructs all four required fields",
          all(token in preflight_run.stdout for token in (
              "HE5-003", "H1 parity 87/87", "legacy mirror conflict",
              "implement local continuity")), preflight_run.stdout[-300:])

    session_run = run_hook(
        HOOKS / "session-open-diagnostic.sh", project, home, sid + "-diagnostic")
    check("real session-open hook succeeds without transcript/private memory",
          session_run.returncode == 0, session_run.stderr)
    check("session-open reads the same local checkpoint",
          "DURABLE-LOCAL-SESSION" in session_run.stdout)

    missing = tmp / "missing-state"
    (missing / ".itd-memory").mkdir(parents=True)
    (missing / ".itd-memory" / "MEMORY.md").write_text(
        "index without state", encoding="utf-8")
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(home)
    try:
        missing_context = preflight.itd_state_context(missing)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
    check("missing local STATE/GOAL produces no false resume claim",
          missing_context == "")

    registry = json.loads((ROOT / "docs" / "host-adapters.json").read_text(
        encoding="utf-8"))
    shared = registry.get("parity", {}).get("shared", [])
    check("both adapters share persistent project-local state",
          "persistent .itd-memory state" in shared)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
