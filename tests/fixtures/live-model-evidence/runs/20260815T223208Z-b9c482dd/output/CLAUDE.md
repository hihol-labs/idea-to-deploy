# Nginx Stream Analyzer Project Instructions

## Project Context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers that streams nginx access logs and reports:

1. top 10 client IPs;
2. top 10 request targets by 4xx/5xx count;
3. all 24 hourly request buckets as percentages; and
4. exact unique User-Agent share with a cardinality ceiling.

Default output is colored terminal text; `--json` and `--csv` support pipelines. The specification is planning-complete but product code has not yet been implemented.

## Sources of Truth

Read these before implementation:

1. `PRD.md` — user behavior, priorities, and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — normative technical and CLI contract; resolves conflicts.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 delivery sequence and verification commands.
4. `STRATEGIC_PLAN.md` — value, scope, risks, KPIs, and release criteria.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for each implementation step.

When behavior changes, update the specification first, then the implementation and tests. Do not let code silently redefine the documented contract.

## Fixed Decisions

- Runtime/stack: Python 3.11, Click, Rich, standard-library dataclasses, pip packaging.
- Architecture: a single local process and one sequential pass over a file or stdin.
- No authentication, database, HTTP API, server/daemon, cloud, Docker requirement, or Kubernetes.
- Budget: $0. MVP delivery: one weekend.
- Release performance gate: a documented 1 GB fixture in under 30 seconds on a recorded representative laptop.
- Hourly percentage formula: `100 × hourly_request_count / total_valid_requests`.
- stdout is result data; stderr is diagnostics. Structured modes contain no ANSI.

## Exit-Code Contract

The complete mapping is mandatory in implementation and tests:

| Code | Meaning |
|---:|---|
| `0` | Successful completed analysis |
| `1` | Unexpected internal error |
| `2` | CLI usage/configuration or input open/read/decode failure |
| `3` | No valid request records |
| `4` | Unique-cardinality exhaustion when another distinct User-Agent would exceed the ceiling |

Never omit, reuse, or remap code 4. For failures 1–4, emit no partial result on stdout.

## Engineering Rules

- Preserve WIP=1 and execute `IMPLEMENTATION_PLAN.md` in dependency order.
- Inspect the existing worktree and preserve unrelated user changes.
- Stream line-by-line; do not load or sort the full input.
- Do not use naive whitespace splitting for nginx records.
- Keep parsing, aggregation, orchestration, and rendering separate.
- Treat every log field as untrusted data; never evaluate it or pass it through Rich markup unsafely.
- Keep output deterministic: count descending, then key ascending for top-list ties.
- Use all valid requests as the hourly percentage denominator; malformed lines never enter it.
- Enforce the User-Agent ceiling before insertion and fail with code 4 rather than approximate silently.
- Add or update tests with each behavior change and run the named verification commands.
- Do not claim performance or completion without actual evidence from the exact candidate.
- Do not publish packages, push branches, or create external resources without explicit authorization.
- At the end of every session or significant block of work, save context through `/session-save`.

## Planned Structure

```text
src/nginx_stream_analyzer/{cli,models,parser,aggregate,service,errors}.py
src/nginx_stream_analyzer/renderers/{terminal,json_output,csv_output}.py
tests/{test_parser,test_aggregate,test_service,test_cli,test_output_contracts,test_performance}.py
scripts/{generate_benchmark_log,run_benchmark}.py
```

Do not create empty speculative modules earlier than their implementation step.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and contracts | Not started | Editable install, package test, `--help` |
| 2 | Nginx parser | Not started | Parser suite and coverage gate |
| 3 | Exact aggregation | Not started | Aggregation/cardinality/hour tests |
| 4 | File/stdin service | Not started | Service and CLI integration tests |
| 5 | Terminal/JSON/CSV | Not started | Semantic output contract tests |
| 6 | Errors and safety | Not started | Independent 0/1/2/3/4 and injection tests |
| 7 | Performance | Not started | Recorded 1 GB timing/RSS result |
| 8 | Packaging/release | Not started | Build check, full suite, clean-wheel smoke |

Change a row only after its current evidence exists. At handoff, record the exact next step and any failed command; do not present an unverified step as done.

