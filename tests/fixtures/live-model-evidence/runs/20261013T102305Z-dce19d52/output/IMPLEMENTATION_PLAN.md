# Implementation Plan: Nginx Lens

Planning only: every step below is unstarted. The eight steps total 14 hours, with a separate 2-hour weekend contingency. Dependency ordering adjusts the RICE order: scaffold and parse before the higher-scoring metrics and exports, then complete operational validation. References: [strategy and RICE](STRATEGIC_PLAN.md), [architecture](PROJECT_ARCHITECTURE.md), [acceptance criteria](PRD.md), [prompts](CLAUDE_CODE_GUIDE.md), [README](README.md), [status](CLAUDE.md).

## Shared Implementation Contract

Preserve Python 3.11, Click, Rich, dataclasses, a single process, and no persistent state or network service. Exit codes are **0/1/2/3/4**: 0 successful/empty input or help/version; 1 I/O or internal runtime failure; 2 invalid CLI usage; 3 malformed input (default report over valid lines, strict mode no report); 4 unique-cardinality exhaustion, including either configured key cap, with no report. Never collapse code 4 into code 1 or 3.

Hourly percentages use `100 × hourly_request_count / total_valid_requests`, with 0 for empty denominators. Exact unique UA share excludes unknown UA markers from the numerator only. PROJECT_ARCHITECTURE.md is the interface and semantics contract; PRD.md provides replayable acceptance criteria. Do not add product features to resolve a test failure without updating those specifications and scope first.

Commands below are planned implementation checks, not evidence of tests already run. Use a Python 3.11 venv. Add pytest, pytest-cov, and build as development extras during Step 1. Commit messages are suggestions for the implementation session; this planning session makes no commits.

## Architectural Runway

| Item | Why first | Effort (included below) |
|---|---|---|
| Package, venv, unit-test command | Reproducible local checks from the first code change | Step 1, 1 hour |
| Dataclass and report schema contract | Parser, metrics, and exporters must agree | Step 1, 0.5 hour |
| Hand-audited combined-log fixtures and parser boundary | Exact metrics depend on recognized records | Step 2, 3 hours |
| Aggregate key/byte budgets | Exact sets cannot grow indefinitely | Step 4, 0.5 hour |

No database migrations, authentication, container stack, or cloud setup belongs in the runway.

## Step 1: Package and Data Contracts

**Goal:** Installable skeleton and agreed dataclasses exist, without fabricated analytics.
**Time:** 1.5 hours.
**Context:** Architecture: Components, Metrics, CLI Interface, Output Schemas.
**Tasks:**

1. Create `pyproject.toml`, `src/nginx_lens/__init__.py`, `src/nginx_lens/cli.py`, and `LICENSE`; wire the `nginx-lens` entry point, help, version, Python requirement, runtime and dev dependencies.
2. Create `src/nginx_lens/models.py` with slotted LogRecord, Limits, ErrorCounts, and Report dataclasses; no mutable shared defaults.
3. Create `tests/test_package.py` for import, help/version, and positive-limit validation.

**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_package.py`; `nginx-lens --help`.
**Commit:** `step-1: establish package and data contracts`.

## Step 2: Bounded Reader and Combined Parser

**Goal:** File and stdin lines produce validated records with deterministic malformed-line classification.
**Time:** 3 hours.
**Context:** Architecture: Input and Parsing Contract, CLI Interface.
**Tasks:**

1. Create `src/nginx_lens/reader.py` and `src/nginx_lens/parser.py`; bound line buffering, drain oversized lines, recognize combined fields, decode nginx escapes, validate IP/status/request/timestamp, and calculate UTC hour.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, `tests/test_reader.py`, and `tests/test_parser.py`. Include LF/CRLF, no final newline, offset day crossings, IPv6, escaped quotes, non-UTF-8 input, unknown UAs, and line-length boundaries.
3. Keep diagnostic data to line number and reason, never the raw record. Default skip versus strict-abort orchestration is integrated in Step 6.

**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.
**Commit:** `step-2: parse combined logs with bounded reads`.

## Step 3: Four Exact Metrics

**Goal:** All report metrics and deterministic rankings are correct before rendering.
**Time:** 2 hours.
**Context:** Architecture: Metrics and In-Memory Model, Output Schemas; PRD stories S1–S4.
**Tasks:**

1. Create `src/nginx_lens/aggregate.py` for valid/invalid totals, IP counts, combined error-URL counts, 24 UTC buckets, and exact known-UA set; finalize an immutable report snapshot at EOF.
2. Create `tests/test_aggregate.py` with hand-calculated denominators, more than ten candidates, tie boundaries, empty input, duplicate/unknown agents, and error category separation.
3. Use full request targets including queries as URL keys. Select top ten without losing exact counts of lower-ranked candidates during streaming.

**Verification:** `python -m pytest tests/test_aggregate.py`.
**Commit:** `step-3: calculate exact traffic and error summaries`.

## Step 4: Cardinality Limits

**Goal:** Aggregation stops predictably before adding keys beyond either capacity budget.
**Time:** 0.5 hour.
**Context:** Architecture: Exactness and Resource Limits; PRD S7.
**Tasks:**

1. Extend `src/nginx_lens/aggregate.py` with preflight over all new keys in each record; define a dedicated capacity exception in `src/nginx_lens/models.py`.
2. Create `tests/test_limits.py` for exact-cap insertion, one-over-cap rejection, repeated keys at capacity, UTF-8 byte lengths, identical text in different collections, and a record that adds three keys atomically.
3. Assert failed preflight leaves every metric unchanged. Connect exception to exit 4 in Step 6.

**Verification:** `python -m pytest tests/test_limits.py tests/test_aggregate.py`.
**Commit:** `step-4: bound exact aggregation state`.

## Step 5: Terminal, JSON, and CSV Reports

**Goal:** Each output contains equivalent metrics and adheres to its display/serialization rules.
**Time:** 2 hours.
**Context:** Architecture: Output Schemas, CLI Interface; PRD S5.
**Tasks:**

1. Create `src/nginx_lens/render.py` with literal Rich text, a version-1 JSON serializer, and the single-table CSV serializer.
2. Create `tests/test_render.py` and `tests/test_export_schema.py` covering empty reports, six-decimal percentages, numeric types, CSV quoting, formula prefixes, control characters, and no ANSI in machine output.
3. Ensure serialization completes before publishing to stdout. Test `NO_COLOR`, explicit no-color, TTY, and redirected output behaviors.

**Verification:** `python -m pytest tests/test_render.py tests/test_export_schema.py`.
**Commit:** `step-5: render terminal and pipeline reports`.

## Step 6: CLI Integration and Failure Paths

**Goal:** Users can analyze files and pipes with documented output and exit behavior.
**Time:** 1.5 hours.
**Context:** Architecture: CLI Interface, error precedence; PRD S6–S7.
**Tasks:**

1. Complete `src/nginx_lens/cli.py`: options, source selection, per-line loop, malformed counts, strict mode, resource closure, final rendering, and exception mapping.
2. Create `tests/test_cli.py` for file/stdin equivalence, the 0/1/2/3/4 contract, stderr/stdout separation, conflicting flags, missing file, interruption, input failure after valid records, and broken output pipes.
3. Assert no stdout on strict or capacity abort, and a valid complete report plus status 3 after non-strict skipped lines. Verify fatal failure precedence.

**Verification:** `python -m pytest tests/test_cli.py`; `nginx-lens --json tests/fixtures/combined.log`; `cat tests/fixtures/combined.log | nginx-lens --csv -`.
**Commit:** `step-6: integrate streaming CLI and failure contract`.

## Step 7: Measure Performance and Security Boundaries

**Goal:** Establish whether the performance acceptance target is met and hostile data remains inert.
**Time:** 2 hours.
**Context:** Architecture: Verification, Performance, and Delivery; PRD nonfunctional requirements.
**Tasks:**

1. Create `benchmarks/generate.py`, `benchmarks/run.py`, and `benchmarks/README.md` with the exact reference workload, generation oracle, resource capture, environment metadata, and repeated-run gate. Keep fixture generation outside the timed interval.
2. Create `tests/test_hostile_input.py` covering terminal control sequences, Rich markup, CSV formulas, oversized lines, and exhaustion. No network or execution of log strings is allowed.
3. Record real results in `benchmarks/results.json`; optimize measured hotspots only. If the target fails, record the failure and block release rather than substituting an easier workload or claiming success.

**Verification:** `python -m pytest tests/test_hostile_input.py`; `python benchmarks/generate.py --bytes 1000000000 --seed 42 --output .benchmark/reference.log`; `python benchmarks/run.py --input .benchmark/reference.log --runs 3 --max-seconds 30 --max-rss-mib 512 --output benchmarks/results.json`.
**Commit:** `step-7: measure throughput and adversarial input boundaries`.

## Step 8: Release Candidate and Handoff

**Goal:** A tested local wheel and accurate user documentation are ready for a release decision.
**Time:** 1.5 hours.
**Context:** Strategy: Definition of Done; README Quick Start; all PRD P0 criteria.
**Tasks:**

1. Update `README.md`, `CLAUDE.md`, and `CLAUDE_CODE_GUIDE.md` with actual installation and verification outcomes. Add `.github/workflows/tests.yml` for Python 3.11 correctness/build checks where free CI is available; local tests remain sufficient to avoid a service dependency.
2. Create `tests/test_wheel_install.py` that builds/installs the wheel into a temporary clean venv and smoke-tests all three output modes. Verify included MIT license and dependency compatibility.
3. Run code/security review during implementation, record remaining issues, and reconcile `.itd-memory/STATE.json` with evidence. No automatic upload to a registry is included.

**Verification:** `python -m pytest --cov=nginx_lens.parser --cov=nginx_lens.aggregate --cov-branch --cov-fail-under=90`; `python -m build`; `python -m pytest tests/test_wheel_install.py`.
**Commit:** `step-8: prepare verified local wheel and handoff`.

## Delivery Boundary and Recovery

The weekend has two daily checkpoints: Saturday completes Steps 1–4; Sunday completes Steps 5–8. This eight-step project needs no multi-sprint cadence. gzip and filters stay deferred even if runtime tuning consumes the contingency. A failed P0 criterion blocks release; record evidence and the next repair action. Reconsider the deadline explicitly if two hours of contingency cannot resolve a failure. Do not weaken exactness, the exit contract, or the benchmark definition silently.

Current next action: external harness architecture review, followed by implementation Step 1 in a separate authorized implementation session. Static blueprint checks are not runtime or independent-review evidence.
