#!/usr/bin/env python3
"""Bounded, idempotent bootstrap core for the Codex `/adopt` workflow.

The lifecycle skill remains responsible for discovery, explaining the plan and
obtaining approval.  This helper removes the error-prone mechanical work after
approval: guidance entry, project contracts, state, and one explicitly supplied
first unit.  It never edits product source, installs dependencies, or touches
user-level host configuration.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


MARKER = "<!-- idea-to-deploy:begin codex-v1 -->"
FAIL_CLOSED = (
    "Not supplied during adoption; fail closed and ask the project owner "
    "before relying on this field."
)


def emit_failure(what: str, why: str, fix: str) -> int:
    print(f"FAILED: {what} | WHY: {why} | FIX: {fix}")
    return 2


def run(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def run_shell(command: str, cwd: Path, timeout: int = 300) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or "") + f"\n[timeout {timeout}s]"
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def git_root(project: Path) -> tuple[Path | None, str]:
    rc, out = run(["git", "rev-parse", "--show-toplevel"], project)
    if rc != 0 or not out.strip():
        return None, out.strip()
    return Path(out.strip().splitlines()[0]).resolve(), ""


def detect_stack(root: Path) -> list[str]:
    signals = {
        "pyproject.toml": "Python",
        "requirements.txt": "Python",
        "package.json": "Node.js",
        "go.mod": "Go",
        "Cargo.toml": "Rust",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle",
        "Dockerfile": "Docker",
    }
    found: list[str] = []
    for manifest, label in signals.items():
        if (root / manifest).is_file() and label not in found:
            found.append(label)
    return found or ["unknown"]


def self_reference(root: Path) -> bool:
    for manifest in (root / ".codex-plugin" / "plugin.json",
                     root / ".claude-plugin" / "plugin.json"):
        if not manifest.is_file():
            continue
        try:
            if json.loads(manifest.read_text(encoding="utf-8")).get("name") == "idea-to-deploy":
                return True
        except (OSError, json.JSONDecodeError):
            continue
    return False


def plugin_layout(plugin_root: Path) -> tuple[bool, str]:
    required = [
        plugin_root / ".codex-plugin" / "plugin.json",
        plugin_root / "hooks" / "hooks.json",
        plugin_root / "skills" / "adopt" / "references" / "agents-md-template.md",
        plugin_root / "docs" / "templates" / "itd",
        plugin_root / "docs" / "templates" / "itd-memory" / "STATE.example.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    return not missing, ", ".join(missing)


def plan(root: Path, plugin_root: Path, args: argparse.Namespace) -> dict:
    agents = root / "AGENTS.md"
    if not agents.exists():
        agents_action = "create"
    elif MARKER in agents.read_text(encoding="utf-8", errors="replace"):
        agents_action = "skip-marker-present"
    else:
        agents_action = "append-guarded-block"
    return {
        "projectRoot": str(root),
        "pluginRoot": str(plugin_root),
        "host": "codex",
        "AGENTS.md": agents_action,
        ".itd": "skip-existing" if (root / ".itd").exists() else "scaffold",
        ".itd-memory": "merge-missing-only" if (root / ".itd-memory").exists() else "initialize",
        "firstUnit": args.unit_id,
        "allowedAreas": args.allowed_area,
        "baselineCommand": args.baseline_command,
        "verificationCommand": args.verification_command,
        "productSourceWrites": [],
        "userLevelWrites": [],
    }


def write_new(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def guidance_entry(root: Path, plugin_root: Path) -> str:
    target = root / "AGENTS.md"
    block = (plugin_root / "skills" / "adopt" / "references" /
             "agents-md-template.md").read_text(encoding="utf-8").rstrip() + "\n"
    if not target.exists():
        target.write_text(block, encoding="utf-8")
        return "created"
    existing = target.read_text(encoding="utf-8")
    if MARKER in existing:
        return "unchanged"
    separator = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    target.write_text(existing + separator + block, encoding="utf-8")
    return "appended"


def fill_placeholder_markdown(itd: Path) -> None:
    """Replace scaffold instructions with an explicit, fail-closed abstention.

    Product invariants cannot be inferred during adoption.  Keeping template
    prose looks filled to a human while conveying no policy; an explicit
    abstention is honest and actionable.
    """
    for path in itd.glob("*.md"):
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        for idx, line in enumerate(lines):
            lowered = line.lower()
            if "replace this line" in lowered or "replace with" in lowered:
                prefix = "- " if line.lstrip().startswith("-") else ""
                lines[idx] = prefix + FAIL_CLOSED
                changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scaffold_contracts(root: Path, plugin_root: Path, args: argparse.Namespace,
                       today: str) -> str:
    itd = root / ".itd"
    if itd.exists():
        return "unchanged"
    source = plugin_root / "docs" / "templates" / "itd"
    shutil.copytree(source, itd)

    (itd / "SCOPE_LOCK.md").write_text(
        "# Scope Lock\n\n"
        "## Current Task\n\n"
        f"- {args.unit_id}: {args.unit_criterion}\n\n"
        "## Allowed Change Areas\n\n" +
        "".join(f"- `{area}`\n" for area in args.allowed_area) +
        "\n## Forbidden Change Areas\n\n"
        "- Everything outside the explicit allowed areas above.\n\n"
        "## Review Rule\n\n"
        "If the diff touches any other area, pause and obtain explicit scope approval.\n",
        encoding="utf-8",
    )
    forbidden = (itd / "FORBIDDEN_CHANGES.md").read_text(encoding="utf-8")
    forbidden = forbidden.replace(
        "- Replace this line with project-owned forbidden changes.",
        "- No project-specific exception was supplied during adoption; preserve existing product semantics and fail closed on ambiguity.",
    )
    (itd / "FORBIDDEN_CHANGES.md").write_text(forbidden, encoding="utf-8")

    verification_path = itd / "VERIFICATION_CONTRACT.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification.update({
        "unitId": args.unit_id,
        "createdAt": today,
        "commands": [{
            "id": "first-unit",
            "command": args.verification_command,
            "timeoutSeconds": args.timeout,
            "expectedOutput": "",
            "passFailParser": "exit_code_zero",
        }],
        "requiredArtifacts": [
            "AGENTS.md",
            ".itd-memory/STATE.json",
            f".itd-memory/contracts/{args.unit_id}.md",
        ],
    })
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")

    acceptance_path = itd / "ACCEPTANCE_CONTRACT.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    acceptance.update({
        "sourceRequest": args.unit_criterion,
        "createdAt": today,
        "criteria": [{
            "id": "AC-1",
            "criterion": args.unit_criterion,
            "source": "Explicit --unit-criterion supplied to the approved adoption plan.",
            "evidence": "Exit-zero output from the declared verification command.",
            "verificationCommand": args.verification_command,
            "status": "pending",
        }],
    })
    acceptance_path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")

    exit_path = itd / "SESSION_EXIT_CONTRACT.json"
    exit_contract = json.loads(exit_path.read_text(encoding="utf-8"))
    exit_contract["startupProbeCommand"] = args.baseline_command
    exit_contract["debugScan"]["paths"] = [
        area.rstrip("/") for area in args.allowed_area
        if (root / area.rstrip("/")).exists()
    ]
    exit_path.write_text(json.dumps(exit_contract, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")

    fill_placeholder_markdown(itd)
    return "created"


def initial_state(plugin_root: Path, stack: list[str], args: argparse.Namespace) -> dict:
    template = plugin_root / "docs" / "templates" / "itd-memory" / "STATE.example.json"
    state = json.loads(template.read_text(encoding="utf-8"))
    state.update({
        "sessionState": "ACTIVE",
        "currentStage": "ADOPTED",
        "intent": "adoption and first verified unit",
        "classification": {
            "productType": "unknown",
            "domain": "unknown",
            "complexity": "unknown",
            "requiredModules": [],
            "infrastructure": [],
        },
        "architecture": {},
        "currentUnit": {
            "id": args.unit_id,
            "goal": args.unit_criterion,
            "status": "pending",
            "startedAt": "",
            "completedAt": "",
        },
        "tddEvidence": {"red": "", "green": "", "lastRecordedAt": ""},
        "rootCause": {"status": "n/a", "summary": "", "evidence": "", "hypothesis": "", "recordedAt": ""},
        "reviewStages": {
            "specCompliance": {"status": "pending", "evidence": "", "recordedAt": ""},
            "codeQuality": {"status": "pending", "evidence": "", "recordedAt": ""},
        },
        "branchFinish": {"status": "pending", "mode": "", "verification": "", "prUrl": "", "recordedAt": ""},
        "verificationHistory": [],
        "decisionLog": [{
            "at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "decision": "Use bounded Codex adoption with project-local contracts and state.",
            "why": "Explicitly approved plan; no product source or user-level configuration writes.",
        }],
        "artifacts": [],
        "completedModules": [],
        "failedValidations": [],
        "blockers": [],
        "eventLog": {"path": ".itd-memory/events.jsonl", "lastEventId": "", "lastEventAt": ""},
        "nextAction": f"Seal and activate {args.unit_id}, then run its verification command.",
    })
    state["existingProject"] = {
        "isExistingProject": True,
        "detectedStack": stack,
        "availableCommands": [args.baseline_command, args.verification_command],
        "currentTaskRoute": "task",
        "lastAnalysisSummary": "Detected from manifests; verify manually.",
    }
    state["gateResults"] = {key: "pending" for key in state.get("gateResults", {})}
    state["gateResults"]["nextStepApproval"] = "approved"
    state["humanSteering"] = {
        "approvalRequired": True,
        "approvalStatus": "approved",
        "recommendedNextStep": f"Start {args.unit_id} under the declared verification oracle.",
        "alternatives": [],
        "pendingQuestions": [],
    }
    return state


def scaffold_state(root: Path, plugin_root: Path, stack: list[str],
                   args: argparse.Namespace, now: str) -> list[str]:
    memory = root / ".itd-memory"
    memory.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    if write_new(memory / "STATE.json",
                 json.dumps(initial_state(plugin_root, stack, args), ensure_ascii=False, indent=2) + "\n"):
        created.append("STATE.json")
    if write_new(memory / "events.jsonl", ""):
        created.append("events.jsonl")
    if write_new(memory / "session-artifacts.json",
                 json.dumps({"version": 1, "artifacts": []}, indent=2) + "\n"):
        created.append("session-artifacts.json")
    goal = {
        "version": 1,
        "goal": args.unit_criterion,
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
        "currentUnitId": args.unit_id,
        "runPolicy": {
            "mode": "bounded_autonomous",
            "maxAttemptsPerUnit": 2,
            "maxWallClockSecondsPerUnit": max(args.timeout * 2, 300),
            "maxTokensPerSession": 20000,
            "freezeVerification": True,
            "requireApproach": True,
            "requireIndependentReview": False,
            "enforceObservedTokens": False,
        },
        "units": [{
            "id": args.unit_id,
            "criterion": args.unit_criterion,
            "verificationCommand": args.verification_command,
            "status": "pending",
            "verifiedAt": "",
            "evidence": "",
            "skippedReason": "",
        }],
    }
    if write_new(memory / "GOAL.json", json.dumps(goal, ensure_ascii=False, indent=2) + "\n"):
        created.append("GOAL.json")
    contract = (
        f"# Task Contract: {args.unit_id} — first verified unit\n\n"
        "## Scope\n" + "".join(f"- `{area}`\n" for area in args.allowed_area) +
        "\n## Verification Standards\n"
        f"- `{args.verification_command}` exits 0.\n"
        f"- Criterion: {args.unit_criterion}\n\n"
        "## Exclusions\n"
        "- No writes outside the approved areas.\n"
        "- No deployment, external write, dependency installation, or user-level configuration change.\n"
    )
    if write_new(memory / "contracts" / f"{args.unit_id}.md", contract):
        created.append(f"contracts/{args.unit_id}.md")
    return created


def validate_args(args: argparse.Namespace) -> str | None:
    required = {
        "--baseline-command": args.baseline_command,
        "--verification-command": args.verification_command,
        "--unit-criterion": args.unit_criterion,
        "--allowed-area": args.allowed_area,
    }
    missing = [name for name, value in required.items() if not value]
    return ", ".join(missing) if missing else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan/apply the bounded Codex adoption bootstrap.")
    parser.add_argument("--project", required=True, help="target git repository")
    parser.add_argument("--plugin-root", default=str(Path(__file__).resolve().parents[3]))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="inspect only; default")
    mode.add_argument("--apply", action="store_true", help="perform the approved bounded writes")
    parser.add_argument("--approved", action="store_true", help="assert that the shown plan was approved")
    parser.add_argument("--baseline-command", required=True)
    parser.add_argument("--verification-command", required=True)
    parser.add_argument("--unit-id", default="U-001")
    parser.add_argument("--unit-criterion", required=True)
    parser.add_argument("--allowed-area", action="append", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    project_arg = Path(args.project).expanduser()
    if not project_arg.is_dir():
        return emit_failure("project discovery", "target directory does not exist",
                            "pass --project pointing at an existing git repository")
    root, detail = git_root(project_arg)
    if root is None:
        return emit_failure("project discovery", detail or "not a git repository",
                            "run git init and create at least one commit, then retry")
    if root != project_arg.resolve():
        return emit_failure("project boundary", f"--project resolves inside {root}",
                            f"rerun with --project {root}")
    if self_reference(root):
        return emit_failure("self-reference guard", "target is the idea-to-deploy methodology repository",
                            "run /adopt from the external project that should consume the methodology")

    plugin_root = Path(args.plugin_root).expanduser().resolve()
    valid, missing = plugin_layout(plugin_root)
    if not valid:
        return emit_failure("plugin discovery", f"required plugin files are missing: {missing}",
                            "update/reinstall idea-to-deploy and pass its root via --plugin-root")
    missing_args = validate_args(args)
    if missing_args:
        return emit_failure("adoption contract", f"missing explicit values: {missing_args}",
                            "supply the baseline, first-unit oracle, criterion, and allowed areas")

    bounded_plan = plan(root, plugin_root, args)
    print("ADOPT PLAN " + json.dumps(bounded_plan, ensure_ascii=False, sort_keys=True))
    if not args.apply:
        print("PLAN ONLY: no files written. FIX: review the plan, then rerun with --apply --approved.")
        return 0
    if not args.approved:
        return emit_failure("approval gate", "--apply was requested without recorded plan approval",
                            "show the ADOPT PLAN to the user and rerun with --apply --approved only after yes")

    today = dt.date.today().isoformat()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stack = detect_stack(root)
    agents_result = guidance_entry(root, plugin_root)
    itd_result = scaffold_contracts(root, plugin_root, args, today)
    state_created = scaffold_state(root, plugin_root, stack, args, now)

    rc, out = run_shell(args.baseline_command, root, timeout=args.timeout)
    if rc != 0:
        tail = out.strip()[-1200:]
        if tail:
            print(tail)
        return emit_failure("baseline verification", f"command exited {rc}: {args.baseline_command}",
                            "repair the declared project-local baseline command; adoption files are preserved as the visible fix target")

    print("BASELINE: PASS")
    print("ADOPTION: PASS " + json.dumps({
        "AGENTS.md": agents_result,
        ".itd": itd_result,
        "stateCreated": state_created,
        "stack": stack,
        "manualRepairs": 0,
        "productSourceWrites": 0,
        "userLevelWrites": 0,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
