#!/usr/bin/env python3
"""verify_installed_proof_head.py - INSTALLED-PROOF-HEAD-1: committed-head canaries in installed-proof.

BACKLOG P2 2026-09-27 (REL-1.106.0 rollback of the fourth command amendment): the installed-proof
leg of the release oracle, `tests/verify_route_debts.py --installed-proof`, revalidated the native
canary receipts only as STAGED candidates (`validate_machine` / `validate_adjudication` with the
default candidate mode), so the release verification had to run on a staged ledger-close
candidate. The live-evidence leg, `tests/verify_live_model_benchmark.py --require-evidence`, pins
the digest of a CLEAN checkout. One command on one checkout could not satisfy both, and the
release lost the `--require-evidence` flag inside its verificationCommand.

Contract of this oracle (all inside temporary repositories; the aggregate oracle and the
Verification Loop are loaded from source, the loop's producers run as real subprocesses):

  1. A canary minted with `--candidate-mode committed-head` on a clean checkout whose HEAD tree is
     the candidate is ACCEPTED by `validate_native_canary`, both directly on that checkout and
     from the isolated aggregate checkout the machine producer materializes.
  2. The validator still REFUSES: a receipt re-sealed over another candidate (mismatched), a
     receipt after HEAD moved past the commit it binds (stale), and a receipt minted in another
     repository (foreign). The mode names what a receipt binds on the checkout, not how it was
     minted: a staged mint before the commit is accepted after it on the same terms.
  3. docs/RELEASE_RUNBOOK.md carries a release command template: one line that runs BOTH
     `tests/verify_route_debts.py --installed-proof` and
     `tests/verify_live_model_benchmark.py --require-evidence`, and names the committed-head mint.
  4. This suite is registered in tests/run-all.sh.

RED on the pre-fix validator (staged-only revalidation, no runbook template), GREEN after.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
AGGREGATE = ROOT / "tests/verify_route_debts.py"
LOOP = ROOT / "skills/_shared/itd_verification_loop.py"
RUNBOOK = ROOT / "docs/RELEASE_RUNBOOK.md"
RUNALL = ROOT / "tests/run-all.sh"
UNIT = "ROUTE-DEBTS:deployment-canary"


def module(name: str, path: Path):
    """Execute the module from its source bytes read now.

    ``spec.loader.exec_module`` may serve a timestamp-valid stale ``.pyc``
    (a same-size, same-mtime edit), so this acceptance oracle would exercise
    old validator bytes and report GREEN for code that is not on disk.
    """
    value = types.ModuleType(name)
    value.__file__ = str(path)
    sys.modules[name] = value
    exec(compile(path.read_bytes(), str(path), "exec"), value.__dict__)
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Fixture:
    """One synthetic repository whose HEAD commit is the candidate, with committed-head canaries."""

    def __init__(self, td: Path, rd, loop, label: str, commit_candidate: bool = True) -> None:
        self.rd, self.loop = rd, loop
        self.repo = (td / label).resolve()
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic installed-proof fixture")
        self.git("config", "user.email", "route@example.invalid")
        self.git("config", "core.hooksPath", str(self.repo / "no-hooks"))
        (self.repo / ".gitignore").write_text(".itd-memory/\n")
        (self.repo / ".itd").mkdir()
        (self.repo / ".itd/SCOPE_LOCK.md").write_text("Synthetic installed-proof fixture only")
        (self.repo / ".itd/ACCEPTANCE_CONTRACT.json").write_text(
            '{"criteria":[{"id":"fixture","status":"pending"}]}')
        (self.repo / "tests").mkdir()
        # The same closed native command the aggregate binds: the fixture's own
        # verify_route_debts.py writes the focused-suite completions to the log.
        (self.repo / "tests/verify_route_debts.py").write_text(
            "import pathlib,sys\n"
            + "raw=" + repr("".join("PASS " + suite + "\n" for suite in rd.REGRESSIONS).encode()) + "\n"
            + "pathlib.Path(sys.argv[2]).write_bytes(raw)\nsys.stdout.buffer.write(raw)\n")
        self.git("add", ".")
        # The label makes the baseline commit distinct per fixture even when two
        # fixtures with identical trees, author and message land in the same
        # second: a foreign canary must never share the primary parent commit.
        self.git("commit", "-qm", f"synthetic baseline {label}")
        (self.repo / "change.txt").write_text(f"candidate {label}\n")
        self.git("add", "change.txt")
        if commit_candidate:
            self.git("commit", "-qm", "the candidate: committed, HEAD tree equals it")
        self.mint_mode = "committed-head" if commit_candidate else "staged"
        policy, _ = loop.load_policy()
        self.receipt_root = loop.receipt_root(self.repo, policy)
        self.proofdir = self.receipt_root / "route-fixture"
        self.proofdir.mkdir(parents=True)
        self.snapshotdir = self.repo / ".itd-memory/host-inputs/ROUTE-DEBTS"
        self.log = self.snapshotdir / "route-fixture/native-tests.log"
        self.log.parent.mkdir(parents=True)
        self.mp, self.ap = self.proofdir / "machine.json", self.proofdir / "adjudication.json"
        self.produce("machine", "--command", "native=" + rd.native_test_command(self.log),
                     "--output", str(self.mp))
        self.produce("adjudicate", "--machine", str(self.mp), "--output", str(self.ap))
        self.snapshots(self.mp, self.ap)
        self.host = {"machine": self.receipt_ref(self.mp), "adjudication": self.receipt_ref(self.ap),
                     "nativeTestsLog": self.input_ref(self.log)}
        self.machine = json.loads(self.mp.read_text(encoding="utf-8"))
        self.expected = {"release": self.machine["candidate"]["methodologyVersion"],
                         "runtimeSha256": "a" * 64}

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True,
                              check=True, encoding="utf-8").stdout

    def produce(self, verb: str, *args: str) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(LOOP), verb, "--root", str(self.repo), "--unit-id", UNIT,
             "--risk-tier", "low", "--candidate-mode", self.mint_mode, *args],
            cwd=self.repo, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"{verb} producer failed:\n{result.stdout}{result.stderr}"

    def receipt_ref(self, p: Path) -> dict:
        return {"path": str(p.relative_to(self.receipt_root)), "sha256": sha(p)}

    def input_ref(self, p: Path) -> dict:
        return {"path": str(p.relative_to(self.snapshotdir)), "sha256": sha(p)}

    def snapshots(self, *paths: Path) -> None:
        for item in paths:
            target = self.snapshotdir / item.relative_to(self.receipt_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)

    def install_machine(self, payload: dict) -> None:
        self.mp.write_text(json.dumps(payload))
        self.snapshots(self.mp)
        self.host["machine"] = self.receipt_ref(self.mp)

    def validate(self, root: Path | None = None, proof: Path | None = None,
                 candidate_repo: Path | None = None) -> dict:
        previous = self.rd.ROOT
        self.rd.ROOT = self.repo if root is None else root
        try:
            return self.rd.validate_native_canary(
                (self.snapshotdir if proof is None else proof) / "INSTALLED.json",
                self.host, self.expected, self.loop, candidate_repo)
        finally:
            self.rd.ROOT = previous

    def refused(self, **kwargs) -> str | None:
        try:
            self.validate(**kwargs)
        except Exception as exc:  # the aggregate maps ValueError/LoopError to FAIL
            return str(exc)
        return None


def main() -> int:
    fails: list[str] = []
    passed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed
        if ok:
            passed += 1
            print(f"ok   {name}")
        else:
            fails.append(name)
            print(f"FAIL {name}: {detail}")

    rd = module("installed_proof_head_aggregate", AGGREGATE)
    loop = module("installed_proof_head_loop", LOOP)
    with tempfile.TemporaryDirectory(prefix="installed-proof-head-") as td:
        base = Path(td)
        fx = Fixture(base, rd, loop, "primary")
        head = fx.git("rev-parse", "HEAD").strip()
        parent = fx.git("rev-parse", "HEAD^").strip()
        check("fixture-canary-binds-committed-head",
              fx.machine["candidate"]["baseCommit"] == parent and fx.git("status", "--porcelain") == "",
              f"baseCommit={fx.machine['candidate']['baseCommit']} parent={parent} status clean required")

        # 1. Accepted on the clean checkout whose HEAD tree is the candidate.
        try:
            result = fx.validate()
            accepted, detail = result.get("status") == "PASSED", json.dumps(result, sort_keys=True)[:200]
        except Exception as exc:
            accepted, detail = False, f"{type(exc).__name__}: {exc}"
        check("accepts-committed-head-canary-on-clean-checkout", accepted, detail)
        check("replay-result-names-the-candidate-mode",
              accepted and result.get("candidateMode") == "committed-head", detail)

        # 1b. Accepted from the isolated aggregate checkout of the same clean HEAD.
        try:
            context = loop.candidate_context(fx.repo, "low")
            with loop.isolated_candidate(fx.repo, context) as isolated:
                copied = isolated / fx.snapshotdir.relative_to(fx.repo)
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(fx.snapshotdir, copied)
                previous = rd.ROOT
                rd.ROOT = isolated
                try:
                    bound = rd.native_source_candidate_repo(str(fx.repo), loop) == fx.repo
                finally:
                    rd.ROOT = previous
                isolated_result = fx.validate(root=isolated, proof=copied, candidate_repo=fx.repo)
            accepted, detail = bound and isolated_result.get("status") == "PASSED", json.dumps(isolated_result)[:200]
        except Exception as exc:
            accepted, detail = False, f"{type(exc).__name__}: {exc}"
        check("accepts-committed-head-canary-from-isolated-aggregate", accepted, detail)

        # 2a. Mismatched: the same receipt re-sealed over another diff.
        original = fx.mp.read_bytes()
        changed = copy.deepcopy(fx.machine)
        changed["candidate"]["diffHash"] = "0" * 64
        changed["candidateDigest"] = loop.candidate_digest(changed["candidate"])
        fx.install_machine(loop.seal_receipt(changed))
        reason = fx.refused()
        check("refuses-mismatched-candidate", reason is not None and "candidate" in reason, str(reason))
        fx.mp.write_bytes(original)
        fx.snapshots(fx.mp)
        fx.host["machine"] = fx.receipt_ref(fx.mp)
        check("fixture-restored-after-mismatch", fx.refused() is None, "restored receipt must be accepted again")

        # 2b. Stale: HEAD moves one commit past the candidate the canary binds.
        (fx.repo / "later.txt").write_text("a later change\n")
        fx.git("add", "later.txt")
        fx.git("commit", "-qm", "later commit: the canary is stale now")
        reason = fx.refused()
        check("refuses-stale-canary-after-head-moved",
              reason is not None and "binds neither the checkout HEAD nor its single parent" in reason,
              str(reason))
        fx.git("reset", "-q", "--hard", head)
        check("fixture-restored-after-stale", fx.git("rev-parse", "HEAD").strip() == head and fx.refused() is None,
              "HEAD back on the candidate must be accepted again")

        # 2c. Foreign: receipts minted in another repository, same unit and policy.
        # Its baseline commit differs by construction (label in the message), so
        # the refusal reason is deterministic, never a same-second hash collision.
        foreign = Fixture(base, rd, loop, "foreign")
        check("foreign-baseline-commit-is-distinct",
              foreign.git("rev-parse", "HEAD^").strip() != parent, "foreign parent must differ from primary parent")
        fx.install_machine(foreign.machine)
        shutil.copyfile(foreign.ap, fx.ap)
        fx.snapshots(fx.ap)
        fx.host["adjudication"] = fx.receipt_ref(fx.ap)
        reason = fx.refused()
        check("refuses-foreign-repository-canary",
              reason is not None and "binds neither the checkout HEAD nor its single parent" in reason,
              str(reason))
        # 2d. A staged mint before the commit binds the same parent/HEAD pair as a
        # committed-head mint after it: accepted on the same terms (by design;
        # the mode names what the receipt binds, not how it was minted).
        staged = Fixture(base, rd, loop, "staged-before-commit", commit_candidate=False)
        try:
            staged.git("commit", "-qm", "the candidate, committed after the staged mint")
            result = staged.validate()
            ok, detail = result.get("status") == "PASSED" and result.get("candidateMode") == "committed-head", str(result)[:200]
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        check("accepts-staged-mint-after-its-commit-as-committed-head", ok, detail)

    # 3. Runbook: one command with both legs on one clean checkout.
    runbook = RUNBOOK.read_text(encoding="utf-8")
    both = [line for line in runbook.splitlines()
            if "tests/verify_route_debts.py --installed-proof" in line
            and "tests/verify_live_model_benchmark.py --require-evidence" in line
            and " && " in line]
    check("runbook-release-command-carries-both-legs", len(both) >= 1,
          "docs/RELEASE_RUNBOOK.md needs one command line joining --installed-proof and --require-evidence with &&")
    check("runbook-names-committed-head-mint", "--candidate-mode committed-head" in runbook,
          "docs/RELEASE_RUNBOOK.md must say the canaries are minted with --candidate-mode committed-head")

    # 4. Registered in run-all.
    runall = RUNALL.read_text(encoding="utf-8")
    tokens: set[str] = set()
    for variable in ("CORE", "FULL"):
        match = re.search(rf'^{variable}="([^"]*)"', runall, re.M)
        if match:
            tokens.update(match.group(1).replace("\\\n", " ").split())
    check("run-all-registered", "verify_installed_proof_head" in tokens,
          "verify_installed_proof_head must be a token of CORE or FULL in tests/run-all.sh")

    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed ({passed} passed)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
