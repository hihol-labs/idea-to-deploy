# Fixture 33 — /graph

The owner saw the "graph engineering" explainer (Greg Isenberg, 2026-08) and
asked for it in idea-to-deploy. Two earlier graph ideas lost their measurement
(ADR-009 GATE G0: node receipt cache, 0 minutes saved per unit; GENG-C-EXP:
parallel reviewer quorum, no gain), and ADR-012 stopped methodology work. So the
skill is a MEASURED EXCEPTION (ADR-013): default-off, explicit invocation only,
read-only nodes, the human is always the terminal node, and it stays default-off
until it wins an A/B measurement of the same kind as `itd-value-exp`.

Sample prompts that should route here (explicit invocation only — the skill
carries `disable-model-invocation: true`, so nothing routes here on its own):
- "/graph module-neighbour-check --module packages/shared/src/billing/limits.ts"
- "/graph построй граф проверки модуля биллинга по четырем классам"
- "/graph design a task graph for this review and let me approve it"

Expected behavior: `/graph` turns ONE task into an explicit agent graph (jobs,
arrows, shared state, a checker separate from the writer, a human terminal),
writes it to `.itd-memory/graph-runs/<run-id>/graph.json`, prints its digest and
WAITS for the owner to approve exactly that digest. Only then does it emit the
host workflow script (or the serial plan when the host has no workflow
runtime), run it, record every node output as its own file under `nodes/`, and
hand the synthesized findings to the human, who closes the run with a decision.
The first and only shipped template is `module-neighbour-check`: four class
hunters (owner/empty id, currency and amount, dedup/idempotency, time
boundaries) read the WHOLE module in parallel, one skeptic tries to refute every
finding, one synthesizer dedups and ranks them with `file:line`, the human
decides and writes the line into the project's leak journal.
