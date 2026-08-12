# Implementation Plan: nginx-log-report

This is a nine-step, one-weekend delivery plan for the contract in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and priorities in [PRD.md](PRD.md). WIP is one step: a step is accepted only after its checks pass, and later steps may not silently alter an earlier contract.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Freeze CLI, report schema, and exit codes | Parsers, renderers, tests, and docs depend on one contract | 0.5 h |
| 2 | Create Python 3.11 package and test skeleton | Every vertical slice needs import, entry-point, and fixture boundaries | 1.0 h |
| 3 | Establish deterministic fixture generation | Correctness and the 1 GB gate need reproducible inputs | 0.5 h |

No database schema, authentication system, API scaffold, Docker setup, or CI deployment runway exists: those would violate the approved CLI-only, local, $0 architecture.

## Step 1: Freeze Public Contracts and Package Skeleton

**Goal:** A clean environment can install the empty package, invoke both entry points, and see the final help/options contract.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Components and Responsibilities,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python 3.11 metadata, bounded Click/Rich dependencies, pytest tooling, wheel configuration, and `nginx-log-report` console script.
2. Create `src/nginx_log_report/__init__.py`, `src/nginx_log_report/__main__.py`, and `src/nginx_log_report/cli.py` with the documented Click signature.
3. Create `tests/test_cli_contract.py` to freeze help text, option conflicts, version behavior, and module/console parity.
4. Create `tests/fixtures/` and `tests/generate_fixture.py` interfaces without generating or committing a large benchmark artifact.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/python -m pytest tests/test_cli_contract.py -q`
- `.venv/bin/nginx-log-report --help`

**Commit:** `step-1: freeze CLI and packaging contracts`

## Step 2: Implement Typed Combined-Log Parsing

**Goal:** Valid nginx combined lines become typed records one at a time; malformed lines are classified without aggregation or output concerns.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Input contract,” “Components and Responsibilities,” and “Reliability and Security.”

**Tasks:**

1. Create `src/nginx_log_report/models.py` with frozen `LogRecord`, report-row dataclasses, and domain exceptions.
2. Create `src/nginx_log_report/parser.py` with one compiled combined-format parser, IP/status/timestamp/request validation, and request-target extraction.
3. Create `tests/test_parser.py` for IPv4, IPv6, escaped/quoted fields, timezone offsets, error statuses, BOM, blank/malformed input, and hostile terminal markup.
4. Add representative small logs under `tests/fixtures/combined.log` and `tests/fixtures/malformed.log`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_log_report.parser --cov-fail-under=90`

**Commit:** `step-2: parse nginx combined logs`

## Step 3: Implement Single-Pass Aggregation

**Goal:** One pass produces exact top-IP/error-URL counts, 24 hourly buckets, and unique User-Agent statistics without retaining records.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Metric semantics,” “Data and State Model,” and ADR-002.

**Tasks:**

1. Create `src/nginx_log_report/aggregator.py` with counters, a fixed 24-element hour array, User-Agent set, and total/malformed counters.
2. Add deterministic tie-breaking and freeze results into the report dataclasses in `src/nginx_log_report/models.py`.
3. Compute hourly percentages with the exact formula `100 × hourly_request_count / total_valid_requests` and define all percentages as `0.0` when the denominator is zero.
4. Create `tests/test_aggregator.py` covering top-10 truncation, ties, separate 4xx/5xx counts, all 24 hours, empty input, repeated User-Agents, and no raw-record retention.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregator.py -q`
- `.venv/bin/python -m pytest tests/test_aggregator.py --cov=nginx_log_report.aggregator --cov-fail-under=90`

**Commit:** `step-3: aggregate required metrics in one pass`

## Step 4: Wire Streaming Input and Failure Boundaries

**Goal:** The CLI incrementally processes a file or stdin with auditable default/strict malformed-line behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” and “Reliability and Security.”

**Tasks:**

1. Update `src/nginx_log_report/cli.py` to open one explicit input path or use stdin, iterate lines lazily, count skipped malformed lines, and honor `--strict`.
2. Add exception-to-exit mapping without displaying input content or default tracebacks.
3. Create `tests/test_cli_input.py` for file/stdin parity, missing/unreadable input, invalid UTF-8, blank/empty input, default skip behavior, and strict fail-fast behavior.
4. Add an iterator spy test that fails if the implementation uses bulk `read()`/`readlines()`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli_input.py -q`
- `.venv/bin/nginx-log-report --strict tests/fixtures/malformed.log; test $? -eq 3`

**Commit:** `step-4: stream input and map data failures`

## Step 5: Build the Rich Terminal Renderer

**Goal:** Default output is a readable colored report whose complete content remains available without color.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Output contract” and ADR-003.

**Tasks:**

1. Create `src/nginx_log_report/renderers/__init__.py` and `src/nginx_log_report/renderers/terminal.py`.
2. Render summary, top IPs, top error URLs, all hourly buckets, and unique User-Agent count/share with Rich markup interpretation disabled for log-derived values.
3. Implement `--no-color` and terminal auto-detection without changing report values.
4. Create `tests/test_terminal_renderer.py` with plain-text golden output, empty sections, hostile markup, long URLs/User-Agents, and a color-enabled snapshot.

**Verification:**

- `.venv/bin/python -m pytest tests/test_terminal_renderer.py -q`
- `.venv/bin/nginx-log-report --no-color tests/fixtures/combined.log`

**Commit:** `step-5: render safe terminal report`

## Step 6: Build Stable JSON and CSV Renderers

**Goal:** `--json` and `--csv` produce deterministic, ANSI-free, pipeline-safe output from the same report model.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Output contract” and ADR-003.

**Tasks:**

1. Create `src/nginx_log_report/renderers/json.py` with schema version 1 and the exact nested field contract.
2. Create `src/nginx_log_report/renderers/csv.py` using `csv.writer` and the frozen columns/row ordering.
3. Update `src/nginx_log_report/cli.py` to select exactly one renderer and reject `--json --csv` as usage error `2`.
4. Create `tests/test_json_renderer.py`, `tests/test_csv_renderer.py`, and golden files under `tests/golden/` for normal and empty reports.

**Verification:**

- `.venv/bin/python -m pytest tests/test_json_renderer.py tests/test_csv_renderer.py -q`
- `.venv/bin/nginx-log-report --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: Enforce Cardinality and Complete Exit Codes

**Goal:** The public exit-code contract is fully tested, including safe failure when exact User-Agent cardinality exceeds its bound.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Exit-code contract,” ADR-002, and `PRD.md` FR-9/FR-10.

**Tasks:**

1. Update `src/nginx_log_report/aggregator.py` to accept the maximum distinct User-Agent count, allow repeats at the limit, and raise a domain exception before adding a new value over the limit.
2. Update `src/nginx_log_report/cli.py` to validate the option and map exhaustion to `4` with stderr-only diagnosis and no report.
3. Create `tests/test_exit_codes.py` to exercise every code using controlled boundaries, including an injected internal failure for `1`.
4. Confirm exact contract: `0` success; `1` unexpected internal failure; `2` CLI usage error; `3` input/data error; `4` unique-cardinality exhaustion.

**Verification:**

- `.venv/bin/python -m pytest tests/test_exit_codes.py -q`
- `.venv/bin/nginx-log-report --max-unique-user-agents 1 tests/fixtures/two-user-agents.log >/dev/null; test $? -eq 4`

**Commit:** `step-7: enforce cardinality and exit contracts`

## Step 8: Verify Correctness, Security, and Performance

**Goal:** The exact candidate passes the full suite and the documented 1 GB/30 s release gate with measured resource evidence.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance and Resource Model,” “Reliability and Security,” and “Test Architecture.”

**Tasks:**

1. Expand `tests/test_end_to_end.py` to independently calculate expected metrics for a deterministic fixture and compare terminal/JSON/CSV semantics.
2. Complete `tests/generate_fixture.py` with deterministic seed, valid/malformed mix, IPv4/IPv6, statuses, hours, and controlled cardinalities.
3. Create `benchmarks/run_1gb.sh` to generate outside Git, record fixture size/seed, Python/OS/hardware, wall time, and peak RSS, then enforce `<30 s` on the reference laptop.
4. Create `benchmarks/README.md` describing cold/warm-cache protocol and prohibiting benchmark-result claims from smaller fixtures.
5. Run coverage and inspect dependency/security reports; resolve all P0 correctness and critical/high security findings.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_log_report --cov-report=term-missing --cov-fail-under=90`
- `bash benchmarks/run_1gb.sh`
- `.venv/bin/python -m pip check`

**Commit:** `step-8: prove correctness and performance`

## Step 9: Package and Release-Readiness Check

**Goal:** A clean Python 3.11 environment installs built artifacts and reproduces documented examples with no contract drift.

**Time:** ~1.5 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done, `PROJECT_ARCHITECTURE.md` “Packaging and Deployment,” and `README.md`.

**Tasks:**

1. Finalize `README.md`, `LICENSE`, `CHANGELOG.md`, and package metadata in `pyproject.toml`.
2. Create `tests/test_docs_examples.py` or executable examples that validate README JSON/CSV invocations.
3. Build wheel and source distribution into `dist/`, install the wheel into a fresh temporary environment, and test console/module entry points.
4. Reconcile `CLAUDE.md` status and record the reference benchmark evidence before tagging; do not publish from this step without explicit release authorization.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/python -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-log-report-smoke && /tmp/nginx-log-report-smoke/bin/pip install dist/*.whl && /tmp/nginx-log-report-smoke/bin/nginx-log-report --version`

**Commit:** `step-9: prepare installable release candidate`

## Sprint Boundaries

For a one-weekend effort, “sprint” means a bounded work block rather than a multi-week cadence.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Contract runway | 1–2 | Installable skeleton and trusted parser boundary | Friday evening + Saturday morning |
| Core slice | 3–5 | Correct aggregation, streaming, and terminal workflow | Saturday |
| Automation and hardening | 6–8 | Machine formats, complete failures, quality/performance evidence | Sunday morning/afternoon |
| Release handoff | 9 | Clean-install proof and documentation reconciliation | Sunday afternoon |

## Cross-Step Acceptance Contract

Every implementation step must preserve this exact mapping:

| Exit | Meaning |
|---:|---|
| `0` | success |
| `1` | unexpected internal failure |
| `2` | CLI usage error |
| `3` | input/data error |
| `4` | unique-cardinality exhaustion |

Completion also requires the literal hourly percentage formula `100 × hourly_request_count / total_valid_requests`, exact top-10 results, no raw-record retention, no partial report on codes `3`/`4`, and no product code outside the approved single-process CLI architecture.
