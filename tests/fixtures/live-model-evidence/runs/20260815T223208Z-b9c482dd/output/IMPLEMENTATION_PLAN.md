# Implementation Plan: Nginx Stream Analyzer

## Plan Contract

This is an eight-step, one-weekend plan for the architecture in `PROJECT_ARCHITECTURE.md` and P0 scope in `PRD.md`. Preserve WIP=1: complete each step's verification before starting the next. No step may introduce authentication, persistence, an HTTP server, cloud resources, Docker, or Kubernetes.

The required exit-code contract applies throughout: `0` success; `1` unexpected internal error; `2` usage/configuration or input open/read/decode failure; `3` no valid records; `4` unique-cardinality exhaustion. Code `4` specifically means adding another distinct User-Agent would exceed the configured ceiling. Tests and documentation must not omit, remap, or collapse it into code 1 or 2.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and console entry point | Every CLI and clean-install check depends on it | 1.0 h |
| 2 | Domain dataclasses and typed errors | Parser, aggregation, rendering, and exit mapping share these contracts | 1.0 h |
| 3 | Deterministic fixtures and schema assertions | Correctness needs executable examples before feature work | 1.0 h |
| 4 | Benchmark generator and measurement protocol | Performance risk must be exposed before polish | 1.0 h |

## STEP 1: Freeze Contracts and Scaffold the Package

**Goal:** A pip-buildable Python 3.11 package exposes the command and shared contracts, with no analysis behavior yet.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 5, and 9; `PRD.md` P0 requirements and acceptance criteria.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, `src` layout, and the `nginx-stream-analyzer` console script.
2. Create `src/nginx_stream_analyzer/__init__.py` with the package version.
3. Create `src/nginx_stream_analyzer/models.py` for frozen `ValidRequest`, ranked item, hourly bucket, User-Agent summary, diagnostics, and `AnalysisResult` dataclasses.
4. Create `src/nginx_stream_analyzer/errors.py` for typed input, no-valid-record, and unique-cardinality exceptions.
5. Create `src/nginx_stream_analyzer/cli.py` with the Click command/options and placeholder orchestration, keeping output transactional.
6. Create `tests/test_package.py` and minimal fixtures under `tests/fixtures/`.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_package.py -q`
- `nginx-stream-analyzer --help`

**Commit:** `step-1: scaffold package and freeze CLI contracts`

## STEP 2: Implement the Nginx Record Parser

**Goal:** Common and combined log records become validated domain records without naive whitespace splitting.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5, 6, and 8; `PRD.md` US-1.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with compiled grammars for common and combined formats.
2. Parse IPv4/IPv6 remote address text, logged timestamp/offset, request target, status 100–599, and User-Agent semantics (`-` missing, `""` a value).
3. Return a structured invalid-line result without throwing for ordinary malformed records.
4. Add `tests/test_parser.py` covering valid variants, quoting/escaping, invalid timestamp/status/request, blanks, and Unicode.
5. Add representative valid and malformed lines to `tests/fixtures/sample.log`.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_analyzer.parser --cov-fail-under=90`

**Commit:** `step-2: parse supported nginx formats`

## STEP 3: Build Exact Streaming Aggregation

**Goal:** One pass produces deterministic top IPs, error URLs, hourly percentages, and exact User-Agent share with a hard ceiling.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3 and 6; `PRD.md` US-2 through US-5.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with exact IP/error counters, 24 hour buckets, and the User-Agent set.
2. Enforce the ceiling before set insertion and raise the unique-cardinality exception that maps only to exit code 4.
3. Finalize deterministic top-10 lists using count-descending/key-ascending order.
4. Compute hourly percentage exactly as `100 × hourly_request_count / total_valid_requests`; round only at the output-model boundary.
5. Compute User-Agent share as specified in the architecture and preserve observation diagnostics.
6. Add `tests/test_aggregate.py` for ties, status boundaries, offsets, rounding, missing values, empty data, and ceiling N/N+1.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py -k 'cardinality or hourly or deterministic' -q`

**Commit:** `step-3: aggregate exact streaming metrics`

## STEP 4: Integrate File and Stdin Processing

**Goal:** A service streams either a file or stdin, accounts for malformed lines, and never emits partial results on failure.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 5, and 8; `PRD.md` US-1 and US-6.

**Tasks:**

1. Create `src/nginx_stream_analyzer/service.py` to connect line iteration, parsing, aggregation, diagnostics, and finalization.
2. Update `src/nginx_stream_analyzer/cli.py` to open explicit paths read-only or consume stdin.
3. Map open/read/decode failure to 2, zero valid records to 3, ceiling exhaustion to 4, and unexpected failure to 1.
4. Add `tests/test_service.py` and CLI integration fixtures for mixed valid/malformed, empty, missing, unreadable, and invalid-UTF-8 input.

**Verification:**

- `python3.11 -m pytest tests/test_service.py tests/test_cli.py -q`
- `nginx-stream-analyzer tests/fixtures/sample.log >/dev/null; test $? -eq 0`
- `printf 'not nginx\n' | nginx-stream-analyzer - >/dev/null; test $? -eq 3`

**Commit:** `step-4: stream file and stdin through analysis service`

## STEP 5: Implement Terminal, JSON, and CSV Renderers

**Goal:** Three presentation modes expose equivalent values with clean pipeline semantics.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 5 Outputs; `PRD.md` US-6.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` for renderer selection.
2. Create `renderers/terminal.py` with escaped Rich content, four labeled tables, diagnostics, and TTY-aware color.
3. Create `renderers/json_output.py` with the versioned schema and numeric percentages.
4. Create `renderers/csv_output.py` with the stable long-form RFC 4180 schema.
5. Update `cli.py` to enforce `--json`/`--csv` exclusivity and no ANSI in structured modes.
6. Add `tests/test_output_contracts.py` to compare semantic values across modes and assert deterministic ordering.

**Verification:**

- `python3.11 -m pytest tests/test_output_contracts.py tests/test_cli.py -q`
- `nginx-stream-analyzer --json tests/fixtures/sample.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-analyzer --csv tests/fixtures/sample.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-5: add terminal json and csv output contracts`

## STEP 6: Lock Error, Exit, and Security Behavior

**Goal:** Every documented failure is reproducible, stderr-only, and mapped to exactly one exit code.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 Exit Codes and 8; `PRD.md` FR-8 and NFR-4.

**Tasks:**

1. Complete exception handling in `src/nginx_stream_analyzer/cli.py` without broad silent catches.
2. Add terminal-control and Rich-markup payload fixtures to `tests/fixtures/adversarial.log`.
3. Extend `tests/test_cli.py` with isolated assertions for codes `0/1/2/3/4`, empty stdout on failure, diagnostics on stderr, option conflicts, and forced internal failure.
4. Verify code 4 means unique-cardinality exhaustion and is not used for any other condition.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -k 'exit_code or stderr or injection' -q`
- `python3.11 -m pytest -q`

**Commit:** `step-6: lock failure and exit-code behavior`

## STEP 7: Measure and Tune the 1 GB Path

**Goal:** The exact release candidate demonstrates the 1 GB-under-30-seconds target on a recorded laptop profile without correctness shortcuts.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` KPI/risk sections; `PROJECT_ARCHITECTURE.md` sections 6 and 10.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically generate exactly 1,000,000,000 bytes of valid bounded-cardinality combined-format data outside Git.
2. Create `scripts/run_benchmark.py` to report file size, record count, Python/OS/CPU metadata, elapsed monotonic seconds, throughput, and peak RSS.
3. Create `tests/test_performance.py` for a small, CI-safe smoke workload; mark the 1 GB gate as an explicit release benchmark.
4. Profile the single-process path, then optimize only measured hotspots while preserving output-contract tests.
5. Record the named reference laptop result and command in `README.md`; do not claim the target before a real run.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --bytes 1000000000 --output /tmp/nginx-stream-analyzer-1gb.log`
- `python3.11 scripts/run_benchmark.py --max-seconds 30 /tmp/nginx-stream-analyzer-1gb.log`
- `python3.11 -m pytest tests/test_performance.py tests/test_output_contracts.py -q`

**Commit:** `step-7: verify and tune gigabyte streaming target`

## STEP 8: Package and Release-Check

**Goal:** A clean Python 3.11 environment can install the artifact and run every public contract.

**Time:** ~2 hours

**Context:** all architecture sections; `STRATEGIC_PLAN.md` Definition of Done; every P0 acceptance criterion in `PRD.md`.

**Tasks:**

1. Finalize `README.md` installation, examples, schemas, supported formats, limitations, and benchmark provenance.
2. Update `pyproject.toml` with classifiers, license, project URLs, dependency bounds, and build configuration.
3. Create `tests/test_installed_cli.py` for wheel smoke behavior and all output modes.
4. Build wheel/sdist, install the wheel into a clean temporary environment, and run the complete suite.
5. Reconcile documentation against the fixed exit-code contract `0/1/2/3/4`, including code 4 as unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest -q`
- `python3.11 -m venv /tmp/nginx-stream-analyzer-release-venv && /tmp/nginx-stream-analyzer-release-venv/bin/pip install dist/*.whl && /tmp/nginx-stream-analyzer-release-venv/bin/nginx-stream-analyzer --version`

**Commit:** `step-8: package and release-check cli`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–2 | Contracts, package, and correct parsing | Friday evening / Saturday morning |
| Weekend block 2 | 3–4 | Exact metrics and streaming orchestration | Saturday |
| Weekend block 3 | 5–6 | Output modes and complete failure contract | Saturday evening / Sunday morning |
| Weekend block 4 | 7–8 | Measured performance and installable release | Sunday |

## Final Acceptance

The implementation is accepted only when the P0 criteria in `PRD.md` have executable evidence, the wheel smoke test passes, JSON and CSV validate semantically, every exit code `0/1/2/3/4` is exercised, and the exact candidate passes the documented 1 GB benchmark on the recorded laptop. A standalone claim of success is not evidence.

