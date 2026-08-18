# Claude Code Implementation Guide: Nginx Insights CLI

Use this guide only after the blueprint is approved for implementation. Work
one numbered prompt at a time, in the order shown, and treat `PRD.md` plus
`PROJECT_ARCHITECTURE.md` as the durable source of truth. Do not add a database,
HTTP API, authentication, server, cloud service, Docker, or Kubernetes.

## Session Start Prompt

> Read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and
> `IMPLEMENTATION_PLAN.md`. Identify the single active step from the status
> table. Restate its acceptance criteria and verification commands. Preserve
> one-pass processing, Python 3.11 compatibility, and runtime dependencies
> limited to Click and Rich. Do not work on later steps.

## Prompt 1 — Package and public contracts

> Implement Step 1 of `IMPLEMENTATION_PLAN.md` only. Create the package skeleton,
> frozen result/error contracts, development tooling, fixtures, and console
> entry point. Keep callbacks free of business logic. Run all Step 1 verification
> commands and record real results before marking the step complete.

## Prompt 2 — Streaming parser

> Implement Step 2 only. Parse the exact Combined Log Format contract from
> `PROJECT_ARCHITECTURE.md`; stream from file or stdin and never retain raw
> input. Cover escaped data, IPv4/IPv6, timestamp offsets, request targets,
> undecodable input, and malformed records. Run focused parser/input tests,
> Ruff, and mypy, then the existing suite.

## Prompt 3 — Ranked aggregation

> Implement Step 3 only. In one pass, count all valid requests by IP and only
> 400–599 requests by target. Final ranking is count descending, then key
> ascending, limited to ten. Do not render inside aggregation. Prove boundary
> statuses, deterministic ties, and more-than-ten cases with tests.

## Prompt 4 — Percentages and cardinality

> Implement Step 4 only. Emit all hours `00`–`23`; define each percentage as
> `100 × hourly_request_count / total_valid_requests`. Track exact User-Agent
> strings and check the positive configured limit before adding a new distinct
> value. Exhaustion must emit no partial structured result, reveal no sensitive
> value, and map only to exit code 4. Run all focused and prior tests.

## Prompt 5 — Terminal output

> Implement Step 5 only. Build the canonical ordered result representation and
> render its four metric families through Rich. Respect TTY detection and
> `--no-color`. Use escaping appropriate to Rich. Add and verify a stable
> no-color golden fixture; do not duplicate calculations in the renderer.

## Prompt 6 — JSON, CSV, and CLI behavior

> Implement Step 6 only. Render JSON and CSV from the same canonical result,
> enforce mutually exclusive format options, implement permissive/strict parse
> behavior, keep diagnostics on stderr, and handle broken pipes. Exercise the
> complete exit contract `0/1/2/3/4`, including unique-cardinality exhaustion as
> 4. Validate JSON syntax and structured-output ANSI absence.

## Prompt 7 — Integration and packaging

> Implement Step 7 only. Prove semantic parity across terminal-model, JSON, and
> CSV paths; run Ruff, mypy, branch coverage, and packaging tests; build a wheel
> and smoke-install it in a clean Python 3.11 environment. Update documentation
> to match observed behavior, not intended behavior. Do not publish externally.

## Prompt 8 — Performance acceptance

> Implement Step 8 only. Generate the fixed-seed representative 1 GB fixture,
> record machine/input metadata, elapsed time, and peak RSS, and run the command
> with output redirected. If it misses 30 seconds, profile before changing code;
> rerun correctness after each optimization. Record honest evidence and apply
> the kill criteria in `PRD.md`.

## Review Prompt After Each Step

> Review only the current step's diff against its PRD stories, architecture
> boundaries, and verification commands. Look for retained input, unstable tie
> ordering, locale-dependent output, partial JSON/CSV on failure, status-boundary
> errors, leaked User-Agent values, and exit-code drift. Do not expand scope.
> Report concrete file/line findings and rerun the current and cumulative tests.

## Complete Exit-Code Contract

Every implementation and review prompt must preserve this exact mapping:

| Code | Meaning |
|---:|---|
| `0` | Success/help/version/graceful downstream broken pipe |
| `1` | Runtime, input I/O, read, or output failure |
| `2` | CLI usage/configuration failure |
| `3` | Strict malformed input, empty input, or no valid requests |
| `4` | Unique-cardinality exhaustion before exceeding the configured limit |

The contract is `0/1/2/3/4`. Never omit or remap code 4.

## Session End Prompt

> Run the active step's verification commands and the cumulative suite. Update
> the status table in `CLAUDE.md` from evidence only, note files changed and any
> remaining risk, and save context through `/session-save`. Leave exactly one
> explicit next action; do not mark later steps complete.

