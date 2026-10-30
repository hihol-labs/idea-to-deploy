#!/usr/bin/env python3
"""Plan session 10 (ADR-016): machine-verified provenance of a ledger close.

Before the model review of a pure ledger-close candidate (coverage inherited
from the closed unit) `itd_free_reviewer_producer.freeze_packet` resolves the
scope's "Start from" commit and every commit named in the added ledger lines,
relates them with `git merge-base --is-ancestor` and `git rev-parse <sha>^`,
and hands the reviewer a MACHINE-VERIFIED PROVENANCE block with the
no-inference instruction. A scope that names no resolvable start commit, or a
start commit outside the candidate's history, is UNVERIFIED before any model
call (the REL-1.109.1 false parent/child finding).

Run: sh skills/_shared/itd_py.sh tests/verify_close_provenance.py
"""
from __future__ import annotations

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
PRODUCER = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"

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


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
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


def commit(root: Path, name: str) -> str:
    write(root / f"{name}.txt", f"{name}\n")
    git(root, "add", f"{name}.txt")
    git(root, "commit", "-qm", name)
    return git(root, "rev-parse", "HEAD")


producer = load_module("itd_free_reviewer_producer_close", PRODUCER)

# ---------------------------------------------------------------------------
print("[1] the provenance block on a three-commit history")
with tempfile.TemporaryDirectory(prefix="close-prov-") as td:
    repo = Path(td).resolve()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "prov@example.test")
    git(repo, "config", "user.name", "Provenance")
    sha_a = commit(repo, "a")
    sha_b = commit(repo, "b")
    sha_c = commit(repo, "c")
    git(repo, "checkout", "-qb", "side", sha_a)
    sha_d = commit(repo, "d")
    git(repo, "checkout", "-q", "-")
    scope = f"## Current Task\n- Start from merged main `{sha_a[:7]}`.\n"
    header = (
        f"diff --git a/.itd-memory/events.jsonl b/.itd-memory/events.jsonl\n"
        f"index {sha_c[:7]}..{sha_b[:7]} 100644\n"
        "--- a/.itd-memory/events.jsonl\n+++ b/.itd-memory/events.jsonl\n@@ -1 +1 @@\n"
    )
    diff = header + (
        f"+{{\"evidence\": \"PR merged to main {sha_b[:7]}; branch head {sha_d[:9]}; "
        "tree feedface0 (not a commit); receipt 75761b17dc7f; count 1793347845\"}\n"
        f"-old line naming {sha_c[:7]} must be ignored\n"
    )
    block = producer._closing_provenance(repo, base=sha_b, parent=sha_c,
                                         scope_text=scope, diff_text=diff)
    check("the provenance block is closed and names the method",
          set(block) == {"version", "kind", "method", "baseCommit", "parentCommit",
                         "baseIsAncestorOfParent", "scopeStart", "commits",
                         "unresolved", "ambiguous"}
          and block["kind"] == "itd-ledger-close-provenance"
          and "merge-base --is-ancestor" in block["method"], json.dumps(block)[:300])
    check("the scope start is resolved from its short form and verified as an ancestor of the parent",
          block["scopeStart"] == {"mentionedAs": sha_a[:7], "sha": sha_a, "ancestorOfParent": True},
          json.dumps(block["scopeStart"]))
    by_mention = {row["mentionedAs"]: row for row in block["commits"]}
    check("a commit named in an added ledger line is resolved with its first parent and ancestry",
          by_mention.get(sha_b[:7]) == {
              "mentionedAs": sha_b[:7], "sha": sha_b, "firstParent": sha_a,
              "ancestorOfParent": True, "descendantOfScopeStart": True},
          json.dumps(by_mention.get(sha_b[:7])))
    check("a squashed branch head outside the history is reported, not judged",
          by_mention.get(sha_d[:9]) == {
              "mentionedAs": sha_d[:9], "sha": sha_d, "firstParent": sha_a,
              "ancestorOfParent": False, "descendantOfScopeStart": True},
          json.dumps(by_mention.get(sha_d[:9])))
    check("non-commit tokens are listed as unresolved, digits-only ones included; removed lines and file headers are ignored",
          block["unresolved"] == ["feedface0", "75761b17dc7f", "1793347845"]
          and sha_c[:7] not in by_mention and block["ambiguous"] == [],
          json.dumps(block["unresolved"]))
    plus_content = header + f"+++ not a header: merged at {sha_b[:7]}\n"
    plus_block = producer._closing_provenance(repo, base=sha_b, parent=sha_c,
                                              scope_text=scope, diff_text=plus_content)
    check("an added ledger line whose content begins with ++ is still read inside the hunk",
          [row["sha"] for row in plus_block["commits"]] == [sha_b], json.dumps(plus_block["commits"]))
    original_status = producer._git_status

    def ambiguous_status(root, *arguments):
        if arguments[:2] == ("rev-parse", "--verify") and arguments[3].startswith("abcdef1"):
            return 128, ""
        if arguments[:1] == ("rev-parse",) and arguments[1] == "--disambiguate=abcdef1":
            return 0, "abcdef1" + "0" * 33 + "\nabcdef1" + "1" * 33
        return original_status(root, *arguments)

    producer._git_status = ambiguous_status
    try:
        amb = producer._closing_provenance(repo, base=sha_b, parent=sha_c, scope_text=scope,
                                           diff_text=header + "+ledger names abcdef1 twice\n")
        try:
            producer._closing_provenance(repo, base=sha_b, parent=sha_c,
                                         scope_text="Start from `abcdef1`\n", diff_text=header)
            amb_start = "accepted"
        except producer.FreeReviewError as exc:
            amb_start = f"{exc.status}: {exc}"
    finally:
        producer._git_status = original_status
    check("a prefix matching more than one object is listed as ambiguous, not as unresolved",
          amb["ambiguous"] == ["abcdef1"] and amb["unresolved"] == [], json.dumps(amb["ambiguous"]))
    check("an ambiguous scope start is UNVERIFIED with its own reason",
          amb_start.startswith("UNVERIFIED") and "ambiguous" in amb_start, amb_start)

    def refused(scope_text: str) -> str:
        try:
            producer._closing_provenance(repo, base=sha_b, parent=sha_c,
                                         scope_text=scope_text, diff_text="")
            return "accepted"
        except producer.FreeReviewError as exc:
            return f"{exc.status}: {exc}"

    outside = refused(f"Start from `{sha_d[:7]}`\n")
    check("a scope start outside the candidate's history is UNVERIFIED before any model call",
          outside.startswith("UNVERIFIED") and "not an ancestor" in outside, outside)
    absent = refused("## Current Task\n- Deliver the unit.\n")
    check("a scope that names no start commit is UNVERIFIED (the ancestry proof is required)",
          absent.startswith("UNVERIFIED") and "names no start commit" in absent, absent)
    unresolvable = refused(f"- Start from merged main `deadbeef1` (see also {sha_a[:7]}).\n")
    check("an unresolvable first token on the start line is UNVERIFIED, a later hash is not substituted",
          unresolvable.startswith("UNVERIFIED") and "cannot be resolved" in unresolvable,
          unresolvable)
    bare_start = refused("- Start from merged main (sha pending).\n")
    check("a start line without a commit token is skipped; with no token-bearing start line the close is UNVERIFIED",
          bare_start.startswith("UNVERIFIED") and "names no start commit" in bare_start, bare_start)
    prose_first = refused(f"We start from the premise that closes are reviewed.\n- Start from merged main `{sha_b[:7]}`\n")
    check("a prose line that merely says 'start from' does not hide the directive that follows it (review a11)",
          prose_first == "accepted", prose_first)
    upper_start = refused(f"- Start from merged main `{sha_b[:7].upper()}`\n")
    check("an uppercase scope-start token resolves (git hex is case-insensitive)", upper_start == "accepted", upper_start)
    upper_block = producer._closing_provenance(repo, base=sha_b, parent=sha_c, scope_text=scope,
                                               diff_text=header + f"+merged {sha_b[:7].upper()}\n")
    check("an uppercase commit reference in an added ledger line is resolved and keeps its spelling",
          [(row["mentionedAs"], row["sha"]) for row in upper_block["commits"]] == [(sha_b[:7].upper(), sha_b)],
          json.dumps(upper_block["commits"])[:200])
    flood = header + "".join(
        f"+{{\"count\": {1793347845 + i}}}\n" for i in range(70)
    ) + f"+{{\"evidence\": \"merged to main {sha_b[:7]}\"}}\n"
    flooded = producer._closing_provenance(repo, base=sha_b, parent=sha_c,
                                           scope_text=scope, diff_text=flood)
    check("seventy decimal counters before a commit do not crowd it out of the block and are all listed as unresolved (review a13)",
          [row["sha"] for row in flooded["commits"]] == [sha_b]
          and len(flooded["unresolved"]) == 70 and flooded["ambiguous"] == [],
          json.dumps({"commits": len(flooded["commits"]), "unresolved": flooded["unresolved"][:3]}))
    many = []
    for i in range(producer.MAX_PROVENANCE_COMMITS + 1):
        many.append(commit(repo, f"m{i:03d}"))
    head_many = git(repo, "rev-parse", "HEAD")
    crowd = header + "".join(f"+{sha[:10]}\n" for sha in many)
    seventy = header + "".join(f"+ref deadbeef{i:03d}c\n" for i in range(70)) + f"+merged at {sha_b[:7]}\n"
    seventy_block = producer._closing_provenance(repo, base=sha_b, parent=sha_c,
                                                 scope_text=scope, diff_text=seventy)
    check("seventy unresolved names are all kept for the reviewer, nothing is truncated",
          len(seventy_block["unresolved"]) == 70
          and [row["sha"] for row in seventy_block["commits"]] == [sha_b],
          str(len(seventy_block["unresolved"])))
    swarm = header + "".join(f"+ref cafe{i:05x}\n" for i in range(producer.MAX_PROVENANCE_TOKENS + 1)) + f"+merged at {sha_b[:7]}\n"
    try:
        producer._closing_provenance(repo, base=sha_b, parent=sha_c, scope_text=scope, diff_text=swarm)
        swarmed = "accepted"
    except producer.FreeReviewError as exc:
        swarmed = f"{exc.status}: {exc}"
    check("a close naming more distinct hex-looking tokens than the work bound is UNVERIFIED before any resolution, never a silent cut",
          swarmed.startswith("UNVERIFIED") and "more hex tokens" in swarmed, swarmed)
    try:
        producer._closing_provenance(repo, base=sha_b, parent=sha_c, scope_text="## Scope\n- no start line here\n", diff_text=swarm)
        unstarted_swarm = "accepted"
    except producer.FreeReviewError as exc:
        unstarted_swarm = f"{exc.status}: {exc}"
    check("the token bound fires before the scope start is resolved (no git call precedes it)",
          "more hex tokens" in unstarted_swarm, unstarted_swarm)
    try:
        producer._closing_provenance(repo, base=head_many, parent=head_many,
                                     scope_text=scope, diff_text=crowd)
        crowded = "accepted"
    except producer.FreeReviewError as exc:
        crowded = f"{exc.status}: {exc}"
    check("a close naming more commits than the block relates is UNVERIFIED, never silently shortened",
          crowded.startswith("UNVERIFIED") and "more commits" in crowded, crowded)
    note = producer._provenance_note({"provenance": block,
                                      "candidate": {"baseCommit": sha_b, "parentCommit": sha_c},
                                      "evidenceCoverage": {"coverageSource": "closed-unit-inherited"}})
    check("the reviewer note renders the block as ground truth and forbids inference from text",
          note.startswith("MACHINE-VERIFIED PROVENANCE\n")
          and json.dumps(block, ensure_ascii=False, sort_keys=True) in note
          and "do not infer parent/child" in note, note[:120])
    check("a packet without provenance renders no note",
          producer._provenance_note({}) == "")
    def packet_for(value, coverage="closed-unit-inherited", base=None, parent=None):
        return {
            "provenance": value,
            "candidate": {"baseCommit": base or sha_b, "parentCommit": parent or sha_c},
            "evidenceCoverage": {"coverageSource": coverage},
        }

    def rendered(value, **kw) -> str:
        try:
            producer._provenance_note(packet_for(value, **kw))
            return "rendered"
        except producer.FreeReviewError as exc:
            return exc.status

    mutations = {
        "wrong kind": {**block, "kind": "other"},
        "extra field": {**block, "extra": 1},
        "missing field": {k: v for k, v in block.items() if k != "ambiguous"},
        "short sha": {**block, "parentCommit": sha_c[:7]},
        "unproven base ancestry": {**block, "baseIsAncestorOfParent": False},
        "scope start not an ancestor": {**block, "scopeStart": {**block["scopeStart"], "ancestorOfParent": False}},
        "commit row with a string flag": {**block, "commits": [{**block["commits"][0], "ancestorOfParent": "yes"}]},
        "unresolved not strings": {**block, "unresolved": [1]},
        "wrong method": {**block, "method": "trust me"},
    }
    bad = [name for name, value in mutations.items() if rendered(value) != "UNVERIFIED"]
    check("every malformed or altered provenance block fails closed under the trusted heading",
          not bad and rendered(block) == "rendered", json.dumps(bad))
    check("a block about another candidate (base or parent differing) is refused",
          rendered(block, base=sha_a) == "UNVERIFIED" and rendered(block, parent=sha_b) == "UNVERIFIED")
    check("a provenance block with active-unit coverage is UNVERIFIED on the note surface",
          rendered(block, coverage="active-unit") == "UNVERIFIED")

# ---------------------------------------------------------------------------
print("[2] end-to-end through freeze_packet on a real ledger-close repository")
LEDGER_STATE_REL = ".itd-memory/STATE.json"
LEDGER_CONTRACT_REL = ".itd/ACCEPTANCE_CONTRACT.json"


def ledger_contract(*, closed: bool) -> dict:
    followup = {
        "unitId": "DELIVERED",
        "status": "verified" if closed else "in_progress",
        "reviewPolicy": {
            "mode": "evidence-first", "riskTier": "low",
            "requiredImpactClasses": ["correctness"],
            "minimumIndependentReviewers": 0,
            "explorer": "isolated-machine-oracle",
            "adjudicator": "sealed-host-union",
        },
    }
    if closed:
        followup["closedAt"] = "2026-10-30T12:00:00Z"
    return {
        "version": 2,
        "criteria": [{
            "id": "DELIVERED-AC1", "status": "passed",
            "reviewEvidence": {
                "claim": "The delivered behaviour is executable.",
                "impactClasses": ["correctness"], "oracleIds": ["domain-oracle"],
            },
        }],
        "activeFollowup": followup,
    }


def machine_receipt(box: Path, repo: Path, parent: str, tree: str,
                    contract: Path, scope_file: Path) -> Path:
    diff_bytes = subprocess.run(
        ["git", "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", parent, "--"],
        cwd=repo, capture_output=True, timeout=30, check=True).stdout
    machine = box / "ledger-machine.json"
    write(machine, json.dumps({
        "version": 1, "kind": "machine-verification", "unitId": "DELIVERED",
        "riskTier": "low", "outcome": "PASSED",
        "candidate": {
            "baseCommit": parent, "reviewedTree": tree,
            "diffHash": hashlib.sha256(diff_bytes).hexdigest(),
            "scopeContractHash": hashlib.sha256(scope_file.read_bytes()).hexdigest(),
            "acceptanceContractHash": hashlib.sha256(contract.read_bytes()).hexdigest(),
        },
        "declaredInputs": [],
        "runs": [{"id": "domain-oracle", "command": "true",
                  "commandSha256": hashlib.sha256(b"true").hexdigest(),
                  "exitCode": 0, "executedTree": tree}],
    }))
    return machine


def ledger_close_repo(box: Path, *, scope_line: str | None) -> tuple[Path, str, str, Path, Path, str]:
    """A repository whose staged diff is a pure ledger close; the scope names
    the seed commit as its start when ``scope_line`` is given."""
    repo = box / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "close@example.test")
    git(repo, "config", "user.name", "Ledger Close")
    git(repo, "remote", "add", "origin", "https://github.com/hihol-labs/idea-to-deploy.git")
    git(repo, "commit", "--allow-empty", "-qm", "seed")
    seed = git(repo, "rev-parse", "HEAD")
    contract = repo / LEDGER_CONTRACT_REL
    state = repo / LEDGER_STATE_REL
    write(contract, json.dumps(ledger_contract(closed=False), indent=2))
    write(state, json.dumps({"currentUnit": {"id": "DELIVERED", "status": "in_progress"}}))
    scope_file = repo / "scope.md"
    start = (scope_line or "").replace("<seed>", seed[:7])
    write(scope_file, "# Frozen scope\n" + (start + "\n" if start else "") + "Ledger close only.\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    parent = git(repo, "rev-parse", "HEAD")
    write(contract, json.dumps(ledger_contract(closed=True), indent=2))
    write(state, json.dumps({"currentUnit": {"id": "DELIVERED", "status": "verified",
                                              "evidence": f"merged at {seed[:7]}"}}))
    git(repo, "add", "-A")
    tree = git(repo, "write-tree")
    return repo, seed, parent, contract, scope_file, tree


with tempfile.TemporaryDirectory(prefix="close-prov-e2e-") as td:
    box = Path(td).resolve()
    repo, seed, parent, contract, scope_file, tree = ledger_close_repo(
        box, scope_line="Start from merged main `<seed>`.")
    machine = machine_receipt(box, repo, parent, tree, contract, scope_file)
    packet = producer.freeze_packet(
        root=repo, base_commit=parent, repository="hihol-labs/idea-to-deploy",
        pull_request=None, expected_head_sha=None, scope_file=scope_file,
        acceptance_file=contract, machine_receipt=machine)
    coverage = packet.get("evidenceCoverage") or {}
    provenance = packet.get("provenance") or {}
    check("a real ledger close inherits coverage and carries the provenance block",
          coverage.get("coverageSource") == "closed-unit-inherited"
          and provenance.get("kind") == "itd-ledger-close-provenance"
          and provenance["scopeStart"] == {"mentionedAs": seed[:7], "sha": seed,
                                           "ancestorOfParent": True}
          and provenance["baseCommit"] == parent and provenance["parentCommit"] == parent,
          json.dumps({"coverage": coverage.get("coverageSource"), "provenance": provenance})[:400])
    check("the commit named in the closing ledger line is related to the parent by git",
          any(row["sha"] == seed and row["ancestorOfParent"] is True
              and row["firstParent"] is None for row in provenance.get("commits", [])),
          json.dumps(provenance.get("commits")))
    prompt = producer.review_prompt(packet)
    check("the closing review prompt shows the verified provenance before the inherited coverage note",
          "MACHINE-VERIFIED PROVENANCE" in prompt
          and prompt.index("MACHINE-VERIFIED PROVENANCE")
          < prompt.index("closing commit: coverage inherited from the delivered unit DELIVERED"))
    try:
        producer.validate_review_prompt_artifact(
            packet, prompt, {"verdict": "PASSED", "findings": [], "unverified": []})
        rootless = "accepted"
    except producer.FreeReviewError as exc:
        rootless = f"{exc.status}: {exc}"
    check("a provenance-bearing packet is never validated without the repository root (fail closed, not optional)",
          rootless.startswith("UNVERIFIED") and "repository root" in rootless, rootless)
    dummy = dict(maker={}, reviewer={}, attempts=[], isolation={}, key_id="k", private_key=b"")
    try:
        producer.phase_one_receipt(packet=packet, prompt=prompt,
                                   report={"verdict": "PASSED", "findings": [], "unverified": []},
                                   reviewers=[{}, {}], root=None, **dummy)
        quorum_rootless = "accepted"
    except producer.FreeReviewError as exc:
        quorum_rootless = f"{exc.status}: {exc}"
    check("the quorum branch of phase_one_receipt refuses a provenance-bearing packet without the root before anything else",
          quorum_rootless.startswith("UNVERIFIED") and "repository root" in quorum_rootless, quorum_rootless)
    tampered = json.loads(json.dumps(packet))
    tampered["provenance"]["commits"][0]["ancestorOfParent"] = False
    try:
        producer.phase_one_receipt(packet=tampered, prompt=producer.review_prompt(tampered),
                                   report={"verdict": "PASSED", "findings": [], "unverified": []},
                                   reviewers=[{}, {}], root=repo, **dummy)
        quorum_tampered = "accepted"
    except producer.FreeReviewError as exc:
        quorum_tampered = f"{exc.status}: {exc}"
    check("the quorum branch recomputes the block with git and refuses an altered ancestry value",
          quorum_tampered.startswith("UNVERIFIED") and "recomputation" in quorum_tampered, quorum_tampered)
    plain = {k: v for k, v in packet.items() if k != "provenance"}
    plain["evidenceCoverage"] = {**packet["evidenceCoverage"], "coverageSource": "active-unit"}
    check("a packet without a provenance block still validates without a root",
          producer.validate_review_prompt_artifact(
              plain, producer.review_prompt(plain), {"verdict": "PASSED", "findings": [], "unverified": []})
          == {"mode": "direct", "unitCount": 1})
    def prompt_status(value) -> str:
        try:
            producer.review_prompt(value)
            return "rendered"
        except producer.FreeReviewError as exc:
            return exc.status

    stripped = dict(packet)
    stripped.pop("evidenceCoverage")
    active = dict(packet)
    active["evidenceCoverage"] = {**packet["evidenceCoverage"], "coverageSource": "active-unit"}
    check("a provenance block without inherited coverage fails closed on the flat prompt (no coverage, active-unit coverage)",
          prompt_status(stripped) == "UNVERIFIED" and prompt_status(active) == "UNVERIFIED")
    check("the prompt artifact revalidates with a git recomputation of the block when the repository is given",
          producer.validate_review_prompt_artifact(
              packet, prompt, {"verdict": "PASSED", "findings": [], "unverified": []}, root=repo)
          == {"mode": "direct", "unitCount": 1})
    altered = json.loads(json.dumps(packet))
    altered["provenance"]["commits"][0]["ancestorOfParent"] = False
    altered_prompt = producer.review_prompt(altered)
    try:
        producer.validate_review_prompt_artifact(
            altered, altered_prompt, {"verdict": "PASSED", "findings": [], "unverified": []}, root=repo)
        recomputed = "accepted"
    except producer.FreeReviewError as exc:
        recomputed = f"{exc.status}: {exc}"
    check("a structurally valid block with an altered ancestry value is refused by the git recomputation",
          recomputed.startswith("UNVERIFIED") and "recomputation" in recomputed, recomputed)

with tempfile.TemporaryDirectory(prefix="close-prov-nostart-") as td:
    box = Path(td).resolve()
    repo, seed, parent, contract, scope_file, tree = ledger_close_repo(box, scope_line=None)
    machine = machine_receipt(box, repo, parent, tree, contract, scope_file)
    try:
        producer.freeze_packet(
            root=repo, base_commit=parent, repository="hihol-labs/idea-to-deploy",
            pull_request=None, expected_head_sha=None, scope_file=scope_file,
            acceptance_file=contract, machine_receipt=machine)
        nostart = "packet frozen"
    except producer.FreeReviewError as exc:
        nostart = f"{exc.status}: {exc}"
    check("a ledger close whose scope names no start commit is UNVERIFIED before the model review",
          nostart.startswith("UNVERIFIED") and "names no start commit" in nostart, nostart)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
