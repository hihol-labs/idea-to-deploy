#!/usr/bin/env python3
"""Run a bounded real headless-model fixture and persist replayable H4 evidence.

Exit 0 means both the live candidate and the independent snapshot oracle
passed. Exit 3 means the external model cannot be run (missing CLI/auth); a
bounded UNVERIFIED report is still written. Every other failure exits 1.
"""
from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import gzip
import hashlib
import json
import os
import stat
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time


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
MAX_CANDIDATE_ATTEMPTS = 2
MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
CAPTURE_LIMIT_EXIT_CODE = 86
# Devil's Advocate runs as a harness-orchestrated SECOND fresh session (S3,
# BACKLOG 2026-08-13): headless transports do not spawn Claude-native
# subagents (claude -p auth-blocked; codex has no subagent mechanism), so the
# real agent definition is executed in its own isolated session instead of
# being substituted with inline self-critique inside the blueprint session.
ADVOCATE_AGENT_RELPATH = "agents/devils-advocate.md"
ADVOCATE_ARTIFACT = "DEVILS_ADVOCATE_REVIEW.md"
ADVOCATE_MIN_BYTES = 400

CAPTURE_REDACTIONS = (
    (re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?"
        r"-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
     "[REDACTED-PRIVATE-KEY]"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
     "[REDACTED-AWS-KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
     "[REDACTED-GITHUB-TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
     "[REDACTED-SLACK-TOKEN]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
     "[REDACTED-GOOGLE-KEY]"),
    (re.compile(r"\b(?:sk-ant-|sk-)[A-Za-z0-9_-]{20,}\b"),
     "[REDACTED-API-KEY]"),
    (re.compile(
        r"(?i)\b(authorization\s*:\s*bearer\s+)"
        r"[A-Za-z0-9._-]{20,}"),
     r"\1[REDACTED]"),
    (re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
     "[REDACTED-EMAIL]"),
    (re.compile(
        r"(?i)([\"'](?:password|passwd|api[_-]?key|secret|token)"
        r"[\"']\s*:\s*[\"'])[^\"']{6,}([\"'])"),
     r"\1[REDACTED-SECRET]\2"),
    (re.compile(
        r"(?i)\b(password|passwd|api[_-]?key|secret|token)"
        r"\b(\s*[=:]\s*)[^\s\"'&]{6,}"),
     r"\1\2[REDACTED-SECRET]"),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sanitize_capture_text(text: str) -> tuple[str, int]:
    """Redact known secret/PII shapes before provider output is retained."""
    redactions = 0
    for pattern, replacement in CAPTURE_REDACTIONS:
        text, count = pattern.subn(replacement, text)
        redactions += count
    return text, redactions


def bounded_subprocess(
        command: list[str], *, cwd: Path, timeout_seconds: float,
        capture_limit_bytes: int, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Capture provider output concurrently with a hard aggregate byte ceiling."""
    if capture_limit_bytes <= 0 or capture_limit_bytes > MAX_TRANSCRIPT_BYTES:
        raise ValueError("capture limit must be inside the transcript budget")
    process = subprocess.Popen(
        command, cwd=cwd,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    lock = threading.Lock()
    overflow = threading.Event()

    def drain(label: str, stream) -> None:
        nonlocal total
        try:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    return
                should_kill = False
                with lock:
                    remaining = max(0, capture_limit_bytes - total)
                    accepted = chunk[:remaining]
                    buffers[label].extend(accepted)
                    total += len(accepted)
                    if len(chunk) > remaining:
                        overflow.set()
                        should_kill = True
                if should_kill:
                    try:
                        process.kill()
                    except OSError:
                        pass
        finally:
            stream.close()

    readers = [
        threading.Thread(
            target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(
            target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    if input_text is not None and process.stdin is not None:
        try:
            process.stdin.write(input_text.encode("utf-8"))
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            process.stdin.close()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    for reader in readers:
        reader.join()

    stdout, stdout_redactions = sanitize_capture_text(
        bytes(buffers["stdout"]).decode("utf-8", errors="replace"))
    stderr, stderr_redactions = sanitize_capture_text(
        bytes(buffers["stderr"]).decode("utf-8", errors="replace"))
    redaction_count = stdout_redactions + stderr_redactions
    sanitized_total_bytes = (
        len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
    )
    sanitized_overflow = sanitized_total_bytes > capture_limit_bytes
    if sanitized_overflow:
        overflow.set()
    if overflow.is_set():
        marker = b'{"type":"itd.capture_limit","status":"rejected"}\n'
        stdout_bytes = marker[:capture_limit_bytes]
        remaining = capture_limit_bytes - len(stdout_bytes)
        overflow_kind = (
            "sanitized provider output" if sanitized_overflow
            else "provider output"
        )
        diagnostic = (
            f"ITD capture limit exceeded by {overflow_kind} "
            f"({capture_limit_bytes} bytes); evidence rejected"
        ).encode("ascii")
        stdout = stdout_bytes.decode("ascii")
        stderr = diagnostic[:remaining].decode("ascii")
    if timed_out:
        timeout_error = subprocess.TimeoutExpired(
            command, timeout_seconds, output=stdout, stderr=stderr)
        timeout_error.itd_redaction_count = redaction_count
        timeout_error.itd_capture_limit_bytes = capture_limit_bytes
        timeout_error.itd_capture_limit_exceeded = overflow.is_set()
        raise timeout_error
    return_code = process.returncode
    if overflow.is_set():
        return_code = CAPTURE_LIMIT_EXIT_CODE
    completed = subprocess.CompletedProcess(
        command, return_code, stdout, stderr)
    completed.itd_redaction_count = redaction_count
    completed.itd_capture_limit_bytes = capture_limit_bytes
    completed.itd_capture_limit_exceeded = overflow.is_set()
    return completed


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


def git_ignored_relatives(relatives: list[str]) -> set[str]:
    """Repository-relative paths that Git ignores, resolved in one batch.

    The tree pin must digest the methodology, not harness debris that happens
    to sit inside it: a stray file under `skills/_shared/.claude/traces/` once
    entered the pin silently and only surfaced later, in an isolated staged
    candidate, as three failing checks. Git already knows which paths are
    debris, so the pin defers to it instead of maintaining a second, always
    incomplete, name-based denylist. A Git that cannot answer raises - a pin
    that silently widens on a broken Git is the exact failure mode being
    removed here. Tracked files are never reported by `check-ignore` unless
    `--no-index` is passed, so a tracked path matching an ignore rule stays in
    the pin.
    """
    if not relatives:
        return set()
    result = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"], cwd=ROOT,
        input="\0".join(relatives).encode("utf-8") + b"\0",
        capture_output=True, timeout=60,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            "git check-ignore failed while pinning the methodology tree: "
            + result.stderr.decode("utf-8", errors="replace").strip()[:200]
        )
    return {item for item in result.stdout.decode("utf-8").split("\0") if item}


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
    ignored = git_ignored_relatives(
        [path.relative_to(ROOT).as_posix() for path in files])
    files = [path for path in files
             if path.relative_to(ROOT).as_posix() not in ignored]
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
        "evidencePurpose": "workflow-output-quality",
        "independentReviewEvidence": False,
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


def parse_result_events_text(text: str, provider: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
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


def parse_result_events(stream: Path, provider: str) -> list[dict]:
    return parse_result_events_text(
        stream.read_text(encoding="utf-8", errors="strict"), provider)


def fixture_prompt(fixture_dir: Path) -> str:
    prompt = fixture_dir / "live-prompt.md"
    if not prompt.is_file():
        raise ValueError("fixture live-prompt.md is missing")
    text = prompt.read_text(encoding="utf-8", errors="strict").strip()
    if "$idea-to-deploy:blueprint" not in text:
        raise ValueError("live prompt does not explicitly invoke the ITD blueprint skill")
    return text


def missing_required_outputs(project: Path, required: list[str]) -> list[str]:
    """Return required outputs that are not regular files, preserving oracle order."""
    return [rel for rel in required if not (project / rel).is_file()]


def recovery_prompt(missing: list[str]) -> str:
    if not missing:
        raise ValueError("recovery requires at least one missing output")
    rendered = "\n".join(f"- `{rel}`" for rel in missing)
    return (
        "Continue `$idea-to-deploy:blueprint --full` in this same already-started "
        "repository. This is the single bounded recovery turn after a partial "
        "first pass.\n\n"
        "Inspect and preserve the valid documents already present. Do not delete "
        "or recreate existing required outputs. Read and follow "
        "`.itd-plugin/skills/blueprint/SKILL.md` and its directly required "
        "`.itd-plugin/skills/blueprint/references/document-templates.md`. "
        "Create and complete only these missing oracle-required files:\n"
        f"{rendered}\n\n"
        "Then verify the complete required set named in the original live prompt. "
        "Do not substitute README content or a chat summary for any missing file. "
        "Work autonomously; all blueprint confirmations remain pre-approved."
    )


def recovery_decision(project: Path, required: list[str],
                      completed_attempts: int) -> tuple[list[str], str | None]:
    """Return missing outputs and the next prompt, if the attempt bound permits it."""
    missing = missing_required_outputs(project, required)
    if not missing or completed_attempts >= MAX_CANDIDATE_ATTEMPTS:
        return missing, None
    return missing, recovery_prompt(missing)


def bounded_attempt_budget(total_budget: str, attempts: int) -> str:
    """Split an Anthropic cap so all possible attempts stay within the old total."""
    if attempts < 1:
        raise ValueError("attempt count must be positive")
    try:
        total = Decimal(total_budget)
    except InvalidOperation as exc:
        raise ValueError("budget must be a decimal number") from exc
    if not total.is_finite() or total <= 0:
        raise ValueError("budget must be positive and finite")
    share = (total / Decimal(attempts)).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN)
    if share <= 0:
        raise ValueError("budget is too small for bounded attempts")
    return format(share, ".2f")


def is_windows_bridge_from_wsl(provider: str, executable: str) -> bool:
    resolved_executable = Path(executable).resolve(strict=False)
    return (
        provider == "openai"
        and os.name == "posix"
        and resolved_executable.suffix.lower() == ".exe"
    )


def workspace_temp_parent(provider: str, executable: str,
                          configured_root: str | None = None) -> Path | None:
    """Select a temp root writable by the candidate host's own sandbox."""
    configured = (
        os.environ.get("ITD_LIVE_MODEL_TEMP_ROOT", "")
        if configured_root is None else configured_root
    )
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if not candidate.is_dir() or not os.access(candidate, os.W_OK):
            raise ValueError(
                f"configured live-model temp root is not writable: {candidate}")
        return candidate

    if not is_windows_bridge_from_wsl(provider, executable):
        return None
    candidate = Path("/mnt/c/tmp").resolve()
    if not candidate.is_dir() or not os.access(candidate, os.W_OK):
        raise ValueError(
            "Windows Codex bridge requires a host-writable temp root; "
            "create C:\\tmp or set ITD_LIVE_MODEL_TEMP_ROOT")
    return candidate


def candidate_workspace_path(provider: str, executable: str,
                             project: Path) -> str:
    """Translate a WSL mount path for a Windows candidate executable."""
    resolved = project.resolve(strict=False)
    if not is_windows_bridge_from_wsl(provider, executable):
        return resolved.as_posix()
    parts = resolved.parts
    if (len(parts) < 4 or parts[0] != "/" or parts[1] != "mnt"
            or len(parts[2]) != 1 or not parts[2].isalpha()):
        raise ValueError(
            f"Windows Codex bridge workspace is not a mounted drive path: {resolved}")
    drive = parts[2].upper()
    tail = "\\".join(parts[3:])
    return f"{drive}:\\{tail}"


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
                  plugin: Path, prompt: str, *, timeout_seconds: float,
                  attempt_budget: str,
                  candidate_project: str,
                  capture_limit_bytes: int
                  ) -> tuple[subprocess.CompletedProcess[str], str]:
    if args.resolved_provider == "anthropic":
        command = [
            executable, "-p", "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--model", args.model or "sonnet",
            "--dangerously-skip-permissions", "--plugin-dir", str(plugin),
            "--max-budget-usd", attempt_budget, prompt,
        ]
        completed = bounded_subprocess(
            command, cwd=project, timeout_seconds=timeout_seconds,
            capture_limit_bytes=capture_limit_bytes)
        return completed, "claude -p --plugin-dir <current-itd>"

    command = [
        executable, "--ask-for-approval", "never",
        "--sandbox", "workspace-write", "exec",
        "--json", "--ephemeral", "--ignore-user-config",
        "--config", 'model_reasoning_effort="medium"',
        "--skip-git-repo-check",
        "--disable", "hooks", "-C", candidate_project,
    ]
    if args.model:
        command.extend(["--model", args.model])
    command.append("-")
    completed = bounded_subprocess(
        command, cwd=project, timeout_seconds=timeout_seconds,
        capture_limit_bytes=capture_limit_bytes, input_text=prompt)
    return completed, "codex exec --json --ephemeral --repository-local-itd"


def fail(args: argparse.Namespace, reason: str, *, code: int = 1) -> int:
    status = "UNVERIFIED" if code == 3 else "FAIL"
    atomic_json(args.evidence, base_report(args, status, reason))
    print(f"{status}: {reason}")
    return code


def archive_failed_run(args: argparse.Namespace, fixture_dir: Path, output: Path,
                       required: list[str], transcript_raw: bytes,
                       attempts: list[dict], command_family: str,
                       reason: str, oracle: dict | None = None) -> int:
    """Retain bounded diagnostics for a real candidate failure."""
    transcript_text, archive_redactions = sanitize_capture_text(
        transcript_raw.decode("utf-8", errors="replace"))
    transcript_raw = transcript_text.encode("utf-8")
    if len(transcript_raw) > MAX_TRANSCRIPT_BYTES:
        transcript_raw = (
            b'{"type":"itd.capture_limit","status":"rejected"}\n')
    reason, reason_redactions = sanitize_capture_text(reason)
    redaction_count = (
        archive_redactions + reason_redactions
        + sum(int(item.get("transcriptRedactionCount", 0))
              for item in attempts)
    )
    transcript_hash = sha256_bytes(transcript_raw)
    run_id = (
        utc_now().replace("-", "").replace(":", "")
        + "-fail-" + transcript_hash[-8:]
    )
    evidence_root = args.evidence.parent.resolve()
    run_dir = evidence_root / "runs" / run_id
    archive_output = run_dir / "output"
    archive_output.mkdir(parents=True, exist_ok=False)
    present_hashes: dict[str, str] = {}
    for rel in required:
        source = output / rel
        if not source.is_file():
            continue
        target = archive_output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        present_hashes[rel] = sha256_file(target)
    transcript_archive = run_dir / "transcript.jsonl.gz"
    with gzip.open(transcript_archive, "wb", compresslevel=9) as handle:
        handle.write(transcript_raw)

    report = base_report(args, "FAIL", reason)
    report.update({
        "runId": run_id,
        "runReport": (run_dir / "run-report.json").relative_to(ROOT).as_posix(),
        "runArtifactDir": run_dir.relative_to(ROOT).as_posix(),
        "candidate": {
            "commandFamily": command_family,
            "exitCode": attempts[-1].get("exitCode") if attempts else None,
            "liveResultEvents": sum(
                item.get("liveResultEvents", 0) for item in attempts),
            "isError": any(item.get("isError") is True for item in attempts),
            "attemptCount": len(attempts),
            "recoveryTriggered": len(attempts) > 1,
            "attempts": attempts,
            "workspaceTransport": getattr(
                args, "workspace_transport", "unknown"),
            "approvalPolicy": "never-no-escalation",
            "hookPolicy": "disabled",
            "captureLimitBytes": MAX_TRANSCRIPT_BYTES,
            "transcriptBytes": len(transcript_raw),
            "transcriptSanitized": True,
            "transcriptRedactionCount": redaction_count,
            "transcriptSha256": transcript_hash,
            "transcriptArtifact": transcript_archive.relative_to(ROOT).as_posix(),
            "transcriptGzipSha256": sha256_file(transcript_archive),
        },
        "harnessInvocation": {
            "mode": "repository-local-adopted-project",
            "skill": "$idea-to-deploy:blueprint",
            "transcriptProvesSkillLoad": transcript_proves_harness(transcript_raw),
            "hookExecution": "disabled-for-live-model-evidence",
            "methodologyTreeSha256": methodology_tree_sha256(),
        },
        "failureArtifacts": {
            "outputDir": archive_output.relative_to(ROOT).as_posix(),
            "presentFiles": list(present_hashes),
            "missingRequiredFiles": missing_required_outputs(output, required),
            "sha256": present_hashes,
        },
        "sourcePins": source_pins(fixture_dir, args.resolved_provider),
    })
    if oracle is not None:
        report["independentVerdict"] = oracle
    atomic_json(run_dir / "run-report.json", report)
    atomic_json(args.evidence, report)
    print(f"FAIL: {reason} -> {run_id}")
    return 1


def _contained_existing(root: Path, raw: str, label: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{label} path is unsafe")
    target = (ROOT / candidate).resolve(strict=True)
    try:
        target.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"{label} escapes the evidence root") from exc
    return target


def reverify_failed_run(args: argparse.Namespace) -> int:
    """Rejudge immutable model output after a corrected deterministic oracle."""
    evidence_root = args.evidence.parent.resolve(strict=True)
    runs_root = (evidence_root / "runs").resolve(strict=True)
    source = args.reverify_failed_run.resolve(strict=True)
    if source.is_dir():
        source = (source / "run-report.json").resolve(strict=True)
    try:
        source.relative_to(runs_root)
    except ValueError as exc:
        raise ValueError("reverify source must stay inside the evidence runs root") from exc
    old = json.loads(source.read_text(encoding="utf-8"))
    if (
        not isinstance(old, dict)
        or old.get("status") != "FAIL"
        or old.get("fixture") != args.fixture
        or old.get("provider") not in {"openai", "anthropic"}
        or (old.get("independentVerdict") or {}).get("status") != "FAIL"
    ):
        raise ValueError("reverify source is not an oracle-rejected live run")
    args.resolved_provider = old["provider"]
    args.model = str(old.get("candidateModelRequested") or "")
    fixture_dir = ROOT / "tests" / "fixtures" / args.fixture
    snapshot = json.loads(
        (fixture_dir / "expected-snapshot.json").read_text(encoding="utf-8")
    )
    required = required_files(snapshot)
    failure = old.get("failureArtifacts") or {}
    old_output = _contained_existing(
        runs_root, str(failure.get("outputDir") or ""), "failed output"
    )
    hashes = failure.get("sha256")
    if (
        not isinstance(hashes, dict)
        or set(hashes) != set(required)
        or any(
            not (old_output / rel).is_file()
            or sha256_file(old_output / rel) != hashes[rel]
            for rel in required
        )
    ):
        raise ValueError("failed output set is incomplete or changed")
    candidate = old.get("candidate") or {}
    old_transcript = _contained_existing(
        runs_root, str(candidate.get("transcriptArtifact") or ""),
        "failed transcript",
    )
    if sha256_file(old_transcript) != candidate.get("transcriptGzipSha256"):
        raise ValueError("failed transcript archive changed")
    with gzip.open(old_transcript, "rb") as handle:
        transcript_raw = handle.read(MAX_TRANSCRIPT_BYTES + 1)
    if (
        len(transcript_raw) > MAX_TRANSCRIPT_BYTES
        or len(transcript_raw) != candidate.get("transcriptBytes")
        or sha256_bytes(transcript_raw) != candidate.get("transcriptSha256")
        or not transcript_proves_harness(transcript_raw)
    ):
        raise ValueError("failed transcript binding is invalid")
    oracle = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "verify_snapshot.py"),
         str(fixture_dir), "--output", str(old_output)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if oracle.returncode != 0:
        detail = (oracle.stdout + "\n" + oracle.stderr).strip().splitlines()
        raise ValueError(
            "corrected oracle still rejects archived output: "
            + " | ".join(detail[-4:])[:1200]
        )
    transcript_hash = sha256_bytes(transcript_raw)
    run_id = (
        utc_now().replace("-", "").replace(":", "")
        + "-reverified-" + transcript_hash[-8:]
    )
    run_dir = runs_root / run_id
    archive_output = run_dir / "output"
    archive_output.mkdir(parents=True, exist_ok=False)
    artifact_hashes: dict[str, str] = {}
    for rel in required:
        target = archive_output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_output / rel, target)
        artifact_hashes[rel] = sha256_file(target)
    transcript_archive = run_dir / "transcript.jsonl.gz"
    shutil.copy2(old_transcript, transcript_archive)
    report = base_report(
        args, "PASS",
        "archived live candidate passed the corrected deterministic oracle "
        "without another model invocation",
    )
    candidate = dict(candidate)
    candidate["transcriptArtifact"] = transcript_archive.relative_to(ROOT).as_posix()
    candidate["transcriptGzipSha256"] = sha256_file(transcript_archive)
    report.update({
        "runId": run_id,
        "runReport": (run_dir / "run-report.json").relative_to(ROOT).as_posix(),
        "runArtifactDir": run_dir.relative_to(ROOT).as_posix(),
        "candidate": candidate,
        "harnessInvocation": {
            "mode": "repository-local-adopted-project",
            "skill": "$idea-to-deploy:blueprint",
            "skillPath": ".itd-plugin/skills/blueprint/SKILL.md",
            "referencePath": ".itd-plugin/skills/blueprint/references/document-templates.md",
            "projectGuidance": "AGENTS.md",
            "projectContracts": ".itd/",
            "projectHooks": ".codex/hooks.json" if args.resolved_provider == "openai" else "plugin hooks/hooks.json",
            "transcriptProvesSkillLoad": True,
            "hookExecution": "disabled-for-live-model-evidence",
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
            "exitCode": 0,
            "status": "PASS",
            "candidateSelfReportAccepted": False,
        },
        "sourcePins": source_pins(fixture_dir, args.resolved_provider),
    })
    atomic_json(run_dir / "run-report.json", report)
    atomic_json(args.evidence, report)
    print(f"PASS reverified live-model: {args.fixture} -> {run_id}")
    return 0


def advocate_prompt(agent_definition: str) -> str:
    """Phase-2 prompt: the real Devil's Advocate agent definition is embedded
    VERBATIM, so the executed role is bound into the recorded prompt/transcript
    by construction rather than depending on the model reading a file."""
    return (
        "This is the Devil's Advocate phase of a non-interactive benchmark, "
        "running in a fresh session with no memory of the blueprint session. "
        "Adopt the following agent definition verbatim as your role — it is "
        f"the exact content of `{ADVOCATE_AGENT_RELPATH}`:\n\n"
        "----- BEGIN AGENT DEFINITION -----\n"
        f"{agent_definition}\n"
        "----- END AGENT DEFINITION -----\n\n"
        "The architectural proposal under review is the current project "
        "root's `PROJECT_ARCHITECTURE.md` (context: `STRATEGIC_PLAN.md`, "
        f"`PRD.md`). Write the complete adversarial review to "
        f"`{ADVOCATE_ARTIFACT}` in the project root, following the Debate "
        "Protocol sections above, including at least one "
        "`#### Challenge N: ...` heading whose body carries the protocol's "
        "`**Weakness:**`, `**Risk level:**`, `**Alternative:**` and "
        "`**Trade-off:**` fields. Do not modify any other file. Do not "
        "soften the review: the goal is rigorous stress-testing, not "
        "approval. Do not claim any other reviewer ran."
    )


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
        required = required_files(snapshot)
    except ValueError as exc:
        return fail(args, str(exc))
    try:
        attempt_budget = (
            bounded_attempt_budget(args.budget, MAX_CANDIDATE_ATTEMPTS)
            if args.resolved_provider == "anthropic" else args.budget
        )
        workspace_parent = workspace_temp_parent(
            args.resolved_provider, executable_or_reason)
    except ValueError as exc:
        return fail(args, str(exc))
    args.workspace_transport = (
        "host-mounted-temp" if workspace_parent is not None else "native-temp")

    with tempfile.TemporaryDirectory(
            prefix="itd-live-model-", dir=workspace_parent) as tmp:
        output, plugin = prepare_adopted_project(Path(tmp))
        try:
            candidate_project = candidate_workspace_path(
                args.resolved_provider, executable_or_reason, output)
        except ValueError as exc:
            return fail(args, str(exc))
        stream = output / ".run.stream.jsonl"
        deadline = time.monotonic() + args.timeout_seconds
        transcript_parts: list[bytes] = []
        results: list[dict] = []
        attempts: list[dict] = []
        candidate: subprocess.CompletedProcess[str] | None = None
        command_family = (
            "claude -p --plugin-dir <current-itd>"
            if args.resolved_provider == "anthropic"
            else "codex exec --json --ephemeral --repository-local-itd"
        )
        attempt_prompt = prompt

        def archive_current(reason: str, oracle: dict | None = None) -> int:
            return archive_failed_run(
                args, fixture_dir, output, required, b"".join(transcript_parts),
                attempts, command_family, reason, oracle)

        for attempt_number in range(1, MAX_CANDIDATE_ATTEMPTS + 1):
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                return archive_current(
                    f"live candidate exceeded shared {args.timeout_seconds}s timeout")
            remaining_capture_bytes = (
                MAX_TRANSCRIPT_BYTES
                - sum(len(part) for part in transcript_parts)
            )
            if remaining_capture_bytes <= 0:
                return archive_current(
                    "live candidate exhausted the transcript byte budget")
            missing_before = missing_required_outputs(output, required)
            try:
                candidate, command_family = run_candidate(
                    args, executable_or_reason, output, plugin, attempt_prompt,
                    timeout_seconds=remaining_seconds,
                    attempt_budget=attempt_budget,
                    candidate_project=candidate_project,
                    capture_limit_bytes=remaining_capture_bytes)
            except subprocess.TimeoutExpired as exc:
                partial = exc.stdout or b""
                raw_part = (
                    partial.encode("utf-8", errors="replace")
                    if isinstance(partial, str) else bytes(partial)
                )
                if (raw_part and not raw_part.endswith(b"\n")
                        and len(raw_part) < remaining_capture_bytes):
                    raw_part += b"\n"
                transcript_parts.append(raw_part)
                stream.write_bytes(b"".join(transcript_parts))
                attempt_results = parse_result_events_text(
                    raw_part.decode("utf-8", errors="replace"),
                    args.resolved_provider)
                attempts.append({
                    "attempt": attempt_number,
                    "exitCode": None,
                    "timedOut": True,
                    "missingBefore": missing_before,
                    "missingAfter": missing_required_outputs(output, required),
                    "liveResultEvents": len(attempt_results),
                    "isError": bool(
                        attempt_results
                        and attempt_results[-1].get("is_error")),
                    "captureLimitBytes": remaining_capture_bytes,
                    "transcriptRedactionCount": int(
                        getattr(exc, "itd_redaction_count", 0)),
                    "transcriptBytes": len(raw_part),
                    "transcriptSha256": sha256_bytes(raw_part),
                })
                return archive_current(
                    f"live candidate exceeded shared {args.timeout_seconds}s timeout")
            raw_part = candidate.stdout.encode("utf-8")
            if (raw_part and not raw_part.endswith(b"\n")
                    and len(raw_part) < remaining_capture_bytes):
                raw_part += b"\n"
            transcript_parts.append(raw_part)
            stream.write_bytes(b"".join(transcript_parts))
            attempt_results = parse_result_events_text(
                candidate.stdout, args.resolved_provider)
            missing_after = missing_required_outputs(output, required)
            attempts.append({
                "attempt": attempt_number,
                "exitCode": candidate.returncode,
                "timedOut": False,
                "missingBefore": missing_before,
                "missingAfter": missing_after,
                "liveResultEvents": len(attempt_results),
                "isError": bool(
                    attempt_results and attempt_results[-1].get("is_error")),
                "captureLimitBytes": remaining_capture_bytes,
                "transcriptRedactionCount": int(
                    getattr(candidate, "itd_redaction_count", 0)),
                "transcriptBytes": len(raw_part),
                "transcriptSha256": sha256_bytes(raw_part),
            })
            if candidate.returncode != 0:
                tail = (candidate.stdout + "\n" + candidate.stderr).strip().splitlines()[-1:]
                return archive_current(
                    "live candidate failed"
                    + (f": {tail[0]}" if tail else ""))
            if not attempt_results or (
                    args.resolved_provider == "anthropic"
                    and attempt_results[-1].get("is_error") is True):
                return archive_current(
                    "live transcript has no successful result event")
            results.extend(attempt_results)
            _, next_prompt = recovery_decision(
                output, required, attempt_number)
            if not missing_after:
                break
            if next_prompt is None:
                reason = (
                    "bounded recovery exhausted; required outputs are still missing: "
                    + ", ".join(missing_after)
                )
                return archive_current(reason)
            attempt_prompt = next_prompt

        if candidate is None or not stream.is_file():
            return archive_current("live candidate produced no stream transcript")
        transcript_raw = stream.read_bytes()
        if not transcript_proves_harness(transcript_raw):
            return archive_current(
                "live transcript does not prove ITD blueprint skill/reference loading")

        oracle_command = [
            sys.executable, str(ROOT / "tests" / "verify_snapshot.py"),
            str(fixture_dir), "--output", str(output),
        ]
        oracle = subprocess.run(
            oracle_command, cwd=ROOT, capture_output=True, text=True, timeout=180)
        if oracle.returncode != 0:
            detail = (oracle.stdout + "\n" + oracle.stderr).strip().splitlines()
            bounded = " | ".join(detail[-4:])[:1200]
            reason = (
                "independent snapshot oracle rejected live output"
                + (f": {bounded}" if bounded else "")
            )
            return archive_current(reason, {
                    "actor": "deterministic-external-oracle",
                    "oracle": "tests/verify_snapshot.py",
                    "exitCode": oracle.returncode,
                    "status": "FAIL",
                    "candidateSelfReportAccepted": False,
                })

        for rel in required:
            if not (output / rel).is_file():
                return archive_current(
                    f"oracle passed but required output is missing: {rel}")

        # Phase 2 — the real Devil's Advocate agent in a fresh isolated
        # session of the same transport (S3): the harness, not the blueprint
        # session, orchestrates the adversarial review.
        agent_source = plugin / "agents" / "devils-advocate.md"
        if not agent_source.is_file():
            return archive_current(
                "devils-advocate agent definition is missing from the plugin")
        advocate_file = output / ADVOCATE_ARTIFACT
        # The artifact must be CREATED by the fresh phase-2 session: a
        # blueprint session that pre-writes it (against the prompt) would let
        # a no-op advocate transport pass the post-phase checks on phase-1
        # content (reviewer finding, phase-one-14).
        if advocate_file.is_file() or advocate_file.is_symlink():
            return archive_current(
                "blueprint session pre-created the devils-advocate artifact")
        # Phase 2 has write access to the oracle-validated phase-1 workspace;
        # its prompt is untrusted, so immutability is proven by hashing the
        # COMPLETE workspace (not just the required artifacts) and allowing
        # exactly one addition afterwards (reviewer findings, phase-one-18/19).
        def workspace_snapshot() -> dict[str, str]:
            snapshot: dict[str, str] = {}
            for path in sorted(output.rglob("*")):
                rel = path.relative_to(output).as_posix()
                if rel == ".run.stream.jsonl":
                    continue  # harness-owned stream, appended between phases
                if path.is_symlink():
                    snapshot[rel] = "symlink:" + os.readlink(path)
                elif path.is_dir():
                    snapshot[rel] = "dir"
                elif path.is_file():
                    snapshot[rel] = sha256_file(path)
                else:
                    snapshot[rel] = "special"
            return snapshot

        phase1_snapshot = workspace_snapshot()
        advocate_remaining = deadline - time.monotonic()
        if advocate_remaining <= 0:
            return archive_current(
                "no time budget left for the devils-advocate phase")
        advocate_capture = (
            MAX_TRANSCRIPT_BYTES - sum(len(part) for part in transcript_parts))
        if advocate_capture <= 0:
            return archive_current(
                "no transcript byte budget left for the devils-advocate phase")
        try:
            advocate, _ = run_candidate(
                args, executable_or_reason, output, plugin,
                advocate_prompt(
                    agent_source.read_text(encoding="utf-8",
                                           errors="replace")),
                timeout_seconds=advocate_remaining,
                attempt_budget=attempt_budget,
                candidate_project=candidate_project,
                capture_limit_bytes=advocate_capture)
        except subprocess.TimeoutExpired:
            return archive_current(
                "devils-advocate phase exceeded the shared timeout")
        advocate_raw = advocate.stdout.encode("utf-8")
        if (advocate_raw and not advocate_raw.endswith(b"\n")
                and len(advocate_raw) < advocate_capture):
            advocate_raw += b"\n"
        transcript_parts.append(advocate_raw)
        stream.write_bytes(b"".join(transcript_parts))
        advocate_results = parse_result_events_text(
            advocate.stdout, args.resolved_provider)
        attempts.append({
            "attempt": len(attempts) + 1,
            "phase": "devils-advocate",
            "exitCode": advocate.returncode,
            "timedOut": False,
            "liveResultEvents": len(advocate_results),
            "isError": bool(
                advocate_results and advocate_results[-1].get("is_error")),
            "captureLimitBytes": advocate_capture,
            "transcriptRedactionCount": int(
                getattr(advocate, "itd_redaction_count", 0)),
            "transcriptBytes": len(advocate_raw),
            "transcriptSha256": sha256_bytes(advocate_raw),
        })
        if advocate.returncode != 0 or not advocate_results or (
                args.resolved_provider == "anthropic"
                and advocate_results[-1].get("is_error") is True):
            return archive_current(
                "devils-advocate phase did not complete successfully")
        # Advocate result events stay OUT of `results`: the candidate report
        # fields (exit/subtype/error) must keep describing the blueprint
        # invocation (reviewer finding, phase-one-18).
        phase2_snapshot = workspace_snapshot()
        expected_added = {ADVOCATE_ARTIFACT}
        added = set(phase2_snapshot) - set(phase1_snapshot)
        removed = set(phase1_snapshot) - set(phase2_snapshot)
        changed = {
            rel for rel in set(phase1_snapshot) & set(phase2_snapshot)
            if phase1_snapshot[rel] != phase2_snapshot[rel]}
        if added != expected_added or removed or changed:
            return archive_current(
                "devils-advocate phase mutated the workspace beyond its "
                f"artifact (added={sorted(added - expected_added)} "
                f"removed={sorted(removed)} changed={sorted(changed)})")
        # Re-check with lstat AFTER the untrusted phase-2 session: reading or
        # archiving through a symlink would hash-bind a foreign target as the
        # review (reviewer finding, phase-one-17).
        try:
            advocate_stat = os.lstat(advocate_file)
        except OSError:
            advocate_stat = None
        advocate_regular = (
            advocate_stat is not None and stat.S_ISREG(advocate_stat.st_mode))
        advocate_text = (
            advocate_file.read_text(encoding="utf-8", errors="replace")
            if advocate_regular else "")
        if (len(advocate_text.encode("utf-8")) < ADVOCATE_MIN_BYTES
                or not re.search(r"^####\s+Challenge\s+\d+:", advocate_text,
                                 re.MULTILINE)
                or "**Weakness:**" not in advocate_text
                or "**Risk level:**" not in advocate_text
                or "**Alternative:**" not in advocate_text
                or "**Trade-off:**" not in advocate_text):
            return archive_current(
                "devils-advocate phase produced no substantive review artifact")

        transcript_raw = stream.read_bytes()
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
        advocate_target = archive_output / ADVOCATE_ARTIFACT
        shutil.copy2(advocate_file, advocate_target)
        artifact_hashes[ADVOCATE_ARTIFACT] = sha256_file(advocate_target)
        transcript_archive = run_dir / "transcript.jsonl.gz"
        with gzip.open(transcript_archive, "wb", compresslevel=9) as handle:
            handle.write(transcript_raw)

        last = results[-1]
        durations = [
            row.get("duration_ms") for row in results
            if isinstance(row.get("duration_ms"), (int, float))
        ]
        costs = [
            row.get("total_cost_usd") for row in results
            if isinstance(row.get("total_cost_usd"), (int, float))
        ]
        reason = (
            # Recovery means a real blueprint retry; the devils-advocate
            # phase entry in attempts[] is transcript coverage, not a retry,
            # and must not make the reason claim a recovery that
            # recoveryTriggered correctly denies.
            "live candidate passed independent snapshot oracle after bounded recovery"
            if len([item for item in attempts
                    if item.get("phase") != "devils-advocate"]) > 1
            else "live candidate passed independent snapshot oracle"
        )
        report = base_report(args, "PASS", reason)
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
                "durationMs": sum(durations) if durations else None,
                "totalCostUsd": sum(costs) if costs else None,
                # attemptCount keeps its historical meaning (blueprint
                # attempts); the devils-advocate phase entry stays in
                # attempts[] only for exact transcript segment coverage.
                "attemptCount": len([
                    item for item in attempts
                    if item.get("phase") != "devils-advocate"]),
                "recoveryTriggered": len([
                    item for item in attempts
                    if item.get("phase") != "devils-advocate"]) > 1,
                "attempts": attempts,
                "workspaceTransport": args.workspace_transport,
                "approvalPolicy": "never-no-escalation",
                "hookPolicy": "disabled",
                "captureLimitBytes": MAX_TRANSCRIPT_BYTES,
                "transcriptBytes": len(transcript_raw),
                "transcriptSanitized": True,
                "transcriptRedactionCount": sum(
                    int(item.get("transcriptRedactionCount", 0))
                    for item in attempts),
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
                "hookExecution": "disabled-for-live-model-evidence",
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
            "devilsAdvocate": {
                "mode": "harness-orchestrated-fresh-session",
                "agentPath": ADVOCATE_AGENT_RELPATH,
                "agentSha256": sha256_file(agent_source),
                "artifact": ADVOCATE_ARTIFACT,
                "artifactSha256": artifact_hashes[ADVOCATE_ARTIFACT],
                "artifactBytes": len(advocate_text.encode("utf-8")),
                "exitCode": advocate.returncode,
                "resultSubtype": advocate_results[-1].get("subtype"),
                "isError": bool(advocate_results[-1].get("is_error")),
                "liveResultEvents": len(advocate_results),
                "phase1ArtifactsUnchanged": True,
                "sessionIsolation": (
                    "claude -p --no-session-persistence"
                    if args.resolved_provider == "anthropic"
                    else "codex exec --ephemeral"),
                "inlineSelfCritiqueSubstitution": False,
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
    parser.add_argument("--reverify-failed-run", type=Path)
    args = parser.parse_args()
    args.resolved_provider = args.provider
    args.evidence = args.evidence.resolve()
    if args.timeout_seconds < 60 or args.timeout_seconds > 3600:
        parser.error("--timeout-seconds must be within 60..3600")
    if args.reverify_failed_run is not None:
        try:
            return reverify_failed_run(args)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            print(f"UNVERIFIED: {exc}", file=sys.stderr)
            return 3
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
