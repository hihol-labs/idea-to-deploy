#!/usr/bin/env python3
"""Claude Code hook entry point: the one ITD dispatcher of every hook event (plan session 6, ADR-016).

The logic lives in itd_dispatch.py next to this file, so it is imported from its install-time bytecode instead of
being compiled on every call. When that module cannot be loaded, this file fails closed on its own: a tool call is
denied and a SubagentStop blocked (the events that carry hard gates), any other event stays silent.
"""
import os
import sys

sys.dont_write_bytecode = True  # before any import: nothing this process imports writes .pyc (1.109.1)


def fail_closed(reason: str) -> int:
    """The exit status of a dispatcher that cannot answer: 2 for a tool call (an event that cannot be told is one) and a
    SubagentStop that does not continue yet, 0 elsewhere. It holds when stdin or the output is unusable (review a8):
    the answer is written and flushed here, and the caller leaves through os._exit, so no late flush changes it."""
    code = 2
    try:
        import json

        try:
            payload = json.loads(sys.stdin.buffer.read() or b"{}")
        except Exception:  # noqa: BLE001 - not JSON, or stdin unusable: an event that cannot be told
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        event = payload.get("hook_event_name") or ("PreToolUse" if "tool_name" in payload else "")
        message = f"ITD high-risk hook transport failed closed: {reason}"
        if event == "SubagentStop" and payload.get("stop_hook_active") is not True:
            answer = {"decision": "block", "reason": message}
        elif event in ("", "PreToolUse"):
            answer = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": message}}
        else:
            code = 0
            print(message, file=sys.stderr, flush=True)
            return code
        print(json.dumps(answer, ensure_ascii=False), flush=True)
        print(message, file=sys.stderr, flush=True)
    except BaseException:  # noqa: BLE001 - stdin or the output unusable: the exit status still carries the decision
        pass
    return code


if __name__ == "__main__":
    try:
        from itd_dispatch import main  # the hooks directory is sys.path[0] of this script
    except BaseException as exc:  # noqa: BLE001 - SystemExit at import too: an unloadable dispatcher must not let a
        os._exit(fail_closed(f"itd_dispatch is not loadable: {type(exc).__name__}: {exc}"))  # hard gate fail open
    try:
        main()  # answers and leaves through os._exit; it fails closed on its own errors (review a7)
    except BaseException as exc:  # noqa: BLE001 - a main() that raises anyway must not exit 1, a non-blocking error
        os._exit(fail_closed(f"itd_dispatch.main raised: {type(exc).__name__}: {exc}"))
