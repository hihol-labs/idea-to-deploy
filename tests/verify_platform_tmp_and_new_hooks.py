#!/usr/bin/env python3
"""v1.42.0 guards — platform-tmp symmetry + functional tests for the two hooks
that shipped without automated coverage (wip-gate.sh, handoff-readiness.sh).

  T1  Static regression guard for the "/tmp on Windows" bug class: no hook may
      build a sentinel/state path from a LITERAL "/tmp/..." f-string. Reading
      the literal "/tmp" as one of several candidate dirs (the dual pattern
      `for d in (tempfile.gettempdir(), "/tmp")`) is allowed; constructing
      paths only there is not. Catches exactly the class fixed in v1.42.0
      (review-gate/cost/risk/stuck/crash/context-aware dead on Windows).

  T2  wip-gate.sh: out-of-scope edit while currentUnit is `verifying` -> hint;
      in-scope edit -> silence; ITD_WIP_GATE=0 -> silence.

  T3  handoff-readiness.sh: dirty repo without fresh session memory -> hint;
      clean repo -> silence; ITD_HANDOFF_READINESS=0 -> silence.

Self-contained, cross-platform (uses sys.executable + tempfile). Run:
  python3 tests/verify_platform_tmp_and_new_hooks.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"

PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + ((" — " + detail) if detail else ""))


def run_hook(hook: str, payload: dict, cwd: Path, env_extra: dict | None = None) -> str:
    env = dict(os.environ)
    env.update(env_extra or {})
    # -X utf8 mirrors how the Windows install invokes hooks (python.exe -X utf8);
    # explicit encoding keeps the parent from decoding UTF-8 hint text as cp1251.
    res = subprocess.run(
        [sys.executable, "-X", "utf8", str(HOOKS / hook)],
        input=json.dumps(payload), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        cwd=str(cwd), env=env, timeout=30,
    )
    return res.stdout or ""


# --- T1: static guard --------------------------------------------------------
LITERAL_TMP_PATH = re.compile(r"""f?["']/tmp/claude-""")
offenders = []
for hook_file in sorted(HOOKS.glob("*.sh")):
    text = hook_file.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if LITERAL_TMP_PATH.search(line):
            offenders.append(f"{hook_file.name}:{i}")
check("T1: no hook builds paths from a literal '/tmp/claude-'",
      not offenders, "offenders: " + ", ".join(offenders))


# --- helpers for functional tests -------------------------------------------
def make_git_repo(base: Path, dirty: bool) -> Path:
    repo = base / f"repo-{uuid.uuid4().hex[:6]}"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True, capture_output=True)
    if dirty:
        (repo / "wip.txt").write_text("wip", encoding="utf-8")
    return repo


# --- T2: wip-gate ------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    proj = Path(td) / "proj"
    (proj / ".itd-memory").mkdir(parents=True)
    (proj / ".itd").mkdir()
    (proj / "src" / "auth").mkdir(parents=True)
    (proj / ".itd-memory" / "STATE.json").write_text(json.dumps(
        {"currentUnit": {"id": "U-1", "goal": "g", "status": "verifying"}}), encoding="utf-8")
    (proj / ".itd" / "SCOPE_LOCK.md").write_text(
        "# Scope Lock\n## Allowed Change Areas\n- src/auth\n", encoding="utf-8")

    sid = f"t{uuid.uuid4().hex[:8]}"

    out = run_hook("wip-gate.sh",
                   {"session_id": sid, "tool_name": "Edit",
                    "tool_input": {"file_path": str(proj / "README.md")}, "cwd": str(proj)}, proj)
    check("T2a: wip-gate hints on out-of-scope edit while verifying",
          "WIP" in out and "additionalContext" in out, "got: " + out[:120])

    out = run_hook("wip-gate.sh",
                   {"session_id": sid + "b", "tool_name": "Edit",
                    "tool_input": {"file_path": str(proj / "src" / "auth" / "x.py")}, "cwd": str(proj)}, proj)
    check("T2b: wip-gate silent on in-scope edit", out.strip() == "", "got: " + out[:120])

    out = run_hook("wip-gate.sh",
                   {"session_id": sid + "c", "tool_name": "Edit",
                    "tool_input": {"file_path": str(proj / "README.md")}, "cwd": str(proj)},
                   proj, {"ITD_WIP_GATE": "0"})
    check("T2c: wip-gate silent with kill-switch", out.strip() == "", "got: " + out[:120])


# --- T3: handoff-readiness ----------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    dirty_repo = make_git_repo(Path(td), dirty=True)
    out = run_hook("handoff-readiness.sh",
                   {"session_id": f"t{uuid.uuid4().hex[:8]}", "cwd": str(dirty_repo)}, dirty_repo)
    check("T3a: handoff-readiness hints on dirty repo",
          "systemMessage" in out and "HANDOFF" in out.upper(), "got: " + out[:120])

    clean_repo = make_git_repo(Path(td), dirty=False)
    out = run_hook("handoff-readiness.sh",
                   {"session_id": f"t{uuid.uuid4().hex[:8]}", "cwd": str(clean_repo)}, clean_repo)
    check("T3b: handoff-readiness silent on clean repo", out.strip() == "", "got: " + out[:120])

    out = run_hook("handoff-readiness.sh",
                   {"session_id": f"t{uuid.uuid4().hex[:8]}", "cwd": str(dirty_repo)},
                   dirty_repo, {"ITD_HANDOFF_READINESS": "0"})
    check("T3c: handoff-readiness silent with kill-switch", out.strip() == "", "got: " + out[:120])


print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
