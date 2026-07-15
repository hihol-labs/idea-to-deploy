#!/usr/bin/env python3
"""Codex transport adapter for the shared Idea to Deploy hooks.

Codex and Claude share the lifecycle payload and decision protocol. The one
material mutation difference is Codex's ``apply_patch`` tool: its input is a
patch string rather than a single ``file_path``. This dispatcher expands the
patch into synthetic Write events, invokes the unchanged shared hook once per
affected path, and merges the results without weakening a deny decision.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:(?:Add|Update|Delete) File:|Move to:) (.+?)\s*$", re.MULTILINE
)
DEFAULT_SHARED_HOOK_TIMEOUT_SECONDS = 3
# The strict completion gate may synchronously rerun the project's approved
# verification contract (bounded internally at 720 seconds).  Keep the Codex
# transport deadline below the 900-second host registration while leaving
# 120 seconds for bounded root/scope/baseline work and process overhead.
SCRIPT_TIMEOUT_SECONDS = {
    "completion-gate.sh": 840,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    return parser.parse_args()


def shared_hook_timeout(script_name: str) -> int:
    return SCRIPT_TIMEOUT_SECONDS.get(script_name, DEFAULT_SHARED_HOOK_TIMEOUT_SECONDS)


def configure_utf8_stdio() -> None:
    """Keep Codex hook transport Unicode-safe on Windows hosts.

    Python otherwise decodes redirected stdin with the active Windows code
    page.  Codex emits UTF-8 JSON, so non-ASCII workspace paths can make the
    dispatcher silently fail open before a shared hook sees the payload.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def plugin_root() -> Path:
    configured = os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    return Path(configured).resolve() if configured else Path(__file__).resolve().parent.parent


def hard_gate_policy(root: Path, script_name: str) -> tuple[dict[str, Any] | None, bool]:
    """Return a canonical hard-gate entry and whether the policy was readable.

    An unreadable policy is not equivalent to a soft/unregistered hook.  The
    caller must fail closed because it cannot safely downgrade the selected
    command while the trust registry is unavailable.
    """
    policy_paths = [
        root / "docs" / "HARNESS_TRUST_POLICY.json",
        Path(__file__).resolve().parent.parent / "docs" / "HARNESS_TRUST_POLICY.json",
    ]
    saw_valid = False
    for policy_path in dict.fromkeys(policy_paths):
        try:
            payload = json.loads(policy_path.read_text(encoding="utf-8"))
            gates = payload["hardGates"]
            if not isinstance(gates, list):
                continue
            saw_valid = True
            for gate in gates:
                if isinstance(gate, dict) and gate.get("script") == script_name:
                    return gate, True
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return None, saw_valid


def transport_failure(root: Path, script_name: str, reason: str) -> int:
    """Preserve graduated trust when the adapter itself cannot run a hook."""
    gate, policy_ok = hard_gate_policy(root, script_name)
    if gate is None and policy_ok:
        return 0
    event = str((gate or {}).get("event") or "PreToolUse")
    message = f"ITD high-risk hook transport failed closed: {script_name}: {reason}"
    if event == "SubagentStop":
        output = {"decision": "block", "reason": message}
    else:
        output = {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }
    print(json.dumps(output, ensure_ascii=False))
    return 2


def affected_paths(command: str) -> list[str]:
    return list(dict.fromkeys(path.strip() for path in PATCH_PATH_RE.findall(command)))


def normalized_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("tool_name") != "apply_patch":
        return [payload]
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or "")
    paths = affected_paths(command)
    if not paths:
        clone = dict(payload)
        clone["tool_name"] = "Write"
        clone["tool_input"] = {"file_path": "", "content": command}
        return [clone]
    result = []
    for path in paths:
        clone = dict(payload)
        clone["tool_name"] = "Write"
        clone["tool_input"] = {
            "file_path": path,
            "content": command,
            "command": command,
        }
        result.append(clone)
    return result


def command_for(script: Path) -> list[str]:
    first_line = script.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    if "python" in first_line:
        return [sys.executable, str(script)]
    bash = shutil.which("bash")
    if bash:
        return [bash, str(script)]
    return [str(script)]


def merge_json(outputs: list[dict[str, Any]], event: str) -> dict[str, Any] | None:
    if not outputs:
        return None
    for item in outputs:
        specific = item.get("hookSpecificOutput") or {}
        if specific.get("permissionDecision") == "deny" or item.get("decision") == "block":
            return item

    contexts: list[str] = []
    messages: list[str] = []
    should_continue = True
    stop_reasons: list[str] = []
    for item in outputs:
        specific = item.get("hookSpecificOutput") or {}
        context = specific.get("additionalContext")
        if context:
            contexts.append(str(context))
        if item.get("systemMessage"):
            messages.append(str(item["systemMessage"]))
        if item.get("continue") is False:
            should_continue = False
        if item.get("stopReason"):
            stop_reasons.append(str(item["stopReason"]))

    merged: dict[str, Any] = {}
    if contexts:
        merged["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": "\n".join(dict.fromkeys(contexts)),
        }
    if messages:
        merged["systemMessage"] = "\n".join(dict.fromkeys(messages))
    if not should_continue:
        merged["continue"] = False
    if stop_reasons:
        merged["stopReason"] = "\n".join(dict.fromkeys(stop_reasons))
    return merged or None


def main() -> int:
    configure_utf8_stdio()
    args = parse_args()
    root = plugin_root()
    try:
        payload = json.load(sys.stdin) or {}
    except Exception:
        return transport_failure(root, args.script, "invalid hook payload")

    script = (root / "hooks" / args.script).resolve()
    hooks_root = (root / "hooks").resolve()
    if hooks_root not in script.parents:
        print(f"Invalid shared hook path: {args.script}", file=sys.stderr)
        return 2
    if not script.is_file():
        return transport_failure(root, args.script, "shared hook file is missing")

    env = os.environ.copy()
    env["ITD_HOST"] = "codex"
    env["PYTHONUTF8"] = "1"
    env.setdefault("PLUGIN_ROOT", str(root))
    env.setdefault("CLAUDE_PLUGIN_ROOT", str(root))
    if payload.get("session_id"):
        env["CLAUDE_SESSION_ID"] = str(payload["session_id"])

    json_outputs: list[dict[str, Any]] = []
    stderr_parts: list[str] = []
    worst_code = 0
    deadline = time.monotonic() + shared_hook_timeout(args.script)
    for normalized in normalized_payloads(payload):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return transport_failure(root, args.script, "shared hook deadline exhausted")
        try:
            proc = subprocess.run(
                command_for(script),
                input=json.dumps(normalized, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                cwd=str(Path(payload.get("cwd") or os.getcwd())),
                env=env,
                timeout=remaining,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return transport_failure(root, args.script, type(exc).__name__)
        if proc.returncode not in (0, 2):
            return transport_failure(root, args.script, f"shared hook exited {proc.returncode}")
        worst_code = 2 if proc.returncode == 2 else max(worst_code, proc.returncode)
        if proc.stderr.strip():
            stderr_parts.append(proc.stderr.strip())
        if proc.stdout.strip():
            try:
                parsed = json.loads(proc.stdout)
                if isinstance(parsed, dict):
                    json_outputs.append(parsed)
            except json.JSONDecodeError:
                # Plain text is valid context on some lifecycle events.
                json_outputs.append({"systemMessage": proc.stdout.strip()})
        if proc.returncode == 2:
            break

    merged = merge_json(json_outputs, str(payload.get("hook_event_name") or "PreToolUse"))
    if merged:
        print(json.dumps(merged, ensure_ascii=False))
    if stderr_parts:
        print("\n".join(dict.fromkeys(stderr_parts)), file=sys.stderr)
    return worst_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        configure_utf8_stdio()
        root = plugin_root()
        script_name = "unknown"
        try:
            script_name = parse_args().script
        except SystemExit:
            pass
        raise SystemExit(transport_failure(root, script_name, type(exc).__name__))
