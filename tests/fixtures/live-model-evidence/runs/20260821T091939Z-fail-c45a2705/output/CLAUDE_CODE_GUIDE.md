# Claude Code Implementation Guide: nginx-insight

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts for future
implementation sessions. It does not authorize changing the approved
architecture or implementing multiple steps at once. Read `PRD.md` and
`PROJECT_ARCHITECTURE.md` before each prompt, keep WIP=1, update the Idea to
Deploy scope/state for the active unit, and preserve existing user work.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, dataclasses, pip packaging.
- One local process; stateless streaming; never retain raw input or all records.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Fixed top 10 with deterministic count-descending/key-ascending ties.
- Hourly percentages use
  `100 × hourly_request_count / total_valid_requests`.
- stdout contains only the selected report; diagnostics use stderr.
- The complete exit-code contract is: `0` success, `1` unexpected
  internal/runtime failure, `2` CLI usage/validation error, `3` input
  open/read/decode or zero-valid-record failure, and `4` unique-cardinality
  exhaustion. Never omit or remap code 4; never emit a partial report on 4.

## Prompt 1 — Package Skeleton

> Execute only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11
> package/build skeleton and smoke tests named there. Do not implement parsing
> or analytics. Run every Step 1 verification command, record actual evidence,
> and stop with the Idea to Deploy state handoff-ready.

## Prompt 2 — Typed Parser

> Execute only Step 2 of `IMPLEMENTATION_PLAN.md`. Implement the exact nginx
> combined-format input and dataclass contract in `PROJECT_ARCHITECTURE.md`,
> including IPv4, IPv6, escaped quoted fields, query strings, `-`, and malformed
> records. Process one line at a time. Run the specified parser, lint, and type
> checks and record evidence before ending.

## Prompt 3 — Streaming Analytics

> Execute only Step 3 of `IMPLEMENTATION_PLAN.md`. Implement all four exact
> metrics, fixed top-10 deterministic ranking, 24 hourly bins, and the literal
> percentage formulas from the PRD. Do not add renderers. Run the aggregate and
> coverage checks and reconcile Idea to Deploy state.

## Prompt 4 — Error Semantics

> Execute only Step 4 of `IMPLEMENTATION_PLAN.md`. Implement typed domain
> failures and integration tests for the complete exit contract `0/1/2/3/4`.
> Force the unexpected-failure path safely in a test; prove code 4 writes no
> partial stdout. Do not weaken malformed-line tolerance. Run and record every
> specified check.

## Prompt 5 — Terminal Renderer

> Execute only Step 5 of `IMPLEMENTATION_PLAN.md`. Implement the Rich terminal
> renderer in the specified files. Preserve renderer separation, safe escaping,
> ordered sections, automatic non-TTY color suppression, and `--no-color`.
> Run the terminal tests and a fixture smoke command.

## Prompt 6 — JSON and CSV

> Execute only Step 6 of `IMPLEMENTATION_PLAN.md`. Implement the exact JSON 1.0
> and long-form CSV contracts from `PROJECT_ARCHITECTURE.md`. Keep percentages
> numeric, diagnostics on stderr, flags mutually exclusive, and row ordering
> deterministic. Run format parsing and equivalence checks.

## Prompt 7 — End-to-End Acceptance

> Execute only Step 7 of `IMPLEMENTATION_PLAN.md`. Add integration and golden
> tests mapping every P0 user story and each exit code `0/1/2/3/4` to evidence.
> Do not regenerate expected values from the implementation under test. Run the
> full coverage, lint, and type commands; address only in-scope failures.

## Prompt 8 — Performance Evidence

> Execute only Step 8 of `IMPLEMENTATION_PLAN.md`. Add the deterministic
> untracked 1 GB generator and benchmark procedure. Record hardware, software,
> cache conditions, elapsed wall time, peak RSS, and correctness. Profile before
> optimizing; do not introduce multiprocessing, persistence, or approximation
> without first changing the architecture/spec and obtaining approval.

## Prompt 9 — Distribution Gate

> Execute only Step 9 of `IMPLEMENTATION_PLAN.md`. Complete user documentation,
> build wheel and sdist, validate metadata, install the wheel into a clean
> temporary Python 3.11 environment, and smoke-test the command. Freeze the
> exact candidate and run the repository's machine oracle plus risk-tier
> checker. Accept only a current revalidated adjudication receipt.

## Verification Discipline

For every prompt:

1. Confirm the step's allowed paths in `.itd/SCOPE_LOCK.md` before edits.
2. Add or update tests before or with behavior changes.
3. Run the exact step checks; do not replace execution with predicted results.
4. Keep benchmark fixtures and build artifacts out of version control.
5. Record failures as recovery work, never as success.
6. Stop after one step with changed files, test evidence, risks, and next action explicit.

The external Devil's Advocate workflow is not a substitute for these machine
checks and is not invoked by this guide.
