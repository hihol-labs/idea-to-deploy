#!/usr/bin/env python3
"""Table-completeness drift-guard for the hook docs (unit G-005).

Registration completeness (every hook file is registered or opt-in) is already
guarded by verify_registration_and_counts.py (P4). This guard closes the other
half: the DOCS must list every hook AND label its enforcement correctly.

It caught real drift when written: the HARNESS_MAP §8.2 per-hook table was
missing `narration-final.sh` and `verdict-contract.sh` (the two SubagentStop
hard gates), and §8.1/§8.2 mislabelled `careful.sh`/`freeze.sh` as "blocking"
though both self-declare `exit 0, permissionDecision: allow`.

Assertions (all derived from `hooks/` + the blocking-decision classifier, then
cross-checked against the docs so a doc cannot silently drift):
  1. The §8.2 per-hook table lists EXACTLY the hooks in `hooks/*.sh` — a hook
     added or removed on disk forces a table update.
  2. The §8.1 quadrant matrix mentions every disk hook.
  3. The rows the §8.2 table marks **blocking** equal the 8 hard gates derived
     by the blocking-decision regex — mislabelling a soft hook "blocking" (or
     omitting a real gate) fails here.
  4. The README taxonomy (8 hard table ∪ 16 soft line) equals the disk hook set
     (full-coverage cross-check with G-002's split).
  5. §8.1 header states the current hook count.

Run: python3 tests/verify_hook_table_completeness.py
Exits non-zero if the docs drift from `hooks/`.
"""
import glob
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
MAP = os.path.join(REPO, "docs", "HARNESS_ENGINEERING_MAP.md")
README = os.path.join(REPO, "README.md")

BLOCK_RE = re.compile(
    r'permissionDecision"?\s*:\s*"deny"'
    r'|"decision"\s*:\s*"block"'
    r'|sys\.exit\(2\)'
    r'|(?:^|\s|;)exit\s+2(?:\s|$)',
    re.M,
)


def disk_hooks():
    return {os.path.basename(h) for h in glob.glob(os.path.join(HOOKS, "*.sh"))}


def derived_hard():
    hard = set()
    for h in glob.glob(os.path.join(HOOKS, "*.sh")):
        if BLOCK_RE.search(open(h, encoding="utf-8").read()):
            hard.add(os.path.basename(h))
    return hard


def section(md, start_marker, end_marker):
    a = md.find(start_marker)
    b = md.find(end_marker, a + 1) if a != -1 else -1
    return md[a:b] if a != -1 and b != -1 else ""


def map_table_rows(md):
    """Return {hook.sh: is_blocking} from the §8.2 per-hook table rows."""
    sec = section(md, "### 8.2", "### 8.3")
    rows = {}
    for line in sec.splitlines():
        m = re.match(r"\|\s*`([a-z0-9-]+\.sh)`\s*\|", line)
        if m:
            rows[m.group(1)] = "**blocking**" in line
    return rows


def map_matrix_names(md):
    """Bare hook names (no .sh) mentioned anywhere in the §8.1 matrix block."""
    sec = section(md, "### 8.1", "### 8.2")
    return set(re.findall(r"`([a-z0-9-]+)`", sec))


def readme_taxonomy(md):
    start = md.find("### Hook taxonomy")
    end = md.find("**Soft (", start)
    table = md[start:end]
    hard = set(re.findall(r"`([a-z0-9-]+\.sh)`", table))
    m = re.search(r"\*\*Soft \(\d+\):\*\*(.+)", md)
    soft = {n if n.endswith(".sh") else n + ".sh"
            for n in re.findall(r"`([a-z0-9-]+)`", m.group(1))}
    return hard, soft


def main():
    passed = failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        print("%s  %s%s" % ("PASS" if cond else "FAIL", name,
                            ("  [%s]" % detail) if detail and not cond else ""))
        if cond:
            passed += 1
        else:
            failed += 1

    disk = disk_hooks()
    hard = derived_hard()
    md = open(MAP, encoding="utf-8").read()
    rd = open(README, encoding="utf-8").read()

    # 1. §8.2 table lists exactly the disk hooks
    rows = map_table_rows(md)
    table_hooks = set(rows)
    check("§8.2 per-hook table lists exactly hooks/*.sh (%d)" % len(disk),
          table_hooks == disk,
          "missing: %s | extra: %s" % (sorted(disk - table_hooks),
                                       sorted(table_hooks - disk)))

    # 2. §8.1 matrix mentions every disk hook
    matrix = map_matrix_names(md)
    disk_stems = {h[:-3] for h in disk}
    check("§8.1 matrix mentions every disk hook",
          disk_stems <= matrix,
          "not in matrix: %s" % sorted(disk_stems - matrix))

    # 3. §8.2 'blocking' rows == the 8 hard gates (classifier)
    doc_blocking = {h for h, b in rows.items() if b}
    check("§8.2 'blocking' rows == the 11 hard gates",
          doc_blocking == hard,
          "doc-only: %s | classifier-only: %s"
          % (sorted(doc_blocking - hard), sorted(hard - doc_blocking)))
    check("exactly 11 hard gates", len(hard) == 11)

    # 4. README taxonomy union == disk hooks
    r_hard, r_soft = readme_taxonomy(rd)
    check("README taxonomy (hard ∪ soft) == disk hook set",
          (r_hard | r_soft) == disk,
          "missing: %s | extra: %s"
          % (sorted(disk - (r_hard | r_soft)), sorted((r_hard | r_soft) - disk)))
    check("README hard table == classifier hard gates", r_hard == hard,
          "diff: %s" % sorted(r_hard ^ hard))

    # 5. §8.1 header states the count
    check("§8.1 header states the hook count %d" % len(disk),
          ("(%d)" % len(disk)) in section(md, "### 8.1", "### 8.2").splitlines()[0])

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
