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

A recorded trusted_hash may still be for an older definition at that position; Codex /hooks shows that case.
Writes nothing. Exit 0 - every entry trusted and enabled; 1 - findings; 2 - usage or unreadable input (no
config.toml, a hooks.state of another shape, no installed hooks.json under a semantic-version directory).

Usage: python3 scripts/itd_codex_hook_trust.py [--codex-home DIR] [--plugin idea-to-deploy@personal]
                                               [--hooks-json PATH]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--codex-home", type=Path,
                        default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--plugin", default="idea-to-deploy@personal")
    parser.add_argument("--hooks-json", type=Path)
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
    print(f"{hooks_json}: {len(layout)} entries")
    for line in lines:
        print(line)
    if lines:
        print("FIX: open /hooks in Codex and trust the untrusted entries; switch hooks off in "
              "~/.claude/itd-disabled-hooks.txt instead of /hooks, then re-enable the disabled positions")
    else:
        print("OK: every entry is trusted and enabled")
    return 1 if lines else 0


if __name__ == "__main__":
    raise SystemExit(main())
