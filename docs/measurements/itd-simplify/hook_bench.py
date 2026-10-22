#!/usr/bin/env python3
"""Hook-chain latency bench for the ITD simplification baseline (plan session 2, ADR-016).

Replays what Claude Code does around one tool call: every hook command whose matcher matches the tool runs in
parallel for PreToolUse, then again for PostToolUse, each with the JSON payload on stdin. Sources, in the host's
order: the user settings.json, the project's .claude/settings.json and settings.local.json, and the hooks.json of
every enabled plugin at its installPath from plugins/installed_plugins.json (else the highest cached version in
numeric order), ${CLAUDE_PLUGIN_ROOT} substituted. Commands run through bash (/bin/bash on Linux, Git Bash
on Windows; the shell the Windows host itself uses is not checked).

Per tool (Bash, Edit, Read) it does one unmeasured warm-up call and RUNS measured calls and prints one JSON line:
the number of hook processes the host starts (Pre + Post commands), the median/min/max wall time of the Pre
phase, the Post phase and the whole chain, the median duration of each command and the count of nonzero exits per
command (warm-up included). Exit status 1 when any hook exited nonzero: its timing is then not a measurement.

The payloads are inert: Bash `git status --short`, Read and Edit of README.md (no tool runs, nothing is edited).
With --transcript the payload names a real session transcript (hooks only read it).
Hooks still write their own telemetry (signals, cost and trace logs) into the project and the user home, tagged
with session_id "itd-baseline-bench".

Usage (run natively on each host, the project as cwd):
  python3 hook_bench.py --home ~/.claude --project ~/projects/idea-to-deploy [--runs 10] [--bash /bin/bash]
  python.exe hook_bench.py --home C:/Users/<user>/.claude --project C:/Users/<user>/AI/buying
                           --bash "C:/Program Files/Git/bin/bash.exe"
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import re
import statistics
import subprocess
import time
from pathlib import Path

TOOLS = ("Bash", "Edit", "Read")
SESSION = "itd-baseline-bench"


def matches(matcher: str | None, tool: str) -> bool:
    if matcher in (None, "", "*"):
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return matcher == tool


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def hook_sources(home: Path, project: Path) -> list[tuple[str, dict, dict]]:
    """(label, hooks mapping, extra env) for every source the host merges."""
    user = load_json(home / "settings.json")
    sources = [("user", user.get("hooks", {}), {})]
    for name in ("settings.json", "settings.local.json"):
        data = load_json(project / ".claude" / name)
        if data.get("hooks"):
            sources.append((f"project/{name}", data["hooks"], {}))
    for plugin, enabled in user.get("enabledPlugins", {}).items():
        if not enabled:
            continue
        root = plugin_root(home, plugin)
        if root is not None and (root / "hooks" / "hooks.json").is_file():
            sources.append((f"plugin/{plugin}", load_json(root / "hooks" / "hooks.json").get("hooks", {}),
                            {"CLAUDE_PLUGIN_ROOT": str(root)}))
    return sources


def version_key(directory: Path) -> tuple:
    """Numeric order of a version directory name (1.10.0 after 1.9.0); non-numeric parts sort first."""
    return tuple((1, int(part)) if part.isdigit() else (0, part) for part in directory.name.replace("-", ".").split("."))


def plugin_root(home: Path, plugin: str) -> Path | None:
    """The install the host uses: installPath from installed_plugins.json, else the highest cached version."""
    installed = load_json(home / "plugins" / "installed_plugins.json")
    records = (installed.get("plugins", installed) if isinstance(installed, dict) else {}).get(plugin)
    if isinstance(records, list):
        for record in records:
            path = record.get("installPath") if isinstance(record, dict) else None
            if isinstance(path, str) and Path(path).is_dir():
                return Path(path)
    name, _, market = plugin.partition("@")
    versions = sorted((p for p in (home / "plugins" / "cache" / market / name).glob("*") if p.is_dir()), key=version_key)
    return versions[-1] if versions else None


def commands(sources, event: str, tool: str) -> list[tuple[str, str, dict]]:
    found = []
    for label, hooks, env in sources:
        for group in hooks.get(event, []):
            if not matches(group.get("matcher"), tool):
                continue
            for hook in group.get("hooks", []):
                if hook.get("type", "command") != "command":
                    continue
                command = hook["command"]
                for key, value in env.items():
                    command = command.replace("${" + key + "}", value.replace("\\", "/"))
                found.append((label, command, env))
    return found


def payload(event: str, tool: str, project: Path, transcript: str) -> dict:
    readme = str(project / "README.md")
    tool_input = {"Bash": {"command": "git status --short", "description": "bench"},
                  "Read": {"file_path": readme},
                  "Edit": {"file_path": readme, "old_string": "a", "new_string": "a"}}[tool]
    data = {"session_id": SESSION, "transcript_path": transcript, "cwd": str(project), "permission_mode": "bypassPermissions",
            "hook_event_name": event, "tool_name": tool, "tool_input": tool_input}
    if event == "PostToolUse":
        data["tool_response"] = {"Bash": {"stdout": "", "stderr": "", "interrupted": False},
                                 "Read": {"type": "text", "file": {"filePath": readme, "content": ""}},
                                 "Edit": {"filePath": readme, "success": True}}[tool]
    return data


def run_one(bash: str, command: str, env: dict, stdin: str, project: Path) -> tuple[float, int]:
    start = time.perf_counter()
    done = subprocess.run([bash, "-c", command], input=stdin.encode("utf-8"), stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, cwd=str(project), env=env, timeout=120)
    return time.perf_counter() - start, done.returncode


def phase(bash: str, cmds, event: str, tool: str, project: Path, base_env: dict,
          transcript: str) -> tuple[float, list[float], list[int]]:
    stdin = json.dumps(payload(event, tool, project, transcript))
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(cmds))) as pool:
        futures = [pool.submit(run_one, bash, command, {**base_env, **env}, stdin, project)
                   for _, command, env in cmds]
        results = [f.result() for f in futures]
    return time.perf_counter() - start, [r[0] for r in results], [r[1] for r in results]


SCRIPT_SUFFIXES = (".sh", ".py", ".mjs", ".js", ".cjs", ".ps1", ".cmd", ".bat")


def command_label(command: str) -> str:
    """The hook script a command runs (its last token naming a script file), else the command text itself."""
    for token in reversed(command.split()):
        name = token.strip("\"'").replace("\\", "/").rsplit("/", 1)[-1]
        if name.lower().endswith(SCRIPT_SUFFIXES):
            return name
    return " ".join(command.split())[:80]


def command_labels(rows: list[tuple[str, str, str]]) -> list[str]:
    """`<event>:<source>:<script>` per command, made unique (`#2`, `#3`) so no timing overwrites another."""
    seen: collections.Counter = collections.Counter()
    labels = []
    for event, source, command in rows:
        base = f"{event}:{source}:{command_label(command)}"
        seen[base] += 1
        labels.append(base if seen[base] == 1 else f"{base}#{seen[base]}")
    return labels


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def ms(values: list[float]) -> dict:
    return {"median": round(statistics.median(values) * 1000), "min": round(min(values) * 1000),
            "max": round(max(values) * 1000)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", type=Path, required=True)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--runs", type=positive, default=10)
    ap.add_argument("--bash", default="/bin/bash")
    ap.add_argument("--transcript", default="", help="a real session transcript the hooks may read (read-only)")
    args = ap.parse_args()
    home, project = args.home.expanduser(), args.project.expanduser()
    base_env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    sources = hook_sources(home, project)
    print(json.dumps({"home": str(home), "project": str(project), "runs": args.runs, "transcript": args.transcript,
                      "sources": [label for label, _, _ in sources]}, ensure_ascii=False))
    failed = False
    for tool in TOOLS:
        pre, post = commands(sources, "PreToolUse", tool), commands(sources, "PostToolUse", tool)
        names = command_labels([(event, label, command)
                                for event, group in (("Pre", pre), ("Post", post)) for label, command, _ in group])
        nonzero: collections.Counter = collections.Counter()
        _, _, ca = phase(args.bash, pre, "PreToolUse", tool, project, base_env, args.transcript)  # warm-up
        _, _, cb = phase(args.bash, post, "PostToolUse", tool, project, base_env, args.transcript)
        nonzero.update(n for n, code in zip(names, ca + cb) if code != 0)
        pre_wall, post_wall, chain, per_command = [], [], [], [[] for _ in pre + post]
        for _ in range(args.runs):
            a, da, ca = phase(args.bash, pre, "PreToolUse", tool, project, base_env, args.transcript)
            b, db, cb = phase(args.bash, post, "PostToolUse", tool, project, base_env, args.transcript)
            pre_wall.append(a), post_wall.append(b), chain.append(a + b)
            for slot, value in zip(per_command, da + db):
                slot.append(value)
            nonzero.update(n for n, code in zip(names, ca + cb) if code != 0)
        failed = failed or bool(nonzero)
        print(json.dumps({"tool": tool, "processes": {"pre": len(pre), "post": len(post), "total": len(pre) + len(post)},
                          "preWallMs": ms(pre_wall), "postWallMs": ms(post_wall), "chainWallMs": ms(chain),
                          "perCommandMedianMs": {n: round(statistics.median(v) * 1000) for n, v in zip(names, per_command)},
                          "nonzeroExits": dict(nonzero)}, ensure_ascii=False))
    # A hook that exits nonzero on an inert payload (missing interpreter, crash, deny) makes its timing meaningless.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
