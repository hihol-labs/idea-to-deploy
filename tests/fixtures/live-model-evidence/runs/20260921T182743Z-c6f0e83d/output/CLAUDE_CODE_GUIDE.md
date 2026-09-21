# Claude Code Implementation Guide: nginx-stream-report

## Purpose

Use this guide to implement the approved blueprint one step at a time. `PROJECT_ARCHITECTURE.md` is the technical source of truth, `PRD.md` is the behavior source of truth, and `IMPLEMENTATION_PLAN.md` fixes dependency order. Preserve work-in-progress at one step, run its verification commands, and update the specs before changing a public contract.

Do not add authentication, a database, HTTP API, server, cloud resources, Docker, or Kubernetes. Do not implement multiple steps in one unreviewed change.

## Global Contract for Every Prompt

Every implementation step must preserve this complete exit mapping: `0` success, `1` I/O failure, `2` usage error, `3` log-data failure, and `4` unique-cardinality exhaustion. The exact `0/1/2/3/4` contract is public; never omit, reuse, or remap code 4.

Hourly distribution is a percentage calculated exactly as `100 × hourly_request_count / total_valid_requests`. Structured output goes to stdout, diagnostics to stderr, and JSON/CSV never contain ANSI escape sequences.

## Prompt 1: Package and CLI Skeleton

> Implement only `IMPLEMENTATION_PLAN.md` Step 1. Read `PRD.md` goals/non-goals and `PROJECT_ARCHITECTURE.md` repository layout plus CLI interface first. Create the Python 3.11 `pyproject.toml`, package initializer, Click skeleton, and focused CLI tests. Do not implement parsing or reports. Run the three Step 1 verification commands and report changed files and evidence.

## Prompt 2: Domain Models and Exit Semantics

> Implement only Step 2. Define frozen dataclasses and typed expected failures in the specified files. Lock CLI tests to the complete public status mapping 0/1/2/3/4, including code 4 for unique-cardinality exhaustion. Avoid framework or persistence abstractions. Run Step 2 checks and stop if any fails.

## Prompt 3: Streaming Input and Parser

> Implement only Step 3. Parse declared nginx common and combined formats from file or stdin one line at a time. Use synthetic fixtures, compile parsing machinery once, preserve the timestamp offset, and never accumulate records. Cover malformed quoting, status, timestamp, empty lines, missing User-Agent, and invalid UTF-8 replacement. Run the parser and regression checks from the plan.

## Prompt 4: Aggregation

> Implement only Step 4. Add one-pass counters, deterministic top-10 selection, 24 hourly buckets, and an exact guarded User-Agent set. Hourly percentage must use `100 × hourly_request_count / total_valid_requests`. Check the cardinality limit before insertion and raise the typed failure mapped to status 4. Test ties and all boundary conditions listed in the plan.

## Prompt 5: Rich Terminal Output

> Implement only Step 5. Render the summary and four metric tables with Rich. Treat parsed values as untrusted text and escape markup. Auto-color only for a terminal and guarantee redirected/default `--no-color` output has no ANSI escapes. Keep rendering free of parsing and aggregation logic. Run the terminal renderer checks.

## Prompt 6: JSON and CSV

> Implement only Step 6. Implement exactly the JSON shape and normalized CSV schema in `PROJECT_ARCHITECTURE.md`. Use standard encoders/writers, deterministic ordering, UTF-8, and no ANSI. Add golden tests including commas, quotes, Unicode, and leading spreadsheet-formula characters as literal data. Run parser-based verification for both formats.

## Prompt 7: End-to-End CLI and Follow Mode

> Implement only Step 7. Wire input, parser, aggregation, renderer, stderr diagnostics, and typed failures in `cli.py`; complete regular-file follow behavior without duplicating data. Verify file/stdin equivalence and strict/default malformed handling. Assert all public exit statuses and specifically prove cardinality exhaustion returns 4. Run all Step 7 checks.

## Prompt 8: Quality and Packaging Gate

> Implement only Step 8. Add missing boundary cases, golden end-to-end assertions, coverage configuration, and wheel validation. Do not alter specified behavior merely to make a test pass; reconcile the spec first if a real contradiction exists. Require at least 90% core coverage and validate installation in a clean temporary environment.

## Prompt 9: Performance Acceptance

> Implement only Step 9. Create a deterministic synthetic benchmark generator and separate small/performance test markers. Generate a representative 1 GB file, measure elapsed time and peak RSS, and record machine, Python, storage, cache assumptions, and exact command. The acceptance target is under 30 seconds; do not claim it from extrapolation. If it fails, profile first and keep database/server/cloud options out of scope.

## Review Checklist After Each Step

- Only the active implementation step and directly required documentation changed.
- No complete input or `AccessRecord` list is retained.
- All user-derived terminal text is markup-safe.
- JSON and CSV remain deterministic, parseable, and ANSI-free.
- Tests cover both success and expected failure paths.
- Verification commands actually ran and their outcome is recorded.
- Public contracts remain synchronized across `PRD.md`, `PROJECT_ARCHITECTURE.md`, Click help, and tests.

## Final Release Prompt

> Review the completed implementation against all P0 requirements and acceptance scenarios in `PRD.md`. Run the full test/coverage/build suite, install the built wheel in a clean Python 3.11 environment, and execute the documented 1 GB benchmark. Confirm each status in the 0/1/2/3/4 exit contract with an end-to-end case. Report failures as blockers; do not call the release done without current command evidence.

