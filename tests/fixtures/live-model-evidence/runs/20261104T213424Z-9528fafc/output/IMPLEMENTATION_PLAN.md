# Implementation Plan: nginx-scan

This is a proposed eight-step weekend plan, approximately 16 hours; every step is pending. No commands below have been run as product verification. Read [PRD.md](PRD.md) and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) first. Keep scope at P0 from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).

## Architectural Runway

| Item | Why first | Effort (included below) |
|---|---|---|
| Local packaging and test entry point | Enable installed-command and fixture tests | 1 hour |
| Dataclasses, grammar and output schema | Keep parser, aggregation and renderers aligned | 1 hour |
| Cardinality and exit-code contract | Prevent incorrect partial-success behavior | 1 hour |

No database, auth, Docker or hosted CI setup is required. Run tests locally; introducing external CI would need separate scope and approval. Follow dependency order while prioritizing high-RICE functionality; packaging scaffolding is a necessary exception to score ordering.

## Exit-code contract

All steps preserve the complete 0/1/2/3/4 contract: 0 successful complete report/help/version; 1 internal failure or interruption; 2 usage error; 3 input/output failure, including broken pipe; 4 unique-cardinality exhaustion or allocation failure. Malformed lines are counted/skipped with exit 0. Fatal errors before rendering produce no report; a stdout write failure may leave partial bytes, which callers must discard.

## Step 1: Package and model foundation

**Goal:** An installable skeleton with explicit report models and a runnable test harness.
**Time:** 1.5 hours.
**Context:** Architecture components, data model and packaging.
**Tasks:**
1. Create `pyproject.toml`, `src/nginx_scan/__init__.py`, `src/nginx_scan/cli.py` and `src/nginx_scan/models.py`; define console entry and development dependencies.
2. Create `tests/test_package.py` and `tests/test_models.py`; establish console help/version and schema defaults.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_package.py tests/test_models.py`; `nginx-scan --help`.
**Proposed commit:** `step-1: package and report model foundation`.

## Step 2: Streaming combined-log parser

**Goal:** File/stdin records validate without retaining raw input.
**Time:** 2.5 hours.
**Context:** Input grammar, size limits and PRD story 1.
**Tasks:**
1. Create `src/nginx_scan/reader.py` and `src/nginx_scan/parser.py` with bounded reads, line draining, escaped fields, IP validation and UTC normalization.
2. Create `tests/fixtures/combined.log`, `tests/test_reader.py`, `tests/test_parser.py`; cover invalid UTF-8, oversized/truncated lines, leap dates, offsets, IPv6, missing final newline and malformed requests.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.
**Proposed commit:** `step-2: stream and validate combined logs`.

## Step 3: Exact metrics and resource limits

**Goal:** Build complete reports with deterministic top-10 and exact counts.
**Time:** 2.5 hours.
**Context:** Metric semantics and PRD stories 2–4.
**Tasks:**
1. Create `src/nginx_scan/aggregate.py`; track three exact key collections, preflight new-key budget, UTC buckets and integer counts; select top-10 without sorting the entire map.
2. Create `tests/test_aggregate.py`; test the worked PRD fixture, ties, >10 keys, repeated keys, per-structure cap accounting, exact boundary and cap+1, unknown agents, zero input and all-malformed input.
3. Represent cardinality failure explicitly and preserve the 0/1/2/3/4 contract when integrating later.
**Verification:** `python -m pytest tests/test_aggregate.py`.
**Proposed commit:** `step-3: exact reports with cardinality guards`.

## Step 4: Terminal reporting

**Goal:** Human-readable default tables display all metrics safely.
**Time:** 1.5 hours.
**Context:** CLI output and terminal security.
**Tasks:**
1. Create `src/nginx_scan/render.py` terminal adapter; literal text, control escaping, TTY-aware color, NO_COLOR and --no-color.
2. Create `tests/test_terminal.py`; assert table contents and color behavior with injected TTY states and malicious markup/control input.
**Verification:** `python -m pytest tests/test_terminal.py`.
**Proposed commit:** `step-4: safe terminal summaries`.

## Step 5: JSON and CSV pipeline formats

**Goal:** Machine outputs carry the same report with stable schemas.
**Time:** 1.5 hours.
**Context:** CLI schema and PRD pipeline story.
**Tasks:**
1. Extend `src/nginx_scan/render.py` with schema-versioned JSON and the unified section/key/count/percentage CSV document.
2. Create `tests/test_exports.py`; parse output back, compare counts and percentages, assert six-decimal CSV fields, no ANSI, quote escaping and deterministic rank order.
**Verification:** `python -m pytest tests/test_exports.py`.
**Proposed commit:** `step-5: deterministic JSON and CSV exports`.

## Step 6: CLI integration and failure paths

**Goal:** Connect all inputs/renderers and deliver the complete error contract.
**Time:** 2 hours.
**Context:** Exact `CLI Interface` contract and all P0 stories.
**Tasks:**
1. Complete `src/nginx_scan/cli.py`; validate flags/cap before opening input, render only after EOF, send bounded diagnostics to stderr and map exceptions.
2. Create `tests/test_cli.py` and `tests/test_failures.py`; cover file/stdin equivalence and real observable exits 0/1/2/3/4, cap exhaustion, injected MemoryError, read failure, write failure, broken pipe, interruption and absence of reports on pre-render failure.
**Verification:** `python -m pytest tests/test_cli.py tests/test_failures.py`; `python -m pytest`.
**Proposed commit:** `step-6: integrated CLI and full exit contract`.

## Step 7: Measure and optimize

**Goal:** Establish evidence for the throughput target without changing semantics.
**Time:** 2.5 hours.
**Context:** Architecture performance protocol and PRD kill criteria.
**Tasks:**
1. Create `benchmarks/generate_log.py` to produce an explicitly synthetic combined-format file of exactly 1,000,000,000 bytes, using variable-length valid lines and controlled distinct counts below the cap. Verify byte size before timing.
2. Create `benchmarks/run.py` to time subprocess invocation through completed output and capture hardware/software, cache conditions, cardinalities and peak RSS; record results in `benchmarks/RESULTS.md`.
3. Run three trials; profile measured hot paths if needed. Never claim a measurement from fixture generation or unit tests.
**Verification:** `python benchmarks/generate_log.py --bytes 1000000000 --output /tmp/nginx-scan-bench.log`; `python benchmarks/run.py --input /tmp/nginx-scan-bench.log --trials 3 --max-seconds 30`; `python -m pytest`.
**Proposed commit:** `step-7: measured streaming performance`.

## Step 8: Local release readiness

**Goal:** A tested wheel and accurate usage docs, without publishing.
**Time:** 2 hours.
**Context:** Strategy Definition of Done and PRD release gate.
**Tasks:**
1. Create `tests/test_wheel.py` that builds a wheel into a temporary directory, installs it in an isolated venv and exercises its command on a known fixture outside the checkout import path.
2. Update `README.md`, `CLAUDE_CODE_GUIDE.md` and `CLAUDE.md` to reflect measured results and actual step status; record test and review evidence in session memory.
3. Resolve external review findings when available; obtain separate permission for commit/push/public publishing. This blueprint does not provide that authorization.
**Verification:** `python -m pytest --cov=nginx_scan --cov-report=term-missing`; `python -m ruff check src tests benchmarks`; `python -m pytest tests/test_wheel.py`; `python -m build`.
**Proposed commit:** `step-8: local wheel and delivery documentation`.

## Handoff

Eight steps need no multiweek sprint cadence. Saturday targets steps 1–5; Sunday targets steps 6–8. Checkpoint after each significant block with session-save. Prompts are in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md); current status is in [CLAUDE.md](CLAUDE.md). All verification commands here are future implementation checks, not blueprint-session results. Do not commit until the relevant suite is green and human authorization exists.
