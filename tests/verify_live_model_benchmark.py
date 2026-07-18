#!/usr/bin/env python3
"""Fail-closed verifier for the scheduled, externally judged H4 benchmark."""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import io
import json
from decimal import Decimal
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "tests" / "fixtures" / "live-model-evidence" / "latest.json"
passed = failed = 0
METHODOLOGY_TREE_ROOTS = (
    "AGENTS.md", ".codex-plugin", ".claude-plugin", "skills", "agents", "hooks",
    "docs/templates/itd", "docs/templates/itd-memory",
    "docs/HOST_ADAPTER_CONTRACT.md", "docs/host-adapters.json",
)
GENERATED_STATUS_PREFIXES = ("tests/fixtures/live-model-evidence/",)


def load_live_runner():
    path = ROOT / "tests" / "run-live-model-benchmark.py"
    spec = importlib.util.spec_from_file_location("itd_live_model_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load live-model benchmark runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f" [{detail[:240]}]" if detail and not condition else ""))
    if condition:
        passed += 1
    else:
        failed += 1


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def transcript_result_events(raw: bytes, provider: str) -> list[dict]:
    rows: list[dict] = []
    terminal_type = "result" if provider == "anthropic" else "turn.completed"
    for line in raw.decode("utf-8", errors="strict").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("type") == terminal_type:
            rows.append(row)
    return rows


def stable_git_status(raw: bytes) -> bytes:
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


def methodology_tree_sha256() -> str:
    files: list[Path] = []
    for raw in METHODOLOGY_TREE_ROOTS:
        path = ROOT / raw
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*")
                         if candidate.is_file() and "__pycache__" not in candidate.parts
                         and candidate.suffix != ".pyc")
    digest = hashlib.sha256()
    for path in sorted(set(files), key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def parse_time(raw: str) -> dt.datetime:
    value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return value.astimezone(dt.timezone.utc)


def status_passes(report: dict) -> bool:
    return report.get("status") == "PASS"


def independent_verdict_passes(report: dict) -> bool:
    verdict = report.get("independentVerdict") or {}
    return (verdict.get("actor") == "deterministic-external-oracle"
            and verdict.get("candidateSelfReportAccepted") is False
            and verdict.get("oracle") == "tests/verify_snapshot.py"
            and verdict.get("exitCode") == 0
            and verdict.get("status") == "PASS")


def workflow_enabled(text: str) -> bool:
    return re.search(r"\bif\s*:\s*false\b", text, re.I) is None


def inside(root: Path, raw: str) -> Path | None:
    candidate = Path(str(raw or ""))
    if not raw or candidate.is_absolute() or ".." in candidate.parts:
        return None
    target = (ROOT / candidate).resolve(strict=False)
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target


def inside_base(base: Path, raw: str) -> Path | None:
    candidate = Path(str(raw or ""))
    if not raw or candidate.is_absolute() or ".." in candidate.parts:
        return None
    target = (base / candidate).resolve(strict=False)
    try:
        target.relative_to(base.resolve())
    except ValueError:
        return None
    return target


def source_pin_paths(fixture: str, provider: str) -> dict[str, Path]:
    fixture_dir = ROOT / "tests" / "fixtures" / fixture
    return {
        "benchmarkRunner": ROOT / "tests" / "run-live-model-benchmark.py",
        "candidateAdapter": ROOT / "tests" / "run-live-model-benchmark.py",
        "oracle": ROOT / "tests" / "verify_snapshot.py",
        "fixturePrompt": fixture_dir / "live-prompt.md",
        "fixtureContract": fixture_dir / "expected-snapshot.json",
        "codexAdapterTemplate": ROOT / "skills" / "adopt" / "references" / "codex-project-hooks.json",
        "agentsTemplate": ROOT / "skills" / "adopt" / "references" / "agents-md-template.md",
    }


def verify_evidence(path: Path, max_age_days: int) -> None:
    evidence_root = (ROOT / "tests" / "fixtures" / "live-model-evidence").resolve()
    check("live evidence artifact exists", path.is_file())
    if not path.is_file():
        return
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        check("live evidence is valid JSON", False, str(exc))
        return
    check("live evidence schema is v1", report.get("schemaVersion") == 1)
    check("only a real PASS can satisfy H4", status_passes(report),
          str(report.get("status")))
    if not status_passes(report):
        return
    check("candidate provider is external", report.get("provider") in {"anthropic", "openai"})
    check("candidate command is a live headless model",
          any(marker in str((report.get("candidate") or {}).get("commandFamily"))
              for marker in ("claude -p", "codex exec")))
    source_state = report.get("source") or {}
    status_bytes = git_status_bytes()
    current_tree = methodology_tree_sha256()
    check("current methodology tree is content-pinned",
          source_state.get("methodologyTreeSha256") == current_tree)
    check("dirty-state digest is pinned",
          source_state.get("workingTreeStatusSha256") ==
          "sha256:" + hashlib.sha256(status_bytes).hexdigest()
          and source_state.get("workingTreeDirty") is bool(status_bytes.strip()))
    try:
        observed = parse_time(str(report.get("observedAt") or ""))
        frozen = parse_time(json.loads((ROOT / "docs" / "HARNESS_CONFORMANCE_CONTRACT.json").read_text())
                            ["frozenAt"])
        age = dt.datetime.now(dt.timezone.utc) - observed
        check("live evidence is fresh", dt.timedelta(0) <= age <= dt.timedelta(days=max_age_days),
              str(age))
        check("live evidence postdates the frozen oracle", observed >= frozen)
    except Exception as exc:
        check("live evidence timestamp is valid", False, str(exc))

    run_report = inside(evidence_root, str(report.get("runReport") or ""))
    check("run report path stays inside evidence root",
          run_report is not None and run_report.is_file())
    if run_report and run_report.is_file():
        try:
            check("latest evidence exactly matches immutable run report",
                  json.loads(run_report.read_text(encoding="utf-8")) == report)
        except Exception as exc:
            check("run report is valid JSON", False, str(exc))

    candidate = report.get("candidate") or {}
    check("live candidate exited zero", candidate.get("exitCode") == 0)
    check("live transcript contains a result event",
          type(candidate.get("liveResultEvents")) is int and candidate.get("liveResultEvents", 0) >= 1)
    check("live result is not an error", candidate.get("isError") is False)
    attempts = candidate.get("attempts") or []
    attempt_count = candidate.get("attemptCount")
    check("live candidate attempt count stays within bounded policy",
          attempt_count in {1, 2} and len(attempts) == attempt_count)
    check("live candidate recovery flag matches attempt count",
          candidate.get("recoveryTriggered") is (attempt_count == 2))
    check("live candidate records its writable workspace transport",
          candidate.get("workspaceTransport")
          in {"native-temp", "host-mounted-temp"})
    check("live candidate used a no-escalation approval policy",
          candidate.get("approvalPolicy") == "never-no-escalation")
    check("all recorded live attempts exited zero",
          bool(attempts)
          and all(item.get("exitCode") == 0
                  and type(item.get("liveResultEvents")) is int
                  and item.get("liveResultEvents", 0) >= 1
                  and item.get("isError") is False
                  for item in attempts))
    check("final live attempt completed the required output set",
          bool(attempts) and attempts[-1].get("missingAfter") == [])
    if attempt_count == 2 and len(attempts) == 2:
        check("recovery continued exactly the first attempt's missing outputs",
              bool(attempts[0].get("missingAfter"))
              and attempts[1].get("missingBefore") == attempts[0].get("missingAfter"))
    transcript = inside(evidence_root, str(candidate.get("transcriptArtifact") or ""))
    check("compressed raw transcript is retained", transcript is not None and transcript.is_file())
    if transcript and transcript.is_file():
        check("compressed transcript hash is pinned",
              sha256_file(transcript) == candidate.get("transcriptGzipSha256"))
        try:
            raw = gzip.decompress(transcript.read_bytes())
            check("raw transcript hash is pinned",
                  "sha256:" + hashlib.sha256(raw).hexdigest() == candidate.get("transcriptSha256"))
            provider = str(report.get("provider") or "")
            rows = transcript_result_events(raw, provider)
            check("retained transcript proves successful live result",
                  bool(rows) and (provider != "anthropic"
                                  or rows[-1].get("is_error") is not True))
            cursor = 0
            segments_valid = bool(attempts)
            for index, attempt in enumerate(attempts, start=1):
                length = attempt.get("transcriptBytes")
                if type(length) is not int or length <= 0 or cursor + length > len(raw):
                    check(f"attempt {index} transcript boundary is valid", False)
                    segments_valid = False
                    break
                segment = raw[cursor:cursor + length]
                cursor += length
                segment_rows = transcript_result_events(segment, provider)
                check(f"attempt {index} transcript segment hash is pinned",
                      "sha256:" + hashlib.sha256(segment).hexdigest()
                      == attempt.get("transcriptSha256"))
                check(f"attempt {index} transcript proves successful terminal event",
                      len(segment_rows) == attempt.get("liveResultEvents")
                      and bool(segment_rows)
                      and (provider != "anthropic"
                           or segment_rows[-1].get("is_error") is not True))
            check("attempt transcript segments exactly cover retained transcript",
                  segments_valid and cursor == len(raw))
            transcript_text = raw.decode("utf-8", errors="replace")
            check("retained transcript proves actual ITD skill and reference loading",
                  "skills/blueprint/SKILL.md" in transcript_text
                  and "skills/blueprint/references/document-templates.md" in transcript_text)
        except Exception as exc:
            check("retained transcript is readable", False, str(exc))

    check("verdict is independent of candidate self-report",
          independent_verdict_passes(report))
    verdict = report.get("independentVerdict") or {}
    check("independent snapshot oracle passed",
          verdict.get("oracle") == "tests/verify_snapshot.py"
          and verdict.get("exitCode") == 0 and verdict.get("status") == "PASS")

    invocation = report.get("harnessInvocation") or {}
    check("live run used the repository-local adopted ITD harness",
          invocation.get("mode") == "repository-local-adopted-project"
          and invocation.get("skill") == "$idea-to-deploy:blueprint"
          and invocation.get("skillPath") == ".itd-plugin/skills/blueprint/SKILL.md"
          and invocation.get("referencePath") ==
          ".itd-plugin/skills/blueprint/references/document-templates.md"
          and invocation.get("projectGuidance") == "AGENTS.md"
          and invocation.get("projectContracts") == ".itd/"
          and invocation.get("transcriptProvesSkillLoad") is True
          and invocation.get("methodologyTreeSha256") == current_tree)

    artifacts = report.get("artifacts") or {}
    output_dir = inside(evidence_root, str(artifacts.get("outputDir") or ""))
    hashes = artifacts.get("sha256") or {}
    required = artifacts.get("requiredFiles") or []
    check("archived output is bounded and replayable",
          output_dir is not None and output_dir.is_dir()
          and isinstance(required, list) and bool(required)
          and isinstance(hashes, dict) and set(required) == set(hashes))
    if output_dir and output_dir.is_dir() and isinstance(hashes, dict):
        for rel, expected in hashes.items():
            target = inside_base(output_dir, str(rel))
            check(f"archived artifact hash matches: {rel}",
                  target is not None and target.is_file() and sha256_file(target) == expected)
        fixture_dir = ROOT / "tests" / "fixtures" / str(report.get("fixture") or "")
        oracle = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "verify_snapshot.py"),
             str(fixture_dir), "--output", str(output_dir)],
            cwd=ROOT, capture_output=True, text=True, timeout=180)
        check("independent verdict replays from archived artifacts",
              oracle.returncode == 0, oracle.stdout + oracle.stderr)

    pins = report.get("sourcePins") or {}
    expected_paths = source_pin_paths(str(report.get("fixture") or ""),
                                      str(report.get("provider") or ""))
    check("all benchmark/oracle/methodology inputs are source-pinned",
          set(pins) == set(expected_paths) | {"methodologyTree"})
    for name, source in expected_paths.items():
        check(f"source pin matches: {name}", source.is_file() and pins.get(name) == sha256_file(source))
    check("source pin matches: methodologyTree", pins.get("methodologyTree") == current_tree)

    # Anti-false-green mutations exercise the same predicates and retained
    # bytes used above. None may be accepted as equivalent evidence.
    mutated = copy.deepcopy(report)
    mutated["status"] = "UNVERIFIED"
    check("mutation: UNVERIFIED cannot satisfy H4", not status_passes(mutated))
    mutated = copy.deepcopy(report)
    mutated["independentVerdict"]["candidateSelfReportAccepted"] = True
    check("mutation: candidate self-verdict is rejected",
          not independent_verdict_passes(mutated))
    mutated = copy.deepcopy(report)
    mutated["harnessInvocation"]["transcriptProvesSkillLoad"] = False
    check("mutation: generic-model run cannot claim harness invocation",
          mutated["harnessInvocation"].get("transcriptProvesSkillLoad") is not True)
    mutated = copy.deepcopy(report)
    mutated["sourcePins"]["methodologyTree"] = "sha256:" + "0" * 64
    check("mutation: methodology-tree pin tampering is rejected",
          mutated["sourcePins"].get("methodologyTree") != current_tree)
    try:
        stale = parse_time(str(report["observedAt"])) - dt.timedelta(days=max_age_days + 1)
        age = dt.datetime.now(dt.timezone.utc) - stale
        check("mutation: stale external evidence is rejected",
              age > dt.timedelta(days=max_age_days))
    except Exception:
        check("mutation: stale external evidence is rejected", False)
    if transcript and transcript.is_file():
        mutated_hash = "sha256:" + "0" * 64
        check("mutation: transcript hash tampering is rejected",
              sha256_file(transcript) != mutated_hash)
    if output_dir and output_dir.is_dir() and isinstance(hashes, dict) and hashes:
        rel = next(iter(hashes))
        target = inside_base(output_dir, str(rel))
        check("mutation: output hash tampering is rejected",
              target is not None and target.is_file()
              and sha256_file(target) != "sha256:" + "0" * 64)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-evidence", action="store_true")
    parser.add_argument("--max-age-days", type=int, default=30)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    workflow = (ROOT / ".github" / "workflows" / "fixture-smoke.yml").read_text(encoding="utf-8")
    check("live workflow has no permanent-disable guard",
          workflow_enabled(workflow))
    check("mutation: permanent-disable guard is rejected",
          not workflow_enabled(workflow + "\nif: false\n"))
    check("live workflow is regular and manually runnable",
          "schedule:" in workflow and "workflow_dispatch:" in workflow)
    check("live workflow invokes canonical benchmark runner",
          "tests/run-live-model-benchmark.py" in workflow)
    check("workflow uploads evidence even on failure",
          "if: always()" in workflow and "live-model-evidence" in workflow)
    runner = (ROOT / "tests" / "run-live-model-benchmark.py").read_text(encoding="utf-8")
    runner_module = load_live_runner()
    max_attempts = getattr(runner_module, "MAX_CANDIDATE_ATTEMPTS", None)
    check("live candidate recovery is bounded to exactly two attempts",
          max_attempts == 2)
    check("mutation: one-shot candidate policy is rejected",
          max_attempts == 2 and max_attempts != 1)
    missing_outputs = getattr(runner_module, "missing_required_outputs", None)
    recovery_decision = getattr(runner_module, "recovery_decision", None)
    bounded_budget = getattr(runner_module, "bounded_attempt_budget", None)
    workspace_parent_for = getattr(
        runner_module, "workspace_temp_parent", None)
    candidate_path_for = getattr(
        runner_module, "candidate_workspace_path", None)
    with tempfile.TemporaryDirectory(prefix="itd-live-verifier-") as tmp:
        project = Path(tmp)
        required_for_recovery = [
            "STRATEGIC_PLAN.md", "PRD.md", "IMPLEMENTATION_PLAN.md",
        ]
        (project / "STRATEGIC_PLAN.md").write_text("existing\n", encoding="utf-8")
        detected = (
            missing_outputs(project, required_for_recovery)
            if callable(missing_outputs) else None
        )
        check("bounded recovery detects only missing outputs",
              detected == ["PRD.md", "IMPLEMENTATION_PLAN.md"])
        first_decision = (
            recovery_decision(project, required_for_recovery, 1)
            if callable(recovery_decision) else (None, None)
        )
        first_missing, first_prompt = first_decision
        check("partial first result schedules same-project continuation",
              first_missing == ["PRD.md", "IMPLEMENTATION_PLAN.md"]
              and isinstance(first_prompt, str)
              and "same already-started repository" in first_prompt
              and "`PRD.md`" in first_prompt
              and "`IMPLEMENTATION_PLAN.md`" in first_prompt
              and "`STRATEGIC_PLAN.md`" not in first_prompt)
        second_decision = (
            recovery_decision(project, required_for_recovery, 2)
            if callable(recovery_decision) else (None, "unexpected")
        )
        check("bounded recovery cannot schedule a third attempt",
              second_decision == (["PRD.md", "IMPLEMENTATION_PLAN.md"], None))
    try:
        per_attempt = (
            Decimal(bounded_budget("5.00", 2))
            if callable(bounded_budget) else Decimal("NaN")
        )
        budget_is_bounded = per_attempt > 0 and per_attempt * 2 <= Decimal("5.00")
    except Exception:
        budget_is_bounded = False
    check("Anthropic budget is bounded across candidate attempts",
          budget_is_bounded)
    workspace_transport_ok = False
    try:
        with tempfile.TemporaryDirectory(prefix="itd-live-host-temp-") as host_tmp:
            host_root = Path(host_tmp).resolve()
            windows_parent = (
                workspace_parent_for(
                    "openai", "/mnt/c/tools/codex.exe",
                    configured_root=str(host_root))
                if callable(workspace_parent_for) else None
            )
            native_parent = (
                workspace_parent_for(
                    "openai", "/usr/bin/codex", configured_root="")
                if callable(workspace_parent_for) else host_root
            )
            workspace_transport_ok = (
                windows_parent == host_root and native_parent is None
            )
    except Exception:
        workspace_transport_ok = False
    check("Windows Codex bridge uses a host-writable temp root",
          workspace_transport_ok)
    candidate_path_ok = False
    try:
        candidate_path_ok = (
            callable(candidate_path_for)
            and candidate_path_for(
                "openai", "/mnt/c/tools/codex.exe",
                Path("/mnt/c/tmp/itd-live-model-123/project"))
            == "C:\\tmp\\itd-live-model-123\\project"
            and candidate_path_for(
                "openai", "/usr/bin/codex",
                Path("/tmp/itd-live-model-123/project"))
            == "/tmp/itd-live-model-123/project"
        )
    except Exception:
        candidate_path_ok = False
    check("Windows Codex bridge receives a native Windows -C path",
          candidate_path_ok)
    check("runner creates the adopted project under the selected host temp root",
          "dir=workspace_parent" in runner)
    check("candidate command uses the translated workspace path",
          '"-C", candidate_project' in runner)
    check("headless Codex uses explicit no-escalation workspace-write policy",
          'executable, "--ask-for-approval", "never",' in runner
          and '"--sandbox", "workspace-write", "exec",' in runner)
    check("candidate attempts share one total timeout deadline",
          "deadline = time.monotonic() + args.timeout_seconds" in runner
          and "remaining_seconds = deadline - time.monotonic()" in runner)
    check("runner executes the explicit bounded recovery loop",
          "for attempt_number in range(1, MAX_CANDIDATE_ATTEMPTS + 1)" in runner)
    candidate_region = runner[
        runner.index("        def archive_current("):
        runner.index("        transcript_hash = sha256_bytes(transcript_raw)")
    ]
    candidate_failures_archive = (
        "def archive_failed_run(" in runner
        and '"failureArtifacts": {' in runner
        and "transcript.jsonl.gz" in runner
        and candidate_region.count("return archive_current(") >= 7
        and "return fail(" not in candidate_region
    )
    check("all real candidate failures retain bounded diagnostic evidence",
          candidate_failures_archive)
    mutated_candidate_region = candidate_region.replace(
        "return archive_current(", "return fail(", 1)
    check("mutation: minimal real-candidate FAIL bypass is rejected",
          candidate_failures_archive
          and "return fail(" in mutated_candidate_region)
    fixture_dir = ROOT / "tests" / "fixtures" / "fixture-03-cli-tool"
    diagnostic_ok = False
    try:
        evidence_parent = ROOT / "tests" / "fixtures" / "live-model-evidence"
        with tempfile.TemporaryDirectory(
                dir=evidence_parent, prefix=".diagnostic-selftest-") as evidence_tmp:
            with tempfile.TemporaryDirectory(prefix="itd-live-failure-output-") as output_tmp:
                output = Path(output_tmp)
                (output / "PRD.md").write_text("partial\n", encoding="utf-8")
                raw = b'{"type":"turn.completed"}\n'
                attempt = {
                    "attempt": 1,
                    "exitCode": 0,
                    "missingBefore": ["PRD.md", "IMPLEMENTATION_PLAN.md"],
                    "missingAfter": ["IMPLEMENTATION_PLAN.md"],
                    "liveResultEvents": 1,
                    "isError": False,
                    "transcriptBytes": len(raw),
                    "transcriptSha256": runner_module.sha256_bytes(raw),
                }
                diagnostic_args = argparse.Namespace(
                    evidence=Path(evidence_tmp) / "latest.json",
                    resolved_provider="openai",
                    provider="openai",
                    fixture="fixture-03-cli-tool",
                    model="",
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    code = runner_module.archive_failed_run(
                        diagnostic_args, fixture_dir, output,
                        ["PRD.md", "IMPLEMENTATION_PLAN.md"], raw, [attempt],
                        "codex exec test", "synthetic bounded failure")
                diagnostic = json.loads(
                    diagnostic_args.evidence.read_text(encoding="utf-8"))
                transcript_artifact = ROOT / diagnostic["candidate"]["transcriptArtifact"]
                diagnostic_ok = (
                    code == 1
                    and diagnostic.get("status") == "FAIL"
                    and diagnostic["failureArtifacts"]["presentFiles"] == ["PRD.md"]
                    and diagnostic["failureArtifacts"]["missingRequiredFiles"]
                    == ["IMPLEMENTATION_PLAN.md"]
                    and transcript_artifact.is_file()
                    and gzip.decompress(transcript_artifact.read_bytes()) == raw
                )
    except Exception:
        diagnostic_ok = False
    check("synthetic candidate failure is archived and replayable",
          diagnostic_ok)
    live_prompt = (fixture_dir / "live-prompt.md").read_text(encoding="utf-8")
    snapshot = json.loads((fixture_dir / "expected-snapshot.json").read_text(encoding="utf-8"))
    required_outputs = ((snapshot.get("files") or {}).get("required") or [])
    prompt_names_all_outputs = (
        bool(required_outputs)
        and all(f"`{name}`" in live_prompt for name in required_outputs)
    )
    check("live prompt explicitly names every oracle-required output",
          prompt_names_all_outputs)
    mutated_prompt = (
        live_prompt.replace(f"`{required_outputs[0]}`", "", 1)
        if required_outputs else live_prompt
    )
    check("mutation: omitted prompt output fails closed",
          bool(required_outputs)
          and not all(f"`{name}`" in mutated_prompt for name in required_outputs))
    check("missing external auth is explicit UNVERIFIED, never PASS",
          'status = "UNVERIFIED" if code == 3 else "FAIL"' in runner
          and "code=3" in runner and "resolve_provider(args)" in runner)
    check("candidate output is judged by snapshot oracle", "verify_snapshot.py" in runner)
    synthetic_status = (
        b" M hooks/completion-gate.sh\n"
        b"?? tests/fixtures/live-model-evidence/runs/generated/report.json\n"
        b"R  hooks/completion-gate.sh -> "
        b"tests/fixtures/live-model-evidence/completion-gate.sh\n"
        b" M tests/unit/tests/fixtures/live-model-evidence/parser.py\n")
    expected_stable_status = (
        b" M hooks/completion-gate.sh\n"
        b"R  hooks/completion-gate.sh -> "
        b"tests/fixtures/live-model-evidence/completion-gate.sh\n"
        b" M tests/unit/tests/fixtures/live-model-evidence/parser.py\n")
    check("generated live evidence cannot invalidate its own dirty-state pin",
          stable_git_status(synthetic_status)
          == expected_stable_status)
    if args.require_evidence:
        verify_evidence(args.evidence.resolve(), args.max_age_days)
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
