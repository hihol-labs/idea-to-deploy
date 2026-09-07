# Implementation Plan: nginx-stream-report

## 1. Delivery Rules

This is a future implementation sequence; this blueprint session creates no product code. Execute one step at a time, keep [PRD.md](PRD.md) and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) as the source of truth, and collect the named verification evidence before marking a step complete. When behavior changes, update the specification first.

The process exit-code contract is fixed throughout implementation: `0` success, `1` runtime I/O/output failure, `2` CLI usage error, `3` strict parse/validation failure, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or collapsed into code 1.

## Architectural Runway

| # | Item | Why first | Estimate |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console-script definition | Every smoke test must exercise the installable entry point | 1.0 h |
| 2 | Domain/error boundaries in `models.py` and `errors.py` | Parser, aggregator, CLI, and renderers need one contract | 1.0 h |
| 3 | Fixture and golden-output conventions under `tests/fixtures/` | Prevents output and parser behavior from drifting during feature work | 1.0 h |
| 4 | Benchmark generator contract in `benchmarks/README.md` | Makes the 1 GB / 30 s target measurable before optimization | 0.5 h |

There is intentionally no database schema, authentication runway, Docker setup, CI/CD service, or deployment infrastructure: those would contradict the selected local CLI architecture.

## STEP 1: Package Skeleton and CLI Contract

**Goal:** A Python 3.11 package installs locally and exposes a Click command with complete help, option validation, and exit-code constants.

**Estimate:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Model” and “CLI Interface”; `PRD.md` FR-1, FR-8, FR-9.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, a `src/` layout, and the `nginx-stream-report` console script.
2. Create `src/nginx_stream_report/__init__.py` and `src/nginx_stream_report/__main__.py`.
3. Create `src/nginx_stream_report/cli.py` with the documented arguments/options and mutual-exclusion validation, but keep processing delegated to later modules.
4. Create `src/nginx_stream_report/errors.py` with typed categories and constants for codes `0/1/2/3/4`.
5. Create `tests/test_cli_contract.py` covering help, version, invalid ranges, conflicting output modes, and stdin/path rules.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/pytest tests/test_cli_contract.py -q`

**Commit:** `step-1: establish package and cli contract`

## STEP 2: Typed Models and nginx Parser

**Goal:** Common and combined access-log lines become deterministic `LogRecord` instances, while malformed input yields structured parse failures.

**Estimate:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Invariants” and “Parsing Contract”; `PRD.md` FR-2 and FR-3.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with frozen/slots dataclasses for `LogRecord`, `ParseStats`, `ReportSnapshot`, and runtime configuration.
2. Create `src/nginx_stream_report/parser.py` with anchored, precompiled common/combined patterns and wall-clock-hour extraction.
3. Create `tests/fixtures/access_combined.log`, `tests/fixtures/access_common.log`, and `tests/fixtures/access_malformed.log` with synthetic, non-sensitive examples.
4. Create `tests/test_parser.py` for IPv4/IPv6, request `-`, quotes, status boundaries, blank lines, timestamp hours 00/23, and missing UA sentinel behavior.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/ruff check src/nginx_stream_report/parser.py src/nginx_stream_report/models.py tests/test_parser.py`
- `.venv/bin/mypy src/nginx_stream_report/parser.py src/nginx_stream_report/models.py`

**Commit:** `step-2: parse common and combined nginx records`

## STEP 3: Streaming Input and Parse Policy

**Goal:** Files and stdin are consumed incrementally in a single logical stream, with exact source/line diagnostics and strict/default malformed-line behavior.

**Estimate:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Streaming and Memory Behavior” and “CLI Interface”; `PRD.md` FR-1 and FR-3.

**Tasks:**

1. Create `src/nginx_stream_report/input.py` for buffered binary iteration over ordered paths or stdin.
2. Extend `src/nginx_stream_report/cli.py` to reject duplicate stdin and translate open/read failures to code 1.
3. Create `tests/test_input.py` for empty files, ordered multiple files, stdin, unreadable paths, and no whole-file reads.
4. Extend `tests/test_cli_contract.py` to prove default skip-and-count behavior and strict code 3 behavior with clean stdout.

**Verification:**

- `.venv/bin/pytest tests/test_input.py tests/test_cli_contract.py -q`
- `printf '%s\n' 'malformed' | .venv/bin/nginx-stream-report --strict - >/tmp/nginx-report.out; test $? -eq 3 && test ! -s /tmp/nginx-report.out`

**Commit:** `step-3: stream files and stdin with explicit parse policy`

## STEP 4: Core Aggregations

**Goal:** One pass produces exact IP counts, error-URL counts, 24 hourly buckets, and the exact User-Agent uniqueness ratio.

**Estimate:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Invariants” and “Streaming and Memory Behavior”; `PRD.md` FR-4 through FR-7.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with a mutable stream accumulator and immutable final snapshot.
2. Implement deterministic top-N ordering by count descending and key ascending.
3. Count only status 400–599 for error URLs.
4. Calculate every hourly percentage as `100 × hourly_request_count / total_valid_requests` and the unique-UA share as a percentage.
5. Create `tests/test_aggregate.py` for ties, status boundaries, 24 buckets, combined sources, zero valid requests, and percentage totals/tolerances.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-fail-under=95 -q`

**Commit:** `step-4: compute all streaming report metrics`

## STEP 5: Unique-Cardinality Guard and Failure Atomicity

**Goal:** Exact User-Agent counting stops safely before exceeding its configured distinct-value limit and never emits a partial report.

**Estimate:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` ADR-002 and exit-code table; `PRD.md` FR-7 and NFR-3.

**Tasks:**

1. Extend `src/nginx_stream_report/aggregate.py` to check a new UA before insertion and raise a typed exhaustion error.
2. Extend `src/nginx_stream_report/cli.py` to map that error exclusively to exit code 4 with a concise stderr diagnostic.
3. Create `tests/test_cardinality.py` covering below-limit, exactly-at-limit, first-over-limit, repeated UA, no partial stdout, and exact lowercase diagnostic wording.

**Verification:**

- `.venv/bin/pytest tests/test_cardinality.py -q`
- `.venv/bin/nginx-stream-report --max-unique-user-agents 1 tests/fixtures/two-user-agents.log >/tmp/nginx-report.out; test $? -eq 4 && test ! -s /tmp/nginx-report.out`

**Commit:** `step-5: fail closed on unique cardinality limit`

## STEP 6: Default Rich Terminal Renderer

**Goal:** Successful default execution prints a readable colored terminal report with all four required sections and safe text handling.

**Estimate:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and security boundaries; `PRD.md` FR-8.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` and `terminal.py`.
2. Add deterministic Rich tables for top IPs, error URLs, hourly percentages, and UA summary.
3. Implement auto/forced/disabled color behavior and escape log-derived control/markup sequences.
4. Create `tests/test_terminal_output.py` with fixed-width snapshots for color modes and malicious control characters.

**Verification:**

- `.venv/bin/pytest tests/test_terminal_output.py -q`
- `.venv/bin/nginx-stream-report --no-color tests/fixtures/access_combined.log | grep -F 'Unique User-Agents'`

**Commit:** `step-6: render safe rich terminal report`

## STEP 7: JSON and CSV Pipeline Renderers

**Goal:** `--json` and `--csv` produce deterministic, serializer-backed schemas on stdout with diagnostics isolated to stderr.

**Estimate:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` JSON/CSV output contracts and ADR-003; `PRD.md` FR-9 and FR-10.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json_output.py` with `schema_version: 1` and the documented object shape.
2. Create `src/nginx_stream_report/renderers/csv_output.py` with the long-form header and all metric row types.
3. Neutralize spreadsheet-formula prefixes in CSV text keys without altering terminal/JSON values.
4. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_machine_output.py` for schema, ordering, quoting, precision, and stderr separation.

**Verification:**

- `.venv/bin/pytest tests/test_machine_output.py -q`
- `.venv/bin/nginx-stream-report --json tests/fixtures/access_combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-stream-report --csv tests/fixtures/access_combined.log | .venv/bin/python -c 'import csv,sys; assert next(csv.reader(sys.stdin)) == ["metric","rank","key","count","percentage"]'`

**Commit:** `step-7: add stable json and csv schemas`

## STEP 8: End-to-End Quality and Packaging

**Goal:** All supported flows, all five exit codes, and clean-environment installation are reproducibly verified.

**Estimate:** ~3 hours

**Context:** All architecture sections; `PRD.md` acceptance matrix.

**Tasks:**

1. Create `tests/test_end_to_end.py` covering file/stdin/multiple inputs, three outputs, common/combined, and exit codes `0/1/2/3/4`.
2. Add property-oriented generated cases for counts and top-N tie ordering without adding an unnecessary runtime dependency.
3. Configure coverage, Ruff, and mypy in `pyproject.toml`.
4. Build a wheel and source distribution; install the wheel in a clean temporary Python 3.11 environment.
5. Update `README.md` with observed commands only after they pass.

**Verification:**

- `.venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest --cov=nginx_stream_report --cov-fail-under=90 -q`
- `.venv/bin/python -m build && .venv/bin/twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-report-smoke && /tmp/nginx-stream-report-smoke/bin/pip install dist/*.whl && /tmp/nginx-stream-report-smoke/bin/nginx-stream-report --version`

**Commit:** `step-8: verify package and end-to-end contracts`

## STEP 9: Performance Gate and Release Handoff

**Goal:** The exact release candidate satisfies the declared 1 GiB performance target and has complete reproducible handoff evidence.

**Estimate:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance Plan”; `STRATEGIC_PLAN.md` KPIs and Definition of Done.

**Tasks:**

1. Create `benchmarks/generate_access_log.py` to deterministically stream-generate a 1 GiB non-sensitive fixture with bounded distinct keys.
2. Create `benchmarks/README.md` with hardware, Python, cache-state, input-hash, wall-time, RSS, and expected-summary recording fields.
3. Profile the unmodified baseline; make only evidence-backed optimizations within the selected architecture and rerun correctness tests after each change.
4. Freeze the exact staged candidate, run the `.itd/VERIFICATION_CONTRACT.json` oracle, and obtain the applicable risk-tier adjudication receipt before acceptance.
5. Record benchmark and verification evidence in the project’s canonical `.itd-memory/` state, then prepare the release notes.

**Verification:**

- `.venv/bin/python benchmarks/generate_access_log.py --bytes 1073741824 --output /tmp/nginx-benchmark.log`
- `/usr/bin/time -v .venv/bin/nginx-stream-report --no-color /tmp/nginx-benchmark.log >/tmp/nginx-benchmark-report.txt`
- `.venv/bin/pytest -q`
- Run the project-declared Idea to Deploy verification command for the frozen candidate and revalidate its current adjudication receipt.

**Commit:** `step-9: meet performance gate and prepare release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable boundary, typed parsing, streaming input | ~7 hours |
| Saturday PM | 4–5 | Correct aggregates and bounded cardinality failure | ~4.5 hours |
| Sunday AM | 6–7 | Terminal and pipeline presentation contracts | ~5 hours |
| Sunday PM | 8–9 | Package QA, performance evidence, release handoff | ~6 hours |

## 4. Dependency and Traceability Matrix

| Requirement | Primary steps | Key evidence |
|---|---|---|
| Streaming file/stdin input | 2–3 | Parser/input tests |
| Top IP and error URL metrics | 4 | Aggregate tests and golden output |
| Hourly percentages | 4 | 24-bucket formula tests |
| Unique-UA share and bounded failure | 4–5 | Cardinality boundary tests and code 4 |
| Rich/JSON/CSV | 6–7 | Snapshot and golden schema tests |
| Pip installability | 1, 8 | Clean-wheel smoke test |
| 1 GB under 30 seconds | 9 | Recorded benchmark plus correctness summary |

## 5. Handoff State

At the end of each step, record changed files, exact verification commands/results, risks, and the next step in the active Idea to Deploy state. Do not mark a step complete from prose alone. A failed performance gate leaves Step 9 in recovery, not accepted.
