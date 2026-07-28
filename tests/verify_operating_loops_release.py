#!/usr/bin/env python3
"""Fail-closed publication and dual-host active-install proof for v1.94.0."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.94.0"
DEFAULT_BRANCH = "codex/operating-loops-v1"
ACCEPTANCE_CONTRACT_SHA256 = "f17567d5cd1a479cec3d66df0d734be43505eabacb706305fb09cf670c03f7ef"
SCOPE_LOCK_SHA256 = "2286b852a27e8ef7db8cd8a6274670f4b050f3a9a628bca11a9c9811eed20d04"
EXPECTED_CRITERIA_COMMANDS = {
    "RLS-001-AC1": "sh skills/_shared/itd_py.sh tests/verify_operating_loops_release.py --phase candidate",
    "RLS-001-AC2": (
        "sh skills/_shared/itd_py.sh tests/verify_host_adapters.py && "
        "sh skills/_shared/itd_py.sh tests/meta_review.py && bash tests/run-all.sh --quick && "
        "bash tests/run-all.sh"
    ),
    "RLS-001-AC3": "sh skills/_shared/itd_py.sh tests/verify_harness_demo_portable.py",
}
EXPECTED_POST_COMMIT_COMMANDS = {
    "RLS-PUB-1": (
        "sh skills/_shared/itd_py.sh tests/verify_operating_loops_release.py "
        "--phase publication --branch codex/operating-loops-v1"
    ),
    "RLS-DEPLOY-1": (
        "sh skills/_shared/itd_py.sh tests/verify_operating_loops_release.py "
        "--phase deployment --branch codex/operating-loops-v1"
    ),
}
EXPECTED_SCOPE_SENTINELS = (
    "# Scope Lock — v1.94.0 publication and dual-host deployment",
    "## Current Task",
    "## Allowed Change Areas Before Freeze",
    "## Forbidden Change Areas",
    "## Exact Release Oracle",
    "No new methodology behavior is allowed.",
    "repair of an evidence-backed release blocker, followed by a fresh exact candidate and all release checks",
    "a sealed portable export of the already validated internal pilot evidence graph plus a separate self-contained oracle",
    "frozen Harness Demo contract, digest, verifier, or historical v4 repair",
    "must execute the sealed portable Harness Demo proof, all self-contained frozen behavioral phases, the 34 frozen mutation guards, and the historical v4 fixture.",
    "merge, tag, production application deployment, or any external write outside the requested branch push, pull request, and local methodology installation",
    "Fresh bound security and general reviews must inspect that same tree.",
    "Any tracked mutation invalidates pre-mutation evidence.",
)
RECIPES = (
    "state freshness",
    "test regression",
    "dependency health",
    "security posture",
    "review drift",
    "documentation drift",
)
EXPECTED_CHANGED = {
    ".claude-plugin/marketplace.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "CHANGELOG.md",
    "LAUNCH_PLAN.md",
    "README.md",
    "README.ru.md",
    "benchmarks/working-deadline/CORPUS.json",
    "benchmarks/working-deadline/CORPUS.sha256",
    "docs/HARNESS_CONFORMANCE_REPORT.md",
    "docs/HARNESS_DOCS_STATE.json",
    "docs/HARNESS_ENGINEERING_MAP.md",
    "docs/QUALITY.json",
    "hooks/validate_state_core.py",
    "scripts/itd_external_outcomes.py",
    "skills/_shared/WORKING_DEADLINE_POLICY.json",
    "skills/_shared/itd_verification_loop.py",
    "skills/_shared/OPERATING_LOOP_RECIPES.json",
    "skills/_shared/itd_operating_loops.py",
    "skills/review/scripts/itd_review_cache.py",
    "skills/task/SKILL.md",
    "tests/verify_operating_loops.py",
    "tests/verify_operating_loops_release.py",
    "tests/verify_review_cache.py",
    "tests/verify_verification_loop.py",
    "tests/verify_work_deadline_contract.py",
}
EXPECTED_CHANGED.update({
    ".itd-memory/GOAL.json",
    ".itd-memory/STATE.json",
    ".itd/ACCEPTANCE_CONTRACT.json",
    ".itd/SCOPE_LOCK.md",
    "BACKLOG.md",
    "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.json",
    "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.sha256",
    "docs/adr/ADR-004-harness-demo-ux-absorption.md",
    "docs/diagnostics-pilot/LABEL_PACKET.json",
    "docs/diagnostics-pilot/OBSERVATIONS.json",
    "docs/diagnostics-pilot/RESULTS.json",
    "docs/examples/brownfield-piv/artifacts/adjudication.json",
    "docs/examples/brownfield-piv/artifacts/checker-prompt.md",
    "docs/examples/brownfield-piv/artifacts/checker.json",
    "docs/examples/brownfield-piv/artifacts/context.json",
    "docs/examples/brownfield-piv/artifacts/machine.json",
    "docs/examples/brownfield-piv/artifacts/metrics.json",
    "docs/examples/brownfield-piv/artifacts/review.json",
    "docs/examples/brownfield-piv/artifacts/task-contract.md",
    "docs/examples/brownfield-piv/artifacts/ticket.md",
    "docs/examples/brownfield-piv/before/.gitignore",
    "docs/examples/brownfield-piv/before/src/invoice.py",
    "docs/examples/brownfield-piv/before/tests/test_invoice.py",
    "docs/examples/brownfield-piv/manifest.json",
    "docs/examples/brownfield-piv/manifest.schema.json",
    "docs/examples/brownfield-piv/patch.diff",
    "docs/harness-demo-pilots/INDEX.json",
    "docs/harness-demo-pilots/HISTORICAL_REPAIR_FIXTURE.json",
    "docs/harness-demo-pilots/HISTORICAL_REPAIR_FIXTURE.sha256",
    "docs/harness-demo-pilots/PORTABLE_EVIDENCE.json",
    "docs/harness-demo-pilots/PORTABLE_EVIDENCE.sha256",
    "docs/semantic-navigation/DEMAND.json",
    "docs/templates/itd/AGENT_CONTEXT_CONTRACT.json",
    "docs/templates/itd/FRESH_SESSION_WORKTREE_CONTRACT.json",
    "docs/templates/itd/INCREMENTAL_DIAGNOSTICS_CONTRACT.json",
    "docs/templates/itd/TOOL_CAPABILITY_REGISTRY.json",
    "skills/_shared/itd_captured_run.py",
    "skills/_shared/itd_diagnostics_pilot.py",
    "skills/_shared/itd_fresh_session_worktree.py",
    "skills/_shared/itd_incremental_diagnostics.py",
    "skills/_shared/itd_semantic_navigation.py",
    "skills/adopt/SKILL.md",
    "skills/adopt/references/codex-adoption.md",
    "skills/adopt/scripts/itd_context_map.py",
    "skills/task/PIV_LITE_ROUTE.json",
    "skills/task/references/routing-matrix.md",
    "tests/verify_adopt_context.py",
    "tests/verify_diagnostics_pilot.py",
    "tests/verify_fresh_session_worktree.py",
    "tests/verify_harness_demo_absorption.py",
    "tests/verify_harness_demo_portable.py",
    "tests/verify_harness_demo_capture_schema.py",
    "tests/verify_harness_demo_pilots.py",
    "tests/verify_incremental_diagnostics.py",
    "tests/fixtures/fixture-03-cli-tool/live-prompt.md",
    "tests/fixtures/live-model-evidence/latest.json",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/output/CLAUDE.md",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/output/CLAUDE_CODE_GUIDE.md",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/output/IMPLEMENTATION_PLAN.md",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/output/PRD.md",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/output/PROJECT_ARCHITECTURE.md",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/output/STRATEGIC_PLAN.md",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/run-report.json",
    "tests/fixtures/live-model-evidence/runs/20260728T135617Z-d0b19052/transcript.jsonl.gz",
    "tests/run-live-model-benchmark.py",
    "tests/verify_semantic_navigation.py",
    "tests/verify_semantic_navigation_demand.py",
    "tests/verify_state_hardening.py",
    "tests/verify_task_piv_lite.py",
    "tests/verify_live_model_benchmark.py",
})


class ReleaseError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def run(*args: str, cwd: Path = ROOT, timeout: int = 60) -> str:
    proc = subprocess.run(
        args, cwd=cwd, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=timeout,
    )
    if proc.returncode:
        raise ReleaseError(
            f"command failed ({proc.returncode}): {' '.join(args)}\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_file(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))



def validate_release_contracts(acceptance: dict, scope: str, *,
                               acceptance_raw: bytes | None = None,
                               scope_raw: bytes | None = None,
                               enforce_hashes: bool = True) -> dict:
    if enforce_hashes:
        require(acceptance_raw is not None and scope_raw is not None,
                "release contract hash inputs are missing")
        require(sha256_bytes(acceptance_raw) == ACCEPTANCE_CONTRACT_SHA256,
                "RLS acceptance contract differs from the exact reviewed contract")
        require(sha256_bytes(scope_raw) == SCOPE_LOCK_SHA256,
                "RLS scope lock differs from the exact reviewed scope")
    require(set(acceptance) == {
        "version", "purpose", "sourceRequest", "createdAt", "criteriaSchema",
        "criteria", "postCommitVerification", "doneRule",
    }, "RLS acceptance contract top-level fields are not closed")
    require(acceptance.get("version") == 1 and acceptance.get("createdAt") == "2026-07-27",
            "RLS acceptance contract version/date drifted")
    require(acceptance.get("sourceRequest") == (
        "Publish the accepted Harness Engineering absorption, deploy it to WSL and Windows, "
        "and make the latest ITD methodology the default in every directory."
    ), "RLS source request no longer matches the approved release/deployment goal")
    schema = acceptance.get("criteriaSchema")
    require(schema == {
        "requiredFields": ["id", "criterion", "source", "evidence",
                           "verificationCommand", "status"],
        "allowedStatus": ["pending", "passed", "failed", "recovery_required"],
    }, "RLS criteria schema drifted")
    criteria = acceptance.get("criteria")
    require(isinstance(criteria, list)
            and [item.get("id") for item in criteria if isinstance(item, dict)]
            == list(EXPECTED_CRITERIA_COMMANDS),
            "RLS-001 criteria are missing, reordered, or substituted")
    for item in criteria:
        require(set(item) == set(schema["requiredFields"]),
                f"{item.get('id')} fields are not closed")
        require(item.get("status") == "passed",
                f"{item.get('id')} is not evidence-backed passed")
        require(item.get("verificationCommand") == EXPECTED_CRITERIA_COMMANDS[item["id"]],
                f"{item.get('id')} verification command drifted")
        require(all(isinstance(item.get(field), str) and item[field].strip()
                    for field in ("criterion", "source", "evidence")),
                f"{item.get('id')} narrative contract is empty")
    post_commit = acceptance.get("postCommitVerification")
    require(isinstance(post_commit, list)
            and [item.get("id") for item in post_commit if isinstance(item, dict)]
            == list(EXPECTED_POST_COMMIT_COMMANDS),
            "post-commit publication/deployment criteria drifted")
    for item in post_commit:
        require(set(item) == {"id", "criterion", "verificationCommand"}
                and isinstance(item.get("criterion"), str) and item["criterion"].strip()
                and item.get("verificationCommand") == EXPECTED_POST_COMMIT_COMMANDS[item["id"]],
                f"{item.get('id')} post-commit contract drifted")
    require(acceptance.get("doneRule") == (
        "The immutable candidate is accepted only when every criterion is passed and one current "
        "exact-candidate Verification Loop adjudication re-runs every named command. The user goal "
        "remains active until both post-commit verification commands also pass."
    ), "RLS done rule was weakened")
    normalized_scope = " ".join(scope.split())
    for sentinel in EXPECTED_SCOPE_SENTINELS:
        require(" ".join(sentinel.split()) in normalized_scope,
                f"RLS scope lock omits immutable constraint: {sentinel}")
    require(scope.count("## Current Task") == 1
            and scope.count("## Allowed Change Areas Before Freeze") == 1
            and scope.count("## Forbidden Change Areas") == 1
            and scope.count("## Exact Release Oracle") == 1,
            "RLS scope sections are duplicated or missing")
    return {"criteria": len(criteria), "postCommitCriteria": len(post_commit)}


def release_contract_mutation_guards(acceptance: dict, scope: str) -> int:
    cases: list[tuple[str, dict, str]] = []
    status = copy.deepcopy(acceptance)
    status["criteria"][0]["status"] = "pending"
    cases.append(("criterion status", status, scope))
    command = copy.deepcopy(acceptance)
    command["criteria"][0]["verificationCommand"] = "true"
    cases.append(("criterion command", command, scope))
    missing = copy.deepcopy(acceptance)
    missing["criteria"].pop()
    cases.append(("missing criterion", missing, scope))
    schema = copy.deepcopy(acceptance)
    schema["criteriaSchema"]["allowedStatus"].append("skipped")
    cases.append(("criteria schema", schema, scope))
    post = copy.deepcopy(acceptance)
    post["postCommitVerification"][1]["verificationCommand"] = "true"
    cases.append(("deployment command", post, scope))
    cases.append(("scope weakening", copy.deepcopy(acceptance),
                  scope.replace("No new methodology behavior is allowed.", "")))
    for label, mutant, mutant_scope in cases:
        try:
            validate_release_contracts(mutant, mutant_scope, enforce_hashes=False)
        except ReleaseError:
            continue
        raise ReleaseError(f"release contract mutation survived: {label}")
    return len(cases)

def candidate_checks() -> dict:
    manifests = (
        json_file(".claude-plugin/plugin.json"),
        json_file(".codex-plugin/plugin.json"),
    )
    marketplace = json_file(".claude-plugin/marketplace.json")
    require(all(item.get("version") == VERSION for item in manifests),
            f"plugin manifests are not synchronized at v{VERSION}")
    plugins = marketplace.get("plugins", [])
    require(len(plugins) == 1 and plugins[0].get("version") == VERSION,
            f"marketplace version is not synchronized at v{VERSION}")
    require(f"## [{VERSION}]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            f"dated v{VERSION} changelog entry is missing")
    acceptance_path = ROOT / ".itd" / "ACCEPTANCE_CONTRACT.json"
    scope_path = ROOT / ".itd" / "SCOPE_LOCK.md"
    acceptance_raw = acceptance_path.read_bytes()
    scope_raw = scope_path.read_bytes()
    acceptance = json.loads(acceptance_raw.decode("utf-8"))
    scope = scope_raw.decode("utf-8")
    release_contracts = validate_release_contracts(
        acceptance, scope, acceptance_raw=acceptance_raw, scope_raw=scope_raw)
    contract_guards = release_contract_mutation_guards(acceptance, scope)
    for relative in ("README.md", "README.ru.md", "docs/OPERATING_LOOPS.md", "CHANGELOG.md"):
        text = " ".join((ROOT / relative).read_text(encoding="utf-8").lower().split())
        missing = [recipe for recipe in RECIPES if recipe not in text]
        require(not missing, f"{relative} omits registry recipes: {missing}")
    run_all = (ROOT / "tests/run-all.sh").read_text(encoding="utf-8")
    require("verify_operating_loops_release" in run_all,
            "release verifier is not registered in tests/run-all.sh")
    demand = json.loads(run(
        "sh", "skills/_shared/itd_py.sh",
        "tests/verify_semantic_navigation_demand.py", "--portable",
        timeout=300,
    ))
    require(demand.get("status") == "PASSED"
            and demand.get("provenanceMode") == "portable",
            "portable semantic-navigation demand provenance failed")
    portable = json.loads(run(
        "sh", "skills/_shared/itd_py.sh",
        "tests/verify_harness_demo_portable.py",
        timeout=300,
    ))
    require(portable.get("status") == "PASSED"
            and portable.get("frozenMutationGuards") == 34
            and portable.get("portableSemanticFiles") == 6,
            "self-contained portable Harness Demo proof failed")
    with tempfile.TemporaryDirectory(prefix="itd-v194-no-git-") as raw:
        archive = Path(raw) / "candidate"
        shutil.copytree(
            ROOT,
            archive,
            ignore=shutil.ignore_patterns(".git", ".itd-memory", "__pycache__", "*.pyc"),
        )
        no_git = subprocess.run(
            [
                "sh",
                "skills/_shared/itd_py.sh",
                "tests/verify_harness_demo_portable.py",
            ],
            cwd=archive,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        require(
            no_git.returncode == 0
            and json.loads(no_git.stdout).get("historicalRepairFixture") == "PASSED",
            f"portable Harness Demo proof requires Git history: "
            f"{no_git.stdout}{no_git.stderr}",
        )
    missing_files = [relative for relative in sorted(EXPECTED_CHANGED)
                     if not (ROOT / relative).is_file()]
    require(not missing_files,
            f"release candidate is missing declared files: {missing_files}")
    return {"version": VERSION, "declaredFiles": len(EXPECTED_CHANGED),
            "semanticDemand": "PASSED", "releaseContracts": release_contracts,
            "contractMutationGuards": contract_guards, "portablePilotEvidence": "PASSED"}


def github_json(path: str, query: dict[str, str] | None = None) -> object:
    suffix = "?" + urlencode(query) if query else ""
    request = Request(
        f"https://api.github.com/repos/hihol-labs/idea-to-deploy/{path}{suffix}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "idea-to-deploy-release-verifier",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        require(response.status == 200, f"GitHub API returned {response.status} for {path}")
        return json.loads(response.read().decode("utf-8"))


def matching_adjudication(receipt_sha: str, tree: str) -> str:
    require(bool(re.fullmatch(r"[0-9a-f]{64}", receipt_sha)),
            "pull request adjudicationReceiptSha256 is not an exact SHA-256")
    root = ROOT / ".itd-memory" / "verification-loop" / "receipts"
    matches: list[Path] = []
    for path in root.glob("*/RLS-001-adjudication-a*.json"):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (receipt.get("receiptSha256") == receipt_sha
                and receipt.get("unitId") == "RLS-001"
                and receipt.get("riskTier") == "high"
                and receipt.get("outcome") == "PASSED"
                and (receipt.get("candidate") or {}).get("reviewedTree") == tree):
            matches.append(path)
    require(len(matches) == 1,
            "PR evidence is not backed by exactly one local RLS-001 adjudication receipt")
    run(
        "sh", "skills/_shared/itd_py.sh",
        "skills/_shared/itd_verification_loop.py", "check",
        "--root", str(ROOT),
        "--unit-id", "RLS-001",
        "--risk-tier", "high",
        "--receipt", str(matches[0]),
        timeout=120,
    )
    return matches[0].relative_to(ROOT).as_posix()


def publication_checks(branch: str) -> dict:
    result = candidate_checks()
    current = run("git", "branch", "--show-current")
    require(current == branch, f"wrong publication branch: {current!r}")
    require(not run("git", "status", "--porcelain"),
            "publication checkout has tracked or untracked drift")
    head = run("git", "rev-parse", "HEAD")
    tree = run("git", "rev-parse", "HEAD^{tree}")
    remote_rows = run("git", "ls-remote", "--heads", "origin", branch).splitlines()
    require(len(remote_rows) == 1 and remote_rows[0].split()[0] == head,
            "origin branch does not resolve to local HEAD")
    rows = github_json("pulls", {
        "state": "open",
        "head": f"hihol-labs:{branch}",
        "base": "main",
        "per_page": "10",
    })
    require(isinstance(rows, list) and len(rows) == 1,
            "expected exactly one open release pull request for the branch")
    number = rows[0].get("number")
    require(type(number) is int, "GitHub pull request number is missing")
    pr = github_json(f"pulls/{number}")
    require(isinstance(pr, dict) and pr.get("state") == "open",
            "release pull request is not open")
    pr_head = pr.get("head") or {}
    pr_base = pr.get("base") or {}
    require(pr_head.get("ref") == branch and pr_head.get("sha") == head,
            "pull request is not bound to the published HEAD")
    require(pr_base.get("ref") == "main", "pull request base is not main")
    base = str(pr_base.get("sha") or "")
    remote_main = run("git", "ls-remote", "--heads", "origin", "main").splitlines()
    require(len(remote_main) == 1 and remote_main[0].split()[0] == base,
            "pull request base OID is not the current origin/main OID")
    run("git", "cat-file", "-e", f"{base}^{{commit}}")
    changed = set(filter(None, run("git", "diff", "--name-only", base, head).splitlines()))
    require(changed == EXPECTED_CHANGED and pr.get("changed_files") == len(EXPECTED_CHANGED),
            f"published/PR scope differs: missing={sorted(EXPECTED_CHANGED - changed)} "
            f"extra={sorted(changed - EXPECTED_CHANGED)}")
    body = str(pr.get("body") or "")
    matches = re.findall(r"<!-- ITD_RELEASE_EVIDENCE\s*(\{.*?\})\s*-->", body, re.DOTALL)
    require(len(matches) == 1, "pull request lacks one structured ITD release evidence block")
    evidence = json.loads(matches[0])
    expected_evidence = {
        "schemaVersion": 1,
        "release": VERSION,
        "candidateTree": tree,
        "unit": "RLS-001",
        "adjudication": "PASSED",
        "checks": {
            "harnessDemoAbsorption": "PASSED",
            "hostAdapters": "PASSED",
            "metaReview": "PASSED",
            "quickRegression": "PASSED",
            "fullRegression": "PASSED",
            "securityReview": "PASSED",
            "generalReview": "PASSED",
        },
    }
    receipt_sha = evidence.pop("adjudicationReceiptSha256", "")
    require(evidence == expected_evidence,
            "pull request structured evidence is not exact or candidate-bound")
    receipt = matching_adjudication(str(receipt_sha), tree)
    result.update({
        "branch": branch,
        "head": head,
        "tree": tree,
        "pr": pr.get("html_url"),
        "adjudication": receipt,
    })
    return result


def windows_home() -> Path:
    explicit = os.environ.get("ITD_WINDOWS_HOME")
    if explicit:
        return Path(explicit)
    require(os.name != "nt", "set ITD_WINDOWS_HOME when running deployment proof on Windows")
    profile = run("cmd.exe", "/d", "/c", "echo", "%USERPROFILE%", cwd=ROOT).splitlines()[-1].strip()
    mounted = run("wslpath", "-u", profile, cwd=ROOT)
    return Path(mounted)


def tracked_hashes(root: Path) -> dict[str, str]:
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
        cwd=root, capture_output=True, timeout=60,
    )
    require(proc.returncode == 0, "cannot enumerate published Git tree")
    result: dict[str, str] = {}
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, encoded = raw.split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split()
        require(mode in {"100644", "100755"} and object_type == "blob",
                f"unsupported published object for deployment: {encoded!r} mode={mode} type={object_type}")
        name = encoded.decode("utf-8", "surrogateescape")
        blob = subprocess.run(
            ["git", "cat-file", "blob", oid], cwd=root, capture_output=True, timeout=60,
        )
        require(blob.returncode == 0, f"cannot read Git blob for {name}")
        result[name] = sha256_bytes(blob.stdout)
    return result


def reject_link_escape(path: Path, windows: bool, recursive: bool = True) -> None:
    require(path.exists(), f"install path is missing: {path}")
    require(path.is_absolute() and ".." not in path.parts,
            f"install path must be literal and absolute: {path}")
    cursor = path
    while True:
        require(not cursor.is_symlink(), f"symlink ancestor is forbidden: {cursor}")
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    if recursive and path.is_dir():
        for current, directories, files in os.walk(path, followlinks=False):
            current_path = Path(current)
            for name in directories:
                child = current_path / name
                mode = child.stat(follow_symlinks=False).st_mode
                require(stat.S_ISDIR(mode) and not child.is_symlink(),
                        f"linked/special directory is forbidden in install: {child}")
            for name in files:
                child = current_path / name
                mode = child.stat(follow_symlinks=False).st_mode
                require(stat.S_ISREG(mode) and not child.is_symlink(),
                        f"linked/special file is forbidden in install: {child}")
    if not windows:
        return
    win_path = run("wslpath", "-w", str(path), cwd=ROOT)
    escaped = win_path.replace("'", "''")
    recurse = (
        "$items += @(Get-ChildItem -LiteralPath $root.FullName -Force -Recurse -ErrorAction Stop);"
        if recursive and path.is_dir() else ""
    )
    script = (
        f"$root=Get-Item -LiteralPath '{escaped}' -Force -ErrorAction Stop;"
        "$items=@($root);$p=$root.Parent;while($null -ne $p){$items+=@($p);$p=$p.Parent};"
        f"{recurse}"
        "$bad=@($items|Where-Object{($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0});"
        "if($bad.Count -ne 0){$bad|ForEach-Object{$_.FullName};exit 3}"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, timeout=120,
    )
    require(proc.returncode == 0,
            f"Windows reparse-point escape detected at {path}: "
            f"{proc.stdout.decode('utf-8', errors='replace').strip()}")


def actual_hashes(root: Path, windows: bool) -> dict[str, str]:
    require(root.is_dir(), f"install directory is missing: {root}")
    reject_link_escape(root, windows)
    result: dict[str, str] = {}
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            path = current_path / name
            require(not path.is_symlink(), f"symlink directory is forbidden in install: {path}")
        for name in files:
            path = current_path / name
            mode = path.stat(follow_symlinks=False).st_mode
            require(stat.S_ISREG(mode) and not path.is_symlink(),
                    f"special/symlink file is forbidden in install: {path}")
            result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def verify_codex_cache(home: Path, expected: dict[str, str], windows: bool) -> str:
    target = home / ".codex" / "plugins" / "cache" / "personal" / "idea-to-deploy" / VERSION
    actual = actual_hashes(target, windows)
    require(actual == expected,
            f"Codex cache hash drift at {target}: missing={sorted(set(expected) - set(actual))[:5]} "
            f"extra={sorted(set(actual) - set(expected))[:5]}")
    return str(target)


def claude_expected(tracked: dict[str, str]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for name, digest in tracked.items():
        rel = Path(name)
        if rel.parts[0] == "skills":
            target = name
        elif rel.parts[0] == "agents" and rel.suffix == ".md":
            target = name
        elif rel.parts[0] == "hooks" and rel.suffix in {".sh", ".py"}:
            target = name
        elif len(rel.parts) == 4 and rel.parts[:2] == ("docs", "templates") and rel.parts[2] in {"itd", "itd-memory"}:
            target = Path("templates", *rel.parts[2:]).as_posix()
        elif name == "scripts/itd_otel_export.py":
            target = name
        else:
            continue
        expected[target] = digest
    return expected


def desired_hooks() -> dict:
    source = (ROOT / "scripts" / "sync-to-active.sh").read_text(encoding="utf-8")
    match = re.search(r"DESIRED_HOOKS=\$\(cat <<'JSON'\n(.+?)\nJSON\n\)", source, re.DOTALL)
    require(bool(match), "cannot locate managed Claude hooks in sync-to-active.sh")
    return json.loads(match.group(1))


def normalized_windows_hooks(desired: dict, home: Path, actual: dict) -> dict:
    normalized = json.loads(json.dumps(desired))
    win_home = run("wslpath", "-w", str(home), cwd=ROOT).replace("\\", "/")
    expected_root = f"{win_home}/.claude/hooks/"
    interpreter = os.environ.get("ITD_WIN_PYTHON", "").strip().replace("\\", "/")
    require(bool(interpreter),
            "ITD_WIN_PYTHON must bind deployment proof to the sync interpreter override")
    mounted_interpreter = Path(run("wslpath", "-u", interpreter, cwd=ROOT))
    reject_link_escape(mounted_interpreter, True, recursive=False)
    require(mounted_interpreter.is_file(), "ITD_WIN_PYTHON does not name a regular file")
    for event, groups in normalized.items():
        actual_groups = actual.get(event)
        require(isinstance(actual_groups, list) and len(actual_groups) == len(groups),
                f"Windows Claude settings group drift for {event}")
        for group, actual_group in zip(groups, actual_groups):
            require(group.get("matcher") == actual_group.get("matcher"),
                    f"Windows Claude matcher drift for {event}")
            hooks = group.get("hooks", [])
            actual_hooks = actual_group.get("hooks", [])
            require(len(hooks) == len(actual_hooks), f"Windows Claude hook count drift for {event}")
            for hook, actual_hook in zip(hooks, actual_hooks):
                script_match = re.search(r"([a-z0-9-]+\.sh)$", hook["command"])
                require(bool(script_match), "unexpected canonical Claude hook command")
                command = str(actual_hook.get("command") or "").replace("\\", "/")
                suffix = expected_root + script_match.group(1)
                expected_command = f'"{interpreter}" -X utf8 "{suffix}"'
                require(command == expected_command,
                        f"Windows Claude wrapper drift for {script_match.group(1)}")
                hook["command"] = command
    return normalized


def verify_claude(home: Path, expected: dict[str, str], windows: bool) -> str:
    target = home / ".claude"
    require(target.is_dir(), f"Claude home is missing: {target}")
    for relative in ("skills", "agents", "hooks", "templates", "scripts"):
        reject_link_escape(target / relative, windows)
    reject_link_escape(target / "settings.json", windows, recursive=False)
    reject_link_escape(target / "CLAUDE.md", windows, recursive=False)
    drift = [name for name, digest in expected.items()
             if not (target / name).is_file()
             or (target / name).is_symlink()
             or not stat.S_ISREG((target / name).stat(follow_symlinks=False).st_mode)
             or sha256(target / name) != digest]
    require(not drift, f"Claude active install hash drift at {target}: {drift[:8]}")
    settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
    managed = {key: settings.get("hooks", {}).get(key) for key in desired_hooks()}
    canonical = desired_hooks()
    if windows:
        canonical = normalized_windows_hooks(canonical, home, managed)
    require(managed == canonical, f"Claude managed settings drift at {target / 'settings.json'}")
    return str(target)


def verify_router(path: Path, host: str, windows: bool) -> None:
    reject_link_escape(path, windows, recursive=False)
    require(path.is_file(), f"global {host} router is missing: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if "Codex" in host:
        expected = (ROOT / "docs" / "templates" / "global-codex-agents.md").read_text(encoding="utf-8")
        require(text == expected, f"global {host} router differs from the canonical policy: {path}")
        return
    template = (ROOT / "docs" / "templates" / "global-claude-md.md").read_text(encoding="utf-8")
    begin = "<!-- ITD:BEGIN"
    end = "<!-- ITD:END methodology -->"
    require(text.count(begin) == 1 and text.count(end) == 1,
            f"global {host} must contain exactly one managed ITD block: {path}")
    require(template.count(begin) == 1 and template.count(end) == 1,
            "canonical Claude template must contain exactly one managed ITD block")
    tb, te = template.find(begin), template.find(end)
    ab, ae = text.find(begin), text.find(end)
    require(min(tb, te, ab, ae) >= 0, f"managed ITD block is missing in {path}")
    require(text[ab:ae + len(end)] == template[tb:te + len(end)],
            f"global {host} managed policy differs from the canonical block: {path}")
    lowered = text.lower()
    require("product factory" not in lowered and "pfo_global" not in lowered,
            f"global {host} contains legacy PFO policy outside the canonical block")


def deployment_checks(branch: str, wsl: Path | None, windows: Path | None) -> dict:
    result = publication_checks(branch)
    wsl_home = (wsl or Path.home()).absolute()
    win_home = (windows or windows_home()).absolute()
    source = tracked_hashes(ROOT)
    claude = claude_expected(source)
    result["codexInstalls"] = [
        verify_codex_cache(wsl_home, source, False),
        verify_codex_cache(win_home, source, True),
    ]
    result["claudeInstalls"] = [verify_claude(wsl_home, claude, False), verify_claude(win_home, claude, True)]
    verify_router(wsl_home / ".codex" / "AGENTS.md", "WSL Codex", False)
    verify_router(win_home / ".codex" / "AGENTS.md", "Windows Codex", True)
    verify_router(wsl_home / ".claude" / "CLAUDE.md", "WSL Claude", False)
    verify_router(win_home / ".claude" / "CLAUDE.md", "Windows Claude", True)
    result["routers"] = 4
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("candidate", "publication", "deployment"), default="candidate")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--wsl-home", type=Path)
    parser.add_argument("--windows-home", type=Path)
    args = parser.parse_args()
    try:
        if args.phase == "candidate":
            details = candidate_checks()
        elif args.phase == "publication":
            details = publication_checks(args.branch)
        else:
            details = deployment_checks(args.branch, args.wsl_home, args.windows_home)
    except (ReleaseError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"phase": args.phase, "status": "PASSED", **details}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
