# Nginx Stream Analyzer — Project Instructions

## Project Context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers that streams supported nginx access logs and reports:

1. Top 10 client IPs by valid request count.
2. Top 10 request URLs among 4xx/5xx responses.
3. All 24 hourly request percentages.
4. Exact unique User-Agent count and share within hard cardinality limits.

Default output is colored Rich terminal text. `--json` and `--csv` provide deterministic pipeline formats. The product is a $0 open-source, one-weekend project targeting a representative 1 GB log in under 30 seconds on a documented laptop.

## Source of Truth

Read these before implementation:

1. `PRD.md` — observable requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — component, schema, CLI, security, and numerical contracts.
3. `IMPLEMENTATION_PLAN.md` — eight WIP=1 delivery units and verification commands.
4. `STRATEGIC_PLAN.md` — scope, priorities, risks, KPIs, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` — ready-to-use prompts for each implementation step.

When behavior changes, update the PRD/architecture first, then implementation. Do not let generated code silently become the specification.

## Non-Negotiable Architecture

Use a single local Python process with streaming input, typed dataclasses, isolated parsing, bounded in-memory aggregation, an immutable report model, and separate renderers. Never retain raw records or read the whole input into memory.

The literal decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. Do not add authentication, persistence, an HTTP server, cloud services, Docker deployment, Kubernetes, telemetry, or network calls.

Required stack:

- Python 3.11 only for the MVP compatibility contract.
- Click for CLI parsing and usage errors.
- Rich for safe terminal presentation.
- Standard-library `dataclasses` for domain and report models.
- Standard-library JSON/CSV encoding and core streaming primitives.
- pip-compatible packaging with a `src/` layout.

## Behavioral Rules

- Top lists contain at most 10 rows, sorted by count descending and key ascending for ties.
- Error URLs include statuses 400 through 599 only.
- Query strings remain in the request-target key.
- All 24 hour buckets appear in `00` through `23` order using the hour and offset from the logged timestamp.
- Hourly percentage uses exactly `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.
- Unique User-Agent matching is exact and case-sensitive; `-` is a literal value.
- Round percentages to two decimals only at serialization.
- Skip and count malformed lines; if none are valid, fail without a report.
- Enforce distinct-key limits before insertion and never silently approximate.
- Treat log values as untrusted data: no execution, interpolation, Rich markup, formula execution, or uncapped diagnostic echo.

## CLI and Exit Contract

Command: `nginx-stream-analyzer [OPTIONS] [INPUT]`. Omitted `INPUT` or `-` reads stdin. `--json` and `--csv` are mutually exclusive; `--no-color` applies only to text.

The complete public exit contract is mandatory in every implementation unit:

| Code | Meaning |
|---:|---|
| 0 | Fully computed and written success, help, or version |
| 1 | Input/output failure |
| 2 | CLI usage failure |
| 3 | Zero valid supported records |
| 4 | Unique-cardinality exhaustion for distinct IP, error URL, or User-Agent state |

Never omit or remap code 4. The shorthand contract is `0/1/2/3/4`.

## Intended Repository Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py
  input.py
  parser.py
  aggregate.py
  models.py
  errors.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_input.py
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_security.py
  test_performance.py
  generate_benchmark_log.py
docs/BENCHMARK.md
```

This is the intended future structure, not evidence that files already exist.

## Engineering Workflow

- Use the repository-local Idea to Deploy lifecycle skill that matches the current unit.
- Preserve WIP=1. Update `.itd/SCOPE_LOCK.md` and reconcile `.itd-memory/` before changing scope.
- Work on one numbered step from `IMPLEMENTATION_PLAN.md` at a time.
- Keep edits within that step's named files unless the scope lock is explicitly revised.
- Write or update tests with behavior; run the exact commands named by the active unit.
- Exclude undeclared ignored/untracked overlays from acceptance. If a non-Git input is required, declare it and bind its content hash in the machine evidence.
- Freeze the exact staged candidate, run its machine oracle, and apply the required risk-tier checker.
- Accept completion only from a current revalidated adjudication receipt; a prose “passed” statement is insufficient.
- Record failures as recovery work with a specific next action.
- Do not create `DEVILS_ADVOCATE_REVIEW.md` during the blueprint session. The benchmark harness runs the real reviewer separately.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Testing and Quality Gates

Minimum future release evidence:

- Parser, aggregation, and renderer unit tests including malformed and adversarial inputs.
- File/stdin equivalence and end-to-end CLI integration tests.
- Golden text/JSON/CSV semantics with deterministic ordering.
- Explicit tests for exits 0, 1, 2, 3, and 4.
- At least 90% coverage for parser, aggregation, and output modules.
- Security cases for Rich markup, terminal controls, CSV formulas, diagnostic redaction, and cardinality exhaustion.
- A deterministic 1 GB benchmark under 30 seconds with reference environment and peak RSS recorded.
- A valid current exact-candidate Verification Loop adjudication receipt.

## Implementation Status

| Step | Deliverable | Status | Next acceptance evidence |
|---:|---|---|---|
| 1 | Package skeleton and CLI boundary | Not started | Install, CLI tests, exit mapping |
| 2 | Models, input adapter, fixtures | Not started | File/stdin and non-seekable tests |
| 3 | Supported nginx parser | Not started | Parser fixtures and coverage |
| 4 | Streaming aggregation | Not started | Metric, boundary, and cardinality tests |
| 5 | Rich text renderer | Not started | Terminal/color/security tests |
| 6 | JSON and CSV renderers | Not started | Golden structured-output tests |
| 7 | End-to-end hardening and packaging | Not started | Full coverage and clean-wheel smoke test |
| 8 | Performance qualification | Not started | 1 GB benchmark and adjudication receipt |

Current next action: implement Step 1 only when a future session explicitly authorizes product-code implementation. This blueprint session creates documentation only.
