#!/usr/bin/env python3
"""Plan session 10 (ADR-016): one review per candidate.

The final candidate's adjudication receipt is minted under the bare active unit
id and the same file is accepted by every consumer while the reviewed tree and
the diff hash still match: the commit review cache, the DoD security gate, the
pre-push gate and `itd pr create` (committed-head after exactly one commit) and
the unit closure (goal harness). A receipt minted under a suffixed claim is
refused; a changed candidate is refused by every consumer; a strict candidate
whose review did not cover the security impact class keeps the security gate
closed. The texts of `/review` and `/cross-review` take the same Step 0 route
command as the other route skills. The machine-verified provenance of a ledger
close is tests/verify_close_provenance.py.

Run: sh skills/_shared/itd_py.sh tests/verify_one_review_per_candidate.py
"""
from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py"
LOOP = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
PRODUCER = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"
GOAL_VERIFY = ROOT / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
DOD_HOOK = ROOT / "hooks" / "check-dod-before-commit.sh"
CROSS_HOOK = ROOT / "hooks" / "cross-review-precommit.sh"
REVIEW_SKILL = ROOT / "skills" / "review" / "SKILL.md"
REVIEW_STRICT = ROOT / "skills" / "review" / "references" / "strict.md"
CROSS_SKILL = ROOT / "skills" / "cross-review" / "SKILL.md"
BUGFIX_SKILL = ROOT / "skills" / "bugfix" / "SKILL.md"
FIXTURE_PATH = ROOT / "tests" / "verification_loop_fixture.py"
UNIT = "U-one"

passed = 0
failed = 0
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}" + (f" - {detail}" if detail else ""))


def sh(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def git(cwd: Path, *args: str) -> str:
    proc = sh(["git", *args], cwd)
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + proc.stderr)
    return proc.stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_module(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@contextlib.contextmanager
def chdir(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


fixture_spec = importlib.util.spec_from_file_location("verification_loop_fixture", FIXTURE_PATH)
assert fixture_spec and fixture_spec.loader
fixture = importlib.util.module_from_spec(fixture_spec)
sys.modules[fixture_spec.name] = fixture
fixture_spec.loader.exec_module(fixture)
make_review_receipt = fixture.make_review_receipt

core = load_module("itd_review_cache_s10", CACHE)
loop = load_module("itd_verification_loop_s10", LOOP)
producer = load_module("itd_free_reviewer_producer_s10", PRODUCER)
goal_verify = load_module("itd_goal_verify_s10", GOAL_VERIFY)

ORACLE = f'"{sys.executable}" -c "pass"'


def review_policy(tier: str, classes: tuple[str, ...]) -> dict:
    return {
        "mode": "evidence-first", "riskTier": tier,
        "requiredImpactClasses": list(classes),
        "minimumIndependentReviewers": 0 if tier == "low" else 1,
        "explorer": "isolated-machine-oracle",
        "adjudicator": "sealed-host-union",
    }


def make_repo(root: Path, *, tier: str = "high",
              classes: tuple[str, ...] = ("correctness", "security"),
              unit: str = UNIT, followup_unit: str | None = None) -> None:
    """A strict project whose staged candidate touches an auth path."""
    git(root, "init", "-q")
    git(root, "config", "user.email", "one-review@example.test")
    git(root, "config", "user.name", "One Review")
    write(root / ".gitignore", ".itd-memory/\n")
    write(root / "CLAUDE.md", "# Project\nitd-route: strict\n")
    write(root / "base.txt", "baseline\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "baseline")
    write(root / "src" / "auth" / "login.py", "TOKEN_TTL = 60\n")
    write(root / "tests" / "test_login.py", "def test_ttl():\n    assert True\n")
    write(root / ".itd" / "SCOPE_LOCK.md", "# Scope\nStart from merged main `baseline`.\n")
    write(root / ".itd" / "ACCEPTANCE_CONTRACT.json", json.dumps({
        "version": 2, "criteria": [],
        "activeFollowup": {
            "unitId": followup_unit or unit, "status": "in_progress",
            "reviewPolicy": review_policy(tier, classes),
        },
    }, indent=2))
    git(root, "add", "-A")
    write(root / ".itd-memory" / "GOAL.json", json.dumps({
        "version": 1, "goal": "one review per candidate", "status": "active",
        "createdAt": "2026-10-30T00:00:00Z", "updatedAt": "2026-10-30T00:00:00Z",
        "currentUnitId": unit,
        "units": [{"id": unit, "riskTier": tier, "status": "in_progress",
                   "criterion": "one receipt", "verificationCommand": "true",
                   "verifiedAt": "", "evidence": "", "skippedReason": "",
                   "blockedReason": ""}],
    }))
    write(root / ".itd-memory" / "STATE.json", json.dumps({
        "sessionState": "ACTIVE",
        "currentUnit": {"id": unit, "riskTier": tier, "status": "in_progress"},
    }))


def dod_main(repo: Path) -> tuple[int, str]:
    """Run the DoD gate's main() on a `git commit` payload inside the repo."""
    dod = load_module("itd_dod_gate_s10", DOD_HOOK)
    dod.CACHE_SCRIPT = CACHE
    payload = json.dumps({"tool_name": "Bash", "tool_input": {
        "command": "git commit -m candidate", "description": ""}})
    out = io.StringIO()
    code = 0
    with chdir(repo), contextlib.redirect_stdout(out):
        sys.stdin = io.StringIO(payload)
        try:
            code = dod.main()
        except SystemExit as exc:
            code = int(exc.code or 0)
        finally:
            sys.stdin = sys.__stdin__
    return code, out.getvalue()


# ---------------------------------------------------------------------------
print("[1] one receipt, every consumer")
with tempfile.TemporaryDirectory(prefix="one-review-") as td:
    repo = Path(td).resolve()
    make_repo(repo)
    check("review_claim_id is the bare unit id for every review kind",
          core.review_claim_id(repo, "general") == UNIT
          and core.review_claim_id(repo, "security") == UNIT,
          core.review_claim_id(repo, "general"))
    receipt = make_review_receipt(repo, unit_id=UNIT, risk_tier="high", command=ORACLE)
    minted = json.loads(receipt.read_text(encoding="utf-8"))
    check("the receipt is minted under the bare unit id with a full checker",
          minted.get("unitId") == UNIT and minted.get("checkerMode") == "full",
          json.dumps({k: minted.get(k) for k in ("unitId", "checkerMode")}))

    accepted, record = core.record_review(
        repo, verdict="PASSED", kind="general", session="s10-one",
        verification_receipt=receipt)
    check("one general record from the final candidate's receipt unlocks the commit review cache",
          accepted and core.cache_allows(repo, kind="general") is True)
    check("the same record unlocks the security gate: the policy requires security and a checker ran",
          core.cache_allows(repo, kind="security") is True)
    cache_file = json.loads((repo / ".itd-memory" / "review-cache.json").read_text(encoding="utf-8"))
    general_bind = cache_file["records"]["general"]["verificationReceipt"]
    security_bind = cache_file["records"]["security"]["verificationReceipt"]
    check("both cache records bind the same receipt file, flagged as security-covered",
          general_bind == security_bind
          and general_bind["securityCoverage"] == "covered"
          and general_bind["claimId"] == UNIT, json.dumps(general_bind))
    check("the CLI check accepts the security kind on the same candidate",
          sh([sys.executable, str(CACHE), "check", "--root", str(repo),
              "--kind", "security"], ROOT).returncode == 0)
    core.record_review(repo, verdict="BLOCKED", kind="general", session="s10-one")
    check("a negative general verdict on the same candidate closes the security slot it had opened",
          core.cache_allows(repo, kind="general") is False
          and core.cache_allows(repo, kind="security") is False)
    accepted, record = core.record_review(
        repo, verdict="PASSED", kind="general", session="s10-one",
        verification_receipt=receipt)
    check("re-recording the accepted receipt reopens both slots",
          accepted and core.cache_allows(repo, kind="general") is True
          and core.cache_allows(repo, kind="security") is True)

    dod = load_module("itd_dod_gate_s10", DOD_HOOK)
    dod.CACHE_SCRIPT = CACHE
    with chdir(repo):
        dod_ok = dod.security_review_was_done()
    check("the DoD security gate accepts the same receipt", dod_ok is True)
    code, out = dod_main(repo)
    check("the DoD gate lets the commit of an auth path through without a second model call",
          code == 0 and '"deny"' not in out, f"rc={code} {out[:200]}")

    # pre-push and `itd pr create` validate the same file in committed-head mode
    git(repo, "commit", "-qm", "candidate")
    head_bound = ""
    try:
        loop.validate_adjudication(repo, receipt, "high", UNIT, candidate_mode="committed-head")
        head_bound = "bound"
    except loop.LoopError as exc:
        head_bound = f"UNVERIFIED: {exc.why}"
    check("after exactly one commit the same receipt validates in committed-head mode (pre-push, itd pr create)",
          head_bound == "bound", head_bound)

    goal_bound = ""
    try:
        goal_verify.validate_verification_receipt(
            repo / ".itd-memory" / "GOAL.json", str(receipt), "high", UNIT,
            candidate_mode="committed-head")
        goal_bound = "bound"
    except Exception as exc:  # noqa: BLE001 - the harness error type is its own
        goal_bound = f"refused: {exc}"
    check("the goal harness (unit closure) consumes the same receipt under the bare id",
          goal_bound == "bound", goal_bound)

    write(repo / "change-1.txt", "a changed candidate\n")
    git(repo, "add", "change-1.txt")
    git(repo, "commit", "-qm", "changed candidate")
    changed = ""
    try:
        loop.validate_adjudication(repo, receipt, "high", UNIT, candidate_mode="committed-head")
        changed = "accepted"
    except loop.LoopError as exc:
        changed = exc.why
    check("a changed candidate is refused by the committed-head consumers",
          changed != "accepted", changed)
    goal_changed = ""
    try:
        goal_verify.validate_verification_receipt(
            repo / ".itd-memory" / "GOAL.json", str(receipt), "high", UNIT,
            candidate_mode="committed-head")
        goal_changed = "accepted"
    except Exception as exc:  # noqa: BLE001 - the harness error type is its own
        goal_changed = f"refused: {exc}"
    check("the goal harness (unit closure) refuses the receipt after the candidate changed",
          goal_changed.startswith("refused"), goal_changed)
    write(repo / "change-2.txt", "staged change\n")
    git(repo, "add", "change-2.txt")
    check("a changed staged candidate closes both cache kinds",
          core.cache_allows(repo, kind="general") is False
          and core.cache_allows(repo, kind="security") is False)

# ---------------------------------------------------------------------------
print("[2] a strict candidate without security coverage stays blocked")
with tempfile.TemporaryDirectory(prefix="one-review-nosec-") as td:
    repo = Path(td).resolve()
    make_repo(repo, classes=("correctness",))
    receipt = make_review_receipt(repo, unit_id=UNIT, risk_tier="high", command=ORACLE)
    accepted, record = core.record_review(
        repo, verdict="PASSED", kind="general", session="s10-nosec",
        verification_receipt=receipt)
    check("the general kind is still unlocked by a security-less review",
          accepted and core.cache_allows(repo, kind="general") is True)
    check("the security kind stays closed when the policy does not require security",
          core.cache_allows(repo, kind="security") is False)
    cache_file = json.loads((repo / ".itd-memory" / "review-cache.json").read_text(encoding="utf-8"))
    check("the binding says none and no security record is written",
          record["verificationReceipt"]["securityCoverage"] == "none"
          and "security" not in cache_file["records"], json.dumps(record["verificationReceipt"]))
    refused = ""
    try:
        core.record_review(repo, verdict="PASSED", kind="security", session="s10-nosec",
                           verification_receipt=receipt)
        refused = "accepted"
    except core.CacheError as exc:
        refused = f"{exc.why} | {exc.fix}"
    check("an explicit security record without coverage is refused with WHY/FIX",
          "security coverage" in refused and "strict route" in refused, refused)
    cli = sh([sys.executable, str(CACHE), "record", "--root", str(repo),
              "--kind", "security", "--verdict", "PASSED",
              "--verification-receipt", str(receipt)], ROOT)
    try:
        cli_payload = json.loads(cli.stdout)
    except Exception:
        cli_payload = {}
    check("the CLI refuses the security kind with a non-zero WHY/FIX",
          cli.returncode != 0 and "security coverage" in str(cli_payload.get("why")),
          cli.stdout + cli.stderr)
    code, out = dod_main(repo)
    check("the DoD gate denies the auth-path commit of a strict candidate without security coverage",
          code == 2 and '"deny"' in out and "security-audit" in out,
          f"rc={code} {out[:200]}")

with tempfile.TemporaryDirectory(prefix="one-review-foreign-") as td:
    repo = Path(td).resolve()
    make_repo(repo, followup_unit="U-other")
    receipt = make_review_receipt(repo, unit_id=UNIT, risk_tier="high", command=ORACLE)
    accepted, record = core.record_review(
        repo, verdict="PASSED", kind="general", session="s10-foreign",
        verification_receipt=receipt)
    cache_file = json.loads((repo / ".itd-memory" / "review-cache.json").read_text(encoding="utf-8"))
    check("a security policy declared for another unit does not cover this receipt",
          accepted and record["verificationReceipt"]["securityCoverage"] == "none"
          and "security" not in cache_file["records"]
          and core.cache_allows(repo, kind="security") is False,
          json.dumps(record["verificationReceipt"]))

with tempfile.TemporaryDirectory(prefix="one-review-low-") as td:
    repo = Path(td).resolve()
    make_repo(repo, tier="low")
    receipt = make_review_receipt(repo, unit_id=UNIT, risk_tier="low", command=ORACLE)
    accepted, _ = core.record_review(
        repo, verdict="PASSED", kind="general", session="s10-low",
        verification_receipt=receipt)
    check("a machine-only (low) receipt never unlocks the security kind, policy or not",
          accepted and core.cache_allows(repo, kind="general") is True
          and core.cache_allows(repo, kind="security") is False)

# ---------------------------------------------------------------------------
print("[3] no suffixed round")
with tempfile.TemporaryDirectory(prefix="one-review-suffix-") as td:
    repo = Path(td).resolve()
    make_repo(repo)
    suffixed = make_review_receipt(repo, unit_id=UNIT + ":general-review",
                                   risk_tier="high", command=ORACLE)
    refused = ""
    try:
        core.record_review(repo, verdict="PASSED", kind="general", session="s10-suffix",
                           verification_receipt=suffixed)
        refused = "accepted"
    except core.CacheError as exc:
        refused = str(exc)
    check("a chain minted under <unit>:general-review is refused by the cache as another unit",
          "another unit" in refused, refused)
    check("the suffixed receipt unlocks nothing",
          core.cache_allows(repo, kind="general") is False
          and core.cache_allows(repo, kind="security") is False)

# ---------------------------------------------------------------------------
print("[4] route texts")
bugfix_text = BUGFIX_SKILL.read_text(encoding="utf-8")
step0 = next(line for line in bugfix_text.splitlines()
             if line.startswith('( cd "$(git rev-parse --show-toplevel'))
review_text = REVIEW_SKILL.read_text(encoding="utf-8")
cross_text = CROSS_SKILL.read_text(encoding="utf-8")
strict_text = REVIEW_STRICT.read_text(encoding="utf-8")
check("/review and /cross-review carry the identical Step 0 route command of /bugfix",
      review_text.count(step0) == 1 and cross_text.count(step0) == 1)
check("the same Step 0 command appears exactly once in /test, /refactor, /task and /adopt (identity across the seven route skills)",
      all((ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8").count(step0) == 1
          for name in ("test", "refactor", "task", "adopt")))
check("the minimal route of /review is the host's native review, with nothing to record",
      "`/code-review` in Claude Code" in review_text
      and "built-in `/review` in Codex" in review_text
      and "No receipt, no claim id, no cache record" in review_text
      and "On the minimal route there is nothing to record" in review_text)
check("the minimal route of /cross-review defers to the native review and stops",
      "`/code-review`" in cross_text and "no second-model\ngate" in cross_text
      and "not a caller bypass" in cross_text)
check("the strict steps of /review live in references/strict.md with the one-receipt rule",
      all(f"## S{n}." in strict_text for n in range(1, 6))
      and "bare active\n  unit id" in strict_text
      and "itd_review_cache.py" in strict_text
      and "MACHINE-VERIFIED PROVENANCE" in strict_text
      and "whenever any strict selector applies" in strict_text
      and ("names no start commit, a start token that does not resolve to a unique "
           "commit, or a start commit outside the candidate's history is `UNVERIFIED`")
      in " ".join(strict_text.split())
      and "no caller bypass" in strict_text)
check("/review names no suffixed claim any more",
      "general-review" not in review_text
      and ":general-review" not in (ROOT / "skills/task/references/strict.md").read_text(encoding="utf-8"))
for rel in ("docs/API_REVIEWER.md", "docs/CI.md", "skills/adopt/references/strict.md"):
    text = (ROOT / rel).read_text(encoding="utf-8")
    check(f"{rel} registers the bare unit id",
          "--local-review-unit-id <unit-id> \\" in text
          and "<unit-id>:general-review" not in text)
loop_doc = (ROOT / "docs/VERIFICATION_LOOP.md").read_text(encoding="utf-8")
check("VERIFICATION_LOOP.md states the bare id and the coverage rule",
      "and it is the bare active unit\nid" in loop_doc and "`security_coverage`" in loop_doc)
for rel, limit in (("skills/review/SKILL.md", 500),
                   ("skills/review/references/strict.md", 500),
                   ("skills/cross-review/SKILL.md", 500),
                   ("tests/verify_one_review_per_candidate.py", 500),
                   ("tests/verify_close_provenance.py", 500)):
    count = len((ROOT / rel).read_text(encoding="utf-8").splitlines())
    check(f"{rel} is at most {limit} lines", count <= limit, str(count))
hook_text = CROSS_HOOK.read_text(encoding="utf-8")
check("the cross-review reminder reads the route marker in the same 8 KB window",
      "def strict_route(" in hook_text and "ROUTE_WINDOW = 8192" in hook_text
      and "if not strict_route(root):\n        return 0" in hook_text
      and "O_NONBLOCK" in hook_text and "os.fstat(fd)" in hook_text)
for rel, needles in (("tests/run-all.sh", ("verify_one_review_per_candidate", "verify_close_provenance")),
                     (".github/workflows/meta-review.yml", ("tests/verify_one_review_per_candidate.py", "tests/verify_close_provenance.py")),
                     (".github/workflows/windows-verify.yml", ("tests/verify_one_review_per_candidate.py", "tests/verify_close_provenance.py"))):
    text = (ROOT / rel).read_text(encoding="utf-8")
    check(f"{rel} runs both session 10 oracles", all(n in text for n in needles))
cache_text = CACHE.read_text(encoding="utf-8")
check("the cache module documents one receipt per candidate",
      "One review per candidate (plan session 10)" in cache_text
      and re.search(r"def review_claim_id\(root: Path, kind: str\) -> str:\n(.*\n){1,12}?    del kind\n    return detected_unit_id\(root\)", cache_text) is not None)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
