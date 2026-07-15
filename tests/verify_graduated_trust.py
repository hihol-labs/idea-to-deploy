#!/usr/bin/env python3
"""Behavioural proof for the machine-readable graduated-trust policy."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs" / "HARNESS_TRUST_POLICY.json"
DISPATCHER = ROOT / "hooks" / "codex-dispatch.py"


def validate_policy(payload: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["root must be an object"]
    if payload.get("version") != 1:
        issues.append("version must be 1")
    if payload.get("defaultRiskTier") != "low":
        issues.append("defaultRiskTier must be low")
    tiers = payload.get("tiers")
    if not isinstance(tiers, dict) or set(tiers) != {"low", "medium", "high"}:
        issues.append("tiers must be exactly low, medium, high")
    else:
        expected = {
            "low": ("allow-or-advisory", "fail-open"),
            "medium": ("ask", "surface-unverified"),
            "high": ("deny-or-block", "fail-closed"),
        }
        for tier, (enforcement, failure) in expected.items():
            row = tiers.get(tier) or {}
            if row.get("enforcement") != enforcement or row.get("transportFailure") != failure:
                issues.append(f"tier {tier} has an invalid enforcement/failure pair")
    gates = payload.get("hardGates")
    if not isinstance(gates, list) or not gates:
        return issues + ["hardGates must be a non-empty list"]
    scripts: set[str] = set()
    for index, gate in enumerate(gates):
        where = f"hardGates[{index}]"
        if not isinstance(gate, dict):
            issues.append(f"{where} must be an object")
            continue
        script = str(gate.get("script") or "")
        if not script.endswith(".sh"):
            issues.append(f"{where}.script must name a shared hook")
        if script in scripts:
            issues.append(f"{where}.script duplicates {script}")
        scripts.add(script)
        if gate.get("riskTier") != "high":
            issues.append(f"{where}.riskTier must be high")
        event = gate.get("event")
        decision = gate.get("decision")
        if (event, decision) not in {("PreToolUse", "deny"), ("SubagentStop", "block")}:
            issues.append(f"{where} has an invalid event/decision pair")
        test_path = ROOT / str(gate.get("behavioralTest") or "")
        if not test_path.is_file():
            issues.append(f"{where}.behavioralTest is missing")
    calibration = payload.get("lowRiskCalibration")
    if not isinstance(calibration, list) or len(calibration) < 4:
        issues.append("lowRiskCalibration must cover at least four controls")
    elif any(item.get("expected") != "allow" for item in calibration if isinstance(item, dict)):
        issues.append("lowRiskCalibration contains a blocking expectation")
    return issues


def run_hook(script: str, payload: dict[str, Any], cwd: Path, host: str) -> tuple[int, str]:
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "CLAUDE_SESSION_ID": "trust-low-risk", "PLUGIN_ROOT": str(ROOT)})
    command = [sys.executable, str(ROOT / "hooks" / script)]
    if host == "codex":
        command = [sys.executable, str(DISPATCHER), "--script", script]
        if payload.get("tool_name") in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
            original = payload.get("tool_input") or {}
            path = str(original.get("file_path") or "src/trust-probe.txt")
            content = str(original.get("content") or "probe")
            patch = "\n".join(
                ["*** Begin Patch", f"*** Update File: {path}"]
                + ["+" + line for line in content.splitlines()]
                + ["*** End Patch"]
            )
            payload = {**payload, "tool_name": "apply_patch", "tool_input": {"command": patch}}
    proc = subprocess.run(
        command,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=20,
    )
    return proc.returncode, proc.stdout


def decision(output: str) -> str:
    try:
        payload = json.loads(output or "{}")
    except json.JSONDecodeError:
        return ""
    return str((payload.get("hookSpecificOutput") or {}).get("permissionDecision") or payload.get("decision") or "")


def main() -> int:
    passed = failed = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"PASS {label}")
        else:
            failed += 1
            print(f"FAIL {label}: {detail}")

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    issues = validate_policy(policy)
    check("canonical graduated-trust policy is structurally valid", not issues, "; ".join(issues))

    mutated = copy.deepcopy(policy)
    del mutated["tiers"]["high"]
    check("mutation: missing high tier is rejected", bool(validate_policy(mutated)))
    mutated = copy.deepcopy(policy)
    mutated["hardGates"][0]["riskTier"] = "low"
    check("mutation: a hard gate cannot be downgraded to low", bool(validate_policy(mutated)))
    mutated = copy.deepcopy(policy)
    mutated["hardGates"][1]["script"] = mutated["hardGates"][0]["script"]
    check("mutation: duplicate hard-gate identity is rejected", bool(validate_policy(mutated)))

    with tempfile.TemporaryDirectory(prefix="itd-trust-") as tmp:
        cwd = Path(tmp)
        low_probes = [
            (
                "check-tool-skill.sh",
                {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status", "description": ""}},
            ),
            (
                "pii-egress-guard.sh",
                {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "echo hello"}},
            ),
            (
                "state-guard.sh",
                {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "README.md", "content": "x"}},
            ),
            (
                "completion-gate.sh",
                {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status", "description": ""}},
            ),
        ]
        for script, payload in low_probes:
            for host in ("claude", "codex"):
                rc, output = run_hook(script, payload, cwd, host)
                check(
                    f"low-risk calibration remains non-blocking on {host}: {script}",
                    rc == 0 and decision(output) not in {"deny", "block"},
                    f"rc={rc} decision={decision(output)!r} output={output[-200:]!r}",
                )

        env = os.environ.copy()
        env.update({"PYTHONUTF8": "1", "PLUGIN_ROOT": str(ROOT)})
        hard_failure = subprocess.run(
            [sys.executable, str(DISPATCHER), "--script", "check-skill-completeness.sh"],
            input="not-json",
            text=True,
            capture_output=True,
            cwd=cwd,
            env=env,
            timeout=20,
        )
        check(
            "high-risk Codex transport failure is fail-closed",
            hard_failure.returncode == 2 and decision(hard_failure.stdout) == "deny",
            f"rc={hard_failure.returncode} out={hard_failure.stdout!r}",
        )
        soft_failure = subprocess.run(
            [sys.executable, str(DISPATCHER), "--script", "execution-trace.sh"],
            input="not-json",
            text=True,
            capture_output=True,
            cwd=cwd,
            env=env,
            timeout=20,
        )
        check(
            "low-risk telemetry transport failure remains fail-open",
            soft_failure.returncode == 0 and decision(soft_failure.stdout) == "",
            f"rc={soft_failure.returncode} out={soft_failure.stdout!r}",
        )

        missing_root = cwd / "missing-plugin-root"
        missing_env = {**env, "PLUGIN_ROOT": str(missing_root)}
        valid_payload = json.dumps(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status"}}
        )
        missing_hard = subprocess.run(
            [sys.executable, str(DISPATCHER), "--script", "check-review-before-commit.sh"],
            input=valid_payload,
            text=True,
            capture_output=True,
            cwd=cwd,
            env=missing_env,
            timeout=20,
        )
        check(
            "missing high-risk hook returns a native fail-closed decision",
            missing_hard.returncode == 2 and decision(missing_hard.stdout) == "deny",
            f"rc={missing_hard.returncode} out={missing_hard.stdout!r}",
        )
        missing_soft = subprocess.run(
            [sys.executable, str(DISPATCHER), "--script", "execution-trace.sh"],
            input=valid_payload,
            text=True,
            capture_output=True,
            cwd=cwd,
            env=missing_env,
            timeout=20,
        )
        check(
            "missing low-risk telemetry hook remains fail-open",
            missing_soft.returncode == 0 and decision(missing_soft.stdout) == "",
            f"rc={missing_soft.returncode} out={missing_soft.stdout!r}",
        )

        slow_root = cwd / "slow-plugin-root"
        (slow_root / "docs").mkdir(parents=True)
        (slow_root / "hooks").mkdir()
        (slow_root / "docs" / POLICY.name).write_text(POLICY.read_text(encoding="utf-8"), encoding="utf-8")
        (slow_root / "hooks" / "check-review-before-commit.sh").write_text(
            "# python slow transport fixture\nimport time\ntime.sleep(10)\n",
            encoding="utf-8",
        )
        slow_env = {**env, "PLUGIN_ROOT": str(slow_root)}
        started = time.monotonic()
        slow_hard = subprocess.run(
            [sys.executable, str(DISPATCHER), "--script", "check-review-before-commit.sh"],
            input=valid_payload,
            text=True,
            capture_output=True,
            cwd=cwd,
            env=slow_env,
            timeout=5,
        )
        elapsed = time.monotonic() - started
        check(
            "internal timeout emits deny before the five-second host boundary",
            slow_hard.returncode == 2 and decision(slow_hard.stdout) == "deny" and elapsed < 5,
            f"elapsed={elapsed:.2f}s rc={slow_hard.returncode} out={slow_hard.stdout!r}",
        )

        (slow_root / "hooks" / "check-review-before-commit.sh").write_text(
            "# python slow multi-path transport fixture\nimport time\ntime.sleep(2)\n",
            encoding="utf-8",
        )
        multi_payload = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": (
                        "*** Begin Patch\n"
                        "*** Update File: first.txt\n+x\n"
                        "*** Add File: second.txt\n+y\n"
                        "*** End Patch"
                    )
                },
            }
        )
        started = time.monotonic()
        slow_multi = subprocess.run(
            [sys.executable, str(DISPATCHER), "--script", "check-review-before-commit.sh"],
            input=multi_payload,
            text=True,
            capture_output=True,
            cwd=cwd,
            env=slow_env,
            timeout=5,
        )
        elapsed = time.monotonic() - started
        check(
            "multi-path patch shares one deadline and denies before host timeout",
            slow_multi.returncode == 2 and decision(slow_multi.stdout) == "deny" and elapsed < 5,
            f"elapsed={elapsed:.2f}s rc={slow_multi.returncode} out={slow_multi.stdout!r}",
        )

        spec = importlib.util.spec_from_file_location("itd_codex_dispatch_timeout", DISPATCHER)
        if spec is None or spec.loader is None:
            check("dispatcher timeout constant is loadable", False, "module spec unavailable")
        else:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            hard_scripts = {gate["script"] for gate in policy["hardGates"]}
            timeout_pairs: list[tuple[str, int]] = []
            for config_path in (
                ROOT / "hooks" / "hooks.json",
                ROOT / "skills" / "adopt" / "references" / "codex-project-hooks.json",
            ):
                config = json.loads(config_path.read_text(encoding="utf-8"))
                for groups in config["hooks"].values():
                    for group in groups:
                        for hook in group.get("hooks", []):
                            command_text = str(hook.get("command", ""))
                            for script in hard_scripts:
                                if script in command_text:
                                    timeout_pairs.append((script, int(hook["timeout"])))
            violations = [
                (script, outer, module.shared_hook_timeout(script))
                for script, outer in timeout_pairs
                if outer <= module.shared_hook_timeout(script)
            ]
            check(
                "each bundled/local hard-gate timeout exceeds its dispatcher deadline",
                bool(timeout_pairs) and not violations,
                f"violations={violations}",
            )

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
