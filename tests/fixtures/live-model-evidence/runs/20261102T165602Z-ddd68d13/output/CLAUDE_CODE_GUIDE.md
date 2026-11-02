# Claude Code Implementation Guide: nginx-stream-report

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts for future implementation sessions. It does not authorize product-code work in the blueprint session. Run one step at a time (WIP=1), inspect existing changes first, and do not advance on red tests.

The public exit-code contract is always `0/1/2/3/4`: `0` success, `1` unexpected internal failure, `2` CLI usage/validation error, `3` input or strict-parse error, and `4` unique-cardinality exhaustion. Never omit, reuse, or remap code `4`.

## Session Bootstrap Prompt

```text
Read CLAUDE.md, PROJECT_ARCHITECTURE.md, PRD.md, and the current step in IMPLEMENTATION_PLAN.md. Inspect the workspace and preserve unrelated changes. Implement only that step, add its specified tests, and run every verification command that is available. Report exact pass/fail results and any skipped check. Do not publish, push, deploy, or contact external services.
```

## Step 1 Prompt — Package and Contracts

```text
Execute STEP 1 from IMPLEMENTATION_PLAN.md only. Create the Python 3.11 src-layout package, console entry point, Click help/version shell, and all dataclasses exactly as PROJECT_ARCHITECTURE.md specifies. Add model and CLI tests. Do not implement parsing or aggregation. Run install, pytest, help, lint, and type checks that apply; stop if any fail.
```

## Step 2 Prompt — Streaming Parser

```text
Execute STEP 2 only. Implement line iteration for file/stdin and the standard nginx combined-log parser. Never materialize the whole input. Cover IPv4, IPv6, timezones, quotes, dash bytes, and malformed records with fixtures and tests. Keep error classification compatible with eventual exit code 3. Run the step checks plus all existing tests.
```

## Step 3 Prompt — Aggregation

```text
Execute STEP 3 only. Implement one-pass counters and the exact User-Agent set with a configurable cap. Raise the typed exhaustion error before inserting cap+1; do not approximate or emit partial results. Cover status boundaries and cap boundaries. Preserve the eventual exit code 4 mapping for unique-cardinality exhaustion. Run targeted and full tests.
```

## Step 4 Prompt — Final Report

```text
Execute STEP 4 only. Implement deterministic top-10 ranking, 24 ordered hour buckets, and safe empty-input behavior. Hourly percentage must be 100 × hourly_request_count / total_valid_requests. Keep unrounded internal values and apply two-decimal policy only at serialization boundaries. Add tie, formula, empty, and rounding tests; run all existing tests.
```

## Step 5 Prompt — Renderers

```text
Execute STEP 5 only. Implement Rich text, JSON, and normalized CSV renderers from the same Report object. Escape log-derived terminal values, keep ANSI out of JSON/CSV, use Python csv quoting, and make output deterministic. Add golden and hostile-value tests, then run targeted and full suites.
```

## Step 6 Prompt — CLI and Exit Contract

```text
Execute STEP 6 only. Connect the pipeline in Click and implement all documented options. Enforce mutually exclusive output modes and stdout/stderr separation. Add subprocess coverage for every exit code 0/1/2/3/4, with code 4 reserved for unique-cardinality exhaustion. Known failures must not print tracebacks. Run integration, JSON validation, CSV validation, and the full suite.
```

## Step 7 Prompt — Performance

```text
Execute STEP 7 only. Add deterministic benchmark generation, a metadata-recording benchmark runner, and a small performance smoke test. Generate large fixtures outside Git. Measure before optimizing, preserve all contracts, and report elapsed time plus peak RSS and reference hardware. The gate is 1 GB under 30 seconds and at most 256 MiB RSS on the recorded laptop.
```

## Step 8 Prompt — Release Candidate

```text
Execute STEP 8 only. Complete local release documentation and artifact checks without publishing. Ensure README documents all metrics, formulas, schemas, privacy behavior, and exit codes 0/1/2/3/4. Run lint, types, full coverage, build, artifact validation, clean-wheel smoke, and the recorded performance gate. Do not push or upload; those external actions need explicit human approval.
```

## Review Prompt

```text
Review the final candidate against PRD.md and PROJECT_ARCHITECTURE.md. Trace every P0 acceptance criterion to a test and every CLI error class to 0/1/2/3/4. Look specifically for whole-file reads, nondeterministic ties, ANSI leakage, Rich markup injection, incorrect 4xx/5xx boundaries, percentage scaling mistakes, incomplete stdout on failure, and cardinality cap off-by-one errors. Report findings with file and line evidence; do not modify files unless explicitly asked.
```

## End-of-Session Checklist

- Record commands actually run and their outcomes.
- Update the step status in `CLAUDE.md` only when its checks pass.
- Keep discovered out-of-scope work in a backlog instead of expanding the active step.
- At the end of each session or meaningful block of work, save context through `/session-save`.

