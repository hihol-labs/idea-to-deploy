#!/usr/bin/env python3
"""Audit invariant for v1.52.0 release B, part 1: the enforcement hooks are
worktree-safe.

The load-bearing claim behind opt-in worktree isolation for /refactor
(skills/refactor/references/worktree-isolation.md) is that a hook running from
inside a linked `git worktree` resolves the methodology repo root the same way
it does in the main tree — because a worktree checks out the same commit, so
`.claude-plugin/plugin.json` is present at the worktree root and the walk-up
detection finds it. That detection is what the commit gates
(check-skill-completeness / check-commit-completeness) use to decide whether to
fire; if it broke in a worktree, a /refactor commit from the worktree would slip
past the gates.

This test drives `find_repo_root(start)` — the exact walk-up function the commit
gates use — directly (deterministic, no subprocess/stdin/env noise), against a
REAL git worktree (fidelity: proves the worktree actually checks out
plugin.json):
  * find_repo_root(worktree root)        == worktree root   ← the claim
  * find_repo_root(worktree/nested/dir)  == worktree root   ← from deep inside
  * find_repo_root(plain non-repo dir)   is None            ← control

The git-worktree creation SKIPs (exit 0) if git is unavailable; the walk-up
assertions still run against a simulated checkout (a dir with plugin.json) so
the invariant is covered even on a runner without git.

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_worktree_hook_safety.py
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Every hook that resolves the methodology root by walking parents for
# .claude-plugin/plugin.json carries its OWN copy of find_repo_root (not shared
# code), so a future edit to one could diverge. Drive each independently — the
# audit's walk-up claim covers all of them, not one representative. (careful.sh
# uses the same walk-up but via os.getcwd() with no path argument, so it is not
# in this path-arg set; its logic is identical and CLAUDE-md/cwd-based, covered
# by the audit doc's note.)
HOOKS = [
    ROOT / "hooks" / "check-skill-completeness.sh",
    ROOT / "hooks" / "check-commit-completeness.sh",
]

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def load_find_repo_root(hook: Path):
    """Import find_repo_root from the .sh-that-is-python hook (meta_review
    pattern): copy to a .py so importlib will load it, then grab the symbol."""
    tmp = Path(tempfile.gettempdir()) / f"_wt_import_{uuid.uuid4().hex[:8]}.py"
    shutil.copy(hook, tmp)
    try:
        spec = importlib.util.spec_from_file_location("_csc_mod", tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore
        return mod.find_repo_root
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


def git(args, cwd) -> subprocess.CompletedProcess:
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=60)


def make_checkout(base: Path) -> tuple[Path, bool]:
    """Return (checkout_root, is_real_worktree). Prefer a real git worktree;
    fall back to a simulated checkout (plain dir with plugin.json) when git is
    unavailable — find_repo_root only cares about the plugin.json marker."""
    def seed_marker(root: Path) -> None:
        (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (root / ".claude-plugin" / "plugin.json").write_text(
            '{"name": "idea-to-deploy"}', encoding="utf-8")

    if shutil.which("git"):
        repo = base / "repo"
        repo.mkdir()
        if git(["init", "-q"], repo).returncode == 0:
            seed_marker(repo)
            git(["add", "-A"], repo)
            if git(["commit", "-qm", "init"], repo).returncode == 0:
                wt = base / "wt"
                if git(["worktree", "add", "-q", str(wt)], repo).returncode == 0:
                    return wt, True
    # Fallback: simulated checkout.
    sim = base / "sim"
    seed_marker(sim)
    return sim, False


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="wt-safety-"))
    try:
        wt, real = make_checkout(base)
        print(("using REAL git worktree" if real
               else "git unavailable — using simulated checkout") + f": {wt}\n")

        check("worktree/checkout contains .claude-plugin/plugin.json",
              (wt / ".claude-plugin" / "plugin.json").is_file())

        nested = wt / "src" / "deep"
        nested.mkdir(parents=True)
        plain = base / "plain"
        plain.mkdir()

        # Drive EACH plugin.json-walk-up hook's own find_repo_root — the audit
        # claim covers all of them, so a per-hook copy that diverged must fail.
        for hook in HOOKS:
            find_repo_root = load_find_repo_root(hook)
            tag = hook.name
            check(f"[{tag}] CLAIM: find_repo_root(worktree root) resolves to "
                  "the worktree root (repo detected from the worktree)",
                  find_repo_root(wt) == wt, f"got {find_repo_root(wt)}")
            check(f"[{tag}] find_repo_root from a nested dir inside the worktree "
                  "resolves to the worktree root",
                  find_repo_root(nested) == wt, f"got {find_repo_root(nested)}")
            check(f"[{tag}] control: find_repo_root(non-repo dir) is None",
                  find_repo_root(plain) is None, f"got {find_repo_root(plain)}")

        if real:
            git(["worktree", "remove", "--force", str(wt)], base / "repo")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
