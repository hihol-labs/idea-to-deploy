# ADR-001: idea-to-deploy builds no runtime of its own

**Date:** 2026-06-28
**Status:** Accepted
**Review date:** 2026-09-28 (90 days) — or earlier if Claude Code / Anthropic ship a
native eval or cost runtime in the harness, which would void part of this rationale.

## Context

The Google whitepaper *The New SDLC With Vibe Coding* (2026) describes an SDLC where
an AI agent executes the phases backed by eval loops, cost/observability, and model
routing. Read literally, it pulls toward building an executable layer of our own — an
`itd` CLI / daemon / state machine / eval-runner / cost-collector / model-router.

idea-to-deploy is a **Claude Code plugin** (`.claude-plugin/plugin.json`): skills +
agents + hooks, with no standalone CLI. It already sits on a runtime substrate it does
not own:

- the **Claude Code hook engine** (PreToolUse / PostToolUse / Stop / PreCompact / …);
- **context-mode** (an MCP server + FTS5 store) and its `ctx-stats`;
- native **allow / deny / ask permissions**;
- the **`cost-tracker.sh`** ledger (since v1.18.0; hard-ceiling ASK since v1.30.0).

"No runtime" has never meant "no code runs" — hooks are code that runs. It means we do
not ship or operate **our own persistent service**. Prior hard-gate experiments
(acceptance-gate, the `score ≥ 7` gate, adversarial debates) were rejected for false
blocks / non-deterministic validation; that lesson informs this one.

## Decision

**We do not build our own runtime.** We delegate execution to the existing substrate:

- lifecycle / gating → the Claude Code hook engine;
- context volume & cost → context-mode + `cost-tracker.sh` / `context-budget.sh`;
- model selection → native `/model` + per-agent `model:` frontmatter (a *policy*, see
  [MODEL-ROUTING-POLICY.md](../MODEL-ROUTING-POLICY.md), not a router);
- eval-suites → artifacts generated **into the user's project**, run by the user's CI.

The real production runtime (observability and guardrails for *deployed* agents) lives
in the **user's products**. The methodology's job is to help *design* that runtime with
discipline (eval-suite + `/harden` + an observability spec), not to be it. All four
New-SDLC enrichments (A eval-branch, D 80%-checklist, C cost-accounting, B routing
policy) are врезки / policies on the existing substrate, never engines.

## Alternatives considered

- **Own `itd` CLI / daemon / state machine** — rejected: duplicates the harness, breaks
  the "plugin, not CLI" positioning, inflates the solo-maintainer surface, and adds an
  install/port/security burden in an environment already fragile to network/VPN breakage.
- **Global eval / acceptance gate** — rejected: false blocks on non-AI work, no
  deterministic validation of LLM output (same failure as the score-gate / debates).
  Eval signal is therefore opt-in/scoped and advisory, not a gate.
- **Automatic cross-vendor model router** — rejected: opaque, conflicts with explicit
  `/model`; a policy + per-agent frontmatter gives the same economic effect transparently.
- **Own observability platform** — rejected: real platforms exist (LangSmith,
  context-mode Insight, OTel); we cannot and need not out-build them.

## Consequences

- (+) Zero new executable surface; count cascades do not trigger (skills/hooks
  unchanged); `meta_review.py` Critical stays reachable at 0.
- (+) Portability: works in any Claude Code install with no external daemon.
- (−) Capability is bounded by what hooks / prompts / permissions can express — a hook
  cannot literally pause the agent loop, so a "limit" is realized as an **ASK**, not a
  hard block (already the pattern in `cost-tracker.sh` v1.30.0).
- (Risk) Eval / cost signal depends on the user actually running CI and reading the
  ledger; mitigation — the врезки make it visible (`/session-save` snapshot, `/task`
  nudge, `/harden` EVAL-1) but never coerce it.
