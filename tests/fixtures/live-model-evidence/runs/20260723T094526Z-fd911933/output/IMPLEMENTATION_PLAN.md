# Implementation Plan: Nginx Stream Analytics CLI

## Planning Assumptions

This is a one-weekend, single-developer plan. It implements P0 before P1/P2 and follows [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and the acceptance criteria in [PRD.md](PRD.md). Each step ends with executable evidence; commands shown here are plans and must not be reported as run until implementation begins.

## Architectural Runway

| # | Item | Why first | Effort |
|---|---|---|---:|
| 1 | Python 3.11 package and console entry point | Every CLI and test invocation depends on installability | 0.5 h |
| 2 | Representative, hand-auditable log fixtures | Parser and reports need an agreed truth set | 0.5 h |
| 3 | Benchmark protocol and fixture generator design | Performance risk must be measured before polish | 0.5 h |
| 4 | CI test matrix for Python 3.11 | Prevents late packaging and compatibility surprises | 0.5 h |

There is deliberately no database schema, auth system, Docker environment, API scaffold, or deployment pipeline beyond Python packaging.

## STEP 1: Package Skeleton and CLI Contract

**Goal:** A clean Python 3.11 environment can install the package and invoke the documented command and options.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 7, and 11; `PRD.md` FR-1, FR-6, and NFR-5.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, and the `nginx-stream-analytics` console entry point.
2. Create `src/nginx_stream_analytics/__init__.py` with package version metadata.
3. Create `src/nginx_stream_analytics/cli.py` with Click declarations for input, `--json`, `--csv`, `--strict`, `--no-color`, `--help`, and `--version`; reject conflicting machine formats.
4. Create `tests/test_cli.py` covering help, version, stdin selection, and option conflicts.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-stream-analytics --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Typed Models and Nginx Parser

**Goal:** Supported combined-log lines become typed, timezone-aware records and malformed input has explicit behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 6; `PRD.md` FR-2 and FR-8.

**Tasks:**

1. Create `src/nginx_stream_analytics/models.py` with frozen `LogRecord`, `RankedCount`, `HourlyCount`, and `AnalysisReport` dataclasses.
2. Create `src/nginx_stream_analytics/parser.py` with one compiled combined-format parser, quoted-field unescaping, integer/range checks, and a typed parse error.
3. Create `tests/fixtures/combined.log` with IPv4, IPv6, query strings, missing fields, escaped quotes, timezone offsets, 2xx/4xx/5xx responses, one malformed line, and an invalid-UTF-8 binary fixture.
4. Create `tests/test_parser.py` with parameterized valid and invalid cases.

**Verification:**

- `pytest -q tests/test_parser.py`
- `python3.11 -m compileall -q src`

**Commit:** `step-2: parse supported nginx combined logs`

## STEP 3: One-Pass Aggregation Core

**Goal:** One scan calculates total/malformed counts, top IPs, top error URLs, 24 hourly buckets, and exact User-Agent share.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 8; `PRD.md` FR-3 through FR-5.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with a mutable internal accumulator and immutable final report.
2. Apply 400–599 error classification, exact User-Agent set semantics, and 24 ordered hour buckets.
3. Implement deterministic top-10 selection using the complete `(-count, key)` comparison.
4. Create `tests/test_aggregate.py` for a 12-way equal-count tie in shuffled input order, fewer/more than ten keys, empty input, repeated UAs, timezones, and 399/400/599 status boundaries.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q --cov=nginx_stream_analytics.aggregate --cov-branch --cov-fail-under=90 tests/test_aggregate.py`

**Commit:** `step-3: implement exact streaming metrics`

## STEP 4: JSON Renderer

**Goal:** `--json` emits one deterministic schema-versioned document with no terminal control bytes.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` section 7 JSON schema; `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_stream_analytics/render_json.py` to map report dataclasses to schema version 1.
2. Create `tests/fixtures/expected.json` as a hand-reviewed golden output.
3. Extend `tests/test_renderers.py` and `tests/test_cli.py` for valid JSON, stable keys/ordering, empty input, redirected output, and ANSI absence.

**Verification:**

- `nginx-stream-analytics --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `pytest -q tests/test_renderers.py tests/test_cli.py -k json`

**Commit:** `step-4: add stable JSON output`

## STEP 5: CSV Renderer

**Goal:** `--csv` emits one standards-compliant normalized table containing every report section.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` section 7 CSV schema; `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_stream_analytics/render_csv.py` using Python's `csv` module and the exact six-column schema.
2. Neutralize spreadsheet formula prefixes in untrusted keys while preserving valid CSV quoting.
3. Create `tests/fixtures/expected.csv` with all row types and adversarial comma, quote, newline, and formula-prefix values.
4. Extend `tests/test_renderers.py` and `tests/test_cli.py` for round-trip parsing and ANSI absence.

**Verification:**

- `nginx-stream-analytics --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert rows'`
- `pytest -q tests/test_renderers.py tests/test_cli.py -k csv`

**Commit:** `step-5: add safe normalized CSV output`

## STEP 6: Rich Terminal Report

**Goal:** Default output is readable colored terminal text and remains clean when redirected or color is disabled.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 7 and 9; `PRD.md` FR-6.

**Tasks:**

1. Create `src/nginx_stream_analytics/render_text.py` with four labeled Rich tables and a concise summary.
2. Convert ESC, CR, C0/C1 controls, and bidi override/isolate controls to visible notation, then escape all log-derived values from Rich markup.
3. Connect automatic TTY detection, `--no-color`, and `NO_COLOR` in `src/nginx_stream_analytics/cli.py`.
4. Add terminal/non-terminal and markup-injection cases to `tests/test_renderers.py` and `tests/test_cli.py`.

**Verification:**

- `NO_COLOR=1 nginx-stream-analytics tests/fixtures/combined.log`
- `pytest -q tests/test_renderers.py tests/test_cli.py -k 'text or color or markup'`

**Commit:** `step-6: render safe Rich terminal reports`

## STEP 7: Streaming I/O and Error Semantics

**Goal:** File/stdin input, lenient and strict parsing, stderr diagnostics, exit codes, and broken pipes match the architecture.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6, 7, and 12; `PRD.md` FR-1, FR-8, and NFR-4.

**Tasks:**

1. Complete binary line-by-line input orchestration in `src/nginx_stream_analytics/cli.py` without whole-file reads; decode UTF-8 per line inside strict/lenient accounting.
2. Add bounded malformed-line diagnostics and strict first-error termination without echoing entire sensitive lines.
3. Handle unreadable files, invalid UTF-8 policy, empty input, and downstream broken pipes.
4. Expand `tests/test_cli.py` with Click's isolated filesystem and stdin runner cases.

**Verification:**

- `printf '%s\n' 'bad line' | nginx-stream-analytics --json`
- `sh -c "printf '%s\n' 'bad line' | nginx-stream-analytics --strict >/dev/null; test $? -eq 2"`
- `pytest -q tests/test_cli.py`

**Commit:** `step-7: finalize streaming and failure behavior`

## STEP 8: Performance and Memory Evidence

**Goal:** A reproducible benchmark proves or falsifies the 1 GB/30 s target and records peak RSS and cardinality assumptions.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 8; `PRD.md` NFR-1 and kill criteria.

**Tasks:**

1. Create `tools/generate_benchmark_log.py` to deterministically produce exact-size typical and high-cardinality 1 GiB profiles without committing generated files.
2. Create `tests/test_performance.py` for a CI-sized throughput regression threshold, kept separate from the 1 GiB acceptance run.
3. Create `docs/BENCHMARK.md` with CPU, RAM, OS, Python version, cache policy, command, file hash/size, key cardinalities/average lengths, elapsed seconds, peak RSS, and result for both profiles.
4. Microbenchmark the parser on at least 100 MiB. If its projected 1 GiB time exceeds 18 seconds, implement/profile the bounded-scanner path described in the architecture and preserve before/after evidence.

**Verification:**

- `python3.11 tools/generate_benchmark_log.py --profile typical --size-gib 1 /tmp/nginx-typical-1g.log`
- `/usr/bin/time -v nginx-stream-analytics --json /tmp/nginx-typical-1g.log >/dev/null`
- `python3.11 tools/generate_benchmark_log.py --profile high-cardinality --size-gib 1 /tmp/nginx-high-cardinality-1g.log`
- `/usr/bin/time -v nginx-stream-analytics --json /tmp/nginx-high-cardinality-1g.log >/dev/null`
- `pytest -q tests/test_performance.py`

**Commit:** `step-8: establish performance acceptance evidence`

## STEP 9: Release Quality and Documentation

**Goal:** The wheel installs cleanly, all contracts are tested, and a user can run the CLI within 30 seconds.

**Time:** ~2 hours

**Context:** All architecture and PRD sections; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Update `README.md` with actual install, examples, schemas, supported log format, privacy, and limitations.
2. Create `.github/workflows/ci.yml` for Python 3.11 lint, type checks, tests, coverage, and package build.
3. Create `tests/test_package.py` for installed console-script smoke checks and distribution metadata.
4. Run the full verification matrix and reconcile any spec changes across `PRD.md`, `PROJECT_ARCHITECTURE.md`, and golden fixtures before tagging.

**Verification:**

- `ruff check src tests tools`
- `mypy src`
- `pytest -q --cov=nginx_stream_analytics --cov-branch --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-cli-release && /tmp/nginx-cli-release/bin/pip install dist/*.whl && /tmp/nginx-cli-release/bin/nginx-stream-analytics --version`

**Commit:** `step-9: validate release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable parser and core metrics | Friday evening–Saturday morning |
| Weekend block 2 | 4–7 | Stable text/JSON/CSV interfaces and errors | Saturday afternoon–Sunday morning |
| Weekend block 3 | 8–9 | Performance evidence and release quality | Sunday afternoon/evening |

## Dependency and WIP Rules

Only one step is active at a time. Do not begin a later step until the current step's listed verification passes or a recovery note records the blocker. Any output-schema behavior change begins as a PRD/architecture edit, then updates implementation and golden fixtures. P2 features are excluded from this plan.
