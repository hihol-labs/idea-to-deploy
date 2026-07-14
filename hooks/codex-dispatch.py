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
from typing import Any


PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:Add|Update|Delete|Move to) File: (.+?)\s*$", re.MULTILINE
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    return parser.parse_args()


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
    try:
        payload = json.load(sys.stdin) or {}
    except Exception:
        return 0

    root = plugin_root()
    script = (root / "hooks" / args.script).resolve()
    hooks_root = (root / "hooks").resolve()
    if hooks_root not in script.parents or not script.is_file():
        print(f"Invalid shared hook path: {args.script}", file=sys.stderr)
        return 2

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
    for normalized in normalized_payloads(payload):
        proc = subprocess.run(
            command_for(script),
            input=json.dumps(normalized, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=str(Path(payload.get("cwd") or os.getcwd())),
            env=env,
            timeout=30,
        )
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
    except subprocess.TimeoutExpired:
        # Shared hooks are fail-open on infrastructure failure.
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
