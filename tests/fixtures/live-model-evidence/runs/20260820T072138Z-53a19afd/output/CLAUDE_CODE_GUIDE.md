# Claude Code Guide: nginx Stream Analytics CLI

This is the execution companion to `IMPLEMENTATION_PLAN.md`. Use one prompt at a time in order, keep WIP=1, inspect the current repository before editing, and stop after the requested step has been implemented and verified. The specification files are the source of truth; do not silently change them to match code.

## Non-negotiable implementation contract

Every prompt below inherits these rules:

- Use Python 3.11, Click, Rich, dataclasses, and standard-library streaming I/O.
- Keep one local stateless process. Add no authentication, database, HTTP API, server, cloud resource, Docker runtime requirement, or Kubernetes artifact.
- Read line-by-line; never read the entire input into memory.
- Preserve deterministic count-descending/key-ascending rankings.
- Define hourly percentages only as `100 × hourly_request_count / total_valid_requests`, never as an unscaled fraction.
- Do not silently approximate distinct User-Agents.
- Run the listed verification; report actual results, not predictions.

The complete exit-code contract is mandatory in every step:

| Code | Meaning |
|---:|---|
| `0` | Successful complete report, including mixed valid/malformed input |
| `1` | Unexpected internal error |
| `2` | CLI usage or input I/O error |
| `3` | Zero valid nginx records |
| `4` | Unique-cardinality exhaustion: another distinct User-Agent would exceed the configured exact limit |

Never omit or remap code `4`. Failure codes produce no partial report; expected errors go to stderr without traceback.

## Prompt 1 — Package skeleton and executable contract

```text
Implement only STEP 1 from IMPLEMENTATION_PLAN.md.

First read AGENTS.md, .itd/SCOPE_LOCK.md, PROJECT_ARCHITECTURE.md (especially ## CLI Interface), PRD.md, and IMPLEMENTATION_PLAN.md STEP 1. Create the pyproject package skeleton, console entry point, Click help/version/options, and focused CLI contract tests. Do not implement parsing or reports yet. Keep the command composition root thin and avoid product behavior beyond STEP 1.

Preserve the guide's exact 0/1/2/3/4 exit-code contract, including 4 for unique-cardinality exhaustion, even where later paths are not implemented yet. Run the STEP 1 install, help, pytest, Ruff, and mypy checks. Finish with changed files, actual command results, unresolved risks, and the next step; do not start STEP 2.
```

## Prompt 2 — Parser and input lifecycle

```text
Implement only STEP 2 from IMPLEMENTATION_PLAN.md.

Read the architecture parsing/data contracts and PRD US-1 before editing. Add the exact combined-format LogRecord dataclass, compiled parser, read-only file/stdin opener, malformed accounting, and boundary fixtures. Keep decoding and request-target semantics exactly as specified. Distinguish input I/O failures from a completed input with zero valid records.

Preserve the guide's exact 0/1/2/3/4 exit-code contract: 0 success, 1 unexpected internal error, 2 usage/input I/O error, 3 zero valid records, 4 unique-cardinality exhaustion. Do not remap or omit 4. Run every STEP 2 check and the existing suite. Report evidence and stop before aggregation work.
```

## Prompt 3 — Deterministic rankings

```text
Implement only STEP 3 from IMPLEMENTATION_PLAN.md.

Read PRD US-2/US-3 and architecture Sections 5-6. Add one-pass exact counters for all valid client IPs and only 400..599 request targets. Finalize at most 10 items with count descending and exact string ascending as the tie-breaker. Keep request targets, including queries, opaque. Add independent boundary/tie fixtures and tests.

Preserve all exit meanings exactly: 0 successful report, 1 unexpected internal error, 2 usage/input I/O error, 3 zero valid records, and 4 unique-cardinality exhaustion. Code 4 remains reserved and must never be collapsed. Run STEP 3 pytest, the full suite, Ruff, and mypy; report actual evidence and stop before hourly/User-Agent work.
```

## Prompt 4 — Hourly and User-Agent metrics

```text
Implement only STEP 4 from IMPLEMENTATION_PLAN.md.

Read PRD US-4/US-5 and architecture metric/resource rules. Add all 24 wall-clock hour buckets. Calculate each percentage as the literal percentage formula 100 × hourly_request_count / total_valid_requests, retaining full precision until two-decimal rendering. Add exact distinct non-placeholder User-Agent counting and check --max-unique-user-agents before inserting a new value. Never approximate or evict.

Implement and test the complete exit mapping: 0 successful complete report; 1 unexpected internal error; 2 CLI usage or input I/O error; 3 zero valid records; 4 unique-cardinality exhaustion. Specifically prove the boundary succeeds and boundary+1 returns 4 with empty stdout and a concise stderr message. Run all STEP 4 checks, report results, and stop before renderers.
```

## Prompt 5 — Rich terminal output

```text
Implement only STEP 5 from IMPLEMENTATION_PLAN.md.

Read architecture output/security rules and PRD US-6. Build the default Rich renderer from the immutable Report without recomputing metrics. Show all four sections and line totals. Implement the documented TTY, NO_COLOR, --color, and --no-color policy. Treat log-derived strings as untrusted text: prevent Rich markup interpretation and normalize terminal control characters. Add deterministic no-color golden tests.

Preserve exit codes 0 success, 1 unexpected internal error, 2 usage/input I/O error, 3 zero valid records, and 4 unique-cardinality exhaustion; code 4 cannot be omitted or remapped. A failure emits no partial Rich report. Run STEP 5 tests, a NO_COLOR smoke command, Ruff, and mypy. Report actual evidence and stop before JSON/CSV.
```

## Prompt 6 — JSON and CSV output

```text
Implement only STEP 6 from IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md ## CLI Interface, output stability rules, and PRD US-7. Add JSON schema_version 1 and normalized CSV with exactly section,rank,key,count,percentage columns. Both renderers must consume the same Report as terminal output, preserve stable ordering/numeric types/two-decimal serialization, end with one newline, and emit no ANSI. Keep --json/--csv exclusive and stdout free of diagnostics. Add golden files and broken-pipe coverage.

Preserve the complete exit contract unchanged: 0 successful report, 1 unexpected internal error, 2 usage/input I/O error, 3 zero valid records, 4 unique-cardinality exhaustion. Never remap 4. Run JSON parsing, CSV smoke, focused/full tests, Ruff, and mypy; report evidence and stop before hardening.
```

## Prompt 7 — Failure matrix and distribution

```text
Implement only the P0 portion of STEP 7 from IMPLEMENTATION_PLAN.md. Attempt P1 gzip only after every P0 check is green and only if the remaining weekend budget permits it.

Read the full architecture CLI contract and PRD release acceptance. Make error handling narrow and typed; expected failures have concise stderr, empty report stdout, and no traceback. Build the complete matrix and prove: 0=successful complete report including mixed valid/malformed input; 1=unexpected internal error; 2=CLI usage or input I/O error; 3=zero valid nginx records; 4=unique-cardinality exhaustion. Do not omit, remap, approximate, or generalize code 4. Add packaging checks, build artifacts, and a clean temporary-environment wheel smoke test. Update README only to reflect verified behavior.

Run coverage >=90%, Ruff, mypy, build, and clean-install checks from STEP 7. Report actual results and stop before the large benchmark.
```

## Prompt 8 — Release and performance acceptance

```text
Implement only STEP 8 from IMPLEMENTATION_PLAN.md and verify the exact release candidate.

Read architecture Section 12 and all PRD non-functional/release criteria. Add deterministic benchmark generation and an argv-safe measurement runner; do not commit the generated 1 GB file. Independently verify report correctness before accepting timing. Record byte size, valid/malformed ratio, distinct cardinalities, Python/OS/hardware, warm-up, all three measured elapsed times, median, and peak RSS in docs/BENCHMARK.md. Acceptance requires median <30.0 seconds on the documented laptop.

Re-run tests for the full exit contract: 0 success, 1 unexpected internal error, 2 usage/input I/O error, 3 zero valid records, and 4 unique-cardinality exhaustion. Code 4 must still mean exact User-Agent cardinality exhaustion and must never be omitted/remapped. Run the full coverage, Ruff, mypy, benchmark, build, and clean-wheel smoke gates. Report only observed evidence, reconcile project state, and do not add post-MVP features.
```

## Handoff format after each prompt

Use this compact handoff:

1. Step status: complete, blocked, or recovery required.
2. Changed files and why each changed.
3. Verification commands with actual exit status and salient result.
4. Exit-code paths added/rechecked, explicitly including code `4`.
5. Scope/spec deviations (normally none).
6. Residual risks and the single next step.

Do not call a step complete from narration alone. Completion requires the current repository's applicable Idea to Deploy verification evidence and reconciled state.
