#!/usr/bin/env python3
"""Functional tests for hooks/narration-final.sh (v1.49.0).

The hook is a SubagentStop detector: it must BLOCK (root {"decision":"block"})
when the subagent's final assistant message ends on process narration with no
verdict anywhere, and stay SILENT in every other case — a false block costs a
whole extra subagent turn, so the negative cases matter as much as the
positive ones. Regression pins from the backlog:
  * a verdict-final message is NEVER blocked;
  * the valid «Не успел проверить: …» tail is NOT narration;
  * stop_hook_active / kill-switch / missing transcript → silent;
  * ping cap: at most ITD_NARRATION_MAX_PINGS blocks per subagent transcript.

Both transcript layouts observed in the wild are covered:
  * agent-direct: transcript_path points at the subagent's own
    subagents/agent-*.jsonl (all entries isSidechain=true);
  * main-fallback: transcript_path points at the MAIN session file (no
    sidechain entries) and the hook must find the newest
    <session-stem>/subagents/agent-*.jsonl next to it.

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_narration_final.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "narration-final.sh"
PY = sys.executable

PASSED, FAILED = 0, 0
TMPDIRS: list[Path] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def assistant_entry(text: str, sidechain: bool = True) -> str:
    return json.dumps({
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"role": "assistant",
                    "content": [{"type": "text", "text": text}]},
    }, ensure_ascii=False)


def tool_use_entry() -> str:
    return json.dumps({
        "type": "assistant",
        "isSidechain": False,
        "message": {"role": "assistant",
                    "content": [{"type": "tool_use", "id": "t1",
                                 "name": "Read", "input": {}}]},
    })


def make_layout(final_text: str, layout: str) -> dict:
    """Create transcript files; return the hook payload."""
    d = Path(tempfile.mkdtemp(prefix="nf49-"))
    TMPDIRS.append(d)
    sid = "s-" + uuid.uuid4().hex[:8]
    agent_dir = d / sid / "subagents"
    agent_dir.mkdir(parents=True)
    agent = agent_dir / ("agent-" + uuid.uuid4().hex[:10] + ".jsonl")
    lines = [
        json.dumps({"type": "user", "isSidechain": True,
                    "message": {"role": "user", "content": "task"}}),
        assistant_entry("Intermediate progress message.", sidechain=True),
        assistant_entry(final_text, sidechain=True),
    ]
    agent.write_text("\n".join(lines) + "\n", encoding="utf-8")
    main = d / (sid + ".jsonl")
    main.write_text("\n".join([
        json.dumps({"type": "user", "isSidechain": False,
                    "message": {"role": "user", "content": "hi"}}),
        tool_use_entry(),
    ]) + "\n", encoding="utf-8")
    tp = agent if layout == "agent-direct" else main
    return {"session_id": sid, "transcript_path": str(tp),
            "stop_hook_active": False, "hook_event_name": "SubagentStop"}


def run_hook(payload, extra_env: dict | None = None,
             raw_stdin: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONUTF8": "1", **(extra_env or {})}
    env.pop("ITD_NARRATION_FINAL", None)
    if extra_env and "ITD_NARRATION_FINAL" in extra_env:
        env["ITD_NARRATION_FINAL"] = extra_env["ITD_NARRATION_FINAL"]
    data = raw_stdin if raw_stdin is not None else json.dumps(payload)
    return subprocess.run([PY, str(HOOK)], input=data, capture_output=True,
                          encoding="utf-8", errors="replace", env=env,
                          timeout=60)


def blocked(proc: subprocess.CompletedProcess) -> bool:
    if not proc.stdout.strip():
        return False
    try:
        out = json.loads(proc.stdout)
    except Exception:
        return False
    return out.get("decision") == "block" and bool(out.get("reason"))


NARR_EN = ("I compared the hook against the checklist and fixed two entries.\n\n"
           "Now check the remaining tests to be sure nothing else regressed.")
NARR_RU = ("Разобрал дифф по файлам, два замечания записал.\n\n"
           "Теперь проверю оставшиеся файлы.")
NARR_BOLD = ("Пробежал по первым трём хукам.\n\n"
             "**Далее** проверю регистрацию в settings.json.")
VERDICT_FINAL = ("## Review findings\n\n- Important: X\n- Minor: Y\n\n"
                 "Вердикт: PASSED_WITH_WARNINGS — 1 Important, 1 Minor.")
NARR_MID_VERDICT = ("Now check the edge cases — done, results below.\n\n"
                    "FINAL STATUS: PASSED (all 12 cases green).")
NE_USPEL_TAIL = ("Разобрал 3 из 5 файлов, замечаний нет.\n\n"
                 "Не успел проверить: hooks/careful.sh, tests/meta_review.py.")
LONG_CONTENT_PARA = ("Summary of the change.\n\nNow check " + "x" * 450)


def main() -> int:
    # --- positives: narration-final with no verdict → block -----------------
    p = run_hook(make_layout(NARR_EN, "agent-direct"))
    check("EN narration-final blocks (agent-direct layout)", blocked(p),
          p.stdout[:200] + p.stderr[:200])
    p = run_hook(make_layout(NARR_RU, "main-fallback"))
    check("RU narration-final blocks (main-transcript fallback layout)",
          blocked(p), p.stdout[:200] + p.stderr[:200])
    p = run_hook(make_layout(NARR_BOLD, "agent-direct"))
    check("markdown-bold narration opener still blocks", blocked(p),
          p.stdout[:200])

    # --- negatives: a verdict-final is NEVER blocked ------------------------
    p = run_hook(make_layout(VERDICT_FINAL, "agent-direct"))
    check("verdict-final stays silent", not blocked(p), p.stdout[:200])
    p = run_hook(make_layout(NARR_MID_VERDICT, "agent-direct"))
    check("narration opener mid-message + verdict final stays silent",
          not blocked(p), p.stdout[:200])
    p = run_hook(make_layout(NE_USPEL_TAIL, "agent-direct"))
    check("«Не успел проверить» tail (valid final) stays silent",
          not blocked(p), p.stdout[:200])
    p = run_hook(make_layout(LONG_CONTENT_PARA, "agent-direct"))
    check("long final paragraph (content, not announcement) stays silent",
          not blocked(p), p.stdout[:200])

    # --- guards --------------------------------------------------------------
    payload = make_layout(NARR_EN, "agent-direct")
    payload["stop_hook_active"] = True
    p = run_hook(payload)
    check("stop_hook_active=true stays silent (loop guard)", not blocked(p),
          p.stdout[:200])
    p = run_hook(make_layout(NARR_EN, "agent-direct"),
                 extra_env={"ITD_NARRATION_FINAL": "0"})
    check("kill switch ITD_NARRATION_FINAL=0 stays silent", not blocked(p),
          p.stdout[:200])
    p = run_hook({"session_id": "x", "stop_hook_active": False,
                  "transcript_path": str(Path(tempfile.gettempdir())
                                         / "nf49-no-such.jsonl")})
    check("missing transcript stays silent (fail-open)",
          not blocked(p) and p.returncode == 0, p.stdout[:200])
    p = run_hook(None, raw_stdin="not a json {")
    check("garbage stdin stays silent, exit 0 (fail-open)",
          not blocked(p) and p.returncode == 0,
          "rc=%s %s" % (p.returncode, p.stdout[:100]))

    # --- ping cap: same transcript blocks at most N times -------------------
    payload = make_layout(NARR_RU, "agent-direct")
    r1 = run_hook(payload)
    r2 = run_hook(payload)
    r3 = run_hook(payload)
    check("ping cap: 1st and 2nd stop blocked, 3rd passes through",
          blocked(r1) and blocked(r2) and not blocked(r3),
          "1=%s 2=%s 3=%s" % (blocked(r1), blocked(r2), blocked(r3)))
    payload = make_layout(NARR_RU, "agent-direct")
    p1 = run_hook(payload, extra_env={"ITD_NARRATION_MAX_PINGS": "1"})
    p2 = run_hook(payload, extra_env={"ITD_NARRATION_MAX_PINGS": "1"})
    check("ITD_NARRATION_MAX_PINGS=1 honored", blocked(p1) and not blocked(p2),
          "1=%s 2=%s" % (blocked(p1), blocked(p2)))

    # --- cleanup -------------------------------------------------------------
    for d in TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
