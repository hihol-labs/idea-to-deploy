# Implementation Plan: nginx Log Top

This is a one-weekend, single-developer plan. It orders shared risk before presentation while respecting the RICE priorities in `STRATEGIC_PLAN.md`. No product code is included in this blueprint.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package skeleton and console entry point | Every behavior and clean-install check depends on import/package boundaries | 1 hour |
| 2 | Frozen dataclass and CLI/output contracts | Prevents renderer and aggregation drift | 1 hour |
| 3 | Representative fixtures and benchmark generator | Correctness and performance need evidence from the start | 1.5 hours |
| 4 | Static/test tooling | Each subsequent step needs a repeatable machine check | 0.5 hour |

There is no database schema, auth system, server, Docker setup, or CI/CD deployment runway because those are explicitly outside the architecture.

## Step 1: Establish packaging and executable CLI

**Goal:** A clean Python 3.11 environment can install the package and invoke help/version without reading input.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4, 9, and 10; `PRD.md` NFR-01.

**Tasks:**

1. Create `pyproject.toml` with Python bounds, Click/Rich dependencies, build backend, and `nginx-log-top` entry point.
2. Create `src/nginx_log_top/__init__.py` with version metadata.
3. Create `src/nginx_log_top/cli.py` with the Click command surface only.
4. Create `tests/test_cli.py` for help, version, and option exclusivity.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e .`
- `.venv/bin/nginx-log-top --help`
- `.venv/bin/pytest tests/test_cli.py`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Freeze domain models and fixtures

**Goal:** Parsed request, report, ranking, diagnostics, and serialization shapes are explicit and test fixtures cover normal and adversarial input.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 5 and `## CLI Interface`; `PRD.md` US-01 through US-09.

**Tasks:**

1. Create `src/nginx_log_top/models.py` with `ParsedRequest`, report-row, diagnostics, and `AnalysisReport` dataclasses.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/common.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/ties.log`, including the architecture grammar’s explicit acceptance/rejection cases.
3. Create `tests/test_models.py` for invariants, empty-report semantics, and 24-hour shape.

**Verification:**

- `.venv/bin/pytest tests/test_models.py`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: define report contracts and fixtures`

## Step 3: Implement and harden the streaming parser

**Goal:** Supported common/combined lines become `ParsedRequest` values, while malformed lines fail cheaply and safely.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5, 7, and 8; `PRD.md` FR-02 and NFR-07.

**Tasks:**

1. Create `src/nginx_log_top/parser.py` with a bounded, non-backtracking parser for required fields.
2. Create `tests/test_parser.py` for IPv4/IPv6, quoted values, escaped characters, timezones, request targets, invalid status/timestamp, truncated lines, and hostile markup.
3. Add property/fuzz-style cases that prove malformed input returns a controlled parse result rather than an exception.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py`
- `.venv/bin/ruff check src/nginx_log_top/parser.py tests/test_parser.py`

**Commit:** `step-3: parse supported nginx access logs`

## Step 4: Add input streaming and diagnostics

**Goal:** File and stdin adapters yield decoded lines, classify open/read failures, bound diagnostic samples, and never retain the input.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 7 and 8 and `## CLI Interface`; `PRD.md` US-01 and US-09.

**Tasks:**

1. Create `src/nginx_log_top/input.py` for buffered binary file/stdin iteration and per-line UTF-8 replacement decoding.
2. Connect `src/nginx_log_top/cli.py` to select the input source and map open/read/interrupt/broken-pipe errors.
3. Extend `tests/test_cli.py` with stdin/file equivalence, missing/unreadable path, invalid bytes, empty input, malformed-only input, Ctrl-C simulation, and broken-pipe behavior.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py -k 'input or stdin or pipe or malformed'`
- `.venv/bin/nginx-log-top does-not-exist.log; test $? -eq 3`

**Commit:** `step-4: stream file and stdin inputs`

## Step 5: Implement exact aggregations

**Goal:** One pass produces exact top-IP, error-URL, hourly, and User-Agent state with deterministic final rankings.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4, 5, and 7; `PRD.md` US-02 through US-05.

**Tasks:**

1. Create `src/nginx_log_top/aggregate.py` with counters, 24 buckets, User-Agent set, and bounded malformed diagnostics.
2. Create `src/nginx_log_top/reports.py` for deterministic top-10 selection and final `AnalysisReport` construction.
3. Create `tests/test_aggregate.py` for exact counts, 400/599 boundaries, 399/600 exclusion, ties, query strings, timezones, empty input, and invariant sums.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_log_top.aggregate --cov=nginx_log_top.reports --cov-fail-under=90`

**Commit:** `step-5: compute exact streaming reports`

## Step 6: Deliver the versioned JSON renderer

**Goal:** `--json` emits the complete schema-versioned report and nothing else on stdout.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` US-07.

**Tasks:**

1. Create `src/nginx_log_top/renderers/__init__.py`.
2. Create `src/nginx_log_top/renderers/json.py` using the standard JSON serializer and explicit schema mapping.
3. Create `tests/test_json_output.py` and `tests/golden/report.json` for schema, escaping, stable ordering, zero values, and stdout/stderr separation.

**Verification:**

- `.venv/bin/pytest tests/test_json_output.py`
- `.venv/bin/nginx-log-top --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON output`

## Step 7: Deliver safe terminal output

**Goal:** Default output is readable colored Rich content on a TTY and safe plain text in pipes.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4 and 8 and `## CLI Interface`; `PRD.md` US-06.

**Tasks:**

1. Create `src/nginx_log_top/renderers/terminal.py` with four labeled tables, bounded diagnostics, and the required control/bidi display sanitizer.
2. Escape untrusted values after sanitization and implement TTY, `--no-color`, and optional `NO_COLOR` behavior.
3. Create `tests/test_terminal_output.py` for labels, values, markup injection, color enable/disable, and width-independent semantic assertions.

**Verification:**

- `.venv/bin/pytest tests/test_terminal_output.py`
- `NO_COLOR=1 .venv/bin/nginx-log-top tests/fixtures/combined.log | sed -n '1,20p'`

**Commit:** `step-7: render safe terminal reports`

## Step 8: Deliver normalized CSV output

**Goal:** `--csv` emits the documented normalized schema with every report represented.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` US-08.

**Tasks:**

1. Create `src/nginx_log_top/renderers/csv.py` using the standard `csv` module and the documented spreadsheet-formula prefix protection.
2. Create `tests/test_csv_output.py` and `tests/golden/report.csv` for header, discriminator rows, quoting, newline behavior, and stdout cleanliness.
3. Wire the renderer selection in `src/nginx_log_top/cli.py`.

**Verification:**

- `.venv/bin/pytest tests/test_csv_output.py`
- `.venv/bin/nginx-log-top --csv tests/fixtures/combined.log | .venv/bin/python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-8: add normalized CSV output`

## Step 9: Prove end-to-end contracts and quality

**Goal:** The installed command meets all P0/P1 interface, correctness, isolation, and coverage requirements.

**Time:** ~2.5 hours

**Context:** `PRD.md` Sections 5, 6, and 9; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Complete `tests/test_cli.py` with exit-code and renderer mutual-exclusion matrices.
2. Create `tests/test_no_side_effects.py` to verify no files or network connections are created.
3. Configure Ruff, type checking, pytest, and coverage in `pyproject.toml`.
4. Build wheel/sdist and install the wheel in a fresh virtual environment.

**Verification:**

- `.venv/bin/ruff check src tests`
- `.venv/bin/mypy src`
- `.venv/bin/pytest --cov=nginx_log_top --cov-fail-under=90`
- `.venv/bin/python -m build && .venv-clean/bin/pip install dist/*.whl && .venv-clean/bin/nginx-log-top --version`

**Commit:** `step-9: verify end-to-end CLI contracts`

## Step 10: Benchmark, document, and freeze the release candidate

**Goal:** The exact staged candidate has performance evidence, current docs, and a passing risk-tier adjudication receipt.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 10 and 11; `PRD.md` NFR-02 and release acceptance.

**Tasks:**

1. Create `benchmarks/generate_log.py` with deterministic representative, high-cardinality, and parser-stress profiles plus seed/cardinality/line-size metadata; create `benchmarks/README.md` with the reference hardware protocol.
2. Create `tests/test_performance.py` for a small CI regression threshold; run all architecture acceptance profiles separately and record wall time, peak RSS, output hash, wheel hash, and environment.
3. Update `README.md`, `CLAUDE.md`, and release notes so examples and `--help` agree.
4. Freeze the exact staged candidate, run the repository machine oracle, and apply the required risk-tier checker under `.itd/VERIFICATION_LOOP_CONTRACT.json`.

**Verification:**

- `/usr/bin/time -v .venv/bin/nginx-log-top --json benchmarks/fixture-1g.log > /tmp/nginx-log-top-report.json`
- `.venv/bin/pytest && .venv/bin/ruff check src tests && .venv/bin/mypy src`
- `python3 .itd/itd_hygiene.py`
- `test -f .itd-memory/verification-receipt.json`

**Commit:** `step-10: benchmark and freeze release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable surface, contracts, and parser | ~6 hours |
| Saturday PM | 4–5 | Streaming input and all exact metrics | ~4.5 hours |
| Sunday AM | 6–8 | JSON, terminal, and CSV output | ~5 hours |
| Sunday PM | 9–10 | Quality, package, benchmark, and candidate acceptance | ~5 hours |

## Dependency and Stop Rules

- Do not start renderer work before models and aggregation contracts pass.
- If Step 3 cannot parse representative common/combined logs reliably, stop and revise the supported grammar in the PRD.
- If the early small benchmark projects beyond 30 seconds per GiB, profile before adding presentation features.
- Do not introduce a database, service, cloud, or multi-process redesign within this unit; revise `SCOPE_LOCK.md` and product documents first.

## Handoff

Start with Step 1 and preserve WIP=1. At each step, update the status table in `CLAUDE.md`, record actual verification output, and keep acceptance criteria aligned with `PRD.md`. Completion requires a current exact-candidate adjudication receipt, not a prose “passed” statement.
