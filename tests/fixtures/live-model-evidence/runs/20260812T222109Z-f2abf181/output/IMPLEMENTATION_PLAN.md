# Implementation Plan: nginx-log-report

This plan implements the P0 scope in `PRD.md` using the component contracts in `PROJECT_ARCHITECTURE.md`. It contains nine dependency-ordered steps sized for one weekend. It does not authorize P1/P2 work before all P0 acceptance criteria pass.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and console entry point | Every test and smoke command needs an importable/installable package | 0.5 h |
| 2 | Typed records and domain errors | Parser, aggregation, renderers, and exit mapping share these contracts | 0.5 h |
| 3 | Deterministic fixtures and quality configuration | Correctness and performance need reproducible evidence from the first feature | 0.5 h |

No database, authentication, API, Docker, cloud, or Kubernetes runway is needed; adding any would contradict `PROJECT_ARCHITECTURE.md`.

## Exit-Code Contract for Every Step

All implementation steps and their tests must preserve the complete contract:

| Code | Meaning |
|---:|---|
| `0` | successful report/help/version; lenient parsing may skip invalid lines |
| `1` | I/O or unexpected runtime failure |
| `2` | Click usage/argument error |
| `3` | input-data failure, including strict malformed input, invalid UTF-8, or no valid requests |
| `4` | unique-cardinality exhaustion when the configured distinct User-Agent cap would be exceeded |

Code `4` must never be omitted, remapped, or collapsed into code `1` or `3`.

## Step 1: Package and Contract Skeleton

**Goal:** A Python 3.11 wheel installs and `nginx-log-report --help` invokes the Click boundary.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Component Design,” and “Deployment and packaging.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, test extras, and the `nginx-log-report` console script.
2. Create `src/nginx_log_report/__init__.py` with the package version.
3. Create `src/nginx_log_report/__main__.py` forwarding to the Click command.
4. Create `src/nginx_log_report/cli.py` with options/help only; do not implement parsing yet.
5. Create `tests/test_cli.py` for help, version, and conflicting `--json --csv` usage.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-log-report --help`

**Commit:** `step-1: establish installable CLI contracts`

## Step 2: Models, Errors, and Fixtures

**Goal:** Typed records, immutable report snapshots, error taxonomy, and representative fixtures are reusable by all later steps.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` “Dataclasses,” exit codes, and testing strategy.

**Tasks:**

1. Create `src/nginx_log_report/models.py` with `AccessRecord`, `RankedCount`, `Report`, `RunConfig`, and format enums.
2. Create `src/nginx_log_report/errors.py` with input, cardinality, and expected I/O domain exceptions mapped to `3`, `4`, and `1` at the CLI boundary.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/common.log`, and `tests/fixtures/malformed.log` with documented expected counts.
4. Create `tests/test_models.py` and `tests/test_errors.py` to freeze invariants and prevent exit-code remapping.

**Verification:**

- `python3.11 -m pytest tests/test_models.py tests/test_errors.py -q`
- `python3.11 -m compileall -q src`

**Commit:** `step-2: define domain and failure models`

## Step 3: Streaming Line Parser

**Goal:** Supported Combined/Common lines become `AccessRecord` objects without retaining raw input.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Inputs,” “Component Design,” and security rules; PRD FR-1 and FR-2.

**Tasks:**

1. Create `src/nginx_log_report/parser.py` with once-compiled grammars, timestamp/status validation, request-target extraction, and UA normalization inputs.
2. Create `tests/test_parser.py` covering IPv4/IPv6, quotes, `-`, offset timestamps, status bounds, malformed requests, blank lines, and invalid UTF-8 at the stream boundary.
3. Update `src/nginx_log_report/cli.py` to iterate stdin or an opened file and apply strict/lenient behavior while tracking 1-based line numbers.
4. Extend `tests/test_cli.py` for file/stdin equivalence and exit `3` on strict malformed or zero-valid input.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_cli.py -q`
- `python3.11 -m pytest tests/test_cli.py -q --disable-warnings`

**Commit:** `step-3: parse nginx streams safely`

## Step 4: Core Rankings and Hourly Distribution

**Goal:** One pass computes top IPs, top 4xx/5xx URLs, and all 24 hourly percentages deterministically.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Streaming and Complexity” and output semantics; PRD FR-3 through FR-5.

**Tasks:**

1. Create `src/nginx_log_report/aggregate.py` with counters, 24 hour buckets, valid/invalid totals, and immutable finalization.
2. Implement top-10 ordering by count descending then key ascending.
3. Calculate each hour as `100 × hourly_request_count / total_valid_requests`; keep raw counts in `Report` and formatting out of the aggregator.
4. Create `tests/test_aggregate.py` for status boundaries, ties, empty buckets, denominator exclusions, and percentages summing to approximately 100% before display rounding.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py -q -k 'ranking or hourly'`

**Commit:** `step-4: aggregate core traffic metrics`

## Step 5: Exact User-Agent Share and Exhaustion Guard

**Goal:** Combined logs receive an exact unique-UA percentage while a hard cap prevents uncontrolled cardinality growth.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` UA definition, streaming safety, and exit `4`; PRD FR-6 and FR-9.

**Tasks:**

1. Extend `src/nginx_log_report/aggregate.py` with normalized UA tracking and cap-before-insert behavior.
2. Return `None` for Common-format UA metrics and exact `100 × unique_normalized_user_agent_count / total_valid_requests` for Combined format.
3. Update `src/nginx_log_report/cli.py` so cardinality exhaustion writes one diagnostic, emits no report, and exits exactly `4`.
4. Add boundary, duplicate, `<missing>`, Common-format, and no-partial-output cases to `tests/test_aggregate.py` and `tests/test_cli.py`.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py tests/test_cli.py -q -k 'user_agent or cardinality'`
- `nginx-log-report --max-unique-user-agents 1 tests/fixtures/combined.log >/tmp/nginx-report.out; test $? -eq 4 && test ! -s /tmp/nginx-report.out`

**Commit:** `step-5: guard exact user-agent cardinality`

## Step 6: Rich Terminal Renderer

**Goal:** Default output is a readable colored terminal report with safe plain-text log values.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and security rules; PRD FR-7.

**Tasks:**

1. Create `src/nginx_log_report/renderers/__init__.py` and `src/nginx_log_report/renderers/text.py`.
2. Render top tables, 24 hour rows, UA percentage or `N/A`, and valid/invalid totals using Rich with markup disabled for untrusted values.
3. Honor `--no-color`, `NO_COLOR`, and non-TTY behavior.
4. Create `tests/test_text_renderer.py` with width-stable semantic assertions and a no-ANSI golden file at `tests/golden/report.txt`.

**Verification:**

- `python3.11 -m pytest tests/test_text_renderer.py -q`
- `nginx-log-report --no-color tests/fixtures/combined.log`

**Commit:** `step-6: render safe terminal reports`

## Step 7: JSON and CSV Pipeline Renderers

**Goal:** `--json` and `--csv` produce deterministic, documented, ANSI-free stdout.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` structured schemas; PRD FR-8.

**Tasks:**

1. Create `src/nginx_log_report/renderers/json.py` with schema version `1` and stable key/value types.
2. Create `src/nginx_log_report/renderers/csv.py` with header `section,rank,key,count,percentage` using the standard CSV writer.
3. Update `src/nginx_log_report/cli.py` to select exactly one renderer and keep diagnostics on stderr.
4. Create `tests/test_json_renderer.py`, `tests/test_csv_renderer.py`, `tests/golden/report.json`, and `tests/golden/report.csv` for schema, escaping, precision, and locale independence.

**Verification:**

- `python3.11 -m pytest tests/test_json_renderer.py tests/test_csv_renderer.py tests/test_cli.py -q`
- `nginx-log-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-7: add deterministic pipeline formats`

## Step 8: End-to-End Failure and Contract Verification

**Goal:** The installed command proves every output and exit-code contract through black-box tests.

**Time:** ~1.5 hours

**Context:** Entire `## CLI Interface` in `PROJECT_ARCHITECTURE.md`; all P0 acceptance criteria.

**Tasks:**

1. Create `tests/test_integration.py` exercising real subprocess invocations with file and stdin input.
2. Prove exit `0`, `1`, `2`, `3`, and `4` independently and assert stdout/stderr separation.
3. Cover broken paths, conflicting options, invalid UTF-8, strict and lenient malformed input, no valid records, and cardinality exhaustion.
4. Create `tests/test_output_contract.py` to validate ranking tie order, 24 hour keys, JSON version, and CSV header.

**Verification:**

- `python3.11 -m pytest tests/test_integration.py tests/test_output_contract.py -q`
- `python3.11 -m pytest -q --cov=nginx_log_report --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-8: verify end-to-end CLI contract`

## Step 9: Performance, Packaging, and Release Evidence

**Goal:** The exact wheel candidate meets quality gates and processes a deterministic representative 1 GB fixture under 30 seconds on the recorded laptop.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` KPIs/Definition of Done and `PROJECT_ARCHITECTURE.md` complexity constraints.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically stream-generate representative and adversarial-cardinality fixtures without committing the generated 1 GB file.
2. Create `tests/test_performance_smoke.py` for a small CI-scale regression and document the full benchmark procedure in `docs/BENCHMARK.md`.
3. Profile the hot loop before optimizing; record machine, OS, Python, storage, cache state, command, elapsed time, throughput, and peak RSS.
4. Update `README.md` with verified install/usage examples and exact JSON/CSV contracts.
5. Build a wheel, install it in a clean virtual environment, rerun smoke/integration tests, and bind benchmark evidence to that candidate.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_log_report --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `/usr/bin/time -v nginx-log-report --json /tmp/nginx-log-report-benchmark-1gb.log >/dev/null`

The final command passes only when elapsed time is under 30 seconds on the documented reference laptop and the report records peak RSS. Generated benchmark data is excluded from version control.

**Commit:** `step-9: validate performance and release candidate`

## Weekend Boundaries

| Iteration | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable boundary and trustworthy parser | 4 h |
| Saturday PM | 4–5 | Complete streaming metric engine and safety cap | 3 h |
| Sunday AM | 6–7 | Human and pipeline output contracts | 3.5 h |
| Sunday PM | 8–9 | Black-box correctness, benchmark, and wheel evidence | 3.5 h |

## Plan-Level Acceptance

- All P0 stories in `PRD.md` pass their acceptance criteria.
- The full suite passes with at least 90% package line coverage.
- The exact installed wheel proves exit codes `0/1/2/3/4`.
- The reproducible 1 GB benchmark is under 30 seconds on the documented laptop.
- No product code introduces persistence, authentication, HTTP services, cloud, Docker, or Kubernetes.

