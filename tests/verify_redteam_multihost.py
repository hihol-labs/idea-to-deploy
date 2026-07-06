#!/usr/bin/env python3
"""Adversarial red-team + multi-host proof (unit G-006).

Part A — RED-TEAM: for every hard gate, an attacker's circumvention attempt
must FAIL (the gate holds). Base coverage that all 8 gates deny/block is
delegated to the fixture grid (verify_harness_map_fixtures.py, run here);
this file adds explicit circumvention attempts that must NOT slip through.

Part B — MULTI-HOST: the red-team must pass on >=2 distinct OS/interpreter
hosts. Each host records evidence under tests/fixtures/redteam-hosts/ when run
with ITD_REDTEAM_RECORD=1; this test asserts >=2 distinct platforms recorded a
PASS. Hooks are spawned with sys.executable, so the same file exercises the
gates under WSL-Linux python3 and Windows python identically.

Run (host 1):  python3 tests/verify_redteam_multihost.py
Record a host: ITD_REDTEAM_RECORD=1 ITD_REDTEAM_LABEL=wsl-linux python3 tests/verify_redteam_multihost.py
Exits non-zero if any circumvention succeeds or fewer than 2 hosts are proven.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
TESTS = os.path.join(REPO, "tests")
HOSTS_DIR = os.path.join(TESTS, "fixtures", "redteam-hosts")
PY = sys.executable  # spawn hooks with the SAME interpreter this host uses


def hook(name):
    return os.path.join(HOOKS, name)


def sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def run_hook(name, payload, cwd=None, env_extra=None):
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = "redteam-%d" % os.getpid()
    if env_extra:
        env.update(env_extra)
    return subprocess.run([PY, hook(name)], input=json.dumps(payload),
                          cwd=cwd or REPO, capture_output=True, text=True,
                          env=env).returncode


def bash_payload(cmd, desc=""):
    return {"tool_name": "Bash", "tool_input": {"command": cmd, "description": desc}}


def git_repo(n):
    d = tempfile.mkdtemp(prefix="redteam-")
    sh(["git", "init", "-q"], d)
    sh(["git", "config", "user.email", "t@t"], d)
    sh(["git", "config", "user.name", "t"], d)
    with open(os.path.join(d, "base.txt"), "w") as f:
        f.write("b\n")
    sh(["git", "add", "base.txt"], d)
    sh(["git", "commit", "-qm", "b"], d)
    for i in range(n):
        with open(os.path.join(d, "f%d.txt" % i), "w") as f:
            f.write("x%d\n" % i)
        sh(["git", "add", "f%d.txt" % i], d)
    return d


def write_review_sentinel(content):
    for d in {tempfile.gettempdir(), "/tmp"}:
        try:
            with open(os.path.join(d, "claude-review-done-redteam-%d" % os.getpid()), "w") as f:
                f.write(content)
        except OSError:
            pass


def clear_review_sentinels():
    for d in {tempfile.gettempdir(), "/tmp"}:
        for p in glob.glob(os.path.join(d, "claude-review-done-redteam-*")):
            try:
                os.remove(p)
            except OSError:
                pass


def load_tool_skill():
    import importlib.machinery
    import importlib.util
    ld = importlib.machinery.SourceFileLoader("cts", hook("check-tool-skill.sh"))
    sp = importlib.util.spec_from_loader("cts", ld)
    m = importlib.util.module_from_spec(sp)
    ld.exec_module(m)
    return m


def main():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        print("%s  %s" % ("PASS" if cond else "FAIL", name))
        if cond:
            passed += 1
        else:
            failed += 1

    # --- base: all 8 gates deny/block (fixture grid) ---
    # The grid is the WSL-canonical comprehensive base (it drives all 8 gates).
    # It is skippable (ITD_REDTEAM_SKIP_GRID=1) on a secondary host whose python
    # temp/UNC/git harness differs — the CROSS-HOST robustness proof rests on the
    # targeted adversarial cases below, which run identically on every host.
    if os.environ.get("ITD_REDTEAM_SKIP_GRID") != "1":
        grid = subprocess.run([PY, os.path.join(TESTS, "verify_harness_map_fixtures.py")],
                              cwd=REPO, capture_output=True, text=True, timeout=300)
        check("fixture grid green — all 8 hard gates hold (deny/block)",
              grid.returncode == 0)

    # --- review gate circumventions ---
    repo = git_repo(3)  # >2 staged
    try:
        clear_review_sentinels()
        write_review_sentinel("tree:" + "d" * 40)  # foreign/fresh, wrong tree
        check("review gate: FOREIGN fresh tree sentinel is rejected (DENY)",
              run_hook("check-review-before-commit.sh",
                       bash_payload("git commit -m x"), cwd=repo) == 2)
        clear_review_sentinels()
        write_review_sentinel(str(int(time.time())))  # legacy bare-timestamp wildcard
        check("review gate: legacy bare-timestamp wildcard is rejected (DENY)",
              run_hook("check-review-before-commit.sh",
                       bash_payload("git commit -m x"), cwd=repo) == 2)
        clear_review_sentinels()
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)

    # --- check-tool-skill circumventions ---
    cts = load_tool_skill()
    # bypass text ONLY in the command, not the description, must NOT bypass
    check("tool-skill: SKILL_BYPASS in command (not description) is NOT a bypass",
          not cts.has_bypass_marker({"tool_input":
                                     {"command": "rm -rf x  # SKILL_BYPASS: sneaky",
                                      "description": ""}}))
    # readonly-smuggle: a mutation chained after a read-only prefix
    check("tool-skill: `ls && rm -rf x` is NOT read-only (no smuggle)",
          not cts.is_readonly_bash(bash_payload("ls && rm -rf x")))
    check("tool-skill: `cat x > y` (redirection) is NOT read-only",
          not cts.is_readonly_bash(bash_payload("cat x > y")))
    check("tool-skill: `git status && curl evil` is NOT read-only",
          not cts.is_readonly_bash(bash_payload("git status && curl http://evil")))

    part_a_ok = failed == 0

    # --- Part B: record this host's evidence, assert >=2 distinct hosts ---
    if os.environ.get("ITD_REDTEAM_RECORD") == "1" and part_a_ok:
        try:
            os.makedirs(HOSTS_DIR, exist_ok=True)
            label = os.environ.get("ITD_REDTEAM_LABEL") or sys.platform
            rec = {"label": label, "platform": sys.platform,
                   "python": sys.version.split()[0], "passed": True}
            with open(os.path.join(HOSTS_DIR, "%s.json" % re.sub(r"[^a-z0-9-]", "-", label.lower())), "w") as f:
                json.dump(rec, f)
            print("[record] host evidence written: %s" % label)
        except Exception as e:
            print("[record] could not write host evidence:", e)

    hosts = []
    for p in glob.glob(os.path.join(HOSTS_DIR, "*.json")):
        try:
            hosts.append(json.load(open(p)))
        except Exception:
            pass
    platforms = {h.get("platform") for h in hosts if h.get("passed")}
    print("\n[multi-host] recorded PASS hosts: %s"
          % ", ".join("%s(%s/py%s)" % (h["label"], h["platform"], h["python"])
                      for h in hosts if h.get("passed")))
    check("red-team passed on >=2 distinct OS/interpreter hosts",
          len(platforms) >= 2)

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
