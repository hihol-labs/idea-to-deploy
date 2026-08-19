# Implementation Plan: Nginx Stream Report

This plan implements the contracts in `PROJECT_ARCHITECTURE.md` and the P0 requirements in `PRD.md`. It contains nine dependency-ordered steps sized for one weekend. Product code is not part of this blueprint; every command below is a future acceptance command for the implementation step.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package, console entry point, and quality configuration | Every later module and check needs a stable import/install boundary | 1.0 h |
| 2 | Domain and output contracts | Parser, aggregator, renderers, and tests must share exact types and schemas | 1.0 h |
| 3 | Fixture/oracle strategy and benchmark profile | Correctness and performance need reproducible evidence before optimization | 1.0 h |

There is no database, auth system, Docker setup, server, or CI/CD infrastructure in the runway because the approved architecture is a local stateless CLI.

## Global Acceptance Contract

Every step must preserve this complete exit-code mapping:

| Code | Meaning |
|---:|---|
| 0 | Success, including a report with malformed lines skipped |
| 1 | Unexpected internal failure or output I/O failure |
| 2 | CLI usage error |
| 3 | Input/read/parse failure, including no valid records |
| 4 | Unique-cardinality exhaustion |

The final candidate is accepted only after the exact staged candidate passes the current Idea to Deploy machine oracle and risk-tier checker, and the resulting adjudication receipt revalidates. Untracked or ignored inputs are excluded unless explicitly declared and content-bound.

## STEP 1: Establish the Installable Package and Quality Gates

**Goal:** A Python 3.11 package builds and exposes the `nginx-report` Click command with help/version behavior.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 7, 11; `PRD.md` FR-01 and NFR-05.

**Tasks:**

1. Create `pyproject.toml` with `src` layout, Python bounds, Click/Rich runtime dependencies, test/lint/type/build extras, and the `nginx-report` entry point.
2. Create `src/nginx_stream_report/__init__.py` with the package version source.
3. Create `src/nginx_stream_report/__main__.py` to invoke the same Click command as the console script.
4. Create `src/nginx_stream_report/cli.py` with the declared command/options and mutually exclusive output validation; leave processing behind injected/called boundaries.
5. Create `tests/test_cli_contract.py` for help, version, invalid `--top`, invalid `--max-unique`, and `--json`/`--csv` exclusivity.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `python3.11 -m nginx_stream_report --help`
- `python3.11 -m build`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Define Domain Models, Errors, and Fixtures

**Goal:** All stages share immutable typed records/results, explicit expected errors, and representative nginx fixtures.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4–7 and 13; `PRD.md` FR-02, FR-08, FR-09.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with frozen/slotted dataclasses for `AccessRecord`, `RankedItem`, `HourlyBucket`, `UserAgentSummary`, and `Report`.
2. Create `src/nginx_stream_report/errors.py` with distinct input, parse/no-valid-record, cardinality-exhaustion, and output failure types plus the 0/1/2/3/4 mapping.
3. Create `tests/fixtures/combined.log` covering IPv4, IPv6, every metric, ties, query strings, and a malformed line.
4. Create `tests/fixtures/all_invalid.log` and a tiny high-cardinality fixture.
5. Create `tests/test_models.py` and `tests/test_exit_codes.py` to freeze dataclass/schema assumptions and all five exit categories.

**Verification:**

- `python3.11 -m pytest tests/test_models.py tests/test_exit_codes.py -q`
- `python3.11 -m mypy src/nginx_stream_report`

**Commit:** `step-2: define models errors and fixtures`

## STEP 3: Implement the Streaming Combined-Log Parser

**Goal:** Buffered file/stdin input yields one `AccessRecord` at a time and counts malformed lines without retaining raw input.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 12; `PRD.md` FR-01 and FR-02.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with a parser compiled once for the documented combined-log grammar.
2. Create `src/nginx_stream_report/input.py` for a non-owning stdin adapter and safely owned file handles.
3. Parse timestamp hour, request target, integer status, client IP, and literal User-Agent into the domain model.
4. Track line number and malformed count without including raw sensitive lines in normal diagnostics.
5. Create `tests/test_parser.py` for valid/invalid bytes, escaping, timestamp/status/request errors, IPv4/IPv6, and one-record-at-a-time iteration.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m ruff check src/nginx_stream_report/parser.py src/nginx_stream_report/input.py tests/test_parser.py`

**Commit:** `step-3: add streaming nginx parser`

## STEP 4: Build Exact Bounded Aggregation

**Goal:** A single pass computes all four metrics with deterministic ranking and fail-closed cardinality guards.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 6, and 12; `PRD.md` FR-03 through FR-06 and FR-09.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with total count, IP/error-URL counters, 24 integer hour buckets, and exact User-Agent set.
2. Enforce `--max-unique` independently for IP, error-URL, and User-Agent keys before accepting a new distinct key.
3. Finalize top lists by descending count then ascending key, respecting `--top`.
4. Calculate hourly percentages using exactly `100 × hourly_request_count / total_valid_requests` and User-Agent share from valid requests only.
5. Create `tests/test_aggregate.py` for formulas, all 24 buckets, tie ordering, no-error input, malformed exclusion, top limits, and each cardinality boundary.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-branch --cov-fail-under=95`

**Commit:** `step-4: implement bounded exact metrics`

## STEP 5: Add Rich Terminal Output

**Goal:** Default invocation emits a readable colored terminal report and safe warnings while preserving metric values.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and sections 9 and 13; `PRD.md` FR-07.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` with a renderer protocol/dispatch boundary.
2. Create `src/nginx_stream_report/renderers/text.py` with summary, two rankings, 24-hour distribution, and User-Agent diversity sections.
3. Escape untrusted URL/User-Agent/control content before Rich rendering.
4. Honor terminal detection and `--no-color`; send malformed warnings to stderr.
5. Create `tests/golden/report.txt` and `tests/test_text_renderer.py` for stable unstyled structure, empty error ranking, rounding, and no markup injection.

**Verification:**

- `python3.11 -m pytest tests/test_text_renderer.py -q`
- `python3.11 -m nginx_stream_report --no-color tests/fixtures/combined.log`

**Commit:** `step-5: add safe Rich terminal report`

## STEP 6: Add JSON and CSV Pipeline Outputs

**Goal:** `--json` and `--csv` emit stable machine-readable equivalents with stdout/stderr separation.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` FR-08.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json.py` for schema version 1 and numeric percentage values.
2. Create `src/nginx_stream_report/renderers/csv.py` with the exact `section,rank,key,count,percentage` header and section discriminators.
3. Wire renderer selection into `src/nginx_stream_report/cli.py` without changing aggregation behavior.
4. Create `tests/golden/report.json` and `tests/golden/report.csv`.
5. Create `tests/test_structured_renderers.py` to validate JSON types/schema, CSV quoting/row semantics, determinism, and absence of ANSI bytes.

**Verification:**

- `python3.11 -m pytest tests/test_structured_renderers.py -q`
- `python3.11 -m nginx_stream_report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `python3.11 -m nginx_stream_report --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add JSON and CSV renderers`

## STEP 7: Complete CLI Integration and Failure Semantics

**Goal:** File/stdin paths, partial warnings, broken output, and fatal errors obey one tested 0/1/2/3/4 contract.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and section 13; `PRD.md` FR-01, FR-09, FR-10.

**Tasks:**

1. Complete orchestration and narrow exception handling in `src/nginx_stream_report/cli.py`.
2. Ensure empty/all-invalid input, unreadable paths, internal/output failures, CLI usage, and cardinality exhaustion map to codes 3, 1, 2, and 4 as specified.
3. Ensure fatal errors emit no partial report and partial success returns 0 with the malformed count on stderr.
4. Create `tests/test_cli_integration.py` for stdin/file equivalence, every mode, exact stdout/stderr ownership, and complete exit codes `0/1/2/3/4`.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py tests/test_exit_codes.py -q`
- `printf '%s\n' 'invalid' | python3.11 -m nginx_stream_report --json; test $? -eq 3`
- `python3.11 -m nginx_stream_report --max-unique 1 tests/fixtures/high_cardinality.log; test $? -eq 4`

**Commit:** `step-7: enforce CLI failure contract`

## STEP 8: Validate Performance and Harden Correctness

**Goal:** The implementation is profiled, optimized only where measured, and demonstrates the 1 GB/30 s target without changing exact semantics.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 12 and 14; `STRATEGIC_PLAN.md` KPIs; `PRD.md` NFR-01 through NFR-04.

**Tasks:**

1. Create `benchmarks/generate_log.py` as a deterministic fixture generator with expected metric metadata and content hash output.
2. Create `benchmarks/run.py` to record fixture identity, hardware/OS/Python profile, elapsed wall time, peak RSS, command, and result-oracle status.
3. Create `tests/test_end_to_end.py` for cross-mode semantic equivalence and stable results on a medium fixture.
4. Profile the parser/aggregator, make only evidence-backed changes in their existing modules, and retain the exact metric contract.
5. Record the benchmark procedure and latest evidence in `benchmarks/README.md`; do not commit a generated 1 GB log.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `python3.11 -m ruff check .`
- `python3.11 -m mypy src/nginx_stream_report benchmarks`
- `python3.11 benchmarks/generate_log.py --size 1GB --output /tmp/nginx-report-benchmark.log`
- `python3.11 benchmarks/run.py --limit-seconds 30 /tmp/nginx-report-benchmark.log`

**Commit:** `step-8: verify correctness and performance`

## STEP 9: Package, Document, and Accept the Release Candidate

**Goal:** A clean environment can install the wheel and obtain correct text, JSON, and CSV reports; documentation matches the delivered interface.

**Time:** ~2 hours

**Context:** All architecture and PRD sections; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Update `README.md` from blueprint status to tested installation, examples, schemas, limitations, and troubleshooting.
2. Create `CHANGELOG.md` with the initial release contract.
3. Create `tests/test_wheel_smoke.py` or an isolated script that installs the built wheel and invokes the real console entry point.
4. Run all quality, security, packaging, and benchmark checks against the frozen candidate.
5. Reconcile `.itd-memory/STATE.json`, record required evidence, and accept only a current exact-candidate adjudication receipt under `.itd/VERIFICATION_CONTRACT.json`.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest -q --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `python3.11 -m pip check`
- `python3.11 -m pip install --force-reinstall dist/*.whl`
- `nginx-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- Run the repository's current Verification Loop freeze, machine oracle, risk-tier checker, and receipt revalidation commands defined by the active Idea to Deploy unit.

**Commit:** `step-9: prepare verified initial release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable runway, contracts, fixtures, and streaming parser | ~4 h |
| Saturday PM | 4–5 | Exact aggregations and default terminal experience | ~3.5 h |
| Sunday AM | 6–7 | Pipeline formats and complete failure semantics | ~3 h |
| Sunday PM | 8–9 | Performance evidence, hardening, packaging, and acceptance | ~5 h |

## Dependencies and Handoff

Steps are WIP=1: begin a step only after its predecessor's stated checks pass and evidence is recorded. The parser precedes aggregation; aggregation precedes every renderer; all feature behavior precedes profiling and release. If the 30-second target fails, remain in Step 8, attach the profile, and choose an evidence-backed recovery rather than advancing or silently relaxing semantics.
