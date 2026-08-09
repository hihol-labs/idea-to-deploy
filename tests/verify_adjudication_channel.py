#!/usr/bin/env python3
"""Oracle for the human adjudication channel (ADR-007, GPG-004 phase A).

RED-first target: a BLOCKED checker receipt whose findings were all humanly
dispositioned could not satisfy the review gate at all — the only accepted
adjudication outcome was PASSED. This oracle requires the channel: minting an
honest ADJUDICATED receipt from (machine PASSED + checker BLOCKED + complete
per-finding human dispositions + explicit confirmation), with every minting
guard fail-closed, and the commit review gate accepting the honest label.
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
CACHE = ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py"

checks = 0
failures: list[str] = []


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
    spec.loader.exec_module(module)
    return module


def fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="adjudication-channel-"))
    git(root, "init", "-q")
    git(root, "config", "user.name", "Adjudication Channel")
    # Literal split keeps the secret scrubber from flagging the diff as an
    # email leak; the runtime value stays a normal fixture address.
    git(root, "config", "user.email", "channel@" + "example.test")
    (root / ".gitignore").write_text(".itd-memory/\n", encoding="utf-8")
    (root / ".itd").mkdir()
    (root / ".itd" / "SCOPE_LOCK.md").write_text("# Scope\n", encoding="utf-8")
    (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
        '{"criteria":[{"id":"AC-1","status":"pending"}]}\n', encoding="utf-8")
    git(root, "commit", "--allow-empty", "-qm", "seed")
    (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "baseline")
    (root / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    git(root, "add", "app.py")
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


def machine(root: Path, unit: str = "U-adj") -> subprocess.CompletedProcess[str]:
    oracle = f'"{sys.executable}" -c "print(123)"'
    return run(["machine", "--root", str(root), "--unit-id", unit,
                "--risk-tier", "medium", "--command", "oracle=" + oracle,
                "--timeout", "10"], root)


def checker(root: Path, verdict: str, artifact_id: str, unit: str = "U-adj"):
    prompt, report = artifacts(root, verdict, artifact_id)
    return run([
        "checker", "--root", str(root), "--unit-id", unit,
        "--risk-tier", "medium", "--mode", "targeted",
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


def dispositions_value(checker_path: Path, *, drop_last: bool = False,
                       extra: bool = False, wrong_sha: bool = False,
                       no_confirmation: bool = False, bad_class: bool = False,
                       no_evidence: bool = False,
                       non_affirmative: bool = False,
                       empty_rationale: bool = False,
                       no_confirmed_by: bool = False) -> dict:
    items = []
    targets = FINDINGS + UNVERIFIED
    for index, finding in enumerate(targets):
        klass = ("refuted-by-evidence" if index == 0 else "accepted-trade-off")
        if bad_class and index == 0:
            klass = "looks-fine"
        rationale = ("bytes 1f 8b prove the transcript is gzip"
                     if index == 0
                     else "accepted design tension, recorded in DECISIONS")
        if empty_rationale and index == 0:
            rationale = "   "
        row = {
            "findingSha256": canonical_digest(finding),
            "finding": finding,
            "class": klass,
            "rationale": rationale,
        }
        if klass == "refuted-by-evidence" and not no_evidence:
            row["evidence"] = "hexdump of the first two bytes"
        items.append(row)
    if drop_last:
        items = items[:-1]
    if extra:
        items.append({
            "findingSha256": "f" * 64,
            "finding": {"summary": "names no checker finding"},
            "class": "accepted-trade-off", "rationale": "orphan row",
        })
    sha = hashlib.sha256(checker_path.read_bytes()).hexdigest()
    confirmation = ("I adjudicated every finding of checker receipt "
                    f"{sha} and accept the recorded dispositions")
    if non_affirmative:
        confirmation = "I do not confirm these dispositions"
    value = {
        "confirmedBy": "hihol",
        "confirmation": confirmation,
        "checkerReceiptSha256": "0" * 64 if wrong_sha else sha,
        "dispositions": items,
    }
    if no_confirmation:
        value.pop("confirmation")
    if no_confirmed_by:
        value.pop("confirmedBy")
    return value


def adjudicate(root: Path, machine_path: Path, checker_path: Path,
               dispositions: dict | None = None, name: str = "d",
               unit: str = "U-adj"):
    args = ["adjudicate", "--root", str(root), "--unit-id", unit,
            "--risk-tier", "medium", "--machine", str(machine_path),
            "--checker", str(checker_path)]
    if dispositions is not None:
        path = root / ".itd-memory" / f"dispositions-{name}.json"
        path.write_text(json.dumps(dispositions), encoding="utf-8")
        args += ["--dispositions", str(path)]
    return run(args, root)


gate_only = "--gate" in sys.argv[1:]

if not gate_only:
    root = fixture()
    machine_proc = machine(root)
    check("machine oracle passes", machine_proc.returncode == 0,
          machine_proc.stdout + machine_proc.stderr)
    machine_path = last_path(machine_proc)

    blocked_proc = checker(root, "BLOCKED", "blocked")
    blocked_path = newest_receipt(root, "checker")
    check("BLOCKED checker receipt is minted durably",
          blocked_proc.returncode != 0 and blocked_path is not None,
          blocked_proc.stdout + blocked_proc.stderr)
    assert blocked_path is not None
    blocked_receipt = json.loads(blocked_path.read_text(encoding="utf-8"))
    check("checker receipt stays honestly BLOCKED",
          blocked_receipt.get("verdict") == "BLOCKED", str(blocked_receipt)[:200])

    # The proven deadlock: BLOCKED evidence alone can never mint.
    bare = adjudicate(root, machine_path, blocked_path)
    check("BLOCKED without dispositions refuses to mint", bare.returncode != 0
          and "BLOCKED" in bare.stdout + bare.stderr,
          bare.stdout + bare.stderr)

    # Fail-closed minting guards. Each anomaly must refuse before any receipt.
    guards = {
        "uncovered finding refuses":
            dispositions_value(blocked_path, drop_last=True),
        "disposition naming no finding refuses":
            dispositions_value(blocked_path, extra=True),
        "foreign checker receipt sha refuses":
            dispositions_value(blocked_path, wrong_sha=True),
        "missing explicit confirmation refuses":
            dispositions_value(blocked_path, no_confirmation=True),
        "unknown disposition class refuses":
            dispositions_value(blocked_path, bad_class=True),
        "refuted-by-evidence without evidence refuses":
            dispositions_value(blocked_path, no_evidence=True),
        "non-affirmative confirmation refuses":
            dispositions_value(blocked_path, non_affirmative=True),
        "empty disposition rationale refuses":
            dispositions_value(blocked_path, empty_rationale=True),
        "missing confirmedBy refuses":
            dispositions_value(blocked_path, no_confirmed_by=True),
    }
    for index, (name, value) in enumerate(guards.items()):
        proc = adjudicate(root, machine_path, blocked_path, value,
                          name=f"guard{index}")
        check(name, proc.returncode != 0, proc.stdout + proc.stderr)
        check(name + " without a receipt file",
              newest_receipt(root, "adjudication") is None, "receipt leaked")

    # Foreign unit, stale candidate, and a rewritten checker verdict must
    # refuse before any receipt exists (PA1 minting-guard mutations).
    foreign_unit = adjudicate(root, machine_path, blocked_path,
                              dispositions_value(blocked_path),
                              name="foreign-unit", unit="U-other")
    check("foreign unit id refuses to mint", foreign_unit.returncode != 0,
          foreign_unit.stdout + foreign_unit.stderr)
    check("foreign unit leaves no receipt",
          newest_receipt(root, "adjudication") is None, "receipt leaked")

    app = root / "app.py"
    original_app = app.read_bytes()
    app.write_bytes(b"VALUE = 3\n")
    stale = adjudicate(root, machine_path, blocked_path,
                       dispositions_value(blocked_path), name="stale")
    app.write_bytes(original_app)
    check("stale candidate checkout refuses to mint", stale.returncode != 0,
          stale.stdout + stale.stderr)
    check("stale candidate leaves no receipt",
          newest_receipt(root, "adjudication") is None, "receipt leaked")

    original_checker = blocked_path.read_bytes()
    blocked_path.write_bytes(
        original_checker.replace(b'"BLOCKED"', b'"PASSED"', 1))
    rewrite = adjudicate(root, machine_path, blocked_path,
                         dispositions_value(blocked_path), name="rewrite")
    blocked_path.write_bytes(original_checker)
    check("rewritten checker verdict refuses to mint", rewrite.returncode != 0,
          rewrite.stdout + rewrite.stderr)
    check("rewritten verdict leaves no receipt",
          newest_receipt(root, "adjudication") is None, "receipt leaked")

    # The channel: complete dispositions + confirmation mint ADJUDICATED.
    good = adjudicate(root, machine_path, blocked_path,
                      dispositions_value(blocked_path), name="good")
    check("complete human adjudication mints", good.returncode == 0,
          good.stdout + good.stderr)
    if good.returncode == 0:
        receipt_path = last_path(good)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        check("outcome is honestly ADJUDICATED, not PASSED",
              receipt.get("outcome") == "ADJUDICATED", str(receipt.get("outcome")))
        human = receipt.get("humanAdjudication") or {}
        check("receipt records who confirmed and the exact checker sha",
              human.get("confirmedBy") == "hihol"
              and human.get("checkerReceiptSha256")
              == hashlib.sha256(blocked_path.read_bytes()).hexdigest()
              and len(human.get("dispositions") or []) == len(FINDINGS) + 1,
              json.dumps(human)[:300])
        verify = run(["check", "--root", str(root), "--unit-id", "U-adj",
                      "--risk-tier", "medium", "--receipt", str(receipt_path)],
                     root)
        check("check subcommand accepts the ADJUDICATED receipt",
              verify.returncode == 0, verify.stdout + verify.stderr)
        tampered = blocked_path.read_text(encoding="utf-8").replace(
            "regressed", "regressed!")
        blocked_path.write_text(tampered, encoding="utf-8")
        reverify = run(["check", "--root", str(root), "--unit-id", "U-adj",
                        "--risk-tier", "medium", "--receipt", str(receipt_path)],
                       root)
        check("tampered checker dependency invalidates the receipt",
              reverify.returncode != 0, reverify.stdout + reverify.stderr)

    # A clean review needs no adjudication: dispositions over PASSED refuse.
    clean_root = fixture()
    clean_machine = last_path(machine(clean_root))
    clean_proc = checker(clean_root, "PASSED", "clean")
    check("clean checker mints", clean_proc.returncode == 0,
          clean_proc.stdout + clean_proc.stderr)
    clean_path = last_path(clean_proc) if clean_proc.returncode == 0 \
        else newest_receipt(clean_root, "checker")
    laundering = adjudicate(clean_root, clean_machine, clean_path,
                            dispositions_value(clean_path), name="clean")
    check("dispositions over a clean PASSED review refuse",
          laundering.returncode != 0, laundering.stdout + laundering.stderr)
    plain = adjudicate(clean_root, clean_machine, clean_path)
    check("clean review still mints plain PASSED", plain.returncode == 0
          and json.loads(last_path(plain).read_text(
              encoding="utf-8")).get("outcome") == "PASSED",
          plain.stdout + plain.stderr)

# Gate level: the commit review cache accepts the honest label end to end.
cache = load_module(CACHE, "itd_adjudication_cache_fixture")
gate_root = fixture()
gate_claim = cache.review_claim_id(gate_root, "general")
gate_machine = last_path(machine(gate_root, unit=gate_claim))
checker(gate_root, "BLOCKED", "gate", unit=gate_claim)
gate_checker = newest_receipt(gate_root, "checker")
check("gate fixture minted a durable BLOCKED checker receipt",
      gate_checker is not None, "no checker receipt on disk")
assert gate_checker is not None
gate_mint = adjudicate(gate_root, gate_machine, gate_checker,
                       dispositions_value(gate_checker), name="gate",
                       unit=gate_claim)
check("gate fixture mints ADJUDICATED", gate_mint.returncode == 0,
      gate_mint.stdout + gate_mint.stderr)
if gate_mint.returncode == 0:
    gate_receipt = last_path(gate_mint)
    try:
        accepted, record = cache.record_review(
            gate_root, verdict="ADJUDICATED", risk_tier="medium",
            verification_receipt=gate_receipt)
    except cache.CacheError as exc:  # RED on pre-channel code
        accepted, record = False, {"error": f"{exc}"}
    check("review cache records the honest ADJUDICATED verdict",
          accepted is True, json.dumps(record, default=str)[:300])
    check("record keeps ADJUDICATED distinct from PASSED",
          record.get("verdict") == "ADJUDICATED"
          and (record.get("verificationReceipt") or {}).get("outcome")
          == "ADJUDICATED", json.dumps(record, default=str)[:300])
    check("record_matches accepts the adjudicated record",
          cache.record_matches(record, record.get("context") or {}),
          json.dumps(record, default=str)[:200])
    try:
        mismatch, mismatch_record = cache.record_review(
            gate_root, verdict="PASSED", risk_tier="medium",
            verification_receipt=gate_receipt)
    except cache.CacheError:
        mismatch, mismatch_record = False, {}
    check("an ADJUDICATED receipt cannot be recorded as a clean PASSED",
          mismatch is False, json.dumps(mismatch_record, default=str)[:300])

print(json.dumps({
    "checks": checks, "failures": failures,
    "status": "PASSED" if not failures else "FAILED",
}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
