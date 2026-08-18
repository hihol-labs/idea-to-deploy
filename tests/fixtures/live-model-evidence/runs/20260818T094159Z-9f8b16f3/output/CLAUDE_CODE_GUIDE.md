# Claude Code Implementation Guide: Nginx Stream Insights

Use these prompts sequentially, one active step at a time. Before each step, read `PROJECT_ARCHITECTURE.md`, `PRD.md`, `IMPLEMENTATION_PLAN.md`, `CLAUDE.md`, and the current `.itd/` contracts. Update the specification first if behavior must change. Never add authentication, a database, HTTP API, server, cloud, or Kubernetes.

The complete exit-code contract applies to every step: `0` success; `1` internal/runtime processing failure; `2` CLI usage/validation error; `3` missing, unreadable, invalid, or failed input; `4` unique-cardinality exhaustion. Code 4 must remain distinct and must never be omitted or remapped.

## Prompt 1 — Package and CLI Contracts

> Implement Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src/` package, Click console entry point, dependency/test metadata, typed error foundation, and install/help tests using the exact paths in the plan. Preserve the CLI and `0/1/2/3/4` contracts in `PROJECT_ARCHITECTURE.md`; code 4 means unique-cardinality exhaustion even before its trigger is implemented. Do not implement metrics yet. Run the listed checks, record actual evidence, and stop after Step 1 is handoff-ready.

## Prompt 2 — Parser and Models

> Implement Step 2 only. Add the specified dataclasses and combined-log parser with timezone-aware timestamps, request-target extraction, and explicit malformed results. Use a compiled parser and do not read whole files. Add domain-specific fixtures/tests, run the Step 2 checks, and preserve all five exit-code meanings (`0/1/2/3/4`, with 4 reserved for unique-cardinality exhaustion).

## Prompt 3 — Streaming Aggregation

> Implement Step 3 only. Stream files/stdin in order, update top-IP, 4xx/5xx URL, 24-hour, and exact User-Agent aggregates in one pass, and finalize deterministic top tens. Hour percentages must use `100 × hourly_request_count / total_valid_requests`. Keep memory independent of line count except exact distinct-value state. Add and run the planned tests. Maintain exit codes `0/1/2/3/4`; code 4 means unique-cardinality exhaustion.

## Prompt 4 — Rich Text

> Implement Step 4 only. Render the shared report dataclass as labeled Rich terminal sections, suppress color when redirected or on `--no-color`, and keep diagnostics on stderr. Add TTY/non-TTY integration tests and run the plan's checks. Do not alter metric semantics or the complete `0/1/2/3/4` contract; 4 remains unique-cardinality exhaustion.

## Prompt 5 — JSON and CSV

> Implement Step 5 only. Add deterministic JSON and RFC 4180 long-form CSV renderers with the exact schemas and ordering in the architecture. Make `--json` and `--csv` mutually exclusive, ensure no ANSI/diagnostics enter stdout, and protect CSV consumers from formula injection according to the documented policy. Add golden tests and run the checks. Preserve `0/1/2/3/4`; code 4 means unique-cardinality exhaustion.

## Prompt 6 — Exit and Cardinality Boundaries

> Implement Step 6 only. Enforce a positive `--cardinality-limit` before inserting a new distinct value, complete typed failure mapping, and add integration coverage for every code: `0` success, `1` internal/runtime failure, `2` usage, `3` input failure, `4` unique-cardinality exhaustion. Ensure failed JSON/CSV produces no partial stdout and broken pipes do not show tracebacks. Run the listed checks and attach actual results.

## Prompt 7 — Performance

> Implement Step 7 only. Build deterministic fixture-generation and benchmark tools under `tests/performance/`, record the required environment metadata, and measure the real production streaming path on a 1 GB fixture. Profile before optimizing and preserve exact metric/schema behavior. The gate is under 30 seconds on the documented laptop. Re-run correctness and `0/1/2/3/4` exit tests after optimization; code 4 remains unique-cardinality exhaustion.

## Prompt 8 — Release Candidate

> Implement Step 8 only after Steps 1–7 are green. Finish verified installation/release documentation and package checks without adding services or persistence. Run the full suite and package validation. Freeze the exact staged candidate, execute the machine oracle, and apply the `.itd/` risk-tier checker; accept only a current revalidated adjudication receipt. Confirm the public `0/1/2/3/4` contract, where 4 means unique-cardinality exhaustion. Reconcile state and leave the next action explicit.

## Optional Prompt 9 — Gzip

> Only if every MVP gate passes and time remains, implement P1 Step 9. Stream valid `.gz` logs through the existing input/parser path and map corrupt gzip input to code 3. Keep all output schemas and `0/1/2/3/4` unchanged; code 4 still means unique-cardinality exhaustion. Run gzip-specific and full regression checks.

## Per-Step Evidence Template

After each prompt, report:

1. Scope completed and files changed.
2. Exact commands run with exit status and meaningful output summary.
3. Acceptance criteria demonstrated, including relevant exit codes.
4. Unresolved risks or `RECOVERY_REQUIRED`; never infer success from prose.
5. Updated `.itd-memory/` state and the next single active step.

Do not claim release completion from a standalone test pass. Follow the current Idea to Deploy Verification Loop and its exact-candidate receipt requirements.
