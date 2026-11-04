#!/usr/bin/env python3
"""Report which Idea to Deploy hooks Codex will not run (plan session 5, BACKLOG P2 2026-10-22).

Codex keeps the user's trust decision per hook entry in config.toml under positional keys,
[hooks.state."<plugin>:hooks/hooks.json:<event>:<group>:<entry>"]. A plugin update that moves an entry leaves the
key of the old position behind, and Codex skips an entry without a trusted_hash as untrusted: on the owner's WSL the
whole pre_tool_use:4:* group (completion-gate, check-dod-before-commit, careful, ...) silently did not run. This
read-only report compares those keys with the installed hooks.json and names:

- untrusted: an entry with no trusted_hash - Codex does not run it until the user trusts it in /hooks;
- disabled: an entry switched off by `enabled = false` - a positional switch that lands on another hook after the
  next layout change; since plan session 5 ~/.claude/itd-disabled-hooks.txt is the switch on both agents;
- stale: a key of this plugin that no entry has any more.

A recorded trusted_hash may still be for an older definition at that position, and Codex 0.166+ also binds the
trust to a fingerprint of the whole plugin contents (trusted_content_hash): after every plugin update all entries are
"modified" and Codex skips them silently (CODEX-HOOKS-0166-1). config.toml cannot show that, so the report asks
Codex itself - `codex app-server`, request hooks/list - and names every entry whose trustStatus is not "trusted".
Without a Codex executable the content trust is reported as unverified, never as OK.

Writes nothing. Exit 0 - every entry trusted (Codex says so) and enabled; 1 - findings or unverified content trust;
2 - usage or unreadable input (no config.toml, a hooks.state of another shape, no installed hooks.json under a
semantic-version directory, a Codex app-server that fails or answers out of shape).

Usage: python3 scripts/itd_codex_hook_trust.py [--codex-home DIR] [--plugin idea-to-deploy@personal]
                                               [--hooks-json PATH] [--codex PATH] [--cwd DIR]
                                               [--timeout SECONDS]
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

EVENTS = {"UserPromptSubmit": "user_prompt_submit", "PreToolUse": "pre_tool_use", "PostToolUse": "post_tool_use",
          "Stop": "stop", "SubagentStop": "subagent_stop"}


# semver.org 2.0.0: no leading zeroes in numeric identifiers, no empty identifiers
NUMERIC = r"0|[1-9]\d*"
IDENT = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
VERSION_RE = re.compile(rf"({NUMERIC})\.({NUMERIC})\.({NUMERIC})(?:-({IDENT}(?:\.{IDENT})*))?"
                        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")


def version_key(name: str) -> tuple | None:
    """Semantic-version precedence: a release after its prereleases, numeric identifiers below alphanumeric ones."""
    match = VERSION_RE.fullmatch(name)
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    if pre is None:
        return int(major), int(minor), int(patch), 1, ()
    ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))
    return int(major), int(minor), int(patch), 0, ids


def installed_hooks_json(codex_home: Path, plugin: str) -> Path:
    name, _, marketplace = plugin.partition("@")
    base = codex_home / "plugins" / "cache" / marketplace / name
    versions = [(version_key(p.name), p) for p in base.glob("*") if (p / "hooks" / "hooks.json").is_file()]
    versions = sorted((pair for pair in versions if pair[0] is not None), key=lambda pair: pair[0])
    if not versions:
        raise FileNotFoundError(f"no installed hooks.json under a semantic-version directory of {base}")
    return versions[-1][1] / "hooks" / "hooks.json"


def entries(hooks_json: Path) -> dict[str, str]:
    """Position key -> 'script (matcher)' for every entry of the plugin's hooks.json."""
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    found = {}
    for event, groups in data["hooks"].items():
        for g, group in enumerate(groups):
            for h, hook in enumerate(group.get("hooks", [])):
                script = re.search(r"--script\s+(\S+)", hook.get("command", ""))
                label = script.group(1) if script else hook.get("command", "")
                found[f"{EVENTS.get(event, event)}:{g}:{h}"] = f"{label} ({group.get('matcher') or '*'})"
    return found


def hook_state(config: dict) -> dict:
    """The [hooks.state] table; a value of another shape is unreadable input, not an empty state."""
    hooks = config.get("hooks", {})
    state = hooks.get("state", {}) if isinstance(hooks, dict) else None
    if not isinstance(state, dict) or not all(isinstance(value, dict) for value in state.values()):
        raise ValueError("hooks.state in config.toml is not a table of tables")
    for key, record in state.items():
        trusted, enabled = record.get("trusted_hash"), record.get("enabled")
        if trusted is not None and not (isinstance(trusted, str) and trusted):
            raise ValueError(f"hooks.state.{key}.trusted_hash is not a non-empty string")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError(f"hooks.state.{key}.enabled is not a boolean")
    return state


def report(state: dict, plugin: str, layout: dict[str, str]) -> list[str]:
    prefix = f"{plugin}:hooks/hooks.json:"
    ours = {key[len(prefix):]: value for key, value in state.items() if key.startswith(prefix)}
    lines = []
    for position, label in layout.items():
        record = ours.get(position) or {}
        if not record.get("trusted_hash"):
            lines.append(f"untrusted {position} {label}")
        if record.get("enabled") is False:
            lines.append(f"disabled {position} {label}")
    lines += [f"stale {position}" for position in ours if position not in layout]
    return lines


def codex_hook_list(codex: str, cwd: Path, timeout: float = 120.0) -> list[dict]:
    """Ask Codex's own app-server (stdio JSON-RPC) for hooks/list: the trustStatus Codex will act on.

    `timeout` bounds the whole exchange, not each read: notifications, malformed lines or answers to other ids never
    extend it."""
    proc = subprocess.Popen([codex, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in proc.stdout] + [lines.put(None)],
                     daemon=True).start()

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        proc.stdin.flush()

    deadline = time.monotonic() + timeout

    def answer(request_id: int) -> dict:
        while True:
            remaining = deadline - time.monotonic()
            try:
                if remaining <= 0:
                    raise queue.Empty
                line = lines.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"codex app-server gave no answer to request {request_id} in {timeout:.0f}s")
            if line is None:
                raise ValueError("codex app-server exited before answering")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("id") == request_id:
                if "error" in message:
                    raise ValueError(f"codex app-server error: {message['error']}")
                return message.get("result")

    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "itd-codex-hook-trust",
                                                                         "version": "1"}}})
        answer(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "hooks/list", "params": {"cwds": [str(cwd)]}})
        result = answer(2)
    finally:
        try:  # EOF first: a launcher (codex.cmd on Windows) may not pass the kill on to the app-server it started
            proc.stdin.close()
        except OSError:
            pass
        proc.kill()
        try:  # cleanup spends only what is left of the overall deadline and never replaces the original outcome
            proc.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, list) or not all(isinstance(entry, dict) for entry in data):
        raise ValueError("hooks/list result has no data list")
    hooks = [hook for entry in data for hook in entry.get("hooks") or []]
    if not all(isinstance(hook, dict) and isinstance(hook.get("key"), str) for hook in hooks):
        raise ValueError("hooks/list returned a hook without a key")
    return hooks


def content_report(hooks: list[dict], plugin: str, layout: dict[str, str]) -> list[str]:
    """Entries Codex itself will not run: every hooks/list entry of the plugin whose trustStatus is not trusted
    (modified = contents changed), including entries the local layout does not have and duplicate keys, plus layout
    positions Codex does not list."""
    prefix = f"{plugin}:hooks/hooks.json:"
    ours = [hook for hook in hooks if hook["key"].startswith(prefix)]
    if layout and not ours:
        return [f"unlisted: Codex lists no hook of {plugin} (plugin disabled or not installed for this Codex)"]
    lines = []
    for hook in ours:
        position = hook["key"][len(prefix):]
        if hook.get("trustStatus") != "trusted":
            label = layout.get(position, "(not in the installed hooks.json)")
            lines.append(f"{hook.get('trustStatus') or 'unknown'} {position} {label} (Codex trustStatus)")
    listed = {hook["key"][len(prefix):] for hook in ours}
    lines += [f"unlisted {position} {label}" for position, label in layout.items() if position not in listed]
    return lines


def positive_seconds(text: str) -> float:
    """A finite, positive number of seconds; inf, nan, zero and negatives are usage errors (exit 2)."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number of seconds: {text!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"must be a finite positive number of seconds: {text!r}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--codex-home", type=Path,
                        default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--plugin", default="idea-to-deploy@personal")
    parser.add_argument("--hooks-json", type=Path)
    parser.add_argument("--codex", help="Codex executable asked for hooks/list (default: codex on PATH)")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(),
                        help="project whose hooks Codex lists (hooks/list cwds; default: the current directory)")
    parser.add_argument("--timeout", type=positive_seconds, default=120.0,
                        help="seconds for the whole hooks/list exchange with the Codex app-server (default 120)")
    args = parser.parse_args()
    try:
        import tomllib
    except ImportError:
        print("Python 3.11+ is needed to read config.toml (tomllib)", file=sys.stderr)
        return 2
    try:
        hooks_json = args.hooks_json or installed_hooks_json(args.codex_home, args.plugin)
        layout = entries(hooks_json)
        config = tomllib.loads((args.codex_home / "config.toml").read_text(encoding="utf-8"))
        state = hook_state(config)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, tomllib.TOMLDecodeError) as exc:
        print(f"cannot read the Codex hook state: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    lines = report(state, args.plugin, layout)
    codex = args.codex or shutil.which("codex")
    if codex:
        try:
            lines += content_report(codex_hook_list(codex, args.cwd, args.timeout), args.plugin, layout)
        except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as exc:
            print(f"cannot read the Codex hook trust from {codex}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    else:
        lines.append("unverified content trust: no Codex executable to ask hooks/list (pass --codex PATH)")
    print(f"{hooks_json}: {len(layout)} entries")
    for line in lines:
        print(line)
    if lines:
        print("FIX: open /hooks in Codex and trust the untrusted entries; switch hooks off in "
              "~/.claude/itd-disabled-hooks.txt instead of /hooks, then re-enable the disabled positions")
        print("     after a plugin update Codex 0.166+ marks every entry modified: start `codex` (on Windows "
              "`codex --no-daemon` - an older shared app-server daemon ignores trusted_content_hash) and choose "
              "\"Trust all and continue\"")
    else:
        print("OK: every entry is trusted (Codex hooks/list) and enabled")
    return 1 if lines else 0


if __name__ == "__main__":
    raise SystemExit(main())
