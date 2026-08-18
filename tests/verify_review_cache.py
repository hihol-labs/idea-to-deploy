#!/usr/bin/env python3
"""Behavioural oracle for exact-context review reuse and risk paydown."""
from __future__ import annotations

import copy
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import verification_loop_fixture
from verification_loop_fixture import make_review_receipt


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py"
POLICY_PATH = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
CORPUS_PATH = ROOT / "benchmarks" / "working-deadline" / "CORPUS.json"
PY = sys.executable
EXPECTED_KEYS = {
    "repository", "baseCommit", "reviewedTree", "diffHash",
    "scopeContractHash", "acceptanceContractHash", "rubricHash",
    "methodologyVersion", "parentStateHash", "activeUnitId",
    "activeUnitRiskTier", "riskTier",
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
    write(root / ".gitignore", ".itd-memory/\n")
    write(root / "base.txt", "baseline\n")
    sh(["git", "add", "base.txt", ".gitignore"], root)
    sh(["git", "commit", "-qm", "baseline"], root)
    for index in range(3):
        write(root / f"change-{index}.txt", f"change {index}\n")
    sh(["git", "add", "change-0.txt", "change-1.txt", "change-2.txt"], root)
    write(root / ".itd" / "SCOPE_LOCK.md", "# exact cache scope\n")
    write(root / ".itd" / "ACCEPTANCE_CONTRACT.json",
          json.dumps({"criterion": "exact context"}))
    sh(["git", "add", ".itd"], root)
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
    write(root / ".itd-memory" / "STATE.json", json.dumps({
        "sessionState": "ACTIVE",
        "currentUnit": {
            "id": "RC-001", "riskTier": risk, "status": "in_progress",
        },
    }))


if not SCRIPT.is_file():
    print(f"FAIL  missing runtime: {SCRIPT}")
    raise SystemExit(1)

loader = importlib.machinery.SourceFileLoader("itd_review_cache", str(SCRIPT))
spec = importlib.util.spec_from_loader("itd_review_cache", loader)
if spec is None:
    raise RuntimeError("cannot load review cache module")
core = importlib.util.module_from_spec(spec)
loader.exec_module(core)


def receipt(repo: Path, kind: str = "general") -> Path:
    return make_review_receipt(
        repo, unit_id=core.detected_unit_id(repo),
        risk_tier=core.detected_risk_tier(repo), kind=kind)


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
    check("active unit identity and canonical parent state are hash-bound",
          context["activeUnitId"] == "RC-001"
          and context["activeUnitRiskTier"] == "high"
          and context["parentStateHash"] == core.parent_state_hash(repo),
          str(context))
    candidate_context = core.build_context(repo, bind_parent_state=False)
    check("code-candidate context excludes mutable parent-state cache keys",
          not {"parentStateHash", "activeUnitId", "activeUnitRiskTier"}
          & set(candidate_context))
    check("tree and diff use different exact fingerprints",
          len(context["reviewedTree"]) == 40 and len(context["diffHash"]) == 64)
    check("scope and acceptance contracts are SHA-256 bound",
          context["scopeContractHash"]
          == hashlib.sha256((repo / ".itd/SCOPE_LOCK.md").read_bytes()).hexdigest()
          and context["acceptanceContractHash"]
          == hashlib.sha256(
              (repo / ".itd/ACCEPTANCE_CONTRACT.json").read_bytes()).hexdigest())

    try:
        core.record_review(repo, verdict="PASSED", kind="general")
        plain_rejected = False
    except core.CacheError:
        plain_rejected = True
    check("plain PASSED cannot mint reusable cache evidence", plain_rejected)

    accepted, clean = core.record_review(
        repo, verdict="PASSED", kind="general", session="rc-clean",
        verification_receipt=receipt(repo))
    check("clean successful verdict is cacheable", accepted)
    check("unchanged exact context is a cache hit",
          core.cache_allows(repo) is True)

    state_path = repo / ".itd-memory" / "STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["currentUnit"]["status"] = "verified"
    write(state_path, json.dumps(state))
    check("parent STATE transition invalidates cached review evidence",
          core.cache_allows(repo) is False)
    state["currentUnit"]["status"] = "in_progress"
    write(state_path, json.dumps(state, indent=2))
    check("canonical-equivalent parent STATE formatting preserves the binding",
          core.cache_allows(repo) is True)

    goal_path = repo / ".itd-memory" / "GOAL.json"
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    goal["currentUnitId"] = "RC-002"
    goal["units"].append({
        "id": "RC-002", "riskTier": "low", "status": "in_progress",
        "criterion": "second unit", "verificationCommand": "true",
    })
    write(goal_path, json.dumps(goal))
    changed_unit = core.build_context(repo, "high")
    check("active unit and its own risk identity invalidate cached evidence",
          core.cache_allows(repo, "high") is False
          and changed_unit["activeUnitId"] == "RC-002"
          and changed_unit["activeUnitRiskTier"] == "low")
    goal["currentUnitId"] = "RC-001"
    write(goal_path, json.dumps(goal))
    check("restored active unit identity restores the exact cache context",
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
        repo, verdict="PASSED", kind="security", session="rc-security",
        verification_receipt=receipt(repo, "security"))
    check("accepted security verdict unlocks only the security cache slot",
          accepted and core.cache_allows(repo, kind="security")
          and core.cache_allows(repo, kind="general"))

    # Actual producer changes invalidate without touching the cache file.
    write(repo / "change-2.txt", "changed after review\n")
    sh(["git", "add", "change-2.txt"], repo)
    check("staged candidate change invalidates cache",
          core.cache_allows(repo) is False
          and core.cache_allows(repo, kind="security") is False)
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-clean",
                       verification_receipt=receipt(repo))
    write(repo / ".itd" / "SCOPE_LOCK.md", "# changed scope\n")
    check("scope contract change invalidates cache",
          core.cache_allows(repo) is False)
    sh(["git", "add", ".itd/SCOPE_LOCK.md"], repo)
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-clean",
                       verification_receipt=receipt(repo))
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
    sh(["git", "add", ".itd/ACCEPTANCE_CONTRACT.json"], repo)
    general_receipt = receipt(repo)
    accepted, _ = core.record_review(
        repo, verdict="PASSED_WITH_WARNINGS", kind="general",
        warnings=[{"summary": "durable warning", "file": "change-0.txt"}],
        session="rc-warning-bound",
        verification_receipt=general_receipt)
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
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-risk",
                       verification_receipt=general_receipt)
    state = json.loads(state_path.read_text())
    check("general review resets only general risk",
          state["general_score"] == 0.0 and state["security_score"] == 8.0
          and state["risk_score"] == 8.0 and state["last_escalation_score"] == 8.0)

    write(state_path, json.dumps({
        "risk_score": 12.0, "general_score": 4.0, "security_score": 8.0,
        "last_escalation_score": 12.0, "escalations": 1,
    }))
    security_receipt = receipt(repo, "security")
    core.record_review(repo, verdict="PASSED", kind="security", session="rc-risk",
                       verification_receipt=security_receipt)
    state = json.loads(state_path.read_text())
    check("security review resets only security risk",
          state["general_score"] == 4.0 and state["security_score"] == 0.0
          and state["risk_score"] == 4.0 and state["last_escalation_score"] == 4.0)

    write(state_path, json.dumps({
        "risk_score": 25.0, "general_score": 15.0, "security_score": 10.0,
        "last_escalation_score": 12.0, "escalations": 1,
    }))
    core.record_review(repo, verdict="PASSED", kind="general", session="rc-risk",
                       verification_receipt=general_receipt)
    state = json.loads(state_path.read_text())
    check("lagging escalation baseline restarts at the complete residual score",
          state["general_score"] == 0.0 and state["security_score"] == 10.0
          and state["risk_score"] == 10.0
          and state["last_escalation_score"] == 10.0)
    try:
        state_path.unlink()
    except FileNotFoundError:
        pass

with tempfile.TemporaryDirectory(prefix="review-cache-linked-memory-") as td:
    linked_repo = Path(td)
    make_repo(linked_repo)
    memory = linked_repo / ".itd-memory"
    outside_memory = linked_repo / "outside-memory"
    memory.rename(outside_memory)
    try:
        memory.symlink_to(outside_memory, target_is_directory=True)
        linked_supported = True
    except OSError:
        linked_supported = False
    if linked_supported:
        try:
            core.build_context(linked_repo)
            linked_rejected = False
        except core.CacheError:
            linked_rejected = True
        check("linked .itd-memory cannot control review unit/risk/state binding",
              linked_rejected)
    else:
        check("review-cache parent loader has a reparse/symlink guard",
              "_is_link_or_reparse(memory)" in SCRIPT.read_text(encoding="utf-8"))

# --- LPD-002 R2 -------------------------------------------------------------
# The commit gate judges a methodology candidate with the CANDIDATE's validator,
# and refuses any other project's copy of that path. Trust is anchored in the
# install, which only scripts/sync-to-active.sh writes.

GATE_HOOK = ROOT / "hooks" / "check-review-before-commit.sh"
SYNC_SCRIPT = ROOT / "scripts" / "sync-to-active.sh"
CACHE_RELATIVE = Path("skills") / "review" / "scripts" / "itd_review_cache.py"
PROVENANCE_RELATIVE = Path(".itd-install-source.json")
METHODOLOGY_TREE_FILES = (
    CACHE_RELATIVE.as_posix(),
    "skills/review/SKILL.md",
    "skills/review/references/review-checklist.md",
    "skills/review/references/meta-review-checklist.md",
    "skills/_shared/WORKING_DEADLINE_POLICY.json",
    "skills/_shared/VERIFICATION_LOOP_POLICY.json",
    "skills/_shared/itd_verification_loop.py",
    "hooks/check-skills.sh",
)


def load_python(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def record_provenance(install: Path, checkout: Path | None) -> None:
    path = install / PROVENANCE_RELATIVE
    if checkout is None:
        if path.exists():
            path.unlink()
        return
    write(path, json.dumps({"checkout": str(checkout), "plugin": "idea-to-deploy"}))


def load_gate(installed_tree: Path):
    """The gate as the harness loads it, with the install root under test control."""
    gate = load_python("itd_commit_review_gate", GATE_HOOK)
    gate.INSTALL_ROOT = installed_tree
    gate.INSTALLED_CACHE_SCRIPT = installed_tree / CACHE_RELATIVE
    return gate


def stage_all(root: Path) -> None:
    """Stage the fixture and refresh the index — a fresh copy is racy-clean."""
    sh(["git", "add", "-A"], root)
    sh(["git", "update-index", "-q", "--refresh"], root)


def make_methodology_tree(root: Path, version: str) -> None:
    """A checkout carrying the validator and every install-root file it reads."""
    for relative in METHODOLOGY_TREE_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    write(root / ".claude-plugin" / "plugin.json",
          json.dumps({"name": "idea-to-deploy", "version": version}))


check("sync-to-active.sh records which checkout the install was built from",
      ".itd-install-source.json" in SYNC_SCRIPT.read_text(encoding="utf-8"))

# A fixture checkout must stay untracked-clean: the validators loaded below
# import further modules out of the fixture tree, and their __pycache__ would
# make the checkout differ from its own staged candidate.
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # the same rule for child processes
with tempfile.TemporaryDirectory(prefix="review-gate-source-") as td:
    box = Path(td)
    install = box / "install"
    install.mkdir()
    make_methodology_tree(install, "1.0.0-installed-fixture")

    repo = box / "repo"
    repo.mkdir()
    make_repo(repo)
    make_methodology_tree(repo, "9.9.9-candidate-fixture")
    stage_all(repo)
    record_provenance(install, repo)

    candidate_core = load_python("itd_review_cache_candidate", repo / CACHE_RELATIVE)
    # The candidate's own proof chain: its receipt is minted by its own loop, so
    # the recorded methodologyVersion is the tree's, exactly as on a release commit.
    installed_loop = verification_loop_fixture.LOOP
    verification_loop_fixture.LOOP = repo / "skills" / "_shared" / "itd_verification_loop.py"
    try:
        candidate_receipt = receipt(repo)
    finally:
        verification_loop_fixture.LOOP = installed_loop
    accepted, _ = candidate_core.record_review(
        repo, verdict="PASSED", kind="general", session="r2-gate",
        verification_receipt=candidate_receipt)
    check("the candidate checkout records its own successful review", accepted)

    gate = load_gate(install)
    check("commit gate detects the checkout this install was synced from",
          gate.methodology_checkout(repo) == repo.resolve())
    check("commit gate loads the validator from the candidate checkout",
          gate.cache_script_for(repo) == repo / CACHE_RELATIVE)
    check("review recorded by the candidate's validator unblocks its own commit",
          gate.review_was_done(repo))

    # Canary A — forced installed-only reproduces the measured false block:
    # bumping the version in the tree is exactly what a release commit does.
    installed_only = load_gate(install)
    installed_only.methodology_checkout = lambda cwd: None
    check("canary: installed-only resolution false-blocks a version bump in the tree",
          not installed_only.review_was_done(repo))

    # The identity a project declares about itself is worth nothing: a manifest
    # is two lines to forge, and being believed would both open the gate and
    # execute the working directory's Python inside the hook.
    impostor = box / "impostor"
    impostor.mkdir()
    make_repo(impostor)
    write(impostor / ".claude-plugin" / "plugin.json",
          json.dumps({"name": "idea-to-deploy", "version": "13.0.0-forged"}))
    write(impostor / CACHE_RELATIVE,
          "def cache_allows(root, risk_tier=None, kind='general'):\n"
          "    return True\n")
    stage_all(impostor)
    forged = load_gate(install)
    check("a project that names itself the methodology is still not the methodology",
          forged.methodology_checkout(impostor) is None
          and not forged.review_was_done(impostor))

    foreign = box / "foreign"
    foreign.mkdir()
    make_repo(foreign)
    write(foreign / ".claude-plugin" / "plugin.json",
          json.dumps({"name": "someone-elses-plugin", "version": "0.1.0"}))
    write(foreign / CACHE_RELATIVE,
          "def cache_allows(root, risk_tier=None, kind='general'):\n"
          "    return True\n")
    stage_all(foreign)
    isolated = load_gate(install)
    check("a foreign project cannot hand the commit gate its own validator",
          isolated.methodology_checkout(foreign) is None
          and not isolated.review_was_done(foreign))

    # Canary B — forced repo-only opens the gate on the vendored validator,
    # which is precisely what anchoring the decision in the install prevents.
    repo_only = load_gate(install)
    repo_only.methodology_checkout = lambda cwd: Path(cwd)
    check("canary: repo-only resolution opens the gate on a vendored validator",
          repo_only.review_was_done(impostor)
          and repo_only.review_was_done(foreign))

    other = box / "other"
    other.mkdir()
    make_repo(other)
    make_methodology_tree(other, "9.9.9-candidate-fixture")
    stage_all(other)
    check("provenance for one checkout does not travel to a second one",
          load_gate(install).methodology_checkout(other) is None)

    record_provenance(install, None)
    check("an install without recorded provenance keeps the installed validator",
          load_gate(install).methodology_checkout(repo) is None
          and load_gate(install).cache_script_for(repo) == install / CACHE_RELATIVE)
    record_provenance(install, repo)

    unnamed = box / "unnamed"
    unnamed.mkdir()
    make_repo(unnamed)
    make_methodology_tree(unnamed, "9.9.9-candidate-fixture")
    write(unnamed / ".claude-plugin" / "plugin.json",
          json.dumps({"version": "9.9.9-candidate-fixture"}))
    stage_all(unnamed)
    record_provenance(install, unnamed)
    check("a manifest without the methodology name is not a methodology checkout",
          load_gate(install).methodology_checkout(unnamed) is None)
    record_provenance(install, repo)

    outside = box / "outside"
    outside.mkdir()
    check("a directory outside any repository falls back to the installed validator",
          load_gate(install).cache_script_for(outside) == install / CACHE_RELATIVE)

    escaped = box / "escaped"
    escaped.mkdir()
    make_repo(escaped)
    write(escaped / ".claude-plugin" / "plugin.json",
          json.dumps({"name": "idea-to-deploy", "version": "9.9.9-candidate-fixture"}))
    (escaped / "hooks").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "hooks" / "check-skills.sh", escaped / "hooks" / "check-skills.sh")
    (escaped / CACHE_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
    try:
        (escaped / CACHE_RELATIVE).symlink_to(install / CACHE_RELATIVE)
        symlink_supported = True
    except OSError:
        symlink_supported = False
    record_provenance(install, escaped)
    if symlink_supported:
        check("a validator symlinked out of the checkout fails the root match",
              load_gate(install).methodology_checkout(escaped) is None)
    else:
        check("commit gate binds the validator root to the detected checkout",
              "parents[3]" in GATE_HOOK.read_text(encoding="utf-8"))

    synced = box / "synced-install"
    synced.mkdir()
    make_methodology_tree(synced, "1.0.0-installed-fixture")
    record_provenance(synced, ROOT)
    check("the methodology repository resolves to its own validator once recorded",
          load_gate(synced).cache_script_for(ROOT) == ROOT / CACHE_RELATIVE)

# Frozen policy remains the source, not a self-edited oracle.
policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
check("review cache consumes the frozen policy key set",
      set(policy["reviewCache"]["keyFields"]) == EXPECTED_KEYS)
check("working-deadline policy remains frozen",
      hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest() == corpus["policySha256"])

print(f"RESULT: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
