# Coding Guide: nginx-insights

## 1. How to Use This Guide

This file turns [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) into bounded implementation prompts. Run one prompt at a time, preserve WIP=1, and verify the exact changed candidate before advancing. The durable source of truth is [PRD.md](PRD.md); [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) governs structure and interfaces. If code and specification disagree, pause and reconcile the specification instead of silently inventing behavior.

Do not add authentication, a database, an HTTP API, a server, Docker, cloud services, or Kubernetes. Do not implement the deferred live-follow story. Use Python 3.11, Click, Rich, dataclasses, standard-library streaming I/O, and pip packaging.

## 2. Non-Negotiable CLI Contract

Every implementation prompt must preserve all five exit codes:

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Operational/internal failure, including stdout write failure |
| `2` | Click usage/options failure |
| `3` | Input/read/decode/strict-parse failure |
| `4` | Unique-cardinality exhaustion |

Code 4 must not be omitted, remapped, or reported as partial success. Exits 1, 3, and 4 emit no normal report. JSON and CSV data go only to stdout; diagnostics go only to stderr.

## 3. Shared Implementation Guardrails

- Process input exactly once and never retain raw lines or all parsed records.
- Use the same immutable `Report` for Rich, JSON, and CSV.
- Rank by count descending and raw value ascending.
- Compute hourly percentages using exactly `100 × hourly_request_count / total_valid_requests`; use `0.0` when there are no valid requests.
- Compute User-Agent share as `100 × unique_user_agent_count / total_valid_requests`; use `0.0` when there are no valid requests.
- Apply `--max-unique` independently to IP, error-URL, and User-Agent trackers before inserting a distinct key.
- Treat all log values as untrusted data; do not render them as Rich markup or include raw lines in diagnostics.
- Add or update tests in the same step as behavior. No placeholder, skipped, or network-dependent test may satisfy a step.
- Do not claim the 1 GB / 30 s target without a recorded run on the exact candidate and documented reference environment.

## 4. Step Prompts

### Prompt 1 — Package and CLI contracts

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Read PRD.md and the CLI Interface in PROJECT_ARCHITECTURE.md first. Create pyproject.toml, the src/nginx_insights package, Click help/version/options, and contract tests. Keep --json and --csv mutually exclusive and --max-unique positive. Do not implement parsing or renderers yet, and do not let an unimplemented analysis path exit 0. Run every STEP 1 verification command, report actual results, and stop without beginning STEP 2.
```

Acceptance evidence: editable install succeeds; Ruff and mypy pass; help/version return 0; incompatible flags and invalid positive-integer constraints return 2.

### Prompt 2 — Models and failure taxonomy

```text
Implement STEP 2 from IMPLEMENTATION_PLAN.md only. Define the exact dataclasses and invariants from PROJECT_ARCHITECTURE.md and typed failures in errors.py. Preserve Click's usage exit 2 and map only operational/internal to 1, input/parse to 3, and unique-cardinality exhaustion to 4. Add focused unit and CLI integration tests, including absence of normal reports for 1/3/4. Run the listed verification commands and stop at the STEP 2 boundary.
```

Acceptance evidence: all model invariants pass and an automated test distinguishes each exact code `0/1/2/3/4`.

### Prompt 3 — Combined-log parser

```text
Implement STEP 3 from IMPLEMENTATION_PLAN.md only. Build a compiled nginx combined-format parser that returns AccessRecord or structured rejection. Follow PRD.md's Input Contract exactly, including timezone offsets, quoted fields, request '-', bytes '-', Unicode, and three-digit status validation. Add synthetic fixtures clearly labeled as test data. Never echo a raw rejected line. Run parser tests, Ruff, and mypy relevant to this step; stop before aggregation.
```

Acceptance evidence: valid/edge fixtures parse deterministically; every declared malformed class rejects without a user traceback.

### Prompt 4 — Streaming aggregation

```text
Implement STEP 4 from IMPLEMENTATION_PLAN.md only. Add a one-pass pipeline and exact aggregators for all four views. Use 24 fixed hour buckets, error statuses 400-599, deterministic top-10 ties, the literal hourly formula 100 × hourly_request_count / total_valid_requests, and the specified User-Agent share. Enforce --max-unique separately before inserting a new IP, error URL, or User-Agent and raise the exit-4 domain error rather than approximate. Test single iteration, zero denominators, boundary values, and all three exhaustion paths. Run the listed checks and stop.
```

Acceptance evidence: unit tests prove the formulas, rankings, lazy iteration, invalid-line policies, and cardinality boundary behavior.

### Prompt 5 — Rich terminal renderer

```text
Implement STEP 5 from IMPLEMENTATION_PLAN.md only. Render the shared Report with Rich as the default output, including totals, both ranked tables, all 24 hourly rows, and unique User-Agent count/share. Make color TTY-aware and honor --color/--no-color. Treat log-derived values as plain text, not Rich markup. Keep diagnostics on stderr. Add integration tests for empty, Unicode, markup-like, color, and narrow-terminal cases. Run the listed checks and stop.
```

Acceptance evidence: terminal golden assertions contain every required view, color behavior is controlled, and injected markup-like values cannot alter presentation.

### Prompt 6 — JSON and CSV renderers

```text
Implement STEP 6 from IMPLEMENTATION_PLAN.md only. Create JSON and CSV renderers over the exact same Report. Follow the normative schemas and ordering in PROJECT_ARCHITECTURE.md, including 24 ascending hour rows, six-decimal percentage serialization, normalized CSV section rows, RFC 4180 quoting, and LF record separators. Ensure no ANSI or diagnostics reach structured stdout. Add reviewed golden fixtures and environment-variance tests. Run every listed check and stop.
```

Acceptance evidence: byte-level golden tests pass, JSON parses, CSV parses, and Rich is never constructed on structured-output paths.

### Prompt 7 — I/O and exit-code integration

```text
Implement STEP 7 from IMPLEMENTATION_PLAN.md only. Finish file/stdin ownership, buffered UTF-8 iteration, line-number diagnostics, exception boundaries, and broken-output handling. Exercise the complete contract: 0 success; 1 operational/internal/stdout failure; 2 usage; 3 unreadable/decode/strict-parse input failure; 4 unique-cardinality exhaustion. Do not remap code 4. Assert no traceback or normal report for 1/3/4 and no diagnostics in JSON/CSV stdout. Run the integration suite, full suite, and coverage gate; stop before performance/package work.
```

Acceptance evidence: subprocess or Click-runner tests demonstrate all five codes and correct stdout/stderr behavior.

### Prompt 8 — Performance and package release candidate

```text
Implement STEP 8 from IMPLEMENTATION_PLAN.md only. Add a deterministic synthetic benchmark generator and runner, record fixture distribution and reference environment, build wheel/sdist, and smoke-test the installed console script. Freeze the exact release candidate before running formatting, lint, type, tests, coverage, build, install, and the 1 GB under-30-second oracle. Do not weaken exact aggregation, the max-unique guard, tests, or input size to obtain a pass. If the benchmark fails, report recovery evidence and profile; do not claim completion.
```

Acceptance evidence: the exact candidate passes all static/test/package gates and the recorded performance oracle, or the step remains explicitly incomplete with measured evidence.

## 5. Review Checklist for Every Step

- [ ] Scope is limited to the current step and named files.
- [ ] Tests fail meaningfully before new behavior and pass after it where applicable.
- [ ] No product contract is inferred from a renderer or test fixture alone.
- [ ] The `0/1/2/3/4` exit mapping remains intact, including code 4 for unique-cardinality exhaustion.
- [ ] New stdout is either the complete normal report or documented help/version output.
- [ ] No raw logs, secrets, telemetry, or network calls were introduced.
- [ ] Relevant verification commands ran against the exact current candidate.
- [ ] [CLAUDE.md](CLAUDE.md) status and session notes are updated only from evidence.

## 6. Recovery Rules

If a check fails, keep the current step active, record the command and relevant failure, fix only within the step, and rerun affected checks plus the step's complete verification set. If a requested change alters user-visible behavior, update PRD first and reconcile architecture and plans. If meeting the benchmark requires multiprocessing, approximation, persistence, or a service, invoke the PRD kill criteria and request a new approved design instead of expanding scope.
