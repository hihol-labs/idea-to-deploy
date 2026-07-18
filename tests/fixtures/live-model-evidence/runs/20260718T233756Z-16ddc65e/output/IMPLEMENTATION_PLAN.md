# Implementation Plan: Nginx Log Lens

This is a documentation-only delivery plan; no product code is implemented by
the blueprint workflow. Steps are dependency-ordered while honoring the RICE
priorities in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package layout and Python 3.11 tool configuration | Every module and check depends on a reproducible install | 1 h |
| 2 | Domain/output schema contracts and fixtures | Prevents parser, aggregator, and renderers from diverging | 1.5 h |
| 3 | Benchmark fixture generator and measurement protocol | Makes the 30-second claim testable before feature polish | 1 h |

No database schema, authentication system, Docker setup, or CI deployment
runway is needed because the approved architecture has none of those systems.

## Step 1: Package and quality skeleton

**Goal:** A Python 3.11 package installs and exposes a placeholder-free Click command.

**Time:** ~1 hour

**Context:** Architecture sections 3, 8, and 9.

**Tasks:**

1. Create `pyproject.toml` with runtime/dev dependencies, console entry point, build backend, test and static-check settings.
2. Create `src/nginx_log_lens/__init__.py`, `src/nginx_log_lens/__main__.py`, and `src/nginx_log_lens/cli.py`.
3. Create `tests/test_cli.py` for help, version, and invalid option behavior.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli.py`
- `nginx-log-lens --help`

**Commit:** `step-1: establish installable CLI package`

## Step 2: Domain and output contracts

**Goal:** Typed records and deterministic report schemas are executable contracts.

**Time:** ~1.5 hours

**Context:** Architecture sections 4 and 6; PRD stories US-05 and US-06.

**Tasks:**

1. Create `src/nginx_log_lens/models.py` with frozen dataclasses for parsed requests, ranked entries, summary, and report snapshot.
2. Create `tests/contracts/test_report_schema.py` for JSON keys, CSV columns, ranks, units, and schema version.
3. Create `tests/fixtures/expected/` with small canonical expected outputs.

**Verification:**

- `python3.11 -m pytest tests/contracts/test_report_schema.py`
- `python3.11 -m mypy src`

**Commit:** `step-2: define report domain contracts`

## Step 3: Streaming nginx parser

**Goal:** Common and combined nginx lines are lazily converted to domain records while malformed lines are counted.

**Time:** ~3 hours

**Context:** Architecture sections 4, 5, and 10; PRD stories US-01 and US-07.

**Tasks:**

1. Create `src/nginx_log_lens/input.py` for lazy file/stdin iteration and explicit input errors.
2. Create `src/nginx_log_lens/parser.py` for common/combined grammar, timestamp, request target, status, and User-Agent parsing.
3. Create `src/nginx_log_lens/errors.py` for stable fatal error categories.
4. Create `tests/test_parser.py`, `tests/test_input.py`, and representative `tests/fixtures/*.log` cases.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_input.py`
- `python3.11 -m ruff check src/nginx_log_lens/parser.py src/nginx_log_lens/input.py`

**Commit:** `step-3: parse nginx logs as a lazy stream`

## Step 4: One-pass aggregation

**Goal:** All four required reports are computed correctly in one pass.

**Time:** ~3 hours

**Context:** Architecture sections 3–5; PRD stories US-02, US-03, and US-04.

**Tasks:**

1. Create `src/nginx_log_lens/aggregate.py` with IP counts, 4xx/5xx URL counts, 24 hour buckets, exact User-Agent cardinality, and final top-10 selection.
2. Create `tests/test_aggregate.py` covering tie order, missing User-Agent, zero valid lines, status boundaries, and all 24 buckets.
3. Create `tests/test_streaming.py` asserting iterator consumption without retaining raw input.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py tests/test_streaming.py`
- `python3.11 -m mypy src/nginx_log_lens/aggregate.py`

**Commit:** `step-4: compute all reports in one pass`

## Step 5: Rich terminal report

**Goal:** Default output is readable colored terminal text without corrupting redirected output.

**Time:** ~2 hours

**Context:** Architecture section 6; PRD story US-05.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/text.py` with four labeled Rich sections and summary diagnostics.
2. Update `src/nginx_log_lens/cli.py` to choose text output and honor `--no-color`/TTY behavior.
3. Create `tests/test_text_renderer.py` with forced-color and no-color snapshots.

**Verification:**

- `python3.11 -m pytest tests/test_text_renderer.py tests/test_cli.py`
- `nginx-log-lens tests/fixtures/combined.log --no-color`

**Commit:** `step-5: render default Rich terminal report`

## Step 6: JSON and CSV pipeline formats

**Goal:** Automation consumers receive stable, ANSI-free, parseable formats.

**Time:** ~2.5 hours

**Context:** Architecture section 6; PRD story US-06.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/json.py` and `src/nginx_log_lens/renderers/csv.py`.
2. Update `src/nginx_log_lens/cli.py` with mutually exclusive `--json` and `--csv` flags and stdout/stderr separation.
3. Create `tests/test_json_renderer.py`, `tests/test_csv_renderer.py`, and pipeline integration assertions.

**Verification:**

- `python3.11 -m pytest tests/test_json_renderer.py tests/test_csv_renderer.py tests/test_cli.py`
- `nginx-log-lens --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: Failure behavior and end-to-end flows

**Goal:** File, stdin, malformed input, broken-pipe, and fatal errors follow the documented contract.

**Time:** ~2 hours

**Context:** Architecture sections 4, 6, and 10; PRD stories US-01, US-06, and US-07.

**Tasks:**

1. Complete exit-code and exception mapping in `src/nginx_log_lens/cli.py` and `src/nginx_log_lens/errors.py`.
2. Create `tests/integration/test_end_to_end.py` for file/stdin and all renderers.
3. Create `tests/integration/test_failures.py` for missing files, invalid encoding, conflicting flags, and closed pipes.

**Verification:**

- `python3.11 -m pytest tests/integration`
- `printf '%s\n' 'malformed' | nginx-log-lens --json | python3.11 -m json.tool >/dev/null`

**Commit:** `step-7: harden CLI boundaries and failure modes`

## Step 8: Performance and resource gate

**Goal:** Reproducible evidence shows whether the 1 GB/30-second target and memory budget are met.

**Time:** ~3 hours

**Context:** Architecture section 5; PRD nonfunctional requirements.

**Tasks:**

1. Create `benchmarks/generate_log.py` for the deterministic 1 GiB fixture and exact cardinalities specified in Architecture section 5, outside version control.
2. Create `benchmarks/run.py` to record Python/platform, bytes, lines, elapsed time, throughput, and peak RSS.
3. Create `tests/performance/test_memory_shape.py` for bounded raw-line retention and document results in `benchmarks/RESULTS.md`.

**Verification:**

- `python3.11 benchmarks/generate_log.py --size-gib 1 --ips 4096 --urls 50000 --user-agents 25000 --seed 20260719 --output /tmp/nginx-log-lens-1g.log`
- `python3.11 benchmarks/run.py /tmp/nginx-log-lens-1g.log --max-seconds 30 --max-rss-mib 250`

**Commit:** `step-8: verify gigabyte-scale performance`

## Step 9: Release and handoff

**Goal:** The package is buildable, installable in isolation, documented, and ready for an open-source release.

**Time:** ~2 hours

**Context:** Strategic Plan Definition of Done; Architecture section 9.

**Tasks:**

1. Update `README.md` with final install, usage, output schema, limitations, and benchmark environment.
2. Create `LICENSE`, `CHANGELOG.md`, and package metadata in `pyproject.toml`.
3. Create `tests/test_package.py` for wheel installation and console entry point.
4. Record acceptance evidence and reconcile the active Idea to Deploy state.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_lens --cov-fail-under=90`
- `python3.11 -m ruff check . && python3.11 -m mypy src && python3.11 -m build`
- `python3.11 -m twine check dist/*`

**Commit:** `step-9: prepare verified open-source release`

## Sprint boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Runway, contracts, parsing | Saturday morning |
| Weekend block 2 | 4–5 | Core metrics and terminal UX | Saturday afternoon |
| Weekend block 3 | 6–7 | Pipeline formats and resilient boundaries | Sunday morning |
| Weekend block 4 | 8–9 | Performance evidence and release | Sunday afternoon |

## Dependency and completion rules

WIP remains one step. A step starts only after the prior step's listed checks
pass and evidence is recorded. A failed performance gate returns work to the
measured bottleneck; it does not permit deleting acceptance criteria or
silently changing exact metrics. The final gate is the Definition of Done in
[STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).
