# Implementation Plan: Nginx Stream Analyzer

## 1. Delivery Rules

This plan implements the approved P0 scope in dependency order over one weekend. Product code does not exist as part of this blueprint; the paths below are the contract for a later implementation session. Each step should be committed only after its checks pass. P1 gzip input and P2 features remain outside the MVP unless all P0 release gates are satisfied.

The public exit-code contract is complete and immutable for MVP: `0` success, `1` input/runtime failure, `2` CLI usage error, `3` non-empty input with no valid records, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or converted into a partial report.

## 2. Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package/test configuration | Makes clean install and all later checks reproducible | 1 hour |
| 2 | Typed report and error contracts | Prevents parser, aggregator, and renderer schema drift | 1 hour |
| 3 | Reviewed nginx fixtures and golden schema samples | Gives implementation work an executable target | 1 hour |
| 4 | Benchmark protocol and corpus generator fixture | Measures performance before late-stage surprises | 1 hour |

There is intentionally no database schema, authentication layer, HTTP API, Docker setup, CI/CD deployment, or infrastructure runway. Those elements would violate `PROJECT_ARCHITECTURE.md`.

## STEP 1: Package Skeleton and Public Contracts

**Goal:** A pip-installable Python 3.11 package exposes a Click command with help/version and frozen model/error contracts.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5, 6, 12; `PRD.md` NFR-1.

**Tasks:**

1. Create `pyproject.toml` with build metadata, Python range, Click/Rich dependencies, test extras, and `nginx-stream-analyzer` console entry point.
2. Create `src/nginx_stream_analyzer/__init__.py`, `models.py`, and `errors.py` with typed dataclasses and distinct failures for input, no-valid-record, and User-Agent cardinality exhaustion.
3. Create `src/nginx_stream_analyzer/cli.py` with Click option declarations, mutual exclusion, and placeholders wired only to defined service interfaces.
4. Create `tests/test_cli.py` for help, version, invalid option combinations, and usage exit 2.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `nginx-stream-analyzer --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold package and public contracts`

## STEP 2: Streaming Input and Parser

**Goal:** Supported common and combined log lines are parsed incrementally into timezone-aware records with transparent invalid-line handling.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3 and 7; `PRD.md` FR-1, FR-10.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with compiled format patterns and timestamp/request parsing.
2. Create `src/nginx_stream_analyzer/input.py` for buffered UTF-8 file/stdin iteration and I/O/decode error normalization.
3. Add `tests/fixtures/common.log`, `combined.log`, `mixed.log`, and `all_invalid.log` with reviewed edge cases.
4. Create `tests/test_parser.py` covering IPv4, IPv6, quoted fields, timezone offsets, missing request, malformed input, and both formats.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_analyzer.parser --cov-report=term-missing`

**Commit:** `step-2: implement streaming nginx parser`

## STEP 3: One-pass Aggregation and Metric Semantics

**Goal:** One pass produces exact totals, deterministic top lists, 24 percentage bins, and safely bounded unique User-Agent results.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 8; `PRD.md` FR-2 through FR-6.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with IP/error URL counters, 24 hourly bins, totals, and the guarded User-Agent set.
2. Create `src/nginx_stream_analyzer/service.py` to combine parsing, invalid accounting, aggregation, and immutable report creation.
3. Create `tests/test_aggregate.py` for error status range, deterministic top-10 ties, common-format UA behavior, zero denominators, and exact cardinality boundary.
4. Assert hourly percentages use `100 × hourly_request_count / total_valid_requests` and not an unscaled fraction.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py -k 'hourly or cardinality or top' -q`

**Commit:** `step-3: add bounded one-pass aggregation`

## STEP 4: Terminal Renderer

**Goal:** Default invocation emits a readable Rich report without allowing log content to become terminal markup.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and section 13; `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` and `terminal.py`.
2. Render totals, top lists, all 24 hourly percentage bins, and User-Agent share with escaped values.
3. Wire `--no-color` and TTY-aware styling without changing report content.
4. Add terminal golden cases to `tests/test_renderers.py` with color disabled.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -k terminal -q`
- `nginx-stream-analyzer --no-color tests/fixtures/combined.log`

**Commit:** `step-4: render safe terminal report`

## STEP 5: JSON Renderer

**Goal:** `--json` emits a complete versioned JSON object with deterministic field and list semantics.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 9 and 13; `PRD.md` US-3 and FR-8.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/json.py` mapping `Report` to the documented schema.
2. Buffer only the final bounded report serialization so fatal failures never leave partial JSON.
3. Add `tests/fixtures/expected/combined.json` and JSON schema/golden assertions to `tests/test_renderers.py`.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -k json -q`
- `nginx-stream-analyzer --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add versioned json output`

## STEP 6: CSV Renderer

**Goal:** `--csv` emits the fixed normalized row schema safely and without terminal decoration.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 9; `PRD.md` US-4 and FR-9.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/csv.py` using the standard `csv` module and fixed columns.
2. Define and test the formula-injection policy for untrusted values.
3. Add `tests/fixtures/expected/combined.csv` and round-trip parsing assertions to `tests/test_renderers.py`.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -k csv -q`
- `nginx-stream-analyzer --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add pipeline-safe csv output`

## STEP 7: Exit Codes and End-to-end Behavior

**Goal:** Every command path obeys the `0/1/2/3/4` contract across file, stdin, and all renderers.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` sections 7 and 9.

**Tasks:**

1. Complete exception-to-exit mapping in `src/nginx_stream_analyzer/cli.py`.
2. Add integration cases to `tests/test_cli.py` for code 0 success, code 1 I/O/decode failure, code 2 usage error, code 3 all-invalid non-empty input, and code 4 unique-cardinality exhaustion.
3. Assert diagnostics use stderr and codes 3/4 emit no partial terminal/JSON/CSV success report.
4. Test empty input as successful zero report and mixed input as successful report with invalid count.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-7: enforce complete cli exit contract`

## STEP 8: Performance, Packaging, and Release Evidence

**Goal:** The release candidate meets correctness, installation, and 1 GB performance gates with reproducible evidence.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` NFR-2 and Release Acceptance.

**Tasks:**

1. Create `tests/perf/generate_log.py` that deterministically generates a representative combined-format corpus outside Git and records line/file size.
2. Create `tests/test_performance.py` for a small default smoke threshold; document the opt-in 1 GB benchmark command and machine-profile capture.
3. Add package build and clean-wheel-install checks to the release procedure in `README.md`.
4. Run formatting, lint, type, unit/integration, coverage, build, install, and benchmark gates; record results without committing the 1 GB corpus.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_stream_analyzer --cov-report=term-missing`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 tests/perf/generate_log.py --size-gib 1 --output /tmp/nginx-stream-analyzer-1g.log`
- `/usr/bin/time -v nginx-stream-analyzer --json /tmp/nginx-stream-analyzer-1g.log >/dev/null`

**Commit:** `step-8: verify performance and release package`

## 11. Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Reproducible package and trustworthy stream parsing | Half day |
| Saturday PM | 3–4 | Correct metrics and default terminal experience | Half day |
| Sunday AM | 5–7 | Pipeline formats and complete failure semantics | Half day |
| Sunday PM | 8 | Performance and release evidence | Half day |

## 12. Deferred Work

After the MVP passes all gates, P1 gzip support may be planned as a separate unit. Configurable top-N and additional log formats remain P2. Database, API, server, auth, cloud, Kubernetes, and historical dashboards remain explicitly out of scope.
