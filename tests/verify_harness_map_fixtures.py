#!/usr/bin/env python3
"""Fixture-proof self-grading grid (unit G-003).

The HARNESS_ENGINEERING_MAP marks the H1/H3 enforcement axes ✅. Those ticks
used to rest on "the hook exists" — a doc-vs-enforcement claim. This grid
turns each ✅ into a *behavioural* proof: every HARD gate (the 8 hooks that
can `deny`/`block`, derived here by the same blocking-decision regex as
`verify_gate_taxonomy.py`) must be mapped to a test that actually spawns the
hook and asserts a real exit-2/block outcome, and that test must pass.

If a 9th hard gate is added without a behavioural proof test, `GATE_TESTS`
no longer covers the derived hard set and this test FAILS — so a gate can
never be graded ✅ without a passing block/deny fixture.

Reported metric: **hard-gate coverage = passing-proofs / hard-gates**;
target 8/8.

Run: python3 tests/verify_harness_map_fixtures.py
Exits non-zero if any hard gate lacks a passing behavioural proof.
"""
import glob
import os
import re
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
TESTS = os.path.join(REPO, "tests")

BLOCK_RE = re.compile(
    r'permissionDecision"?\s*:\s*"deny"'
    r'|"decision"\s*:\s*"block"'
    r'|sys\.exit\(2\)'
    r'|(?:^|\s|;)exit\s+2(?:\s|$)',
    re.M,
)

# hard gate hook  ->  behavioural test that drives it to deny/block
GATE_TESTS = {
    "check-review-before-commit.sh": "verify_review_sentinel_diffbind.py",
    "check-dod-before-commit.sh":    "verify_dod_gate.py",
    "check-commit-completeness.sh":  "verify_commit_completeness_gate.py",
    "check-skill-completeness.sh":   "verify_skill_completeness_gate.py",
    "check-tool-skill.sh":           "verify_skill_enforcement.py",
    "pii-egress-guard.sh":           "verify_pii_egress.py",
    "narration-final.sh":            "verify_narration_final.py",
    "verdict-contract.sh":           "verify_verdict_contract.py",
    "completion-gate.sh":            "verify_completion_gate.py",
    "state-guard.sh":                "verify_state_hardening.py",
    "cost-tracker.sh":               "verify_cost_gate.py",
}

# a mapped test is "behavioural" if it spawns a subprocess and asserts a
# block/deny/exit-2 outcome (not merely a doc grep)
SPAWN_RE = re.compile(r"subprocess|Popen|check_output|\.run\(")
ASSERT_RE = re.compile(r"==\s*2|returncode|permissionDecision|\bdeny\b|\bblock\b")


def derived_hard_gates():
    hard = []
    for h in sorted(glob.glob(os.path.join(HOOKS, "*.sh"))):
        if BLOCK_RE.search(open(h, encoding="utf-8").read()):
            hard.append(os.path.basename(h))
    return set(hard)


def is_behavioural(test_path, hook_stem):
    src = open(test_path, encoding="utf-8").read()
    return (hook_stem in src) and bool(SPAWN_RE.search(src)) and bool(ASSERT_RE.search(src))


def run_test(test_path):
    return subprocess.run(["python3", test_path], cwd=REPO,
                          capture_output=True, text=True, timeout=180).returncode


def main():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        print("%s  %s" % ("PASS" if cond else "FAIL", name))
        if cond:
            passed += 1
        else:
            failed += 1

    hard = derived_hard_gates()
    check("derived hard-gate set has 11 members", len(hard) == 11)

    # every hard gate is mapped to a proof, and nothing extraneous is mapped
    check("GATE_TESTS covers exactly the derived hard set (no gap)",
          set(GATE_TESTS) == hard)
    missing = hard - set(GATE_TESTS)
    if missing:
        print("   UNPROVEN hard gates (no behavioural test mapped):", sorted(missing))

    covered = 0
    for gate in sorted(hard):
        test_name = GATE_TESTS.get(gate)
        if not test_name:
            check("proof mapped for %s" % gate, False)
            continue
        test_path = os.path.join(TESTS, test_name)
        exists = os.path.exists(test_path)
        check("proof test exists: %s -> %s" % (gate, test_name), exists)
        if not exists:
            continue
        hook_stem = gate[:-3]  # strip .sh
        behav = is_behavioural(test_path, hook_stem)
        check("proof is behavioural (spawns hook + asserts block/deny): %s" % test_name,
              behav)
        rc = run_test(test_path)
        ok = rc == 0
        check("proof PASSES (drives %s to block/deny): %s" % (gate, test_name), ok)
        if exists and behav and ok:
            covered += 1

    cov_ok = covered == len(hard)
    print("\n[metric] hard-gate coverage = %d/%d (%.0f%%)"
          % (covered, len(hard), 100.0 * covered / max(1, len(hard))))
    check("hard-gate coverage == 11/11 (every hard gate behaviourally proven)", cov_ok)

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
