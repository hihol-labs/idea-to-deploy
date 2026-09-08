# Claude Code Implementation Guide: nginx-insights

## 1. How to Use This Guide

Execute one numbered prompt at a time in the order shown, keeping WIP at one. Before editing, read `PRD.md`, the relevant `PROJECT_ARCHITECTURE.md` sections, and the matching `IMPLEMENTATION_PLAN.md` step. Do not implement scope marked P2 or Won't unless the specification is changed first. Each prompt requires actual command output before the step can be marked complete.

Across every step, preserve the exit-code contract: `0` success; `1` input/output or unexpected operational failure; `2` usage/configuration error; `3` input with zero valid requests; `4` unique-cardinality exhaustion. The exact phrase for code 4 is: unique-cardinality exhaustion.

## 2. Global Implementation Prompt

> Implement only the requested nginx-insights plan step. Use Python 3.11, Click, Rich, and dataclasses. Preserve a single-process, stateless, one-pass pipeline with no database, HTTP API, server, auth, cloud, Docker requirement, or Kubernetes. Keep report data on stdout and diagnostics on stderr. Never retain raw lines. Add or update tests before declaring the step complete, run the specified checks, and report real results. If behavior differs from PRD.md, stop and update the specification first.

## 3. Step Prompts

### Prompt 1 — Package skeleton

> Execute `IMPLEMENTATION_PLAN.md` Step 1. Create only the package metadata, import skeleton, console entry point, dataclasses, error taxonomy, and help/version tests named there. Make the exit constants explicit for all codes `0/1/2/3/4`. Run the three Step 1 verification commands and summarize changed files and evidence.

### Prompt 2 — Parser and normalization

> Execute Step 2. Implement declared common/combined nginx parsing and URL-path normalization in the specified files. Treat malformed records as typed invalid results and log fields as untrusted data. Cover IPv4, IPv6, timezone offsets, dashes, escaped quotes, bad timestamps/status/request fields, and query/fragment removal. Run only Step 2 checks plus any directly affected fast tests.

### Prompt 3 — Streaming aggregation

> Execute Step 3. Build exact one-record-at-a-time aggregation with no raw-record collection. Implement deterministic top-10 ranking, 4xx/5xx status boundaries, 24 hourly buckets, and unique User-Agent share. Hourly percentage must use `100 × hourly_request_count / total_valid_requests`. Enforce the configured UA cap before inserting the overflowing key and cover code 4. Run Step 3 verification.

### Prompt 4 — Inputs and exit behavior

> Execute Step 4. Support stdin, `-`, and multiple files in argument order; close only owned streams. Wire the parser and aggregator without renderer leakage. Test and preserve exactly: 0 success, 1 I/O/operational failure, 2 usage/configuration error, 3 no valid records, 4 unique-cardinality exhaustion. Emit no partial machine report on failure. Run Step 4 verification.

### Prompt 5 — JSON

> Execute Step 5. Implement one versioned JSON document using the exact keys and types in `PROJECT_ARCHITECTURE.md`. Keep full numeric precision and deterministic list order. Ensure warnings stay on stderr. Add golden and CLI checks, then run both Step 5 commands.

### Prompt 6 — CSV

> Execute Step 6. Implement the exact long-form CSV header `metric,rank,key,count,percentage` with the standard CSV writer and deterministic ordering. Enforce `--json`/`--csv` exclusivity as exit 2. Add quoting and parser round-trip tests, then run both Step 6 commands.

### Prompt 7 — Terminal

> Execute Step 7. Build four Rich report sections and totals, rendering all log-derived values literally. Implement TTY auto-color plus explicit color control, with configuration conflicts exiting 2. Verify no escape sequences under `--no-color`; run both Step 7 commands.

### Prompt 8 — End-to-end quality

> Execute Step 8. Add cross-renderer agreement tests, injection-oriented fixtures, mixed-validity behavior, and exhaustive `0/1/2/3/4` exit tests. Confirm machine stdout never contains diagnostics and failures never contain partial reports. Run the coverage and compile checks; do not waive the 90% critical-module threshold.

### Prompt 9 — Performance

> Execute Step 9. Add deterministic benchmark generation and a three-trial runner without committing generated logs. First record baseline wall time and peak RSS, then optimize only measured hot spots. Re-run golden correctness tests after every hot-path change. Accept only a recorded median below 30 seconds for 1 GB on the documented reference laptop.

### Prompt 10 — Release readiness

> Execute Step 10. Update user documentation from verified behavior, add license/changelog, build wheel and sdist, inspect artifacts, run the full suite, and install the wheel in a clean Python 3.11 virtual environment. Do not publish externally. Record actual results and any remaining limitation.

## 4. Review Prompt

> Review the exact candidate against `PRD.md` and `PROJECT_ARCHITECTURE.md`. Check parser correctness, status boundaries, percentage denominators, stable JSON/CSV schemas, literal terminal rendering, memory growth, stdout/stderr isolation, and all five exit codes. Treat omitted code 4 or partial output on failure as blocking. Cite file/line evidence and run targeted tests; do not infer success from prose.

## 5. Completion Checklist

- [ ] P0 behavior and output schemas match `PRD.md`.
- [ ] The full exit-code contract `0/1/2/3/4` is tested.
- [ ] The 1 GB median is below 30 seconds on the recorded laptop profile.
- [ ] Critical modules meet the 90% coverage threshold.
- [ ] Wheel installation and console entry point work on Python 3.11.
- [ ] No database, HTTP API, auth, server, cloud, or Kubernetes dependency exists.
- [ ] README and specification reflect verified behavior.
- [ ] Session state is saved according to `CLAUDE.md`.
