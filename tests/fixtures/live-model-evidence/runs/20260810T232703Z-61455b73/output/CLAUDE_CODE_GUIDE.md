# Claude Code Implementation Guide: nginx-insights

This guide converts `IMPLEMENTATION_PLAN.md` into bounded prompts for a coding agent. It does not authorize implementation during the blueprint phase. Run one prompt at a time, require the listed tests, and reconcile the documents before moving to the next step.

## Permanent Guardrails

- Read `CLAUDE.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the active step in `IMPLEMENTATION_PLAN.md` first.
- Preserve a single Python 3.11 process, streaming input, no database, no HTTP API, no server, no auth, no network, no cloud, no Docker/Kubernetes, and no persistence.
- Use Click, Rich, and dataclasses; do not introduce a framework or analytics dependency without an architecture change.
- Keep stdout report-only and stderr diagnostic-only. JSON and CSV must never contain ANSI escapes.
- Preserve the exact exit mapping in every step: `0` success/help/version; `1` runtime or input I/O failure; `2` usage/configuration error; `3` completed stream with zero valid records; `4` unique-cardinality exhaustion with no partial report. Code 4 must never be omitted or remapped.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests` over valid records only.
- Freeze and verify the exact candidate according to the repository verification contract before marking a step complete.

## Prompt 1: Package Skeleton

> Implement only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the pip-installable `src/` package, Click entry point, empty renderer package, and test/tool configuration. Do not implement parsing or reports. Add tests proving clean invocation and run the Step 1 verification commands. Report changed files, real command outcomes, and the next blocked step.

## Prompt 2: Models and Exit Codes

> Implement only Step 2. Add frozen dataclasses and typed domain errors. Test the complete public contract: `0/1/2/3/4`, where 4 means exact unique-cardinality exhaustion and yields no partial report. Do not implement the parser or renderers. Run the specified pytest and mypy commands and do not mark complete from prose alone.

## Prompt 3: Parser

> Implement only Step 3. Parse documented nginx Common and Combined formats line-by-line into `AccessRecord`; normalize request targets and classify invalid lines. Add the named fixtures and boundary tests. Do not retain source lines, add custom-format support, or alter exit semantics. Run parser tests and Ruff.

## Prompt 4: Aggregator

> Implement only Step 4. In one pass, count IPs, error paths for status 400–599, all 24 log-local hours, and exact non-empty User-Agents up to the configured ceiling. Use deterministic count-descending/key-ascending ties. Calculate hourly percentages with `100 × hourly_request_count / total_valid_requests`. Raise the typed exhaustion condition before exceeding the UA ceiling; do not emit output here. Run aggregation tests and coverage.

## Prompt 5: Rich Text

> Implement only Step 5. Render the complete default report with Rich. Color must be TTY-aware and disabled by `--no-color` or `NO_COLOR`; escape untrusted log-derived values. Add golden and injection-safety tests. Do not import Rich from parsing, aggregation, JSON, or CSV modules. Run text renderer tests and the no-color smoke command.

## Prompt 6: JSON and CSV

> Implement only Step 6. Match the exact JSON and CSV schemas and ordering under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. Use the standard JSON/CSV libraries, UTF-8, deterministic output, and no ANSI. Add golden files and quoting/order tests. Run the machine-renderer tests and JSON parser smoke check.

## Prompt 7: CLI Integration

> Implement only Step 7. Wire optional file/stdin input, renderer selection, color controls, a positive UA ceiling, version, and help. Enforce mutual exclusion for JSON/CSV. Map `0/1/2/3/4` exactly: 0 success/help/version, 1 runtime/I/O, 2 usage/config, 3 zero valid records, 4 unique-cardinality exhaustion. Both 3 and 4 produce no partial report. Run all CLI and exit tests plus the installed-command smoke check.

## Prompt 8: Release Evidence

> Implement only Step 8. Add a deterministic external 1 GB fixture generator, the documented warm-up/three-run median benchmark, no-side-effect checks, and release documentation. Run the full suite, 90% coverage gate, Ruff, mypy, the under-30-second laptop benchmark, build, and clean-wheel installation. Record the real laptop profile and outcomes. Do not claim the target if it was not executed.

## Review Prompt

> Review the current exact candidate against `PROJECT_ARCHITECTURE.md`, every P0 criterion in `PRD.md`, and the active implementation step. Look specifically for whole-file reads, invalid denominators, nondeterministic ties, query-string leakage, missing hours, Rich/ANSI leakage, stdout diagnostics, unsafe terminal markup, and any incomplete `0/1/2/3/4` path. Treat code 4 as unique-cardinality exhaustion. Return findings by severity with file/line evidence; do not edit during review.

## Release Checklist

- [ ] Steps 1–8 have current machine evidence.
- [ ] P0 user stories pass end-to-end for file and stdin.
- [ ] Common and Combined fixtures cover invalid and boundary cases.
- [ ] JSON and CSV match golden schemas and contain no ANSI.
- [ ] Exit codes `0/1/2/3/4` are tested without omission or remapping; 4 is unique-cardinality exhaustion.
- [ ] The documented 1 GB median is under 30 seconds on the recorded laptop profile.
- [ ] Wheel installs and runs in a clean Python 3.11 environment.
- [ ] No database, API, server, auth, network, cloud, Kubernetes, or persistence was introduced.
