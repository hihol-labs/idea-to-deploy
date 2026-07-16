#!/usr/bin/env python3
"""Static and behavioral parity checks for Claude and Codex adapters."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    claude = load_json(ROOT / ".claude-plugin" / "plugin.json")
    codex = load_json(ROOT / ".codex-plugin" / "plugin.json")
    registry = load_json(ROOT / "docs" / "host-adapters.json")
    hook_config = load_json(ROOT / "hooks" / "hooks.json")
    trust_policy = load_json(ROOT / registry["methodologyCore"]["trustPolicy"])

    check(claude["name"] == codex["name"] == "idea-to-deploy", "plugin names diverge", errors)
    check(claude["version"] == codex["version"], "plugin versions diverge", errors)
    check(codex.get("skills") == "./skills/", "Codex skills path is not canonical", errors)
    check("agents" not in codex, "Codex manifest contains unsupported agents field", errors)
    check("hooks" not in codex, "Codex manifest should use default hooks/hooks.json discovery", errors)

    for host in ("claude", "codex"):
        config = registry["hosts"][host]
        check((ROOT / config["pluginManifest"]).is_file(), f"{host} manifest missing", errors)
        check(config["guidanceFile"] in ("CLAUDE.md", "AGENTS.md"), f"{host} guidance mapping invalid", errors)

    events = hook_config.get("hooks", {})
    for event in ("UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SubagentStop"):
        check(event in events and events[event], f"Codex event {event} is not registered", errors)

    referenced_scripts: set[str] = set()
    for groups in events.values():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                windows_command = hook.get("commandWindows", "")
                check("codex-dispatch.py" in command, f"hook bypasses Codex dispatcher: {command}", errors)
                check(bool(windows_command), f"hook lacks Windows command: {command}", errors)
                check(
                    "$env:PLUGIN_ROOT" in windows_command and "%PLUGIN_ROOT%" not in windows_command,
                    f"hook Windows command does not use PowerShell environment syntax: {windows_command}",
                    errors,
                )
                marker = "--script "
                if marker in command:
                    script = command.split(marker, 1)[1].split()[0].strip('"')
                    referenced_scripts.add(script)
                    check((ROOT / "hooks" / script).is_file(), f"missing shared hook {script}", errors)

    hard_gates = {gate["script"] for gate in trust_policy["hardGates"]}
    check(hard_gates <= referenced_scripts, f"hard Codex gates missing: {sorted(hard_gates - referenced_scripts)}", errors)
    mutation_hard_gates = {"check-tool-skill.sh", "check-skill-completeness.sh", "state-guard.sh"}
    apply_patch_scripts: set[str] = set()
    for group in events.get("PreToolUse", []):
        if "apply_patch" not in str(group.get("matcher", "")):
            continue
        for hook in group.get("hooks", []):
            command = hook.get("command", "")
            if "--script " in command:
                apply_patch_scripts.add(command.split("--script ", 1)[1].split()[0].strip('"'))
    check(
        mutation_hard_gates <= apply_patch_scripts,
        f"Codex apply_patch matcher misses mutation gates: {sorted(mutation_hard_gates - apply_patch_scripts)}",
        errors,
    )

    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    check("[CLAUDE.md](CLAUDE.md)" not in agents_text, "AGENTS.md still points to missing CLAUDE.md", errors)
    check((ROOT / "skills/adopt/references/codex-adoption.md").is_file(), "Codex adoption branch missing", errors)
    check((ROOT / "skills/adopt/references/agents-md-template.md").is_file(), "Codex AGENTS template missing", errors)

    explicit_skills = []
    for skill_md in (ROOT / "skills").glob("*/SKILL.md"):
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        if "explicit_invocation: true" not in text:
            continue
        explicit_skills.append(skill_md.parent.name)
        policy_path = skill_md.parent / "agents" / "openai.yaml"
        check(policy_path.is_file(), f"explicit skill {skill_md.parent.name} lacks Codex policy", errors)
        if policy_path.is_file():
            check("allow_implicit_invocation: false" in policy_path.read_text(encoding="utf-8"), f"explicit skill {skill_md.parent.name} allows implicit Codex invocation", errors)
    check(bool(explicit_skills), "no explicit-invocation skills discovered", errors)

    dispatcher_path = ROOT / "hooks" / "codex-dispatch.py"
    spec = importlib.util.spec_from_file_location("itd_codex_dispatch", dispatcher_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    patch = (
        "*** Begin Patch\n"
        "*** Update File: README.md\n"
        "*** Move to: .itd-memory/STATE.json\n"
        "*** Add File: src/new.py\n"
        "*** Delete File: src/old.py\n"
        "*** End Patch"
    )
    expected_paths = ["README.md", ".itd-memory/STATE.json", "src/new.py", "src/old.py"]
    check(module.affected_paths(patch) == expected_paths, "apply_patch add/update/delete/move path expansion failed", errors)
    normalized = module.normalized_payloads({"tool_name": "apply_patch", "tool_input": {"command": patch}})
    check([p["tool_input"]["file_path"] for p in normalized] == expected_paths, "apply_patch payload normalization failed", errors)

    probe = {
        "session_id": "codex-adapter-test",
        "cwd": str(ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "tool_input": {
            "command": "*** Begin Patch\n*** Add File: skills/fake-adapter/SKILL.md\n+body references/missing.md\n*** End Patch"
        },
    }
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PLUGIN_ROOT"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, str(dispatcher_path), "--script", "check-skill-completeness.sh"],
        input=json.dumps(probe),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        timeout=15,
    )
    check(proc.returncode == 2, f"normalized hard-gate probe did not deny (rc={proc.returncode})", errors)
    check("permissionDecision" in proc.stdout and "deny" in proc.stdout, "normalized deny payload was not preserved", errors)

    direct_probe = dict(probe)
    direct_probe["tool_name"] = "Write"
    direct_probe["tool_input"] = {
        "file_path": "skills/fake-adapter/SKILL.md",
        "content": "body references/missing.md",
    }
    direct = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "check-skill-completeness.sh")],
        input=json.dumps(direct_probe),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        timeout=15,
    )
    check(direct.returncode == proc.returncode == 2, "Claude/Codex hard-gate exit status diverges", errors)
    try:
        direct_decision = json.loads(direct.stdout)["hookSpecificOutput"]
        codex_decision = json.loads(proc.stdout)["hookSpecificOutput"]
        check(direct_decision == codex_decision, "Claude/Codex hard-gate decision payload diverges", errors)
    except (json.JSONDecodeError, KeyError):
        errors.append("Claude/Codex parity probe returned an invalid decision payload")

    unicode_env = env.copy()
    unicode_env.pop("PYTHONUTF8", None)
    with tempfile.TemporaryDirectory(prefix="itd-кодекс-") as unicode_cwd:
        unicode_probe = {
            "session_id": "codex-unicode-test",
            "cwd": unicode_cwd,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
        }
        unicode_run = subprocess.run(
            [sys.executable, str(dispatcher_path), "--script", "execution-trace.sh"],
            input=json.dumps(unicode_probe, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=ROOT,
            env=unicode_env,
            timeout=15,
        )
        trace_path = Path(unicode_cwd) / ".claude/traces/session-codex-unicode-test.jsonl"
        check(unicode_run.returncode == 0, f"Unicode transport probe failed (rc={unicode_run.returncode})", errors)
        check(trace_path.is_file(), "Unicode transport probe did not create an execution trace", errors)

    if errors:
        print("FAIL host adapters")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS host adapters: {len(referenced_scripts)} shared hook registrations, all {len(hard_gates)} hard gates registered for Codex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
