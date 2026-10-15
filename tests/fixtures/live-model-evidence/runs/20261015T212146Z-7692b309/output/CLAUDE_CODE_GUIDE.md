# Claude Code Guide: nginx-stream-report

## Purpose and Guardrails

Use this guide to implement one step from `IMPLEMENTATION_PLAN.md` at a time. Before editing, read `PROJECT_ARCHITECTURE.md`, the matching PRD requirements, and the current step. Do not implement deferred P1/P2 work while a P0 step is active.

Non-negotiable constraints:

- Python 3.11, Click, Rich, dataclasses, pip-installable `src` layout.
- One local process; no database, HTTP API, server, authentication, cloud, Docker, or Kubernetes.
- Streaming input with no raw-record retention.
- Metric semantics and schemas come from `PROJECT_ARCHITECTURE.md`.
- The complete exit-code contract is `0/1/2/3/4`: `0` success; `1` input/I/O/decoding or unexpected runtime failure; `2` CLI usage error; `3` strict parse failure; `4` unique-cardinality exhaustion.
- Add or update tests in the same step and run the stated verification commands.
- Do not claim the 1 GB/30 s target until the exact benchmark has run on documented hardware.

## Session Workflow

1. Select only the next incomplete step in `IMPLEMENTATION_PLAN.md`.
2. Restate its acceptance criteria and affected files.
3. Inspect existing work and preserve user changes.
4. Implement the smallest coherent slice with tests.
5. Run step verification, then the relevant regression suite.
6. Report files changed, commands run, actual outcomes, and the next step.
7. At the end of every session or meaningful block of work, save context with `/session-save`.

## Prompt 1: Package and CLI contracts

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Create the Python 3.11 src-layout package, Click entry point, declared options, and tests for help/version/usage validation. Do not parse logs or emit reports yet. Keep --json and --csv mutually exclusive, validate a positive --max-unique-user-agents, and preserve Click usage exit 2. Run every STEP 1 verification command and report actual output succinctly.
```

## Prompt 2: Models, fixtures, and errors

```text
Implement STEP 2 from IMPLEMENTATION_PLAN.md only. Add the dataclasses and typed errors exactly as specified in PROJECT_ARCHITECTURE.md, plus compact secret-free fixtures. Freeze tests for the 0/1/2/3/4 boundary before later wiring. Do not implement parsing or aggregation in this step. Run compile and focused tests.
```

## Prompt 3: Combined-log parser

```text
Implement STEP 3 from IMPLEMENTATION_PLAN.md only. Parse whole nginx combined-format lines into timezone-aware ParsedRequest values. Treat log text as untrusted, bound error excerpts, avoid catastrophic regex behavior, and cover the documented edge cases. The parser must not print or retain lines. Run the parser tests and duration report.
```

## Prompt 4: Streaming aggregation

```text
Implement STEP 4 from IMPLEMENTATION_PLAN.md only. Build one-pass aggregation for top-10 IPs, top-10 4xx/5xx URLs, all 24 hour buckets, and unique User-Agent count/share. Use deterministic tie-breaking. Hourly percentage must be 100 × hourly_request_count / total_valid_requests. Enforce the unique-UA cap before insertion and raise the typed cardinality error. Do not render output. Run focused parser and aggregate tests.
```

## Prompt 5: Renderers

```text
Implement STEP 5 from IMPLEMENTATION_PLAN.md only. Render the immutable snapshot as Rich terminal text, versioned JSON, and normalized CSV. Escape/disable markup for log-derived text, emit no ANSI in JSON/CSV, and round percentages only at serialization. Test schemas, deterministic order, empty rankings, and 24 hourly rows. Do not add I/O orchestration.
```

## Prompt 6: End-to-end CLI

```text
Implement STEP 6 from IMPLEMENTATION_PLAN.md only. Wire file/stdin iteration, tolerant and strict parsing, aggregation, renderer selection, stdout/stderr separation, resource ownership, and centralized errors. Exercise every exit code: 0 success, 1 I/O/runtime, 2 usage, 3 strict parse failure, 4 unique-cardinality exhaustion. A failing run must not emit a partial report. Run focused and full tests.
```

## Prompt 7: Performance evidence

```text
Implement STEP 7 from IMPLEMENTATION_PLAN.md only. Add a deterministic benchmark-log generator, CI-safe performance/resource regression tests, and docs/BENCHMARK.md. Generate the 1 GiB fixture outside Git and run the exact timed command. Record hardware, software, fixture cardinalities, wall time, and peak RSS. If it misses 30 seconds, profile first and change only measured hotspots without weakening correctness.
```

## Prompt 8: Release readiness

```text
Implement STEP 8 from IMPLEMENTATION_PLAN.md only. Reconcile README, help, schemas, limitations, and the exact 0/1/2/3/4 exit mapping. Build and install the wheel in a clean Python 3.11 environment, run the full suite, and smoke-test stdin JSON. Do not add gzip, configurable top-N, services, or storage. Report observed results rather than predicted success.
```

## Completion Checklist for Each Step

- [ ] Only the active step and necessary tests/docs changed.
- [ ] No raw logs, generated 1 GB fixture, secrets, or benchmark outputs are committed.
- [ ] Focused tests and the listed verification commands actually ran.
- [ ] Failures remain failures; no test or gate was removed to obtain green output.
- [ ] User-facing behavior agrees with the PRD and architecture.
- [ ] Session state and the next action are explicit.

