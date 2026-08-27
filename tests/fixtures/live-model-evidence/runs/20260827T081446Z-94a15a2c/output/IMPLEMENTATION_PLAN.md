# Implementation Plan: nginx Stream Analytics CLI

## Plan Contract

This is a planning document; none of the listed product files or commands have
been implemented or run by this blueprint. Delivery is constrained to one
weekend and follows `PROJECT_ARCHITECTURE.md` and the P0 acceptance criteria in
`PRD.md`. Steps are dependency ordered, with RICE priority used within each
dependency layer.

Every step preserves the public exit-code contract: `0` success, `1`
unexpected/runtime processing failure, `2` CLI usage error, `3` input,
decoding, or strict malformed-line failure, and `4` unique-cardinality
exhaustion. Code 4 is never remapped or silently downgraded.

## Architectural Runway

These foundations precede feature work:

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package layout and Python 3.11 tool configuration | All modules and verification commands require an installable package | 45 min |
| 2 | Domain dataclasses and typed errors | Parser, aggregation, renderers, and CLI need one shared contract | 45 min |
| 3 | Representative fixtures and benchmark generator | Correctness and performance must be measured against controlled input | 60 min |

No database schema, authentication system, API scaffold, container, or CI/CD
deployment runway is needed because those components are explicitly outside
the architecture.

## Step 1: Establish the Installable CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the project, run the
placeholder command, and execute the test runner without product behavior.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` Component Boundaries and CLI Interface.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12` for the MVP, Click and
   Rich runtime dependencies, pytest development configuration, and the
   `nginx-log-report` console entry point.
2. Create `src/nginx_stream_analytics/__init__.py` with version metadata.
3. Create `src/nginx_stream_analytics/cli.py` with the Click command signature
   and eager `--help`/`--version` behavior only.
4. Create `tests/test_cli_contract.py` for install, help, version, and option
   conflict expectations.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `nginx-log-report --help`

**Commit:** `step-1: establish installable CLI skeleton`

## Step 2: Define Models, Errors, and Test Fixtures

**Goal:** All later modules share frozen domain records, one report schema, and
typed failures; fixtures make expected metrics hand-verifiable.

**Time:** ~1.5 hours

**Context:** Architecture Data Model, Failure Safety, and PRD edge cases.

**Tasks:**

1. Create `src/nginx_stream_analytics/models.py` with frozen `AccessRecord`,
   `RankedCount`, `HourlyBucket`, `UserAgentSummary`, and `Report` dataclasses.
2. Create `src/nginx_stream_analytics/errors.py` with usage, input, parsing,
   runtime, and cardinality error categories mapped to `2/3/1/4`.
3. Create `tests/fixtures/access_combined.log`,
   `tests/fixtures/access_common.log`, and `tests/fixtures/malformed.log` with
   small auditable cases.
4. Create `tests/conftest.py` factories for records and canonical reports.

**Verification:**

- `python3.11 -m pytest tests/test_models.py tests/test_errors.py -q`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-2: define report and failure contracts`

## Step 3: Implement Buffered Input and nginx Parsing

**Goal:** Files and stdin yield validated records one at a time under the
documented common/combined syntax and strictness rules.

**Time:** ~2 hours

**Context:** Architecture Data Flow and CLI Inputs; PRD FR-001–FR-003.

**Tasks:**

1. Create `src/nginx_stream_analytics/input.py` to open paths read-only,
   preserve stdin ownership, decode with the chosen codec, and attach line
   numbers to input failures.
2. Create `src/nginx_stream_analytics/parser.py` for common/combined parsing,
   quoted request extraction, status validation, and timestamp-hour parsing.
3. Create `tests/test_input.py` for file/stdin equivalence, unreadable input,
   decoding errors, and streaming iteration.
4. Create `tests/test_parser.py` for IPv4/IPv6, query strings, status and hour
   boundaries, missing fields, quoting, blank lines, and malformed timestamps.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_input.py::test_reader_is_lazy -q`

**Commit:** `step-3: parse supported nginx streams`

## Step 4: Build Core Ranking and Hourly Aggregation

**Goal:** One mutable aggregator produces deterministic IP/error rankings and
24 hourly counts/percentages without retaining records.

**Time:** ~2 hours

**Context:** Architecture Metric Semantics; PRD US-2, US-3, and US-4.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with IP counts, 400–599 URL
   counts, 24 integer buckets, total counters, and deterministic top-10
   finalization.
2. Calculate each hourly percentage with
   `100 × hourly_request_count / total_valid_requests` and explicit zero-total
   behavior.
3. Create `tests/test_aggregate_rankings.py` for count and lexical tie order,
   fewer/more than ten keys, and status boundaries.
4. Create `tests/test_aggregate_hourly.py` for all buckets, totals, the literal
   percentage semantics, and zero valid input.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate_rankings.py tests/test_aggregate_hourly.py -q`
- `python3.11 -m pytest tests/test_aggregate_hourly.py -q --maxfail=1`

**Commit:** `step-4: aggregate rankings and hourly percentages`

## Step 5: Add Exact User-Agent Cardinality Guard

**Goal:** The report includes exact distinct User-Agent count and share, while
adversarial cardinality fails explicitly before a misleading report exists.

**Time:** ~1 hour

**Context:** Architecture ADR-002; PRD US-5 and FR-007.

**Tasks:**

1. Extend `src/nginx_stream_analytics/aggregate.py` with normalization,
   requests-with-User-Agent count, exact set membership, and a positive
   configurable cap.
2. Raise the typed cardinality failure only when a new value would exceed the
   cap; repeated values at the cap remain valid.
3. Calculate share against `total_valid_requests` with explicit zero behavior.
4. Create `tests/test_user_agents.py` for missing values, duplicates, cap
   boundary, repeated-at-cap input, share calculation, and error type.

**Verification:**

- `python3.11 -m pytest tests/test_user_agents.py -q`
- `python3.11 -m pytest tests/test_user_agents.py::test_next_distinct_value_raises_cardinality_error -q`

**Commit:** `step-5: guard exact user-agent cardinality`

## Step 6: Implement Rich, JSON, and CSV Renderers

**Goal:** One canonical report renders with identical values as colored text,
stable JSON, or stable long-form CSV.

**Time:** ~2 hours

**Context:** Architecture CLI Outputs and ADR-003; PRD US-6.

**Tasks:**

1. Create `src/nginx_stream_analytics/render/__init__.py` with a renderer
   protocol and dispatch table.
2. Create `src/nginx_stream_analytics/render/text.py` with Rich tables,
   TTY-aware color, safe field display, all 24 hours, and summary warnings.
3. Create `src/nginx_stream_analytics/render/json.py` with the stable top-level
   schema and UTF-8 JSON encoding.
4. Create `src/nginx_stream_analytics/render/csv.py` with columns
   `metric,rank,key,count,percentage` using the standard `csv` module.
5. Create `tests/test_render_text.py`, `tests/test_render_json.py`, and
   `tests/test_render_csv.py` including golden fixtures under `tests/golden/`.

**Verification:**

- `python3.11 -m pytest tests/test_render_text.py tests/test_render_json.py tests/test_render_csv.py -q`
- `python3.11 -m pytest tests/test_render_json.py tests/test_render_csv.py -q --maxfail=1`

**Commit:** `step-6: render one report in three formats`

## Step 7: Integrate CLI Options and Complete Failure Mapping

**Goal:** The installed command connects input, parsing, aggregation, and
rendering while enforcing stdout/stderr and the full exit contract.

**Time:** ~1.5 hours

**Context:** Architecture CLI Interface; PRD FR-009 and FR-010.

**Tasks:**

1. Complete `src/nginx_stream_analytics/cli.py` with `INPUT`, `--json`,
   `--csv`, `--strict`, `--encoding`, `--max-unique-user-agents`, and
   `--color/--no-color`.
2. Buffer report output until successful finalization so failures never leave
   a plausible partial report.
3. Map success/runtime/usage/input/cardinality outcomes to `0/1/2/3/4` and
   send all diagnostics to stderr.
4. Create `tests/test_cli_integration.py` for file/stdin parity, three output
   modes, strict/non-strict parsing, conflicts, decoding, cardinality, broken
   pipe, and stdout cleanliness.

**Verification:**

- `python3.11 -m pytest tests/test_cli_contract.py tests/test_cli_integration.py -q`
- `nginx-log-report --json tests/fixtures/access_combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-report --csv tests/fixtures/access_combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: integrate CLI and exit codes`

## Step 8: Prove Correctness, Safety, and Performance

**Goal:** The complete implementation has regression, security, memory, and
representative 1 GB performance evidence.

**Time:** ~2 hours

**Context:** Architecture Performance, Safety, and Testing; PRD NFR-001–006.

**Tasks:**

1. Create `tests/test_end_to_end.py` with hand-calculated expected reports for
   common, combined, malformed, empty, and all-invalid fixtures.
2. Create `tests/test_output_safety.py` for terminal controls, CSV-special
   values, JSON escaping, and diagnostics that do not echo complete log lines.
3. Create `benchmarks/generate_fixture.py` to deterministically stream-generate
   a representative 1 GB fixture with documented cardinality distribution.
4. Create `benchmarks/run_benchmark.py` to invoke the installed CLI, validate
   output, and record Python version, machine, elapsed time, and peak RSS.
5. Profile only if the initial result misses the target; record any chosen
   optimization and its before/after evidence.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 benchmarks/generate_fixture.py --size-gib 1 --output /tmp/nginx-stream-benchmark.log`
- `python3.11 benchmarks/run_benchmark.py --input /tmp/nginx-stream-benchmark.log --max-seconds 30`

**Commit:** `step-8: verify correctness safety and performance`

## Step 9: Finalize Packaging and Operator Documentation

**Goal:** A clean Python 3.11 environment can build, install, invoke, and
understand the release without undocumented behavior.

**Time:** ~1 hour

**Context:** Strategic Definition of Done; all PRD release acceptance.

**Tasks:**

1. Create `README.md` with a sub-30-second quick start, supported log formats,
   metric definitions, CLI examples, schemas, and the complete exit table.
2. Create `CHANGELOG.md` with the initial public contract.
3. Add packaging metadata and source inclusion checks to `pyproject.toml`.
4. Build wheel and sdist, inspect their contents, install the wheel in a clean
   environment, and run the end-to-end smoke test.
5. Record benchmark environment and result in `benchmarks/RESULTS.md` without
   committing the generated 1 GB fixture.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 -m build`
- `python3.11 -m pip install --force-reinstall dist/*.whl`
- `nginx-log-report --json tests/fixtures/access_combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-9: prepare installable documented release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---:|
| Saturday foundation | 1–3 | Installable shell, contracts, and validated input records | 4.5 hours |
| Saturday/Sunday core | 4–6 | Exact metrics and three consistent renderers | 5 hours |
| Sunday acceptance | 7–9 | Full CLI contract, performance evidence, and package | 4.5 hours |

## Dependency and Scope Rules

- Complete only one step at a time and keep the test suite green before moving
  to the next.
- If a behavior changes, update `PRD.md` first and reconcile architecture and
  tests before implementation.
- Do not add persistence, HTTP, authentication, server processes, cloud
  resources, containers, or Kubernetes.
- Gzip, custom log formats, progress output, and parallel processing remain
  deferred unless the P0 scope is formally changed.
- A missed benchmark triggers profiling and scope review, not an unmeasured
  architectural rewrite.

## Final Acceptance Checklist

- [ ] All P0 user-story acceptance criteria pass.
- [ ] Every exit code `0/1/2/3/4` has an integration test.
- [ ] Text, JSON, and CSV reflect the same canonical report.
- [ ] The representative 1 GB benchmark is below 30 seconds on the documented
  laptop and peak RSS is recorded.
- [ ] Wheel and sdist install and run under Python 3.11.
- [ ] No input-sized raw buffer, persistent state, or network access exists.
- [ ] Documentation matches the shipped CLI and schemas.

