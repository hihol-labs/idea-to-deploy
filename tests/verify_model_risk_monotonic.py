#!/usr/bin/env python3
"""Invariant test: risk-tier ⇒ model monotonicity for the verify agents (v1.60.0
— Ось 2, agentic engineering, unit G-003).

The higher-risk a verify agent's surface, the higher (never lower) its model
tier must be. The named invariant: the `security-reviewer` (gates exploitability
/ production safety — the highest-stakes verify class) must never sit on a model
tier BELOW the `code-reviewer`. Today security=opus, code=sonnet — monotone; the
value inversion the unit guards against does not currently exist, so this gate's
job is to make regression IMPOSSIBLE (a future cost-cut that quietly drops
security-reviewer to sonnet while code-reviewer is opus fails CI here) AND to pin
the DOCS (MODEL-ROUTING-POLICY.md, AGENT_EFFORT_TIERS.md) to the actual
frontmatter, so the contract can no longer invert from the model.

Asserts:
  1. rank(security-reviewer.model) >= rank(code-reviewer.model)  [named invariant]
  2. security-reviewer.model == opus  [highest-risk verify agent at the top tier]
  3. AGENT_EFFORT_TIERS.md model cells for both agents match their frontmatter
  4. MODEL-ROUTING-POLICY.md documents the monotonicity invariant + names the gate
  5. protected quality-floor agents retain high effort;
  6. the frozen working-deadline policy permits low effort only for bounded
     low/medium mechanical work and never removes evidence contours;
  7. the gate is wired into a CI workflow ("и в CI" clause)

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_model_risk_monotonic.py
Exits non-zero if the invariant or any doc-consistency check fails.
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
POLICY = ROOT / "docs" / "MODEL-ROUTING-POLICY.md"
TIERS = ROOT / "docs" / "AGENT_EFFORT_TIERS.md"
WORKFLOWS = ROOT / ".github" / "workflows"
DEADLINE_POLICY = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"

RANK = {"haiku": 1, "sonnet": 2, "opus": 3}

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def normalize_tier(token: str) -> str:
    """Map a `model:` value to its tier alias. Accepts a bare tier (`opus`) or a
    pinned full id (`claude-opus-4-20250514`) — the family word inside the id is
    the tier. Unknown families fall through unchanged, so they land outside RANK
    and fail SAFE (a clear diagnostic), never a false-pass. This keeps the gate
    policing the invariant, not the naming convention (review G-003 #1)."""
    t = token.strip().lower()
    if t in RANK:
        return t
    for family in RANK:  # opus / sonnet / haiku inside a claude-<family>-… id
        if re.search(r"(?:^|[-_.])" + family + r"(?:[-_.]|$)", t):
            return family
    return t


def frontmatter_model(agent: str) -> str | None:
    """Read the `model:` value from an agent's YAML frontmatter (tier-normalized)."""
    f = AGENTS / (agent + ".md")
    if not f.is_file():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*model:\s*([A-Za-z0-9._-]+)", line)
        if m:
            return normalize_tier(m.group(1))
    return None


def frontmatter_effort(agent: str) -> str | None:
    f = AGENTS / (agent + ".md")
    if not f.is_file():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*effort:\s*(low|medium|high)\s*$", line)
        if m:
            return m.group(1)
    return None


def tiers_model(agent: str) -> str | None:
    """Extract the model token from the AGENT_EFFORT_TIERS.md row for `agent`."""
    if not TIERS.is_file():
        return None
    for line in TIERS.read_text(encoding="utf-8").splitlines():
        if "`" + agent + "`" in line and "|" in line:
            cells = [c.strip().lower() for c in line.split("|")]
            for c in cells:
                token = c.strip("* ")
                if token in RANK:
                    return token
    return None


def main() -> int:
    sec = frontmatter_model("security-reviewer")
    code = frontmatter_model("code-reviewer")

    check("security-reviewer has a parseable model frontmatter",
          sec in RANK, "got %r" % sec)
    check("code-reviewer has a parseable model frontmatter",
          code in RANK, "got %r" % code)
    if sec not in RANK or code not in RANK:
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1

    # 1. named invariant: security tier >= code tier
    check("invariant: rank(security-reviewer) >= rank(code-reviewer)",
          RANK[sec] >= RANK[code],
          "security=%s(%d) < code=%s(%d) — INVERSION" %
          (sec, RANK[sec], code, RANK[code]))

    # 2. highest-risk verify agent at the top tier
    check("security-reviewer sits at the top model tier (opus)",
          sec == "opus", "security-reviewer model = %s, expected opus" % sec)

    # 3. AGENT_EFFORT_TIERS.md rows agree with frontmatter (no doc drift)
    t_sec = tiers_model("security-reviewer")
    t_code = tiers_model("code-reviewer")
    check("AGENT_EFFORT_TIERS.md security-reviewer model matches frontmatter",
          t_sec == sec, "table=%r frontmatter=%r" % (t_sec, sec))
    check("AGENT_EFFORT_TIERS.md code-reviewer model matches frontmatter",
          t_code == code, "table=%r frontmatter=%r" % (t_code, code))

    # 4. MODEL-ROUTING-POLICY.md documents the invariant + names the gate
    pol = POLICY.read_text(encoding="utf-8") if POLICY.is_file() else ""
    pol_low = pol.lower()
    check("MODEL-ROUTING-POLICY.md documents risk-tier => model monotonicity",
          "monoton" in pol_low
          and "security-reviewer" in pol_low and "code-reviewer" in pol_low,
          "policy must state the monotonicity invariant over the two agents")
    check("MODEL-ROUTING-POLICY.md names this gate as the enforcer",
          "verify_model_risk_monotonic.py" in pol,
          "policy should point at the CI gate that enforces the invariant")

    # 5. protected roles keep their declared high-effort floor.
    protected = ("architect", "code-reviewer", "devils-advocate",
                 "perf-analyzer", "security-reviewer", "test-generator")
    protected_effort = {agent: frontmatter_effort(agent) for agent in protected}
    check("protected review/security/root-cause/architecture roles remain high effort",
          all(value == "high" for value in protected_effort.values()),
          repr(protected_effort))

    # 6. frozen working-deadline model-routing contract.
    try:
        deadline = json.loads(DEADLINE_POLICY.read_text(encoding="utf-8"))
        routing = deadline["modelRouting"]
    except (OSError, ValueError, KeyError, TypeError):
        routing = {}
    check("low effort allowlist is bounded low/medium mechanical only",
          set(routing.get("lowEffortAllowedFor") or []) == {
              "bounded-low-mechanical", "bounded-medium-mechanical"},
          repr(routing.get("lowEffortAllowedFor")))
    forbidden = set(routing.get("lowEffortForbiddenFor") or [])
    check("quality-floor and unknown/high risk are forbidden low-effort routes",
          {"review", "security", "root-cause", "architecture",
           "high-risk", "unknown-risk"} <= forbidden, repr(sorted(forbidden)))
    check("model choice cannot remove an evidence contour",
          routing.get("modelChoiceMayRemoveEvidenceContour") is False,
          repr(routing.get("modelChoiceMayRemoveEvidenceContour")))

    # 7. CI wiring
    wired = False
    if WORKFLOWS.is_dir():
        for yml in WORKFLOWS.glob("*.yml"):
            if "verify_model_risk_monotonic.py" in yml.read_text(encoding="utf-8"):
                wired = True
                break
    check("gate is wired into a CI workflow", wired,
          "add 'python3 tests/verify_model_risk_monotonic.py' to a workflow")

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
