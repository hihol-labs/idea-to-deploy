#!/usr/bin/env python3
"""Functional checks for the v1.50.0 Fable 5 release-A snippet pack.

Pins the four vendor-canonical snippets + the cross-cutting harness invariant
(advisor/red-team decision 2026-07-05, release A of the Fable 5 adoption plan):

  #1 docs/templates/global-claude-md.md — "Grounded progress claims" is a
     numbered item INSIDE the "## Always" list, and the "Harness-native
     features — best-effort invariant" section exists INSIDE the
     ITD:BEGIN/ITD:END managed block (sync propagates only that block).
  #2 skills/goal/SKILL.md — the autonomous-run reminder lives between
     Step 2 and Step 3 (it is a unit-driving aid, not goal-closure text) and
     keeps the boundary caveat (data-sensitive still needs a human).
  #3 skills/_shared/helpers.md — §8 delegation intent template with the
     three intent lines and both companion rules (prescriptive triggers,
     report-back contract).
  #4 skills/caveman/SKILL.md — Fable 5 note sits in the Intensity area
     BEFORE Auto-Clarity; lite stays the default; ultra/wenyan are scoped to
     working messages, never final summaries.

Checks are positional/structural where possible — a snippet pasted into the
wrong section must FAIL, not pass on mere substring presence.

Self-contained:  python3 tests/verify_fable_snippets.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def flat(s: str) -> str:
    """Collapse whitespace/newlines/quote-prefixes so phrase checks survive
    markdown line-wrapping ("…your last\n> paragraph…")."""
    return re.sub(r"\s+", " ", s.replace("\n> ", " ").replace("\n", " "))


# ---------------------------------------------------------------- #1 global
g = read("docs/templates/global-claude-md.md")

# The real markers are HTML comments; the header prose also MENTIONS the
# marker names, so match the comment form, not the bare word.
begin, end = g.find("<!-- ITD:BEGIN"), g.find("<!-- ITD:END")
check("global: single managed block, BEGIN before END",
      begin != -1 and end != -1 and begin < end
      and g.count("<!-- ITD:BEGIN") == 1 and g.count("<!-- ITD:END") == 1)

always = re.search(r"## Always\n(.*?)\n## ", g, re.S)
check("global: Always section found", always is not None)
always_body = always.group(1) if always else ""
check("global: grounded-claims is a numbered Always item",
      re.search(r"^\d+\. \*\*Grounded progress claims\.\*\*", always_body, re.M)
      is not None,
      "item must live inside ## Always, numbered like the other rules")
check("global: grounded-claims keeps the evidence wording",
      "audit each claim" in always_body and "tool result" in always_body
      and "Report" in always_body)

inv = re.search(r"## Harness-native features — best-effort invariant.*?(?=\n## |\Z)",
                g, re.S)
check("global: harness-invariant section exists", inv is not None)
inv_body = inv.group(0) if inv else ""
check("global: invariant — transport, never the contract",
      "TRANSPORT" in inv_body and "never BE the contract" in inv_body)
check("global: invariant — vendor-neutral contract named",
      "vendor-neutral" in inv_body)
check("global: invariant — no gate/verified/handoff on a tool-call",
      "gate" in inv_body and "`verified`" in inv_body and "handoff" in inv_body)
check("global: invariant — egress via scrubber + human",
      "scrubber" in inv_body and "human confirmation" in inv_body)
check("global: invariant — background agents read-only",
      "read-only reporters" in inv_body)
check("global: invariant section is INSIDE the managed block",
      inv is not None and begin < g.find("## Harness-native features") < end,
      "sync-to-active.sh only propagates the ITD:BEGIN/END block")

# ------------------------------------------------------------------ #2 goal
goal = read("skills/goal/SKILL.md")

s2 = goal.find("### Step 2:")
s3 = goal.find("### Step 3:")
auto = goal.find("#### Автономный прогон")
check("goal: autonomous reminder present", auto != -1)
check("goal: reminder sits between Step 2 and Step 3",
      s2 != -1 and s3 != -1 and s2 < auto < s3,
      "must be part of unit-driving (Step 2), not goal closure")
auto_body = flat(goal[auto:s3]) if (auto != -1 and s3 != -1) else ""
check("goal: reminder — operating autonomously wording",
      "operating autonomously" in auto_body)
check("goal: reminder — last-paragraph self-check",
      "check your last paragraph" in auto_body)
check("goal: reminder — pairs with narration-final hook",
      "narration-final.sh" in auto_body)
check("goal: reminder — data-sensitive boundary preserved",
      "data-sensitive" in auto_body and "человека" in auto_body,
      "autonomy must not override the human gate on irreversible ops")

# --------------------------------------------------------------- #3 helpers
h = read("skills/_shared/helpers.md")

sec8 = re.search(r"## 8\. Delegation Intent Template.*", h, re.S)
check("helpers: §8 delegation intent template exists", sec8 is not None)
h8 = flat(sec8.group(0)) if sec8 else ""
check("helpers: §8 — three intent lines in the fenced template",
      "Я работаю над" in h8 and "Результат нужен" in h8
      and "С учётом этого" in h8)
check("helpers: §8 — prescriptive triggers rule",
      "Prescriptive triggers" in h8 and "WHEN" in h8)
check("helpers: §8 — report-back contract rule",
      "Report-back contract" in h8 and "return value" in h8)
check("helpers: §8 — pairs with narration-final hook",
      "narration-final.sh" in h8)
check("helpers: §7 context budget untouched above §8",
      h.find("## 7. Context Budget") != -1
      and h.find("## 7. Context Budget") < h.find("## 8. Delegation Intent"))

# --------------------------------------------------------------- #4 caveman
c = read("skills/caveman/SKILL.md")

note = c.find("### Fable 5-class models")
intensity = c.find("## Intensity")
autoclar = c.find("## Auto-Clarity")
check("caveman: Fable 5 note present", note != -1)
check("caveman: note sits in Intensity area, before Auto-Clarity",
      intensity != -1 and autoclar != -1 and intensity < note < autoclar)
note_body = c[note:autoclar] if (note != -1 and autoclar != -1) else ""
check("caveman: note — lite stays the default",
      "lite" in note_body and "default" in note_body)
check("caveman: note — ultra scoped to working messages, not final summaries",
      "inter-tool-call" in note_body and "final summary" in note_body)
check("caveman: note — routed through Auto-Clarity semantics",
      "Auto-Clarity" in note_body)

# ------------------------------------------------------- #5 CI registration
ci = read(".github/workflows/windows-verify.yml")
check("ci: verify_fable_snippets registered in windows-verify",
      "tests/verify_fable_snippets.py" in ci,
      "review finding v1.50.0: the test must guard its own CI registration")

# ------------------------------------------------------------------- result
print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
