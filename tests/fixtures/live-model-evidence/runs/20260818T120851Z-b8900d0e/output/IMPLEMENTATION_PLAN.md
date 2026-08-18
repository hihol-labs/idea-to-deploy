# Implementation Plan: Nginx Insights CLI

This plan implements the approved specification in `PRD.md` and the selected
single-process design in `PROJECT_ARCHITECTURE.md`. It describes future work;
no product code is part of this blueprint. WIP remains one step at a time.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python 3.11 package and console-entry skeleton | Every test and feature needs stable imports and invocation | 1 hour |
| 2 | Canonical dataclasses and typed domain errors | Parser, aggregator, CLI, and renderers need one contract | 1 hour |
| 3 | Test fixtures and quality commands | Correctness must be executable before feature expansion | 1 hour |

There is deliberately no database schema, authentication system, HTTP server,
Docker setup, or CI/CD deployment runway. Those items contradict the local,
stateless, pip-installed CLI architecture.

## Step 1: Package, contracts, and fixtures

**Goal:** A clean Python 3.11 environment can install and invoke an empty CLI
shell, and the public data/exit contracts have executable test fixtures.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3 and 6; `PRD.md` FR-9.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, and the `nginx-insights` entry point.
2. Create `src/nginx_insights/__init__.py`, `src/nginx_insights/cli.py`, `src/nginx_insights/models.py`, and `src/nginx_insights/errors.py` with public types and error categories only.
3. Create `tests/fixtures/small_combined.log`, `tests/fixtures/malformed.log`, and `tests/conftest.py` with deterministic expected records.
4. Configure pytest, coverage, Ruff, and mypy in `pyproject.toml` without adding runtime dependencies beyond Click and Rich.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-insights --help`
- `.venv/bin/python -m pytest --collect-only -q`

**Commit:** `step-1: establish package and behavioral contracts`

## Step 2: Combined Log Format parser and input adapter

**Goal:** Valid records stream from file/stdin as frozen dataclasses; malformed
records are classified without retaining input.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3–4 and CLI Inputs; `PRD.md` US-6.

**Tasks:**

1. Create `src/nginx_insights/input.py` for a readable-file/stdin context boundary and line iteration.
2. Create `src/nginx_insights/parser.py` with one compiled Combined Log Format parser and timestamp/status validation.
3. Create `tests/test_parser.py` for IPv4/IPv6, escaped quotes, offsets, query strings, invalid UTF-8, truncated records, and boundary statuses.
4. Create `tests/test_input.py` to prove file/stdin byte equivalence and I/O error mapping.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py tests/test_input.py -q`
- `.venv/bin/ruff check src/nginx_insights/input.py src/nginx_insights/parser.py tests/test_parser.py tests/test_input.py`
- `.venv/bin/mypy src/nginx_insights/input.py src/nginx_insights/parser.py`

**Commit:** `step-2: stream and parse combined nginx logs`

## Step 3: Core aggregation and ranked metrics

**Goal:** One pass computes total/malformed counts, top client IPs, and top
4xx/5xx request targets with deterministic tie ordering.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 4; `PRD.md` US-1, US-2, FR-1–FR-4.

**Tasks:**

1. Create `src/nginx_insights/aggregate.py` with counters and a final immutable `AnalysisResult` snapshot.
2. Update `src/nginx_insights/models.py` with typed ranked entries and processing metadata.
3. Create `tests/test_aggregate_rankings.py` for top-10 truncation, ties, status boundaries, query strings, and malformed counts.
4. Add `tests/fixtures/ranking_combined.log` containing more than ten IPs and error targets.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate_rankings.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate_rankings.py --cov=nginx_insights.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-3: aggregate ranked traffic and error metrics`

## Step 4: Hourly percentages and guarded User-Agent cardinality

**Goal:** Results contain all 24 hourly percentage buckets and an exact unique
User-Agent share, with fail-closed cardinality exhaustion.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 4; `PRD.md` US-3 and US-4.

**Tasks:**

1. Extend `src/nginx_insights/aggregate.py` with 24 integer buckets and exact User-Agent-set tracking.
2. Extend `src/nginx_insights/errors.py` with a unique-cardinality exhaustion error mapped only to exit code 4.
3. Create `tests/test_aggregate_distribution.py` proving `100 × hourly_request_count / total_valid_requests`, offset semantics, two-decimal serialization values, and zero buckets.
4. Create `tests/test_user_agent_cardinality.py` proving exact comparison, exhaustion before insertion, no sensitive-value diagnostic, and exit-code intent.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate_distribution.py tests/test_user_agent_cardinality.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate_distribution.py tests/test_user_agent_cardinality.py --cov=nginx_insights.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: add distributions and cardinality guard`

## Step 5: Canonical result schema and terminal renderer

**Goal:** The default command renders the complete canonical result as readable
Rich tables, with color controlled by terminal capability and `--no-color`.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Outputs; `PRD.md` P0 presentation requirements.

**Tasks:**

1. Create `src/nginx_insights/render/__init__.py` and `src/nginx_insights/render/base.py` for stable ordering and percentage formatting.
2. Create `src/nginx_insights/render/terminal.py` with four labeled tables and processing metadata.
3. Create `tests/test_render_terminal.py` and `tests/golden/terminal_no_color.txt` for deterministic, escaped no-color output.
4. Wire the parser, aggregator, and terminal renderer in `src/nginx_insights/cli.py` without embedding domain logic in Click callbacks.

**Verification:**

- `.venv/bin/python -m pytest tests/test_render_terminal.py -q`
- `.venv/bin/nginx-insights --no-color tests/fixtures/small_combined.log`

**Commit:** `step-5: render canonical terminal report`

## Step 6: JSON, CSV, and complete CLI failure contract

**Goal:** Pipelines receive stable JSON/CSV on stdout and can distinguish every
specified outcome using the complete `0/1/2/3/4` contract.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` entire `## CLI Interface`; `PRD.md` US-5–US-7.

**Tasks:**

1. Create `src/nginx_insights/render/json_output.py` and `src/nginx_insights/render/csv_output.py` from the canonical result only.
2. Update `src/nginx_insights/cli.py` with mutually exclusive formats, strict mode, positive cardinality limit, stdin/path selection, stderr diagnostics, and broken-pipe handling.
3. Create `tests/test_render_json.py`, `tests/test_render_csv.py`, and golden structured fixtures.
4. Create `tests/test_cli.py` that directly exercises every exit code and verifies stdout/stderr separation and absence of ANSI in structured formats.

**Verification:**

- `.venv/bin/python -m pytest tests/test_render_json.py tests/test_render_csv.py tests/test_cli.py -q`
- `.venv/bin/nginx-insights --json tests/fixtures/small_combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'exit_code_0 or exit_code_1 or exit_code_2 or exit_code_3 or exit_code_4'`

**Commit:** `step-6: stabilize structured outputs and exit codes`

## Step 7: Cross-format integration, quality, and packaging

**Goal:** All formats are semantically identical, quality thresholds pass, and
an isolated Python 3.11 environment can install the wheel.

**Time:** ~1.5 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` release acceptance.

**Tasks:**

1. Create `tests/test_format_parity.py` to compare counts and percentages across terminal-model, JSON, and CSV render paths.
2. Create `tests/test_packaging.py` or a shell-neutral documented smoke procedure for built wheel installation.
3. Update `README.md` with actual help/output examples and the `gzip -cd` workaround.
4. Add `LICENSE` with an approved open-source license and ensure wheel metadata includes it.

**Verification:**

- `.venv/bin/ruff check . && .venv/bin/mypy src`
- `.venv/bin/python -m pytest --cov=nginx_insights --cov-branch --cov-fail-under=90`
- `.venv/bin/python -m build && python3.11 -m venv /tmp/nginx-insights-smoke && /tmp/nginx-insights-smoke/bin/pip install dist/*.whl && /tmp/nginx-insights-smoke/bin/nginx-insights --version`

**Commit:** `step-7: verify quality and wheel installation`

## Step 8: Reproducible 1 GB performance acceptance

**Goal:** A release candidate has reproducible evidence that a representative
1 GB log completes under 30 seconds without uncontrolled memory use.

**Time:** ~1.5 hours

**Context:** `STRATEGIC_PLAN.md` KPI and kill criteria; `PROJECT_ARCHITECTURE.md` section 7.

**Tasks:**

1. Create `benchmarks/generate_log.py` with a fixed seed and representative IP, URL, status, hour, and User-Agent diversity.
2. Create `benchmarks/run_benchmark.sh` that records OS, CPU, RAM, Python/package versions, fixture hash/bytes, elapsed time, and peak RSS.
3. Create `benchmarks/README.md` with the exact cold/warm-run method and output-redirection rules.
4. Record the candidate result in `benchmarks/results/reference.md`; optimize only measured hot paths and rerun correctness after every change.

**Verification:**

- `.venv/bin/python benchmarks/generate_log.py --bytes 1073741824 --seed 20260818 /tmp/nginx-insights-1gb.log`
- `benchmarks/run_benchmark.sh /tmp/nginx-insights-1gb.log`
- `.venv/bin/python -m pytest -q`

**Commit:** `step-8: record performance acceptance evidence`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable skeleton and trustworthy parser | ~4.5 hours |
| Saturday PM | 3–4 | Complete one-pass metric engine | ~4 hours |
| Sunday AM | 5–6 | Human and pipeline interfaces | ~4.5 hours |
| Sunday PM | 7–8 | Quality, packaging, and performance evidence | ~3 hours |

## Complete Exit-Code Contract for Every Step

| Code | Meaning |
|---:|---|
| `0` | Success/help/version/graceful broken pipe |
| `1` | Runtime or I/O/output failure |
| `2` | CLI usage or option-validation failure |
| `3` | Strict malformed input, empty input, or no valid request |
| `4` | Unique-cardinality exhaustion |

Every implementation step must preserve `0/1/2/3/4`; code 4 must never be
omitted or remapped. After each step, run its focused checks plus all previously
passing tests before changing WIP to the next step.

