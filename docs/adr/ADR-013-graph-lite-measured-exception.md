# ADR-013: Graph Lite - one measured, default-off exception to ADR-012 item 5

- **Status:** accepted (owner decision 2026-10-07: variant A+B of the three offered; the skill ships default-off and
  stays so until it wins the measurement in item 6)
- **Amends:** [ADR-012](ADR-012-minimal-path-default.md) item 5 ("methodology development stops") for exactly one
  thing: the `/graph` skill and its first template. Does not touch ADR-012 items 1-4 and 6-8,
  [ADR-001](ADR-001-no-own-runtime.md) (no owned runtime), [ADR-009](ADR-009-graph-contract-layer.md) (its
  invariants are kept; its program stays NO-GO) or [ADR-011](ADR-011-default-risk-tier-low.md).

## Context

The owner asked to "implement graph engineering" after the explainer by Greg Isenberg ("Why Graph Engineering will
10x your Claude/Codex", 2026-08-03, youtube JWhICz1QR8M). The talk is conceptual: a graph is jobs connected by arrows
with shared state; an agent graph routes work between a planner, parallel researchers, a skeptic, a synthesizer and a
human; a graph is reserved for work with several steps, sources, parallel paths, checks, risks or approvals; the
writer is separated from the checker; "aim for the smallest graph that raises quality" and put the human gate where
mistakes get expensive; level 1 is a drawing, level 2 is Claude Code or Codex where every step writes its own file,
level 3 is LangGraph or n8n. Its coding graph (plan -> edit -> review the diff -> run tests -> check the UI -> hunt
edge cases -> human approves the PR) is the existing ITD route node for node; `docs/graph-engineering.md` maps it.

Three facts bound the decision:

1. Two graph ideas already lost their measurement. ADR-009 GATE G0 (2026-08-22): a cache of node receipts would save
   a median of 0.00 minutes per unit over 134 units - NO-GO. GENG-C-EXP (2026-08-28): a quorum of parallel reviewers
   on one candidate removed no false PASSED - stop. Neither measured what a graph could do for defects.
2. ADR-012 item 5 stops methodology development: a change is allowed only when it blocks product work, and a new
   check becomes mandatory only after it wins a measurement of the same kind as `~/projects/itd-value-exp`.
3. That measurement left one measured gap: 8 of the 16 seeded defects sat in NEIGHBOURING functions of the module
   (owner and access checks, an empty currency, a dedup window, a 24-hour boundary) and both arms missed all 8,
   because a diff review does not look there by construction. ADR-012 item 6 answered with a one-line class check in
   the neuroexpert CLAUDE.md, item 7 with a 30-day leak journal (2026-10-07..2026-11-05).

The host ships a graph runtime of its own (the Workflow tool: `agent`, `parallel`, `pipeline`), unused by ITD so
far. Per ADR-001 and the harness best-effort invariant it may TRANSPORT a graph; it may not BE the contract.

## Decision

1. **One skill, `/graph` (Graph Lite).** It turns ONE task into an explicit agent graph kept as files under
   `.itd-memory/graph-runs/<run-id>/`: `graph.json` (nodes, edges, shared state, prompts, output schemas),
   `approval.json`, `nodes/<id>.md`, `receipt.json`, `decision.json`. `skills/graph/scripts/itd_graph.py` is its
   deterministic half (init, validate, approve, emit-workflow, emit-serial, record, close, status); it never runs a
   model, never edits sources and never uses the network.
2. **Default-off.** The skill carries `disable-model-invocation: true` and `explicit_invocation: true`: no hook
   trigger, no auto-routing, no mention in the minimal path. It runs only when the owner types `/graph`.
3. **Invariants kept from ADR-009, now enforced by code.** A proposal is not an authorization: the owner approves the
   exact `graphDigest` (sha256 of the canonical graph) and any later edit makes the approval stale. Every non-human
   node is read-only in this version: the validator rejects `purity != read-only`, a prompt without the read-only
   clause, a graph without a checker node, a checker that checks itself or a node it is not wired to, a cycle, more or
   fewer than one human terminal, and a node that never reaches the human. At run time read-only stays a contract
   backed by two mechanisms, and Graph Lite is not a sandbox: both emitters run every node as the `Explore`
   subagent type (no Edit, Write or NotebookEdit tools; shell and network access stay with the host and its hooks),
   and `approve` stores the project's git state (HEAD plus every changed or untracked path with a content hash) so
   that `record` refuses a change to any git-visible project file. Not detected: git-ignored files, `.itd-memory/`,
   harness telemetry, anything outside the project and network use. A project outside git cannot be approved. The run directory is confined to `.itd-memory/graph-runs/<run-id>`
   without symbolic links; `record` checks every node output against its schema and writes atomically; `close`
   and `status` re-verify the approval and every node file. The human is the only terminal node; `close` records
   the decision. No graph mechanism mints `verified`; `/graph` replaces no gate.
4. **Transport, not contract.** `emit-workflow` prints a Workflow tool script that runs the approved graph layer by
   layer (parallel inside a layer, a barrier between layers, a null node output throws); `emit-serial` prints the
   same graph as an ordered plan for a host without a workflow runtime (Codex, a refused tool, a failed run). A
   missing node output is a refused `record`, never a green run.
5. **One shipped template, `module-neighbour-check`,** aimed at the measured gap: four hunters, one per class of
   ADR-012 item 6 (owner or empty id, currency and amount, dedup and idempotency, time boundaries), read the WHOLE
   module in parallel; a skeptic tries to refute every finding (refuted by default); a synthesizer dedups, ranks and
   drafts the leak-journal line; the human decides and writes the line. The template is the candidate "targeted
   check" of ADR-012 item 7, nothing more.
6. **Pre-registered decision rule (fixed before any run; same shape as `itd-value-exp`).** Arm G:
   `/graph module-neighbour-check` on a money or access module of the frozen neuroexpert base with seeded defects in
   a sealed manifest. Arm K: the one-line class check of the neuroexpert CLAUDE.md, run by one fresh agent on the
   same module. Fresh subagent executors, no commits. Metric: the catch rate of seeded defects in neighbouring
   functions of the module (defects in the task's own function are reported separately and do not enter the rule).
   Cost: median duration and tokens G/K. At least 4 modules, each pair in both orders. The template becomes
   default-on for money and access tasks (a line in the project CLAUDE.md, still not a gate) only if the catch-rate
   gain is >= 0.25 AND the median duration ratio G/K is <= 3.0. Otherwise it stays default-off, or is removed if the
   owner says so. The protocol file, the seeder and the scorer follow `~/projects/itd-value-exp`
   (BACKLOG "Graph Lite (ADR-013): замер", sessions 2-3).
7. **Scope of the exception.** This record permits exactly: `skills/graph/`, `tests/verify_graph_skill.py`,
   `tests/fixtures/fixture-33-graph/`, `docs/graph-engineering.md`, this ADR and the amended-by note in ADR-012; the
   count and registration edits a new skill needs (manifests, READMEs, the CLAUDE.md template, the harness map and
   docs state, CONTRACTS, count prose, the absorption contract with its digest and test); the wiring of the new suite
   (`tests/run-all.sh`, `.github/workflows/windows-verify.yml`, the regenerated `.itd/IMPACT_GRAPH.json`); the records
   of the decision (`CHANGELOG.md`, `.itd/DECISIONS.md`, `BACKLOG.md`); the publication contracts of this candidate
   (`.itd/SCOPE_LOCK.md`, the `activeFollowup` and two criteria in `.itd/ACCEPTANCE_CONTRACT.json`); and the
   live-model evidence re-recorded on the new methodology tree. Everything else stays under ADR-012 item 5.

## Consequences

- The owner gets graph engineering in the form the talk recommends for level 2: a drawn graph, every step a file, the
  human gate at the expensive step - without a runtime of ITD's own and without touching the minimal path.
- The skill is a measurement instrument first: every run leaves `receipt.json` and per-node files that the protocol
  of item 6 can score. Until the rule of item 6 is met, nobody is asked to use it.
- Cost of the record: 41 skills to keep registered (the count drift guards), one more suite in CI, the live-benchmark
  evidence re-recorded once.
- Not covered: mutating nodes, per-node model routing, a cache of node receipts (ADR-009 B stays NO-GO), graphs that
  span several tasks or sessions.

## Rejected

- **A graph runtime or scheduler owned by ITD, or the graph as a replacement for the route** (variant C):
  contradicts ADR-001, ADR-009 and ADR-012 and both NO-GO verdicts.
- **A documentation-only answer** (variant B alone): the owner chose A+B; the map alone cannot test the one measured
  gap.
- **Hook triggers on "graph engineering" phrases:** would make the skill opt-out instead of opt-in and reopen the
  skill-hint friction ADR-012 removed.
- **Reusing the GENG-A/B contract layer** (schemas, dual digest, node receipt cache): its value was not shown
  (GATE G0); Graph Lite keeps one digest, one approval and one receipt per run.
