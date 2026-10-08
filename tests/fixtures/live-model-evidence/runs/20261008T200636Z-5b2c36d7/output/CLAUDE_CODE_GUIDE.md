# Claude Code Implementation Guide: nginx-log-insights

## Purpose

Use these prompts in separate, reviewable sessions after the blueprint is approved. They implement the nine steps in `IMPLEMENTATION_PLAN.md`; they are not authorization to expand scope. Each session begins by reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the named plan step, and ends by recording actual evidence before changing status.

The immutable exit-code contract in every session is: `0` success, `1` runtime or I/O failure, `2` CLI usage error, `3` parse-quality failure, and `4` unique-cardinality exhaustion. Never omit, reuse, or remap code 4.

## Global Execution Rules

- Preserve the single-process, CLI-only, no-database architecture.
- Implement only one plan step at a time; keep WIP at one.
- Start with or add tests that fail for the missing behavior, then implement the smallest passing change.
- Use Python 3.11, Click, Rich, and standard-library dataclasses; do not replace the approved stack.
- Treat log text as untrusted data and keep stdout free of diagnostics.
- Do not add authentication, HTTP endpoints, a server, Docker, cloud resources, or Kubernetes.
- Do not mark a step complete unless every verification command for that step has actually passed.
- At each session end, run `/session-save` and update only evidence-backed status in `CLAUDE.md`.

## Session 1 Prompt — Package and CLI Contracts

```text
Read CLAUDE.md, PROJECT_ARCHITECTURE.md under “CLI Interface,” PRD.md US-5 through US-7, and IMPLEMENTATION_PLAN.md Step 1. Implement only Step 1.

Create the Python 3.11 src-layout package, Click console entry point, development test configuration, and contract tests for help, version, invalid input, mutually exclusive --json/--csv, and usage exit code 2. The command may remain behaviorally incomplete where later steps own parsing. Do not add parser, aggregator, renderer, service, database, or deployment code.

Run every Step 1 verification command. Report changed files, exact command outcomes, and any blocked acceptance criterion. Update CLAUDE.md status only if the evidence passed, then /session-save.
```

## Session 2 Prompt — Models, Errors, and Fixtures

```text
Read CLAUDE.md, PROJECT_ARCHITECTURE.md “Data Model and Streaming State” and “Error and Resource Handling,” PRD.md, and IMPLEMENTATION_PLAN.md Step 2. Implement only Step 2.

Add the exact dataclasses and named expected-error types from the architecture. Build compact deterministic fixtures that cover IPv4, IPv6, ties, status classes, hours, repeated and missing User-Agents, quoting, and malformed lines. Models must not import Click or Rich. Do not implement parsing or aggregation yet.

Run every Step 2 verification command. Record evidence, update only the Step 2 status when green, then /session-save.
```

## Session 3 Prompt — Streaming Parser

```text
Read CLAUDE.md, PROJECT_ARCHITECTURE.md “Input and Parsing Contract,” PRD.md FR-01 through FR-03, and IMPLEMENTATION_PLAN.md Step 3. Implement only Step 3 using test-first changes.

Create a side-effect-free combined-log parser with one precompiled grammar. Extract only remote address, aware timestamp, method, request target, status, and User-Agent. A malformed line must never yield a partial record. Preserve line-by-line operation and do not print, read files, aggregate, or exit from the parser.

Run the Step 3 test and coverage commands. Record red-to-green evidence and coverage, update status only after passing, then /session-save.
```

## Session 4 Prompt — Aggregation and Cardinality

```text
Read CLAUDE.md, the data-model section of PROJECT_ARCHITECTURE.md, PRD.md US-1 through US-4 and US-6, and IMPLEMENTATION_PLAN.md Step 4. Implement only Step 4.

Build exact one-pass counters, 24 hourly buckets, User-Agent uniqueness, parse accounting, deterministic top-ten tie ordering, and immutable Report finalization. Calculate hourly percentage exactly as 100 × hourly_request_count / total_valid_requests. Enforce the configured unique-value ceiling before retaining any new IP, error URL, or User-Agent key. The boundary error must later map to exit code 4 and must never produce a partial success report.

Run every Step 4 verification command, including the ceiling boundary tests. Record evidence, update status only when green, then /session-save.
```

## Session 5 Prompt — Three Renderers

```text
Read CLAUDE.md, PROJECT_ARCHITECTURE.md “Outputs” and “Output Schemas and Numerical Rules,” PRD.md US-5, and IMPLEMENTATION_PLAN.md Step 5. Implement only Step 5.

Create Rich terminal, JSON schema-version 1, and normalized CSV renderers over the same immutable Report. Escape untrusted terminal values, use csv.writer, emit exactly 24 hourly rows for successful reports, and keep JSON/CSV free of ANSI and diagnostics. Protect deterministic results with golden tests.

Run every Step 5 verification command. Record evidence and intentional golden changes, update status only when green, then /session-save.
```

## Session 6 Prompt — Integrated CLI and Exit Codes

```text
Read CLAUDE.md, PROJECT_ARCHITECTURE.md “CLI Interface,” all P0 PRD acceptance criteria, and IMPLEMENTATION_PLAN.md Step 6. Implement only Step 6.

Wire file/stdin streaming, strict and non-strict parse handling, unique ceiling, renderer selection, diagnostics, and exception mapping at one CLI boundary. Assert the complete mapping: 0 success; 1 runtime/I/O failure; 2 usage error; 3 parse-quality failure; 4 unique-cardinality exhaustion. Ensure stdout contains only the selected report and file/stdin results match.

Run every Step 6 command plus integration tests that independently trigger all five codes. Record exact outcomes, update status only when green, then /session-save.
```

## Session 7 Prompt — Quality and Untrusted Output

```text
Read CLAUDE.md, PROJECT_ARCHITECTURE.md “Security and Privacy,” every P0 criterion in PRD.md, and IMPLEMENTATION_PLAN.md Step 7. Implement only Step 7.

Close acceptance-test gaps, test hostile Rich markup/control strings and CSV quoting, and finalize lint/type/coverage configuration. Do not broaden feature scope. Fix product defects rather than weakening assertions or excluding core modules from coverage.

Run the full coverage, Ruff, and mypy commands in Step 7. Record outcomes, update status only when all are green, then /session-save.
```

## Session 8 Prompt — Reproducible Performance Evidence

```text
Read CLAUDE.md, STRATEGIC_PLAN.md success metrics, PROJECT_ARCHITECTURE.md “Testing and Performance Architecture,” PRD.md US-7, and IMPLEMENTATION_PLAN.md Step 8. Implement only Step 8.

Create a deterministic out-of-repository 1 GB fixture generator and a benchmark runner that records input size, environment, three wall-time runs, median, peak RSS, and exit status. Run the baseline before optimization. Profile measured hot paths and change only what evidence supports while preserving all correctness tests. Never silently raise the cardinality ceiling or change fixture shape to make the target pass.

Run every Step 8 verification command and the complete regression suite. Record the environment and results, update status only if the stated target passes, then /session-save.
```

## Session 9 Prompt — Release Candidate

```text
Read all blueprint documents and IMPLEMENTATION_PLAN.md Step 9. Implement only the release gate.

Finalize user documentation, package metadata, changelog, and license. Build a wheel, install it into a clean Python 3.11 virtual environment, run help and a fixture report, run the complete suite, and rerun the benchmark against the exact release candidate. Confirm the README behavior, JSON/CSV schemas, formulas, and the 0/1/2/3/4 exit contract match the implementation.

Do not declare version 0.1.0 ready if any P0 acceptance criterion, smoke test, quality command, or performance target lacks current evidence. Record outcomes, reconcile CLAUDE.md, then /session-save.
```

## Recovery Prompt

```text
The current step is blocked or failing. Do not start another implementation step. Read the failing acceptance criterion and its owning architecture section, reproduce the smallest failure, and identify whether the defect is in product code, test setup, fixture assumptions, or the blueprint contract. Preserve stdout/stderr and exit-code contracts. If the desired behavior requires a product decision or spec change, stop and propose the smallest document change before editing code. Otherwise fix the defect, rerun the focused check, then rerun the step verification. Save only verified state with /session-save.
```

## Completion Checklist

- [ ] Steps 1–9 have current command evidence.
- [ ] P0 acceptance criteria in `PRD.md` all pass.
- [ ] Terminal, JSON, and CSV derive from identical metrics.
- [ ] Exit codes `0/1/2/3/4`, including code 4 for unique-cardinality exhaustion, are integration-tested.
- [ ] The clean wheel smoke test passes on Python 3.11.
- [ ] The exact release candidate meets the documented 1 GB time and memory target.
- [ ] `CLAUDE.md`, user documentation, and session state are reconciled.
