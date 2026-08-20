# Implementation Plan: Nginx Stream Analytics CLI

## Planning Rules

This plan covers the one-weekend MVP only. Work proceeds in order with WIP=1: a step starts only after the previous step's checks pass and its evidence is recorded. `PROJECT_ARCHITECTURE.md` is authoritative for technical contracts; `PRD.md` is authoritative for user-visible acceptance criteria. No database, HTTP API, authentication, server, cloud, Docker, or Kubernetes work is permitted.

Public exit codes are fixed in every step: `0` report success, `1` operational/internal failure, `2` CLI usage error, `3` input data/parse failure, and `4` unique-cardinality exhaustion. Code 4 applies when a new distinct IP, error URL, or User-Agent would exceed the configured guard; it must never be omitted, remapped, or collapsed into code 1.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and test layout | Every later module and console test depends on stable import and fixture paths | 1.0 h |
| 2 | Canonical models and output schemas | Prevents parser, aggregator, and reporters from inventing incompatible contracts | 0.75 h |
| 3 | Deterministic benchmark protocol | Makes the 1 GB / 30 s target measurable before optimization pressure | 0.75 h |
| 4 | Golden nginx fixtures | Creates known common, combined, malformed, Unicode, and high-cardinality cases | 0.5 h |

## STEP 1: Establish Package, Contracts, and Test Harness

**Goal:** A pip-oriented Python 3.11 package imports cleanly, exposes the planned console command, and has test/benchmark fixtures without implementing product behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 3–4 and 12; `PRD.md` Sections 5–8.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, runtime dependencies Click and Rich, a `nginx-log-report` console script, and pytest development configuration.
2. Create `src/nginx_stream_analytics/__init__.py` with version metadata and `src/nginx_stream_analytics/__main__.py` delegating to the CLI.
3. Create `src/nginx_stream_analytics/models.py` with typed dataclass contracts for `AccessRecord`, ranked entries, hourly entries, `Report`, and typed failure categories.
4. Create `tests/conftest.py` and fixtures under `tests/fixtures/` for common, combined, mixed-validity, empty, and special-character logs.
5. Create `benchmarks/generate_log.py` and `benchmarks/README.md` defining deterministic size/seed generation and required environment recording.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -c "import nginx_stream_analytics; print(nginx_stream_analytics.__version__)"`
- `python3.11 -m pytest --collect-only -q`

**Commit:** `step-1: establish package and executable contracts`

## STEP 2: Implement the Streaming Parser

**Goal:** Common and combined nginx records are parsed one line at a time into exact domain records, with malformed input categorized without leaking raw lines.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5 and 7; `PRD.md` FR-001, FR-002, FR-011.

**Tasks:**

1. Create `src/nginx_stream_analytics/parser.py` with one compiled, anchored parser and a `parse_line(line, line_number)` boundary.
2. Parse IPv4/IPv6 text, timezone-aware timestamps, request target, status, and optional User-Agent according to the architecture.
3. Represent empty lines separately from malformed non-empty lines so reporting counts remain exact.
4. Create `tests/unit/test_parser.py` covering common/combined formats, escaped quotes, missing request targets, invalid status/timestamps, Unicode replacement characters, empty lines, and sanitized diagnostic categories.

**Verification:**

- `python3.11 -m pytest tests/unit/test_parser.py -q`
- `python3.11 -m pytest tests/unit/test_parser.py --cov=nginx_stream_analytics.parser --cov-branch --cov-fail-under=90`

**Commit:** `step-2: parse nginx common and combined records`

## STEP 3: Implement Exact Streaming Aggregation

**Goal:** Valid records update all four metrics in one pass, produce deterministic top lists and exact percentages, and stop safely at the cardinality limit.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5–6 and ADR-002; `PRD.md` FR-003 through FR-008.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with a streaming `Aggregator` that retains counts but no raw records.
2. Implement top-10 IP and combined 4xx/5xx URL selection with count-descending/key-ascending ties.
3. Implement 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests`.
4. Implement unique User-Agent count and `100 × unique_non_missing_user_agent_count / total_valid_requests`.
5. Check the per-container distinct-key limit before insertion and raise the typed cardinality failure that maps to exit code 4.
6. Create `tests/unit/test_aggregate.py` with tie, zero-hour, mixed-status, missing-User-Agent, exact denominator, and exhaustion tests.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregate.py -q`
- `python3.11 -m pytest tests/unit/test_aggregate.py --cov=nginx_stream_analytics.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-3: aggregate exact bounded streaming metrics`

## STEP 4: Build the CLI and Failure Boundary

**Goal:** File/stdin selection, option validation, strict/default malformed handling, and the complete `0/1/2/3/4` contract work before presentation formatting is added.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` and Section 10; `PRD.md` FR-001, FR-002, FR-009 through FR-011.

**Tasks:**

1. Create `src/nginx_stream_analytics/cli.py` with Click arguments/options: `INPUT`, `--json`, `--csv`, `--strict`, `--max-unique`, `--no-color`, `--version`, and `--help`.
2. Stream input once using UTF-8 replacement semantics and collect only sanitized malformed metadata.
3. Translate successful completion to `0`, operational/internal failures to `1`, Click usage failures to `2`, input/parse failures to `3`, and cardinality exhaustion to `4`.
4. Handle downstream broken pipes without a traceback and keep report data on stdout and diagnostics on stderr.
5. Create `tests/integration/test_cli_exit_codes.py` with at least one subprocess/Click-runner assertion for every code `0/1/2/3/4`.

**Verification:**

- `python3.11 -m pytest tests/integration/test_cli_exit_codes.py -q`
- `python3.11 -m nginx_stream_analytics --help`
- `test "$(python3.11 -m nginx_stream_analytics --json --csv tests/fixtures/combined.log >/dev/null 2>&1; printf '%s' "$?")" = 2`

**Commit:** `step-4: enforce cli and complete exit-code boundary`

## STEP 5: Add Text, JSON, and CSV Reporters

**Goal:** All three output modes render one canonical report with matching values, stable schemas, and no structured-output ANSI sequences.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 9 and ADR-003; `PRD.md` FR-012 through FR-014.

**Tasks:**

1. Create `src/nginx_stream_analytics/reporters/__init__.py` with the reporter selection boundary.
2. Create `src/nginx_stream_analytics/reporters/text.py` with Rich summary/top/hour tables, escaped untrusted values, terminal-aware color, `NO_COLOR`, and `--no-color`.
3. Create `src/nginx_stream_analytics/reporters/json.py` with schema version 1, 24 ordered hour entries, six-decimal percentages, UTF-8, and a trailing newline.
4. Create `src/nginx_stream_analytics/reporters/csv.py` with the normalized `schema_version,section,rank,key,count,percent` schema and deterministic section order.
5. Create `tests/golden/` expected outputs and `tests/integration/test_reporters.py` to compare values across formats and check ANSI absence in JSON/CSV.

**Verification:**

- `python3.11 -m pytest tests/integration/test_reporters.py -q`
- `python3.11 -m nginx_stream_analytics --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `python3.11 -m nginx_stream_analytics --csv tests/fixtures/combined.log | python3.11 -c "import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert rows"`

**Commit:** `step-5: render canonical text json and csv reports`

## STEP 6: Close Functional and Safety Acceptance

**Goal:** End-to-end behavior satisfies every P0 story, including mixed input, privacy-safe diagnostics, deterministic ties, special characters, and controlled cardinality failure.

**Time:** ~2.5 hours

**Context:** All of `PRD.md`; `PROJECT_ARCHITECTURE.md` Sections 7, 10, and 11.

**Tasks:**

1. Create `tests/acceptance/test_user_stories.py` mapping tests to P0 user-story identifiers.
2. Add file-versus-stdin equivalence, common-versus-combined, mixed-validity, strict-stop, empty input, all-hours, all-status-boundary, and tie-order cases.
3. Add control-character/Rich-markup escaping and diagnostic redaction assertions.
4. Add an adversarial fixture generator that reaches `--max-unique` cheaply and proves exit 4 without relying on actual memory exhaustion.
5. Run coverage across parser, aggregation, CLI, and reporters and close uncovered P0 branches.

**Verification:**

- `python3.11 -m pytest tests/acceptance tests/integration tests/unit -q`
- `python3.11 -m pytest --cov=nginx_stream_analytics --cov-branch --cov-fail-under=90`

**Commit:** `step-6: satisfy functional and safety acceptance`

## STEP 7: Prove the Performance Contract

**Goal:** A reproducible 1 GB run completes in under 30 seconds on the documented reference laptop, with peak memory captured and bottlenecks supported by measurements.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 6; `STRATEGIC_PLAN.md` KPIs and kill criteria; `PRD.md` NFR-001 through NFR-003.

**Tasks:**

1. Generate `benchmarks/data/combined-1gb.log` locally from the deterministic generator; keep it ignored by Git.
2. Create `benchmarks/run.sh` to record platform, CPU, RAM, Python version, input bytes/lines, cache condition, elapsed time, and peak RSS for default text mode.
3. Create `benchmarks/RESULTS.md` with the reference command and measured evidence.
4. Profile only if the first run misses the target; optimize the measured hot path without changing output semantics.
5. Run an adversarial high-cardinality benchmark separately to demonstrate controlled code 4.

**Verification:**

- `python3.11 benchmarks/generate_log.py --bytes 1073741824 --seed 311 --output benchmarks/data/combined-1gb.log`
- `bash benchmarks/run.sh benchmarks/data/combined-1gb.log`
- `python3.11 -m pytest tests/performance/test_memory_guard.py -q`

**Commit:** `step-7: verify one-gigabyte performance contract`

## STEP 8: Validate Distribution and Release Readiness

**Goal:** Clean Python 3.11 environments can install the artifacts, invoke both entrypoints, and reproduce documented examples and all acceptance checks.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 12; `STRATEGIC_PLAN.md` Definition of Done; this document's Planning Rules.

**Tasks:**

1. Finalize `README.md` with installation, 30-second quick start, formats, malformed-input policy, formulas, and the exact exit-code table.
2. Create `CHANGELOG.md` with the initial release scope and known limitations, without promising custom formats or gzip support.
3. Build wheel and sdist into `dist/`, install the wheel into a clean temporary Python 3.11 virtual environment, and exercise file/stdin plus all reporters.
4. Run the complete suite and validate that tracked files contain no placeholders, benchmark data, caches, secrets, or generated build artifacts.
5. Record release evidence and reconcile Idea to Deploy state before marking the implementation unit verified.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest -q`
- `python3.11 -m pip check`
- `rg -n 'TODO|TBD|Lorem ipsum' README.md src tests pyproject.toml && exit 1 || exit 0`

**Commit:** `step-8: validate installable release candidate`

## Weekend Boundaries

| Block | Steps | Goal | Expected duration |
|---|---|---|---:|
| Friday | 1 | Reproducible runway | 2 h |
| Saturday morning | 2–3 | Correct streaming engine | 6 h |
| Saturday afternoon | 4–5 | Stable CLI and outputs | 5.5 h |
| Sunday morning | 6 | Functional/safety acceptance | 2.5 h |
| Sunday afternoon | 7–8 | Performance and distributable proof | 5 h |

Total estimate is approximately 21 hours. `.gz`, configurable top-N, arbitrary nginx formats, persistence, and any server architecture remain outside these eight steps.

## Completion Evidence

Implementation is not complete from prose or a green unit test alone. Required evidence is: full suite output, coverage result, exact exit-code integration results for `0/1/2/3/4`, cross-format golden output, sanitized-error tests, a current 1 GB benchmark record, high-cardinality exit-4 evidence, build output, and a clean-environment wheel smoke test. The exact candidate must then pass the repository's current Idea to Deploy verification/adjudication route.
