# Claude Code Guide: nginx-log-top

Use these prompts sequentially after the blueprint is approved. Each prompt authorizes only one implementation-plan step. Preserve WIP=1, read `AGENTS.md` and `.itd/` first, update specs before changing behavior, and attach command evidence rather than asserting success.

## Step 1 Prompt

> Execute Implementation Plan Step 1 only. Create the Python 3.11 packaging and CLI contract skeleton at the listed paths. Do not implement metrics. Add tests first for help, version, invocation, and conflicting output flags. Freeze the exact candidate and run the repository's required verification plus the step commands. Reconcile `.itd-memory/STATE.json` with evidence and stop.

## Step 2 Prompt

> Execute Implementation Plan Step 2 only. Define the frozen dataclasses and synthetic supported fixtures exactly as specified by PROJECT_ARCHITECTURE.md. Do not add parsing or I/O. Verify model invariants and compileability, record outputs, reconcile state, and stop.

## Step 3 Prompt

> Execute Implementation Plan Step 3 only. Implement the documented combined-log parser and expected error types using test-first red/green evidence. Cover every listed parser edge case; do not aggregate or render. Run the step verification and methodology gate, reconcile state, and stop.

## Step 4 Prompt

> Execute Implementation Plan Step 4 only. Implement one-pass exact aggregation with deterministic ties and all 24 hour buckets. Add a test that detects eager input materialization. Do not add output renderers. Run the listed tests/static checks and exact-candidate verification, reconcile state, and stop.

## Step 5 Prompt

> Execute Implementation Plan Step 5 only. Complete file/stdin lifecycle, diagnostics, exit codes, broken-pipe behavior, and stdout/stderr separation. Keep behavior identical to the CLI Interface contract. Prove each terminal condition in tests, run verification, reconcile state, and stop.

## Step 6 Prompt

> Execute Implementation Plan Step 6 only. Implement the Rich terminal renderer, TTY/NO_COLOR behavior, diagnostics, and markup escaping. Use golden tests without making them brittle to terminal width. Run verification, reconcile state, and stop.

## Step 7 Prompt

> Execute Implementation Plan Step 7 only. Implement schema-versioned JSON and normalized CSV exactly as documented. Ensure deterministic, ANSI-free output and no partial output for known failures. Run golden/parser checks and the exact-candidate gate, reconcile state, and stop.

## Step 8 Prompt

> Execute Implementation Plan Step 8 only. Add deterministic benchmark generation, end-to-end/performance smoke tests, release documentation, license, and packaging evidence. Run the full suite, static checks, build/install smoke test, and the hashed 1 GB benchmark on a declared environment. Do not claim the <30 s target without actual elapsed/RSS output and a current adjudication receipt. Reconcile final state and stop.

## Review Prompt

> Review the current exact candidate against PRD P0 criteria and PROJECT_ARCHITECTURE.md. Confirm there is no database, HTTP listener, auth, cloud, Docker/Kubernetes requirement, or hidden whole-file read. Check unsafe terminal markup, deterministic ties, machine schemas, and performance evidence. Return findings ordered by severity with paths/lines, then run the required acceptance gate.

## Working Rules

- `PRD.md` is the behavioral source of truth; architecture controls component boundaries.
- Never combine plan steps without explicit scope reclassification.
- Do not add dependencies beyond Click, Rich, and development tooling without an ADR.
- Do not weaken exact semantics or performance fixtures to make tests pass.
- At the end of every session or meaningful block of work, save context through `/session-save`.
