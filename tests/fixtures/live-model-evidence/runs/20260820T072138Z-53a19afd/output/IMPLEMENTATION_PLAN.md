# Implementation Plan: nginx Stream Analytics CLI

## Planning Rules

- Scope is the P0 MVP in `PRD.md`; P1 gzip is attempted only after every P0 gate passes. P2 work is deferred.
- Preserve the approved one-process, stateless architecture in `PROJECT_ARCHITECTURE.md`.
- Implement by specification: change the PRD/architecture contract before intentionally changing behavior.
- Each step ends with its listed checks and a reviewable commit. Do not begin a second unfinished step (WIP=1).

## Exit-code contract used by every step

All CLI implementation and tests must preserve the complete mapping:

| Code | Required meaning |
|---:|---|
| `0` | Successful complete report, including mixed valid/malformed input |
| `1` | Unexpected internal error |
| `2` | CLI usage or input I/O error |
| `3` | Zero valid nginx records |
| `4` | Unique-cardinality exhaustion; the exact User-Agent limit would be exceeded |

Code `4` is never omitted, remapped, collapsed into code `1`/`2`/`3`, or replaced by approximate counting. Expected failures emit no partial report.

## Architectural Runway

Infrastructure and architecture work required before feature work is deliberately local and small:

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console entry point | Every behavioral check must run the installed command | 1 h |
| 2 | Typed dataclasses and module boundaries | Parser, aggregator, and renderers need one stable contract | 1 h |
| 3 | Deterministic fixtures and test helpers | Metrics and output need independently stated expected values | 1.5 h |
| 4 | Local quality configuration | Formatting, typing, and tests should gate every later step | 0.5 h |

There is no database schema, authentication system, Docker setup, service deployment, or CI/CD service dependency because the product is a local CLI with a $0 budget.

## STEP 1: Package skeleton and executable contract

**Goal:** A pip-installed `nginx-stream-report` command exposes help/version and the approved options without implementing reports.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4 and `CLI Interface`; `PRD.md` FR-1, FR-6, FR-7.

**Files:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12` (or a documented compatible upper policy), Click/Rich runtime dependencies, build backend, console script, pytest/Ruff/mypy configuration.
2. Create `src/nginx_stream_report/__init__.py` with package version metadata.
3. Create `src/nginx_stream_report/cli.py` with Click argument/options, mutual exclusion, stdin/path declaration, and a thin composition placeholder.
4. Create `tests/test_cli.py` for help, version, invalid option combinations, and invalid cardinality limit.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-1: scaffold installable CLI contract`

## STEP 2: Combined-format parser and input lifecycle

**Goal:** Plain file and stdin streams yield typed valid records while malformed lines and I/O failures remain distinguishable.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5–7 and `CLI Interface`; `PRD.md` US-1.

**Files:**

1. Create `src/nginx_stream_report/models.py` with frozen/slotted `LogRecord` and initial report dataclasses.
2. Create `src/nginx_stream_report/parser.py` with precompiled combined-format parsing and request-target extraction.
3. Create `src/nginx_stream_report/input.py` with read-only binary path/stdin context management and line decoding policy.
4. Create `tests/fixtures/basic.log`, `tests/fixtures/malformed.log`, and `tests/test_parser.py` with IPv4, IPv6, quoted User-Agent, timestamp, malformed, and invalid-status cases.
5. Extend `tests/test_cli.py` for missing/unreadable input (`2`) and zero-valid input (`3`).

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py tests/test_cli.py -q`
- `.venv/bin/ruff check src/nginx_stream_report tests`
- `.venv/bin/mypy src`

**Commit:** `step-2: parse combined logs from file and stdin`

## STEP 3: High-value rankings and deterministic aggregation

**Goal:** One pass computes exact top-10 IP and 4xx/5xx URL rankings with deterministic ties.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5–6; `PRD.md` US-2, US-3, FR-3.

**Files:**

1. Create `src/nginx_stream_report/aggregate.py` with IP/error-URL counters and report finalization.
2. Complete `RankedItem` and ranking fields in `src/nginx_stream_report/models.py`.
3. Create `tests/test_aggregate.py` for status boundaries (`399/400/499/500/599/600`), fewer-than-ten, more-than-ten, ties, repeated targets, and query-string identity.
4. Extend `tests/fixtures/basic.log` with independently counted ranking cases.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-3: aggregate deterministic IP and error URL rankings`

## STEP 4: Hourly distribution and exact User-Agent share

**Goal:** The same pass computes 24 hourly percentage buckets and exact User-Agent diversity, stopping safely at its limit.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5–6; `PRD.md` US-4, US-5, FR-4, FR-5.

**Files:**

1. Extend `src/nginx_stream_report/aggregate.py` with a 24-counter array, exact User-Agent set, pre-insertion limit check, and typed cardinality-exhaustion error.
2. Complete `HourBucket` and `Report` in `src/nginx_stream_report/models.py`.
3. Extend `src/nginx_stream_report/cli.py` to map cardinality exhaustion only to exit code `4`.
4. Extend `tests/test_aggregate.py` for all 24 buckets, multiple dates/offsets, placeholders, duplicates, rounding, and the literal calculation `100 × hourly_request_count / total_valid_requests`.
5. Extend `tests/test_cli.py` to prove limit-at-boundary succeeds, limit-plus-one returns `4`, stdout is empty, and stderr is concise.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py tests/test_cli.py -q`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-4: add hourly and bounded exact user-agent metrics`

## STEP 5: Rich terminal renderer

**Goal:** Default output is a safe, readable Rich report whose values exactly match the domain report.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 8–10; `PRD.md` US-6.

**Files:**

1. Create `src/nginx_stream_report/renderers/__init__.py` with renderer selection/protocol.
2. Create `src/nginx_stream_report/renderers/terminal.py` with summary, ranking, hourly, and unique-agent sections.
3. Wire terminal rendering in `src/nginx_stream_report/cli.py`, including TTY detection, `NO_COLOR`, `--color`, and `--no-color` policy.
4. Create `tests/test_renderers.py` and malicious/control-character fixtures to prove values are text, not Rich markup or terminal instructions.
5. Add terminal golden outputs under `tests/fixtures/expected/` for color-disabled deterministic assertions.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py tests/test_cli.py -q`
- `NO_COLOR=1 .venv/bin/nginx-stream-report tests/fixtures/basic.log`
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-5: render safe rich terminal report`

## STEP 6: JSON and CSV pipeline renderers

**Goal:** `--json` and `--csv` expose stable, ANSI-free, golden-tested representations of the identical report.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` and Section 9; `PRD.md` US-7.

**Files:**

1. Create `src/nginx_stream_report/renderers/json.py` with `schema_version: 1` and numeric count/percentage values.
2. Create `src/nginx_stream_report/renderers/csv.py` with fixed columns and normalized ordered section rows.
3. Extend `src/nginx_stream_report/renderers/__init__.py` and `src/nginx_stream_report/cli.py` to select exactly one renderer.
4. Add `tests/fixtures/expected/basic.json` and `tests/fixtures/expected/basic.csv`.
5. Extend `tests/test_renderers.py` and `tests/test_cli.py` for schema, types, ordering, newlines, stdout/stderr separation, ANSI absence, and broken pipes.

**Verification:**

- `.venv/bin/nginx-stream-report --json tests/fixtures/basic.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-stream-report --csv tests/fixtures/basic.log > /tmp/nginx-stream-report.csv`
- `.venv/bin/python -m pytest tests/test_renderers.py tests/test_cli.py -q`
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-6: add stable JSON and CSV renderers`

## STEP 7: Full failure matrix, packaging, and optional gzip

**Goal:** All exit paths are regression-tested, distribution artifacts install cleanly, and P1 gzip is added only if the P0 suite is already green.

**Time:** ~3 hours P0; +1 hour optional P1

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface`, Sections 10–11; `PRD.md` FR-7, US-8.

**Files:**

1. Extend `src/nginx_stream_report/cli.py` with narrow typed failure mapping and unexpected-error boundary.
2. Extend `tests/test_cli.py` to exercise exact codes `0`, `1`, `2`, `3`, and `4`, asserting no traceback and no partial stdout for failures.
3. Create `tests/test_packaging.py` or a release script check for wheel metadata and console entry point.
4. Update `README.md` with actual installation, examples, schemas, metric definitions, and the full exit table.
5. If P0 is green with time remaining, extend `src/nginx_stream_report/input.py` and tests for `.gz` streaming/corruption as P1.

**Verification:**

- `.venv/bin/python -m pytest -q --cov=nginx_stream_report --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python -m build`
- Create a fresh temporary virtual environment, install `dist/*.whl`, then run `nginx-stream-report --help` and a fixture report.
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-7: harden failure contract and distribution`

## STEP 8: Correctness and 1 GB performance acceptance

**Goal:** The exact release candidate passes quality, resource, and under-30-second acceptance with reproducible evidence.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 12; `PRD.md` NFR-1 through NFR-6 and Release Acceptance.

**Files:**

1. Create `tests/test_performance.py` for a small, non-flaky throughput smoke threshold and report correctness.
2. Create `scripts/generate_benchmark_log.py` with deterministic seed/parameters; generated 1 GB output remains ignored and outside Git.
3. Create `scripts/benchmark.py` or a documented argv-safe runner recording bytes, cardinalities, environment, elapsed time, and peak RSS.
4. Create `docs/BENCHMARK.md` with reference laptop details, generation command, correctness oracle, warm-up, three measurements, median, and result.
5. Update `README.md`, `PRD.md`, and `CLAUDE.md` only if measured behavior requires a spec-approved clarification.

**Verification:**

- `.venv/bin/ruff check . && .venv/bin/mypy src`
- `.venv/bin/python -m pytest -q --cov=nginx_stream_report --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python scripts/generate_benchmark_log.py --bytes 1073741824 --output /tmp/nginx-stream-report-1gb.log`
- Run the documented benchmark once as warm-up and three measured times; confirm report totals, median `<30.0 s`, and record peak RSS.
- Build a wheel and repeat a representative CLI smoke test from a clean temporary environment.

**Commit:** `step-8: verify correctness performance and release readiness`

## Weekend Boundaries

| Block | Steps | Goal | Time budget |
|---|---|---|---:|
| Saturday morning | 1–2 | Installable CLI, parser, and fixtures | 5 h |
| Saturday afternoon | 3–4 | All four exact metrics and cardinality guard | 6 h |
| Sunday morning | 5–6 | Human and pipeline renderers | 5.5 h |
| Sunday afternoon | 7–8 | Failure matrix, packaging, and measured acceptance | 7 h |

If time is constrained, omit P1 gzip before reducing P0 verification. P2 configurable top-N is not part of this plan.

## Final Acceptance Checklist

- [ ] `PRD.md` P0 acceptance criteria all have automated evidence.
- [ ] Exit codes `0/1/2/3/4` are exercised and retain their exact meanings, including `4` for unique-cardinality exhaustion.
- [ ] Default, JSON, and CSV reports contain equal underlying metric values.
- [ ] Hourly percentages use `100 × hourly_request_count / total_valid_requests` and all 24 buckets are present.
- [ ] Quality suite and >=90% product-module coverage pass.
- [ ] Clean pip wheel install works on Python 3.11.
- [ ] Representative 1 GB median processing time is under 30 seconds on the documented reference laptop.
- [ ] No database, HTTP API, server, authentication, cloud, or Kubernetes implementation has entered scope.
