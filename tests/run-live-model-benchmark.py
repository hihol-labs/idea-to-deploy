#!/usr/bin/env python3
"""Run one real headless-model fixture and persist replayable H4 evidence.

Exit 0 means both the live candidate and the independent snapshot oracle
passed. Exit 3 means the external model cannot be run (missing CLI/auth); a
bounded UNVERIFIED report is still written. Every other failure exits 1.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "tests" / "fixtures" / "live-model-evidence" / "latest.json"
METHODOLOGY_TREE_ROOTS = (
    "AGENTS.md",
    ".codex-plugin",
    ".claude-plugin",
    "skills",
    "agents",
    "hooks",
    "docs/templates/itd",
    "docs/templates/itd-memory",
    "docs/HOST_ADAPTER_CONTRACT.md",
    "docs/host-adapters.json",
)
GENERATED_STATUS_PREFIXES = ("tests/fixtures/live-model-evidence/",)
def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def stable_git_status(raw: bytes) -> bytes:
    """Exclude benchmark-owned outputs from the dirty input fingerprint."""
    kept = []
    for line in raw.splitlines(keepends=True):
        decoded = line.decode("utf-8", errors="replace")
        path_field = decoded.rstrip("\r\n")[3:] if len(decoded) >= 3 else decoded
        paths = [item.strip().strip('"') for item in path_field.split(" -> ")]
        generated_only = bool(paths) and all(
            any(path.startswith(prefix) for prefix in GENERATED_STATUS_PREFIXES)
            for path in paths)
        if generated_only:
            continue
        kept.append(line)
    return b"".join(kept)


def git_status_bytes() -> bytes:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT,
        capture_output=True, timeout=20)
    return (stable_git_status(result.stdout) if result.returncode == 0
            else b"git-status-unavailable")


def methodology_files() -> list[Path]:
    files: list[Path] = []
    for raw in METHODOLOGY_TREE_ROOTS:
        path = ROOT / raw
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*")
                         if candidate.is_file() and "__pycache__" not in candidate.parts
                         and candidate.suffix != ".pyc")
    return sorted(set(files), key=lambda item: item.relative_to(ROOT).as_posix())


def methodology_tree_sha256() -> str:
    digest = hashlib.sha256()
    for path in methodology_files():
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def source_pins(fixture_dir: Path, provider: str) -> dict[str, str]:
    paths = {
        "benchmarkRunner": Path(__file__).resolve(),
        "candidateAdapter": Path(__file__).resolve(),
        "oracle": ROOT / "tests" / "verify_snapshot.py",
        "fixturePrompt": fixture_dir / "live-prompt.md",
        "fixtureContract": fixture_dir / "expected-snapshot.json",
        "codexAdapterTemplate": ROOT / "skills" / "adopt" / "references" / "codex-project-hooks.json",
        "agentsTemplate": ROOT / "skills" / "adopt" / "references" / "agents-md-template.md",
    }
    pins = {name: sha256_file(path) for name, path in paths.items()}
    pins["methodologyTree"] = methodology_tree_sha256()
    return pins


def anthropic_auth_available(claude: str) -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    try:
        result = subprocess.run(
            [claude, "auth", "status", "--json"], capture_output=True,
            text=True, timeout=15)
        if result.returncode != 0:
            return False
        status = json.loads(result.stdout)
        return status.get("loggedIn") is True
    except Exception:
        return False


def openai_auth_available(codex: str) -> bool:
    try:
        result = subprocess.run(
            [codex, "login", "status"], capture_output=True, text=True,
            timeout=15)
        diagnostic = result.stdout + "\n" + result.stderr
        return result.returncode == 0 and "logged in" in diagnostic.lower()
    except Exception:
        return False


def base_report(args: argparse.Namespace, status: str, reason: str) -> dict:
    status_bytes = git_status_bytes()
    return {
        "schemaVersion": 1,
        "benchmark": "itd-live-fixture-v1",
        "status": status,
        "observedAt": utc_now(),
        "provider": args.resolved_provider,
        "fixture": args.fixture,
        "candidateModelRequested": args.model or "provider-default",
        "reason": reason,
        "source": {
            "revision": git_revision(),
            "workingTreeDirty": bool(status_bytes.strip()),
            "workingTreeStatusSha256": sha256_bytes(status_bytes),
            "methodologyTreeSha256": methodology_tree_sha256(),
        },
        "runner": "tests/run-live-model-benchmark.py",
    }


def required_files(snapshot: dict) -> list[str]:
    files = snapshot.get("files") or {}
    required = files.get("required") if isinstance(files, dict) else []
    if not isinstance(required, list) or not required:
        raise ValueError("active fixture has no required files")
    clean: list[str] = []
    for raw in required:
        rel = Path(str(raw))
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"unsafe required fixture path: {raw}")
        clean.append(rel.as_posix())
    return clean


def parse_result_events(stream: Path, provider: str) -> list[dict]:
    rows: list[dict] = []
    for line in stream.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        terminal_type = "result" if provider == "anthropic" else "turn.completed"
        if isinstance(row, dict) and row.get("type") == terminal_type:
            rows.append(row)
    return rows


def fixture_prompt(fixture_dir: Path) -> str:
    prompt = fixture_dir / "live-prompt.md"
    if not prompt.is_file():
        raise ValueError("fixture live-prompt.md is missing")
    text = prompt.read_text(encoding="utf-8", errors="strict").strip()
    if "$idea-to-deploy:blueprint" not in text:
        raise ValueError("live prompt does not explicitly invoke the ITD blueprint skill")
    return text


def copy_path(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def prepare_adopted_project(workspace: Path) -> tuple[Path, Path]:
    """Build an isolated project using the current repository-local adapter."""
    project = workspace / "project"
    plugin = project / ".itd-plugin"
    project.mkdir(parents=True)
    for raw in METHODOLOGY_TREE_ROOTS:
        source = ROOT / raw
        if source.exists():
            copy_path(source, plugin / raw)

    guidance = (ROOT / "skills" / "adopt" / "references" / "agents-md-template.md").read_text(
        encoding="utf-8")
    guidance += (
        "\n## Local benchmark adapter\n\n"
        "The enabled repository-local Idea to Deploy plugin is `.itd-plugin/`. "
        "For `$idea-to-deploy:blueprint`, you MUST read and follow "
        "`.itd-plugin/skills/blueprint/SKILL.md` and every directly required reference. "
        "This local plugin, not general model knowledge, is the workflow source of truth.\n"
    )
    (project / "AGENTS.md").write_text(guidance, encoding="utf-8")
    shutil.copytree(plugin / "docs" / "templates" / "itd", project / ".itd")

    hooks = json.loads((plugin / "skills" / "adopt" / "references" /
                        "codex-project-hooks.json").read_text(encoding="utf-8"))
    hooks = {key: value for key, value in hooks.items() if not str(key).startswith("_comment")}
    rendered = json.dumps(hooks, ensure_ascii=False, indent=2)
    rendered = rendered.replace("{{ITD_ROOT}}", plugin.as_posix())
    rendered = rendered.replace("{{ITD_ROOT_WINDOWS}}", plugin.as_posix().replace("/", "\\"))
    (project / ".codex").mkdir()
    (project / ".codex" / "hooks.json").write_text(rendered + "\n", encoding="utf-8")
    return project, plugin


def transcript_proves_harness(raw: bytes) -> bool:
    text = raw.decode("utf-8", errors="replace")
    return ("skills/blueprint/SKILL.md" in text
            and "skills/blueprint/references/document-templates.md" in text)


def resolve_provider(args: argparse.Namespace) -> tuple[str, str] | tuple[None, str]:
    claude = shutil.which("claude")
    codex = shutil.which("codex")
    if args.provider == "anthropic":
        if not claude:
            return None, "claude CLI is unavailable"
        if not anthropic_auth_available(claude):
            return None, "claude CLI has no external credential/auth session"
        return "anthropic", claude
    if args.provider == "openai":
        if not codex:
            return None, "codex CLI is unavailable"
        if not openai_auth_available(codex):
            return None, "codex CLI has no external credential/auth session"
        return "openai", codex
    if claude and (os.environ.get("ANTHROPIC_API_KEY")
                   or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")):
        return "anthropic", claude
    if codex and openai_auth_available(codex):
        return "openai", codex
    if claude and anthropic_auth_available(claude):
        return "anthropic", claude
    return None, "no authenticated live-model CLI is available"


def run_candidate(args: argparse.Namespace, executable: str, project: Path,
                  plugin: Path, prompt: str) -> tuple[subprocess.CompletedProcess[str], str]:
    if args.resolved_provider == "anthropic":
        command = [
            executable, "-p", "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--model", args.model or "sonnet",
            "--dangerously-skip-permissions", "--plugin-dir", str(plugin),
            "--max-budget-usd", args.budget, prompt,
        ]
        completed = subprocess.run(
            command, cwd=project, capture_output=True, text=True,
            timeout=args.timeout_seconds)
        (project / ".run.stream.jsonl").write_text(completed.stdout, encoding="utf-8")
        return completed, "claude -p --plugin-dir <current-itd>"

    command = [
        executable, "exec", "--json", "--ephemeral", "--ignore-user-config",
        "--config", 'model_reasoning_effort="medium"',
        "--skip-git-repo-check", "--sandbox", "workspace-write",
        "--dangerously-bypass-hook-trust", "-C", str(project),
    ]
    if args.model:
        command.extend(["--model", args.model])
    command.append("-")
    completed = subprocess.run(
        command, cwd=project, input=prompt, capture_output=True,
        text=True, timeout=args.timeout_seconds)
    (project / ".run.stream.jsonl").write_text(completed.stdout, encoding="utf-8")
    return completed, "codex exec --json --ephemeral --repository-local-itd"


def fail(args: argparse.Namespace, reason: str, *, code: int = 1) -> int:
    status = "UNVERIFIED" if code == 3 else "FAIL"
    atomic_json(args.evidence, base_report(args, status, reason))
    print(f"{status}: {reason}")
    return code


def run(args: argparse.Namespace) -> int:
    fixture_dir = ROOT / "tests" / "fixtures" / args.fixture
    snapshot_path = fixture_dir / "expected-snapshot.json"
    stream_input = fixture_dir / "stream.jsonl"
    live_prompt = fixture_dir / "live-prompt.md"
    if (not fixture_dir.is_dir() or not snapshot_path.is_file()
            or not stream_input.is_file() or not live_prompt.is_file()):
        return fail(args, "fixture contract or stream is missing")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("status") != "active":
        return fail(args, "fixture is not active")
    provider, executable_or_reason = resolve_provider(args)
    if provider is None:
        args.resolved_provider = args.provider
        return fail(args, executable_or_reason, code=3)
    args.resolved_provider = provider
    try:
        prompt = fixture_prompt(fixture_dir)
    except ValueError as exc:
        return fail(args, str(exc))

    with tempfile.TemporaryDirectory(prefix="itd-live-model-") as tmp:
        output, plugin = prepare_adopted_project(Path(tmp))
        try:
            candidate, command_family = run_candidate(
                args, executable_or_reason, output, plugin, prompt)
        except subprocess.TimeoutExpired:
            return fail(args, f"live candidate exceeded {args.timeout_seconds}s timeout")
        if candidate.returncode != 0:
            tail = (candidate.stdout + "\n" + candidate.stderr).strip().splitlines()[-1:]
            return fail(args, "live candidate/oracle failed" + (f": {tail[0]}" if tail else ""))

        stream = output / ".run.stream.jsonl"
        if not stream.is_file():
            return fail(args, "live candidate produced no stream transcript")
        transcript_raw = stream.read_bytes()
        results = parse_result_events(stream, args.resolved_provider)
        if not results or (args.resolved_provider == "anthropic"
                           and results[-1].get("is_error") is True):
            return fail(args, "live transcript has no successful result event")
        if not transcript_proves_harness(transcript_raw):
            return fail(args, "live transcript does not prove ITD blueprint skill/reference loading")

        oracle_command = [
            sys.executable, str(ROOT / "tests" / "verify_snapshot.py"),
            str(fixture_dir), "--output", str(output),
        ]
        oracle = subprocess.run(
            oracle_command, cwd=ROOT, capture_output=True, text=True, timeout=180)
        if oracle.returncode != 0:
            detail = (oracle.stdout + "\n" + oracle.stderr).strip().splitlines()
            bounded = " | ".join(detail[-4:])[:1200]
            return fail(args, "independent snapshot oracle rejected live output"
                        + (f": {bounded}" if bounded else ""))

        required = required_files(snapshot)
        for rel in required:
            if not (output / rel).is_file():
                return fail(args, f"oracle passed but required output is missing: {rel}")

        transcript_hash = sha256_bytes(transcript_raw)
        run_id = utc_now().replace("-", "").replace(":", "") + "-" + transcript_hash[-8:]
        evidence_root = args.evidence.parent.resolve()
        run_dir = evidence_root / "runs" / run_id
        archive_output = run_dir / "output"
        archive_output.mkdir(parents=True, exist_ok=False)
        artifact_hashes: dict[str, str] = {}
        for rel in required:
            target = archive_output / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output / rel, target)
            artifact_hashes[rel] = sha256_file(target)
        transcript_archive = run_dir / "transcript.jsonl.gz"
        with gzip.open(transcript_archive, "wb", compresslevel=9) as handle:
            handle.write(transcript_raw)

        last = results[-1]
        report = base_report(args, "PASS", "live candidate passed independent snapshot oracle")
        report.update({
            "runId": run_id,
            "runReport": (run_dir / "run-report.json").relative_to(ROOT).as_posix(),
            "runArtifactDir": run_dir.relative_to(ROOT).as_posix(),
            "candidate": {
                "commandFamily": command_family,
                "exitCode": candidate.returncode,
                "liveResultEvents": len(results),
                "resultSubtype": last.get("subtype"),
                "isError": bool(last.get("is_error")),
                "durationMs": last.get("duration_ms"),
                "totalCostUsd": last.get("total_cost_usd"),
                "transcriptSha256": transcript_hash,
                "transcriptArtifact": transcript_archive.relative_to(ROOT).as_posix(),
                "transcriptGzipSha256": sha256_file(transcript_archive),
            },
            "harnessInvocation": {
                "mode": "repository-local-adopted-project",
                "skill": "$idea-to-deploy:blueprint",
                "skillPath": ".itd-plugin/skills/blueprint/SKILL.md",
                "referencePath": ".itd-plugin/skills/blueprint/references/document-templates.md",
                "projectGuidance": "AGENTS.md",
                "projectContracts": ".itd/",
                "projectHooks": ".codex/hooks.json" if args.resolved_provider == "openai" else "plugin hooks/hooks.json",
                "transcriptProvesSkillLoad": True,
                "methodologyTreeSha256": methodology_tree_sha256(),
            },
            "artifacts": {
                "outputDir": archive_output.relative_to(ROOT).as_posix(),
                "requiredFiles": required,
                "sha256": artifact_hashes,
            },
            "independentVerdict": {
                "actor": "deterministic-external-oracle",
                "oracle": "tests/verify_snapshot.py",
                "exitCode": oracle.returncode,
                "status": "PASS",
                "candidateSelfReportAccepted": False,
            },
            "sourcePins": source_pins(fixture_dir, args.resolved_provider),
        })
        atomic_json(run_dir / "run-report.json", report)
        atomic_json(args.evidence, report)
        print(f"PASS live-model: {args.fixture} -> {run_id}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="fixture-03-cli-tool")
    parser.add_argument("--provider", choices=("auto", "anthropic", "openai"), default="auto")
    parser.add_argument("--model", default="")
    parser.add_argument("--budget", default="5.00")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    args.resolved_provider = args.provider
    args.evidence = args.evidence.resolve()
    if args.timeout_seconds < 60 or args.timeout_seconds > 3600:
        parser.error("--timeout-seconds must be within 60..3600")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
