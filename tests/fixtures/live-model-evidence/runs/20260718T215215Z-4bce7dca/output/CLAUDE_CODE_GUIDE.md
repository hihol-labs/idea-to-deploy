# Claude Code Guide: nginx-stream-report

Use these prompts one at a time after the planning documents are accepted. They intentionally generate no code during the blueprint phase. Begin every session by reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the active step in `IMPLEMENTATION_PLAN.md`.

## Prompt 1 — Package and CLI contract

> Execute Implementation Plan Step 1 only. Preserve WIP=1. Create the package metadata and Click command contract, without parser/aggregation implementation. Write tests first for help, version, conflicting formats, and invalid source combinations. Run the exact Step 1 verification commands and record evidence; update project state before stopping.

## Prompt 2 — Models, fixtures, benchmark protocol

> Execute Step 2 only. Define the dataclasses from Architecture §5, sanitized correctness fixtures, a deterministic benchmark generator/protocol, and the worst-case key-memory calibration. Do not implement parsing or metrics. Ensure no fixture is represented as production data. Lock separate map defaults to the 192 MiB projected envelope, run model/calibration/generator smoke checks, then reconcile state.

## Prompt 3 — Streaming source and parser

> Execute Step 3 only, using the exact byte/encoding/common-combined grammar in Architecture §5. Test first for line/key limits, UTF-8 replacement, quoting, escapes, timestamps, malformed tokens, file/stdin equivalence, and prohibition of full-file reads. Use only the minimal slotted hot-path record. Run the Step 3 pytest and mypy commands.

## Prompt 4 — Four metric aggregations

> Execute Step 4 only. Implement the exact semantics from Architecture §6 against an independent test oracle. Include deterministic ties, all 24 hours, the unique-UA denominator, status boundaries, empty input, and count/byte fail-closed behavior. Do not add approximation. Prove >=90% branch coverage, then run the source/parser/aggregator-only 100–250 MB throughput/RSS gate before renderer work; stop and profile below 34 MiB/s or above 256 MiB RSS.

## Prompt 5 — JSON and CSV

> Execute Step 5 only. Implement both machine formats from Architecture §8 from the shared Report model. Keep stdout parseable, include schema_version, and preserve exact decoded values with standard JSON/CSV encoding. Do not silently prefix formula-like CSV cells; document spreadsheet risk. Test semantic equivalence and run the JSON pipe smoke command.

## Prompt 6 — Rich terminal integration

> Execute Step 6 only. Add the Rich terminal renderer and connect the finite input pipeline in cli.py. Color must be TTY-aware and absent for --no-color, JSON, CSV, and non-TTY stdout. Complete exit-code/stderr tests, then manually inspect the no-color fixture report.

## Prompt 7 — Follow mode

> Execute Step 7 only. Add bounded-poll follow behavior for regular files, complete-line handling, terminal-only Rich Live refresh, incompatible machine/non-TTY validation, and Ctrl-C final-snapshot semantics. Do not silently claim log-rotation support; document/test its current limitation. Avoid slow/flaky sleeps by injecting poll/clock seams. Run the focused and full suites.

## Prompt 8 — Release evidence

> Execute Step 8 only. Finish user documentation and packaging metadata, then run Ruff, mypy, pytest/coverage, the reproducible 1 GB benchmark, dependency/security checks, wheel/sdist build, fresh-environment install, and terminal/JSON/CSV smoke tests. Record exact hardware and peak RSS. If the 30-second target fails, mark recovery required and profile; do not weaken the target or claim completion.

## Review prompt

> Review the candidate against PRD P0 criteria and Architecture output/security/performance contracts. Report Critical, Important, and Minor findings with file/line evidence. Reject any database, HTTP API, telemetry, full-file read, silent approximation, stdout diagnostic contamination, unstable tie ordering, or undocumented schema drift.

## Session handoff prompt

> Reconcile the active Idea to Deploy unit: record commands and outcomes, changed paths, unresolved risks, the next single action, and current specification links. Save context through /session-save. Do not mark a step complete without the named evidence.
