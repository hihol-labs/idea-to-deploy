#!/usr/bin/env python3
"""verify_otk_failed_attempt.py - OTK-FAILED-ATTEMPT-1: a failed harness attempt does not block the next one.

Route trap (b) of TIER-WORDING-2 (BACKLOG P2 2026-10-01): a failed committed-head attempt of the goal
harness appended `verification_failed` to the TRACKED `.itd-memory/events.jsonl`. The checkout then
differed from the committed candidate, so the next attempt with the same receipt was refused
("working tree differs from the staged candidate", `itd_verification_loop.py`), and
`scripts/itd_closure_delta.py` rejected the line in the ledger-close delta. Owner choice 2026-10-04
(variant A): the failed attempt goes to an untracked attempts journal, `.itd-memory/attempts/attempts.jsonl`,
whose directory ignores itself (`.gitignore` = `*`), so it stays out of the candidate even where
`.itd-memory/` is tracked; the retro scan reads both journals.

Contract of this oracle (all in a temporary git repository, never the live one; the fixture tracks
`.itd-memory/` WITHOUT any ignore rule - the hard case for a target project; `.claude/` is ignored
as in this repository, because the completion signal `.claude/completion/signals.jsonl` is written on
every outcome and is not the failed-attempt record - BACKLOG P2 2026-10-04):

  1. A committed candidate with an activated low unit; the verification command fails until a flag
     file outside the repository exists. The harness attempt fails: exit 1, the line
     `FAILED U-1 stays in_progress`.
  2. After the failed attempt the checkout still equals the committed candidate: no tracked change
     (GOAL, STATE, events), no untracked non-ignored file, and the candidate check of the
     Verification Loop (`assert_checkout_matches_candidate`) accepts the checkout - the next attempt
     with the same receipt is not refused because of the failed-attempt record.
  3. The record is not lost: the attempts journal holds exactly one harness event
     (`verification_failed`, actor harness, unit, ledger, evidence), and the retro scan
     (`scan_project`) counts it in `failedVerifications`.
  4. The next attempt verifies the unit, and `scripts/itd_closure_delta.py` accepts the ledger-close
     delta (GOAL/STATE/events as written by the harness) against the reviewed tree: exit 0, silent.
  5. An ignore rule does not untrack a path (Sol s1): where the attempts journal is already tracked,
     the failed attempt still exits 1 with its FAILED line and no traceback, names the refusal
     ("not journalled ... tracked by git") and leaves the checkout unchanged.
  6. Only a positively established non-repository skips that guard (Sol s2): a git failure inside
     the ledger's repository (a broken index) refuses the journal ("cannot tell whether ...", no
     attempts directory created), while a directory without git journals the failed attempt. Since
     OTK-HOST-TREE-1 the command runs in a copy built by git, so a broken index in the repository
     the command runs from refuses the run itself ("nothing ran"); the journal guard is reached
     with the ledger in a broken repository and the command in a healthy one.

RED on the pre-fix tree (e725c07): the failed attempt changes the tracked events.jsonl - legs of
points 2, 3 (journal) and 4 (closure-delta) fail.
Run: sh skills/_shared/itd_py.sh tests/verify_otk_failed_attempt.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
UNIT = "U-1"
ATTEMPTS = ".itd-memory/attempts/attempts.jsonl"

fails: list[str] = []
passes: list[str] = []


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The closure-delta oracle owns the fixture ledger and the git helpers; reuse them, do not fork them.
cd = load("verify_closure_delta_fixture", ROOT / "tests" / "verify_closure_delta.py")


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passes.append(name)
        print(f"PASS  {name}")
    else:
        fails.append(name)
        print(f"FAIL  {name}" + (f"  - {detail}" if detail else ""))


def git_ok(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          env=cd.clean_env(), timeout=60)


def make_repo(tmp: Path, name: str, flag: Path, extra: dict | None = None, init: bool = True) -> Path:
    """A fixture repository with the harness of this checkout; `extra` files are committed with it."""
    repo = tmp / name
    repo.mkdir()
    if init:
        cd.git(repo, "init", "-q")
    base = cd.base_files()
    command = (f'"{PY}" -c "import os,sys; '
               f"sys.exit(0 if os.path.exists('{flag.as_posix()}') else 1)\"")
    base[cd.GOAL] = cd.unit_edit(base[cd.GOAL], verificationCommand=command)
    base[".gitignore"] = b".claude/\n"
    base.update(extra or {})
    for rel, data in base.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes(data)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for part in ("skills/_shared", "skills/goal/scripts", "skills/task/scripts", "skills/retro/scripts"):
        shutil.copytree(ROOT / part, repo / part, ignore=ignore)
    shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=ignore)
    (repo / "hooks").mkdir()
    shutil.copy(ROOT / "hooks" / "validate_state_core.py", repo / "hooks" / "validate_state_core.py")
    return repo


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-otk-failed-attempt-") as tmp_name:
        tmp = Path(tmp_name)
        flag = tmp / "verification-passes.flag"
        repo = make_repo(tmp, "repo", flag)

        print("[1] a committed candidate, a failed harness attempt")
        act = cd.run_harness(repo, "--activate", UNIT)
        check("harness-activate", act.returncode == 0, (act.stdout + act.stderr)[-300:])
        cd.git(repo, "add", "-A")
        cd.git(repo, "commit", "-qm", "candidate")
        reviewed = cd.git(repo, "rev-parse", "HEAD^{tree}")
        failed = cd.run_harness(repo, UNIT)
        check("failed-attempt-exit-and-line",
              failed.returncode == 1 and f"FAILED {UNIT} stays in_progress" in failed.stdout
              and "Traceback" not in failed.stderr,
              f"rc={failed.returncode} {(failed.stdout + failed.stderr)[-300:]!r}")

        print("[2] the checkout still equals the committed candidate")
        dirty = git_ok(repo, "diff", "--name-only", "HEAD", "--")
        check("failed-attempt-leaves-tracked-ledger",
              dirty.returncode == 0 and not dirty.stdout.strip(),
              dirty.stdout.decode("utf-8", "replace").strip())
        others = git_ok(repo, "ls-files", "--others", "--exclude-standard")
        check("failed-attempt-leaves-no-untracked-input",
              others.returncode == 0 and not others.stdout.strip(),
              others.stdout.decode("utf-8", "replace").strip())
        loop = load("itd_verification_loop_oracle", ROOT / "skills" / "_shared" / "itd_verification_loop.py")
        try:
            executed = loop.assert_checkout_matches_candidate(repo, {"reviewedTree": reviewed})
            refused = "" if executed == reviewed else f"executed tree {executed} != {reviewed}"
        except Exception as exc:  # LoopError: the refusal the next attempt would get
            refused = str(exc)
        check("retry-candidate-check-accepts-checkout", not refused, refused)

        print("[3] the failed attempt is journalled and counted")
        journal = repo / ATTEMPTS
        rows = ([json.loads(r) for r in journal.read_text(encoding="utf-8").splitlines() if r.strip()]
                if journal.is_file() else [])
        event = rows[0] if len(rows) == 1 else {}
        check("failed-attempt-journalled",
              len(rows) == 1 and event.get("decision") == "verification_failed"
              and event.get("actor") == "harness" and event.get("type") == "unit"
              and event.get("name") == UNIT and event.get("ledger") == "GOAL.json"
              and str(event.get("evidence") or "").startswith("exit 1"),
              repr(rows)[:300])
        tracked_events = (repo / cd.EVENTS).read_text(encoding="utf-8")
        check("failed-attempt-not-in-tracked-journal", "verification_failed" not in tracked_events)
        retro = load("itd_retro_scan_oracle", ROOT / "skills" / "retro" / "scripts" / "itd_retro_scan.py")
        scanned = retro.scan_project(repo / ".itd-memory")
        check("retro-counts-failed-attempt", scanned.get("failedVerifications") == 1,
              f"failedVerifications={scanned.get('failedVerifications')!r}")

        print("[4] the next attempt verifies, closure-delta accepts the ledger-close")
        flag.write_text("ok\n", encoding="utf-8")
        ver = cd.run_harness(repo, UNIT)
        check("retry-verifies", ver.returncode == 0 and f"VERIFIED {UNIT}" in ver.stdout,
              (ver.stdout + ver.stderr)[-300:])
        closure = cd.tree_with(repo, reviewed, {rel: (repo / rel).read_bytes()
                                                for rel in (cd.GOAL, cd.STATE, cd.EVENTS)})
        receipt = repo / ".claude" / "receipts" / "adjudication.json"  # inside the root, ignored
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({
            "version": 1, "kind": "adjudication", "unitId": UNIT, "outcome": "PASSED",
            "receiptSha256": cd.RECEIPT_SHA,
            "candidate": {"reviewedTree": reviewed, "riskTier": "low"},
            "dependencies": {"machine": {"path": "receipts/machine.json", "sha256": "e" * 64}}}),
            encoding="utf-8")
        rc, out, err = cd.run_tool(repo, "--receipt", str(receipt), "--tree", closure)
        check("closure-delta-accepts-ledger-close", rc == 0 and not out and not err,
              f"rc={rc} out={out!r} err={err[-400:]!r}")

        print("[5] a tracked attempts path is refused, not appended to (Sol s1)")
        repo2 = make_repo(tmp, "tracked", tmp / "never.flag", {ATTEMPTS: b""})
        act2 = cd.run_harness(repo2, "--activate", UNIT)
        cd.git(repo2, "add", "-A")
        cd.git(repo2, "commit", "-qm", "candidate with a tracked attempts journal")
        failed2 = cd.run_harness(repo2, UNIT)
        out2 = failed2.stdout + failed2.stderr
        check("tracked-journal-attempt-fails-cleanly",
              act2.returncode == 0 and failed2.returncode == 1
              and f"FAILED {UNIT} stays in_progress" in failed2.stdout and "Traceback" not in out2,
              f"rc={failed2.returncode} {out2[-300:]!r}")
        check("tracked-journal-refusal-named",
              "not journalled" in failed2.stdout and "tracked by git" in failed2.stdout, out2[-300:])
        dirty2 = git_ok(repo2, "status", "--porcelain", "--untracked-files=all")
        check("tracked-journal-left-unchanged",
              dirty2.returncode == 0 and not dirty2.stdout.strip(),
              dirty2.stdout.decode("utf-8", "replace").strip())

        print("[6] a git failure refuses the journal; only a non-repository skips the guard (Sol s2)")
        repo3 = make_repo(tmp, "broken-index", tmp / "never.flag")
        act3 = cd.run_harness(repo3, "--activate", UNIT)
        cd.git(repo3, "add", "-A")
        cd.git(repo3, "commit", "-qm", "candidate")
        (repo3 / ".git" / "index").write_bytes(b"not an index")  # git ls-files now exits 128
        refused3 = cd.run_harness(repo3, UNIT)
        check("git-failure-in-command-repo-refuses-the-run",
              refused3.returncode == 1 and "nothing ran" in refused3.stdout
              and "VERIFIED" not in refused3.stdout and "Traceback" not in refused3.stdout + refused3.stderr
              and not (repo3 / ".itd-memory" / "attempts").exists(),
              (refused3.stdout + refused3.stderr)[-300:])
        healthy = make_repo(tmp, "healthy-cwd", tmp / "never.flag")
        failed3 = subprocess.run([PY, str(repo3 / cd.HARNESS), "--goal", str(repo3 / cd.GOAL), UNIT],
                                 cwd=str(healthy), capture_output=True, encoding="utf-8",
                                 errors="replace", env=cd.clean_env(), timeout=120)
        out3 = failed3.stdout + failed3.stderr
        check("git-failure-attempt-fails-cleanly",
              act3.returncode == 0 and failed3.returncode == 1
              and f"FAILED {UNIT} stays in_progress" in failed3.stdout and "Traceback" not in out3,
              f"rc={failed3.returncode} {out3[-300:]!r}")
        check("git-failure-refuses-journal",
              "not journalled" in failed3.stdout and "cannot tell whether" in failed3.stdout
              and not (repo3 / ".itd-memory" / "attempts").exists(), out3[-300:])
        repo4 = make_repo(tmp, "no-git", tmp / "never.flag", init=False)
        act4 = cd.run_harness(repo4, "--activate", UNIT)
        failed4 = cd.run_harness(repo4, UNIT)
        journal4 = repo4 / ATTEMPTS
        check("non-repository-journals-attempt",
              act4.returncode == 0 and failed4.returncode == 1 and "not journalled" not in failed4.stdout
              and journal4.is_file() and "verification_failed" in journal4.read_text(encoding="utf-8"),
              (failed4.stdout + failed4.stderr)[-300:])

    print(f"\n{len(passes)} passed, {len(fails)} failed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
