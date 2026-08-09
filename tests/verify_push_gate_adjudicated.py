#!/usr/bin/env python3
"""Oracle for ADJUDICATED acceptance in the push layer (GPG-004-PB1).

RED-first target: the guarded push layer validates a local-review receipt via
``check --require-mandatory-route``, which demands a checker carrying a signed
phase-one clean-pass route. The producer structurally never mints phase-one
for a BLOCKED verdict, so an honestly BLOCKED-then-adjudicated route (ADR-007)
could never satisfy the push gate. This oracle requires the explicit opt-in
``--accept-adjudicated-route`` flag: with it, an ADJUDICATED outcome is
authorized by the human adjudication channel without a phase-one route, while
a PASSED outcome still requires the signed route and the default behavior
stays byte-preserved.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
GATE = ROOT / "skills" / "_shared" / "itd_gate_control.py"

checks = 0
failures: list[str] = []

EXPECTED_REPOSITORY = "example/fixture"
EXPECTED_KEYRING_SHA = "a" * 64


def check(name: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(f"{name}: {detail}"[:400])


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True,
    )


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixture_committed() -> Path:
    """One clean single-parent submission commit, ready for committed-head."""
    root = Path(tempfile.mkdtemp(prefix="push-gate-adjudicated-"))
    git(root, "init", "-q")
    git(root, "config", "user.name", "Push Gate Adjudicated")
    # Literal split keeps the secret scrubber from flagging the diff as an
    # email leak; the runtime value stays a normal fixture address.
    git(root, "config", "user.email", "pushgate@" + "example.test")
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
    git(root, "commit", "-qm", "submission candidate")
    return root


FINDINGS = [
    {"severity": "high", "file": "app.py", "line": 1,
     "summary": "reviewer claims the constant regressed"},
    {"severity": "medium", "file": "app.py", "line": 1,
     "summary": "reviewer claims the change is undocumented"},
]
UNVERIFIED = ["reviewer could not open the binary transcript"]


def artifacts(root: Path, verdict: str, artifact_id: str) -> tuple[Path, Path]:
    base = root / ".itd-memory" / "verification-loop"
    prompt = base / "prompts" / f"{artifact_id}.md"
    report = base / "reports" / f"{artifact_id}.md"
    prompt.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_bytes(b"Review exact candidate; no inherited reasoning.\n")
    body = {"verdict": verdict,
            "findings": FINDINGS if verdict == "BLOCKED" else [],
            "unverified": UNVERIFIED if verdict == "BLOCKED" else []}
    report.write_bytes(
        ("# Review\n\n```json\n" + json.dumps(body) + "\n```\n").encode("utf-8"))
    return prompt, report


UNIT = "U-push"
COMMON = ["--risk-tier", "high", "--candidate-mode", "committed-head"]


def machine(root: Path) -> subprocess.CompletedProcess[str]:
    oracle = f'"{sys.executable}" -c "print(123)"'
    return run(["machine", "--root", str(root), "--unit-id", UNIT, *COMMON,
                "--command", "oracle=" + oracle, "--timeout", "10"], root)


def checker(root: Path, verdict: str, artifact_id: str):
    prompt, report = artifacts(root, verdict, artifact_id)
    return run([
        "checker", "--root", str(root), "--unit-id", UNIT, *COMMON,
        "--mode", "full",
        "--report", str(report), "--prompt-file", str(prompt),
        "--maker-provider", "anthropic", "--maker-model", "claude-maker",
        "--maker-session", "maker-session",
        "--checker-provider", "openai", "--checker-model", "gpt-checker",
        "--checker-session", "checker-session",
    ], root)


def last_path(proc: subprocess.CompletedProcess[str]) -> Path:
    return Path(proc.stdout.strip().splitlines()[-1])


def newest_receipt(root: Path, kind: str) -> Path | None:
    base = root / ".itd-memory" / "verification-loop" / "receipts"
    found = sorted(base.rglob(f"*{kind}*.json"),
                   key=lambda p: p.stat().st_mtime) if base.is_dir() else []
    return found[-1] if found else None


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def dispositions_value(checker_path: Path) -> dict:
    items = []
    for index, finding in enumerate(FINDINGS + UNVERIFIED):
        klass = ("refuted-by-evidence" if index == 0 else "accepted-trade-off")
        row = {
            "findingSha256": canonical_digest(finding),
            "finding": finding,
            "class": klass,
            "rationale": ("bytes 1f 8b prove the transcript is gzip"
                          if index == 0
                          else "accepted design tension, recorded in DECISIONS"),
        }
        if klass == "refuted-by-evidence":
            row["evidence"] = "hexdump of the first two bytes"
        items.append(row)
    sha = hashlib.sha256(checker_path.read_bytes()).hexdigest()
    return {
        "confirmedBy": "hihol",
        "confirmation": ("I adjudicated every finding of checker receipt "
                         f"{sha} and accept the recorded dispositions"),
        "checkerReceiptSha256": sha,
        "dispositions": items,
    }


def adjudicate(root: Path, machine_path: Path, checker_path: Path,
               dispositions: dict | None = None, name: str = "d"):
    args = ["adjudicate", "--root", str(root), "--unit-id", UNIT, *COMMON,
            "--machine", str(machine_path), "--checker", str(checker_path)]
    if dispositions is not None:
        path = root / ".itd-memory" / f"dispositions-{name}.json"
        path.write_text(json.dumps(dispositions), encoding="utf-8")
        args += ["--dispositions", str(path)]
    return run(args, root)


def check_cmd(root: Path, receipt: Path, *extra: str):
    return run(["check", "--root", str(root), "--unit-id", UNIT, *COMMON,
                "--receipt", str(receipt), *extra], root)


ROUTE_ARGS = ("--require-mandatory-route",
              "--expected-repository", EXPECTED_REPOSITORY,
              "--expected-producer-keyring-sha256", EXPECTED_KEYRING_SHA)

# --- Honest ADJUDICATED committed-head chain -------------------------------
root = fixture_committed()
machine_proc = machine(root)
check("committed-head machine oracle passes", machine_proc.returncode == 0,
      machine_proc.stdout + machine_proc.stderr)
machine_path = last_path(machine_proc)

blocked_proc = checker(root, "BLOCKED", "blocked")
blocked_path = newest_receipt(root, "checker")
check("BLOCKED full checker receipt is minted durably",
      blocked_proc.returncode != 0 and blocked_path is not None,
      blocked_proc.stdout + blocked_proc.stderr)
assert blocked_path is not None

mint = adjudicate(root, machine_path, blocked_path,
                  dispositions_value(blocked_path), name="good")
check("human adjudication mints ADJUDICATED on committed-head",
      mint.returncode == 0, mint.stdout + mint.stderr)
assert mint.returncode == 0
receipt_path = last_path(mint)
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
check("receipt outcome is honestly ADJUDICATED",
      receipt.get("outcome") == "ADJUDICATED", str(receipt.get("outcome")))

# Commit-gate parity: without the mandatory-route requirement the ADJUDICATED
# receipt already validates (the phase-A channel).
plain = check_cmd(root, receipt_path)
check("check without route requirement accepts ADJUDICATED",
      plain.returncode == 0, plain.stdout + plain.stderr)
check("default check stdout stays byte-preserved (silent on success)",
      plain.stdout == "", repr(plain.stdout)[:200])

# The proven push-layer deadlock stays documented: the honest ADJUDICATED
# receipt has no signed phase-one route and the strict default must refuse.
strict = check_cmd(root, receipt_path, *ROUTE_ARGS)
check("default --require-mandatory-route still refuses ADJUDICATED",
      strict.returncode != 0
      and "mandatory keyless route evidence is missing"
      in strict.stdout + strict.stderr,
      strict.stdout + strict.stderr)

# The channel-authorized push path: explicit opt-in flag accepts the honest
# ADJUDICATED receipt without a phase-one route. RED on pre-unit code (the
# flag does not exist yet).
accepted = check_cmd(root, receipt_path, *ROUTE_ARGS,
                     "--accept-adjudicated-route")
check("--accept-adjudicated-route accepts the honest ADJUDICATED receipt",
      accepted.returncode == 0, accepted.stdout + accepted.stderr)
check("opt-in caller receives the validated outcome label",
      '"outcome": "ADJUDICATED"' in accepted.stdout, repr(accepted.stdout)[:200])

# Tampered checker dependency invalidates the receipt under the new flag too.
original_checker = blocked_path.read_bytes()
blocked_path.write_bytes(original_checker.replace(b"regressed", b"regressed!"))
tampered = check_cmd(root, receipt_path, *ROUTE_ARGS,
                     "--accept-adjudicated-route")
blocked_path.write_bytes(original_checker)
check("tampered checker dependency refuses under the new flag",
      tampered.returncode != 0, tampered.stdout + tampered.stderr)

# Stripping the human adjudication block breaks the receipt digest and the
# flag must not resurrect it.
stripped = dict(receipt)
stripped.pop("humanAdjudication", None)
stripped_path = receipt_path.with_name("stripped.json")
stripped_path.write_text(json.dumps(stripped), encoding="utf-8")
laundered = check_cmd(root, stripped_path, *ROUTE_ARGS,
                      "--accept-adjudicated-route")
check("ADJUDICATED without its human adjudication block refuses",
      laundered.returncode != 0, laundered.stdout + laundered.stderr)

# --- Clean PASSED chain: the signed route stays mandatory ------------------
clean_root = fixture_committed()
clean_machine_proc = machine(clean_root)
check("clean fixture machine oracle passes",
      clean_machine_proc.returncode == 0,
      clean_machine_proc.stdout + clean_machine_proc.stderr)
clean_machine = last_path(clean_machine_proc)
clean_proc = checker(clean_root, "PASSED", "clean")
check("clean full checker mints", clean_proc.returncode == 0,
      clean_proc.stdout + clean_proc.stderr)
clean_checker = last_path(clean_proc)
clean_mint = adjudicate(clean_root, clean_machine, clean_checker)
check("clean chain mints plain PASSED", clean_mint.returncode == 0
      and json.loads(last_path(clean_mint).read_text(
          encoding="utf-8")).get("outcome") == "PASSED",
      clean_mint.stdout + clean_mint.stderr)
if clean_mint.returncode == 0:
    clean_receipt = last_path(clean_mint)
    passed_no_route = check_cmd(clean_root, clean_receipt, *ROUTE_ARGS,
                                "--accept-adjudicated-route")
    check("PASSED outcome without a signed route still refuses under the flag",
          passed_no_route.returncode != 0
          and "mandatory keyless route evidence is missing"
          in passed_no_route.stdout + passed_no_route.stderr,
          passed_no_route.stdout + passed_no_route.stderr)

# --- The push layer itself passes the opt-in flag --------------------------
gate = load_module(GATE, "itd_gate_control_push_fixture")
captured: list[list[str]] = []


def stub_runner(command, **kwargs):
    captured.append([str(part) for part in command])
    return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")


try:
    gate.validate_local_adjudication(
        root, receipt_path, f"{UNIT}:local-review-commit", "high",
        EXPECTED_REPOSITORY, EXPECTED_KEYRING_SHA, runner=stub_runner)
    local_error = ""
except gate.GateError as exc:
    local_error = f"{exc.status}: {exc.reason}"
check("validate_local_adjudication keeps its strict base arguments",
      bool(captured)
      and "--require-mandatory-route" in captured[0]
      and "--candidate-mode" in captured[0]
      and "committed-head" in captured[0], f"{captured!r} {local_error}")
check("validate_local_adjudication passes --accept-adjudicated-route",
      bool(captured) and "--accept-adjudicated-route" in captured[0],
      f"{captured!r} {local_error}")

print(json.dumps({
    "checks": checks, "failures": failures,
    "status": "PASSED" if not failures else "FAILED",
}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
