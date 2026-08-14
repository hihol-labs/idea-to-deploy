# Implementation Plan: Nginx Stream Analytics CLI

## Delivery Rules

This plan implements the durable specifications in `PRD.md` and `PROJECT_ARCHITECTURE.md`; a behavior change starts by updating those specifications. Work in dependency order, keep commits independently reviewable, and do not add a database, server, HTTP API, authentication, cloud resources, Docker, or Kubernetes.

Every implementation step preserves the complete exit-code contract: `0` success, `1` input/runtime I/O failure, `2` CLI usage error, `3` strict parse failure, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or collapsed into a generic failure.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python 3.11 package and test skeleton | All modules, CLI tests, and wheel checks require stable package paths | 1 hour |
| 2 | Immutable domain contracts and error taxonomy | Parser, aggregator, renderers, and exit mapping need one vocabulary | 1 hour |
| 3 | Golden fixture corpus | Correctness must be executable before feature growth | 1 hour |
| 4 | Benchmark protocol and marker | Performance is a release constraint, not late polish | 1 hour |

No database schema, authentication system, container environment, or CI deployment infrastructure belongs in the runway because the approved product is a local stateless CLI.

## Step 1: Package, Tooling, and CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the package and invoke a Click command with stable help and version output.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Package and Module Boundaries,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, and the `nginx-stream-report = nginx_stream_report.cli:main` console script.
2. Create `src/nginx_stream_report/__init__.py` containing only package version metadata.
3. Create `src/nginx_stream_report/cli.py` with the documented argument/options, mutual exclusion for `--json`/`--csv`, positive cardinality validation, and placeholder-free orchestration seams.
4. Create `tests/test_cli.py` for help, version, invalid option combinations, and stdin/path selection.
5. Create the lint, type-check, and pytest configuration in `pyproject.toml`.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Domain Models and Error Taxonomy

**Goal:** Parser, aggregation, and rendering boundaries share typed, immutable result contracts and distinct expected failures.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Domain and Data Model” and “Exit Codes.”

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with frozen dataclasses for `LogRecord`, `RankedIP`, `RankedURL`, `HourlyBucket`, `UserAgentStats`, `InputStats`, and `Summary`.
2. Create `src/nginx_stream_report/errors.py` with `InputIOError`, `StrictParseError`, and `UniqueCardinalityError` carrying safe diagnostic context.
3. Extend `tests/test_models.py` to check invariants, tuple-based collections, and JSON-safe primitive conversion boundaries.
4. Update `src/nginx_stream_report/cli.py` to map the error taxonomy to `1/3/4`; leave Click usage validation mapped to 2 and success to 0.

**Verification:**

- `.venv/bin/pytest tests/test_models.py tests/test_cli.py -q`
- `.venv/bin/mypy src/nginx_stream_report`

**Commit:** `step-2: define domain and failure contracts`

## Step 3: Combined-Log Parser and Fixture Corpus

**Goal:** Each conventional nginx combined-format line becomes a validated `LogRecord`, while invalid lines are classified without crashing.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Parsing Contract”; `PRD.md` requirement P0-FR-1.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with a bounded parser for address, timestamp/offset, request triple, status, bytes, referrer, and User-Agent.
2. Create `tests/fixtures/valid_combined.log`, `tests/fixtures/mixed_combined.log`, and `tests/fixtures/invalid_utf8.log` with documented expected counts; fixtures are synthetic test data and never presented as production data.
3. Create `tests/test_parser.py` covering IPv4, IPv6, escaped quotes, `-` bytes, timezone offsets, malformed timestamps, invalid request triples, invalid statuses, blank lines, truncation, and undecodable bytes.
4. Add property/fuzz-style bounded cases that prove arbitrary input produces a record or parse result without unhandled exceptions or pathological delay.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/ruff check src/nginx_stream_report/parser.py tests/test_parser.py`

**Commit:** `step-3: parse nginx combined logs safely`

## Step 4: Streaming Aggregations and Cardinality Guard

**Goal:** One pass computes all four metrics exactly and deterministically within the documented memory policy.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Metrics and Deterministic Ordering,” “Domain and Data Model,” and “Processing Lifecycle.”

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with an `Accumulator` using IP/error-URL counters, 24 hourly integers, and a capped exact User-Agent set.
2. Implement valid/malformed/total accounting and the invariant `total_lines = valid_requests + malformed_lines`.
3. Implement deterministic top-10 tie handling and status filter 400–599.
4. Implement hourly percentages with `100 × hourly_request_count / total_valid_requests` and unique User-Agent share with its specified percentage calculation; handle zero valid requests.
5. Raise `UniqueCardinalityError` as soon as the configured limit would be exceeded.
6. Create `tests/test_aggregate.py` for all metrics, ties, more than 10 keys, zero input, malformed input, status boundaries, timezone hours, precision, and exhaustion at limit+1.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-fail-under=95`

**Commit:** `step-4: implement streaming metrics and cap`

## Step 5: JSON and CSV Pipeline Renderers

**Goal:** Automation receives deterministic, valid, schema-stable JSON or CSV derived from the same `Summary`.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Outputs”; `PRD.md` requirements P0-FR-6 and P0-FR-7.

**Tasks:**

1. Create `src/nginx_stream_report/render_json.py` with schema version `1`, stable keys, UTF-8 output, and no NaN/Infinity values.
2. Create `src/nginx_stream_report/render_csv.py` using `csv.writer` and the exact normalized header/section contract.
3. Create `tests/test_renderers.py` with JSON schema assertions, RFC 4180 quoting cases, deterministic snapshots, and cross-format metric reconciliation.
4. Update `src/nginx_stream_report/cli.py` to select exactly one renderer and keep diagnostics off stdout.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py tests/test_cli.py -q`
- `.venv/bin/nginx-stream-report --json tests/fixtures/valid_combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-5: add JSON and CSV contracts`

## Step 6: Rich Terminal Renderer

**Goal:** Interactive users receive a clear four-section colored report that remains safe and readable without color.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs” and “Security and Privacy”; `PRD.md` requirement P0-FR-5.

**Tasks:**

1. Create `src/nginx_stream_report/render_text.py` with Rich tables for IPs, error URLs, hourly distribution, User-Agent statistics, and the input-quality footer.
2. Escape or disable markup for all log-derived values.
3. Implement TTY-aware color, `--no-color`, and `NO_COLOR` behavior with explicit option precedence.
4. Extend `tests/test_renderers.py` and `tests/test_cli.py` with forced-terminal/no-terminal output, hostile markup strings, empty input, and no-ANSI assertions.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py tests/test_cli.py -q`
- `.venv/bin/nginx-stream-report --no-color tests/fixtures/valid_combined.log`

**Commit:** `step-6: render safe Rich terminal report`

## Step 7: End-to-End Failure and Pipe Semantics

**Goal:** Real file/stdin runs honor the complete output and exit-code contract without partial reports.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Processing Lifecycle,” and “Error and Observability Contract.”

**Tasks:**

1. Complete buffered file/stdin iteration in `src/nginx_stream_report/cli.py`, including ownership and broken-pipe behavior.
2. Ensure unreadable/missing input returns 1, bad options return 2, `--strict` plus malformed input returns 3, and cardinality exhaustion returns 4.
3. Ensure codes 1–4 emit no partial JSON/CSV or terminal report and write concise diagnostics only to stderr.
4. Create `tests/test_integration.py` using Click's runner and subprocess installation smoke cases for paths, stdin, malformed input, read failure, format conflicts, cardinality overflow, and broken pipes.

**Verification:**

- `.venv/bin/pytest tests/test_integration.py tests/test_cli.py -q`
- `.venv/bin/pytest -q --cov=nginx_stream_report --cov-fail-under=90`

**Commit:** `step-7: enforce end-to-end CLI semantics`

## Step 8: Performance, Memory, and Quality Gate

**Goal:** The measured release candidate processes 1 GB under 30 seconds on the documented laptop and fails safely under adversarial cardinality.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Performance Architecture”; `PRD.md` non-functional requirements.

**Tasks:**

1. Create `tests/performance/generate_log.py` to generate a deterministic 1 GB on-disk benchmark corpus outside Git.
2. Create `tests/test_performance.py` with an opt-in `performance` marker, wall-clock measurement, exact result assertions, and peak-RSS capture appropriate to the host OS.
3. Profile `parser.py` and `aggregate.py`; optimize only measured hot paths while preserving domain/output contracts.
4. Create `docs/PERFORMANCE.md` recording hardware, OS, Python patch version, command, corpus parameters, bytes, time, throughput, peak RSS, and result.
5. Run lint, format check, typing, unit/integration tests, packaging validation, and the performance gate against the exact candidate.

**Verification:**

- `.venv/bin/python tests/performance/generate_log.py --bytes 1073741824 --output /tmp/nginx-stream-report-1gb.log`
- `.venv/bin/pytest tests/test_performance.py -m performance --input /tmp/nginx-stream-report-1gb.log -q`
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src && .venv/bin/pytest -q --cov=nginx_stream_report --cov-fail-under=90`

**Commit:** `step-8: prove performance and quality gates`

## Step 9: Packaging, Documentation, and Release Candidate

**Goal:** A clean environment can build, install, understand, and execute the release candidate with stable contracts.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Packaging and Deployment”; all P0 acceptance criteria in `PRD.md`.

**Tasks:**

1. Update `README.md` with actual package name, install command, quick-start examples, output schema links, privacy statement, and complete exit codes.
2. Create `CHANGELOG.md` with the initial contract and `LICENSE` using the selected open-source license.
3. Build sdist/wheel into `dist/`, validate metadata, and install the wheel into a new Python 3.11 virtual environment.
4. Execute every P0 acceptance criterion and record release evidence through the repository's Idea to Deploy verification contract.
5. Confirm generated package contents exclude fixtures, 1 GB corpus, caches, and local environments except intentionally shipped metadata.

**Verification:**

- `.venv/bin/python -m build && .venv/bin/twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-report-smoke && /tmp/nginx-stream-report-smoke/bin/pip install dist/*.whl && /tmp/nginx-stream-report-smoke/bin/nginx-stream-report --version`
- `/tmp/nginx-stream-report-smoke/bin/nginx-stream-report --json tests/fixtures/valid_combined.log`

**Commit:** `step-9: package release candidate`

## Sprint Boundaries

The one-weekend cadence uses focused delivery blocks rather than calendar-week sprints.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable package, contracts, parser | ~7 hours |
| Saturday PM | 4–5 | Four metrics and pipeline formats | ~7 hours |
| Sunday AM | 6–7 | Terminal UX and full failure semantics | ~5 hours |
| Sunday PM | 8–9 | Measured performance and releasable wheel | ~7 hours |

## Dependency and Scope Checkpoints

- Steps 1–3 establish the runway; do not begin renderers before `Summary` and parser behavior are stable.
- Step 4 is the single metric source of truth; renderers must not recalculate metrics.
- Step 7 freezes the public CLI and exit behavior before performance tuning.
- Step 8 may change internals only when output contract tests remain green.
- Gzip input and custom log formats remain P2 and are not inserted into the MVP steps.
- Product code implementation is outside the current blueprint session.

## Completion Evidence

Implementation is complete only when the exact release candidate passes the repository's current verification/adjudication workflow, all P0 acceptance criteria in `PRD.md` have evidence, the documented performance run is current, and the install-from-wheel smoke test succeeds. A narrated or standalone passed claim is not sufficient.
