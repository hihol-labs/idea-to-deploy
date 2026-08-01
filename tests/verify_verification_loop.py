#!/usr/bin/env python3
"""Behavioural/adversarial oracle for Verification Loop v1."""
from __future__ import annotations

import importlib.util
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
POLICY = ROOT / "skills" / "_shared" / "VERIFICATION_LOOP_POLICY.json"
PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"PASS  {name}")
    else:
        FAILED += 1
        print(f"FAIL  {name}: {detail}")


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd,
                          text=True, capture_output=True, encoding="utf-8",
                          errors="replace", env=env, timeout=30)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True,
                   text=True, capture_output=True)


def fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="verification-loop-"))
    git(root, "init", "-q")
    git(root, "config", "user.name", "Verification Loop")
    git(root, "config", "user.email", "loop@example.test")
    (root / ".gitignore").write_text(".itd-memory/\n", encoding="utf-8")
    (root / ".itd").mkdir()
    (root / ".itd" / "SCOPE_LOCK.md").write_text("# Scope\n", encoding="utf-8")
    (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
        '{"criteria":[{"id":"AC-1","status":"pending"}]}\n', encoding="utf-8")
    (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "baseline")
    (root / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    git(root, "add", "app.py")
    return root


def last_path(proc: subprocess.CompletedProcess[str]) -> Path:
    return Path(proc.stdout.strip().splitlines()[-1])


def artifacts(root: Path, verdict: str = "PASSED") -> tuple[Path, Path]:
    base = root / ".itd-memory" / "verification-loop"
    prompt = base / "prompts" / "U-loop.md"
    report = base / "reports" / "U-loop.md"
    prompt.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text("Review exact candidate; do not inherit maker reasoning.\n", encoding="utf-8")
    report.write_text(
        "# Review\n\n```json\n" + json.dumps({
            "verdict": verdict, "findings": [], "unverified": []
        }) + "\n```\n", encoding="utf-8")
    return prompt, report


def machine(root: Path, risk: str, command: str | None = None,
            inputs: list[str] | None = None):
    oracle = command or f'"{sys.executable}" -c "print(123)"'
    args = ["machine", "--root", str(root), "--unit-id", "U-loop",
            "--risk-tier", risk, "--command", "oracle=" + oracle,
            "--timeout", "10"]
    for path in inputs or []:
        args += ["--input", path]
    return run(args, root)


def checker(root: Path, risk: str, mode: str, *, same_session: bool = False,
            same_model: bool = False, missing_maker: bool = False,
            report: Path | None = None):
    prompt, default_report = artifacts(root)
    return run([
        "checker", "--root", str(root), "--unit-id", "U-loop",
        "--risk-tier", risk, "--mode", mode,
        "--report", str(report or default_report), "--prompt-file", str(prompt),
        "--maker-provider", "" if missing_maker else "openai",
        "--maker-model", "" if missing_maker else "gpt-maker",
        "--maker-session", "" if missing_maker else "maker-session",
        "--checker-provider", "openai",
        "--checker-model", "gpt-maker" if same_model else "gpt-checker",
        "--checker-session", "maker-session" if same_session else "checker-session",
    ], root)


def adjudicate(root: Path, risk: str, machine_path: Path,
               checker_path: Path | None = None, attempt: int | None = None):
    args = ["adjudicate", "--root", str(root), "--unit-id", "U-loop",
            "--risk-tier", risk, "--machine", str(machine_path)]
    if attempt is not None:
        args += ["--attempt", str(attempt)]
    if checker_path:
        args += ["--checker", str(checker_path)]
    return run(args, root)


quiet = run([], ROOT)
check("no arguments is a quiet no-op", quiet.returncode == 0 and not quiet.stdout)

policy = json.loads(POLICY.read_text(encoding="utf-8"))
source = SCRIPT.read_text(encoding="utf-8")
check("checkout probes tolerate native Windows access to WSL UNC worktrees",
      "CHECKOUT_PROBE_TIMEOUT_SECONDS = 60" in source)
check("machine producer selects a hash-bound host-owned shell transport",
      "GetSystemDirectoryW" in source
      and "pushd" in source and "{repo}" in source
      and "keeping shell=False" in source
      and '[str(shell), "-c", command]' in source
      and '"shellSha256": shell_digest' in source
      and 'shutil.which("sh")' not in source
      and 'os.environ.get("COMSPEC"' not in source)
check("immutable receipt publication has a Windows UNC-safe no-replace path",
      "os.rename(tmp, path)" in source and "os.link(tmp, path)" in source)
check("machine oracle is materialized from the staged tree in isolation",
      '"clone", "--shared", "--no-checkout"' in source
      and '"executionMode": "isolated-staged-tree"' in source)
check("each machine command receives a fresh isolated checkout",
      "for ident, command in commands:\n            with isolated_candidate(repo, context)" in source)
check("adjudication bounds and contains dependency JSON before reading",
      "JSON_INPUT_MAX_BYTES = 4 * 1024 * 1024" in source
      and "secure_dependency_path(repo, root, args.machine" in source)
check("all evidence producers use exclusive publication",
      "write_json_atomic" not in source
      and source.count("write_json_exclusive(output, receipt)") == 3)
check("policy makes low machine-only and medium/high checker-backed",
      policy["riskRoutes"]["low"] == {"checkerMode": "machine_only", "checkerRequired": False}
      and policy["riskRoutes"]["medium"]["checkerMode"] == "targeted"
      and policy["riskRoutes"]["high"]["checkerMode"] == "full")
check("plain-text checker evidence is forbidden",
      policy["invariants"]["plainTextCheckerEvidenceAccepted"] is False)
check("policy freezes isolated execution and immutable evidence history",
      policy["invariants"]["machineExecutionMode"] == "isolated-staged-tree"
      and policy["invariants"]["machineOutputRetention"] == "hashes-only"
      and policy["invariants"]["undeclaredIgnoredInputsEnterMachineOracle"] is False
      and policy["invariants"]["immutableReceiptPublicationRequired"] is True)
check("threat model does not overclaim same-principal authentication",
      policy["threatModel"]["trustRoot"] == "honest-host-orchestrator"
      and "malicious-same-os-principal" in policy["threatModel"]["nonGuarantees"]
      and policy["invariants"]["samePrincipalByzantineResistanceClaimed"] is False)

# Low risk: harness executes the command and can adjudicate without an LLM tax.
low = fixture()
low_machine = machine(low, "low")
check("low-risk machine oracle executes", low_machine.returncode == 0, low_machine.stderr + low_machine.stdout)
low_machine_path = last_path(low_machine)
low_machine_value = json.loads(low_machine_path.read_text(encoding="utf-8"))
check("machine receipt binds a trusted absolute shell digest",
      Path(low_machine_value["runs"][0]["shell"]).is_absolute()
      and len(low_machine_value["runs"][0]["shellSha256"]) == 64
      and low_machine_value["runs"][0]["shellSha256"]
      == hashlib.sha256(Path(low_machine_value["runs"][0]["shell"]).read_bytes()).hexdigest())
impossible_chronology = json.loads(low_machine_path.read_text(encoding="utf-8"))
impossible_chronology["runs"][0]["startedAt"] = "2026-08-01T16:24:16Z"
impossible_chronology["runs"][0]["completedAt"] = "2026-08-01T16:24:13Z"
impossible_chronology.pop("receiptSha256", None)
impossible_chronology["receiptSha256"] = hashlib.sha256(json.dumps(
    impossible_chronology, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
impossible_chronology_path = low_machine_path.with_name("impossible-chronology.json")
impossible_chronology_path.write_text(
    json.dumps(impossible_chronology), encoding="utf-8")
impossible_chronology_adjudication = adjudicate(
    low, "low", impossible_chronology_path)
check("consumer rejects impossible machine-run chronology",
      impossible_chronology_adjudication.returncode != 0
      and "chronology" in impossible_chronology_adjudication.stdout,
      impossible_chronology_adjudication.stdout)
missing_chronology = json.loads(low_machine_path.read_text(encoding="utf-8"))
del missing_chronology["runs"][0]["startedAt"]
missing_chronology.pop("receiptSha256", None)
missing_chronology["receiptSha256"] = hashlib.sha256(json.dumps(
    missing_chronology, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
missing_chronology_path = low_machine_path.with_name("missing-chronology.json")
missing_chronology_path.write_text(json.dumps(missing_chronology), encoding="utf-8")
missing_chronology_adjudication = adjudicate(low, "low", missing_chronology_path)
check("consumer rejects missing machine-run chronology",
      missing_chronology_adjudication.returncode != 0
      and "timestamp is invalid" in missing_chronology_adjudication.stdout,
      missing_chronology_adjudication.stdout)
invalid_chronology = json.loads(low_machine_path.read_text(encoding="utf-8"))
invalid_chronology["runs"][0]["completedAt"] = "not-a-timestamp"
invalid_chronology.pop("receiptSha256", None)
invalid_chronology["receiptSha256"] = hashlib.sha256(json.dumps(
    invalid_chronology, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
invalid_chronology_path = low_machine_path.with_name("invalid-chronology.json")
invalid_chronology_path.write_text(json.dumps(invalid_chronology), encoding="utf-8")
invalid_chronology_adjudication = adjudicate(low, "low", invalid_chronology_path)
check("consumer rejects unparseable machine-run chronology",
      invalid_chronology_adjudication.returncode != 0
      and "timestamp is invalid" in invalid_chronology_adjudication.stdout,
      invalid_chronology_adjudication.stdout)
cross_run_chronology = json.loads(low_machine_path.read_text(encoding="utf-8"))
earlier_run = dict(cross_run_chronology["runs"][0])
earlier_run["id"] = "chronology-replay"
earlier_run["startedAt"] = "2000-01-01T00:00:00Z"
earlier_run["completedAt"] = "2000-01-01T00:00:01Z"
cross_run_chronology["runs"].append(earlier_run)
cross_run_chronology.pop("receiptSha256", None)
cross_run_chronology["receiptSha256"] = hashlib.sha256(json.dumps(
    cross_run_chronology, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
cross_run_chronology_path = low_machine_path.with_name("cross-run-chronology.json")
cross_run_chronology_path.write_text(
    json.dumps(cross_run_chronology), encoding="utf-8")
cross_run_chronology_adjudication = adjudicate(
    low, "low", cross_run_chronology_path)
check("consumer rejects cross-run non-monotonic chronology",
      cross_run_chronology_adjudication.returncode != 0
      and "chronology" in cross_run_chronology_adjudication.stdout,
      cross_run_chronology_adjudication.stdout)
post_receipt_chronology = json.loads(low_machine_path.read_text(encoding="utf-8"))
receipt_created = dt.datetime.fromisoformat(
    post_receipt_chronology["createdAt"].replace("Z", "+00:00"))
post_receipt_chronology["runs"][0]["startedAt"] = (
    receipt_created.isoformat().replace("+00:00", "Z"))
post_receipt_chronology["runs"][0]["completedAt"] = (
    (receipt_created + dt.timedelta(seconds=1)).isoformat().replace("+00:00", "Z"))
post_receipt_chronology.pop("receiptSha256", None)
post_receipt_chronology["receiptSha256"] = hashlib.sha256(json.dumps(
    post_receipt_chronology, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
post_receipt_chronology_path = low_machine_path.with_name("post-receipt-chronology.json")
post_receipt_chronology_path.write_text(
    json.dumps(post_receipt_chronology), encoding="utf-8")
post_receipt_chronology_adjudication = adjudicate(
    low, "low", post_receipt_chronology_path)
check("consumer rejects a run completed after receipt creation",
      post_receipt_chronology_adjudication.returncode != 0
      and "chronology" in post_receipt_chronology_adjudication.stdout,
      post_receipt_chronology_adjudication.stdout)
fake_shell_dir = Path(tempfile.mkdtemp(prefix="forged-verification-shell-"))
fake_shell = fake_shell_dir / ("cmd.exe" if os.name == "nt" else "sh")
fake_shell.write_text("@exit /b 0\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n",
                      encoding="utf-8")
fake_shell.chmod(0o755)
old_path = os.environ.get("PATH", "")
old_comspec = os.environ.get("COMSPEC")
try:
    os.environ["PATH"] = str(fake_shell_dir) + os.pathsep + old_path
    os.environ["COMSPEC"] = str(fake_shell)
    forged_shell = machine(low, "low", "exit /b 9" if os.name == "nt" else "exit 9")
finally:
    os.environ["PATH"] = old_path
    if old_comspec is None:
        os.environ.pop("COMSPEC", None)
    else:
        os.environ["COMSPEC"] = old_comspec
forged_shell_value = json.loads(last_path(forged_shell).read_text(encoding="utf-8"))
check("inherited PATH and COMSPEC cannot substitute the verification shell",
      forged_shell.returncode != 0
      and forged_shell_value["runs"][0]["exitCode"] == 9
      and Path(forged_shell_value["runs"][0]["shell"]).resolve() != fake_shell.resolve())
secret_output = machine(
    low, "low",
    f'"{sys.executable}" -c "print(bytes([83,69,78,83,73,84,73,86,69,45,79,82,65,67,76,69,45,79,85,84,80,85,84]).decode())"',
)
secret_receipt = last_path(secret_output).read_text(encoding="utf-8")
check("machine receipt retains output hashes without raw sensitive tails",
      secret_output.returncode == 0
      and "SENSITIVE-ORACLE-OUTPUT" not in secret_receipt
      and "stdoutSha256" in secret_receipt
      and "stdoutTail" not in secret_receipt
      and "stderrTail" not in secret_receipt,
      secret_receipt)
unsafe_receipt = json.loads(secret_receipt)
unsafe_receipt["runs"][0]["stdoutTail"] = "SENSITIVE-ORACLE-OUTPUT"
unsafe_receipt.pop("receiptSha256", None)
unsafe_receipt["receiptSha256"] = hashlib.sha256(json.dumps(
    unsafe_receipt, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
unsafe_path = last_path(secret_output).with_name("unsafe-machine-tail.json")
unsafe_path.write_text(json.dumps(unsafe_receipt), encoding="utf-8")
unsafe_adjudication = adjudicate(low, "low", unsafe_path)
check("consumer rejects a digest-valid receipt containing raw output tails",
      unsafe_adjudication.returncode != 0
      and "non-schema fields" in unsafe_adjudication.stdout,
      unsafe_adjudication.stdout)
alternate_tail_receipt = json.loads(secret_receipt)
alternate_tail_receipt["runs"][0]["outputTail"] = "SENSITIVE-ALTERNATE-FIELD"
alternate_tail_receipt.pop("receiptSha256", None)
alternate_tail_receipt["receiptSha256"] = hashlib.sha256(json.dumps(
    alternate_tail_receipt, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
alternate_tail_path = last_path(secret_output).with_name("unsafe-alternate-tail.json")
alternate_tail_path.write_text(json.dumps(alternate_tail_receipt), encoding="utf-8")
alternate_tail_adjudication = adjudicate(low, "low", alternate_tail_path)
check("closed machine-run schema rejects alternate raw output fields",
      alternate_tail_adjudication.returncode != 0
      and "non-schema fields" in alternate_tail_adjudication.stdout,
      alternate_tail_adjudication.stdout)
oversized_path = low_machine_path.with_name("oversized-machine.json")
oversized_path.write_bytes(b" " * (4 * 1024 * 1024 + 1))
oversized_adjudication = adjudicate(low, "low", oversized_path)
check("oversized dependency JSON is rejected before parsing",
      oversized_adjudication.returncode != 0
      and "exceeds the 4194304-byte limit" in oversized_adjudication.stdout,
      oversized_adjudication.stdout)
low_machine_bytes = low_machine_path.read_bytes()
low_machine_repeat = machine(low, "low")
low_machine_repeat_path = last_path(low_machine_repeat)
check("repeated machine producers append immutable receipts",
      low_machine_repeat.returncode == 0
      and low_machine_repeat_path != low_machine_path
      and low_machine_path.read_bytes() == low_machine_bytes,
      low_machine_repeat.stdout)
low_adj = adjudicate(low, "low", low_machine_path)
check("low-risk machine-only adjudication passes", low_adj.returncode == 0, low_adj.stdout)
low_adj_path = last_path(low_adj)
low_check = run(["check", "--root", str(low), "--unit-id", "U-loop",
                 "--risk-tier", "low", "--receipt", str(low_adj_path)], low)
check("adjudication receipt is reusable on the exact candidate", low_check.returncode == 0)
wrong_unit = run(["check", "--root", str(low), "--unit-id", "U-other",
                  "--risk-tier", "low", "--receipt", str(low_adj_path)], low)
check("receipt cannot cross unit boundaries",
      wrong_unit.returncode != 0 and "another unit" in wrong_unit.stdout,
      wrong_unit.stdout)
wrong_risk = run(["check", "--root", str(low), "--unit-id", "U-loop",
                  "--risk-tier", "medium", "--receipt", str(low_adj_path)], low)
check("receipt cannot cross risk routes",
      wrong_risk.returncode != 0 and "risk tier" in wrong_risk.stdout,
      wrong_risk.stdout)

# An ignored source overlay must never enter the machine execution checkout.
ignored_overlay = fixture()
(ignored_overlay / ".git" / "info" / "exclude").write_text("ignored/\n", encoding="utf-8")
(ignored_overlay / "ignored").mkdir()
(ignored_overlay / "ignored" / "proof").write_text("false pass\n", encoding="utf-8")
ignored_command = (f'"{sys.executable}" -c "from pathlib import Path; '
                   "raise SystemExit(0 if Path('ignored/proof').exists() else 9)\"")
ignored_machine = machine(ignored_overlay, "low", ignored_command)
ignored_receipt = json.loads(last_path(ignored_machine).read_text(encoding="utf-8"))
check("ignored source overlay cannot create a false machine PASS",
      ignored_machine.returncode != 0
      and ignored_receipt["runs"][0]["exitCode"] == 9
      and ignored_receipt["runs"][0]["executionMode"] == "isolated-staged-tree",
      ignored_machine.stdout)

# One command must not be able to feed an undeclared overlay to a later
# command in the same machine receipt.
cross_command = fixture()
writer = (f'"{sys.executable}" -c "from pathlib import Path; '
          "Path('oracle-overlay.tmp').write_text('poison')\"")
reader = (f'"{sys.executable}" -c "from pathlib import Path; '
          "raise SystemExit(9 if Path('oracle-overlay.tmp').exists() else 0)\"")
cross_machine = run([
    "machine", "--root", str(cross_command), "--unit-id", "U-loop",
    "--risk-tier", "low", "--command", "writer=" + writer,
    "--command", "reader=" + reader, "--timeout", "10",
], cross_command)
cross_receipt = json.loads(last_path(cross_machine).read_text(encoding="utf-8"))
check("machine commands cannot share undeclared overlays",
      cross_machine.returncode == 0
      and [item["exitCode"] for item in cross_receipt["runs"]] == [0, 0],
      cross_machine.stdout + cross_machine.stderr)

# A genuinely required non-Git oracle input must be explicit, snapshotted and
# revalidated instead of reopening the whole ignored workspace.
declared_root = fixture()
(declared_root / ".git" / "info" / "exclude").write_text("result.txt\n", encoding="utf-8")
(declared_root / "result.txt").write_text("pass\n", encoding="utf-8")
declared_command = (f'"{sys.executable}" -c "from pathlib import Path; '
                    "raise SystemExit(0 if Path('result.txt').read_text().strip()=='pass' else 8)\"")
declared_machine = machine(declared_root, "low", declared_command, inputs=["result.txt"])
declared_path = last_path(declared_machine)
check("declared ignored input is copied and hash-bound",
      declared_machine.returncode == 0
      and json.loads(declared_path.read_text(encoding="utf-8"))["declaredInputs"][0]["path"] == "result.txt",
      declared_machine.stdout)
(declared_root / "result.txt").write_text("changed\n", encoding="utf-8")
declared_stale = adjudicate(declared_root, "low", declared_path)
check("changed declared input invalidates machine evidence",
      declared_stale.returncode != 0
      and "declared machine input is missing or changed" in declared_stale.stdout,
      declared_stale.stdout)

# The oracle must execute the staged candidate, never an unstaged overlay.
mismatch = fixture()
(mismatch / "app.py").write_text("VALUE = 999\n", encoding="utf-8")
mismatch_machine = machine(mismatch, "low")
check("unstaged checkout overlay is rejected before command execution",
      mismatch_machine.returncode != 0
      and "working tree differs from the staged candidate" in mismatch_machine.stdout,
      mismatch_machine.stdout)

# Any staged candidate change invalidates the whole evidence chain.
(low / "app.py").write_text("VALUE = 3\n", encoding="utf-8")
git(low, "add", "app.py")
stale = run(["check", "--root", str(low), "--unit-id", "U-loop",
             "--risk-tier", "low", "--receipt", str(low_adj_path)], low)
check("candidate change invalidates prior receipts",
      stale.returncode != 0 and "exact current candidate" in stale.stdout, stale.stdout)

# Medium: a targeted, fresh-session checker is mandatory.
medium = fixture()
medium_machine = machine(medium, "medium")
missing_checker = adjudicate(medium, "medium", last_path(medium_machine))
check("medium risk without checker stays UNVERIFIED",
      missing_checker.returncode != 0 and "required checker" in missing_checker.stdout,
      missing_checker.stdout)

prompt, report = artifacts(medium)
plain_report = report.with_name("U-loop-plain.md")
plain_report.write_text("PASSED\n", encoding="utf-8")
plain = checker(medium, "medium", "targeted", report=plain_report)
check("plain PASSED string cannot mint checker evidence",
      plain.returncode != 0 and "no valid verdict" in plain.stdout, plain.stdout)

same_session = checker(medium, "medium", "targeted", same_session=True)
check("checker must use a fresh session",
      same_session.returncode != 0 and "reused the maker session" in same_session.stdout,
      same_session.stdout)

medium_checker = checker(medium, "medium", "targeted", same_model=True)
check("targeted checker may use same model in a fresh context",
      medium_checker.returncode == 0, medium_checker.stdout)
medium_checker_path = last_path(medium_checker)
medium_checker_bytes = medium_checker_path.read_bytes()
medium_checker_repeat = checker(medium, "medium", "targeted", same_model=True)
check("repeated checker producers append immutable receipts",
      medium_checker_repeat.returncode == 0
      and last_path(medium_checker_repeat) != medium_checker_path
      and medium_checker_path.read_bytes() == medium_checker_bytes,
      medium_checker_repeat.stdout)
medium_adj = adjudicate(medium, "medium", last_path(medium_machine), last_path(medium_checker))
check("medium targeted evidence adjudicates", medium_adj.returncode == 0, medium_adj.stdout)

# Dirty overlays introduced after machine evidence must block both semantic
# evidence minting and final adjudication, even though the staged hash is unchanged.
dirty_checker_root = fixture()
dirty_checker_machine = machine(dirty_checker_root, "medium")
(dirty_checker_root / "app.py").write_text("VALUE = 999\n", encoding="utf-8")
dirty_checker = checker(dirty_checker_root, "medium", "targeted")
check("checker rejects an unstaged overlay introduced after machine evidence",
      dirty_checker.returncode != 0
      and "working tree differs from the staged candidate" in dirty_checker.stdout,
      dirty_checker.stdout)

dirty_adj_root = fixture()
dirty_adj_machine = machine(dirty_adj_root, "medium")
dirty_adj_checker = checker(dirty_adj_root, "medium", "targeted")
(dirty_adj_root / "app.py").write_text("VALUE = 999\n", encoding="utf-8")
dirty_adj = adjudicate(dirty_adj_root, "medium", last_path(dirty_adj_machine),
                       last_path(dirty_adj_checker))
check("adjudicator rejects an unstaged overlay introduced after checker evidence",
      dirty_adj.returncode != 0
      and "working tree differs from the staged candidate" in dirty_adj.stdout,
      dirty_adj.stdout)

# High/unknown: full checker must differ by model or provider.
high = fixture()
high_machine = machine(high, "high")
same_model_full = checker(high, "high", "full", same_model=True)
check("full checker rejects same provider/model pair",
      same_model_full.returncode != 0 and "not model/provider-independent" in same_model_full.stdout,
      same_model_full.stdout)
missing_maker_full = checker(high, "high", "full", missing_maker=True)
check("full checker rejects missing maker provenance",
      missing_maker_full.returncode != 0 and "identity is incomplete" in missing_maker_full.stdout,
      missing_maker_full.stdout)
high_checker = checker(high, "high", "full")
check("full checker receipt binds different model and session",
      high_checker.returncode == 0, high_checker.stdout)
high_checker_path = last_path(high_checker)
whitespace_checker_receipt = json.loads(high_checker_path.read_text(encoding="utf-8"))
whitespace_checker_receipt["provenance"]["checker"]["model"] = " gpt-maker "
whitespace_checker_receipt.pop("receiptSha256", None)
whitespace_checker_receipt["receiptSha256"] = hashlib.sha256(json.dumps(
    whitespace_checker_receipt, ensure_ascii=False, sort_keys=True,
    separators=(",", ":")).encode("utf-8")).hexdigest()
whitespace_checker_path = high_checker_path.with_name("forged-whitespace-model.json")
whitespace_checker_path.write_text(json.dumps(whitespace_checker_receipt), encoding="utf-8")
whitespace_adj = adjudicate(high, "high", last_path(high_machine), whitespace_checker_path)
check("normalized provenance comparison rejects whitespace independence bypass",
      whitespace_adj.returncode != 0
      and "not model/provider-independent" in whitespace_adj.stdout,
      whitespace_adj.stdout)
high_adj = adjudicate(high, "high", last_path(high_machine), high_checker_path)
check("high-risk full evidence adjudicates", high_adj.returncode == 0, high_adj.stdout)
high_adj_path = last_path(high_adj)

# Editing the durable report breaks the dependency chain even if receipt JSON is unchanged.
_, high_report = artifacts(high)
high_report.write_text(high_report.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
tampered_report = run(["check", "--root", str(high), "--unit-id", "U-loop",
                       "--risk-tier", "high", "--receipt", str(high_adj_path)], high)
check("changed checker report invalidates adjudication",
      tampered_report.returncode != 0 and "artifact is missing or changed" in tampered_report.stdout,
      tampered_report.stdout)

# Self-edited receipts and attempt inflation fail closed.
forged = json.loads(high_adj_path.read_text(encoding="utf-8"))
forged["outcome"] = "FAILED"
high_adj_path.write_text(json.dumps(forged), encoding="utf-8")
forged_check = run(["check", "--root", str(high), "--unit-id", "U-loop",
                    "--risk-tier", "high", "--receipt", str(high_adj_path)], high)
check("edited receipt digest is rejected",
      forged_check.returncode != 0 and "digest is invalid" in forged_check.stdout,
      forged_check.stdout)

attempt_root = fixture()
attempt_machine = machine(attempt_root, "low")
attempt_machine_path = last_path(attempt_machine)
attempt_one = adjudicate(attempt_root, "low", attempt_machine_path, attempt=1)
check("first explicit attempt is durably allocated", attempt_one.returncode == 0, attempt_one.stdout)
replayed_one = adjudicate(attempt_root, "low", attempt_machine_path, attempt=1)
check("replaying --attempt 1 cannot reset the durable budget",
      replayed_one.returncode != 0 and "non-monotonic attempt" in replayed_one.stdout,
      replayed_one.stdout)
attempt_two = adjudicate(attempt_root, "low", attempt_machine_path)
attempt_three = adjudicate(attempt_root, "low", attempt_machine_path)
check("automatic attempt allocation is monotonic",
      attempt_two.returncode == 0 and attempt_three.returncode == 0,
      attempt_two.stdout + attempt_three.stdout)
over_attempt = adjudicate(attempt_root, "low", attempt_machine_path)
check("repair/adjudication attempts are durably bounded",
      over_attempt.returncode != 0 and "attempt budget exhausted" in over_attempt.stdout,
      over_attempt.stdout)
attempt_one_path = last_path(attempt_one)
attempt_one_check = run(["check", "--root", str(attempt_root), "--unit-id", "U-loop",
                         "--risk-tier", "low", "--receipt", str(attempt_one_path)], attempt_root)
check("earlier immutable attempt remains independently verifiable",
      attempt_one_check.returncode == 0, attempt_one_check.stdout)

# A host crash can leave a complete linked receipt immediately before its
# ledger entry and can leave the allocation lock behind. The retry must
# reconcile that exact transaction, not overwrite or spend another attempt.
crash_root = fixture()
crash_machine = machine(crash_root, "low")
crash_machine_path = last_path(crash_machine)
before_crash = adjudicate(crash_root, "low", crash_machine_path)
before_crash_path = last_path(before_crash)
before_crash_receipt = json.loads(before_crash_path.read_text(encoding="utf-8"))
crash_entry = crash_root / before_crash_receipt["attemptLedger"]["entryPath"]
crash_entry.unlink()
(crash_entry.parent / ".allocate.lock").write_text("99999999\n", encoding="ascii")
recovered = adjudicate(crash_root, "low", crash_machine_path)
check("dead lock and complete orphan receipt are crash-recovered",
      recovered.returncode == 0 and last_path(recovered) == before_crash_path
      and crash_entry.is_file(), recovered.stdout)
recovered_check = run(["check", "--root", str(crash_root), "--unit-id", "U-loop",
                       "--risk-tier", "low", "--receipt", str(before_crash_path)], crash_root)
check("crash-reconciled receipt remains independently verifiable",
      recovered_check.returncode == 0, recovered_check.stdout)

failed_root = fixture()
failed_machine = machine(failed_root, "low", "false")
check("failing oracle writes FAILED evidence and exits nonzero", failed_machine.returncode != 0)
failed_adj = adjudicate(failed_root, "low", last_path(failed_machine))
check("FAILED machine receipt cannot adjudicate PASSED",
      failed_adj.returncode != 0 and "machine verification failed" in failed_adj.stdout,
      failed_adj.stdout)

# Policy mutation: the executable consumer rejects a weakened trust model.
spec = importlib.util.spec_from_file_location("verification_loop_under_test", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix="declared-input-link-") as td:
    link_root = Path(td)
    source_root = link_root / "source"
    isolated = link_root / "isolated"
    outside = link_root / "outside"
    (source_root / "nested").mkdir(parents=True)
    isolated.mkdir()
    outside.mkdir()
    (source_root / "nested" / "proof.txt").write_text("sealed\n", encoding="utf-8")
    try:
        (isolated / "nested").symlink_to(outside, target_is_directory=True)
        link_supported = True
    except OSError:
        link_supported = False
    if link_supported:
        manifest = module.input_snapshot(
            source_root / "nested" / "proof.txt", "nested/proof.txt")
        try:
            module.copy_declared_inputs(source_root, isolated, [manifest])
            link_rejected = False
        except module.LoopError:
            link_rejected = True
        check("declared input copy rejects a symlinked checkout ancestor",
              link_rejected and not (outside / "proof.txt").exists())
        source_link = link_root / "source-link"
        sealed_root = link_root / "sealed-source"
        source_link.mkdir()
        sealed_root.mkdir()
        (outside / "proof.txt").write_text("outside\n", encoding="utf-8")
        (source_link / "nested").symlink_to(outside, target_is_directory=True)
        sealed_destination = module.secure_destination(
            sealed_root, "nested/proof.txt")
        try:
            module.secure_copy_declared_source(
                source_link, "nested/proof.txt", sealed_destination)
            source_link_rejected = False
        except module.LoopError:
            source_link_rejected = True
        check("declared input snapshot rejects a symlinked source ancestor",
              source_link_rejected and not sealed_destination.exists())
    else:
        check("declared input copy has a no-follow ancestor guard on this host",
              "follow_symlinks=False" in SCRIPT.read_text(encoding="utf-8"))
with tempfile.TemporaryDirectory(prefix="declared-input-alias-") as td:
    alias_root = Path(td)
    canonical_repo = alias_root / "repo"
    alias_hop = alias_root / "alias-hop"
    snapshot_root = alias_root / "snapshot"
    (canonical_repo / "nested").mkdir(parents=True)
    alias_hop.mkdir()
    snapshot_root.mkdir()
    (canonical_repo / "nested" / "proof.txt").write_text(
        "sealed\n", encoding="utf-8")
    # A lexical alias with the same canonical target deterministically models
    # the Windows 8.3/long-name mismatch that triggered the no-dir_fd fallback
    # failure on GitHub-hosted runners.
    aliased_repo = alias_hop / ".." / canonical_repo.name
    destination = module.secure_destination(
        snapshot_root, "nested/proof.txt")
    disabled_dir_fd = {
        function for function in (os.open, os.stat)
        if function in os.supports_dir_fd
    }
    os.supports_dir_fd.difference_update(disabled_dir_fd)
    try:
        try:
            module.secure_copy_declared_source(
                aliased_repo, "nested/proof.txt", destination)
            alias_copy_ok = destination.read_text(encoding="utf-8") == "sealed\n"
        except (module.LoopError, OSError):
            alias_copy_ok = False
        check("guarded fallback canonicalizes equivalent repo spellings",
              alias_copy_ok)

        outside = alias_root / "outside"
        outside.mkdir()
        (outside / "escape.txt").write_text("outside\n", encoding="utf-8")
        try:
            (canonical_repo / "linked").symlink_to(
                outside, target_is_directory=True)
            fallback_link_supported = True
        except OSError:
            fallback_link_supported = False
        if fallback_link_supported:
            linked_snapshot = alias_root / "linked-snapshot"
            linked_snapshot.mkdir()
            linked_destination = module.secure_destination(
                linked_snapshot, "linked/escape.txt")
            try:
                module.secure_copy_declared_source(
                    aliased_repo, "linked/escape.txt", linked_destination)
                fallback_link_rejected = False
            except module.LoopError:
                fallback_link_rejected = True
            check("guarded fallback still rejects a linked source ancestor",
                  fallback_link_rejected and not linked_destination.exists())
        else:
            check("guarded fallback retains the reparse-point rejection",
                  "_is_link_or_reparse(current)" in
                  SCRIPT.read_text(encoding="utf-8"))
    finally:
        os.supports_dir_fd.update(disabled_dir_fd)
with tempfile.TemporaryDirectory(prefix="weak-loop-policy-") as td:
    weak_path = Path(td) / "policy.json"
    weak = json.loads(POLICY.read_text(encoding="utf-8"))
    weak["invariants"]["plainTextCheckerEvidenceAccepted"] = True
    weak_path.write_text(json.dumps(weak), encoding="utf-8")
    original = module.POLICY_PATH
    module.POLICY_PATH = weak_path
    try:
        rejected = False
        try:
            module.load_policy()
        except module.LoopError:
            rejected = True
        check("weakened policy mutation is rejected", rejected)
    finally:
        module.POLICY_PATH = original

print(f"\n{PASSED} passed, {FAILED} failed")
raise SystemExit(1 if FAILED else 0)
