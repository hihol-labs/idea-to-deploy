# Implementation Plan: Nginx Lens

This is a future eight-step plan, not a record of executed implementation. Scope and semantics come from [PRD](PRD.md) and [architecture](PROJECT_ARCHITECTURE.md); priorities and estimates come from [strategy](STRATEGIC_PLAN.md). Total estimate: 16 hours. Every step includes tests and a verification command to execute when code exists. Suggested commits are local future milestones, not authorization to commit or publish now.

## Architectural Runway
| Item | Why first | Effort |
|---|---|---|
| Package layout, pytest, console entry point | Makes each later increment executable | Step 1, 1 hour |
| Record/report dataclasses and fixture contract | Prevents parser/renderer drift | Step 1, 0.5 hour |
| Cardinality and exit-code contracts | Prevents silent approximation and ambiguous errors | Design fixed now; tests in steps 3 and 6 |

No database migration, auth, server infrastructure, Docker, or deployment runway is required. RICE order follows parser → metrics → exports → terminal → integrated delivery; package scaffolding is a dependency exception.

## Contract carried through all steps
Exit codes are **0/1/2/3/4**: 0 success (including empty input/help/version); 1 I/O, interruption, or internal processing failure; 2 usage error; 3 nonempty input with no valid records; 4 unique-cardinality exhaustion. Preserve code 4 in every integrated CLI and test it without approximating results. Hourly percentage is `100 × hourly_request_count / total_valid_requests`; the zero-denominator rule and remaining schemas are in architecture's CLI Interface section.

## Step 1: Executable package skeleton and data contracts
**Goal:** Establish a pip-installable Python 3.11 skeleton with typed models and test tooling.
**Time:** 1.5 hours.
**Context:** Architecture components, data model, and local delivery.
**Tasks:**
1. Create `pyproject.toml` with Click/Rich runtime dependencies, pytest/coverage/build development dependencies, and `nginx-lens = nginx_lens.cli:main` console entry point.
2. Create `src/nginx_lens/__init__.py`, `src/nginx_lens/cli.py`, `src/nginx_lens/models.py`, and `src/nginx_lens/errors.py`; define the report schema without product logic shortcuts.
3. Create `tests/test_package.py` for help/version/import behavior and `tests/fixtures/combined.log` with explicitly synthetic records. Add `LICENSE` with MIT terms after confirming ownership metadata.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_package.py`; `nginx-lens --help`.
**Suggested commit:** `step-1: scaffold local CLI and typed contracts`.

## Step 2: Bounded reader and combined-log parser
**Goal:** Convert supported physical lines into validated records with explicit malformed outcomes.
**Time:** 3 hours.
**Context:** Architecture input and parsing contract; PRD US-1.
**Tasks:**
1. Create `src/nginx_lens/reader.py` with bounded reads, oversized-line draining, final unterminated line support, and UTF-8 validation.
2. Create `src/nginx_lens/parser.py` for escaped combined fields, IPv4/IPv6 canonicalization, numeric status/bytes, timestamp validation, and request target extraction.
3. Create `tests/test_reader.py` and `tests/test_parser.py` covering escaped quotes, CRLF, invalid dates/offsets/status, missing fields, invalid UTF-8, and huge lines without whole-line allocation.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.
**Suggested commit:** `step-2: stream and validate combined logs`.

## Step 3: Exact metrics and cardinality guard
**Goal:** Compute all four metrics deterministically without retaining raw records.
**Time:** 3 hours.
**Context:** Architecture data model/resource contract; PRD US-2, US-3, US-4.
**Tasks:**
1. Create `src/nginx_lens/aggregate.py` with IP counts, error URL counts, 24 hourly counters, exact User-Agent set, and shared key budget.
2. Check all new keys before record mutation; raise the specific exhaustion exception for eventual code 4. Use bounded top-10 selection with deterministic ties.
3. Create `tests/test_aggregate.py` covering exact rankings, 399/400/499/500/599 boundaries, query-string distinction, two timezone offsets, missing agents, and cap-at-boundary/cap-overflow behavior.
4. Add a small early synthetic throughput probe to `benchmarks/benchmark.py`; treat its results as diagnostic rather than final acceptance.
**Verification:** `python -m pytest tests/test_aggregate.py`; `python benchmarks/benchmark.py --bytes 10000000 --runs 1`.
**Suggested commit:** `step-3: aggregate exact traffic metrics with resource guard`.

## Step 4: Stable JSON and normalized CSV
**Goal:** Expose deterministic pipeline reports with versioned schemas.
**Time:** 2 hours.
**Context:** Architecture CLI Interface output schemas; PRD US-5.
**Tasks:**
1. Create `src/nginx_lens/render.py` machine renderers using JSON and CSV standard-library encoders.
2. Create `tests/test_exports.py` for complete field names, ordering, quoting, Unicode, null/empty share values, two-decimal percentages, and ANSI-free output.
3. Add `tests/fixtures/expected.json` and `tests/fixtures/expected.csv` as golden outputs from hand-calculated synthetic input.
**Verification:** `python -m pytest tests/test_exports.py`.
**Suggested commit:** `step-4: render versioned JSON and CSV reports`.

## Step 5: Readable terminal report
**Goal:** Render default Rich tables with safe labels and predictable color rules.
**Time:** 1.5 hours.
**Context:** Architecture text output and NO_COLOR rules; PRD US-6.
**Tasks:**
1. Extend `src/nginx_lens/render.py` with top lists, hourly count/percentage columns, User-Agent diversity, and malformed totals.
2. Create `tests/test_terminal.py` for non-TTY output, explicit color modes, NO_COLOR, empty results, Rich markup strings, and terminal control-character escaping.
**Verification:** `python -m pytest tests/test_terminal.py`.
**Suggested commit:** `step-5: add safe colored terminal reports`.

## Step 6: CLI integration and complete failure behavior
**Goal:** Connect finite file/stdin input to one complete report and documented status behavior.
**Time:** 2 hours.
**Context:** Architecture CLI Interface, especially precedence and stdout/stderr separation.
**Tasks:**
1. Complete `src/nginx_lens/cli.py` for options, stdin ownership, file closing, error diagnostics, EOF handling, warning counts, and interruption mapping.
2. Create `tests/test_cli.py` for file/stdin equivalence, mutually exclusive exports, invalid positive limits, missing files, permission/read failure, broken pipe, interruption, mixed/all-malformed input, and cardinality overflow.
3. Assert all codes 0/1/2/3/4 and no report on pre-render failures; code 4 must not become generic code 1.
**Verification:** `python -m pytest tests/test_cli.py`; `nginx-lens --json tests/fixtures/combined.log`.
**Suggested commit:** `step-6: integrate CLI and five exit statuses`.

## Step 7: Acceptance and performance evidence
**Goal:** Prove semantic and resource behavior on reproducible synthetic workloads.
**Time:** 2 hours.
**Context:** PRD nonfunctional requirements and strategy KPIs.
**Tasks:**
1. Create `tests/test_acceptance.py` tracing all P0 stories, with independently calculated expected counts and percentages.
2. Complete `benchmarks/generate.py` and `benchmarks/benchmark.py`: deterministic input generation, chosen cardinality, byte size, subprocess timing, cache conditions, peak RSS, and three-run median.
3. Record actual results in `benchmarks/RESULTS.md`; separately test unique-cardinality exhaustion and repeated-key memory behavior. Never label synthetic records production data.
4. Optimize only demonstrated parser/aggregation hotspots; rerun correctness tests after changes.
**Verification:** `python -m pytest --cov=nginx_lens --cov-branch --cov-report=term-missing`; `python benchmarks/benchmark.py --bytes 1000000000 --runs 3`.
**Suggested commit:** `step-7: verify acceptance and record throughput evidence`.

## Step 8: Local distribution and handoff
**Goal:** Deliver a tested wheel and accurate usage documentation locally.
**Time:** 1 hour.
**Context:** Architecture delivery, strategy Definition of Done, [README](README.md).
**Tasks:**
1. Update `README.md`, `CLAUDE_CODE_GUIDE.md`, and `CLAUDE.md` from actual verified behavior and step status; include known benchmark limitations.
2. Build `dist/` artifacts, create a clean `.venv-smoke/`, and install the local wheel without assuming public package availability.
3. Run clean-environment help, empty-input, file/stdin, and export smoke cases; record package dependencies and future code-review evidence. Do not publish a package or push without explicit authorization.
**Verification:** `python -m pytest`; `python -m build`; `python -m venv .venv-smoke`; `.venv-smoke/bin/python -m pip install dist/*.whl`; `.venv-smoke/bin/nginx-lens --help`.
**Suggested commit:** `step-8: finalize local wheel and operator docs`.

## Delivery boundary
Eight steps fit one weekend; no multi-sprint cadence is introduced. If the target is missed, defer P1/P2, then reassess scope or performance assumptions with evidence. Do not remove a Must feature or change the approved stack silently. [Implementation prompts](CLAUDE_CODE_GUIDE.md) correspond one-to-one to these steps; [CLAUDE.md](CLAUDE.md) tracks their unstarted status.
