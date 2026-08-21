# Claude Code Implementation Guide: Nginx Stream Analyzer

Use these prompts sequentially after the blueprint is approved. Keep WIP=1: complete and verify one step before beginning the next. Read `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the matching section of `IMPLEMENTATION_PLAN.md` before editing.

## Binding Contracts for Every Step

- Python 3.11; Click; Rich; dataclasses; pip-installable package.
- One local process, incremental input, no database, HTTP API, auth, server, cloud, Docker, or Kubernetes.
- Do not retain parsed request records after aggregation.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Complete exit-code contract: `0` success; `1` input I/O or decoding failure; `2` Click usage error; `3` no valid nginx records; `4` unique-cardinality exhaustion.
- A nonzero result writes no partial report to stdout; diagnostics go to stderr.
- Preserve output schemas and deterministic tie ordering from `PROJECT_ARCHITECTURE.md`.
- Never mark a step complete without executing and recording its verification commands.

## Prompt 1: Package Skeleton and CLI

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Create the Python 3.11 src-layout package, pyproject.toml, Click console entry point, typed domain errors, and CLI contract tests. Preserve the exact options and complete 0/1/2/3/4 exit-code meanings in PROJECT_ARCHITECTURE.md even where later steps provide the behavior. Do not implement parsing or aggregation. Run the listed Step 1 verification commands, report results, and update the project status only with real evidence.
```

## Prompt 2: Parser and Models

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Add the dataclasses and a pure parser for the documented nginx common/combined formats, plus synthetic fixtures and boundary tests. Treat lines as untrusted, avoid logging raw malformed content, and keep parsing independent of rendering. Preserve the full exit-code contract: 0 success, 1 I/O/decoding, 2 usage, 3 no valid records, 4 unique-cardinality exhaustion. Run the listed Step 2 verification commands and record actual evidence.
```

## Prompt 3: Input and Aggregation

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Stream file/stdin input, aggregate top IPs, 4xx/5xx URLs, all 24 hourly buckets, and exact User-Agent cardinality. Use the literal formula 100 × hourly_request_count / total_valid_requests. Enforce the configurable User-Agent cap and map exhaustion to code 4; retain codes 0/1/2/3 as documented. Never load the file or retain request records. Run the listed tests and record evidence.
```

## Prompt 4: Rich Terminal Output

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Render the normalized result using Rich, with safe untrusted text, deterministic ranks, all 24 hours, malformed count, and auto/forced/disabled color. Do not alter calculations or the complete exit codes 0 success, 1 I/O/decoding, 2 usage, 3 no-valid-data, 4 cardinality exhaustion. Run the renderer tests and manual fixture command, then record actual results.
```

## Prompt 5: JSON and CSV

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Add JSON and long-form CSV renderers matching PROJECT_ARCHITECTURE.md exactly and verify semantic parity with terminal results. JSON/CSV must contain no ANSI and diagnostics must stay on stderr. Preserve codes 0/1/2/3/4 with code 4 meaning unique-cardinality exhaustion. Run every listed verification command and record evidence.
```

## Prompt 6: Failure Semantics

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Complete and test the exact mapping: 0 success, 1 input I/O or decoding failure, 2 Click usage error, 3 input with no valid nginx records, 4 unique-cardinality exhaustion. Ensure every nonzero path leaves stdout empty and produces a concise stderr diagnostic. Add end-to-end stdin/file equivalence tests. Run the full listed verification suite and record results.
```

## Prompt 7: Performance and Robustness

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Add deterministic corpus generation, a benchmark runner that records machine/Python/time/peak-RSS context, and adversarial-input tests. Measure the current code before optimizing, change only demonstrated bottlenecks, and prove the representative 1 GB run is under 30 seconds. Preserve all metrics, schemas, and codes 0/1/2/3/4; code 4 remains exact unique-cardinality exhaustion. Record commands and measured results without committing generated gigabyte files.
```

## Prompt 8: Release Readiness

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Finalize open-source packaging and user documentation, including examples, supported formats, limitations, output schemas, and the full codes: 0 success; 1 I/O/decoding; 2 usage; 3 no valid records; 4 unique-cardinality exhaustion. Build and validate distributions, install the wheel in a clean environment, run the complete test suite, and reconcile project status from actual evidence. Do not add a database, service, HTTP API, auth, cloud, Docker, or Kubernetes.
```

## Completion Handoff

At the end of each step report: changed files, verification commands and outcomes, unresolved risks, current WIP step, and the exact next step. If a command fails, leave the step active and provide the smallest recovery action.

