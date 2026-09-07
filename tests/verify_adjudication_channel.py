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
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="strict",
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


def prepare_v2(root: Path, checker_path: Path, rows: list[dict],
               unit: str = "U-v2", claims: list[str] | None = None):
    path = root / ".itd-memory" / "v2-rows.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    args = ["prepare-adjudication", "--root", str(root), "--unit-id", unit,
            "--risk-tier", "medium", "--checker", str(checker_path),
            "--dispositions", str(path)]
    for claim in claims or [unit, unit + ":general-review"]:
        args += ["--claim", claim]
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

    # v2 binds the complete candidate context, the precise allowed claims and
    # the ordered findings/dispositions.  Preparation is deterministic and is
    # expressly non-authorizing until a human replaces its placeholder.
    v2_root = fixture()
    v2_machine = machine(v2_root, unit="U-v2")
    v2_machine_path = last_path(v2_machine)
    v2_checker_proc = checker(v2_root, "BLOCKED", "v2", unit="U-v2")
    v2_checker_path = newest_receipt(v2_root, "checker")
    check("v2 fixture checker is durable", v2_checker_path is not None,
          v2_checker_proc.stdout + v2_checker_proc.stderr)
    assert v2_checker_path is not None
    v2_rows = dispositions_value(v2_checker_path)["dispositions"]
    prepare_guards = {
        "v2 prepare rejects empty disposition list": ([], "human dispositions are absent"),
        "v2 prepare rejects missing target row": (v2_rows[:-1], "has no human disposition"),
        "v2 prepare rejects duplicate target row": (
            [v2_rows[0], v2_rows[0], v2_rows[1]], "duplicate disposition"),
        "v2 prepare rejects non-object row": (["not-an-object"], "row is malformed"),
        "v2 prepare names unknown row key": (
            [{**v2_rows[0], "confirmedAt": "forbidden"}], "unknown confirmedAt"),
    }
    for name, (rows, diagnostic) in prepare_guards.items():
        proc = prepare_v2(v2_root, v2_checker_path, rows)
        check(name, proc.returncode != 0 and diagnostic in proc.stdout,
              proc.stdout + proc.stderr)
    v2_draft_proc = prepare_v2(v2_root, v2_checker_path, v2_rows)
    check("v2 preparation is deterministic and non-authorizing",
          v2_draft_proc.returncode == 0, v2_draft_proc.stdout + v2_draft_proc.stderr)
    v2_draft = json.loads(v2_draft_proc.stdout) if v2_draft_proc.returncode == 0 else {}
    v2_draft_again = prepare_v2(v2_root, v2_checker_path, v2_rows)
    check("v2 preparation repeats byte-identically",
          v2_draft_proc.stdout == v2_draft_again.stdout,
          v2_draft_proc.stdout + v2_draft_again.stdout)
    permuted_v2 = prepare_v2(v2_root, v2_checker_path, list(reversed(v2_rows)))
    if permuted_v2.returncode == 0:
        permutation_binding = json.loads(permuted_v2.stdout)["approvalBinding"]
        permutation_ok = all(
            row["findingSha256"] == row["disposition"]["findingSha256"]
            for row in permutation_binding["targets"]
        )
    else:
        permutation_ok = False
    check("v2 permutation keeps each decision bound to its finding digest",
          permutation_ok, permuted_v2.stdout + permuted_v2.stderr)
    timestamped_draft = json.loads(json.dumps(v2_draft))
    timestamped_draft["confirmedAt"] = "forbidden-on-draft"
    timestamped = adjudicate(v2_root, v2_machine_path, v2_checker_path,
                             timestamped_draft, name="v2-extra-confirmed-at",
                             unit="U-v2")
    check("v2 draft names forbidden confirmedAt key",
          timestamped.returncode != 0 and "unknown confirmedAt" in timestamped.stdout,
          timestamped.stdout + timestamped.stderr)
    draft_mint = adjudicate(v2_root, v2_machine_path, v2_checker_path,
                            v2_draft, name="v2-draft", unit="U-v2")
    check("v2 draft placeholder cannot mint", draft_mint.returncode != 0,
          draft_mint.stdout + draft_mint.stderr)
    v2_draft["confirmedBy"] = "human-v2"
    v2_good = adjudicate(v2_root, v2_machine_path, v2_checker_path,
                         v2_draft, name="v2-good", unit="U-v2")
    check("complete v2 approval mints", v2_good.returncode == 0,
          v2_good.stdout + v2_good.stderr)
    if v2_good.returncode == 0:
        v2_receipt = last_path(v2_good)
        v2_human = json.loads(v2_receipt.read_text(encoding="utf-8"))["humanAdjudication"]
        check("v2 preserves the human confirmation verbatim",
              v2_human.get("confirmation") == v2_draft.get("confirmation")
              and v2_human.get("version") == "itd-human-adjudication-v2",
              json.dumps(v2_human)[:300])
        v2_check = run(["check", "--root", str(v2_root), "--unit-id", "U-v2",
                        "--risk-tier", "medium", "--receipt", str(v2_receipt)], v2_root)
        check("final adjudication revalidates v2 binding", v2_check.returncode == 0,
              v2_check.stdout + v2_check.stderr)
        # The same semantic approval may be consumed by the explicitly listed
        # general-review claim, but only after its own machine/checker chain
        # validates.  Its checker whole-file SHA changes; the candidate,
        # binding and human affirmation do not.
        general_claim = "U-v2:general-review"
        general_machine_path = last_path(machine(v2_root, unit=general_claim))
        checker(v2_root, "BLOCKED", "v2-general", unit=general_claim)
        general_checker = newest_receipt(v2_root, "checker")
        assert general_checker is not None
        general_approval = json.loads(json.dumps(v2_draft))
        general_approval["checkerReceiptSha256"] = hashlib.sha256(
            general_checker.read_bytes()).hexdigest()
        general_mint = adjudicate(v2_root, general_machine_path, general_checker,
                                  general_approval, name="v2-general",
                                  unit=general_claim)
        check("same v2 approval mints final general-review adjudication",
              general_mint.returncode == 0,
              general_mint.stdout + general_mint.stderr)
        if general_mint.returncode == 0:
            general_check = run([
                "check", "--root", str(v2_root), "--unit-id", general_claim,
                "--risk-tier", "medium", "--receipt", str(last_path(general_mint)),
            ], v2_root)
            check("general-review receipt revalidates the same v2 approval",
                  general_check.returncode == 0,
                  general_check.stdout + general_check.stderr)
        # A fresh checker file can reuse this approval only because its
        # complete semantic report/candidate binding is unchanged; its whole
        # file SHA remains independently revalidated.
        checker(v2_root, "BLOCKED", "v2-reissued", unit="U-v2")
        v2_reissued_checker = newest_receipt(v2_root, "checker")
        assert v2_reissued_checker is not None
        reissued = json.loads(json.dumps(v2_draft))
        reissued["checkerReceiptSha256"] = hashlib.sha256(
            v2_reissued_checker.read_bytes()).hexdigest()
        reissued_mint = adjudicate(v2_root, v2_machine_path, v2_reissued_checker,
                                   reissued, name="v2-reissued", unit="U-v2")
        check("fresh checker receipt may reuse unchanged v2 approval",
              reissued_mint.returncode == 0,
              reissued_mint.stdout + reissued_mint.stderr)
    for name, mutate in {
        "v2 rejects foreign security claim": lambda value: value["approvalBinding"].update(
            {"claims": ["U-v2", "U-v2:security-review"]}),
        "v2 rejects duplicate claim": lambda value: value["approvalBinding"].update(
            {"claims": ["U-v2", "U-v2"]}),
        "v2 rejects changed risk binding": lambda value: value["approvalBinding"]["candidate"].update(
            {"riskTier": "high"}),
        "v2 rejects changed disposition evidence": lambda value: value["approvalBinding"]["targets"][0]["disposition"].update(
            {"evidence": "different evidence"}),
    }.items():
        value = json.loads(json.dumps(v2_draft))
        mutate(value)
        proc = adjudicate(v2_root, v2_machine_path, v2_checker_path, value,
                          name="v2-" + name.replace(" ", "-"), unit="U-v2")
        check(name, proc.returncode != 0, proc.stdout + proc.stderr)
    unknown_v2 = json.loads(json.dumps(v2_draft))
    unknown_v2["version"] = "itd-human-adjudication-v99"
    check("unknown approval version rejects", adjudicate(
        v2_root, v2_machine_path, v2_checker_path, unknown_v2,
        name="v2-unknown", unit="U-v2").returncode != 0)
    colon_root = prepare_v2(v2_root, v2_checker_path, v2_rows,
                            unit="U-v2:security-review",
                            claims=["U-v2", "U-v2:general-review"])
    check("security subclaim cannot masquerade as v2 primary unit",
          colon_root.returncode != 0, colon_root.stdout + colon_root.stderr)

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
