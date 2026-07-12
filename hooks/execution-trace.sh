#!/usr/bin/env python3
"""
Pre/PostToolUse hook — live execution tracer (v1.21; v1.89.0 two-phase).

Closes the live-execution-trace gap noted in docs/DESIGN_SPACE.md (K15) and
docs/HARNESS_ENGINEERING_MAP.md (H5). Appends JSON lines to
`.claude/traces/session-<id>.jsonl` in the current project, giving a live,
replayable record of the session — for debugging the methodology and oversight.

Two phases (v1.89.0, GO-001 — «информативность шага: исход в трейсе»):
  - PreToolUse  → intent line   {phase:"pre",  tool, target}
  - PostToolUse → outcome line  {phase:"post", tool, target, outcome, exit,
                                 error?}  — outcome извлекается для ЛЮБОГО tool
                                 (Bash/PowerShell exit-код; Edit/Write success;
                                 Agent пустой финал; Skill/прочее).
Раньше писался только интент (0/N событий несли исход — «трейс из намерений,
не результатов»). Теперь каждый шаг имеет парную outcome-строку.

Opt-in: active only when registered in settings.json (matcher "*"). Never
blocks (exit 0, no verdict), injects NOTHING into context, best-effort writes.
`.claude/` is gitignored — traces never pollute the repo.

Reads JSON on stdin (Pre): {"session_id","cwd","tool_name","tool_input"}
                     (Post): + {"tool_response": {...}|"...", "hook_event_name"}
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Per-tool: the input field that best identifies the target of the call.
TARGET_FIELDS = ("file_path", "command", "path", "pattern", "url", "notebook_path", "prompt")
MAX_TARGET = 300


def summarize_target(tool_input: dict) -> str:
    if not isinstance(tool_input, dict):
        return ""
    for field in TARGET_FIELDS:
        val = tool_input.get(field)
        if isinstance(val, str) and val:
            return val[:MAX_TARGET] + ("…" if len(val) > MAX_TARGET else "")
    return ""


# Detect an event as PostToolUse from either the explicit event name or the
# presence of a tool_response (harness variants differ).
def is_post(payload: dict) -> bool:
    ev = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
    if ev:
        return ev == "PostToolUse"
    return "tool_response" in payload or "tool_result" in payload


def extract_outcome(tool: str, resp) -> dict:
    """(outcome, exit?, error?) для любого tool. outcome: ok|fail|empty|unknown.

    - int exit-код (Bash/PowerShell) решает first: 0->ok иначе fail.
    - dict с is_error/error -> fail; Agent с пустым финалом -> empty.
    - строка непустая -> ok; None/пусто -> unknown.
    """
    out = {"outcome": "unknown"}
    if resp is None:
        return out
    text = ""
    if isinstance(resp, str):
        text = resp
    elif isinstance(resp, dict):
        for k in ("exitCode", "exit_code", "returncode", "code"):
            v = resp.get(k)
            if isinstance(v, int):
                out["exit"] = v
                out["outcome"] = "ok" if v == 0 else "fail"
                if v != 0:
                    out["error"] = _first_err(resp)
                return out
        if resp.get("is_error") or resp.get("error"):
            out["outcome"] = "fail"
            out["error"] = _first_err(resp)
            return out
        if resp.get("interrupted"):
            out["outcome"] = "fail"
            out["error"] = "interrupted"
            return out
        for k in ("stdout", "output", "content", "result", "response", "text"):
            v = resp.get(k)
            if isinstance(v, str):
                text = v
                break
    # Agent: пустой финал — известный дефект «субагент вернул пусто» (сет-4).
    if tool in ("Agent", "Task") and not text.strip():
        out["outcome"] = "empty"
        return out
    out["outcome"] = "ok" if text.strip() else "unknown"
    return out


def _first_err(resp: dict) -> str:
    for k in ("stderr", "error", "stdout", "content", "result"):
        v = resp.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().splitlines()[-1][:200]
    return ""


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0  # bad/empty payload — stay silent, never break the session

    try:
        post = is_post(payload) if isinstance(payload, dict) else False
        tool = payload.get("tool_name", "") if isinstance(payload, dict) else ""
        if not tool:
            raise ValueError
        session_id = str(payload.get("session_id") or "unknown")
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64] or "unknown"
        cwd = payload.get("cwd") or "."
        trace_dir = Path(cwd) / ".claude" / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "phase": "post" if post else "pre",
            "tool": tool,
            "target": summarize_target(payload.get("tool_input") or {}),
        }
        if post:
            resp = payload.get("tool_response")
            if resp is None:
                resp = payload.get("tool_result")
            entry.update(extract_outcome(tool, resp))
        with (trace_dir / f"session-{safe_id}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return 0  # telemetry failure must never break the session

    ev = "PostToolUse" if post else "PreToolUse"
    out = {"hookSpecificOutput": {"hookEventName": ev}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
