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
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath


MARKER = "<!-- idea-to-deploy:begin codex-v1 -->"
FAIL_CLOSED = (
    "Not supplied during adoption; fail closed and ask the project owner "
    "before relying on this field."
)
SHELL_CONTROL_TOKENS = {
    "&",
    "&&",
    "|",
    "||",
    ";",
    "<",
    ">",
    ">>",
    "2>",
    "2>&1",
}


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
        "verificationArgv": args.verification_argv,
        "trustedVerifierPaths": args.trusted_verifier_path,
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
            "argv": args.verification_argv,
            "trustedVerifierPaths": args.trusted_verifier_path,
            "timeoutSeconds": args.timeout,
            "expectedOutput": "",
            "passFailParser": "exit_code_zero",
        }],
        "requiredArtifacts": [
            "AGENTS.md",
            ".itd/VERIFICATION_CONTRACT.json",
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
        "--trusted-verifier-path": args.trusted_verifier_path,
        "--unit-criterion": args.unit_criterion,
        "--allowed-area": args.allowed_area,
    }
    missing = [name for name, value in required.items() if not value]
    return ", ".join(missing) if missing else None


def verification_argv(command: str) -> list[str]:
    try:
        result = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError("verification command quoting is invalid") from exc
    if (
        not result
        or any(token in SHELL_CONTROL_TOKENS for token in result)
        or any("\x00" in token for token in result)
    ):
        raise ValueError(
            "verification command must be one shell-free argv invocation"
        )
    executable = Path(result[0].replace("\\", "/")).name.casefold()
    if executable.startswith(("python", "pypy")) and "-I" not in result[1:]:
        result.insert(1, "-I")
    return result


def normalize_trusted_paths(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        path = PurePosixPath(value.replace("\\", "/"))
        if (
            not value
            or path.is_absolute()
            or ".." in path.parts
            or any(part in {"", "."} for part in path.parts)
        ):
            raise ValueError("trusted verifier path is unsafe")
        relative = path.as_posix()
        if relative in normalized:
            raise ValueError("trusted verifier path is duplicated")
        normalized.append(relative)
    return normalized


def validate_trusted_paths(root: Path, paths: list[str]) -> str | None:
    """Validate bootstrap HEAD inputs; protected authority is established later."""
    for path in paths:
        rc, output = run(
            [
                "git",
                "ls-tree",
                "-r",
                "--full-tree",
                "HEAD",
                "--",
                path,
            ],
            root,
        )
        rows = [line for line in output.splitlines() if line.strip()]
        target = root / path
        if (
            rc != 0
            or len(rows) != 1
            or "\t" not in rows[0]
            or rows[0].split("\t", 1)[1] != path
            or not target.is_file()
            or target.is_symlink()
        ):
            return f"{path} is not tracked in the current project HEAD"
        metadata = rows[0].split("\t", 1)[0].split()
        if (
            len(metadata) != 3
            or metadata[0] not in {"100644", "100755"}
            or metadata[1] != "blob"
            or not re.fullmatch(r"[0-9a-f]{40,64}", metadata[2])
        ):
            return f"{path} contains a symlink or non-regular Git object"
        rc, worktree_sha = run(["git", "hash-object", "--", path], root)
        if rc != 0 or worktree_sha.strip() != metadata[2]:
            return f"{path} content differs from the current project HEAD"
    return None


def validate_verification_argv(
    root: Path,
    argv: list[str],
    trusted_paths: list[str],
) -> str | None:
    def references_trusted(argument: str) -> bool:
        normalized = argument.replace("\\", "/").lstrip("./")
        dotted = normalized.replace("/", ".")
        return any(
            normalized == path
            or dotted == path.replace("/", ".")
            or (
                path.endswith(".py")
                and dotted == path[:-3].replace("/", ".")
            )
            for path in trusted_paths
        )

    launcher = PurePosixPath(
        argv[0].replace("\\", "/")
    ).name.casefold()
    system_launcher = (
        re.fullmatch(
            r"(?:python|pypy)(?:\d+(?:\.\d+)*)?(?:\.exe)?",
            launcher,
        )
        is not None
        or launcher
        in {
            "sh",
            "bash",
            "dash",
            "ksh",
            "zsh",
            "node",
            "node.exe",
            "pwsh",
            "pwsh.exe",
            "powershell",
            "powershell.exe",
        }
    )
    launcher_value = argv[0].replace("\\", "/")
    launcher_path = PurePosixPath(launcher_value)
    launcher_is_absolute = (
        launcher_path.is_absolute()
        or re.match(r"^[A-Za-z]:/", launcher_value) is not None
    )
    if system_launcher and launcher_is_absolute:
        trusted_launchers: set[Path] = set()
        discovered = shutil.which(launcher)
        if discovered:
            trusted_launchers.add(Path(discovered).resolve())
        if launcher.startswith(("python", "pypy")):
            trusted_launchers.add(Path(sys.executable).resolve())
        if Path(argv[0]).resolve() not in trusted_launchers:
            return (
                "verification argv absolute interpreter does not resolve "
                "to the active or PATH-selected system launcher"
            )
    if not references_trusted(argv[0]) and not system_launcher:
        return (
            "verification argv launcher is neither a declared trusted "
            "executable nor an approved system interpreter"
        )
    if (
        launcher
        in {"sh", "bash", "dash", "ksh", "zsh"}
        and "-c" in argv[1:]
    ) or (
        launcher.startswith(("python", "pypy"))
        and any(item in {"-c", "-"} for item in argv[1:])
    ) or (
        launcher in {"node", "node.exe"}
        and any(item in {"-e", "--eval", "-p", "--print"} for item in argv[1:])
    ) or (
        launcher
        in {"pwsh", "pwsh.exe", "powershell", "powershell.exe"}
        and any(
            item.casefold() in {"-command", "-encodedcommand"}
            for item in argv[1:]
        )
    ):
        return "verification argv uses an inline-code interpreter mode"

    referenced = False
    for argument_index, argument in enumerate(argv):
        values = [(argument, False)]
        if argument.startswith("-") and "=" in argument:
            option_value = argument.split("=", 1)[1]
            if option_value:
                values = [(option_value, True)]
        for value, path_option in values:
            if references_trusted(value):
                referenced = True
            candidate = PurePosixPath(value.replace("\\", "/"))
            if (
                candidate.is_absolute()
                or re.match(r"^[A-Za-z]:/", value.replace("\\", "/"))
                or ".." in candidate.parts
                or any(part in {"", "."} for part in candidate.parts)
            ):
                if argument_index == 0 and system_launcher:
                    continue
                return (
                    "verification argv contains an unsafe path-bearing "
                    + ("option value" if path_option else "argument")
                )
            relative = candidate.as_posix()
            rc, output = run(
                ["git", "ls-files", "--stage", "--", relative],
                root,
            )
            path_like = (
                "/" in relative
                or candidate.suffix.casefold()
                in {
                    ".py", ".js", ".mjs", ".cjs", ".sh", ".ps1",
                    ".rb", ".pl", ".json", ".yaml", ".yml", ".toml",
                    ".ini", ".cfg", ".conf",
                }
            )
            if (
                argument_index > 0
                and path_like
                and not references_trusted(value)
                and (rc != 0 or not output.strip())
            ):
                return (
                    "verification argv references an undeclared untracked "
                    f"input: {relative}"
                )
            if (
                rc == 0
                and output.strip()
                and not any(
                    relative == path
                    or relative.startswith(path.rstrip("/") + "/")
                    for path in trusted_paths
                )
            ):
                return (
                    f"verification argv references undeclared tracked input: "
                    f"{relative}"
                )
    if not referenced:
        return (
            "verification argv does not invoke a declared trusted verifier"
        )
    return None


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
    parser.add_argument(
        "--trusted-verifier-path",
        action="append",
        required=True,
        help=(
            "exact tracked verifier file whose protected-base Git content "
            "must match the PR candidate; repeat as needed"
        ),
    )
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
    try:
        args.verification_argv = verification_argv(
            args.verification_command
        )
        args.trusted_verifier_path = normalize_trusted_paths(
            args.trusted_verifier_path
        )
    except ValueError as exc:
        return emit_failure(
            "machine oracle",
            str(exc),
            "use one argv command and explicit tracked relative verifier paths",
        )
    trusted_path_error = validate_trusted_paths(
        root,
        args.trusted_verifier_path,
    )
    if trusted_path_error:
        return emit_failure(
            "machine oracle",
            trusted_path_error,
            "commit regular verifier files first, then rerun adoption",
        )
    argv_trust_error = validate_verification_argv(
        root,
        args.verification_argv,
        args.trusted_verifier_path,
    )
    if argv_trust_error:
        return emit_failure(
            "machine oracle",
            argv_trust_error,
            "invoke the tracked verifier path directly and declare every "
            "tracked argv input",
        )

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
