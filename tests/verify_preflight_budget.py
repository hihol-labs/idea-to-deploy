#!/usr/bin/env python3
"""verify_preflight_budget.py — G-002 CONTEXT-BUDGET-1: the pre-flight hook prints the
full dump once per session and only a bounded delta afterwards.

Audit 2026-09-22 (advisor x3): `hooks/pre-flight-check.sh` re-injected 4-6 KB of git
context, ITD state, contract drift and the memory index on EVERY prompt of a session.
Contract of this unit (the goal ledger owns the criterion; this file pins it):

  1. First prompt of a session in a repository: the full dump, unchanged, and a
     per-session/per-repository state file is written (sentinel + last HEAD + last lock).
  2. Later prompts in the same session and repository emit ONLY the delta: commits that
     appeared since the previous prompt and the parallel-session warning when a fresh
     `.active-session.lock` appeared or advanced; the additionalContext is <= 1024 bytes
     (UTF-8); when there is no delta the hook prints nothing at all (exit 0, empty stdout).
  3. A different repository in the same session gets its own first dump; an unreadable
     state file degrades to the full dump (fail-open toward context, never toward silence).
  4. The host memory index `~/.claude/projects/-home-hihol-projects-idea-to-deploy/memory/
     MEMORY.md` is <= 24 400 bytes with no line longer than 200 characters - checked only
     when that file exists on this host (CI has no host memory) and reported as skipped
     otherwise.

`--mutations` copies `hooks/` into a temp dir, applies three independent mutations and
requires the suite to go RED on each (lethality proof).
Run: sh skills/_shared/itd_py.sh tests/verify_preflight_budget.py [--mutations]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_INDEX = Path.home() / ".claude" / "projects" / "-home-hihol-projects-idea-to-deploy" / "memory" / "MEMORY.md"
INDEX_MAX_BYTES = 24400
INDEX_MAX_LINE_CHARS = 200
DELTA_MAX_BYTES = 1024
FULL_MARKERS = ("[PRE-FLIGHT CHECK]", "**Git context**", "Recent commits:")

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=30).stdout.strip()


def make_repo(base: Path, name: str) -> Path:
    repo = base / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "oracle@example.invalid")
    git(repo, "config", "user.name", "oracle")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "init: fixture repository")
    return repo


def commit(repo: Path, subject: str) -> None:
    p = repo / "notes.txt"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(subject + "\n")
    git(repo, "add", "notes.txt")
    git(repo, "commit", "-q", "-m", subject)


def run_hook(hook: Path, cwd: Path, home: Path, sid: str) -> tuple[int, str, str]:
    """Run the real hook as the host does; return (rc, additionalContext or '', stderr)."""
    env = dict(os.environ)
    env.update({"HOME": str(home), "USERPROFILE": str(home), "CLAUDE_SESSION_ID": sid,
                "TMPDIR": str(home / "tmp"), "TMP": str(home / "tmp"), "TEMP": str(home / "tmp")})
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(hook)], input=json.dumps({"session_id": sid}),
                       capture_output=True, text=True, cwd=cwd, env=env, timeout=60)
    if not r.stdout.strip():
        return r.returncode, "", r.stderr
    try:
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        ctx = "<<unparseable: " + r.stdout[:200] + ">>"
    return r.returncode, ctx, r.stderr


def nbytes(text: str) -> int:
    return len(text.encode("utf-8"))


def write_lock(repo: Path, ts: float, note: str) -> None:
    mem = repo / ".itd-memory"
    mem.mkdir(exist_ok=True)
    (mem / ".active-session.lock").write_text(json.dumps(
        {"timestamp": ts, "pid": 4242, "branch": "other", "project": str(repo), "note": note}), encoding="utf-8")


def suite(root: Path, quiet: bool = False) -> list[str]:
    """Return the failed check names for the product tree at `root` (hooks/ used)."""
    local_fails: list[str] = []

    def c(name: str, cond: bool, detail: str = "") -> None:
        if not quiet:
            check(name, cond, detail)
        if not cond:
            local_fails.append(name)

    hook = root / "hooks" / "pre-flight-check.sh"
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        home = base / "home"
        home.mkdir()
        repo = make_repo(base, "repo")
        sid = "g002-" + uuid.uuid4().hex

        # 1. first prompt: full dump
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("first-prompt-exit-0", rc == 0, err[-200:])
        c("first-prompt-full-dump", all(m in ctx for m in FULL_MARKERS), ctx[:200])

        # 2. second prompt, nothing changed: empty stdout
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("second-prompt-exit-0", rc == 0, err[-200:])
        c("second-prompt-no-delta-is-empty", ctx == "", ctx[:200])

        # 3. a new commit: bounded delta naming the commit, no full-dump sections
        commit(repo, "feat: delta commit visible to the next prompt")
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("delta-commit-exit-0", rc == 0, err[-200:])
        c("delta-commit-named", "delta commit visible" in ctx, ctx[:300])
        c("delta-commit-under-1024-bytes", 0 < nbytes(ctx) <= DELTA_MAX_BYTES, f"{nbytes(ctx)} bytes")
        c("delta-commit-no-full-sections", not any(m in ctx for m in FULL_MARKERS)
          and "Project memory index" not in ctx and "ITD state" not in ctx, ctx[:300])

        # 4. the delta is consumed: next prompt is empty again
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("delta-consumed-next-prompt-empty", rc == 0 and ctx == "", ctx[:200])

        # 5. a fresh parallel-session lock appears: warning only, bounded
        write_lock(repo, time.time(), "other session note")
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("lock-appears-warning-emitted", "Parallel session warning" in ctx and "other session note" in ctx, ctx[:300])
        c("lock-warning-under-1024-bytes", 0 < nbytes(ctx) <= DELTA_MAX_BYTES, f"{nbytes(ctx)} bytes")
        c("lock-warning-no-full-sections", not any(m in ctx for m in FULL_MARKERS), ctx[:300])
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("same-lock-not-repeated", rc == 0 and ctx == "", ctx[:200])
        write_lock(repo, time.time() + 7, "advanced note")
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("advanced-lock-warns-again", "Parallel session warning" in ctx and "advanced note" in ctx, ctx[:300])

        # 6. many long commits: hard cap with a truncation marker, warning survives
        for i in range(40):
            commit(repo, f"chore: long subject number {i:02d} " + ("x" * 90))
        write_lock(repo, time.time() + 20, "lock during burst")
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("burst-capped-at-1024-bytes", 0 < nbytes(ctx) <= DELTA_MAX_BYTES, f"{nbytes(ctx)} bytes")
        c("burst-keeps-lock-warning-first", ctx.find("Parallel session warning") >= 0
          and ctx.find("Parallel session warning") < ctx.find("number"), ctx[:300])
        c("burst-has-truncation-marker", "…" in ctx or "..." in ctx, ctx[-120:])

        # 7. a second repository in the same session: its own first dump
        repo2 = make_repo(base, "repo2")
        rc, ctx, err = run_hook(hook, repo2, home, sid)
        c("second-repo-same-session-full-dump", rc == 0 and all(m in ctx for m in FULL_MARKERS), ctx[:200])
        rc, ctx, err = run_hook(hook, repo2, home, sid)
        c("second-repo-second-prompt-empty", rc == 0 and ctx == "", ctx[:200])
        # ...and the first repository is still in delta mode
        rc, ctx, err = run_hook(hook, repo, home, sid)
        c("first-repo-still-delta-mode", rc == 0 and ctx == "", ctx[:200])

        # 8. unreadable state file -> full dump, exit 0 (fail-open toward context)
        states = sorted((home / "tmp").glob(f"claude-preflight-{sid}-*.json"))
        c("state-files-exist-per-repo", len(states) == 2, str(states))
        if states:
            victim = states[0]
            victim.unlink()
            victim.mkdir()   # a directory where the JSON file should be
            rc, ctx, err = run_hook(hook, repo, home, sid)
            rc2, ctx2, err2 = run_hook(hook, repo2, home, sid)
            got_full = (all(m in ctx for m in FULL_MARKERS) or all(m in ctx2 for m in FULL_MARKERS))
            c("unreadable-state-degrades-to-full-dump", rc == 0 and rc2 == 0 and got_full,
              f"rc={rc}/{rc2} ctx={ctx[:120]!r} ctx2={ctx2[:120]!r}")

        # 9. a fresh session id in the same repository: full dump again
        rc, ctx, err = run_hook(hook, repo, home, "g002-" + uuid.uuid4().hex)
        c("fresh-session-full-dump-again", rc == 0 and all(m in ctx for m in FULL_MARKERS), ctx[:200])

        # 10. no git repository: never crashes
        plain = base / "plain"
        plain.mkdir()
        rc, ctx, err = run_hook(hook, plain, home, sid)
        c("no-git-directory-exit-0", rc == 0, err[-200:])

    # 11. host memory index budget (only where the host memory exists)
    if HOST_INDEX.is_file():
        raw = HOST_INDEX.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        longest = max((len(l) for l in text.splitlines()), default=0)
        c("host-memory-index-under-24400-bytes", len(raw) <= INDEX_MAX_BYTES, f"{len(raw)} bytes")
        c("host-memory-index-lines-under-200-chars", longest <= INDEX_MAX_LINE_CHARS, f"longest {longest}")
    elif not quiet:
        print("skip host-memory-index-budget (no host memory index on this machine)")

    c("oracle-registered-in-run-all", "verify_preflight_budget" in (root / "tests" / "run-all.sh").read_text(encoding="utf-8"))
    return local_fails


def copy_product(dst: Path) -> None:
    shutil.copytree(ROOT / "hooks", dst / "hooks")
    (dst / "tests").mkdir()
    shutil.copy2(ROOT / "tests" / "run-all.sh", dst / "tests" / "run-all.sh")


def mutate(dst: Path, old: str, new: str) -> None:
    p = dst / "hooks" / "pre-flight-check.sh"
    s = p.read_text(encoding="utf-8")
    assert old in s, f"mutation anchor missing: {old!r}"
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


def _hook_fails(root: Path) -> list[str]:
    """Hook-behaviour checks only: the host memory index budget does not depend on the
    hook bytes and must not mask (or fake) a mutation verdict."""
    return [f for f in suite(root, quiet=True) if not f.startswith("host-memory-index")]


def mutations() -> int:
    baseline = _hook_fails(ROOT)
    if baseline:
        print("skip mutations: baseline suite is red: " + ", ".join(baseline))
        return 1
    cases = [
        ("state-never-written", "def _save_preflight_state(path: Path, state: dict) -> None:\n",
         "def _save_preflight_state(path: Path, state: dict) -> None:\n    return\n"),
        ("delta-cap-removed", "PREFLIGHT_DELTA_MAX_BYTES = 1024", "PREFLIGHT_DELTA_MAX_BYTES = 10 ** 9"),
        ("commit-delta-ignored", "    new_commits = _new_commits(cwd, last_head, head)",
         "    new_commits = \"\""),
    ]
    rc = 0
    for name, old, new in cases:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "tree"
            copy_product(dst)
            mutate(dst, old, new)
            fails = _hook_fails(dst)
            check(f"mutation-{name}-lethal", bool(fails), "suite stayed green")
            if not fails:
                rc = 1
    return rc


def main() -> int:
    if "--mutations" in sys.argv[1:]:
        suite(ROOT)
        rc = mutations()
        print(("PASSED" if not FAILS and rc == 0 else "FAILED") + f": {len(FAILS)} failed")
        return 1 if FAILS or rc else 0
    suite(ROOT)
    print(("PASSED" if not FAILS else "FAILED") + f": {len(FAILS)} failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
