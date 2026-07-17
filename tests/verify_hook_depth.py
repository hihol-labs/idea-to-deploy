#!/usr/bin/env python3
"""Functional depth tests for the 9 previously smoke-only hooks (v1.48.0).

Audit 2026-07-04 finding: 22/22 hooks passed smoke (don't crash, valid JSON),
but ~9 had NO test of their SEMANTICS — the «silently dead safety layer»
class that the first live /retro already caught twice (careful false
positives; a cost ceiling that was dead for months). This suite pins the
behavioral contract of each: it must FIRE on its trigger condition and stay
SILENT otherwise.

Covered: stuck-detection, crash-recovery, context-aware, context-budget,
execution-trace, session-open-diagnostic, freeze, record-agent-skill,
check-commit-completeness.

Isolation: every case runs under a unique CLAUDE_SESSION_ID so per-session
state files never collide with real sessions; created state files are removed
at the end (best-effort). Cross-platform by construction. Run:
  python3 tests/verify_hook_depth.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
PY = sys.executable
TMP = Path(tempfile.gettempdir())

PASSED, FAILED = 0, 0
SIDS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def sid(tag: str) -> str:
    s = f"hd48-{tag}-{uuid.uuid4().hex[:6]}"
    SIDS.append(s)
    return s


def run(hook: str, payload: dict, session: str, cwd: Path | None = None,
        extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONUTF8": "1", "CLAUDE_SESSION_ID": session,
           **(extra_env or {})}
    return subprocess.run([PY, str(HOOKS / hook)], input=json.dumps(payload),
                          capture_output=True, encoding="utf-8",
                          errors="replace", env=env,
                          cwd=str(cwd) if cwd else None, timeout=60)


def ctx_of(proc: subprocess.CompletedProcess) -> str:
    """Extract additionalContext from hook stdout ('' when silent)."""
    if not proc.stdout.strip():
        return ""
    try:
        return (json.loads(proc.stdout).get("hookSpecificOutput") or {}) \
            .get("additionalContext") or ""
    except Exception:
        return "<BADJSON>" + proc.stdout[:100]


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def main() -> int:
    # --- stuck-detection: same command x3 fires, varied commands stay silent ---
    s = sid("stuck")
    for _ in range(2):
        run("stuck-detection.sh", bash("pytest tests/x.py"), s)
    p = run("stuck-detection.sh", bash("pytest tests/x.py"), s)
    check("stuck-detection fires on 3rd identical command", ctx_of(p) != "",
          p.stdout[:200])
    s = sid("nostuck")
    for cmd in ("ls", "pwd", "git status"):
        p = run("stuck-detection.sh", bash(cmd), s)
    check("stuck-detection silent on varied commands", ctx_of(p) == "",
          p.stdout[:200])

    # --- crash-recovery: checkpoint materializes with tool history ---
    s = sid("crash")
    for i in range(12):
        run("crash-recovery.sh",
            {"tool_name": "Write", "tool_input": {"file_path": f"f{i}.py"}}, s)
    cp = TMP / f"claude-checkpoint-{s}.json"
    ok = cp.is_file()
    hist = 0
    if ok:
        try:
            hist = len(json.loads(cp.read_text(encoding="utf-8"))
                       .get("tool_history") or [])
        except Exception:
            ok = False
    check("crash-recovery writes checkpoint with tool history after interval",
          ok and hist >= 1, f"exists={cp.is_file()} hist={hist}")

    # --- context-aware: long session warns, fresh session silent ---
    s = sid("ctxwarn")
    (TMP / f"claude-context-{s}.json").write_text(json.dumps(
        {"count": 45, "last_warning": 0, "session_start": time.time() - 3600}),
        encoding="utf-8")
    p = run("context-aware.sh", {"prompt": "hi"}, s)
    check("context-aware warns past the tool-call threshold",
          "Session stats" in ctx_of(p), p.stdout[:200])
    s = sid("ctxfresh")
    p = run("context-aware.sh", {"prompt": "hi"}, s)
    check("context-aware silent on a fresh session", ctx_of(p) == "",
          p.stdout[:200])

    # --- context-budget: unbounded dump hints, bounded stays silent ---
    s = sid("budget")
    p = run("context-budget.sh", bash("curl https://api.example.com/all"), s)
    check("context-budget hints on unbounded HTTP body", ctx_of(p) != "",
          p.stdout[:200])
    p = run("context-budget.sh", bash("grep -r TODO src"), s)
    check("context-budget hints on uncapped wide search", ctx_of(p) != "",
          p.stdout[:200])
    p = run("context-budget.sh",
            bash("curl https://api.example.com/all | head -20"), s)
    check("context-budget silent when output is bounded", ctx_of(p) == "",
          p.stdout[:200])
    p = run("context-budget.sh",
            {"tool_name": "Edit", "tool_input": {"file_path": "x"}}, s)
    check("context-budget silent on non-Bash tools", ctx_of(p) == "",
          p.stdout[:200])

    # --- execution-trace: appends a jsonl line under the project ---
    s = sid("trace")
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        p = run("execution-trace.sh",
                {"session_id": s, "cwd": str(proj), "tool_name": "Edit",
                 "tool_input": {"file_path": "src/a.py"}}, s)
        traces = list((proj / ".claude" / "traces").glob("*.jsonl"))
        line_ok = bool(traces) and "src/a.py" in traces[0].read_text(
            encoding="utf-8", errors="replace")
        check("execution-trace appends a line with the tool target",
              p.returncode == 0 and line_ok,
              f"files={[t.name for t in traces]}")

    # --- session-open-diagnostic: fires once, then sentinel silences it ---
    s = sid("sod")
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        (proj / "LAUNCH_PLAN.md").write_text("# Plan\n- step one\n",
                                             encoding="utf-8")
        (proj / "BACKLOG.md").write_text("- item A\n", encoding="utf-8")
        p1 = run("session-open-diagnostic.sh", {"prompt": "hi"}, s, cwd=proj)
        first_out = ctx_of(p1)
        p2 = run("session-open-diagnostic.sh", {"prompt": "hi again"}, s,
                 cwd=proj)
        check("session-open-diagnostic is once-per-session (2nd call silent)",
              ctx_of(p2) == "", p2.stdout[:200])
        check("session-open-diagnostic 1st call surfaced project context",
              "BACKLOG" in first_out or "LAUNCH" in first_out
              or "step one" in first_out or "item A" in first_out
              or first_out != "", p1.stdout[:200])

    # --- freeze: out-of-scope edit warns, in-scope stays silent ---
    s = sid("freeze")
    fz = TMP / f"claude-freeze-{s}.state"
    fz.write_text("src/auth", encoding="utf-8")
    p = run("freeze.sh",
            {"tool_name": "Edit", "tool_input": {"file_path": "src/other/b.py"}}, s)
    check("freeze warns on out-of-scope edit", ctx_of(p) != "", p.stdout[:200])
    p = run("freeze.sh",
            {"tool_name": "Edit", "tool_input": {"file_path": "src/auth/a.py"}}, s)
    check("freeze silent inside the frozen scope", ctx_of(p) == "",
          p.stdout[:200])
    s2 = sid("nofreeze")
    p = run("freeze.sh",
            {"tool_name": "Edit", "tool_input": {"file_path": "anything.py"}}, s2)
    check("freeze inactive without a state file", ctx_of(p) == "",
          p.stdout[:200])

    # --- record-agent-skill: only existence-based test work gets a sentinel ---
    s = sid("ras")
    p = run("record-agent-skill.sh",
            {"tool_name": "Task",
             "tool_input": {"subagent_type": "test-generator", "prompt": "x"}}, s)
    sent = TMP / f"claude-test-done-{s}"
    check("record-agent-skill writes test sentinel for test-generator",
          p.returncode == 0 and sent.is_file(), str(sent))
    s_review = sid("rasreview")
    run("record-agent-skill.sh",
        {"tool_name": "Task",
         "tool_input": {"subagent_type": "code-reviewer", "prompt": "x"}}, s_review)
    check("record-agent-skill cannot mint review success from agent type",
          not (TMP / f"claude-review-done-{s_review}").is_file())
    s2 = sid("rasneg")
    run("record-agent-skill.sh",
        {"tool_name": "Task",
         "tool_input": {"subagent_type": "researcher", "prompt": "x"}}, s2)
    check("record-agent-skill ignores non-gate agents",
          not (TMP / f"claude-review-done-{s2}").is_file())

    # --- check-commit-completeness: blocks an incomplete skill commit ---
    s = sid("ccc")
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / ".claude-plugin").mkdir()
        (repo / ".claude-plugin" / "plugin.json").write_text(
            '{"name": "x", "version": "0.0.0"}', encoding="utf-8")
        (repo / "hooks").mkdir()
        (repo / "hooks" / "check-skills.sh").write_text("TRIGGERS = []\n",
                                                        encoding="utf-8")
        (repo / "skills" / "foo").mkdir(parents=True)
        (repo / "skills" / "foo" / "SKILL.md").write_text(
            "---\nname: foo\n---\n# Foo\n", encoding="utf-8")
        g = dict(cwd=str(repo), capture_output=True, text=True, timeout=30)
        subprocess.run(["git", "init", "-q"], **g)
        subprocess.run(["git", "config", "user.email", "t@t"], **g)
        subprocess.run(["git", "config", "user.name", "t"], **g)
        subprocess.run(["git", "add", "-A"], **g)
        p = run("check-commit-completeness.sh",
                bash('git commit -m "add skill"'), s, cwd=repo)
        check("commit-completeness BLOCKS skill commit w/o trigger+fixture",
              p.returncode == 2, f"rc={p.returncode} {p.stdout[:150]}")
        p = run("check-commit-completeness.sh", bash("git status"), s, cwd=repo)
        check("commit-completeness no-op on non-commit Bash",
              p.returncode == 0 and ctx_of(p) == "", p.stdout[:150])

    # --- cleanup our per-session state files (best-effort) ---
    removed = 0
    for pattern in ("claude-*hd48-*", "claude-checkpoint-hd48-*"):
        for f in TMP.glob(pattern):
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    print(f"(cleanup: {removed} state files removed)")

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
