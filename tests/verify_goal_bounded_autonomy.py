#!/usr/bin/env python3
"""Behavioural contract for the opt-in bounded `/goal` run envelope."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
REPORT = ROOT / "skills" / "goal" / "scripts" / "itd_goal_report.py"
VALIDATE = ROOT / "scripts" / "validate_state.py"
LOOP = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
PY = sys.executable
RESULT_CMD = (
    f'"{PY}" -c "import pathlib,sys; '
    "ok=pathlib.Path('result.txt').read_text().strip()=='pass'; "
    "print('pass' if ok else 'fail'); sys.exit(0 if ok else 1)\""
)

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        [PY, str(script), *args], cwd=str(cwd), capture_output=True,
        encoding="utf-8", errors="replace", env=env, timeout=60)


def make_goal(root: Path, *, attempts: int = 2, wall: int = 3600,
              tokens: int = 1000, review: bool = True,
              enforce_tokens: bool = False, adaptive: bool = False,
              risk_tier: str = "medium") -> Path:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Goal Fixture"],
                   cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "goal@example.test"],
                   cwd=root, check=True)
    (root / ".gitignore").write_text(
        ".itd-memory/\n.claude/\nresult.txt\n", encoding="utf-8")
    (root / ".itd").mkdir()
    (root / ".itd" / "SCOPE_LOCK.md").write_text("# Goal fixture\n", encoding="utf-8")
    (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
        '{"criteria":[{"id":"AC-1","status":"pending"}]}\n',
        encoding="utf-8")
    (root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
    mem = root / ".itd-memory"
    mem.mkdir(parents=True)
    (root / "result.txt").write_text("fail", encoding="utf-8")
    goal = {
        "version": 1,
        "goal": "Bounded autonomy fixture",
        "status": "active",
        "createdAt": "2026-07-14T00:00:00Z",
        "updatedAt": "2026-07-14T00:00:00Z",
        "currentUnitId": "",
        "runPolicy": {
            "mode": "bounded_autonomous",
            "maxAttemptsPerUnit": attempts,
            "maxWallClockSecondsPerUnit": wall,
            "maxTokensPerSession": tokens,
            "freezeVerification": True,
            "requireApproach": True,
            "requireIndependentReview": review,
            "enforceObservedTokens": enforce_tokens,
        },
        "units": [{
            "id": "G-001",
            "criterion": "result fixture passes",
            "verificationCommand": RESULT_CMD,
            "status": "pending",
            "verifiedAt": "",
            "evidence": "",
            "skippedReason": "",
            "blockedReason": "",
            **({"riskTier": risk_tier} if adaptive else {}),
        }],
    }
    if adaptive:
        goal["runPolicy"]["verificationStrategy"] = "adaptive"
        goal["runPolicy"]["maxCheckpointBytes"] = 4096
    path = mem / "GOAL.json"
    path.write_text(json.dumps(goal, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def unit(path: Path) -> dict:
    return load(path)["units"][0]


def rel() -> str:
    return os.path.join(".itd-memory", "GOAL.json")


def seal_and_activate(root: Path) -> tuple[subprocess.CompletedProcess, subprocess.CompletedProcess]:
    sealed = run(VERIFY, "--goal", rel(), "--seal", cwd=root)
    active = run(VERIFY, "--goal", rel(), "--activate", "G-001", cwd=root)
    return sealed, active


def last_path(proc: subprocess.CompletedProcess) -> Path:
    return Path(proc.stdout.strip().splitlines()[-1])


def make_verification_receipt(root: Path, risk_tier: str) -> Path:
    """Produce the same proof chain a real goal run must consume."""
    base = root / ".itd-memory" / "verification-loop"
    prompt = base / "prompts" / "G-001.md"
    report = base / "reports" / "G-001.md"
    prompt.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text(
        "Review the exact candidate independently and return canonical JSON.\n",
        encoding="utf-8")
    report.write_text(
        "# Independent review\n\n```json\n"
        + json.dumps({"verdict": "PASSED", "findings": [], "unverified": []})
        + "\n```\n", encoding="utf-8")
    machine = run(
        LOOP, "machine", "--root", str(root), "--unit-id", "G-001",
        "--risk-tier", risk_tier, "--command", "oracle=" + RESULT_CMD,
        "--input", "result.txt",
        cwd=root)
    if machine.returncode != 0:
        raise AssertionError(machine.stdout + machine.stderr)
    mode = "targeted" if risk_tier == "medium" else "full"
    checker = run(
        LOOP, "checker", "--root", str(root), "--unit-id", "G-001",
        "--risk-tier", risk_tier, "--mode", mode,
        "--report", str(report), "--prompt-file", str(prompt),
        "--maker-provider", "openai", "--maker-model", "gpt-maker",
        "--maker-session", "maker-session",
        "--checker-provider", "openai", "--checker-model", "gpt-checker",
        "--checker-session", "checker-session", cwd=root)
    if checker.returncode != 0:
        raise AssertionError(checker.stdout + checker.stderr)
    adjudication = run(
        LOOP, "adjudicate", "--root", str(root), "--unit-id", "G-001",
        "--risk-tier", risk_tier, "--machine", str(last_path(machine)),
        "--checker", str(last_path(checker)), cwd=root)
    if adjudication.returncode != 0:
        raise AssertionError(adjudication.stdout + adjudication.stderr)
    return last_path(adjudication)


# Oracle must be sealed after approval, never inferred during activation.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root)
    r = run(VERIFY, "--goal", rel(), "--activate", "G-001", cwd=root)
    check("activation refuses an unsealed oracle",
          r.returncode == 1 and unit(path)["status"] == "pending" and "seal" in r.stdout.lower(),
          r.stdout + r.stderr)
    r = run(VERIFY, "--goal", rel(), "--seal", cwd=root)
    data = load(path)
    check("seal freezes policy and unit verifier",
          r.returncode == 0
          and data["runPolicy"]["sealedFingerprint"].startswith("sha256:")
          and data["runPolicy"]["sealedPolicy"]["maxAttemptsPerUnit"] == 2
          and data["units"][0]["runState"]["verificationFingerprint"].startswith("sha256:"))
    rv = run(VALIDATE, str(path), cwd=root)
    check("sealed bounded ledger validates", rv.returncode == 0, rv.stdout + rv.stderr)
    data["units"][0]["criterion"] = "mutated after approval"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "--activate", "G-001", cwd=root)
    check("post-approval oracle mutation blocks",
          r.returncode == 3 and unit(path)["status"] == "blocked"
          and unit(path)["runState"]["stopReason"] == "blocked", r.stdout + r.stderr)


# Attempts require an approach/checker, persist failures, and stop at the cap.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, attempts=3, review=True)
    seal_and_activate(root)
    r = run(VERIFY, "--goal", rel(), "G-001",
            "--review-evidence", "fresh reviewer PASSED", cwd=root)
    check("bounded attempt requires approach", r.returncode == 1 and not unit(path)["attempts"])
    (root / "result.txt").write_text("pass", encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "try A", cwd=root)
    check("policy can require independent checker evidence",
          r.returncode == 1 and len(unit(path)["attempts"]) == 1
          and unit(path)["attempts"][0]["outcome"] == "unverified")
    rv = run(VALIDATE, str(path), cwd=root)
    check("missing-checker attempt leaves a valid ledger",
          rv.returncode == 0, rv.stdout + rv.stderr)
    (root / "result.txt").write_text("fail", encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "try A", cwd=root)
    u = unit(path)
    check("failed attempt is journaled and remains active",
          r.returncode == 1 and u["status"] == "in_progress"
          and len(u["attempts"]) == 2 and u["attempts"][1]["approach"] == "try A")
    rv = run(VALIDATE, str(path), cwd=root)
    check("machine-red attempt leaves a valid ledger",
          rv.returncode == 0, rv.stdout + rv.stderr)
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "try B", cwd=root)
    u = unit(path)
    check("attempt cap produces typed budget stop",
          r.returncode == 3 and u["status"] == "blocked"
          and u["runState"]["stopReason"] == "budget_exhausted"
          and u["runState"]["exhaustedBudget"]["kind"] == "attempts"
          and len(u["attempts"]) == 3, r.stdout + r.stderr)
    r = run(VERIFY, "--goal", rel(), "--activate", "G-001",
            "--reason", "retry unchanged", cwd=root)
    check("budget resume refuses unchanged limit", r.returncode == 1, r.stdout + r.stderr)
    data = load(path)
    data["runPolicy"]["maxAttemptsPerUnit"] = 4
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "result.txt").write_text("pass", encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "--activate", "G-001",
            "--reason", "human approved one more attempt", cwd=root)
    check("increased exhausted budget can be explicitly resumed", r.returncode == 0,
          r.stdout + r.stderr)
    receipt = make_verification_receipt(root, "unknown")
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "try C",
            "--verification-receipt", str(receipt), cwd=root)
    u = unit(path)
    check("resumed attempt can verify with full evidence",
          r.returncode == 0 and u["status"] == "verified"
          and u["runState"]["stopReason"] == "verified" and len(u["attempts"]) == 4,
          r.stdout + r.stderr)
    verified = load(path)
    rv = run(VALIDATE, str(path), cwd=root)
    check("verified receipt chain validates from durable state",
          rv.returncode == 0, rv.stdout + rv.stderr)
    binding = verified["units"][0]["attempts"][-1]["verificationReceipt"]
    for label, field, value in (
            ("missing receipt path", "path", "missing/adjudication.json"),
            ("forged receipt file hash", "sha256", "0" * 64),
            ("forged receipt digest", "receiptSha256", "0" * 64)):
        mutated = json.loads(json.dumps(verified))
        mutated["units"][0]["attempts"][-1]["verificationReceipt"][field] = value
        if field == "receiptSha256":
            mutated["units"][0]["attempts"][-1]["reviewEvidence"] = "adjudicated:" + value
        path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
        rv = run(VALIDATE, str(path), cwd=root)
        check(f"state validator rejects {label}", rv.returncode == 1,
              rv.stdout + rv.stderr)
    path.write_text(json.dumps(verified, ensure_ascii=False, indent=2), encoding="utf-8")
    receipt_file = root / binding["path"]
    receipt_bytes = receipt_file.read_bytes()
    receipt_file.write_bytes(receipt_bytes + b"\n")
    rv = run(VALIDATE, str(path), cwd=root)
    check("state validator rejects a changed receipt file",
          rv.returncode == 1, rv.stdout + rv.stderr)
    receipt_file.write_bytes(receipt_bytes)


# Rechecks are budgeted executions too.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, attempts=2, review=False)
    (root / "result.txt").write_text("pass", encoding="utf-8")
    seal_and_activate(root)
    run(VERIFY, "--goal", rel(), "G-001", "--approach", "initial", cwd=root)
    r = run(VERIFY, "--goal", rel(), "--recheck", "G-001",
            "--approach", "first recheck", cwd=root)
    check("successful recheck consumes the attempt budget",
          r.returncode == 0 and len(unit(path)["attempts"]) == 2)
    r = run(VERIFY, "--goal", rel(), "--recheck", "G-001",
            "--approach", "unbounded recheck", cwd=root)
    check("recheck cannot bypass exhausted attempt budget",
          r.returncode == 3 and len(unit(path)["attempts"]) == 2
          and unit(path)["runState"]["stopReason"] == "budget_exhausted")


# A failing final-budget recheck must materialize the stop immediately.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, attempts=2, review=False)
    (root / "result.txt").write_text("pass", encoding="utf-8")
    seal_and_activate(root)
    run(VERIFY, "--goal", rel(), "G-001", "--approach", "initial", cwd=root)
    (root / "result.txt").write_text("fail", encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "--recheck", "G-001",
            "--approach", "final recheck", cwd=root)
    u = unit(path)
    check("failing final-budget recheck stops in the same invocation",
          r.returncode == 3 and u["status"] == "blocked"
          and u["runState"]["stopReason"] == "budget_exhausted"
          and len(u["attempts"]) == 2
          and u["attempts"][-1]["outcome"] == "regressed",
          r.stdout + r.stderr)


# Host-observed token ceilings require a typed stop and a real limit increase.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, tokens=1000, review=False)
    seal_and_activate(root)
    r = run(VERIFY, "--goal", rel(), "--budget-exhausted", "G-001",
            "--budget-kind", "tokens", "--reason", "host ceiling reached", cwd=root)
    check("token stop refuses an unproved host assertion",
          r.returncode == 1 and unit(path)["status"] == "in_progress",
          r.stdout + r.stderr)
    r = run(VERIFY, "--goal", rel(), "--budget-exhausted", "G-001",
            "--budget-kind", "tokens", "--budget-observed", "999",
            "--reason", "host ceiling reached", cwd=root)
    check("token stop refuses an observation below the sealed limit",
          r.returncode == 1 and unit(path)["status"] == "in_progress",
          r.stdout + r.stderr)
    r = run(VERIFY, "--goal", rel(), "--budget-exhausted", "G-001",
            "--budget-kind", "tokens", "--budget-observed", "1000",
            "--reason", "host ceiling reached", cwd=root)
    check("host token ceiling becomes a typed stop",
          r.returncode == 3
          and unit(path)["runState"]["exhaustedBudget"]["kind"] == "tokens"
          and unit(path)["runState"]["exhaustedBudget"]["observed"] == 1000)
    r = run(VERIFY, "--goal", rel(), "--activate", "G-001",
            "--reason", "same token budget", cwd=root)
    check("token stop cannot resume under the same ceiling", r.returncode == 1)
    data = load(path)
    data["runPolicy"]["maxTokensPerSession"] = 1500
    data["runPolicy"]["requireIndependentReview"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "--activate", "G-001",
            "--reason", "attempt an overbroad policy change", cwd=root)
    check("budget resume rejects unrelated policy changes", r.returncode == 1,
          r.stdout + r.stderr)
    data = load(path)
    data["runPolicy"]["requireIndependentReview"] = False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "--activate", "G-001",
            "--reason", "human approved only 1500 tokens", cwd=root)
    check("token stop resumes only after a higher approved ceiling", r.returncode == 0,
          r.stdout + r.stderr)


# A policy may require cumulative host token evidence on every verification.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, tokens=1000, review=False, enforce_tokens=True)
    seal_and_activate(root)
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "missing meter", cwd=root)
    check("token-enforced verification requires an observation",
          r.returncode == 1 and not unit(path)["attempts"], r.stdout + r.stderr)
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "at ceiling",
            "--tokens-used", "1000", cwd=root)
    check("observed token ceiling stops before command execution",
          r.returncode == 3 and not unit(path)["attempts"]
          and unit(path)["runState"]["exhaustedBudget"]["observed"] == 1000,
          r.stdout + r.stderr)


# Wall-clock budget stops before executing another command.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, wall=1, review=False)
    seal_and_activate(root)
    data = load(path)
    data["units"][0]["runState"]["startedAt"] = "2020-01-01T00:00:00Z"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "too late", cwd=root)
    check("wall-clock cap stops without spending an attempt",
          r.returncode == 3 and not unit(path)["attempts"]
          and unit(path)["runState"]["exhaustedBudget"]["kind"] == "wall_clock")


# Adaptive checker policy is sealed by risk tier instead of always doubling work.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, review=False, adaptive=True, risk_tier="low")
    (root / "result.txt").write_text("pass", encoding="utf-8")
    seal_and_activate(root)
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "machine gates", cwd=root)
    check("low-risk adaptive verification needs no full checker",
          r.returncode == 0 and unit(path)["attempts"][0]["checkerMode"] == "machine_only",
          r.stdout + r.stderr)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, review=False, adaptive=True, risk_tier="high")
    (root / "result.txt").write_text("pass", encoding="utf-8")
    seal_and_activate(root)
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "unsafe shortcut", cwd=root)
    check("high-risk adaptive verification requires a full checker",
          r.returncode == 1 and len(unit(path)["attempts"]) == 1
          and unit(path)["attempts"][0]["outcome"] == "unverified",
          r.stdout + r.stderr)
    receipt = make_verification_receipt(root, "high")
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "checked",
            "--verification-receipt", str(receipt), cwd=root)
    check("high-risk adaptive verification records checker mode",
          r.returncode == 0 and unit(path)["attempts"][0]["checkerMode"] == "full",
          r.stdout + r.stderr)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, review=False, adaptive=True, risk_tier="medium")
    (root / "result.txt").write_text("pass", encoding="utf-8")
    seal_and_activate(root)
    receipt = make_verification_receipt(root, "medium")
    r = run(VERIFY, "--goal", rel(), "G-001", "--approach", "residual only",
            "--verification-receipt", str(receipt), cwd=root)
    check("medium-risk adaptive verification selects targeted checker",
          r.returncode == 0 and unit(path)["attempts"][0]["checkerMode"] == "targeted",
          r.stdout + r.stderr)
    r = run(REPORT, "--goal", rel(), "--compact", cwd=root)
    check("compact checkpoint carries only bounded handoff fields",
          r.returncode == 0 and len(r.stdout.encode("utf-8")) <= 4096
          and all(label in r.stdout for label in
                  ("Done", "Evidence", "Status", "Open risks", "Next"))
          and "<details>" not in r.stdout,
          r.stdout + r.stderr)


# Reporter exposes the envelope; malformed opt-in policy fails closed.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, review=False)
    r = run(REPORT, "--goal", rel(), cwd=root)
    check("handoff report exposes an unsealed oracle honestly",
          "oracle=UNSEALED" in r.stdout)
    seal_and_activate(root)
    r = run(REPORT, "--goal", rel(), cwd=root)
    check("handoff report exposes bounded budgets", "**Bounded autonomy:**" in r.stdout)
    sealed = load(path)
    tampered = json.loads(json.dumps(sealed))
    tampered["runPolicy"]["sealedFingerprint"] = "sha256:" + ("0" * 64)
    path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(REPORT, "--goal", rel(), cwd=root)
    check("handoff report rejects a forged policy seal", "oracle=UNSEALED" in r.stdout)
    tampered = json.loads(json.dumps(sealed))
    tampered["units"][0]["criterion"] = "tampered oracle"
    path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(REPORT, "--goal", rel(), cwd=root)
    check("handoff report rejects a changed unit oracle", "oracle=UNSEALED" in r.stdout)
    path.write_text(json.dumps(sealed, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(REPORT, "--goal", rel(), "--json", cwd=root)
    report = json.loads(r.stdout)
    check("JSON report exposes attempts and stop reason",
          report["runPolicy"]["mode"] == "bounded_autonomous"
          and report["oracleSealed"] is True
          and report["units"][0]["attempts"] == 0)
    data = load(path)
    data["runPolicy"]["freezeVerification"] = False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VALIDATE, str(path), cwd=root)
    check("validator rejects a weakened bounded policy", r.returncode == 1,
          r.stdout + r.stderr)


# Scheduled timeout must cover the declared worst-case 24-minute probe budget.
workflow = (ROOT / ".github" / "workflows" / "hygiene-schedule.yml").read_text(
    encoding="utf-8")
check("weekly CI timeout covers the 24-minute probe budget",
      "weekly:\n" in workflow and "timeout-minutes: 30" in workflow)


print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("ALL PASS")
