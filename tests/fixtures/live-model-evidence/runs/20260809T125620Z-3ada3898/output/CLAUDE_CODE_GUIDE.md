# Claude Code Implementation Guide: Nginx Insights CLI

## How to Use This Guide

Start each session by reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `.itd/SCOPE_LOCK.md`, and applicable `.itd/` verification contracts. Work on exactly one numbered step. Update the specification before changing an approved behavior. Do not add a database, HTTP API, server, authentication, cloud service, Docker dependency, or Kubernetes.

The complete exit-code contract applies to every prompt below: `0` success; `1` unexpected runtime, processing, or output failure; `2` invalid CLI usage/options; `3` unreadable input or no valid records; `4` unique-cardinality exhaustion. Code `4` specifically means exact User-Agent cardinality would exceed the configured limit; it must not be omitted, remapped, or replaced by partial output.

Before accepting any step, freeze the exact candidate and run the evidence required by the current `.itd/VERIFICATION_CONTRACT.json` and Verification Loop risk route. Narration alone is not completion.

## Prompt 1: Package and CLI Contract

> Implement only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src` package, `pyproject.toml`, console entry point, and Click interface contract with file/stdin input, mutually exclusive `--json`/`--csv`, `--no-color`, and `--max-unique-user-agents`. Preserve the full exit contract 0 success, 1 runtime/output failure, 2 usage, 3 input/no-valid-records, and 4 unique-cardinality exhaustion. Add and run only the Step 1 tests and commands. Do not implement parsing or metrics early. Report changed paths and real command results, then reconcile project state.

## Prompt 2: Models and Failures

> Implement only Step 2 of `IMPLEMENTATION_PLAN.md`. Add the frozen dataclasses and domain exceptions specified in `PROJECT_ARCHITECTURE.md`. Prove the full 0/1/2/3/4 mapping in tests, with 4 reserved for unique-cardinality exhaustion. Keep models independent of Click, streams, and renderers. Run the listed unit and type checks, report evidence, and reconcile state.

## Prompt 3: Combined-Log Parser

> Implement only Step 3 of `IMPLEMENTATION_PLAN.md`. Build the once-compiled nginx combined-log parser and focused fixtures for quoting, escapes, IPv4/IPv6, timestamps, status boundaries, missing fields, and empty User-Agents. Never print rejected raw lines. Preserve all 0/1/2/3/4 semantics at the caller boundary, including 4 for unique-cardinality exhaustion even though the parser does not raise it. Run the listed parser tests and lint check, report evidence, and reconcile state.

## Prompt 4: Streaming Metrics

> Implement only Step 4 of `IMPLEMENTATION_PLAN.md`. Add exact one-pass IP/error-URL counters, 24 hour buckets, and the exact nonempty User-Agent set. Use the literal hourly formula `100 × hourly_request_count / total_valid_requests`. Enforce the limit before adding a new User-Agent and fail with code 4, emitting no partial report. Preserve deterministic ties and the complete 0/1/2/3/4 contract. Run the listed unit/type checks, report evidence, and reconcile state.

## Prompt 5: Rich Terminal Output

> Implement only Step 5 of `IMPLEMENTATION_PLAN.md`. Render the immutable report with safe Rich tables, TTY-aware color, and explicit no-color behavior. Escape every log-derived value. Do not recalculate metrics. Preserve the complete exit contract 0/1/2/3/4, where 4 is unique-cardinality exhaustion. Run the listed renderer tests, report evidence, and reconcile state.

## Prompt 6: JSON and CSV

> Implement only Step 6 of `IMPLEMENTATION_PLAN.md`. Add schema-version-1 JSON and fixed long-form CSV exactly as defined under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. Emit no ANSI or diagnostics on stdout. Preserve deterministic output and the complete 0/1/2/3/4 contract, including 4 for unique-cardinality exhaustion. Add golden fixtures, run the listed checks, report evidence, and reconcile state.

## Prompt 7: End-to-End CLI

> Implement only Step 7 of `IMPLEMENTATION_PLAN.md`. Connect finite file/stdin reading, parsing, aggregation, renderer selection, stderr summaries, expected errors, and quiet broken-pipe handling. Add end-to-end proof for every code: 0 success, 1 unexpected runtime/output failure, 2 invalid use, 3 unreadable/no-valid input, and 4 unique-cardinality exhaustion with empty stdout. Run the listed integration and pipeline checks, report evidence, and reconcile state.

## Prompt 8: Acceptance and Release Readiness

> Implement only Step 8 of `IMPLEMENTATION_PLAN.md`. Add deterministic performance tooling, run lint, format, types, full tests, coverage, package build/check, clean-install smoke test, and the documented 1 GB benchmark. Verify the complete 0/1/2/3/4 contract remains intact, with 4 meaning unique-cardinality exhaustion. Do not claim the performance target without a real reference-laptop run. Freeze the exact candidate and complete the current Verification Loop risk route before accepting it. Report real evidence and reconcile state.

## Review Checklist for Every Step

- The active scope and WIP=1 state match the numbered step.
- No unapproved product surface or dependency was added.
- P0 behavior is traceable to a PRD acceptance criterion.
- Tests fail closed and commands actually ran.
- JSON/CSV stdout remains machine-clean where relevant.
- All five exit codes retain their single documented meanings.
- Documentation changes accompany contract changes.
- Exact-candidate verification evidence is current before acceptance.
