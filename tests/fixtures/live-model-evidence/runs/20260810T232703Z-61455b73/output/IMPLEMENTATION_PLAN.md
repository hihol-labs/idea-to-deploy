# Implementation Plan: nginx-insights

This is a documentation-only execution plan. Implementation must follow `PROJECT_ARCHITECTURE.md` and satisfy the acceptance criteria in `PRD.md`. Work remains WIP=1: complete and verify one step before starting the next.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry-point skeleton | Every test and feature needs import/install boundaries | 1 hour |
| 2 | Shared dataclasses, errors, and exit codes | Parser, aggregator, renderers, and CLI share these contracts | 1 hour |
| 3 | Representative Common/Combined fixtures and golden schemas | Correctness must be executable before feature growth | 1 hour |
| 4 | Benchmark generator and documented laptop protocol | Performance regressions need an early repeatable oracle | 1 hour |

No database schema, migrations, auth system, server, Docker setup, or CI deployment infrastructure belongs in the runway because the approved product is a local stateless CLI.

## Step 1: Package and Quality Skeleton

**Goal:** A clean Python 3.11 environment can install and invoke an empty-but-valid CLI boundary.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Component and File Boundaries; Packaging and Deployment.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build backend, test/lint/type-check groups, and `nginx-insights = nginx_insights.cli:main`.
2. Create `src/nginx_insights/__init__.py`, `src/nginx_insights/__main__.py`, `src/nginx_insights/cli.py`, and `src/nginx_insights/render/__init__.py`.
3. Create `tests/conftest.py` and tool configuration for pytest, coverage, Ruff, and mypy.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-insights --help`
- `.venv/bin/python -m pytest`

**Commit:** `step-1: establish installable CLI skeleton`

## Step 2: Domain and Failure Contracts

**Goal:** Shared immutable models and the exact `0/1/2/3/4` behavior are test-defined.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` — Data Model and Algorithms; CLI Interface.

**Tasks:**

1. Create `src/nginx_insights/models.py` with frozen `AccessRecord`, ranked item, hourly bucket, summary, and report dataclasses.
2. Create `src/nginx_insights/errors.py` with typed runtime, no-valid-records, and cardinality-exhaustion exceptions plus exit constants.
3. Create `tests/test_exit_codes.py` covering: `0` success/help/version, `1` I/O/runtime, `2` usage, `3` zero-valid-input, and `4` unique-cardinality exhaustion with no partial stdout.

**Verification:**

- `.venv/bin/python -m pytest tests/test_exit_codes.py -q`
- `.venv/bin/python -m mypy src`

**Commit:** `step-2: define models and complete exit contract`

## Step 3: Streaming nginx Parser

**Goal:** Common and Combined lines become typed records without retaining input.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — AccessRecord; Inputs.

**Tasks:**

1. Create `src/nginx_insights/parser.py` with one precompiled structural pattern, timestamp parsing, request-target normalization, and an invalid-line result.
2. Create `tests/fixtures/common.log`, `tests/fixtures/combined.log`, and `tests/fixtures/mixed_invalid.log` with IPv4, IPv6, timezone, escaped User-Agent, query, 4xx, 5xx, blank, and malformed cases.
3. Create `tests/test_parser.py` covering required fields, Common missing-UA semantics, normalization, and skip decisions.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m ruff check src/nginx_insights/parser.py tests/test_parser.py`

**Commit:** `step-3: parse common and combined logs`

## Step 4: One-Pass Aggregation

**Goal:** One input pass produces all exact report values and deterministic rankings.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Aggregation state; Complexity and performance budget.

**Tasks:**

1. Create `src/nginx_insights/aggregate.py` with counters, 24 buckets, exact bounded UA set, and report finalization.
2. Implement top-10 ordering by count descending then key ascending.
3. Implement hourly percentages using `100 × hourly_request_count / total_valid_requests` and unique-UA percentage from distinct non-empty values.
4. Create `tests/test_aggregate.py` for status boundaries 399/400/599/600, ties, 24 buckets, skipped denominators, Common logs, rounding, and the ceiling boundary.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_insights.aggregate --cov-fail-under=90`

**Commit:** `step-4: aggregate all reports in one pass`

## Step 5: Terminal Renderer

**Goal:** Default output is readable Rich text and safe for terminals and redirection.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Outputs; Configuration, Security, and Privacy.

**Tasks:**

1. Create `src/nginx_insights/render/text.py` with summary and four named report sections.
2. Escape untrusted IP/path values and make color conditional on TTY, `--no-color`, and `NO_COLOR`.
3. Create `tests/golden/report.txt` and `tests/test_render_text.py` for TTY/non-TTY and control/markup payloads.

**Verification:**

- `.venv/bin/python -m pytest tests/test_render_text.py -q`
- `NO_COLOR=1 .venv/bin/nginx-insights tests/fixtures/combined.log`

**Commit:** `step-5: render safe terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipeline modes implement the exact stable schemas without presentation leakage.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Outputs.

**Tasks:**

1. Create `src/nginx_insights/render/json.py` with schema version 1, fixed top-level keys, 24 ordered hours, and numeric percentages.
2. Create `src/nginx_insights/render/csv.py` using the standard `csv` module and the fixed `report,rank,key,count,percentage` header/order.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_render_machine.py` covering quoting, UTF-8, ordering, and absence of ANSI bytes.

**Verification:**

- `.venv/bin/python -m pytest tests/test_render_machine.py -q`
- `.venv/bin/nginx-insights --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: CLI Integration and Acceptance Matrix

**Goal:** The installed command owns input/output correctly and all P0 stories pass end-to-end.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — CLI Interface; `PRD.md` — User Stories.

**Tasks:**

1. Complete `src/nginx_insights/cli.py` with `[INPUT]`, stdin, mutually exclusive `--json`/`--csv`, `--no-color`, positive `--max-unique-user-agents`, help, and version.
2. Map the public contract without omission or remapping: `0` success, `1` I/O/runtime, `2` usage/configuration, `3` zero valid records, `4` unique-cardinality exhaustion.
3. Ensure errors use stderr, machine data uses stdout, and exits 3/4 emit no partial report.
4. Create `tests/test_cli.py` with Click's runner plus subprocess tests for file, stdin, pipes, all formats, malformed mixtures, missing file, conflicting options, and cardinality exhaustion.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py tests/test_exit_codes.py -q`
- `.venv/bin/nginx-insights --json tests/fixtures/combined.log | .venv/bin/python -c 'import json,sys; assert json.load(sys.stdin)["schema_version"] == 1'`

**Commit:** `step-7: integrate CLI and acceptance contracts`

## Step 8: Performance, Packaging, and Release Evidence

**Goal:** The release candidate meets correctness, memory, installation, and 1 GB performance gates.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Complexity and performance budget; Packaging and Deployment; `STRATEGIC_PLAN.md` — Definition of Done.

**Tasks:**

1. Create `tests/perf/generate_log.py` to deterministically produce the documented 1 GB valid-log corpus outside version control.
2. Create `tests/perf/test_throughput.py` or a benchmark command that records platform/profile, performs one warm-up and three measured runs, and checks the median under 30 seconds.
3. Create `tests/test_no_side_effects.py` to assert no network use, source mutation, or created data files.
4. Update `README.md` with installation, examples, formats, limitations, performance protocol, and exit codes.
5. Build wheel/sdist, install the wheel in a fresh temporary Python 3.11 environment, run all quality gates, and reconcile release evidence.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_insights --cov-fail-under=90`
- `.venv/bin/python -m ruff check . && .venv/bin/python -m mypy src`
- `.venv/bin/python tests/perf/generate_log.py --size 1GB --output /tmp/nginx-insights-1gb.log && .venv/bin/python -m pytest tests/perf/test_throughput.py -q --log-file /tmp/nginx-insights-1gb.log`
- `.venv/bin/python -m build && tmp_env="$(mktemp -d)" && python3.11 -m venv "$tmp_env/venv" && "$tmp_env/venv/bin/pip" install dist/*.whl && "$tmp_env/venv/bin/nginx-insights" --version`

**Commit:** `step-8: verify performance and release package`

## Sprint Boundaries

The one-weekend cadence uses work blocks rather than multi-week sprints.

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday morning | 1–3 | Runway, failure contract, parsing | 4–5 hours |
| Saturday afternoon | 4 | Correct one-pass report model | 2–3 hours |
| Sunday morning | 5–7 | All interfaces and end-to-end acceptance | 5 hours |
| Sunday afternoon | 8 | Performance and release evidence | 3 hours |

## Dependency and Risk Notes

- RICE value informs ordering within dependency constraints: shared ingestion and aggregation must exist before their high-value report surfaces can be accepted.
- The exact UA set is the only deliberately capped metric; exit 4 is preferable to silent approximation.
- If the benchmark fails, profile before considering Variant B. Do not add processes, a database, or a server without changing the architecture and PRD first.
- Each step produces evidence before the next begins; narrative completion is not sufficient.
