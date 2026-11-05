# Implementation Plan: Nginx Lens

Eight dependency-ordered steps, estimated 16 focused hours across one weekend. All work below is planned, not implemented. RICE order from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) applies after prerequisite setup. [PRD.md](PRD.md) defines acceptance; [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) defines exact interfaces. [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) supplies matching prompts; [CLAUDE.md](CLAUDE.md) tracks status.

## Architectural Runway
| Item | Why first | Effort |
|---|---|---|
| pyproject, src package, test layout | Installable command and reproducible test invocation | Step 1, 1 h |
| Typed record and output contract | Parser, accumulator, and renderers agree on semantics | Step 1, 1 h |
| Small checked-in combined fixtures | Hand-computed oracle before implementation | Steps 1–2, included |

No database, authentication, Docker, service setup, or deployment runway applies. Use local automated checks; any external CI/publishing work requires separate authorization.

## Shared Verification Contract
All steps preserve exit codes **0/1/2/3/4**: 0 complete success/help/version; 1 I/O or runtime failure; 2 CLI usage; 3 no valid requests; 4 unique-cardinality exhaustion (including MemoryError). Failure reports use stderr and no aggregate on stdout. The command interfaces and metric formulas are in architecture's `CLI Interface` and metric sections. Hourly percentage is `100 × hourly_request_count / total_valid_requests`.

The file and test names below are planned artifacts. Verification commands become runnable as each step creates its tests. Do not label a step complete until its command actually passes. Commit messages are suggested local checkpoints; no commit or publishing occurs in this blueprint session.

## Step 1: Package and Contract Fixtures
**Goal:** A locally installed entry point and typed model boundaries exist.

**Time:** 2 h.

**Context:** Architecture components, models, CLI contract.

**Tasks:**
1. Create `pyproject.toml` with Python >=3.11, Click/Rich, pytest/pytest-cov/build dev extras, and `nginx-lens = nginx_lens.cli:main`.
2. Create `src/nginx_lens/__init__.py`, `cli.py`, and `models.py`; install help/version skeleton only.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/expected.json` with hand-computed valid/invalid, error, hourly, and UA examples; create `tests/test_package.py` and `tests/test_models.py`.

**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_package.py tests/test_models.py`; `nginx-lens --help`.

**Commit:** `step-1: establish package and report contracts`.

## Step 2: Bounded Input and Combined Parser
**Goal:** Iterate valid records and count malformed input without loading the file.

**Time:** 3 h.

**Context:** Architecture input/parsing and data model.

**Tasks:**
1. Create `src/nginx_lens/reader.py` for stdin/files, strict UTF-8, bounded reads and oversized-line draining; do not close caller-owned stdin.
2. Create `src/nginx_lens/parser.py` for timestamp/status/request validation, escaped fields, IPv6, missing UA, and query/fragment stripping.
3. Create `tests/test_reader.py`, `tests/test_parser.py`, and `tests/fixtures/malformed.log` for CRLF, no trailing newline, bad dates/status/escapes, long lines, Unicode, custom-format rejection, and read failure injection.

**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.

**Commit:** `step-2: stream and validate combined access records`.

## Step 3: Top IP and Error URL Counters
**Goal:** Exact deterministic rankings answer the first two incident questions.

**Time:** 1.5 h.

**Context:** Architecture metric contract, PRD stories S1–S2.

**Tasks:**
1. Create `src/nginx_lens/aggregate.py` with IP and combined 400–599 path counters over valid records.
2. Add `tests/test_rankings.py` for 399/400/499/500/599 boundaries, lexical ties, fewer/more than 10 keys, and normalized paths; use bounded top selection without sorting every input record.

**Verification:** `python -m pytest tests/test_rankings.py tests/test_parser.py`.

**Commit:** `step-3: rank IP traffic and error paths`.

## Step 4: Hourly/UA Metrics and Capacity Guard
**Goal:** All metric values are exact and capacity failure is explicit.

**Time:** 2 h.

**Context:** Architecture metrics/resource contract; PRD stories S3–S4 and S7.

**Tasks:**
1. Extend `aggregate.py` and `models.py` with 24 local-offset hour bins, exact nonmissing UA set, valid/invalid counts, percentage conversion and complete summary construction.
2. Add pre-update global entry-budget check for all new keys together; implement a dedicated capacity exception. Default limit is 1,000,000 entries; no approximation or disk spill.
3. Create `tests/test_metrics.py` and `tests/test_capacity.py` for hand-computed percentages, repeated/missing UAs, mixed dates/offsets, exactly-at-limit, multi-key overflow before mutation, empty input, and injected MemoryError mapping boundary.

**Verification:** `python -m pytest tests/test_metrics.py tests/test_capacity.py tests/test_rankings.py`.

**Commit:** `step-4: compute hourly and UA metrics with exact bounds`.

## Step 5: Terminal, JSON, and CSV Reports
**Goal:** The same summary produces readable and stable machine reports.

**Time:** 2 h.

**Context:** Architecture output schemas and CLI Interface.

**Tasks:**
1. Create `src/nginx_lens/render.py` with Rich tables, two-decimal percentages, schema-versioned JSON, normalized CSV and safe terminal escaping.
2. Create `tests/test_render.py` and `tests/fixtures/expected.csv` to validate exact fields, row order, quoting, tie order, missing percentages, numeric JSON percentages and no ANSI in machine modes.
3. Check dangerous controls and Rich markup appear as inert text; preserve machine keys through standards-compliant escaping.

**Verification:** `python -m pytest tests/test_render.py`.

**Commit:** `step-5: render deterministic terminal and pipeline reports`.

## Step 6: Complete CLI and Failure Semantics
**Goal:** The public command implements every option and every failure path.

**Time:** 2 h.

**Context:** Architecture CLI Interface; PRD S5–S7.

**Tasks:**
1. Wire `cli.py` to reader/parser/aggregator/renderers; validate options before opening input. Support optional path or `-`, mutually exclusive --json/--csv, --max-unique, --no-color, --help and --version.
2. Create `tests/test_cli.py` using Click CliRunner for 0/1/2/3/4, invalid-line warnings, zero stdout on fatal input/resource failures, NO_COLOR/TTY behavior, interruption, and broken pipe.
3. Require complete input consumption before output; keep diagnostics on stderr and never echo raw log lines.

**Verification:** `python -m pytest tests/test_cli.py tests/test_capacity.py tests/test_render.py`.

**Commit:** `step-6: connect CLI and preserve exit contract`.

## Step 7: End-to-End Correctness and Wheel Installation
**Goal:** Independent hand-counted fixtures and a clean installed package agree across modes.

**Time:** 1.5 h.

**Context:** PRD P0 acceptance; architecture security/distribution.

**Tasks:**
1. Create `tests/test_end_to_end.py` to compare real subprocess file/stdin invocations against checked-in metric oracles and parsed JSON/CSV, including all-invalid input and capacity exhaustion.
2. Create `tests/test_install.py` to install a built wheel in a temporary environment and verify entry point, version and a report without relying on source-directory imports.
3. Inspect terminal control handling, no outbound operations and dependency scope; update `README.md` examples if needed.

**Verification:** `python -m pytest --cov=nginx_lens --cov-branch --cov-report=term-missing`; `python -m build`; `python -m pytest tests/test_install.py`.

**Commit:** `step-7: verify reports and installed wheel`.

## Step 8: Performance Evidence and Handoff
**Goal:** Measure the target honestly and reconcile final documentation with implementation.

**Time:** 2 h.

**Context:** Architecture performance section and strategic DoD.

**Tasks:**
1. Create `benchmarks/generate_log.py` and `benchmarks/run.py` for a deterministic, explicitly synthetic, valid 1 GB input below default cardinality budget and subprocess wall-clock/peak-RSS collection.
2. Record laptop, workload distribution, dependency versions, cache state, three warm runs, median, and any available cold observation in `benchmarks/RESULTS.md`; profile and rerun only if changes warrant it.
3. If the median is not below 30 s, record failure and optimize within the same architecture; escalate scope explicitly if the weekend is insufficient. Never substitute a partial-input/code-4 timing.
4. Reconcile `README.md`, all blueprint documents and `CLAUDE.md` status; record tests and unresolved risks through session-save. Obtain separate authorization before release publication.

**Verification:** `python benchmarks/generate_log.py --bytes 1000000000 --output /tmp/nginx-lens-bench.log`; `python benchmarks/run.py --input /tmp/nginx-lens-bench.log --runs 3 --max-seconds 30`; `python -m pytest`.

**Commit:** `step-8: record throughput and delivery evidence`.

## Delivery Boundaries
Saturday completes steps 1–6 where possible; Sunday completes steps 7–8 and absorbs parser/performance risk. No multiweek sprint scheme is needed for eight steps. Gzip and configurable formats stay outside this implementation sequence. No code, test suite, wheel, or benchmark was executed during this planning session.
