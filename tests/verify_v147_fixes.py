#!/usr/bin/env python3
"""Functional tests for the v1.47.0 retro-fix pack (RETRO-2026-07-04 #1,2,3,6).

Pins the behaviors the first live /retro run flagged:
  #1 careful.sh — `git branch -D` warns; the soft `-d` and gh's
     `--delete-branch` do NOT (the file-global IGNORECASE used to swallow the
     case distinction: 3 false positives in one day).
  #2 check-tool-skill.sh is_readonly_bash — unwraps `wsl.exe … bash -lc "…"`
     wrappers and recognises gh read-only subcommands / `cd &&` chains, while
     mutations (inner `git push`, `gh pr merge`, redirects, `git branch -d`)
     stay gated. 628 ceremony bypasses came from this gap.
  #3 pre-flight-check.sh — warns when `.itd-memory` is in use but
     `events.jsonl` is missing/empty (blind VCR //retro), silent otherwise.
  #6 cost-tracker.sh — session id no longer derives from getppid() (a new
     ledger per hook spawn: 500 stale files); old ledgers are rotated.

Cross-platform by construction. Self-contained:
  python3 tests/verify_v147_fixes.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def load_module(hook: str):
    src = ROOT / "hooks" / hook
    tmp = Path(tempfile.gettempdir()) / f"_v147_{hook.replace('.', '_')}.py"
    shutil.copy(src, tmp)
    spec = importlib.util.spec_from_file_location(tmp.stem, tmp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_hook(hook: str, payload: dict, cwd: Path | None = None) -> str:
    env = {**os.environ, "PYTHONUTF8": "1", "CAREFUL_MODE": "1"}
    proc = subprocess.run(
        [PY, str(ROOT / "hooks" / hook)], input=json.dumps(payload),
        capture_output=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(cwd) if cwd else None, timeout=60)
    return proc.stdout or ""


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def main() -> int:
    # --- #1 careful.sh: case-sensitive force-delete ---
    out = run_hook("careful.sh", bash("git branch -D feat/x"))
    check("#1 careful warns on git branch -D", "force-deletes" in out, out[:200])
    out = run_hook("careful.sh", bash("git branch --delete --force feat/x"))
    check("#1 careful warns on --delete --force", "force-deletes" in out, out[:200])
    out = run_hook("careful.sh", bash("GIT BRANCH -D feat/x"))
    check("#1 careful warns on uppercase GIT BRANCH -D (no keyword regression)",
          "force-deletes" in out, out[:200])
    out = run_hook("careful.sh", bash("git branch -Df feat/x"))
    check("#1 careful warns on combined -Df", "force-deletes" in out, out[:200])
    out = run_hook("careful.sh", bash("git branch -fD feat/x"))
    check("#1 careful warns on combined -fD", "force-deletes" in out, out[:200])
    out = run_hook("careful.sh", bash("git branch -d feat/x"))
    check("#1 careful SILENT on soft git branch -d", "force-deletes" not in out, out[:200])
    out = run_hook("careful.sh", bash("GIT branch -d feat/x"))
    check("#1 careful SILENT on uppercase-keyword soft -d",
          "force-deletes" not in out, out[:200])
    out = run_hook("careful.sh",
                   bash("gh pr merge 1 --squash --delete-branch && git branch -d x"))
    check("#1 careful SILENT on gh --delete-branch + -d",
          "force-deletes" not in out, out[:200])

    # --- #2 is_readonly_bash: wsl unwrap + gh read-only + mutations gated ---
    cts = load_module("check-tool-skill.sh")
    ro = cts.is_readonly_bash
    check("#2 wsl-wrapped read-only exempted",
          ro(bash('wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd /repo && git log --oneline -5"')))
    check("#2 wsl-wrapped mutation still gated",
          not ro(bash('wsl.exe -d Ubuntu-24.04 --exec bash -lc "git push origin main"')))
    check("#2 wsl-wrapped inner redirect still gated",
          not ro(bash('wsl.exe --exec bash -lc "git log > /tmp/x"')))
    # v1.53.0 (retro 2026-07-05, P1): the SHORT `-e` form of --exec must unwrap too.
    check("#2 wsl -e (short exec) read-only exempted",
          ro(bash("wsl -e bash -lc 'cd /repo && git status --short'")))
    check("#2 wsl -d X -e (short exec) read-only exempted",
          ro(bash("wsl -d Ubuntu-24.04 -e bash -lc 'git log --oneline -5'")))
    check("#2 wsl -e mutation still gated",
          not ro(bash("wsl -e bash -lc 'git commit -m x'")))
    check("#2 gh pr checks exempted", ro(bash("gh pr checks 108")))
    check("#2 gh pr merge still gated", not ro(bash("gh pr merge 108 --squash")))
    check("#2 cd && read-only exempted", ro(bash("cd /x && git status")))
    check("#2 cd && rm still gated", not ro(bash("cd /x && rm -rf y")))
    check("#2 git branch listing exempted", ro(bash("git branch -vv")))
    check("#2 git branch -d NOT read-only", not ro(bash("git branch -d x")))
    check("#2 git remote add NOT read-only", not ro(bash("git remote add o url")))

    # --- #3 pre-flight events.jsonl hint ---
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        mem = proj / ".itd-memory"
        mem.mkdir()
        (mem / "STATE.json").write_text(
            json.dumps({"nextAction": "do x", "blockers": []}), encoding="utf-8")
        out = run_hook("pre-flight-check.sh", {}, cwd=proj)
        check("#3 pre-flight warns on missing events.jsonl",
              "events.jsonl" in out, out[:300])
        (mem / "events.jsonl").write_text(
            '{"type":"unit","name":"U-1","decision":"activated"}\n', encoding="utf-8")
        out = run_hook("pre-flight-check.sh", {}, cwd=proj)
        check("#3 pre-flight silent when events.jsonl has entries",
              "Unit-телеметрия" not in out, out[:300])

    # --- #6 cost-tracker: stable session id + rotation ---
    ct = load_module("cost-tracker.sh")
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ct.tempfile.gettempdir = lambda: str(tmpdir)  # sandbox the ledgers
        old_env = os.environ.pop("CLAUDE_SESSION_ID", None)
        try:
            sid1, sid2 = ct.session_id(), ct.session_id()
            check("#6 session id stable across spawns (no getppid)",
                  sid1 == sid2 and not sid1.startswith("pid"), f"{sid1} vs {sid2}")
            old = tmpdir / "claude-cost-old.json"
            old.write_text("{}", encoding="utf-8")
            stale = time.time() - (ct.ROTATE_AFTER_DAYS + 1) * 86400
            os.utime(old, (stale, stale))
            fresh = tmpdir / "claude-cost-fresh.json"
            fresh.write_text("{}", encoding="utf-8")
            ct.rotate_old_ledgers()
            check("#6 rotation deletes stale ledger, keeps fresh",
                  not old.exists() and fresh.exists())
            ct.rotate_old_ledgers()  # marker fresh -> no-op, must not raise
            check("#6 rotation is daily-throttled no-op on second call", True)
        finally:
            if old_env is not None:
                os.environ["CLAUDE_SESSION_ID"] = old_env

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
