#!/usr/bin/env python3
"""Behavioural oracle for exact-context review reuse and risk paydown."""
from __future__ import annotations

import copy
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py"
POLICY_PATH = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
CORPUS_PATH = ROOT / "benchmarks" / "working-deadline" / "CORPUS.json"
PY = sys.executable
EXPECTED_KEYS = {
    "repository", "baseCommit", "reviewedTree", "diffHash",
    "scopeContractHash", "acceptanceContractHash", "rubricHash",
    "methodologyVersion", "riskTier",
}

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


def sh(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=30)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(root: Path, risk: str = "high") -> None:
    sh(["git", "init", "-q"], root)
    sh(["git", "config", "user.email", "review-cache@example.test"], root)
    sh(["git", "config", "user.name", "Review Cache Test"], root)
    write(root / "base.txt", "baseline\n")
    sh(["git", "add", "base.txt"], root)
    sh(["git", "commit", "-qm", "baseline"], root)
    for index in range(3):
        write(root / f"change-{index}.txt", f"change {index}\n")
    sh(["git", "add", "change-0.txt", "change-1.txt", "change-2.txt"], root)
    write(root / ".itd" / "SCOPE_LOCK.md", "# exact cache scope\n")
    write(root / ".itd" / "ACCEPTANCE_CONTRACT.json",
          json.dumps({"criterion": "exact context"}))
    goal = {
        "version": 1,
        "goal": "review cache fixture",
        "status": "active",
        "currentUnitId": "RC-001",
        "units": [{
            "id": "RC-001", "riskTier": risk, "status": "in_progress",
            "criterion": "cache exact", "verificationCommand": "true",
        }],
    }
    write(root / ".itd-memory" / "GOAL.json", json.dumps(goal))


if not SCRIPT.is_file():
    print(f"FAIL  missing runtime: {SCRIPT}")
    raise SystemExit(1)

loader = importlib.machinery.SourceFileLoader("itd_review_cache", str(SCRIPT))
spec = importlib.util.spec_from_loader("itd_review_cache", loader)
if spec is None:
    raise RuntimeError("cannot load review cache module")
core = importlib.util.module_from_spec(spec)
loader.exec_module(core)


# Deployment baseline: no command is a quiet no-op.
r = sh([PY, str(SCRIPT)], ROOT)
check("no command is a quiet no-op",
      r.returncode == 0 and not r.stdout and not r.stderr, r.stdout + r.stderr)
check("CLI durable warning syntax preserves file and summary",
      core.warning_args(["src/cache.py: investigate fallback"])
      == [{"file": "src/cache.py", "summary": "investigate fallback"}])
check("CLI warning syntax preserves a Windows drive colon",
      core.warning_args([r"C:\\repo\\cache.py: investigate fallback"])
      == [{"file": r"C:\\repo\\cache.py", "summary": "investigate fallback"}])
check("malformed CLI warning syntax is rejected by the parser",
      core.warning_args(["missing file separator"]) == [])

with tempfile.TemporaryDirectory(prefix="review-cache-") as td:
    repo = Path(td)
    make_repo(repo)

    context = core.build_context(repo)
    check("cache key has exactly the frozen context fields",
          set(context) == EXPECTED_KEYS, json.dumps(context, indent=2))
    check("risk tier comes from the active goal producer",
          context["riskTier"] == "high", str(context))
    check("tree and diff use different exact fingerprints",
          len(context["reviewedTree"]) == 40 and len(context["diffHash"]) == 64)
    check("scope and acceptance contracts are SHA-256 bound",
          context["scopeContractHash"]
          == hashlib.sha256((repo / ".itd/SCOPE_LOCK.md").read_bytes()).hexdigest()
          and context["acceptanceContractHash"]
          == hashlib.sha256(
              (repo / ".itd/ACCEPTANCE_CONTRACT.json").read_bytes()).hexdigest())

    accepted, clean = core.record_review(
        repo, verdict="PASSED", kind="general", session="rc-clean")
    check("clean successful verdict is cacheable", accepted)
    check("unchanged exact context is a cache hit",
          core.cache_allows(repo) is True)

    for key in sorted(EXPECTED_KEYS):
        mutant = copy.deepcopy(clean)
        value = mutant["context"][key]
        mutant["context"][key] = ("x" + value[1:]) if value else "changed"
        check(f"cache rejects changed {key}",
              core.record_matches(mutant, context) is False)
    wrong_kind = copy.deepcopy(clean)
    wrong_kind["kind"] = "security"
    check("security evidence cannot occupy the general review cache slot",
          core.record_matches(wrong_kind, context) is False)
    accepted, _ = core.record_review(
        repo, verdict="PASSED", kind="security", session="rc-security")
    check("accepted security verdict unlocks only the security cache slot",
          accepted and core.cache_allows(repo, kind="security")
          and core.cache_allows(repo, kind="general"))

    # Actual producer changes invalidate without touching the cache file.
    write(repo / "change-2.txt", "changed after review\n")
    sh(["git", "add", "change-2.txt"], repo)
    check("staged candidate change invalidates cache",
          core.cache_allows(repo) is False
          and core.cache_allows(repo, kind="security") is False)
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-clean")
    write(repo / ".itd" / "SCOPE_LOCK.md", "# changed scope\n")
    check("scope contract change invalidates cache",
          core.cache_allows(repo) is False)
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-clean")
    write(repo / ".itd" / "ACCEPTANCE_CONTRACT.json",
          json.dumps({"criterion": "changed"}))
    check("acceptance contract change invalidates cache",
          core.cache_allows(repo) is False)

    # Status-aware verdict semantics.
    accepted, _ = core.record_review(
        repo, verdict="BLOCKED", kind="general", session="rc-blocked")
    check("BLOCKED neither caches nor unlocks", not accepted and not core.cache_allows(repo))
    accepted, _ = core.record_review(
        repo, verdict="UNVERIFIED", kind="general", session="rc-unverified")
    check("UNVERIFIED neither caches nor unlocks", not accepted and not core.cache_allows(repo))
    accepted, _ = core.record_review(
        repo, verdict="PASSED_WITH_WARNINGS", kind="general",
        warnings=[], session="rc-warning-empty")
    check("warning verdict without durable warnings fails closed", not accepted)
    accepted, _ = core.record_review(
        repo, verdict="PASSED_WITH_WARNINGS", kind="general",
        warnings=[{"summary": "durable warning", "file": "change-0.txt"}],
        session="rc-warning-bound")
    check("warning verdict is reusable only with durable warnings",
          accepted and core.cache_allows(repo))

    # Rejected CLI evidence is actionable and non-zero.
    r = sh([PY, str(SCRIPT), "record", "--root", str(repo),
            "--verdict", "BLOCKED", "--kind", "general"], ROOT)
    try:
        payload = json.loads(r.stdout)
    except Exception:
        payload = {}
    check("rejected CLI verdict returns nonzero WHY/FIX",
          r.returncode != 0 and payload.get("why") and payload.get("fix"),
          r.stdout + r.stderr)

    # Risk paydown is accepted-verdict-only and bucket-specific.
    state_path = core.risk_state_path("rc-risk")
    write(state_path, json.dumps({
        "risk_score": 12.0, "general_score": 4.0, "security_score": 8.0,
        "last_escalation_score": 12.0, "escalations": 1,
    }))
    core.record_review(repo, verdict="BLOCKED", kind="general", session="rc-risk")
    state = json.loads(state_path.read_text())
    check("failed review does not reset either risk bucket",
          state["general_score"] == 4.0 and state["security_score"] == 8.0)
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-risk")
    state = json.loads(state_path.read_text())
    check("general review resets only general risk",
          state["general_score"] == 0.0 and state["security_score"] == 8.0
          and state["risk_score"] == 8.0 and state["last_escalation_score"] == 8.0)

    write(state_path, json.dumps({
        "risk_score": 12.0, "general_score": 4.0, "security_score": 8.0,
        "last_escalation_score": 12.0, "escalations": 1,
    }))
    core.record_review(repo, verdict="PASSED", kind="security", session="rc-risk")
    state = json.loads(state_path.read_text())
    check("security review resets only security risk",
          state["general_score"] == 4.0 and state["security_score"] == 0.0
          and state["risk_score"] == 4.0 and state["last_escalation_score"] == 4.0)

    write(state_path, json.dumps({
        "risk_score": 25.0, "general_score": 15.0, "security_score": 10.0,
        "last_escalation_score": 12.0, "escalations": 1,
    }))
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-risk")
    state = json.loads(state_path.read_text())
    check("lagging escalation baseline restarts at the complete residual score",
          state["general_score"] == 0.0 and state["security_score"] == 10.0
          and state["risk_score"] == 10.0
          and state["last_escalation_score"] == 10.0)
    try:
        state_path.unlink()
    except FileNotFoundError:
        pass

# Frozen policy remains the source, not a self-edited oracle.
policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
check("review cache consumes the frozen policy key set",
      set(policy["reviewCache"]["keyFields"]) == EXPECTED_KEYS)
check("working-deadline policy remains frozen",
      hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest() == corpus["policySha256"])

print(f"RESULT: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
