# Claude Code Implementation Guide: nginx-stream-report

## Purpose

Use this guide after the blueprint is accepted to implement one step at a time. The durable product source of truth is `PRD.md`; `PROJECT_ARCHITECTURE.md` owns technical contracts; `IMPLEMENTATION_PLAN.md` owns ordering. Preserve WIP=1, change the specification before changing promised behavior, and do not begin the next step until the current exact candidate has the evidence required by `.itd/VERIFICATION_CONTRACT.json`.

This guide does not authorize implementation during the blueprint session.

## Global Guardrails for Every Prompt

- Use Python 3.11, Click, Rich, and dataclasses; keep the package pip-installable.
- Keep one local process and streaming input. Never use a whole-file read or retain parsed request rows.
- Add no authentication, database, HTTP API, server, cloud, Docker, or Kubernetes component.
- Keep stdout report-only and stderr diagnostic-only. JSON/CSV never contain ANSI escapes.
- Preserve exact metric semantics, especially `100 × hourly_request_count / total_valid_requests`.
- Preserve the full exit mapping: `0` success, `1` input I/O failure, `2` CLI usage error, `3` parse/data failure, `4` unique-cardinality exhaustion.
- Code 4 must emit no partial report. Do not silently approximate or truncate distinct User-Agents.
- Use tests and current verification evidence; do not declare success based on inspection alone.

## Prompt 1 — Package and CLI Skeleton

> Implement only Step 1 of `IMPLEMENTATION_PLAN.md`. Read `PRD.md` and the “CLI Interface” and “Components and Source Layout” sections of `PROJECT_ARCHITECTURE.md`. Create `pyproject.toml`, the package entry points, the Click option surface, and focused CLI tests. The command need not parse data yet, but `--help`, `--version`, format mutual exclusion, and invalid option values must be tested. Use Python 3.11, Click, Rich, src layout, and pip packaging. Run the exact Step 1 verification commands, record evidence in the repository's Idea to Deploy state, and stop without starting Step 2.

## Prompt 2 — Models and Failures

> Implement only Step 2 of `IMPLEMENTATION_PLAN.md` on top of the accepted Step 1 candidate. Define the dataclasses and typed exceptions in the documented files. Keep report data renderer-independent and represent percentages without premature display rounding. Wire typed failures to the complete `0/1/2/3/4` contract without implementing the parser or renderers. Add invariant and error-mapping tests, run Step 2 verification, reconcile Idea to Deploy state, and stop.

## Prompt 3 — Combined-Log Parser

> Implement only Step 3 of `IMPLEMENTATION_PLAN.md`. Follow the “Parsing Contract” exactly. Parse one nginx combined line into the minimal `ParsedRequest`; support IPv4/IPv6 strings, timezone-bearing timestamps, escaped quoted content, and the stated malformed conditions. Never log a full sensitive input line. Create the specified fixture and focused tests, including strict/non-strict-ready error information, run both Step 3 verification commands, record evidence, and stop before aggregation.

## Prompt 4 — Streaming Aggregation

> Implement only Step 4 of `IMPLEMENTATION_PLAN.md`. Aggregate requests as a stream into exact IP, 4xx/5xx target, 24-hour, and User-Agent data. Calculate hourly percentages with `100 × hourly_request_count / total_valid_requests` and unique User-Agent share with the PRD formula. Enforce the configured exact User-Agent ceiling before insertion; exceeding it raises the typed code-4 failure and cannot create a report. Add tests for ties, bounds, empty values, error statuses, formulas, and ceiling exhaustion. Run Step 4 verification, attach evidence, and stop.

## Prompt 5 — Rich Terminal Output

> Implement only Step 5 of `IMPLEMENTATION_PLAN.md`. Render the shared `Report` through Rich as four readable sections plus totals. Escape or disable markup for log-derived strings. Honor `--no-color` and non-TTY output without changing metric values. Add and review a no-color golden fixture and the stated renderer tests. Run Step 5 verification, record current-candidate evidence, and stop.

## Prompt 6 — JSON and CSV Output

> Implement only Step 6 of `IMPLEMENTATION_PLAN.md`. Add schema-versioned JSON and normalized RFC 4180 CSV renderers using standard-library encoders. Do not recompute metrics or localize numbers. Ensure deterministic order, one trailing newline, and zero ANSI escapes. Add parse-backed golden tests that compare semantics with the terminal report. Run all Step 6 verification commands, record evidence, and stop.

## Prompt 7 — End-to-End CLI

> Implement only Step 7 of `IMPLEMENTATION_PLAN.md`. Connect file/stdin streaming, parser, aggregate state, renderer selection, strict behavior, diagnostics, and typed exception mapping in `cli.py`. Exercise all exit codes: 0 successful complete report; 1 input I/O failure; 2 invalid CLI usage; 3 parse/data failure or no valid records; 4 unique-cardinality exhaustion with no partial output. Test file/stdin parity, stdout/stderr isolation, malformed summaries, broken pipe behavior, and all formats. Run Step 7 verification, reconcile state, and stop.

## Prompt 8 — Performance and Package Evidence

> Implement only Step 8 of `IMPLEMENTATION_PLAN.md`. Create a deterministic streaming 1 GB fixture generator and benchmark harness without committing the large generated file. Record input size/seed, hardware, Python version, wall time, and peak RSS. Build wheel and sdist, install the wheel into a clean Python 3.11 environment, and smoke-test the console command. Run the complete test suite and the documented under-30-second/under-256-MiB benchmark. Freeze and adjudicate the exact candidate using the repository verification contract. If any gate fails, leave the unit in recovery rather than claiming completion.

## Handoff Checklist

- [ ] The active step alone was implemented and its listed files match the architecture.
- [ ] Its verification commands actually ran and their outputs were recorded.
- [ ] Product behavior still matches `PRD.md` and the complete `0/1/2/3/4` contract.
- [ ] No prohibited service, persistence, deployment, or approximation was introduced.
- [ ] `.itd-memory/` state identifies the current unit, evidence, and explicit next action.
- [ ] Completion, if claimed, is backed by a current revalidated adjudication receipt.

At the end of every implementation session or significant block, save context through `/session-save` as required by `CLAUDE.md`.
