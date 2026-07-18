# Claude Code Guide: Nginx Stream Analyzer

This guide turns [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) into bounded implementation prompts. Run one step at a time (WIP=1). Before each step, read [PRD.md](PRD.md), the cited architecture sections, and the repository Idea to Deploy contracts. Do not mark a step complete without the listed runtime/static evidence.

## Global Prompt Prefix

Prepend this to every step prompt:

> Implement only the named step from IMPLEMENTATION_PLAN.md. Preserve the approved single-process, one-pass CLI architecture: no database, HTTP API, auth, server, cloud, Docker, or Kubernetes. Use Python 3.11, Click, Rich, and dataclasses. Do not change output semantics without first updating PRD.md and PROJECT_ARCHITECTURE.md. Keep stdout machine-readable and stderr diagnostic-only. Run the step’s verification commands and report exact evidence; anything not run is NOT VERIFIED. End by updating the step status in CLAUDE.md and saving session context with `/session-save`.

## Prompt 1: Package Skeleton and CLI Contract

> Execute Step 1 only. Create `pyproject.toml`, `src/nginx_stream_analyzer/__init__.py`, `src/nginx_stream_analyzer/cli.py`, and the initial `tests/test_cli.py`. Implement the documented Click surface and exit behavior, but do not implement parsing, aggregation, or final renderers. Verify editable install, help, and CLI tests. Stop after evidence and handoff.

## Prompt 2: Domain Models and Contract Fixtures

> Execute Step 2 only. Define the dataclasses and representative/golden fixtures exactly as PROJECT_ARCHITECTURE.md Sections 5 and 9 specify. Write aggregation-contract tests without implementing aggregation. Make ties, empty input, all 24 hours, and the User-Agent ratio explicit. Validate test collection and JSON syntax. Stop after evidence and handoff.

## Prompt 3: Streaming Parser

> Execute Step 3 only. Implement strict nginx combined-format line parsing in `parser.py` and comprehensive parser tests. Treat input as untrusted, do not retain/echo malformed lines, support IPv4/IPv6 and offset-aware timestamps, and avoid whole-file reads. Run parser tests and lint. Stop after evidence and handoff.

## Prompt 4: One-Pass Aggregation

> Execute Step 4 only. Implement exact counters, the distinct User-Agent set, 24 hour buckets, deterministic top-10 selection, malformed-line accounting, and orchestration. Do not add a database, temporary files, multiprocessing, approximation, or output formatting. Run aggregation tests and coverage. Stop after evidence and handoff.

## Prompt 5: JSON Renderer

> Execute Step 5 only. Implement the stable JSON document in PROJECT_ARCHITECTURE.md with UTF-8, all 24 hour rows, finite ratios, and no ANSI output. Wire only enough CLI behavior to exercise `--json`; do not implement CSV or Rich tables. Run renderer tests and pipe output through `json.tool`. Stop after evidence and handoff.

## Prompt 6: CSV Renderer

> Execute Step 6 only. Implement the normalized four-column CSV contract using the standard library, including correct quoting and documented formula-prefix neutralization for log-derived cells. Add round-trip tests. Do not alter JSON keys or metric semantics. Run CSV-specific tests and a CLI smoke command. Stop after evidence and handoff.

## Prompt 7: Terminal UX and Failures

> Execute Step 7 only. Implement Rich terminal sections, TTY-aware color, `NO_COLOR`, `--no-color`, renderer selection, stdout/stderr separation, safe markup handling, unreadable-file behavior, partial malformed input, and broken-pipe behavior. Run the CLI and renderer suites and a no-color manual smoke test. Stop after evidence and handoff.

## Prompt 8: Quality, Benchmark, and Release

> Execute Step 8 only. Add performance-smoke coverage, the out-of-repository benchmark generator, final developer/user documentation, lint/coverage configuration, and build verification. Run lint, tests with ≥90% coverage, build, and clean-install checks. Generate the documented 1 GB fixture outside Git, run one warm-up and three timed installed-CLI measurements, validate counts against the oracle, and record environment, median time, and peak RSS. Never claim the <30 second gate if measurement is absent. Stop after evidence and handoff.

## Review Prompt

> Review the completed step against PRD acceptance criteria, PROJECT_ARCHITECTURE.md, the active scope lock, and its verification commands. Look specifically for whole-file reads, unstable ties, 400/599 boundary bugs, stdout contamination, unsafe Rich markup, CSV formula injection, sensitive malformed-line diagnostics, and unmeasured performance claims. Return findings ordered by severity with file/line evidence and an accepted or revision-required verdict.

## Handoff Checklist

- [ ] Only the active implementation step changed.
- [ ] Spec changes, if any, were made before behavior changes and reconciled across documents.
- [ ] Verification commands ran with captured output.
- [ ] No placeholder, debug output, generated benchmark log, or secret entered Git.
- [ ] `CLAUDE.md` status and next action are current.
- [ ] Session context was saved through `/session-save`.
