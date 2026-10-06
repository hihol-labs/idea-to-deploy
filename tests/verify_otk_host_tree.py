#!/usr/bin/env python3
"""verify_otk_host_tree.py - OTK-HOST-TREE-1: the harness verdict does not depend on git-ignored files.

Route trap (c) of TIER-WORDING-2 (BACKLOG P2 2026-10-01): the goal harness ran the unit
verificationCommand in the host working tree, so a local git-ignored file changed the verdict (the
first attempt of the TIER-WORDING-2 ledger-close failed on a git-ignored `.itd/COMPLETION_POLICY.json`
while the isolated copy of the machine receipt was green). Owner choice 2026-10-04 (variant A): the
harness runs the command in a disposable copy of the working tree WITHOUT git-ignored files; an
ignored input a command needs is declared with `--input` (the declared-input semantics of the
Verification Loop); a directory outside git runs on the host and says so.

Contract of this oracle (temporary repositories only, never the live one; a low unit, so no receipt):

  1. A git-ignored file that would fail the leg does not fail it, and one that would pass the leg
     does not pass it - both directions for a single command and for an `&&` chain; the clean
     checkout gives the same verdict. Out of scope (owner, stop rule after Sol s3b): clean/smudge
     filters and other programs the owner configured in git run while the copy is built - they are
     trusted host programs, the same class as the verificationCommand itself.
  2. The copy is the working tree: unstaged changes, untracked non-ignored files and a staged
     force-added ignored file are seen; a git-ignored file (also under an ignored `.itd-memory/`
     next to the force-added ledger) and an unstaged deletion are not.
  3. The command runs at the caller's relative cwd inside the copy and cannot change the host tree;
     inherited repository-local git variables (every name `git rev-parse --local-env-vars` lists,
     GIT_INTERNAL_SUPER_PREFIX, and a name only the installed git reports) reach neither the
     harness's git nor the command.
  4. `--input` copies a declared ignored file or directory (verify and --recheck; a recheck without
     the input regresses the unit); a tracked path, `.git`, an escaping
     path, a link and a missing path are refused by name before the run - the unit stays
     in_progress and no event is written.
  5. A directory outside git runs on the host with the line `host tree: not a git repository`;
     a git failure inside a repository (a broken index, a broken config), a missing git binary inside
     a checkout and a caller's directory that is not part of the copy (git-ignored) refuse the run
     instead of falling back.
  6. The harness names the copy (`isolated candidate: tree <sha>`), and the `evidence` format of
     the ledger is unchanged (`exit 0: ...`; one line per command of a chain).

RED on the pre-fix tree (86ca61f): the harness reads the host tree and has no `--input`.
Run: sh skills/_shared/itd_py.sh tests/verify_otk_host_tree.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERIFY = ROOT / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
PY = sys.executable
UNIT = "U-1"
GOAL = ".itd-memory/GOAL.json"
EVENTS = ".itd-memory/events.jsonl"
IGNORE = ".itd/\n.itd-memory/\nignored-dir/\n*.tmp\n"

fails: list[str] = []
passes: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passes.append(name)
        print(f"PASS  {name}")
    else:
        fails.append(name)
        print(f"FAIL  {name}" + (f"  - {detail}" if detail else ""))


def clean_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in ("CLAUDE_PROJECT_DIR",)}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Oracle", "GIT_AUTHOR_EMAIL": "oracle@example.com",
                "GIT_COMMITTER_NAME": "Oracle", "GIT_COMMITTER_EMAIL": "oracle@example.com",
                "PYTHONUTF8": "1"})
    return env


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          env=clean_env(), timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args}: {proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout.decode("utf-8", "replace").strip()


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def ledger(command: str) -> str:
    return json.dumps({
        "version": 1, "goal": "Oracle goal for the host-tree trap", "status": "active",
        "createdAt": "2026-10-04T00:00:00Z", "updatedAt": "2026-10-04T00:00:00Z",
        "currentUnitId": "",
        "units": [{"id": UNIT, "criterion": "the leg passes", "verificationCommand": command,
                   "riskTier": "low", "status": "pending"}],
    }, indent=2) + "\n"


def make_repo(tmp: Path, name: str, command: str, tracked: dict | None = None,
              use_git: bool = True) -> Path:
    """A committed fixture: `.itd-memory/` is ignored and the ledger is force-added, as here."""
    repo = tmp / name
    repo.mkdir()
    write(repo, GOAL, ledger(command))
    for rel, text in (tracked or {}).items():
        write(repo, rel, text)
    if use_git:
        write(repo, ".gitignore", IGNORE)
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "add", "-f", GOAL)
        git(repo, "commit", "-qm", "fixture")
    return repo


def otk(repo: Path, *args: str, cwd: Path | None = None,
        env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(VERIFY), "--goal", str(repo / GOAL), *args],
                          cwd=str(cwd or repo), capture_output=True, encoding="utf-8",
                          errors="replace", env={**clean_env(), **(env or {})}, timeout=300)


def unit(repo: Path) -> dict:
    data = json.loads((repo / GOAL).read_text(encoding="utf-8"))
    return next(u for u in data["units"] if u["id"] == UNIT)


def events(repo: Path) -> list[str]:
    path = repo / EVENTS
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def activate(repo: Path) -> None:
    result = otk(repo, "--activate", UNIT)
    if result.returncode != 0:
        raise RuntimeError(f"activation failed: {result.stdout}{result.stderr}")


def verify(repo: Path, *args: str, cwd: Path | None = None,
           env: dict | None = None) -> subprocess.CompletedProcess:
    activate(repo)
    return otk(repo, UNIT, *args, cwd=cwd, env=env)


def tail(result: subprocess.CompletedProcess) -> str:
    text = (result.stdout + result.stderr).strip().splitlines()
    return " | ".join(text[-3:])[:300]


def verified(result: subprocess.CompletedProcess) -> bool:
    return result.returncode == 0 and f"VERIFIED {UNIT}" in result.stdout


def failed(result: subprocess.CompletedProcess) -> bool:
    return result.returncode == 1 and f"FAILED {UNIT} stays in_progress" in result.stdout


def ignored_clean(repo: Path, rel: str) -> bool:
    """The extra file is git-ignored and the checkout is otherwise clean."""
    probe = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", rel], env=clean_env())
    return probe.returncode == 0 and git(repo, "status", "--porcelain") == ""


def case_ignored_cannot_flip(tmp: Path) -> None:
    single_fail = "test ! -e .itd/LOCAL_POLICY.json"
    clean = make_repo(tmp, "clean", single_fail)
    result = verify(clean)
    check("clean-checkout-verifies", verified(result), tail(result))
    isolation = re.search(r"isolated candidate: tree ([0-9a-f]{40})", result.stdout)
    check("harness-names-the-isolated-tree", bool(isolation), tail(result))
    stored = unit(clean).get("evidence", "")
    check("evidence-format-single-unchanged",
          stored == "exit 0: (no output)", repr(stored))

    dirty = make_repo(tmp, "ignored-fail", single_fail)
    write(dirty, ".itd/LOCAL_POLICY.json", "{}\n")
    check("fixture-ignored-file-is-ignored", ignored_clean(dirty, ".itd/LOCAL_POLICY.json"))
    result = verify(dirty)
    check("ignored-file-cannot-fail-a-single-leg", verified(result), tail(result))

    passing = make_repo(tmp, "ignored-pass", "test -e .itd/LOCAL_POLICY.json")
    write(passing, ".itd/LOCAL_POLICY.json", "{}\n")
    result = verify(passing)
    check("ignored-file-cannot-pass-a-single-leg", failed(result), tail(result))

    chain = make_repo(tmp, "ignored-chain", "test -f kept.txt && test ! -e .itd/LOCAL_POLICY.json",
                      {"kept.txt": "kept\n"})
    write(chain, ".itd/LOCAL_POLICY.json", "{}\n")
    result = verify(chain)
    check("ignored-file-cannot-fail-a-chain", verified(result), tail(result))
    stored = unit(chain).get("evidence", "")
    lines = stored.splitlines()
    chain_pass = make_repo(tmp, "ignored-chain-pass",
                           "test -f kept.txt && test -e .itd/LOCAL_POLICY.json", {"kept.txt": "kept\n"})
    write(chain_pass, ".itd/LOCAL_POLICY.json", "{}\n")
    result_pass = verify(chain_pass)
    check("ignored-file-cannot-pass-a-chain", failed(result_pass), tail(result_pass))
    check("evidence-format-chain-unchanged",
          len(lines) == 2 and lines[0].startswith("test -f kept.txt: exit 0, stdout sha256 ")
          and lines[1].startswith("test ! -e .itd/LOCAL_POLICY.json: exit 0, stdout sha256 "),
          repr(stored))


def case_working_tree_semantics(tmp: Path) -> None:
    command = ("grep -q new changed.txt && test -f untracked.txt && test -f ignored-dir/forced.txt "
               "&& test ! -e gone.txt && test -f .itd-memory/GOAL.json "
               "&& test ! -e .itd-memory/notes.txt && test ! -e ignored-dir/local.txt")
    repo = make_repo(tmp, "working-tree", command,
                     {"changed.txt": "old\n", "gone.txt": "gone\n"})
    write(repo, "changed.txt", "new\n")                       # unstaged change
    write(repo, "untracked.txt", "untracked\n")               # untracked, not ignored
    write(repo, "ignored-dir/forced.txt", "forced\n")         # staged force-added, ignored path
    git(repo, "add", "-f", "ignored-dir/forced.txt")
    (repo / "gone.txt").unlink()                              # unstaged deletion
    write(repo, ".itd-memory/notes.txt", "local\n")           # ignored, next to the tracked ledger
    write(repo, "ignored-dir/local.txt", "local\n")           # ignored
    result = verify(repo)
    check("copy-is-the-working-tree-without-ignored-files", verified(result), tail(result))


def case_cwd_and_host(tmp: Path) -> None:
    repo = make_repo(tmp, "subdir", "test -f here.txt && test ! -e local.tmp",
                     {"sub/here.txt": "here\n"})
    write(repo, "sub/local.tmp", "local\n")
    result = verify(repo, cwd=repo / "sub")
    check("relative-cwd-kept-inside-the-copy", verified(result), tail(result))

    listed = subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True,
                            encoding="utf-8", env=clean_env()).stdout.split()
    names = sorted(set(listed) | {"GIT_INTERNAL_SUPER_PREFIX"})
    probe = "! env | grep -E '^(" + "|".join(names) + ")='"
    repo = make_repo(tmp, "git-env", f"test ! -e .itd/LOCAL_POLICY.json && {probe}")
    write(repo, ".itd/LOCAL_POLICY.json", "{}\n")
    inherited = {name: "/nonexistent-oracle-value" for name in names}
    inherited.update({"GIT_DIR": str(repo / ".git"), "GIT_WORK_TREE": str(repo),
                      "GIT_INDEX_FILE": str(repo / ".git" / "index"), "GIT_CONFIG_COUNT": "1",
                      "GIT_INTERNAL_SUPER_PREFIX": "sub/"})
    result = verify(repo, env=inherited)
    check("inherited-git-variables-do-not-reach-the-host",
          len(listed) >= 10 and verified(result), f"{len(listed)} listed; {tail(result)}")

    real_git = shutil.which("git")
    if os.name == "nt" or real_git is None:
        print("SKIP  git-variables-named-by-the-installed-git-are-scrubbed - POSIX wrapper only")
    else:
        wrapper = tmp / "wrapper-bin"
        wrapper.mkdir()
        (wrapper / "git").write_text(
            "#!/bin/sh\n"
            f'if [ "$1 $2" = "rev-parse --local-env-vars" ]; then "{real_git}" "$@"; '
            "echo GIT_ORACLE_FUTURE_VAR; exit 0; fi\n"
            f'exec "{real_git}" "$@"\n', encoding="utf-8")
        (wrapper / "git").chmod(0o755)
        repo = make_repo(tmp, "git-env-future", 'test -z "$GIT_ORACLE_FUTURE_VAR"')
        result = verify(repo, env={"GIT_ORACLE_FUTURE_VAR": "leaked",
                                   "PATH": f"{wrapper}{os.pathsep}{os.environ.get('PATH', '')}"})
        check("git-variables-named-by-the-installed-git-are-scrubbed", verified(result), tail(result))

    repo = make_repo(tmp, "host", "echo changed > kept.txt; echo made > made.txt",
                     {"kept.txt": "kept\n"})
    result = verify(repo)
    check("command-cannot-change-the-host-tree",
          verified(result) and (repo / "kept.txt").read_text(encoding="utf-8") == "kept\n"
          and not (repo / "made.txt").exists(), tail(result))


def case_inputs(tmp: Path) -> None:
    repo = make_repo(tmp, "input-file", "test -f .itd/LOCAL_POLICY.json && test -f ignored-dir/data.txt")
    write(repo, ".itd/LOCAL_POLICY.json", "{}\n")
    write(repo, "ignored-dir/data.txt", "data\n")
    result = verify(repo, "--input", ".itd/LOCAL_POLICY.json", "--input", "ignored-dir")
    check("declared-inputs-are-copied", verified(result), tail(result))
    check("declared-inputs-are-named",
          ".itd/LOCAL_POLICY.json" in result.stdout and "ignored-dir" in result.stdout, tail(result))
    recheck = otk(repo, "--recheck", UNIT, "--input", ".itd/LOCAL_POLICY.json", "--input", "ignored-dir")
    plain = otk(repo, "--recheck", UNIT)
    check("recheck-runs-in-the-copy-with-inputs",
          recheck.returncode == 0 and "isolated candidate: tree" in recheck.stdout
          and plain.returncode == 1 and f"REGRESSED {UNIT}" in plain.stdout, tail(plain))

    refusals = [
        ("tracked", "kept.txt", "already tracked"),
        ("git-database", ".git", "Git database"),
        ("escaping", "../outside.txt", "not canonical"),
        ("missing", "nope.txt", "nope.txt"),
    ]
    repo = make_repo(tmp, "input-refusals", "true", {"kept.txt": "kept\n"})
    write(tmp, "outside.txt", "outside\n")
    activate(repo)
    try:
        (repo / "link.txt").symlink_to(repo / "kept.txt")
        write(repo, ".gitignore", IGNORE + "link.txt\n")
        git(repo, "commit", "-qam", "ignore the link")
        refusals.append(("link", "link.txt", "link"))
    except OSError:
        print("SKIP  input-refused-link - symlinks are not available here")
    for label, rel, words in refusals:
        before = events(repo)
        result = otk(repo, UNIT, "--input", rel)
        check(f"input-refused-{label}",
              result.returncode != 0 and "VERIFIED" not in result.stdout
              and "nothing ran" in result.stdout and words in result.stdout
              and unit(repo)["status"] == "in_progress" and events(repo) == before,
              tail(result))


def case_outside_git(tmp: Path) -> None:
    plain = make_repo(tmp, "plain", "test -f kept.txt", {"kept.txt": "kept\n"}, use_git=False)
    result = verify(plain)
    check("directory-outside-git-runs-on-the-host",
          verified(result) and "host tree: not a git repository" in result.stdout, tail(result))

    broken = make_repo(tmp, "broken-index", "true")
    activate(broken)
    (broken / ".git" / "index").write_bytes(b"not an index")
    result = otk(broken, UNIT)
    check("git-failure-refuses-the-run",
          result.returncode != 0 and "VERIFIED" not in result.stdout
          and unit(broken)["status"] == "in_progress", tail(result))

    sh_path = shutil.which("sh")
    if os.name == "nt" or sh_path is None:
        print("SKIP  missing-git-* - POSIX PATH fixture only")
    else:
        no_git = tmp / "no-git-bin"
        no_git.mkdir()
        (no_git / "sh").symlink_to(sh_path)
        bare_path = {"PATH": str(no_git)}
        inside = make_repo(tmp, "missing-git-inside", "true")
        activate(inside)
        result = otk(inside, UNIT, env=bare_path)
        check("missing-git-inside-a-checkout-refuses-the-run",
              result.returncode != 0 and "nothing ran" in result.stdout and ".git" in result.stdout
              and "VERIFIED" not in result.stdout and unit(inside)["status"] == "in_progress", tail(result))
        outside = make_repo(tmp, "missing-git-outside", "true", use_git=False)
        activate(outside)
        result = otk(outside, UNIT, env=bare_path)
        check("missing-git-outside-a-checkout-runs-on-the-host",
              verified(result) and "host tree: not a git repository" in result.stdout, tail(result))

    config = make_repo(tmp, "broken-config", "true")
    activate(config)
    (config / ".git" / "config").write_bytes(b"[core\nnot a config\n")
    result = otk(config, UNIT)
    check("git-repository-error-is-not-no-git",
          result.returncode != 0 and "nothing ran" in result.stdout and "VERIFIED" not in result.stdout
          and "host tree" not in result.stdout and unit(config)["status"] == "in_progress", tail(result))

    ignored_cwd = make_repo(tmp, "ignored-cwd", "true")
    (ignored_cwd / "ignored-dir").mkdir()
    activate(ignored_cwd)
    result = otk(ignored_cwd, UNIT, cwd=ignored_cwd / "ignored-dir")
    check("ignored-cwd-refuses-the-run",
          result.returncode != 0 and "nothing ran" in result.stdout
          and "Traceback" not in result.stdout + result.stderr
          and unit(ignored_cwd)["status"] == "in_progress", tail(result))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-otk-host-tree-") as raw:
        tmp = Path(raw)
        case_ignored_cannot_flip(tmp)
        case_working_tree_semantics(tmp)
        case_cwd_and_host(tmp)
        case_inputs(tmp)
        case_outside_git(tmp)
    if fails:
        print(f"FAILED: {len(fails)} failed ({len(passes)} passed)")
        return 1
    print(f"PASSED: 0 failed ({len(passes)} passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
