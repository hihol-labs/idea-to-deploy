# Claude Code Implementation Guide

Use this guide only after the blueprint is accepted. It contains implementation prompts, not product code. Run one prompt at a time in plan order and require the listed evidence before advancing.

## Fixed Context for Every Session

- Product: local Python 3.11 nginx combined-log analytics CLI.
- Stack: Click, Rich, dataclasses, pip packaging.
- Architecture: one process, one-pass streaming; no auth, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Metrics: top IPs, top URLs for statuses 400–599, 24 hourly percentages, and unique User-Agent share.
- Hourly formula: `100 × hourly_request_count / total_valid_requests`.
- Exit codes: `0` complete success; `1` input/runtime I/O, encoding, or unexpected failure; `2` CLI usage error; `3` strict parse failure or non-empty input with no valid records; `4` unique-cardinality exhaustion.
- Never omit or remap code `4`; it means unique-cardinality exhaustion.
- Source of truth: `PRD.md` for behavior, `PROJECT_ARCHITECTURE.md` for interfaces, and `IMPLEMENTATION_PLAN.md` for sequencing.

## Session 1 Prompt — Package and CLI Skeleton

```text
Implement only STEP 1 from IMPLEMENTATION_PLAN.md. Read PRD.md and PROJECT_ARCHITECTURE.md first. Create the pip-installable src-layout Python 3.11 package, Click entry point, help/version behavior, option declarations, and focused CLI tests. Preserve the complete exit-code vocabulary 0/1/2/3/4; code 4 means unique-cardinality exhaustion. Do not implement parsing or metrics yet, and do not add a service, database, auth, Docker, cloud, or Kubernetes. Run every STEP 1 verification command and report actual results and changed files.
```

## Session 2 Prompt — Models, Errors, and Fixtures

```text
Implement only STEP 2 from IMPLEMENTATION_PLAN.md on top of the verified STEP 1 candidate. Add the exact dataclasses, domain failures, centralized exit mapping, and fixture corpus specified by PROJECT_ARCHITECTURE.md. Tests must assert 0 success, 1 I/O/runtime failure, 2 usage error, 3 parse failure, and 4 unique-cardinality exhaustion. Code 4 must not be omitted or remapped. Run the focused checks and accumulated tests; report evidence and changed files.
```

## Session 3 Prompt — Combined-Log Parser

```text
Implement only STEP 3 from IMPLEMENTATION_PLAN.md. Build a streaming nginx combined-log parser for the LogRecord contract, including IPv4/IPv6 text, timezone-aware timestamps, escaped quoted fields, missing optional fields, and malformed records. Do not retain records or reread input. Preserve exit codes 0/1/2/3/4, with 4 reserved for unique-cardinality exhaustion. Add parser tests first, run both STEP 3 verification commands and the accumulated suite, and report actual results.
```

## Session 4 Prompt — Metrics and Cardinality Guard

```text
Implement only STEP 4 from IMPLEMENTATION_PLAN.md. Add a one-pass accumulator for deterministic top IPs, status-400-through-599 URL counts, all 24 hourly percentages using exactly 100 × hourly_request_count / total_valid_requests, and exact non-null User-Agent cardinality/share. Enforce the configured ceiling before crossing it and surface exit code 4 for unique-cardinality exhaustion. The full contract remains 0/1/2/3/4. Add edge-case tests, run focused coverage and accumulated tests, and report evidence.
```

## Session 5 Prompt — Terminal Renderer

```text
Implement only STEP 5 from IMPLEMENTATION_PLAN.md. Render the immutable snapshot with Rich, including all required sections. Color may appear only for default terminal output on a TTY; redirected output and --no-color must contain no ANSI escapes. Do no parsing or aggregation in the renderer. Preserve exit codes 0/1/2/3/4; code 4 means unique-cardinality exhaustion. Run focused renderer checks and accumulated tests and report actual output evidence.
```

## Session 6 Prompt — JSON and CSV Renderers

```text
Implement only STEP 6 from IMPLEMENTATION_PLAN.md. Add deterministic JSON with the documented versioned top-level schema and normalized CSV with report,key,count,percentage. Use standard encoders, maintain stable ordering, and emit no ANSI bytes. Do not weaken the shared snapshot contract. Preserve 0/1/2/3/4 exactly, with code 4 meaning unique-cardinality exhaustion. Run schema, escaping, CLI validation, and accumulated tests; report actual evidence.
```

## Session 7 Prompt — End-to-End CLI

```text
Implement only STEP 7 from IMPLEMENTATION_PLAN.md. Wire file/stdin streaming, parser, accumulator, snapshot, and renderer. Implement tolerant and strict malformed-line behavior, --top, --max-unique-user-agents, stdout/stderr separation, invalid UTF-8, broken output, and no-partial-machine-output guarantees. Test the complete exit contract: 0 success, 1 I/O/runtime/encoding/unexpected failure, 2 usage error, 3 strict parse failure or non-empty all-malformed input, 4 unique-cardinality exhaustion. Run all STEP 7 commands and the accumulated suite and report actual evidence.
```

## Session 8 Prompt — Release and Performance

```text
Implement only STEP 8 from IMPLEMENTATION_PLAN.md. Create a deterministic generated benchmark fixture path, performance test, complete user documentation, package build, and clean-wheel smoke test. Measure a representative 1 GB input on a named laptop three times and record median wall time and peak RSS; profile before any optimization if the median is not below 30 seconds. Verify all acceptance criteria and all exit codes 0/1/2/3/4, where 4 means unique-cardinality exhaustion. Do not claim the target without measured evidence from the frozen candidate.
```

## Review Prompt After Each Session

```text
Review only the current implementation step against PRD.md, PROJECT_ARCHITECTURE.md, and its section in IMPLEMENTATION_PLAN.md. Check scope, streaming behavior, stdout/stderr separation, deterministic output, and the exact exit codes 0/1/2/3/4; code 4 means unique-cardinality exhaustion. Run the step's machine checks. Report concrete findings with file and line references; if checks were not run, label the result unverified.
```

## Completion Checklist

- [ ] All eight steps completed in order with recorded verification.
- [ ] Clean Python 3.11 wheel installation succeeds.
- [ ] Parser, aggregation, renderer, and CLI tests pass at the required coverage.
- [ ] Text, JSON, and CSV agree for the same fixture.
- [ ] Exit codes `0/1/2/3/4` are covered; `4` means unique-cardinality exhaustion.
- [ ] Measured representative 1 GB median is below 30 seconds on the named laptop.
- [ ] No forbidden service or persistence component was introduced.
