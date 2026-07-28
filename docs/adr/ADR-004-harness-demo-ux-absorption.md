# ADR-004: Absorb harness-demo UX without a competing runtime

**Date:** 2026-07-26
**Status:** Accepted
**Review date:** 2026-08-30

## Context

`coleam00/harness-engineering-demo` makes a brownfield harness easy to understand:
it has a short Plan → Implement → Validate path, project-specific context modules,
fast edit feedback, an inspectable captured run, worktree isolation, and structured
symbol navigation.

Idea to Deploy already has stronger acceptance and governance mechanisms:
host-neutral contracts and state, WIP=1, risk-routed review, exact-candidate machine
oracles, and adjudication receipts. Copying the demo literally would add a second
state plane and an owned Ralph runtime while weakening completion evidence to an
agent-written `DONE.txt`.

The measurable gap is therefore usability and feedback latency, not missing
acceptance authority.

| Dimension | Current | Target | Gap | Root cause |
|---|---:|---:|---:|---|
| Generated conditional brownfield context indexes | 0 | 1 per adopted project | 1 | `/adopt` can split a long entry file but does not derive a semantic project map |
| Reproducible, reader-facing captured brownfield runs | 0 | 1 version-pinned run | 1 | Evidence exists across tests and retros, not as one inspectable journey |
| Simple façade commands added | 0 | 0 | 0 | Existing `/task` must be made legible, not duplicated |
| Project-aware incremental diagnostic profiles | 0 | 1 opt-in profile | 1 | Full verification is strong; edit-to-diagnostic latency is not managed |
| Fresh-session isolated brownfield pilots | 0/3 | 3/3 | 3 | Host-native continuation exists, but the worktree/resource recipe lacks a real pilot |
| Declared semantic-navigation capability families | 0 | 1 multi-language contract | 1 | The tool registry describes side effects, not structured code navigation semantics |

## Options considered

### A. Copy the demo wholesale

Add PIV skills, Markdown plan/report state, Ralph, `DONE.txt`, its hooks, and its
Python AST MCP.

- Positive: fastest visual similarity to the demo.
- Negative: duplicates lifecycle/state, is Claude- and Python-specific, bypasses
  exact-candidate verification, and conflicts with ADR-001.
- Decision: rejected.

### B. Absorb the useful UX into existing ITD mechanisms

Extend `/adopt`, `/task`, project checks, operating-loop recipes, the tool capability
registry, and documentation. Keep all authoritative transitions and completion
decisions in the existing contracts and Verification Loop.

- Positive: closes the usability gap without weakening guarantees or adding public
  lifecycle skills.
- Negative: requires cross-host parity work and measured pilots rather than a small
  demo-only patch.
- Decision: accepted by the project owner on 2026-07-26.

### C. Keep the current methodology unchanged

- Positive: zero implementation risk.
- Negative: preserves adoption friction and slow feedback despite a concrete external
  reference and an explicit owner request.
- Decision: rejected.

## Decision

Implement the following sequence with WIP=1:

1. conditional context modules in `/adopt`;
2. a captured-run schema and clean-temp replay harness;
3. a PIV-lite brownfield façade inside `/task`, with no new lifecycle skill;
4. a captured reproducible brownfield example produced through that façade;
5. an opt-in incremental diagnostic pilot with latency/noise telemetry;
6. a host-native fresh-session/worktree recipe and three real brownfield pilot runs;
7. a demand gate and, only when activated, a multi-language semantic-navigation
   capability contract;
8. exact-candidate verification, host parity, meta-review, and full regression.

The implementation must preserve these invariants:

- no ITD-owned scheduler, daemon, or Ralph runtime;
- no Markdown or sentinel file becomes authoritative state;
- no new public lifecycle skill;
- the staged exact candidate and current Verification Loop remain the only completion
  authority;
- isolation failure blocks unattended mutation instead of falling back to a shared
  mutable resource;
- pilots and internal examples never count as external adoption evidence.

## Consequences

### Positive

- Faster time to first verified brownfield change.
- Less irrelevant context and fewer speculative code reads.
- Earlier diagnostics without weakening the final oracle.
- A legible onboarding story backed by real receipts.
- Structured navigation can use LSP, tree-sitter, or host-native providers instead of
  a bundled Python-only server.

### Negative

- `/adopt` gains another generated artifact family and freshness responsibility.
- Incremental diagnostics add hook latency and require strict budgets.
- The worktree pilot needs isolated mutable resources and cannot be proven by fixtures
  alone.

### Risks and rollback

- If context modules become stale or duplicate `.itd`, disable generation and keep the
  index as a derived view only.
- If diagnostic median latency or false-noise exceeds the sealed threshold, keep the
  profile default-off or remove it.
- If any worktree pilot shares a mutable resource, mark the pilot failed and do not
  promote the recipe.
- If semantic providers cannot declare language coverage and degradation, retain plain
  text search as the honest fallback.
