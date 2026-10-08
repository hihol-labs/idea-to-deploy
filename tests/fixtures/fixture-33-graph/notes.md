# Fixture 33 — /graph — manual verification notes

`/graph` is Graph Lite: one explicit agent graph per task, designed, approved,
run and recorded as files. It is a measured exception to ADR-012 (ADR-013), so
its contract is deliberately narrow:

- **DESIGN** — `skills/graph/scripts/itd_graph.py init` writes
  `.itd-memory/graph-runs/<run-id>/graph.json` from a template and prints the
  graph digest; `validate` is a pure validator (DAG, one human terminal,
  read-only nodes, checker separate from writer). Covered by
  `tests/verify_graph_skill.py`, NOT manual.
- **APPROVE** — the owner approves the exact digest (`approve --digest`); a
  changed graph invalidates the approval. Script-checked.
- **RUN** — the host runs the graph (`emit-workflow` prints the Workflow tool
  script; `emit-serial` prints the serial plan for a host without a workflow
  runtime). The model part is manual: see the contract below.
- **RECORD / CLOSE** — `record` writes one file per node plus `receipt.json`;
  `close` stores the human decision. Script-checked.

Validation of the model part deferred (status: contract) — same read-and-advise
bucket as fixture-15-advisor / fixture-19-grill-me: the snapshot schema cannot
assert a design → approval → run → decision dialogue.

## Contract to verify manually

`/graph` MUST:
- Be invoked explicitly (`/graph ...`); it carries `disable-model-invocation: true`
  and never auto-routes — default-off is the whole point of ADR-013.
- Write the graph to `.itd-memory/graph-runs/<run-id>/graph.json` BEFORE running
  anything, print the digest, and STOP until the owner approves that digest.
- Refuse to run a graph whose digest differs from the approved one
  (re-approval required after any edit).
- Instruct every node to stay read-only (no Edit/Write to project sources, no git
  mutation, no deploy, no network) and write only under the run directory itself.
  The run tool backs this contract (Explore agent type, git-state check at
  `record`) but is not a sandbox: git-ignored files, `.itd-memory/`, harness
  telemetry and network use are not detected.
- Keep the human as the terminal node: the synthesized findings are presented,
  the human decides, and `close` records the decision — the skill never
  "accepts" its own findings.
- Degrade to the serial plan (`emit-serial`) when the host has no Workflow tool
  or the run fails mid-way; a missing node output is a refused `record`, never a
  green run.
- Record one file per node under `nodes/` plus `receipt.json` with the graph
  digest and per-node sha256, so the run is reproducible and comparable.
- Run every node as the `Explore` subagent type and refuse `record` when the
  project's git state differs from the state stored at approval.
- Keep every run under `.itd-memory/graph-runs/<run-id>/` (no symbolic links),
  refuse node outputs that break their schema, and refuse to close a run whose
  node files no longer match the receipt.

`/graph` MUST NOT:
- Mint `verified`, replace `/review`, `/test`, the Verification Loop or any human
  gate (deploy, push, PR, migration, money).
- Add nodes that mutate state in this version (`purity: read-only` is enforced
  by the validator).
- Run without an approved digest or re-use an approval after the graph changed.
- Become default-on: that needs a won A/B measurement of the same kind as
  `~/projects/itd-value-exp` (ADR-013, pre-registered rule).
