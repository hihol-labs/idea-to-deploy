# Implementation Plan: nginx-stream-report

## 1. Delivery Rules

- Scope is the P0 MVP in `PRD.md`; gzip and configurable top-N remain deferred.
- Follow the architecture and schemas in `PROJECT_ARCHITECTURE.md`.
- Add tests with each behavior, then run the step verification before committing.
- Never add a database, HTTP service, authentication, cloud resource, Docker, or Kubernetes.
- Preserve the complete exit-code contract `0/1/2/3/4`: `0` success, `1` input/I/O/decoding or unexpected runtime failure, `2` usage error, `3` strict parse failure, `4` unique-cardinality exhaustion.

## 2. Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and console entry point | Every CLI and install test depends on import/install structure | 1 hour |
| 2 | Golden combined-log fixtures and schemas | Freeze expected semantics before implementation | 1 hour |
| 3 | Typed domain/error model | Keeps parser, aggregator, renderers, and exit mapping independent | 1 hour |
| 4 | Benchmark harness | Detects performance regression while changes are still small | 1 hour |

## STEP 1: Freeze package and CLI contracts

**Goal:** An installable skeleton exposes help/version and the stable options without processing data.  
**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 6, 10; `PRD.md` FR-7.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11 metadata, Click/Rich dependencies, pytest tooling, `src` layout, and console script.
2. Create `src/nginx_stream_report/__init__.py` with the package version.
3. Create `src/nginx_stream_report/cli.py` with the Click command and option declarations only.
4. Create `tests/test_cli.py` covering help, version, incompatible flags, invalid caps, and the no-input stdin rule.

**Verification:**

- `python3.11 -m pip install -e .`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-report --help`

**Commit:** `step-1: freeze package and CLI contracts`

## STEP 2: Define models, fixtures, and errors

**Goal:** Typed records, snapshots, and failure categories encode the documented contract.  
**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 7, 8.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with the five documented dataclass/state types.
2. Create `src/nginx_stream_report/errors.py` with input, strict-parse, and cardinality exceptions carrying sanitized context.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/edge_cases.log` without secrets.
4. Extend `tests/test_cli.py` with parameterized expectations for exit codes `0/1/2/3/4` at the command boundary.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m compileall -q src`

**Commit:** `step-2: define report models and failure taxonomy`

## STEP 3: Implement the combined-log parser

**Goal:** Each valid combined-format line becomes one timezone-aware `ParsedRequest`; malformed records are explicit.  
**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 5; `PRD.md` FR-1.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with a whole-line parser and bounded error excerpts.
2. Create `tests/test_parser.py` for IPv4/IPv6-like addresses, quoted fields, missing UA, timezone offsets, boundary statuses, blanks, invalid dates, and control characters.
3. Ensure the parser neither prints nor retains input and avoids catastrophic-backtracking patterns.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py -q --durations=10`

**Commit:** `step-3: parse nginx combined records safely`

## STEP 4: Build one-pass aggregation

**Goal:** One stream produces all four exact metrics with deterministic ordering and a guarded UA set.  
**Time:** ~4 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 2, 4, 8; `PRD.md` FR-2 through FR-5.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with totals, IP/error-URL counters, 24 hourly counters, and unique-UA cap enforcement.
2. Create `tests/test_aggregate.py` for top-ten ties, error boundaries, all 24 buckets, zero-valid input, percentage formulas, repeated UAs, cap boundary, and cap exhaustion.
3. Verify hourly percentages use `100 × hourly_request_count / total_valid_requests` and are rounded only by renderers.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_parser.py tests/test_aggregate.py -q`

**Commit:** `step-4: aggregate four reports in one pass`

## STEP 5: Implement terminal, JSON, and CSV renderers

**Goal:** The same immutable snapshot renders consistently for humans and pipelines.  
**Time:** ~4 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 7; `PRD.md` FR-6.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` with renderer selection boundaries.
2. Create `src/nginx_stream_report/renderers/terminal.py` with Rich summary/tables and escaped log-derived values.
3. Create `src/nginx_stream_report/renderers/json.py` with schema version 1.
4. Create `src/nginx_stream_report/renderers/csv.py` with `section,key,count,percentage` rows.
5. Create `tests/test_renderers.py` for schema, order, escaping, 24 hour rows, empty rankings, and absence of ANSI in machine modes.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest tests/test_aggregate.py tests/test_renderers.py -q`

**Commit:** `step-5: render stable terminal JSON and CSV reports`

## STEP 6: Wire streaming I/O and exit behavior

**Goal:** File/stdin streams flow through parser, aggregator, and renderer with clean stdout/stderr and exact failure mapping.  
**Time:** ~4 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 5, 6, 8; `PRD.md` FR-1 and FR-7.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` with context-managed file iteration, tolerant/strict parsing, renderer choice, and centralized exception mapping.
2. Extend `tests/test_cli.py` for multiple files, stdin, malformed summaries, unreadable/invalid UTF-8 input, broken output behavior, no partial failure output, and all exit codes.
3. Confirm code `4` exclusively represents unique-cardinality exhaustion and is never remapped.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-6: connect streaming CLI and exit contracts`

## STEP 7: Prove performance and resource behavior

**Goal:** The documented reference run processes 1 GB in under 30 seconds and resource scaling is recorded.  
**Time:** ~3 hours  
**Context:** `STRATEGIC_PLAN.md` success metrics; `PRD.md` non-functional requirements.

**Tasks:**

1. Create `tests/generate_benchmark_log.py` to deterministically generate a non-secret combined-format fixture outside Git.
2. Create `tests/test_performance.py` for smaller CI-safe regression thresholds and streaming memory assertions.
3. Add `docs/BENCHMARK.md` recording CPU, RAM, OS, Python version, command, input characteristics, wall time, peak RSS, and result.
4. Profile only if the target fails; optimize measured hotspots without changing schemas or metric semantics.

**Verification:**

- `python3.11 tests/generate_benchmark_log.py --bytes 1073741824 --output /tmp/nginx-stream-report-1gb.log`
- `/usr/bin/time -v nginx-stream-report --json /tmp/nginx-stream-report-1gb.log > /tmp/nginx-stream-report.json`
- `python3.11 -m pytest tests/test_performance.py -q`

**Commit:** `step-7: validate throughput and memory bounds`

## STEP 8: Release-quality verification and documentation

**Goal:** A clean Python 3.11 environment can install, run, test, and understand the MVP.  
**Time:** ~3 hours  
**Context:** All blueprint documents; especially `PRD.md` release acceptance.

**Tasks:**

1. Update `README.md` with installation, examples, schemas, exit codes, input format, limitations, and benchmark link.
2. Add `LICENSE` after selecting a permissive license and add `CHANGELOG.md` for the initial release contract.
3. Run the full suite from a clean virtual environment and inspect terminal, JSON, and CSV golden outputs.
4. Reconcile code/help/docs so the complete `0/1/2/3/4` mapping is identical everywhere.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 -m build`
- `python3.11 -m pip install --force-reinstall dist/*.whl`
- `printf '%s\n' '127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET / HTTP/1.1" 200 1 "-" "curl/8"' | nginx-stream-report --json -`

**Commit:** `step-8: verify and document MVP release`

## 3. Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Contracts, domain model, and parsing | ~7 hours |
| Saturday PM | 4 | Correct streaming aggregation | ~4 hours |
| Sunday AM | 5–6 | Outputs and end-to-end CLI | ~8 hours |
| Sunday PM | 7–8 | Performance evidence and release readiness | ~6 hours |

## 4. Deferred Work

After MVP acceptance, evaluate P1 gzip input using the existing line-iterator boundary. P2 configurable top-N requires explicit schema/help compatibility review. Persistent storage, HTTP/API service, auth, cloud, and Kubernetes remain out of scope rather than backlog items.

