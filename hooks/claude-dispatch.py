#!/usr/bin/env python3
"""Claude Code hook entry point: the one ITD dispatcher of every hook event (plan session 6, ADR-016).

The logic lives in itd_dispatch.py next to this file, so it is imported from its install-time bytecode instead of
being compiled on every call. When that module cannot be loaded, this file fails closed on its own: a tool call is
denied and a SubagentStop blocked (the events that carry hard gates), any other event stays silent.
"""
import sys

sys.dont_write_bytecode = True  # before any import: nothing this process imports writes .pyc (1.109.1)


def fail_closed(reason: str) -> int:
    import json

    try:
        payload = json.loads(sys.stdin.buffer.read() or b"{}")
    except ValueError:
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
        print(message, file=sys.stderr)
        return 0
    print(json.dumps(answer, ensure_ascii=False))
    print(message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        from itd_dispatch import main  # the hooks directory is sys.path[0] of this script
    except Exception as exc:  # noqa: BLE001 - an unloadable dispatcher must not let a hard gate fail open
        sys.exit(fail_closed(f"itd_dispatch is not loadable: {type(exc).__name__}: {exc}"))
    sys.exit(main())
