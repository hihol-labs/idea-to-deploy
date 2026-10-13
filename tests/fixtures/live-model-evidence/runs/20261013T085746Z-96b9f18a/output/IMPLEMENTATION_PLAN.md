# Implementation Plan: Nginx Lens

Planning only. All paths and commands below describe future work; none of the product tests has run. Source contracts: [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). Execute one step at a time with evidence before updating status. Total estimate: 16 hours across eight steps.

## Shared Contract

Preserve exit codes **0/1/2/3/4**: 0 success, 1 operational/internal failure, 2 invalid usage, 3 completed report with malformed lines skipped, 4 unique-cardinality exhaustion. Fatal read/budget errors suppress reports; output failures can leave partial bytes and return 1. Hourly percentages use `100 × hourly_request_count / total_valid_requests`. Use the architecture's exact UA definition, UTC buckets, JSON/CSV schema, and shared budget.

## Architectural Runway

| Item | Why first | Effort included below |
|---|---|---|
| Package/console entry point and CLI skeleton | Enables end-to-end checks | Step 1, 1 hour |
| Typed record/report and synthetic fixture conventions | Keeps all renderers consistent | Step 1, 0.5 hour |
| Local pytest setup and documented contracts | Makes behavior verifiable before features | Step 1, 0.5 hour |

No database, authentication, Docker, or hosted infrastructure runway is needed. RICE drives parser, metrics, terminal, and exports in that order; packaging starts early as a dependency and finishes at release.

## Step 1: Package and CLI Skeleton

**Goal:** An installable command validates options and exposes stable help.
**Time:** 2 hours.
**Context:** Architecture, CLI Interface and Components.
**Tasks:**
1. Create `pyproject.toml`, `src/nginx_lens/__init__.py`, and `src/nginx_lens/cli.py` with the console entry point and Click options.
2. Create `src/nginx_lens/models.py`, `tests/conftest.py`, and `tests/test_cli.py`; define typed records/report and usage tests.
3. Add a proposed MIT `LICENSE` and development extras for pytest, coverage, and build tooling; record resolved versions.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_cli.py`; `nginx-lens --help`.
**Commit:** `step-1: establish package and CLI contract`.

## Step 2: Bounded Streaming Parser

**Goal:** File/stdin records follow the documented combined grammar without whole-file reads.
**Time:** 2 hours.
**Context:** Architecture, Input Grammar and Validation.
**Tasks:**
1. Create `src/nginx_lens/reader.py` and `src/nginx_lens/parser.py` for bounded binary lines, UTF-8, quoted escapes, IP normalization, and UTC conversion.
2. Create `tests/test_reader.py`, `tests/test_parser.py`, and synthetic `tests/fixtures/combined.log` plus invalid-format fixtures.
3. Test oversize draining, missing newline, invalid dates/offsets, IPv6, malformed escapes, and unsupported requests.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.
**Commit:** `step-2: parse combined logs incrementally`.

## Step 3: Exact Metrics and Resource Guard

**Goal:** All four metrics are correct within a declared cardinality budget.
**Time:** 3 hours.
**Context:** Architecture, In-Memory Data Model and Resource and Failure Model.
**Tasks:**
1. Create `src/nginx_lens/aggregate.py`; update `models.py` for error rows and final reports.
2. Track namespaced key additions before atomic per-record updates; include UA-only growth and error-path-only growth in budget tests.
3. Create `tests/test_aggregate.py` for ties, UTC buckets across dates, query stripping, missing UAs, zero denominators, fewer than ten values, exact cap and overflow.
**Verification:** `python -m pytest tests/test_aggregate.py`.
**Commit:** `step-3: implement exact metrics and cardinality limit`.

## Step 4: Terminal Report

**Goal:** A local user can inspect the complete report safely.
**Time:** 2 hours.
**Context:** Architecture, CLI Outputs and Environment.
**Tasks:**
1. Create `src/nginx_lens/render.py` terminal rendering; wire reader/parser/accumulator into `cli.py`.
2. Create `tests/test_terminal.py` for every section, rounding, color controls, markup literals, and control-character escaping.
3. Emit aggregate malformed-line diagnostics without raw log content.
**Verification:** `python -m pytest tests/test_terminal.py`; `nginx-lens --no-color tests/fixtures/combined.log`.
**Commit:** `step-4: add readable terminal summaries`.

## Step 5: JSON and CSV Exports

**Goal:** Both machine formats serialize the same report model deterministically.
**Time:** 3 hours.
**Context:** Architecture, CLI Outputs; PRD export story.
**Tasks:**
1. Extend `src/nginx_lens/render.py` with standard-library json/csv writers and schema_version 1.
2. Create `tests/test_exports.py` for exact fields/header, row order, precision, proper escaping, empty input, and no ANSI/log contamination.
3. Compare round-tripped export data against independent expected values and terminal source report data.
**Verification:** `python -m pytest tests/test_exports.py`; `nginx-lens --json tests/fixtures/combined.log`; `nginx-lens --csv tests/fixtures/combined.log`.
**Commit:** `step-5: add deterministic pipeline exports`.

## Step 6: Failure and Integration Verification

**Goal:** Shell callers can trust every exit status and failure boundary.
**Time:** 1.5 hours.
**Context:** Architecture, complete exit-code contract 0/1/2/3/4.
**Tasks:**
1. Finalize exception mapping in `src/nginx_lens/cli.py` including handled interrupt, broken pipe, and output failure.
2. Create `tests/test_integration.py` for file/stdin parity, all-invalid and mixed input, bad options, missing file, and unique-cardinality exhaustion.
3. Verify stdout is empty on input/cardinality fatal errors and stderr never exposes raw lines. Use a controlled failing stream for output errors.
**Verification:** `python -m pytest tests/test_integration.py`; `python -m pytest --cov=nginx_lens --cov-branch --cov-report=term-missing` (inspect parser/aggregate branch coverage against 90% gate).
**Commit:** `step-6: verify process and failure semantics`.

## Step 7: Performance Evidence

**Goal:** Measure the throughput claim and explain resource scaling.
**Time:** 1.5 hours.
**Context:** Architecture, Performance and Verification.
**Tasks:**
1. Create `benchmarks/generate.py` with deterministic seed, declared synthetic combined logs, exact requested byte size, and documented cardinalities below the default budget.
2. Create `benchmarks/run.py` to launch the CLI, validate status/schema, record wall times and peak RSS with platform units, and save `benchmarks/RESULTS.md` with laptop metadata.
3. Test a separate overflow fixture; profile any throughput failure and record it without changing semantics or calling a failed run a success.
**Verification:** `python benchmarks/generate.py --bytes 1000000000 --seed 42 --output /tmp/nginx-lens-benchmark.log`; `python benchmarks/run.py --input /tmp/nginx-lens-benchmark.log --runs 3 --format json`.
**Commit:** `step-7: record reproducible performance evidence`.

## Step 8: Local Release Candidate and Handoff

**Goal:** A clean environment can install the wheel and use the documented interface.
**Time:** 1 hour.
**Context:** Strategic Definition of Done and PRD release gates.
**Tasks:**
1. Finalize `pyproject.toml`, `README.md`, `CLAUDE.md`, and `CLAUDE_CODE_GUIDE.md` to match verified behavior.
2. Build wheel/sdist and verify installation in an isolated Python 3.11 environment; the installed version for the first candidate is 0.1.0.
3. Record verification and external-review status in `ITD_REPORT.md` and canonical `.itd-memory/STATE.json`; do not publish automatically.
**Verification:** `python -m pytest`; `python -m build`; `python -m venv /tmp/nginx-lens-release-check`; `/tmp/nginx-lens-release-check/bin/python -m pip install dist/nginx_lens-0.1.0-py3-none-any.whl`; `/tmp/nginx-lens-release-check/bin/nginx-lens --json tests/fixtures/combined.log`.
**Commit:** `step-8: prepare verified local release candidate`.

## Handoff

No product implementation is present yet. The next step is external adversarial architecture review, then Step 1 implementation once that separate review is available. Use the step prompts in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md). Keep P1/P2 deferred; report any unmet gate explicitly. Eight steps fit a single weekend, so a multi-sprint cadence is not applicable.
