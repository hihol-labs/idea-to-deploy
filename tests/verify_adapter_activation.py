#!/usr/bin/env python3
"""INSTALLED-PROOF-DISPATCH-1: the installed-proof oracle judges the Claude adapter by the layout of plan sessions 5-6.

tests/verify_route_debts.py validate_claude_activation() accepts a Claude home only when it equals what sync of the
release writes for the owner hook lists: the routing table row for row (script, matcher, timeout, hard-gate flag) and,
per routed event, exactly the one dispatcher group sync writes and nothing else (reviews a1-a4: matching pairs, a
matching command or text scanning of extra commands are not enough); the owner's hooks belong to other events. The fixtures build a home the way
scripts/sync-to-active.sh does: its DESIRED_HOOKS, filtered by hook_selected(), routed by itd_dispatch.routing().
Stdlib-only, cross-platform.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
WIN_PY = "C:/Users/u/AppData/Local/Programs/Python/Python312/python.exe"
RESULTS: list[bool] = []
NOT_EXACT = "are not exactly the one dispatcher group"


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


route = module("activation_route_debts", ROOT / "tests/verify_route_debts.py")
dispatch = module("activation_itd_dispatch", ROOT / "hooks/itd_dispatch.py")
selection = module("activation_codex_dispatch", ROOT / "hooks/codex-dispatch.py")
POLICY = json.loads((ROOT / "docs/HARNESS_TRUST_POLICY.json").read_text(encoding="utf-8"))
HARD = {(gate["script"], gate["event"]) for gate in POLICY["hardGates"] if "script" in gate}
DESIRED = json.loads(re.search(r"DESIRED_HOOKS=\$\(cat <<'JSON'\n(.+?)\nJSON\n\)",
                               (ROOT / "scripts/sync-to-active.sh").read_text(encoding="utf-8"), re.DOTALL).group(1))


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" - {detail}" if detail and not ok else ""))


def install(home: Path, disabled=(), enabled=(), windows: bool = False) -> Path:
    """A Claude home as sync-to-active.sh writes it for the given owner lists."""
    claude = home / ".claude"
    hooks = claude / "hooks"
    hooks.mkdir(parents=True)
    for name, values in ((selection.DISABLED_HOOKS_FILE, disabled), (selection.ENABLED_HOOKS_FILE, enabled)):
        if values:
            (claude / name).write_text("".join(value + "\n" for value in values), encoding="utf-8")
    desired = copy.deepcopy(DESIRED)
    for event in list(desired):
        kept = []
        for group in desired[event]:
            group["hooks"] = [hook for hook in group["hooks"] if selection.hook_selected(
                re.search(r"hooks/([^/\s\"]+)$", hook["command"]).group(1), set(disabled), set(enabled))]
            if group["hooks"]:
                kept.append(group)
        desired[event] = kept
    table, registration = dispatch.routing(desired, HARD)
    (hooks / dispatch.TABLE_FILE).write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    command = (f'"{WIN_PY}" -X utf8 "{(hooks / "claude-dispatch.py").as_posix()}"' if windows
               else dispatch.DISPATCHER_COMMAND)
    for groups in registration.values():
        for group in groups:
            for hook in group["hooks"]:
                hook["command"] = command
    (claude / "settings.json").write_text(json.dumps({"hooks": registration}, indent=2) + "\n", encoding="utf-8")
    scripts = {entry["script"] for entries in table["hooks"].values() for entry in entries}
    for script in scripts | {"claude-dispatch.py", "itd_dispatch.py"}:
        shutil.copyfile(ROOT / "hooks" / script, hooks / script)
    return claude


def verdict(home: Path, windows: bool = False) -> str:
    try:
        route.validate_claude_activation(home, WIN_PY, windows)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return f"refused: {exc}"
    return "accepted"


def table_pairs(claude: Path) -> set:
    table = json.loads((claude / "hooks" / dispatch.TABLE_FILE).read_text(encoding="utf-8"))
    return {(entry["script"], event) for event, entries in table["hooks"].items() for entry in entries}


def edit_settings(claude: Path, change) -> None:
    path = claude / "settings.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def edit_table(claude: Path, change) -> None:
    path = claude / "hooks" / dispatch.TABLE_FILE
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value["hooks"])
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def row(hooks: dict, event: str, script: str) -> dict:
    return next(entry for entry in hooks[event] if entry["script"] == script)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-adapter-activation-") as tmp:
        base = Path(tmp)
        risk = ("risk-score.sh", "PostToolUse")

        claude = install(base / "default")
        check("default lists: accepted, risk-score.sh (optional) not routed",
              verdict(base / "default") == "accepted" and risk not in table_pairs(claude), verdict(base / "default"))
        install(base / "owner-off", disabled=("risk-score.sh", "careful.sh"))
        check("owner disables risk-score.sh and careful.sh: accepted", verdict(base / "owner-off") == "accepted",
              verdict(base / "owner-off"))
        claude = install(base / "risk-on", enabled=("risk-score.sh",))
        check("enabled list names risk-score.sh: accepted and routed",
              verdict(base / "risk-on") == "accepted" and risk in table_pairs(claude), verdict(base / "risk-on"))

        claude = install(base / "stale-on")
        (claude / selection.ENABLED_HOOKS_FILE).write_text("risk-score.sh\n", encoding="utf-8")
        result = verdict(base / "stale-on")
        check("selected risk-score.sh missing from the table: refused", "missing risk-score.sh@PostToolUse" in result,
              result)
        claude = install(base / "stale-off")
        (claude / selection.DISABLED_HOOKS_FILE).write_text("careful.sh\n", encoding="utf-8")
        result = verdict(base / "stale-off")
        check("a disabled hook still routed: refused", "not selected careful.sh@PreToolUse" in result, result)

        claude = install(base / "legacy", enabled=("risk-score.sh",))
        edit_settings(claude, lambda value: value.update(hooks={"PostToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": "~/.claude/hooks/risk-score.sh", "timeout": 5}]}]}))
        result = verdict(base / "legacy")
        check("pre-session-6 direct risk-score.sh registration: refused", "dispatcher is not registered" in result,
              result)
        claude = install(base / "no-table")
        (claude / "hooks" / dispatch.TABLE_FILE).unlink()
        check("no routing table: refused", "routing table is not installed" in verdict(base / "no-table"))
        claude = install(base / "bad-table")
        table_path = claude / "hooks" / dispatch.TABLE_FILE
        table = json.loads(table_path.read_text(encoding="utf-8"))
        table_path.write_text(json.dumps(dict(table, kind="other"), indent=2) + "\n", encoding="utf-8")
        result = verdict(base / "bad-table")
        check("the selected routes under another table kind: refused", "not a version 1" in result, result)

        install(base / "windows", windows=True)
        check("Windows wrapper form with the pinned interpreter: accepted",
              verdict(base / "windows", windows=True) == "accepted", verdict(base / "windows", windows=True))
        result = verdict(base / "windows", windows=False)
        check("Windows wrapper judged as a POSIX host: refused", "dispatcher is not registered" in result, result)

        claude = install(base / "all-off")
        edit_settings(claude, lambda value: value.update(disableAllHooks=True))
        check("disableAllHooks: refused", "disableAllHooks" in verdict(base / "all-off"))
        claude = install(base / "twice")
        edit_settings(claude, lambda value: value["hooks"]["PreToolUse"].append(
            copy.deepcopy(value["hooks"]["PreToolUse"][0])))
        result = verdict(base / "twice")
        check("dispatcher registered twice for an event: refused", NOT_EXACT in result, result)
        for name, change in (("matcher", lambda h: row(h, "PreToolUse", "pii-egress-guard.sh").update(matcher="None")),
                             ("timeout", lambda h: row(h, "UserPromptSubmit", "pre-flight-check.sh").update(timeout=1))):
            claude = install(base / f"table-{name}")
            edit_table(claude, change)
            result = verdict(base / f"table-{name}")
            check(f"a table row with another {name}: refused", "differs from the table sync writes" in result, result)
        for name, change in (("matcher", lambda g: g.update(matcher="None")),
                             ("timeout", lambda g: g["hooks"][0].update(timeout=1))):
            claude = install(base / f"group-{name}")
            edit_settings(claude, lambda value: change(value["hooks"]["PreToolUse"][0]))
            result = verdict(base / f"group-{name}")
            check(f"the dispatcher group with another {name}: refused", NOT_EXACT in result, result)
        claude = install(base / "stale-event")
        edit_settings(claude, lambda value: value["hooks"].update(Notification=[
            copy.deepcopy(value["hooks"]["Stop"][0])]))
        result = verdict(base / "stale-event")
        check("the dispatcher under an event that routes no hook: refused", "routes no hook" in result, result)
        # Reviews a2-a4: no spelling of an extra command matters - a routed event holds the dispatcher group only.
        for index, command in enumerate(("python3 ~/.claude/hooks/claude-dispatch.py", "~/.claude/hooks/careful.sh",
                                         "echo $(~/.claude/hooks/careful.sh)", "~/.claude/hooks/careful.sh>/tmp/out",
                                         "x=`~/.claude/hooks/freeze.sh`", "~/.claude/hooks/careful'.'sh",
                                         "~/.claude/hooks/careful\\.sh", "C:/Users/u/.claude/hooks/CLAUDE-DISPATCH.PY",
                                         "/usr/local/bin/my-careful.sh", "/usr/local/bin/my-hook")):
            claude = install(base / f"extra-{index}")
            edit_settings(claude, lambda value: value["hooks"]["PreToolUse"].append(
                {"matcher": "*", "hooks": [{"type": "command", "command": command}]}))
            result = verdict(base / f"extra-{index}")
            check(f"another command in a routed event ({command}): refused", NOT_EXACT in result, result)
        claude = install(base / "own-hooks")
        edit_settings(claude, lambda value: value["hooks"].update(SessionStart=[{"hooks": [
            {"type": "command", "command": "/usr/local/bin/my-hook"},
            {"type": "command", "command": "~/.claude/hooks/careful'.'sh"}]}]))
        check("the owner's own hooks in an event that routes no ITD hook: accepted",
              verdict(base / "own-hooks") == "accepted", verdict(base / "own-hooks"))
        claude = install(base / "missing")
        (claude / "hooks" / "pre-flight-check.sh").unlink()
        result = verdict(base / "missing")
        check("a routed hook file is absent: refused", "pre-flight-check.sh is not installed" in result, result)
        for script in ("pii-egress-guard.sh", "claude-dispatch.py", "itd_dispatch.py"):
            claude = install(base / f"edited-{script}")
            with (claude / "hooks" / script).open("a", encoding="utf-8") as handle:
                handle.write("\n# edited\n")
            result = verdict(base / f"edited-{script}")
            check(f"{script} with other bytes: refused", f"{script} is not installed" in result, result)
        if os.name != "nt":
            claude = install(base / "linked")
            table = claude / "hooks" / dispatch.TABLE_FILE
            moved = base / "elsewhere.json"
            table.rename(moved)
            table.symlink_to(moved)
            check("a symlinked routing table: refused", "routing table is not installed" in verdict(base / "linked"))
            for script in ("pii-egress-guard.sh", "claude-dispatch.py", "itd_dispatch.py"):
                claude = install(base / f"linked-{script}")
                target, moved = claude / "hooks" / script, base / f"elsewhere-{script}"
                target.rename(moved)
                target.symlink_to(moved)
                result = verdict(base / f"linked-{script}")
                check(f"{script} as a symlink to the release bytes: refused", f"{script} is not installed" in result,
                      result)

    source = (ROOT / "tests/verify_route_debts.py").read_text(encoding="utf-8")
    body = source[source.index("def validate_adapter_activation("):]
    body = body[:body.index("\ndef ", 1)]
    check("validate_adapter_activation delegates to validate_claude_activation on the real home",
          'validate_claude_activation(Path.home(), Path(sys.executable).as_posix(), os.name == "nt")' in body
          and "risk-score.sh" not in body)
    check("the regression runs in run-all and in the native canary suites",
          "verify_adapter_activation" in (ROOT / "tests/run-all.sh").read_text(encoding="utf-8")
          and '"tests/verify_adapter_activation.py"' in source)
    failed = RESULTS.count(False)
    print(f"\n{len(RESULTS) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
