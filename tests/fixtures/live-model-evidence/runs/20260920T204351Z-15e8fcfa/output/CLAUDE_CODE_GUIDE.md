# Claude Code Implementation Guide: nginx-insights

Use this guide only after the blueprint is approved. Work in the numbered order from `IMPLEMENTATION_PLAN.md`, keep WIP=1, and stop after each gate for review. The specifications—not generated code—are the source of truth.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, dataclasses, `src/` packaging, and pip installation.
- One local process, one-pass input, no whole-file read, no network or persistence.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Required metrics: top-10 IPs, top-10 normalized URL paths for 4xx/5xx, 24 hourly percentages, and unique User-Agent share.
- Hourly percentages use exactly `100 × hourly_request_count / total_valid_requests`.
- Exit codes are complete and fixed: `0` success; `1` unexpected internal failure; `2` usage or input I/O error; `3` parse-quality failure; `4` unique-cardinality exhaustion.
- JSON and CSV are machine contracts on stdout; diagnostics go to stderr; neither contains ANSI escapes.
- Do not silently approximate, sample, discard cardinality, or change a required formula.

## Session Prompt

Use this at the beginning of every implementation session:

> Read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md`. Identify the single active step in `CLAUDE.md`; do not start a second step. Reconcile existing changes before editing. Implement only that step with its tests, run every verification command listed for it, and report actual evidence and remaining risks. Do not claim completion from narration. Do not create `DEVILS_ADVOCATE_REVIEW.md`; that artifact belongs to the external harness.

## Step 1 Prompt — Package and CLI Contracts

> Execute only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src` package, console entry point, Click help/version surface, and initial contract tests. Do not implement parsing or metrics. Ensure `--json` and `--csv` conflict through validated CLI behavior. Run the three Step 1 verification commands and update the status table in `CLAUDE.md` only from observed results.

Expected evidence: editable install succeeds, contract tests pass, and installed help is displayed.

## Step 2 Prompt — Parser and Models

> Execute only Step 2. Implement typed dataclasses and a parser for the supported nginx common/combined formats defined in `PROJECT_ARCHITECTURE.md`. Cover IPv4, IPv6, timestamps with offsets, quoted/escaped fields, dashes, malformed lines, request decomposition, and query removal. Compile parsing machinery once. Do not add aggregation or rendering. Run both Step 2 verification commands.

Expected evidence: parser tests and parser-specific coverage gate pass.

## Step 3 Prompt — Streaming Input

> Execute only Step 3. Implement file/stdin iteration and typed failures. Prove file and stdin parity and prove the implementation never requests an unbounded/full read. Keep raw log input local and do not persist it. Run all Step 3 checks.

Expected evidence: input/streaming tests and input-error CLI contract pass.

## Step 4 Prompt — Exact Aggregation

> Execute only Step 4. Implement one-pass exact aggregation over parsed records. Error URLs include statuses 400–599 and path only. Rankings sort by descending count then ascending label. Include all 24 hours and compute `100 × hourly_request_count / total_valid_requests`; compute User-Agent share only over valid requests with non-null User-Agent. Do not render output yet. Run both Step 4 checks.

Expected evidence: aggregation boundary, tie, denominator, and coverage checks pass.

## Step 5 Prompt — Limits and Exit Codes

> Execute only Step 5. Enforce the positive per-dimension cardinality ceiling at the documented boundary, implement strict malformed behavior, and map typed failures to exactly `0/1/2/3/4`. Tests must exercise all five codes and prove normal stdout is suppressed for codes 2, 3, and 4. Never turn cap exhaustion into a partial-success report. Run both Step 5 checks.

Expected evidence: all exit-code branches and all three cardinality dimensions are tested.

## Step 6 Prompt — Renderers

> Execute only Step 6. Render the shared report model as Rich terminal tables, stable JSON, and RFC-compatible long-form CSV. Sanitize terminal control characters, keep diagnostics off stdout, use no ANSI in machine formats, and apply documented two-decimal output rounding without recalculating metrics. Run renderer tests and JSON parsing smoke check.

Expected evidence: golden outputs, hostile-label cases, and JSON validity pass.

## Step 7 Prompt — End-to-End CLI

> Execute only Step 7. Wire all components and options without duplicating domain calculations in the CLI. Add end-to-end tests for path/stdin parity, each output mode, strict/non-strict malformed input, deterministic ties, pipes, and all exit conditions. Run every Step 7 verification command.

Expected evidence: installed or module-invoked end-to-end behavior matches the PRD.

## Step 8 Prompt — Performance and Quality

> Execute only Step 8. Create deterministic benchmark tooling, keep generated gigabyte data outside version control, and record baseline machine details, wall time, throughput, and peak RSS. Profile before optimizing. Any optimization must retain byte-equivalent JSON/CSV or semantically equivalent terminal golden results. Run the 1 GB/30-second oracle and full 90% coverage gate.

Expected evidence: current benchmark record and complete green suite; estimates are not evidence.

## Step 9 Prompt — Release Readiness

> Execute only Step 9. Reconcile documentation with observed behavior, build wheel and sdist, validate metadata, inspect package contents, and install the wheel in a fresh Python 3.11 environment. Run the full suite and all packaging smoke checks. Do not publish externally unless separately authorized.

Expected evidence: tests/coverage, build, artifact validation, and clean-environment command smoke test all pass.

## Review Checklist

- [ ] P0 acceptance criteria in `PRD.md` map to tests.
- [ ] Parser rejects unsupported input explicitly rather than guessing.
- [ ] Exact cardinality cap has boundary tests and code 4 behavior.
- [ ] Terminal, JSON, and CSV consume one report model.
- [ ] Output is deterministic and locale-independent.
- [ ] The 1 GB benchmark excludes fixture generation and rendering overhead is controlled.
- [ ] Wheel install is tested, not inferred from an editable install.
- [ ] No prohibited service, storage, network, or deployment component was introduced.

## Recovery Rules

If a verification command fails, leave the active step in progress, record the failure and recovery action, and rerun the smallest relevant check before the full step gate. If implementation reveals a contract defect, update the PRD/architecture deliberately before code; do not quietly make code the source of truth.
