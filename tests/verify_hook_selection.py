#!/usr/bin/env python3
"""Acceptance of plan session 5 (ADR-016): one default hook registration, the same selection on both agents.

- a fresh sync into an empty HOME registers the core hooks and the hooks that stay silent without .itd-memory, and
  none of the optional ones (diagnostics, crash-recovery) and none of the three unregistered skill-decision hooks;
- a repeated sync is idempotent (byte-identical settings.json, "already up-to-date");
- a user's own hook in the same event, matcher and group survives the sync, foreign event keys too;
- itd-enabled-hooks.txt registers an optional hook under every event of its registration and removing it
  unregisters it; itd-disabled-hooks.txt drops even a core hook;
- codex-dispatch.py runs exactly the hooks the sync registers, from the same two lists: a disabled or a not enabled
  optional hook is not executed (its process never starts), an enabled one is;
- the Claude project template equals the sync registration and the Codex project template equals the plugin
  hooks.json, so /adopt installs the same set (and nothing registered user-level, see verify_hooks_autoinstall.py);
- check-dod-before-commit.sh has a host budget above its dispatcher deadline and its project-check bound on every
  registration (a 5 s budget cut it on slow Windows commits, BACKLOG P2 2026-10-22);
- the merge refuses what it cannot own safely: a non-object settings.json, a Windows python-wrapper registration
  under a non-Windows target (exit 1, file untouched); a registration of a RETIRED hook file goes away, and every hook
  ITD has shipped is a hook file or RETIRED.

Every run is confined to temporary homes (CLAUDE_HOME / HOME); the user's real lists never decide a check.
On Windows the sync runs in Git Bash (ITD_BASH, default bash) and registers python.exe wrappers; the checks compare
script names, so the same test is the Windows acceptance.
Usage: python3 tests/verify_hook_selection.py
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sync-to-active.sh"
DISPATCHER = ROOT / "hooks" / "codex-dispatch.py"
CORE = {"pre-flight-check.sh", "pii-egress-guard.sh", "careful.sh", "check-predeploy-gate.sh",
        "completion-signals.sh", "completion-gate.sh"}
STATE = {"state-guard.sh", "wip-gate.sh", "freeze.sh", "handoff-readiness.sh"}
UNREGISTERED = {"check-skills.sh", "check-tool-skill.sh", "check-review-before-commit.sh"}
# The acceptance sets, pinned here independently of the production code (plan session 5).
DEFAULT_SET = CORE | STATE | {"check-commit-completeness.sh", "check-dod-before-commit.sh", "check-skill-completeness.sh",
                              "cross-review-precommit.sh", "graph-route.sh", "model-policy.sh", "narration-final.sh",
                              "record-agent-skill.sh", "verdict-contract.sh"}
OPTIONAL = {"completion-stop.sh", "context-aware.sh", "context-budget.sh", "cost-tracker.sh", "crash-recovery.sh",
            "execution-trace.sh", "risk-score.sh", "session-open-diagnostic.sh", "stuck-detection.sh"}

spec = importlib.util.spec_from_file_location("itd_codex_dispatch", DISPATCHER)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)

passed = failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS {label}")
    else:
        failed += 1
        print(f"FAIL {label}" + (f": {detail}" if detail else ""))


USER_HOOKS = {"audit.sh", "my-own.sh", "wrap.sh"}


# Every hook file ITD shipped by plan session 5; a file deleted from hooks/ must move to RETIRED in the sync merge,
# or its old registrations would stay behind as a user's hooks.
SHIPPED = {"careful.sh", "check-commit-completeness.sh", "check-dod-before-commit.sh", "check-predeploy-gate.sh",
           "check-review-before-commit.sh", "check-skill-completeness.sh", "check-skills.sh", "check-tool-skill.sh",
           "completion-gate.sh", "completion-signals.sh", "completion-stop.sh", "context-aware.sh",
           "context-budget.sh", "cost-tracker.sh", "crash-recovery.sh", "cross-review-precommit.sh",
           "execution-trace.sh", "freeze.sh", "graph-route.sh", "handoff-readiness.sh", "model-policy.sh",
           "narration-final.sh", "pii-egress-guard.sh", "pre-flight-check.sh", "record-agent-skill.sh",
           "risk-score.sh", "session-open-diagnostic.sh", "state-guard.sh", "stuck-detection.sh",
           "verdict-contract.sh", "wip-gate.sh"}


def sync_raw(home: Path, script: Path = SYNC) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_HOME": home.as_posix()}
    return subprocess.run([os.environ.get("ITD_BASH", "bash"), script.as_posix()], cwd=script.parents[1], env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)


def sync(home: Path) -> str:
    proc = sync_raw(home)
    if proc.returncode:
        raise AssertionError(f"sync exited {proc.returncode}: {proc.stderr[-400:]}")
    return proc.stdout + proc.stderr


def rows(home: Path) -> list[tuple[str, str, str]]:
    data = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    return [(event, group.get("matcher", ""), hook["command"])
            for event, groups in data.get("hooks", {}).items() for group in groups for hook in group["hooks"]]


def hook_file(command: str) -> str:
    """The hook file a command runs: its last .sh token (a bare path or a python.exe wrapper on Windows)."""
    found = re.findall(r"([A-Za-z0-9._-]+\.sh)(?=$|[\"'\s])", command.replace("\\", "/"))
    return found[-1] if found else ""


def names(found: list[tuple[str, str, str]]) -> set[str]:
    """ITD hooks among the rows (the fixture's own user hooks left out)."""
    return {hook_file(command) for _, _, command in found} - USER_HOOKS - {""}


def desired() -> dict:
    text = SYNC.read_text(encoding="utf-8")
    return json.loads(re.search(r"DESIRED_HOOKS=\$\(cat <<'JSON'\n(.+?)\nJSON\n\)", text, re.DOTALL).group(1))


def registered_names(hooks: dict, pattern: str) -> set[str]:
    return {name for groups in hooks.values() for group in groups for hook in group["hooks"]
            for name in re.findall(pattern, hook["command"])}


def dispatch_runs(script: str, lists: Path, plugin: Path, marker: Path) -> tuple[int, bool]:
    env = {**os.environ, "CLAUDE_HOME": str(lists), "PLUGIN_ROOT": str(plugin), "PYTHONUTF8": "1"}
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "true"},
               "cwd": str(plugin)}
    marker.unlink(missing_ok=True)
    proc = subprocess.run([sys.executable, str(DISPATCHER), "--script", script], input=json.dumps(payload),
                          text=True, capture_output=True, env=env, timeout=30)
    return proc.returncode, marker.exists()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-hook-selection-") as raw:
        tmp = Path(raw)

        # 1. fresh install into an empty HOME
        home = tmp / "fresh"
        home.mkdir()
        out = sync(home)
        got = names(rows(home))
        check("fresh install registers every core hook", CORE <= got, f"missing={sorted(CORE - got)}")
        check("fresh install registers the state hooks", STATE <= got, f"missing={sorted(STATE - got)}")
        check("fresh install registers exactly the 19 default hooks", got == DEFAULT_SET,
              f"diff={sorted(got ^ DEFAULT_SET)}")
        check("the dispatcher's optional set is the accepted one", dispatch.OPTIONAL_HOOKS == OPTIONAL,
              f"diff={sorted(dispatch.OPTIONAL_HOOKS ^ OPTIONAL)}")
        check("fresh install registers no optional hook", not got & OPTIONAL, f"optional={sorted(got & OPTIONAL)}")
        check("fresh install registers none of the three skill-decision hooks", not got & UNREGISTERED,
              f"registered={sorted(got & UNREGISTERED)}")
        check("the sync names the optional hooks it left off",
              f"optional hooks off by default: {len(dispatch.OPTIONAL_HOOKS)}" in out, out[-300:])
        default_set = got

        # 2. idempotent re-run
        before = (home / "settings.json").read_bytes()
        again = sync(home)
        check("a repeated sync keeps settings.json byte-identical", (home / "settings.json").read_bytes() == before)
        check("a repeated sync reports the hooks up to date", "settings.json hooks already up-to-date" in again)

        # 3. a user's own hooks survive, in the same group and in foreign keys
        data = json.loads(before)
        bash_group = next(g for g in data["hooks"]["PreToolUse"] if g.get("matcher") == "Bash")
        bash_group["hooks"].append({"type": "command", "command": "/opt/me/audit.sh", "timeout": 3})
        mention = "~/.claude/hooks/careful.sh --version; /opt/me/wrap.sh"  # mentions an ITD hook path; the user's
        bash_group["hooks"].append({"type": "command", "command": mention})
        data["hooks"]["PreToolUse"].append(
            {"matcher": "Read", "hooks": [{"type": "command", "command": "~/.claude/hooks/my-own.sh"}]})
        data["hooks"]["SessionStart"] = [{"hooks": [{"type": "command", "command": "other-plugin start"}]}]
        data["hooks"]["PreToolUse"][0]["hooks"].append({"type": "command", "command": "~/.claude/hooks/careful.sh"})
        (home / "settings.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if os.name != "nt":
            (home / "settings.json").chmod(0o640)
        sync(home)
        found = rows(home)
        check("a user hook in the ITD Bash group is kept",
              ("PreToolUse", "Bash", "/opt/me/audit.sh") in found)
        check("a user command that only mentions an ITD hook path is kept", ("PreToolUse", "Bash", mention) in found)
        check("the rewrite is atomic: no temporary file is left next to settings.json",
              not list(home.glob(".settings-*")))
        if os.name != "nt":
            check("the rewrite keeps the file mode", (home / "settings.json").stat().st_mode & 0o777 == 0o640,
                  oct((home / "settings.json").stat().st_mode & 0o777))
        check("a user hook in ~/.claude/hooks with its own name is kept",
              ("PreToolUse", "Read", "~/.claude/hooks/my-own.sh") in found)
        check("a foreign event key is kept", ("SessionStart", "", "other-plugin start") in found)
        careful = [row[:2] for row in found if hook_file(row[2]) == "careful.sh"]
        check("a stray ITD hook copy is replaced, not duplicated", careful == [("PreToolUse", "Bash")], str(careful))
        user_state = (home / "settings.json").read_bytes()
        sync(home)
        check("the merge with user hooks is idempotent", (home / "settings.json").read_bytes() == user_state)

        # 4. the two lists
        (home / "itd-enabled-hooks.txt").write_text("﻿cost-tracker.sh  # diagnostics\n", encoding="utf-8")
        (home / "itd-disabled-hooks.txt").write_text("careful.sh\n", encoding="utf-8")
        out = sync(home)
        found = rows(home)
        cost = sorted((event, matcher) for event, matcher, command in found if hook_file(command) == "cost-tracker.sh")
        check("an enabled optional hook is registered under every event of its registration",
              cost == [("PostToolUse", "*"), ("PreToolUse", "Bash|PowerShell|Task|Agent")], str(cost))
        check("a disabled core hook is not registered", "careful.sh" not in names(found))
        check("the sync counts both lists", "optional hooks enabled by itd-enabled-hooks.txt: 1" in out
              and "hooks disabled by itd-disabled-hooks.txt: 1" in out, out[-400:])
        (home / "itd-enabled-hooks.txt").unlink()
        (home / "itd-disabled-hooks.txt").unlink()
        sync(home)
        found = rows(home)
        check("removing the lists returns to the default set",
              names(found) == default_set and ("PreToolUse", "Bash", "/opt/me/audit.sh") in found,
              f"diff={sorted(names(found) ^ default_set)}")

        # 5. Codex: codex-dispatch.py runs exactly what the sync registers
        plugin = tmp / "plugin"
        (plugin / "hooks").mkdir(parents=True)
        marker = tmp / "ran.txt"
        for script in ("careful.sh", "cost-tracker.sh"):
            (plugin / "hooks" / script).write_text(
                "#!/usr/bin/env python3\nfrom pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('ran')\n", encoding="utf-8")
        lists = tmp / "lists"
        lists.mkdir()
        check("Codex runs a default hook", dispatch_runs("careful.sh", lists, plugin, marker) == (0, True))
        check("Codex does not run an optional hook by default",
              dispatch_runs("cost-tracker.sh", lists, plugin, marker) == (0, False))
        (lists / "itd-enabled-hooks.txt").write_text("cost-tracker.sh\n", encoding="utf-8")
        check("Codex runs an enabled optional hook", dispatch_runs("cost-tracker.sh", lists, plugin, marker) == (0, True))
        (lists / "itd-disabled-hooks.txt").write_text("careful.sh\ncost-tracker.sh\n", encoding="utf-8")
        check("Codex does not run a disabled hook", dispatch_runs("careful.sh", lists, plugin, marker) == (0, False))
        check("a disabled hook stays off when it is also enabled",
              dispatch_runs("cost-tracker.sh", lists, plugin, marker) == (0, False))
        (lists / "itd-disabled-hooks.txt").unlink()
        (lists / "itd-disabled-hooks.txt").mkdir()
        check("an unreadable disabled list switches no hook off",
              dispatch_runs("careful.sh", lists, plugin, marker) == (0, True))

        plugin_hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        codex_names = registered_names(plugin_hooks, r"--script ([a-z0-9-]+\.sh)")
        claude_names = registered_names(desired(), r"hooks/([a-z0-9-]+\.sh)$")
        host_only = {"record-agent-skill.sh"}  # Codex has no Task/Agent tool event for it
        check("Claude and Codex register the same hooks", claude_names - host_only == codex_names,
              f"diff={sorted((claude_names - host_only) ^ codex_names)}")
        for label, disabled, enabled in (("no lists", set(), set()),
                                         ("owner lists", dispatch.OPTIONAL_HOOKS | UNREGISTERED, set()),
                                         ("one enabled, one disabled", {"careful.sh"}, {"risk-score.sh"})):
            home = tmp / f"lists-{len(label)}"
            home.mkdir()
            if disabled:
                (home / "itd-disabled-hooks.txt").write_text("\n".join(sorted(disabled)) + "\n", encoding="utf-8")
            if enabled:
                (home / "itd-enabled-hooks.txt").write_text("\n".join(sorted(enabled)) + "\n", encoding="utf-8")
            sync(home)
            synced = names(rows(home)) - host_only
            selected = {name for name in codex_names if dispatch.hook_selected(name, disabled, enabled)}
            check(f"sync and codex-dispatch select the same hooks ({label})", synced == selected,
                  f"diff={sorted(synced ^ selected)}")

        # 6. the /adopt templates are the same registration
        template = json.loads((ROOT / "skills" / "adopt" / "references" / "project-settings-template.json")
                              .read_text(encoding="utf-8"))["hooks"]
        rendered = json.loads(json.dumps(template).replace("{{PLUGIN_HOOKS_DIR}}/", "~/.claude/hooks/"))
        check("the Claude project template equals the sync registration", rendered == desired())
        codex_template = json.loads((ROOT / "skills" / "adopt" / "references" / "codex-project-hooks.json")
                                    .read_text(encoding="utf-8"))["hooks"]
        check("the Codex project template registers the plugin's hooks",
              registered_names(codex_template, r"--script ([a-z0-9-]+\.sh)") == codex_names)
        check("every optional hook can be enabled on both agents",
              dispatch.OPTIONAL_HOOKS <= codex_names and dispatch.OPTIONAL_HOOKS <= claude_names)

        # 7. the DoD gate budget: host > dispatcher deadline > its own project-check bound
        bound = max(int(n) for n in re.findall(r"timeout=(\d+)", (ROOT / "hooks" / "check-dod-before-commit.sh")
                                                .read_text(encoding="utf-8")))
        deadline = dispatch.shared_hook_timeout("check-dod-before-commit.sh")
        budgets = [hook["timeout"] for hooks in (desired(), template, plugin_hooks, codex_template)
                   for groups in hooks.values() for group in groups for hook in group["hooks"]
                   if hook_file(hook["command"]) == "check-dod-before-commit.sh"]
        check("check-dod-before-commit has a budget above its checks on all four registrations",
              len(budgets) == 4 and min(budgets) > deadline > bound, f"budgets={budgets} deadline={deadline} "
              f"bound={bound}")

        # 8. what the merge must refuse or still own
        for label, text in (("a JSON array", "[]\n"), ("hooks as a list", '{"hooks": []}\n'),
                            ("an event as an object", '{"hooks": {"PreToolUse": {}}}\n'),
                            ("a foreign event as a string", '{"hooks": {"SessionStart": "x"}}\n')):
            home = tmp / f"shape-{len(label)}"
            home.mkdir()
            (home / "settings.json").write_text(text, encoding="utf-8")
            proc = sync_raw(home)
            check(f"a non-object settings.json is refused, exit 1, file untouched ({label})",
                  proc.returncode == 1 and "Traceback" not in proc.stderr
                  and (home / "settings.json").read_text(encoding="utf-8") == text, proc.stderr[-300:])
        if os.name != "nt":
            home = tmp / "wrapper"
            home.mkdir()
            wrapper = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command":
                       '"C:/Python312/python.exe" -X utf8 "C:/Users/u/.claude/hooks/careful.sh"'}]}]}}
            (home / "settings.json").write_text(json.dumps(wrapper) + "\n", encoding="utf-8")
            before = (home / "settings.json").read_bytes()
            proc = sync_raw(home)
            check("a Windows wrapper under a non-Windows target is refused with exit 1",
                  proc.returncode == 1 and "REFUSING" in proc.stderr
                  and (home / "settings.json").read_bytes() == before, proc.stderr[-300:])

        retired = re.search(r"^RETIRED = (.+)$", SYNC.read_text(encoding="utf-8"), re.M).group(1)
        retired_names = set(re.findall(r"[\"']([a-z0-9-]+\.sh)[\"']", retired))
        files = {path.name for path in (ROOT / "hooks").glob("*.sh")}
        check("every hook ITD shipped is a hook file or RETIRED", SHIPPED <= files | retired_names,
              f"missing={sorted(SHIPPED - files - retired_names)}")
        # a copy of the sync whose hooks/ lost a file: its registration stays a user's hook until it is RETIRED
        fake = tmp / "fake-repo"
        (fake / "scripts").mkdir(parents=True)
        (fake / "skills" / "x").mkdir(parents=True)
        (fake / "skills" / "x" / "SKILL.md").write_text("x\n", encoding="utf-8")
        (fake / ".claude-plugin").mkdir()
        (fake / ".claude-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
        shutil.copytree(ROOT / "hooks", fake / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
        (fake / "hooks" / "freeze.sh").unlink()
        text = SYNC.read_text(encoding="utf-8")
        for variant, sync_text in (("kept", text), ("retired", text.replace("RETIRED = set()",
                                                                             'RETIRED = {"freeze.sh"}', 1))):
            (fake / "scripts" / "sync-to-active.sh").write_text(sync_text, encoding="utf-8")
            home = tmp / f"retired-{variant}"
            home.mkdir()
            proc = sync_raw(home, fake / "scripts" / "sync-to-active.sh")
            data = json.loads((home / "settings.json").read_text(encoding="utf-8"))
            for groups in data["hooks"].values():
                for group in groups:
                    group["hooks"] = [h for h in group["hooks"] if not h["command"].endswith("/freeze.sh")]
            data["hooks"]["PreToolUse"].append(
                {"matcher": "Edit", "hooks": [{"type": "command", "command": "~/.claude/hooks/freeze.sh"}]})
            (home / "settings.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            proc = sync_raw(home, fake / "scripts" / "sync-to-active.sh")
            left = [row for row in rows(home) if hook_file(row[2]) == "freeze.sh" and row[1] == "Edit"]
            expected = 1 if variant == "kept" else 0
            check(f"a stale registration of a deleted hook file is {variant}",
                  proc.returncode == 0 and len(left) == expected, f"left={left} {proc.stderr[-200:]}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
