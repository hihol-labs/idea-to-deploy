#!/usr/bin/env python3
"""verify_machine_oracle_legs.py - ORACLE-LEGS-1 oracle.

`itd_verification_loop.py machine` minting for the claim equal to the active
follow-up unit refuses BEFORE running any leg when a `reviewEvidence.oracleIds`
entry of that unit's acceptance criteria is not among the `--command` leg ids.
Before the fix the gap surfaced only in the Sol producer
(`itd_review_evidence.coverage_matrix`: "... oracle X is missing"), after the
receipt was minted and a reviewer run was already paid for (TIER-WORDING-2,
committed-head p1).

Checks:
  1. a missing oracle refuses, names the criterion and the oracle, writes no
     receipt and runs no leg (a sentinel leg leaves no marker);
  2. every missing pair is named, not only the first one;
  3. a complete leg set mints as before (PASSED receipt);
  4. a `:general-review` claim mints with any leg set;
  5. a claim that is not the active unit, a closed follow-up and criteria
     without reviewEvidence mint as before;
  6. the contract is read from the candidate tree, not from the checkout:
     an oracle id added only to the staged contract is enforced;
  7. malformed explicit ownership of the active unit refuses before any leg;
  8. a follow-up without reviewPolicy is checked as well (intentional: the
     declared oracleIds name legs whether or not a policy is set);
  9. committed-head mode reads the contract of the committed tree;
 10. a declared but malformed reviewEvidence / oracleIds (not an object, not
     a list, empty, a non-string, a padded or duplicated id) refuses before
     any leg with the producer's rule (Sol s1);
 11. a git probe timeout is a refusal, not a traceback (/review r2);
 12. the producer rules are compiled from the current source: a stale
     __pycache__ entry with the same size and mtime is not run (Sol s3).

`--loop PATH` runs the checks against another copy of the Verification Loop
(RED-first on the pre-fix code).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCRIPT = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
UNIT = "U-legs"
PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"PASS  {name}")
    else:
        FAILED += 1
        print(f"FAIL  {name}: {detail}")


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True,
                   text=True, capture_output=True)


def criterion(cid: str, oracle_ids: list[str] | None, unit: str = UNIT) -> dict:
    row: dict = {"id": cid, "unitId": unit, "status": "pending",
                 "criterion": "fixture criterion"}
    if oracle_ids is not None:
        row["reviewEvidence"] = {"claim": "fixture claim",
                                 "impactClasses": ["correctness"],
                                 "oracleIds": oracle_ids}
    return row


POLICY = {"mode": "evidence-first", "riskTier": "medium",
          "requiredImpactClasses": ["correctness"],
          "minimumIndependentReviewers": 1,
          "explorer": "isolated-machine-oracle",
          "adjudicator": "sealed-host-union"}


def contract(criteria: list[dict], *, unit: str = UNIT,
             status: str = "active", policy: bool = True) -> dict:
    followup: dict = {"unitId": unit, "status": status}
    if policy:
        followup["reviewPolicy"] = dict(POLICY)
    return {"criteria": criteria, "activeFollowup": followup}


def write_contract(root: Path, value: dict) -> None:
    (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
        json.dumps(value, indent=1) + "\n", encoding="utf-8")


def fixture(value: dict) -> Path:
    root = Path(tempfile.mkdtemp(prefix="oracle-legs-")).resolve()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Oracle Legs")
    git(root, "config", "user.email", "legs@example.test")
    (root / ".gitignore").write_text(".itd-memory/\n", encoding="utf-8")
    (root / ".itd").mkdir()
    (root / ".itd" / "SCOPE_LOCK.md").write_text("# Scope\n", encoding="utf-8")
    write_contract(root, value)
    git(root, "commit", "--allow-empty", "-qm", "seed")
    (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "baseline")
    (root / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    git(root, "add", "app.py")
    return root


def ok_leg(ident: str) -> str:
    return f'{ident}="{sys.executable}" -c "pass"'


def marker_leg(ident: str, marker: Path) -> str:
    code = f"open({str(marker)!r}, 'w').close()"
    return f'{ident}="{sys.executable}" -c "{code}"'


def mint(script: Path, root: Path, claim: str, legs: list[str],
         mode: str = "staged"):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    args = [sys.executable, str(script), "machine", "--root", str(root),
            "--unit-id", claim, "--risk-tier", "medium",
            "--candidate-mode", mode, "--timeout", "30"]
    for leg in legs:
        args += ["--command", leg]
    return subprocess.run(args, cwd=root, text=True, capture_output=True,
                          encoding="utf-8", errors="replace", env=env,
                          timeout=120)


def receipts(root: Path) -> list[Path]:
    base = root / ".itd-memory" / "verification-loop"
    return sorted(base.rglob("*.json")) if base.exists() else []


def minted(proc) -> bool:
    # The receipt file written by `command_machine` carries "verdict"; the
    # pre-PR producer's review packet renames it to "outcome"
    # (itd_free_reviewer_producer._machine_summary). This reads the file.
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    path = Path(proc.stdout.strip().splitlines()[-1])
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("verdict") == "PASSED"
    except (OSError, ValueError):
        return False


def refusal(proc) -> str:
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return ""
    if payload.get("status") != "UNVERIFIED":
        return ""
    return str(payload.get("why", "")) + " | " + str(payload.get("fix", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--loop", type=Path, default=DEFAULT_SCRIPT,
                        help="Verification Loop script under test")
    script = parser.parse_args().loop.resolve()
    scratch = Path(tempfile.mkdtemp(prefix="oracle-legs-marker-")).resolve()

    # 1. One oracle id missing: refusal before any leg, no receipt.
    root = fixture(contract([criterion("U-legs-1", ["unit", "meta-review"])]))
    marker = scratch / "ran-1"
    proc = mint(script, root, UNIT, [marker_leg("unit", marker)])
    why = refusal(proc)
    check("missing oracle refuses with a nonzero exit", proc.returncode != 0,
          f"rc={proc.returncode} out={proc.stdout[-300:]}")
    check("the refusal names the criterion", "U-legs-1" in why, why or proc.stdout[-300:])
    check("the refusal names the missing oracle", "meta-review" in why, why)
    check("no leg ran before the refusal", not marker.exists(), "marker written")
    check("no receipt was written", not receipts(root), str(receipts(root)))

    # 2. Every missing pair is named.
    root = fixture(contract([criterion("U-legs-1", ["unit", "lint"]),
                             criterion("U-legs-2", ["types"])]))
    why = refusal(mint(script, root, UNIT, [ok_leg("unit")]))
    check("all missing pairs are named",
          all(token in why for token in ("U-legs-1", "lint", "U-legs-2", "types")),
          why)

    # 3. A complete leg set mints as before.
    root = fixture(contract([criterion("U-legs-1", ["unit", "meta-review"])]))
    proc = mint(script, root, UNIT, [ok_leg("unit"), ok_leg("meta-review")])
    check("a complete leg set mints a PASSED receipt", minted(proc),
          f"rc={proc.returncode} {proc.stdout[-300:]} {proc.stderr[-300:]}")
    proc = mint(script, root, UNIT,
                [ok_leg("unit"), ok_leg("meta-review"), ok_leg("extra")])
    check("extra legs beyond the oracleIds still mint", minted(proc),
          f"rc={proc.returncode} {proc.stdout[-300:]}")

    # 4. The :general-review claim is not checked.
    root = fixture(contract([criterion("U-legs-1", ["unit", "meta-review"])]))
    proc = mint(script, root, UNIT + ":general-review", [ok_leg("oracle")])
    check("a :general-review claim mints with any leg set", minted(proc),
          f"rc={proc.returncode} {proc.stdout[-300:]}")

    # 5. Not the active unit / closed follow-up / no reviewEvidence.
    root = fixture(contract([criterion("U-legs-1", ["unit"])]))
    proc = mint(script, root, "U-other", [ok_leg("oracle")])
    check("a claim that is not the active unit mints as before", minted(proc),
          f"rc={proc.returncode} {proc.stdout[-300:]}")
    root = fixture(contract([criterion("U-legs-1", ["unit"])], status="closed"))
    proc = mint(script, root, UNIT, [ok_leg("oracle")])
    check("a closed follow-up mints as before", minted(proc),
          f"rc={proc.returncode} {proc.stdout[-300:]}")
    root = fixture(contract([criterion("U-legs-1", None)]))
    proc = mint(script, root, UNIT, [ok_leg("oracle")])
    check("criteria without reviewEvidence mint as before", minted(proc),
          f"rc={proc.returncode} {proc.stdout[-300:]}")

    # 6. The candidate contract decides: an oracle id added in the index only.
    root = fixture(contract([criterion("U-legs-1", ["unit"])]))
    write_contract(root, contract([criterion("U-legs-1", ["unit", "staged-only"])]))
    git(root, "add", ".itd/ACCEPTANCE_CONTRACT.json")
    why = refusal(mint(script, root, UNIT, [ok_leg("unit")]))
    check("the staged contract of the candidate is enforced",
          "staged-only" in why and "U-legs-1" in why, why)

    # 7. Malformed explicit ownership refuses before any leg.
    bad = contract([criterion("U-legs-1", ["unit"])])
    bad["criteria"].append({"id": "", "unitId": UNIT})
    root = fixture(bad)
    marker = scratch / "ran-7"
    proc = mint(script, root, UNIT, [marker_leg("unit", marker)])
    check("malformed ownership of the active unit refuses",
          bool(refusal(proc)) and not marker.exists(),
          f"rc={proc.returncode} {proc.stdout[-300:]}")

    # 8. No reviewPolicy: still checked.
    root = fixture(contract([criterion("U-legs-1", ["unit", "lint"])], policy=False))
    why = refusal(mint(script, root, UNIT, [ok_leg("unit")]))
    check("a follow-up without reviewPolicy is checked too",
          "U-legs-1" in why and "lint" in why, why)

    # 9. committed-head: the committed contract decides.
    root = fixture(contract([criterion("U-legs-1", ["unit", "meta-review"])]))
    git(root, "commit", "-qm", "candidate")
    marker = scratch / "ran-9"
    proc = mint(script, root, UNIT, [marker_leg("unit", marker)], "committed-head")
    why = refusal(proc)
    check("committed-head refuses a missing oracle before any leg",
          "meta-review" in why and not marker.exists() and not receipts(root),
          f"rc={proc.returncode} {proc.stdout[-300:]}")
    proc = mint(script, root, UNIT, [ok_leg("unit"), ok_leg("meta-review")],
                "committed-head")
    check("committed-head mints with a complete leg set", minted(proc),
          f"rc={proc.returncode} {proc.stdout[-300:]} {proc.stderr[-300:]}")

    # 10. Malformed declared oracle evidence refuses before any leg.
    bad_values = {
        "evidence not an object": "unit",
        "oracleIds not a list": {"claim": "c", "impactClasses": ["correctness"],
                                 "oracleIds": "unit"},
        "empty oracleIds": {"claim": "c", "impactClasses": ["correctness"],
                            "oracleIds": []},
        "non-string oracle id": {"claim": "c", "impactClasses": ["correctness"],
                                 "oracleIds": ["unit", 7]},
        "padded oracle id": {"claim": "c", "impactClasses": ["correctness"],
                             "oracleIds": [" unit"]},
        "duplicated oracle id": {"claim": "c", "impactClasses": ["correctness"],
                                 "oracleIds": ["unit", "unit"]},
    }
    for index, (label, value) in enumerate(bad_values.items()):
        row = criterion("U-legs-1", None)
        row["reviewEvidence"] = value
        root = fixture(contract([row]))
        marker = scratch / f"ran-10-{index}"
        proc = mint(script, root, UNIT, [marker_leg("unit", marker)])
        why = refusal(proc)
        check(f"malformed evidence refuses before any leg: {label}",
              "U-legs-1" in why and not marker.exists() and not receipts(root),
              f"rc={proc.returncode} {proc.stdout[-300:]}")

    # 11. A git probe timeout is a LoopError.
    detail = ""
    try:
        spec = importlib.util.spec_from_file_location("oracle_legs_loop", script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = fixture(contract([criterion("U-legs-1", ["unit"])]))

        def timed_out(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0] if args else "git", 1)

        real_run = module.subprocess.run
        module.subprocess.run = timed_out
        try:
            module.assert_oracle_legs_declared(root, "a" * 40, UNIT, ["unit"])
            detail = "no refusal"
        except module.LoopError as exc:
            detail = "LoopError: " + exc.why
        finally:
            module.subprocess.run = real_run
    except Exception as exc:  # pre-fix code has no such function
        detail = f"{type(exc).__name__}: {exc}"
    check("a git probe timeout refuses with LoopError",
          detail.startswith("LoopError:") and "timed out" in detail, detail)

    # 12. A stale bytecode entry of itd_review_evidence is not used.
    detail = ""
    try:
        shared = Path(tempfile.mkdtemp(prefix="oracle-legs-pyc-")).resolve()
        loop_copy = shared / "itd_verification_loop.py"
        evidence_copy = shared / "itd_review_evidence.py"
        shutil.copyfile(script, loop_copy)
        shutil.copyfile(script.with_name("itd_review_evidence.py"), evidence_copy)
        old = b'"verified", "closed", "done", "superseded"'
        new = b'"verified", "closed", "DONE", "superseded"'
        source = evidence_copy.read_bytes()
        assert source.count(old) == 1, "fixture anchor moved"
        py_compile.compile(str(evidence_copy), doraise=True)
        stamp = evidence_copy.stat()
        evidence_copy.write_bytes(source.replace(old, new))
        os.utime(evidence_copy, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        spec = importlib.util.spec_from_file_location("oracle_legs_loop_pyc", loop_copy)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        statuses = module._review_evidence_module().CLOSED_FOLLOWUP_STATUSES
        detail = "current source" if "DONE" in statuses else f"stale bytecode: {sorted(statuses)}"
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
    check("the producer rules come from the current source, not stale bytecode",
          detail == "current source", detail)

    total = PASSED + FAILED
    if FAILED:
        print(f"FAILED: {FAILED} failed ({PASSED} passed of {total})")
        return 1
    print(f"PASSED: 0 failed ({PASSED} passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
