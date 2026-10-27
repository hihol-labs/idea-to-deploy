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


def load_main():
    """itd_dispatch.main, its code from the install-time bytecode only when the inventory records it (review a9).

    trust_bytecode() in itd_dispatch guards every load after it, but not the load of its own module: here the .pyc of
    itd_dispatch is used only when its SHA-256 is the bytecodeSha256 of itd-bytecode.json and its checked-hash header
    names this source; anything else compiles the source in memory, as itd_dispatch.cached_code() does for a hook.
    """
    import hashlib
    import importlib.util
    import json
    import marshal
    import types

    hooks = os.path.dirname(os.path.realpath(__file__))
    root = os.path.dirname(hooks)
    source_path = os.path.join(hooks, "itd_dispatch.py")
    with open(source_path, "rb") as handle:
        source = handle.read()
    code = None
    try:
        pyc = importlib.util.cache_from_source(source_path)
        with open(pyc, "rb") as handle:
            data = handle.read()
        with open(os.path.join(root, "itd-bytecode.json"), encoding="utf-8") as handle:
            inventory = json.load(handle)
        key = lambda path: os.path.normcase(os.path.realpath(path))  # noqa: E731
        recorded = {key(os.path.join(root, row["bytecode"])): row["bytecodeSha256"] for row in inventory["files"]} \
            if inventory.get("kind") == "itd-hook-bytecode-v1" else {}
        if (recorded.get(key(pyc)) == hashlib.sha256(data).hexdigest() and data[:4] == importlib.util.MAGIC_NUMBER
                and int.from_bytes(data[4:8], "little") == 0b11 and data[8:16] == importlib.util.source_hash(source)):
            code = marshal.loads(data[16:])
    except Exception:  # noqa: BLE001 - no bytecode the install vouches for: the source below
        code = None
    module = types.ModuleType("itd_dispatch")
    module.__file__ = source_path
    sys.modules["itd_dispatch"] = module
    exec(code if isinstance(code, types.CodeType) else compile(source, source_path, "exec", dont_inherit=True),
         module.__dict__)
    return module.main


if __name__ == "__main__":
    try:
        main = load_main()
    except BaseException as exc:  # noqa: BLE001 - SystemExit at import too: an unloadable dispatcher must not let a
        os._exit(fail_closed(f"itd_dispatch is not loadable: {type(exc).__name__}: {exc}"))  # hard gate fail open
    try:
        main()  # answers and leaves through os._exit; it fails closed on its own errors (review a7)
    except BaseException as exc:  # noqa: BLE001 - a main() that raises anyway must not exit 1, a non-blocking error
        os._exit(fail_closed(f"itd_dispatch.main raised: {type(exc).__name__}: {exc}"))
