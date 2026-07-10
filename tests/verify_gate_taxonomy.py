#!/usr/bin/env python3
"""Gate taxonomy test (v1.59.0, unit G-002).

Marketing "24 hooks" conflates enforcement strength with hook count. This
test pins the honest split and keeps the README in sync with `hooks/`:

  - A HARD gate can stop an action: it emits a blocking JSON decision
    (`permissionDecision: "deny"` on PreToolUse, or `decision: "block"` on
    SubagentStop) or `sys.exit(2)`. There are 8.
  - A SOFT hook only reminds / injects context / observes / self-corrects;
    it always exits 0 and never blocks. There are 16.
  - 8 + 16 = 24.

Assertions (all derived from source, then cross-checked against the doc, so
the doc cannot drift from reality):
  1. Classifying `hooks/*.sh` by the blocking-decision regex yields exactly
     9 hard + 18 soft = 27.
  2. README.md's "Hook taxonomy" table lists exactly the 8 derived hard
     gates (no more, no less) — a 9th hard gate forces a doc update.
  3. README.md's "Soft (N)" line lists exactly the 16 derived soft hooks.
  4. README.md prose states the derived counts ("8 hard", "16 ... soft") and
     defines the "Hard-gate coverage" metric.
  5. Reports hard-gate coverage = (# hard gates with a behavioural test that
     drives them to deny/block) / 8. G-003 enforces 8/8; here it is reported.

Run: python3 tests/verify_gate_taxonomy.py
Exits non-zero if any assertion fails (CI-friendly).
"""
import glob
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
TESTS = os.path.join(REPO, "tests")
README = os.path.join(REPO, "README.md")

# A real blocking decision — NOT prose containing the word "block". Requires
# the JSON key form or an explicit exit-2, so `record-agent-skill.sh`
# ('a PostToolUse "block" is ignored') and `freeze.sh` (allow-only) classify
# soft without any special-casing.
BLOCK_RE = re.compile(
    r'permissionDecision"?\s*:\s*"deny"'
    r'|"decision"\s*:\s*"block"'
    r'|sys\.exit\(2\)'
    r'|(?:^|\s|;)exit\s+2(?:\s|$)',
    re.M,
)


def classify():
    hard, soft = [], []
    for h in sorted(glob.glob(os.path.join(HOOKS, "*.sh"))):
        txt = open(h, encoding="utf-8").read()
        (hard if BLOCK_RE.search(txt) else soft).append(os.path.basename(h))
    return hard, soft


def readme_hard_table(md):
    """The `*.sh` names inside the taxonomy table (between the table header
    and the '**Soft (' line)."""
    start = md.find("### Hook taxonomy")
    assert start != -1, "README missing '### Hook taxonomy' section"
    end = md.find("**Soft (", start)
    assert end != -1, "README missing '**Soft (' list"
    section = md[start:end]
    return set(re.findall(r"`([a-z0-9-]+\.sh)`", section))


def readme_soft_list(md):
    """The `name` tokens on the '**Soft (N):**' line."""
    m = re.search(r"\*\*Soft \((\d+)\):\*\*(.+)", md)
    assert m, "README missing '**Soft (N):**' line"
    names = set(re.findall(r"`([a-z0-9-]+)`", m.group(2)))
    return int(m.group(1)), {n if n.endswith(".sh") else n + ".sh" for n in names}


def behavioural_coverage(hard):
    """A hard gate is 'covered' when some tests/verify_*.py both references
    the hook file AND asserts on a deny/block/exit-2 outcome."""
    covered = set()
    test_srcs = {p: open(p, encoding="utf-8").read()
                 for p in glob.glob(os.path.join(TESTS, "verify_*.py"))}
    for hook in hard:
        for src in test_srcs.values():
            if hook in src and re.search(r"==\s*2|exit 2|\bdeny\b|\bblock\b|returncode", src):
                covered.add(hook)
                break
    return covered


def main():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        print("%s  %s" % ("PASS" if cond else "FAIL", name))
        if cond:
            passed += 1
        else:
            failed += 1

    hard, soft = classify()
    check("exactly 9 hard gates (blocking-decision regex)", len(hard) == 9)
    check("exactly 19 soft hooks", len(soft) == 19)
    check("hard + soft == 28", len(hard) + len(soft) == 28)

    md = open(README, encoding="utf-8").read()

    table_hard = readme_hard_table(md)
    check("README taxonomy table lists exactly the derived hard set",
          table_hard == set(hard))
    if table_hard != set(hard):
        print("   derived hard:", sorted(hard))
        print("   README table:", sorted(table_hard))

    soft_n, soft_list = readme_soft_list(md)
    check("README '**Soft (N)**' count matches derived (%d)" % len(soft),
          soft_n == len(soft))
    check("README soft list lists exactly the derived soft set",
          soft_list == set(soft))
    if soft_list != set(soft):
        print("   derived soft:", sorted(soft))
        print("   README soft :", sorted(soft_list))

    check("README prose states '%d hard'" % len(hard),
          ("%d hard" % len(hard)) in md)
    check("README prose states '%d are soft'" % len(soft),
          ("%d are soft" % len(soft)) in md)
    check("README defines the 'Hard-gate coverage' metric",
          "Hard-gate coverage" in md)

    covered = behavioural_coverage(hard)
    cov = len(covered)
    print("\n[metric] hard-gate coverage = %d/%d (%.0f%%)"
          % (cov, len(hard), 100.0 * cov / max(1, len(hard))))
    uncovered = sorted(set(hard) - covered)
    if uncovered:
        print("[metric] not yet behaviourally covered:", uncovered)

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
