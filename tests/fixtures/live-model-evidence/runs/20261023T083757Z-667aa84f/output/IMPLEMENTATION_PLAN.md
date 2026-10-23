# Implementation Plan: Nginx Stream Analyzer

This plan implements the P0 scope in dependency order and leaves P1 gzip support until the core contract is proven. Product behavior comes from `PRD.md`; component boundaries and schemas come from `PROJECT_ARCHITECTURE.md`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package skeleton and Python 3.11 tooling | Every module and verification command depends on reproducible installation | 1 hour |
| 2 | Typed records and error taxonomy | Parser, aggregator, renderers, and CLI need one shared contract | 1 hour |
| 3 | Representative fixture corpus | Prevents implementation from defining correctness after the fact | 1 hour |
| 4 | Benchmark generator and measurement protocol | Tests the weekend’s highest technical risk early | 1 hour |

No database schema, migration, authentication system, API, Docker setup, or CI deployment pipeline belongs in the runway because the approved product is a local stateless CLI.

## Step 1: Establish Package and Quality Baseline

**Goal:** A clean Python 3.11 environment can install the package and invoke a placeholder CLI entry point.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Design” and “Packaging and Deployment”.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, test extras, build backend, and the `nginx-stream-analyzer` entry point.
2. Create `src/nginx_stream_analyzer/__init__.py` and `src/nginx_stream_analyzer/__main__.py`.
3. Create `src/nginx_stream_analyzer/cli.py` with Click help and version wiring only.
4. Create `tests/test_cli.py` for help, version, and import smoke tests.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/nginx-stream-analyzer --help`

**Commit:** `step-1: establish installable CLI skeleton`

## Step 2: Define Models, Configuration, and Errors

**Goal:** All later components share typed, immutable contracts and stable error categories.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Metric Semantics” and “Parsing and Failure Policy”.

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with frozen dataclasses for `AccessRecord`, ranked values, hourly values, and `ReportSnapshot`.
2. Create `src/nginx_stream_analyzer/config.py` with a frozen run configuration and validation for encoding and cardinality cap.
3. Create `src/nginx_stream_analyzer/errors.py` with input, empty-valid-input, and cardinality exhaustion exceptions.
4. Create `tests/test_models.py` and `tests/test_config.py` for immutability and validation boundaries.

**Verification:**

- `.venv/bin/python -m pytest tests/test_models.py tests/test_config.py -q`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: define domain and failure contracts`

## Step 3: Implement and Lock the Nginx Parser

**Goal:** Supported combined-format lines become exact records; malformed or undecodable data is classified consistently.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Parsing and Failure Policy”; `PRD.md` FR-P0-1.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with one compiled combined-format parser and timestamp conversion.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/edge-cases.log` with hand-audited expected values.
3. Create `tests/test_parser.py` covering IPv4/IPv6, quotes, query strings, timezone offsets, status boundaries, empty User-Agent, malformed request, and invalid timestamp.
4. Document the supported format boundary in `README.md`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_stream_analyzer.parser --cov-fail-under=95`

**Commit:** `step-3: implement combined-log parser`

## Step 4: Build Buffered Input Handling

**Goal:** Regular files and stdin yield lines incrementally with explicit open/read/decode failures.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Security and Privacy”.

**Tasks:**

1. Create `src/nginx_stream_analyzer/reader.py` with context-managed file and non-owning stdin iterators.
2. Add `tests/test_reader.py` for file, stdin, missing file, permission/read failure where portable, decoding failure, and constant-size reads.
3. Ensure the reader never closes caller-owned stdin and never opens input for writing.

**Verification:**

- `.venv/bin/python -m pytest tests/test_reader.py -q`
- `.venv/bin/python -m pytest tests/test_reader.py -k 'stdin or decode or missing' -q`

**Commit:** `step-4: add streaming input adapters`

## Step 5: Implement Exact Streaming Aggregation

**Goal:** One pass computes all four metrics with deterministic top lists and explicit cardinality limits.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Metric Semantics” and “Performance and Resource Strategy”; `PRD.md` FR-P0-2 through FR-P0-6.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with counters, hourly buckets, User-Agent set, invalid-line count, and finalization.
2. Compute hourly distribution with exactly `100 × hourly_request_count / total_valid_requests`.
3. Apply count-descending/key-ascending ordering and truncate both rankings to 10 entries.
4. Raise the typed exhaustion error before adding a distinct key beyond `--max-unique`; do not create a report snapshot afterward.
5. Create `tests/test_aggregate.py` covering 4xx/5xx boundaries, ties, zero valid records, percentage totals, and exhaustion for each guarded dimension.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_stream_analyzer.aggregate --cov-fail-under=95`

**Commit:** `step-5: implement bounded streaming metrics`

## Step 6: Add Terminal, JSON, and CSV Renderers

**Goal:** A single snapshot renders as readable Rich output or stable machine formats without semantic drift.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs” and “Output Schemas”; `PRD.md` FR-P0-7 through FR-P0-9.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/base.py` for the renderer protocol.
2. Create `src/nginx_stream_analyzer/renderers/terminal.py`, escaping untrusted log values and honoring color policy.
3. Create `src/nginx_stream_analyzer/renderers/json.py` with schema version 1.
4. Create `src/nginx_stream_analyzer/renderers/csv.py` using Python’s `csv` module and the long-form schema.
5. Create `tests/test_renderers.py` with snapshots/schema assertions, Unicode, commas, quotes, newlines, and ANSI-exclusion checks.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -q`
- `.venv/bin/python -m pytest tests/test_renderers.py -k 'json or csv or ansi' -q`

**Commit:** `step-6: add stable report renderers`

## Step 7: Wire the Complete CLI and Exit Contract

**Goal:** The installed command runs end to end and maps every documented outcome to the stable code.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface”; `PRD.md` FR-P0-10.

**Tasks:**

1. Complete `src/nginx_stream_analyzer/cli.py` with optional input, mutually exclusive `--json`/`--csv`, `--no-color`, `--max-unique`, and `--encoding`.
2. Map success/internal/input/usage-or-no-valid/cardinality outcomes to the complete `0/1/2/3/4` exit-code contract.
3. Ensure code `4` means unique-cardinality exhaustion and emits no normal report.
4. Extend `tests/test_cli.py` for file/stdin parity, stream separation, every option, every exit code, and absence of tracebacks for expected failures.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/nginx-stream-analyzer --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-stream-analyzer --csv tests/fixtures/combined.log | .venv/bin/python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: wire CLI and exit codes`

## Step 8: Add End-to-End Contract Tests

**Goal:** Cross-format metrics, malformed-line behavior, and pipeline behavior are replayable acceptance evidence.

**Time:** ~2 hours

**Context:** `PRD.md` “Acceptance Matrix” and `PROJECT_ARCHITECTURE.md` “CLI Interface”.

**Tasks:**

1. Create `tests/test_end_to_end.py` to compare terminal-visible values, JSON fields, and CSV rows against one hand-calculated fixture.
2. Create `tests/test_exit_codes.py` covering the complete `0/1/2/3/4` contract in separate subprocesses.
3. Create `tests/test_security.py` for terminal markup/control content, CSV quoting, diagnostic redaction, and no network/file writes.
4. Add property-based or generated cases only if they fit the weekend scope; deterministic fixtures remain authoritative.

**Verification:**

- `.venv/bin/python -m pytest tests/test_end_to_end.py tests/test_exit_codes.py tests/test_security.py -q`
- `.venv/bin/python -m pytest --cov=nginx_stream_analyzer --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-8: lock end-to-end behavior`

## Step 9: Prove Performance and Memory Bounds

**Goal:** The selected architecture meets the 1 GB under 30 seconds requirement or produces evidence for an architecture decision.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` “KPIs” and `PROJECT_ARCHITECTURE.md` “Performance and Resource Strategy”.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate a corpus with a recorded seed and expected aggregates.
2. Create `benchmarks/run_benchmark.sh` to record command, Python version, machine, input size/hash, elapsed time, and peak RSS.
3. Create `benchmarks/README.md` with cold/warm-cache protocol and pass threshold.
4. Profile before changing algorithms; record any approved optimization in `PROJECT_ARCHITECTURE.md`.

**Verification:**

- `.venv/bin/python benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-stream-analyzer-1gb.log`
- `benchmarks/run_benchmark.sh /tmp/nginx-stream-analyzer-1gb.log`
- `.venv/bin/python -m pytest -q`

**Commit:** `step-9: verify throughput and memory`

## Step 10: Package and Document the Release Candidate

**Goal:** A clean environment can build, install, run, and understand the CLI without repository knowledge.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` “Definition of Done” and `PROJECT_ARCHITECTURE.md` “Packaging and Deployment”.

**Tasks:**

1. Finalize `README.md` with installation, examples, supported format, output schemas, privacy behavior, and the full exit contract.
2. Add `LICENSE` using an approved open-source license selected by the maintainer.
3. Build source and wheel artifacts through `python -m build`; do not publish in this step.
4. Test the wheel in a new virtual environment and run all acceptance examples.
5. Record benchmark evidence and known limitations in release notes.

**Verification:**

- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m build`
- `python3.11 -m venv /tmp/nginx-stream-analyzer-release-venv && /tmp/nginx-stream-analyzer-release-venv/bin/pip install dist/*.whl`
- `/tmp/nginx-stream-analyzer-release-venv/bin/nginx-stream-analyzer --json tests/fixtures/combined.log`

**Commit:** `step-10: prepare verified release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable foundation and trusted parsing | Friday evening |
| Weekend block 2 | 4–5 | Complete one-pass metric engine | Saturday morning |
| Weekend block 3 | 6–8 | Outputs, CLI, and behavioral evidence | Saturday afternoon–Sunday morning |
| Weekend block 4 | 9–10 | Performance proof and package readiness | Sunday afternoon |

## Cross-Cutting Verification Rules

- Run the focused test after each step and the complete suite before every commit.
- Treat `PRD.md` acceptance criteria as the source of truth; change the specification before intentionally changing behavior.
- Never publish a package, push a commit, or create a release without explicit human confirmation.
- A failing benchmark, red suite, missing exit-code case, or unmeasured performance target blocks completion.
- The release must preserve the complete exit-code contract `0/1/2/3/4`; code `4` always means unique-cardinality exhaustion.

