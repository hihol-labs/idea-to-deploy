# ADR-001: idea-to-deploy builds no runtime of its own

**Date:** 2026-06-28
**Status:** Accepted
**Review date:** 2026-09-28 (90 days) — or earlier if a supported host ships a
native eval or cost runtime that voids part of this rationale.

> **Portability clarification (2026-07-18):** the no-owned-runtime decision now
> applies to one model-neutral methodology core transported by validated Claude
> Code and Codex adapters. Host-specific APIs remain adapter concerns. This ADR
> does not claim compatibility with arbitrary models or agent hosts.

## Context

The Google whitepaper *The New SDLC With Vibe Coding* (2026) describes an SDLC where
an AI agent executes the phases backed by eval loops, cost/observability, and model
routing. Read literally, it pulls toward building an executable layer of our own — an
`itd` CLI / daemon / state machine / eval-runner / cost-collector / model-router.

Idea to Deploy has a shared methodology core plus host packages, with no
standalone CLI. It already sits on runtime substrates it does not own:

- the active host hook/lifecycle engine (currently Claude Code or Codex);
- **context-mode** (an MCP server + FTS5 store) and its `ctx-stats`;
- host-native **allow / deny / ask permissions** where available, with declared
  adapter degradation otherwise;
- the **`cost-tracker.sh`** ledger (since v1.18.0; hard-ceiling ASK since v1.30.0).

"No runtime" has never meant "no code runs" — hooks are code that runs. It means we do
not ship or operate **our own persistent service**. Prior hard-gate experiments
(acceptance-gate, the `score ≥ 7` gate, adversarial debates) were rejected for false
blocks / non-deterministic validation; that lesson informs this one.

## Decision

**We do not build our own runtime.** We delegate execution to the existing substrate:

- lifecycle / gating → the active host adapter and lifecycle engine;
- context volume & cost → context-mode + `cost-tracker.sh` / `context-budget.sh`;
- model selection → host-native model/effort controls plus role policy. The
  current Claude adapter uses `/model` + per-agent `model:` frontmatter; Codex
  uses its native model/effort transport (see
  [MODEL-ROUTING-POLICY.md](../MODEL-ROUTING-POLICY.md));
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
- **Automatic cross-vendor model router** — rejected: opaque and host-coupled;
  explicit host controls plus role policy give the economic effect
  transparently without pretending provider equivalence.
- **Own observability platform** — rejected: real platforms exist (LangSmith,
  context-mode Insight, OTel); we cannot and need not out-build them.

## Consequences

- (+) Zero new executable surface; count cascades do not trigger (skills/hooks
  unchanged); `meta_review.py` Critical stays reachable at 0.
- (+) Portability across the currently validated Claude Code and Codex adapters,
  with no external daemon.
- (−) Capability is bounded by what each host's hooks, prompts, and permissions
  can express. A host adapter must declare degradations; a hook
  cannot literally pause the agent loop, so a "limit" is realized as an **ASK**, not a
  hard block (already the pattern in `cost-tracker.sh` v1.30.0).
- (Risk) Eval / cost signal depends on the user actually running CI and reading the
  ledger; mitigation — the врезки make it visible (`/session-save` snapshot, `/task`
  nudge, `/harden` EVAL-1) but never coerce it.

---

## Note (2026-06-28) — Day-3 Context Engineering scope (v1.32.0)

The same series (Google, *The New SDLC With Vibe Coding*) — **Day 3, Context
Engineering** — pulls in the same direction the original decision rejected: it is
tempting to read "manage the agent context window" and "give the agent durable,
async-updated memory" as *build a context store / a memory service of our own*.

This note extends ADR-001 to that material without reopening it. The decision is
unchanged:

- **Context engineering is design work, performed *into the user's product*** — a
  context-budget spec, a retrieval/grounding layout, a prompt-injection boundary, an
  agent-memory schema. The methodology teaches and reviews this design (врезки in
  `/blueprint`, `/discover`, `/test`, `/review`, `/harden`, `/security-audit`,
  `/session-save`); it does **not** ship the store.
- **Our own context substrate is still not ours to build.** Where the *methodology
  session itself* needs context-volume control, that is already delegated to
  **context-mode** (MCP + FTS5) and `context-budget.sh` — see the original Decision.
  We do not add a second store.
- **Async-memory policy (the load-bearing distinction).** "Memory that updates out of
  band" — a background job that writes to an agent's long-term store after the turn —
  belongs to the **user's deployed product**, not to the plugin. The plugin's own
  cross-session memory (`MEMORY.md`, `/session-save`) stays **synchronous and
  in-session**: it is written by an explicit skill step the user can see and review,
  never by a daemon. An out-of-band writer would be exactly the "persistent service"
  this ADR forbids, and — more sharply — an *unreviewed* mutation path into context,
  which is a security surface (see review `C-code-7`, the new `MEMORY_RE` DoD signal,
  and the `/security-audit` context-integrity врезка). Async memory is therefore a
  **product pattern we help design and gate**, not a methodology feature.

**Consequence:** Day-3 adds zero runtime, zero new skill, zero new hook *file* — only
врезки, one new review check (`C-code-7`), and one new risk-signal (`MEMORY_RE`) inside
the existing DoD hook. Counts stay 40 skills / 19 hooks. The Review date above is
unchanged; this note is re-evaluated on the same 2026-09-28 cycle.

---

## Note (2026-06-28) — Day-5 Spec-Driven Production scope (v1.33.0)

Day 5 of the series (*Spec-Driven Production*) tempts hardest toward an owned runtime:
its summary ships an `agents-cli scaffold / eval run / deploy` — exactly the `itd` CLI
this ADR rejects. The decision is unchanged:

- **`agents-cli` / owned agent-runtime → icebox.** Scaffolding, eval-running and deploy
  are delegated to the existing substrate (skills generate artifacts into the user's
  project; the user's CI runs them). We do not ship a CLI / daemon.
- **Zero-Trust Development is product design we help build, not our engine.** Policy
  server, sandboxing, human-in-the-loop, context hygiene — врезки the methodology
  *teaches and audits* (`/harden` `ZT-1`, `/security-audit` `MEM-7`, `/blueprint`
  Step 1.6), realized inside the *user's* deployed agent.
- **Semantic gating is an ASK, never a hard gate.** An LLM "referee" over an action is
  inferential; a blocking inferential gate is non-deterministic (the retired score-gate
  lesson). It is surfaced as advisory / ASK only — a hook cannot pause the model loop,
  the same realization as `cost-tracker.sh` v1.30.0 and the `MEMORY_RE` signal.

**Consequence:** Day-5 adds zero runtime, zero new skill, zero new hook file — only
врезки (`ZT-1`, `MEM-7`, blueprint/adopt/review pointers). Counts stay 40 skills /
19 hooks. Re-evaluated on the same 2026-09-28 cycle.
