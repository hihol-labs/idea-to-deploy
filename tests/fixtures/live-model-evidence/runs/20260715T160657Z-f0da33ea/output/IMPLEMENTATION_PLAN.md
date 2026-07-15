# Implementation Plan: Nginx Stream Analytics CLI

## 1. Delivery Rules

This plan implements the P0 scope in [PRD.md](PRD.md) using the selected architecture in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). Steps are dependency-ordered, preserve one active work item, and fit a one-weekend delivery. No database, API, service, cloud, Docker, or Kubernetes work is included.

Every step ends with its stated verification before the next begins. Commands assume a Python 3.11 virtual environment and editable development install.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Packaging and console entry point | Every integration check needs an installable command | 1.0 h |
| 2 | Typed runtime/output contracts | Parser, aggregation, and all renderers need one stable model | 1.0 h |
| 3 | Deterministic fixtures and quality configuration | Enables fail-closed behavior checks before feature growth | 1.0 h |

Database schema, authentication, CI deployment, and Docker setup are not runway items because the architecture explicitly excludes them.

## Step 1: Package and CLI Skeleton

**Goal:** A Python 3.11 package installs through pip and exposes `nginx-stats` with help and version output.

**Time:** ~1 hour

**Context:** Architecture sections 4, 8, and 10.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11`, Click, Rich, build metadata, and the `nginx-stats` console script.
2. Create `src/nginx_stream_analytics/__init__.py` with the package version.
3. Create `src/nginx_stream_analytics/cli.py` with the Click argument/options and mutual exclusion for `--json`/`--csv`.
4. Create `tests/test_cli.py` covering help, version, invalid option combinations, and missing files.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-stats --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Domain and Output Contracts

**Goal:** Typed dataclasses express parsed records, mutable aggregation state, ranked items, and immutable reports.

**Time:** ~1 hour

**Context:** Architecture sections 5 and 9; PRD data definitions.

**Tasks:**

1. Create `src/nginx_stream_analytics/models.py` with `AccessRecord`, `AggregateState`, `RankedItem`, and `Report`.
2. Create `tests/test_models.py` for 24-hour state initialization, immutability, unique-key accounting, and zero-request share behavior.
3. Add shared deterministic builders to `tests/conftest.py`.

**Verification:**

- `pytest -q tests/test_models.py`
- `mypy src/nginx_stream_analytics`

**Commit:** `step-2: define typed report contracts`

## Step 3: Combined-Log Streaming Parser

**Goal:** Valid combined-format lines become records one at a time; malformed input follows lenient and strict policies.

**Time:** ~2.5 hours

**Context:** Architecture section 6; PRD stories US-1 and US-7.

**Tasks:**

1. Create `src/nginx_stream_analytics/parser.py` with allocation-conscious parsing, direct hour extraction, request/escape handling, and status/timestamp validation; the production path directly updates aggregates without per-line dataclass/datetime allocation.
2. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with spaces, nginx escapes, IPv4/IPv6, `"-"` requests, invalid UTF-8, empty fields, bad statuses, and long values.
3. Create `tests/test_parser.py` for valid fields, malformed reasons, strict UTF-8 behavior, escape grammar, and non-retention iteration.
4. Wire file/stdin iteration and `--strict` behavior in `src/nginx_stream_analytics/cli.py`.

**Verification:**

- `pytest -q tests/test_parser.py tests/test_cli.py`
- `ruff check src tests`

**Commit:** `step-3: parse combined logs as a stream`

## Step 4: Exact Aggregation and Rankings

**Goal:** A single pass computes all required counts and deterministic top-ten lists.

**Time:** ~2 hours

**Context:** Architecture sections 5 and 7; PRD stories US-2 through US-5.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` to update IP, error-target, hourly, and User-Agent aggregates.
2. Implement ranking by count descending and key ascending with a hard maximum of ten items.
3. Compute unique User-Agent share from distinct non-empty values over parsed requests, returning `0.0` for empty input.
4. Enforce `--max-unique` across the three exact maps before each first insertion, failing with exit 1 without returning partial results.
5. Create `tests/test_aggregate.py` for 4xx/5xx inclusion, 2xx/3xx exclusion, ties, query strings, all hours, empty input, duplicate/empty agents, and guard boundaries.

**Verification:**

- `pytest -q tests/test_aggregate.py --cov=nginx_stream_analytics.aggregate --cov-branch --cov-fail-under=90`
- `mypy src/nginx_stream_analytics`

**Commit:** `step-4: compute exact streaming metrics`

## Step 5: JSON Renderer

**Goal:** `--json` emits the versioned schema with no non-JSON stdout noise.

**Time:** ~1.25 hours

**Context:** Architecture section 9; PRD story US-6.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/__init__.py` with renderer selection.
2. Create `src/nginx_stream_analytics/renderers/json.py` with schema version `1.0`, 24 ordered hours, numeric counts, and one trailing newline.
3. Add `tests/fixtures/expected.json` and JSON golden/integration cases to `tests/test_renderers.py` and `tests/test_cli.py`.

**Verification:**

- `nginx-stats --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `pytest -q tests/test_renderers.py tests/test_cli.py -k json`

**Commit:** `step-5: add stable JSON output`

## Step 6: CSV Renderer

**Goal:** `--csv` emits normalized RFC 4180 rows for every report section.

**Time:** ~1.25 hours

**Context:** Architecture section 9; PRD story US-6.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/csv.py` using Python’s `csv` writer and the six-column schema.
2. Add `tests/fixtures/expected.csv` with summary, rankings, 24 hour rows, and User-Agent rows.
3. Test commas, quotes, newlines, UTF-8 values, deterministic row order, and clean stdout.

**Verification:**

- `nginx-stats --csv tests/fixtures/combined.log > /tmp/nginx-stats.csv`
- `pytest -q tests/test_renderers.py tests/test_cli.py -k csv`

**Commit:** `step-6: add normalized CSV output`

## Step 7: Rich Terminal Report and Diagnostics

**Goal:** Default output is readable colored text, while redirected output and pipeline modes remain clean.

**Time:** ~1.5 hours

**Context:** Architecture sections 8, 9, and 12; PRD stories US-1 and US-7.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/terminal.py` with four report sections and parsed/skipped summary.
2. Escape or disable Rich markup for all log-derived strings.
3. Implement TTY/`NO_COLOR`/`--no-color` behavior and stderr diagnostics in `src/nginx_stream_analytics/cli.py`.
4. Extend `tests/test_renderers.py` and `tests/test_cli.py` for color, no-color, malicious markup, ANSI/C0/C1 controls, EPIPE exit 0, other write failures exit 1, diagnostics, and exit codes.

**Verification:**

- `NO_COLOR=1 nginx-stats tests/fixtures/combined.log`
- `pytest -q tests/test_renderers.py tests/test_cli.py`

**Commit:** `step-7: render safe terminal reports`

## Step 8: Performance Gate and Hardening

**Goal:** The exact CLI proves the 1 GB under 30 seconds requirement on recorded reference hardware without exceeding the memory kill criterion.

**Time:** ~3 hours

**Context:** Architecture sections 7, 11, and 12; Strategic Plan KPIs and kill criteria.

**Tasks:**

1. Create `benchmarks/generate_log.py` for seeded valid, mixed-error, high-cardinality, and 250,000-key guard-boundary combined logs.
2. Create `benchmarks/benchmark.md` with reference hardware, fixture checksum/profile, cold/warm commands, wall time, and peak RSS.
3. Profile parser/aggregation only if the first measured run misses the target; record any optimization and correctness evidence.
4. Add adversarial tests for long fields, invalid bytes, malformed lines, and empty input.

**Verification:**

- `python3.11 benchmarks/generate_log.py --size-gib 1 --seed 2026 --output /tmp/nginx-1g.log`
- `/usr/bin/time -v nginx-stats --json /tmp/nginx-1g.log >/dev/null`
- `pytest -q --cov=nginx_stream_analytics --cov-branch --cov-fail-under=90`

**Commit:** `step-8: prove performance and harden input handling`

## Step 9: Release Documentation and Package Validation

**Goal:** A clean checkout can install, verify, and package the CLI using documented commands.

**Time:** ~1.5 hours

**Context:** Architecture section 10; [README.md](README.md); Definition of Done.

**Tasks:**

1. Update `README.md` with actual installation, examples, schemas, constraints, performance evidence, and troubleshooting.
2. Add `LICENSE` using an approved open-source license and create `CHANGELOG.md` for version `0.1.0`.
3. Add `.github/workflows/ci.yml` for Python 3.11 lint, type, test, and package-build checks; it publishes nothing.
4. Build source/wheel artifacts and test installation in a fresh local virtual environment.

**Verification:**

- `ruff check src tests benchmarks && mypy src/nginx_stream_analytics && pytest -q`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stats-release && /tmp/nginx-stats-release/bin/pip install dist/*.whl && /tmp/nginx-stats-release/bin/nginx-stats --version`

**Commit:** `step-9: validate release package and docs`

## Sprint Boundaries

For a one-weekend project, “sprint” means a focused half-day block.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable CLI, contracts, reliable parser | ~4.5 h |
| Saturday PM | 4–6 | Exact metrics plus pipeline renderers | ~4.5 h |
| Sunday AM | 7–8 | Terminal UX, safety, and performance proof | ~4.5 h |
| Sunday PM | 9 | Release-quality handoff | ~1.5 h |

## Release Evidence Checklist

- [ ] All step verification commands have recorded pass output.
- [ ] JSON/CSV golden schemas match [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).
- [ ] P0 acceptance criteria in [PRD.md](PRD.md) are passed.
- [ ] The 1 GB benchmark evidence names hardware and reports wall time and peak RSS.
- [ ] No P1/P2 work displaced an incomplete P0 item.
- [ ] Package installation succeeds in a fresh Python 3.11 environment.
