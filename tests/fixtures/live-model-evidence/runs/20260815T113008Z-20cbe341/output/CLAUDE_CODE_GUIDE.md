# Claude Code Guide: Nginx Stream Analyzer

## Purpose

This guide contains execution-ready prompts for implementing `IMPLEMENTATION_PLAN.md` one WIP unit at a time. It does not authorize implementation during the blueprint session. Before using a prompt, read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, the active `.itd/` contracts, and current `.itd-memory/` state.

The specification is the source of truth. If a requested behavior conflicts with the PRD or architecture, update and review the specification before changing code.

## Non-Negotiable Contract

All implementation sessions preserve the full exit-code mapping:

| Code | Meaning |
|---:|---|
| 0 | Complete success |
| 1 | Input/output failure |
| 2 | CLI usage failure |
| 3 | Zero valid supported records |
| 4 | Unique-cardinality exhaustion for distinct IP, error URL, or User-Agent state |

The complete contract is `0/1/2/3/4`. Code 4 must never be omitted, converted to code 1 or 3, or replaced with silent approximation.

For every step: keep processing single-process and streaming; add no authentication, database, HTTP API, server, cloud, Docker deployment, or Kubernetes; do not retain raw records; use Python 3.11, Click, Rich, and dataclasses; run the step's tests; and use the repository Verification Loop on the exact staged candidate before accepting completion.

## Prompt 1: Package Skeleton and CLI Boundary

```text
Implement only Step 1 from IMPLEMENTATION_PLAN.md.

Read CLAUDE.md, PRD.md, and PROJECT_ARCHITECTURE.md first. Reconcile the active Idea to Deploy unit and scope lock before editing. Create only pyproject.toml, src/nginx_stream_analyzer/__init__.py, src/nginx_stream_analyzer/cli.py, src/nginx_stream_analyzer/errors.py, and the Step 1 portions of tests/test_cli.py.

Expose nginx-stream-analyzer with INPUT, --json, --csv, --no-color, --version, and --help. Keep analysis behind a clean internal boundary; do not implement later steps. Preserve the complete exits: 0 success, 1 I/O, 2 usage, 3 zero valid records, 4 unique-cardinality exhaustion.

Run the exact Step 1 verification commands, inspect the diff for scope, then freeze and verify the exact staged candidate under the current Idea to Deploy risk route. Report evidence and the next step; do not claim completion from prose.
```

## Prompt 2: Models, Input, and Fixtures

```text
Implement only Step 2 from IMPLEMENTATION_PLAN.md on top of the verified Step 1 candidate.

Create models.py, input.py, the three named small fixtures, and test_input.py. Use frozen dataclasses for the stable report boundary. Read from one file or stdin as an iterator; never seek, buffer the whole file, or retain raw records. Surface input failures through code 1.

Do not add parsing or aggregation. Preserve all exits 0/1/2/3/4, including reserved code 4 for unique-cardinality exhaustion. Run the Step 2 verification commands and the existing Step 1 tests, then use the exact-candidate Verification Loop and current risk checker before accepting.
```

## Prompt 3: Supported Nginx Parser

```text
Implement only Step 3 from IMPLEMENTATION_PLAN.md.

Create parser.py and test_parser.py for the declared nginx combined/common-compatible fields. Parse client IP, timezone-aware timestamp, request target, status, and User-Agent. Never include a full raw line in a diagnostic. Keep query strings in ranking keys and treat '-' User-Agent deterministically.

Do not aggregate or render. Preserve exits 0 success, 1 I/O, 2 usage, 3 zero valid records, and 4 unique-cardinality exhaustion. Run parser coverage and all earlier tests, then freeze and adjudicate the exact staged candidate using the repository Verification Loop.
```

## Prompt 4: Streaming Aggregation

```text
Implement only Step 4 from IMPLEMENTATION_PLAN.md.

Create aggregate.py and test_aggregate.py. In one pass, update valid/malformed totals, IP counts, 4xx/5xx request-target counts, a fixed 24-hour array, and an exact User-Agent set. Do not retain AccessRecord objects. Enforce hard limits before inserting a new distinct IP, error URL, or User-Agent.

Top 10 ordering is count descending then key ascending. Compute hourly percentage with the exact formula `100 × hourly_request_count / total_valid_requests`. Zero valid records maps to 3. Any distinct-state limit maps to 4 without partial output. Preserve the entire 0/1/2/3/4 contract.

Run the Step 4 boundary, ordering, formula, and coverage tests plus all prior tests. Freeze and adjudicate the exact staged candidate before accepting.
```

## Prompt 5: Rich Terminal Output

```text
Implement only Step 5 from IMPLEMENTATION_PLAN.md.

Create the renderer package boundary and text.py, then connect default text selection in cli.py. Render totals and the four required sections. Enable color only for interactive text unless --no-color is set. Treat every log-derived value as untrusted plain text; escape markup and terminal control behavior.

Do not add JSON or CSV yet. Preserve 0/1/2/3/4 exactly: success, I/O, usage, zero-valid-data, unique-cardinality exhaustion. Run focused text/color/security cases and the full existing suite. Use the exact-candidate Verification Loop and current risk-tier adjudication before accepting.
```

## Prompt 6: JSON and CSV Output

```text
Implement only Step 6 from IMPLEMENTATION_PLAN.md.

Create json.py and csv.py renderers and the named golden files. JSON must emit schema_version 1 and the architecture-defined fields. CSV must emit section,rank,key,count,percentage in the fixed section order and neutralize spreadsheet formula prefixes. Neither format may contain ANSI sequences. Keep diagnostics on stderr.

The hourly percentage is `100 × hourly_request_count / total_valid_requests`. Preserve and test all exits 0/1/2/3/4; code 4 means unique-cardinality exhaustion and must not be remapped. Run focused renderer, JSON parser, CSV reader, golden, and prior tests. Freeze and adjudicate the exact staged candidate.
```

## Prompt 7: End-to-End Hardening and Packaging

```text
Implement only Step 7 from IMPLEMENTATION_PLAN.md.

Complete CLI orchestration, tests/test_security.py, installed-wheel verification, stdout/stderr separation, file/stdin parity, malformed mixes, and hostile-value tests. Keep orchestration thin; parser, aggregation, and renderer logic remain in their modules. Do not add services, persistence, or network behavior.

Exercise the complete exit matrix: 0 full success; 1 input/output failure; 2 usage failure; 3 no valid supported records; 4 unique-cardinality exhaustion. Never emit a partial success report on exits 1, 3, or 4.

Run the full suite with coverage, build/install in a clean temporary environment, inspect dependency scope, and apply the exact-candidate Verification Loop and risk checker before accepting.
```

## Prompt 8: Performance Qualification

```text
Implement only Step 8 from IMPLEMENTATION_PLAN.md.

Create the deterministic benchmark generator, CI-scale performance tests, and docs/BENCHMARK.md. Generate the 1 GB fixture outside Git. Record CPU, storage, OS, Python version, command, wall time, peak RSS, generator seed, and output mode. First measure; profile only on a miss; do not weaken parsing, exactness, safety limits, or output contracts to improve speed.

Confirm the exact formula `100 × hourly_request_count / total_valid_requests` remains intact and the public exit contract remains 0/1/2/3/4, with code 4 for unique-cardinality exhaustion.

Run the full suite and the documented 1 GB command. Accept only if the documented reference laptop finishes under 30 seconds and the frozen exact candidate receives a current valid Verification Loop adjudication receipt. Otherwise record recovery_required and the next measured action.
```

## Review Checklist for Every Prompt

- [ ] Scope contains only the current plan step; WIP remains 1.
- [ ] Behavior traces to PRD IDs and architecture sections.
- [ ] No raw-record collection, database, server, auth, network, cloud, or Kubernetes was introduced.
- [ ] Text, JSON, and CSV values are semantically identical where applicable.
- [ ] Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- [ ] Exit codes remain `0/1/2/3/4`, and code 4 means unique-cardinality exhaustion.
- [ ] Tests were actually run and recorded.
- [ ] The exact staged candidate, not an ignored/untracked overlay, was frozen and adjudicated.
- [ ] State and handoff artifacts identify the next action.
