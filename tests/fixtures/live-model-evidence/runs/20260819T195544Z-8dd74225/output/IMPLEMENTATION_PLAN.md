# Implementation Plan: Nginx Log Lens

## Planning Basis

This nine-step weekend plan implements the P0 scope in dependency order. RICE
scores order work within dependency boundaries; the parser is necessarily the
first product capability because every metric depends on it. Product behavior
comes from `PRD.md`; component boundaries and CLI semantics come from
`PROJECT_ARCHITECTURE.md`.

No step may add authentication, a database, HTTP API, server, cloud service, or
Kubernetes. The complete exit-code contract is immutable across every step:
`0` success, `1` input/I/O failure, `2` CLI usage error, `3` nonempty input with
no valid record, and `4` unique-cardinality exhaustion. Code 4 must never be
omitted or remapped.
The complete contract is `0/1/2/3/4`. Code `4` means unique-cardinality
exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package and console entry point | Gives every later capability a stable import and CLI boundary | 0.75 h |
| 2 | Typed domain and exception contracts | Prevents renderers and CLI from inventing metric or failure semantics | 0.50 h |
| 3 | Fixture taxonomy and quality commands | Makes parser/output/performance changes measurable from the start | 0.75 h |

There is intentionally no database schema, auth runway, container, or CI/CD
deployment setup. Those would be product scope, not enabling infrastructure.

## Step 1: Establish the Installable Package

**Goal:** A clean Python 3.11 environment can install the project and invoke a
minimal Click command.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Packaging and Runtime,
Components and Responsibilities.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11`, Click, Rich, build metadata,
   the `src/` package discovery rule, and `nginx-log-lens` console entry point.
2. Create `src/nginx_log_lens/__init__.py` with package version exposure.
3. Create `src/nginx_log_lens/cli.py` with the Click command shell, help, and
   version behavior only.
4. Create `src/nginx_log_lens/models.py` and `src/nginx_log_lens/errors.py` with
   the typed contracts specified by the architecture.
5. Create `tests/test_cli.py` with install/import/help/version smoke coverage.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-log-lens --help`
- `.venv/bin/python -m pytest tests/test_cli.py -q`

**Commit:** `step-1: establish installable CLI package`

## Step 2: Implement Combined-Format Parsing

**Goal:** Valid nginx combined lines become typed `LogRecord` objects, while
malformed lines are identified without per-line output.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Inputs, Data Model, Error
Handling; `PRD.md` FR-01 through FR-03.

**Tasks:**

1. Create `src/nginx_log_lens/parser.py` with one precompiled combined-format
   parser, timestamp offset handling, request splitting, status conversion, and
   `-` bytes handling.
2. Create `tests/fixtures/combined.log` containing representative IPv4, IPv6,
   quoted User-Agent, query-string, zero-byte, and timezone cases.
3. Create `tests/fixtures/malformed.log` for truncated, undecodable, invalid
   status, and invalid timestamp cases.
4. Create `tests/test_parser.py` with exact field and malformed-result tests.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/ruff check src/nginx_log_lens/parser.py tests/test_parser.py`
- `.venv/bin/mypy src/nginx_log_lens/parser.py`

**Commit:** `step-2: parse nginx combined access logs`

## Step 3: Aggregate Top IPs and Error URLs

**Goal:** A single pass produces deterministic top-N client-IP and 4xx/5xx URL
rankings plus valid/malformed totals.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Streaming and Complexity; `PRD.md` US-1,
US-2, and FR-04.

**Tasks:**

1. Create `src/nginx_log_lens/aggregate.py` with line iteration, parser
   integration, request counters, error-status filtering, and deterministic
   count-descending/key-ascending top-N finalization.
2. Extend `src/nginx_log_lens/models.py` with frozen `RankedItem` and `Report`
   fields required by this step.
3. Create `tests/test_aggregate_rankings.py` for ties, fewer/more than ten keys,
   non-error exclusion, query-string identity, and mixed malformed input.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate_rankings.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py tests/test_aggregate_rankings.py -q`
- `.venv/bin/mypy src/nginx_log_lens/models.py src/nginx_log_lens/aggregate.py`

**Commit:** `step-3: aggregate deterministic top rankings`

## Step 4: Add Hourly and Unique User-Agent Metrics

**Goal:** The report includes all 24 hourly percentages, unique User-Agent
count/share, and a fail-closed cardinality guard.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs and Streaming and Complexity;
`PRD.md` US-3 and US-4.

**Tasks:**

1. Extend `src/nginx_log_lens/aggregate.py` with 24 fixed counters and compute
   each percentage as `100 × hourly_request_count / total_valid_requests`.
2. Track distinct User-Agents and all other guarded distinct dimensions with
   `--max-unique` semantics; raise the dedicated cardinality exception before
   exceeding the configured ceiling.
3. Extend `src/nginx_log_lens/models.py` with `HourlyBucket`, unique count, and
   share fields.
4. Create `tests/test_aggregate_metrics.py` for all hours, empty input,
   rounding boundaries, unique share, and exhaustion at/above the limit.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate_metrics.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate_rankings.py tests/test_aggregate_metrics.py -q`
- `.venv/bin/mypy src/nginx_log_lens/aggregate.py src/nginx_log_lens/models.py`

**Commit:** `step-4: calculate hourly and user-agent metrics`

## Step 5: Build the Three Renderers

**Goal:** Rich text, JSON, and CSV serialize one immutable report with identical
values and deterministic ordering.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs, Components and Responsibilities,
Security and Privacy; `PRD.md` US-5 and US-6.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/__init__.py` with renderer selection
   types only.
2. Create `src/nginx_log_lens/renderers/text.py` with Rich summary and four
   clearly labeled metric sections, respecting non-TTY color behavior.
3. Create `src/nginx_log_lens/renderers/json.py` with stable snake_case keys and
   two-decimal percentage values.
4. Create `src/nginx_log_lens/renderers/csv.py` with
   `section,rank,key,count,percentage` records and formula-injection protection.
5. Create `tests/test_renderers.py` and golden files under `tests/golden/` to
   reconcile all formats against one known report.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -q`
- `.venv/bin/python -m pytest tests/test_renderers.py --snapshot-update` is not permitted; golden changes require explicit review
- `.venv/bin/ruff check src/nginx_log_lens/renderers tests/test_renderers.py`

**Commit:** `step-5: render text json and csv reports`

## Step 6: Complete CLI Options and Exit Handling

**Goal:** File/stdin processing, options, diagnostics, and all five exit codes
behave exactly as the public contract specifies.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section CLI Interface; `PRD.md` US-6,
US-7, and FR-08.

**Tasks:**

1. Complete `src/nginx_log_lens/cli.py` with optional `INPUT`, mutually
   exclusive `--json`/`--csv`, `--top`, and `--max-unique`.
2. Map success to 0, I/O failure to 1, Click usage error to 2, malformed-only
   parsing to 3, and unique-cardinality exhaustion to 4.
3. Ensure all failure diagnostics go to stderr and no partial report reaches
   stdout.
4. Extend `tests/test_cli.py` with file, stdin, flags, bounds, conflict, empty,
   malformed-only, missing-file, and cardinality-exhaustion cases.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/nginx-log-lens --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`
- `test "$(.venv/bin/nginx-log-lens --max-unique 1 tests/fixtures/combined.log >/dev/null 2>&1; echo $?)" -eq 4`

**Commit:** `step-6: enforce CLI and exit-code contracts`

## Step 7: Close Correctness and Quality Gaps

**Goal:** The complete behavior suite, type checks, lint, and coverage gate pass
without placeholders or skipped P0 cases.

**Time:** ~1.5 hours

**Context:** `PRD.md` Release Acceptance and Non-Functional Requirements.

**Tasks:**

1. Create `tests/test_end_to_end.py` to reconcile text, JSON, and CSV values
   and exercise pipes and redirected output.
2. Create `tests/test_exit_codes.py` as the single table-driven oracle for
   `0/1/2/3/4`, explicitly asserting code 4 for unique-cardinality exhaustion.
3. Add pytest, coverage, Ruff, and mypy configuration to `pyproject.toml`.
4. Review every P0 acceptance criterion and add any missing focused case.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_log_lens --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/ruff check .`
- `.venv/bin/mypy src`

**Commit:** `step-7: complete correctness and quality gates`

## Step 8: Prove the 1 GB Performance Contract

**Goal:** A deterministic 1 GB fixture completes below 30 seconds and within
256 MiB peak RSS on the documented reference laptop.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Streaming and Complexity; `PRD.md`
NFR-01 and NFR-02.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically stream a 1 GB
   combined-format fixture without committing the generated file.
2. Create `scripts/run_benchmark.sh` to record Python version, CPU/OS profile,
   elapsed time, peak RSS, input size, and exit status.
3. Create `BENCHMARK.md` with the reference machine and measured result.
4. Profile only if the first measurement fails; optimize the measured hotspot
   without changing output or exit semantics.

**Verification:**

- `.venv/bin/python scripts/generate_benchmark_log.py --size-gib 1 --output /tmp/nginx-log-lens-benchmark.log`
- `scripts/run_benchmark.sh /tmp/nginx-log-lens-benchmark.log`
- `.venv/bin/python -m pytest -q`

**Commit:** `step-8: verify one-gigabyte performance target`

## Step 9: Validate Distribution and Handoff

**Goal:** A clean Python 3.11 environment installs the built artifact and the
documentation matches the tested CLI.

**Time:** ~1 hour

**Context:** All blueprint documents, especially `PRD.md` Release Acceptance.

**Tasks:**

1. Update `README.md` with final install, usage, supported input, output, and
   complete `0/1/2/3/4` exit-code examples.
2. Build wheel and sdist into `dist/`; do not publish during this step.
3. Install the wheel into a new temporary Python 3.11 environment and run
   file/stdin/JSON/CSV smoke tests.
4. Reconcile `CLAUDE.md` status and record exact quality/benchmark evidence in
   the project handoff.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/python -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-log-lens-smoke && /tmp/nginx-log-lens-smoke/bin/pip install dist/*.whl && /tmp/nginx-log-lens-smoke/bin/nginx-log-lens --json tests/fixtures/combined.log`

**Commit:** `step-9: validate package and documentation handoff`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable foundation and correct parser | ~3.5 h |
| Saturday PM | 3–4 | Complete streaming metric engine | ~4 h |
| Sunday AM | 5–6 | Human/machine output and CLI contracts | ~4.5 h |
| Sunday PM | 7–9 | Quality, benchmark, and distribution proof | ~4 h |

## Plan Acceptance

Implementation is complete only after Step 9 evidence is recorded and every P0
criterion in `PRD.md` is traceable to a passing test. Narrative confidence does
not replace commands, benchmark evidence, or a clean-wheel smoke test.
