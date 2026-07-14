#!/usr/bin/env python3
"""Drift guards (v1.39.0) — prevent the two regressions an audit could catch:

  P4  Hook registration completeness. Every hook file in hooks/ must be EITHER
      in the canonical registration set (DESIRED_HOOKS in scripts/sync-to-active.sh)
      OR in the explicit opt-in allowlist (freeze). This is exactly the v1.37.0
      root-cause bug (hooks shipped but silently unregistered) turned into a test.

  P5  Count consistency. The skill/agent/hook counts asserted in plugin.json,
      marketplace.json, docs/HARNESS_ENGINEERING_MAP.md, and the global CLAUDE.md
      template must all equal the ACTUAL counts on disk. Stops "34 skills / 16
      hooks"-style stale docs.

Self-contained. Run: python3 tests/verify_registration_and_counts.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Hooks that ship but are intentionally NOT registered (activated on demand).
# v1.42.0: freeze.sh is now REGISTERED (it is a no-op until a skill writes the
# freeze state file, so always-on registration costs nothing) — the set is
# empty, kept for the next genuinely opt-in hook.
OPT_IN_HOOKS: set = set()

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# --- actual counts on disk -------------------------------------------------
# Underscore-prefixed directories are internal libraries. `_shared/SKILL.md`
# exists so Codex plugin ingestion can validate every directory, but it is not
# a user-facing workflow and must not inflate published skill counts.
skills = [d for d in os.listdir(os.path.join(ROOT, "skills"))
          if not d.startswith("_")
          and os.path.isfile(os.path.join(ROOT, "skills", d, "SKILL.md"))]
agents = [f for f in os.listdir(os.path.join(ROOT, "agents")) if f.endswith(".md")]
hook_files = [f for f in os.listdir(os.path.join(ROOT, "hooks")) if f.endswith(".sh")]
N_SKILLS, N_AGENTS, N_HOOKS = len(skills), len(agents), len(hook_files)
print("actual: %d skills, %d agents, %d hooks\n" % (N_SKILLS, N_AGENTS, N_HOOKS))


# --- P4: hook registration completeness ------------------------------------
sync = read("scripts/sync-to-active.sh")
# Extract only the DESIRED_HOOKS heredoc so prose/other refs don't count.
m = re.search(r"DESIRED_HOOKS=\$\(cat <<'JSON'\n(.*?)\nJSON", sync, re.DOTALL)
check("DESIRED_HOOKS heredoc found in sync-to-active.sh", m is not None)
registered = set(re.findall(r"~/\.claude/hooks/([a-z0-9-]+\.sh)", m.group(1))) if m else set()

files = set(hook_files)
unregistered = files - registered - OPT_IN_HOOKS
check("every hook file is registered or explicitly opt-in", not unregistered,
      "orphans: " + ", ".join(sorted(unregistered)))
missing_files = registered - files
check("every registered hook has a file", not missing_files,
      "registered but absent: " + ", ".join(sorted(missing_files)))
# freeze must stay out of the registered set (it is opt-in by design).
check("opt-in hooks are NOT in the registered set",
      not (OPT_IN_HOOKS & registered),
      "unexpectedly registered: " + ", ".join(sorted(OPT_IN_HOOKS & registered)))
print("  registered ITD hooks: %d" % len(registered))


# --- P5: count consistency across manifests & docs -------------------------
def assert_counts(label, text, pat):
    mm = re.search(pat, text)
    if not mm:
        check("%s: count triple present" % label, False, "pattern not found")
        return
    s, a, h = int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
    check("%s counts == actual (%d/%d/%d)" % (label, N_SKILLS, N_AGENTS, N_HOOKS),
          (s, a, h) == (N_SKILLS, N_AGENTS, N_HOOKS),
          "doc says %d/%d/%d" % (s, a, h))


# Optional qualifier word before "agents"/"hooks" (e.g. "specialized subagents",
# "enforcement hooks") — the manifests phrase it slightly differently.
MANIFEST_PAT = (r"(\d+)\s+skills\s*\+\s*(\d+)\s+(?:\w+\s+)?(?:sub)?agents"
                r"\s*\+\s*(\d+)\s+(?:\w+\s+)?hooks")
assert_counts("plugin.json", read(".claude-plugin/plugin.json"), MANIFEST_PAT)
assert_counts("marketplace.json", read(".claude-plugin/marketplace.json"), MANIFEST_PAT)
assert_counts("HARNESS_ENGINEERING_MAP.md", read("docs/HARNESS_ENGINEERING_MAP.md"),
              r"(\d+)\s+skills,\s*(\d+)\s+subagents,\s*(\d+)\s+hooks")
assert_counts("global-claude-md template", read("docs/templates/global-claude-md.md"),
              r"(\d+)\s+skills\s*\+\s*(\d+)\s+agents\s*\+\s*(\d+)\s+hooks")

# The template must carry the ITD:BEGIN/END markers sync relies on.
tpl = read("docs/templates/global-claude-md.md")
check("template has ITD:BEGIN/END markers",
      "<!-- ITD:BEGIN" in tpl and "<!-- ITD:END methodology -->" in tpl)


print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
