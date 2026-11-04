# Implementation Plan: Nginx Lens

Planning only: all eight steps below are unimplemented. Total estimate: 16 hours over one weekend. [PRD.md](PRD.md) is the acceptance source and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is the interface source. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) defines priorities; use [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for execution prompts and update [CLAUDE.md](CLAUDE.md) with evidence.

## Shared Contract

Every step preserves exits **0/1/2/3/4**: 0 clean completion; 1 operational/I/O/output failure or interruption; 2 usage error; 3 report with malformed lines skipped; 4 unique-cardinality exhaustion, no report. Fatal input errors also suppress reports; output errors may leave partial stdout. No remapping to Click defaults. Hourly percentage is `100 × hourly_request_count / total_valid_requests`; unique-UA percentage is `100 × distinct_nonmissing_user_agents / total_valid_requests`; zero denominators yield zero.

Commands below are future implementation checks, not runs claimed by this blueprint. Run from the repository root after setting up a Python 3.11 virtual environment and installing the package's future dev extra. No commit is performed by this planning session; suggested commit messages identify future checkpoints and require green checks.

## Architectural Runway

| Item | Why first | Effort |
|---|---|---|
| Console entry point and test harness | All feature checks need an executable | Included in step 1 |
| Dataclasses, schema and exit mapping | Avoid renderer/parser contract drift | Included in step 1 |
| Small hand-computed fixture and bounded reader contract | Establish correctness before optimization | Included in steps 1–2 |

No database, migrations, auth infrastructure, hosted CI configuration, or Docker runway is needed. Use local tests; adding CI or publishing is separate authorized work.

## Step 1: Package and Public Contracts

**Goal:** installable command, validated options, and reusable typed models.
**Time:** 1.5 hours.
**Context:** Architecture “CLI Interface” and “In-Memory Data Contracts”.
**Tasks:**
1. Create `pyproject.toml`, `src/nginx_lens/__init__.py`, and `src/nginx_lens/cli.py` for setuptools, Click entry point and version.
2. Create `src/nginx_lens/models.py` for validated request, aggregate, URL errors and immutable report dataclasses.
3. Create `tests/test_cli_contract.py` and `tests/fixtures/combined-small.log`; cover help, version, stdin default, conflicting flags, invalid cap, and the specified hand-computed fixture.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_cli_contract.py -q`; `nginx-lens --help`.
**Suggested commit:** `step-1: establish package and CLI contracts`.

## Step 2: Bounded Input and Combined Parser

**Goal:** yield validated requests incrementally with exact malformed accounting.
**Time:** 3 hours.
**Context:** Architecture “Input Format and Parsing”; PRD US-1.
**Tasks:**
1. Create `src/nginx_lens/input.py` with bounded binary reads, oversized-line draining, file ownership and stdin support.
2. Create `src/nginx_lens/parser.py` with quoted escape parsing, address canonicalization, calendar/offset validation, status validation and query stripping.
3. Create `tests/test_input.py` and `tests/test_parser.py` covering IPv6, offsets crossing day boundaries, leap dates, invalid encoding, escaped quote/backslash/hex, unsupported request-targets, CRLF, missing LF, and oversized/blank records.
**Verification:** `python -m pytest tests/test_input.py tests/test_parser.py -q`.
**Suggested commit:** `step-2: stream and validate combined log records`.

## Step 3: Exact Aggregation and Key Budget

**Goal:** correct four-metric report with deterministic top ten and explicit exhaustion.
**Time:** 2.5 hours.
**Context:** Architecture “Cardinality and Performance”; PRD US-2.
**Tasks:**
1. Create `src/nginx_lens/aggregate.py` with all-valid IP counts, error-only URL counters, UTC hour counts and exact nonmissing-UA set.
2. Preflight all new keys before mutating each valid request; enforce sum-of-namespaces cap and exit 4 propagation.
3. Create `tests/test_aggregate.py` for hand-calculated percentages, no-valid input, top-ten cutoff/ties, shuffled input equivalence, exact cap, repeat-at-cap and three-new-keys overflow.
**Verification:** `python -m pytest tests/test_aggregate.py -q`.
**Suggested commit:** `step-3: add exact capped streaming aggregates`.

## Step 4: Terminal Report

**Goal:** readable default output respecting TTY and color controls.
**Time:** 1.5 hours.
**Context:** Architecture outputs; PRD US-3.
**Tasks:**
1. Create `src/nginx_lens/render.py` terminal renderer consuming only Report.
2. Connect it in `src/nginx_lens/cli.py`; keep warnings on stderr and sanitize controls/literal Rich text.
3. Create `tests/test_terminal.py` for tables, zero rows, TTY/non-TTY, NO_COLOR and hostile field text.
**Verification:** `python -m pytest tests/test_terminal.py -q`.
**Suggested commit:** `step-4: render safe terminal summaries`.

## Step 5: JSON Export

**Goal:** stable schema-versioned machine output.
**Time:** 1 hour.
**Context:** Architecture JSON schema; PRD US-4.
**Tasks:**
1. Extend `src/nginx_lens/render.py` and `src/nginx_lens/cli.py` for one UTF-8 JSON object without Rich formatting.
2. Create `tests/test_json.py` checking all required keys, types, 24 hours, rounding, deterministic rankings and the hand-computed result.
**Verification:** `python -m pytest tests/test_json.py -q`.
**Suggested commit:** `step-5: export schema-versioned JSON`.

## Step 6: CSV Export

**Goal:** one interoperable long-form table covering every metric.
**Time:** 1 hour.
**Context:** Architecture CSV schema; PRD US-5.
**Tasks:**
1. Extend `src/nginx_lens/render.py` and CLI selection for csv.writer output with fixed header/row order.
2. Create `tests/test_csv.py` for six-column round trips, commas/quotes/controls, empty cells, and count/percentage equivalence with JSON.
**Verification:** `python -m pytest tests/test_csv.py -q`.
**Suggested commit:** `step-6: export stable long-form CSV`.

## Step 7: Failure Matrix and End-to-End Verification

**Goal:** all complete 0/1/2/3/4 outcomes behave consistently across formats.
**Time:** 2 hours.
**Context:** Architecture exit precedence; PRD US-6.
**Tasks:**
1. Finish exception mapping in `src/nginx_lens/cli.py` and input/output boundaries; explicitly override default broken-pipe success behavior.
2. Create `tests/test_integration.py` with subprocess cases for clean/empty input, missing file, conflicting formats, mixed/all-malformed lines, cardinality overflow, interrupt, read/write failures and closed output pipes.
3. Check no-report guarantees before rendering and authoritative nonzero status after partial write failure; verify no raw lines leak into stderr.
**Verification:** `python -m pytest tests/test_integration.py -q`; `python -m pytest --cov=nginx_lens --cov-branch --cov-report=term-missing` (inspect parser/aggregate coverage against the 90% target).
**Suggested commit:** `step-7: enforce complete exit and stream contracts`.

## Step 8: Benchmark and Local Delivery Rehearsal

**Goal:** measured performance and a working local wheel, or an explicit failed release gate.
**Time:** 3.5 hours.
**Context:** Architecture benchmark protocol and packaging; strategic Definition of Done.
**Tasks:**
1. Create `benchmarks/generate.py`, `benchmarks/run.py`, and `benchmarks/RESULTS.md`. Generate the exact decimal-GB bounded fixture, record hardware/versions, run three timed file-to-JSON trials and a separate key-exhaustion scenario, measuring peak RSS.
2. Profile only if needed; rerun affected correctness tests after every optimization. Record misses without changing acceptance targets.
3. Update `README.md` and package metadata; add `LICENSE` with MIT terms and confirmed author attribution. Build and install a wheel in a fresh venv. Run help and fixture analyses there; no upload or deployment.
4. Request actual code/dependency review before release; external architecture review is a distinct harness action, not proof of implementation correctness.
**Verification:** `python -m pytest -q`; `python benchmarks/generate.py --bytes 1000000000 --output /tmp/nginx-lens-bench.log`; `python benchmarks/run.py --input /tmp/nginx-lens-bench.log --runs 3 --format json`; `python -m build`; `python -m venv /tmp/nginx-lens-wheel-check`; install the newly built wheel there with that venv's pip and execute `nginx-lens --json tests/fixtures/combined-small.log` using the venv executable. Generator/runner flags are contracts to implement in this step.
**Suggested commit:** `step-8: record benchmark and local wheel verification`.

## Delivery Boundaries

Saturday covers steps 1–6 (10.5 hours); Sunday covers steps 7–8 (5.5 hours). There are eight steps, so no multi-sprint PI cadence is needed. Should/Could items remain outside the weekend. Reconcile status only from actual checks, save context with `/session-save`, and never mark performance or review complete from this plan alone.
