# Implementation Plan: nginx-report

## 1. Delivery Rules

This plan implements the spec in `PRD.md` using the architecture in `PROJECT_ARCHITECTURE.md`. It creates product code only in a later implementation session. Keep one active step at a time, add tests with each behavior, and do not add a database, API, server, authentication, cloud resources, or Kubernetes.

Every step must preserve the complete exit-code contract: `0` success (including empty input), `1` I/O or unexpected runtime failure, `2` CLI usage error, `3` non-empty input with zero valid requests, and `4` unique-cardinality exhaustion. Code `4` must never be omitted, remapped, or replaced by an approximate result.

## 2. Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and test skeleton | Makes every later behavior installable and executable | 1.0 h |
| 2 | Immutable data contracts | Keeps parser, aggregator, and renderers decoupled | 0.5 h |
| 3 | Representative fixtures and benchmark shape | Establishes correctness and performance evidence before optimization | 0.5 h |

No database schema, authentication system, Docker environment, CI deployment, or network infrastructure belongs in the runway because the product is a local stateless CLI.

## STEP 1: Establish Packaging and Contract Tests

**Goal:** A Python 3.11 package builds, installs, and exposes a placeholder-free `nginx-report` command contract ready for behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 4, 7, and 11; `PRD.md` FR-10.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build, test, coverage, lint, and console-script metadata.
2. Create `src/nginx_report/__init__.py` with the package version.
3. Create `src/nginx_report/cli.py` with Click options matching the normative CLI table, without implementing fake report data.
4. Create `tests/test_cli.py` for help/version, incompatible formats, range validation, and initial usage exit `2` behavior.
5. Create `tests/fixtures/` and document that fixtures are test data, never production evidence.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-report --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Define Domain Models and Combined-log Parser

**Goal:** Individual combined-format lines become typed records or explicit invalid results without retaining input.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 6; `PRD.md` FR-1, FR-2.

**Tasks:**

1. Create `src/nginx_report/models.py` with immutable `LogRecord`, `RankedRow`, `HourlyRow`, and `Report` dataclasses.
2. Create `src/nginx_report/parser.py` with one-time parser initialization, timestamp/status/request validation, `-` User-Agent handling, and 1 MiB line limit.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` containing small, explicitly synthetic cases.
4. Create `tests/test_parser.py` covering IPv4/IPv6, query strings, timezone offsets, escapes, malformed lines, status bounds, and overlong input.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/python -m compileall -q src/nginx_report`

**Commit:** `step-2: parse nginx combined records`

## STEP 3: Implement Exact Streaming Aggregation

**Goal:** One pass over parsed records produces exact counters, hourly percentages, and User-Agent share with bounded failure behavior.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 2, 5, 6, and 10; `PRD.md` FR-3 through FR-6 and FR-9.

**Tasks:**

1. Create `src/nginx_report/aggregate.py` with total/valid/invalid counters, IP/error-target counters, 24 UTC buckets, and the User-Agent set.
2. Enforce `--max-unique` independently before adding new IP, error-target, or User-Agent keys; raise a typed exhaustion error mapped later to `4`.
3. Build deterministic top rows using count descending and key ascending.
4. Compute hourly percentages with exactly `100 × hourly_request_count / total_valid_requests` and unique share with the PRD formula.
5. Create `tests/test_aggregate.py` covering ties, statuses, UTC normalization, zero totals, malformed accounting, alternate top-N, and every cardinality dimension.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_parser.py tests/test_aggregate.py --cov=nginx_report --cov-fail-under=90`

**Commit:** `step-3: add exact streaming metrics`

## STEP 4: Add Stable JSON and CSV Renderers

**Goal:** Pipeline consumers receive deterministic, ANSI-free JSON or normalized CSV without metric recomputation.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 7 Output Contracts; `PRD.md` US-3, US-4, FR-7.

**Tasks:**

1. Create `src/nginx_report/renderers/__init__.py` with a small renderer protocol/type alias.
2. Create `src/nginx_report/renderers/json.py` implementing schema version 1 and 24 ordered hour rows.
3. Create `src/nginx_report/renderers/csv.py` implementing `section,rank,key,count,percentage` through the standard CSV writer.
4. Create `tests/test_render_json.py`, `tests/test_render_csv.py`, and golden files under `tests/fixtures/expected/`.

**Verification:**

- `.venv/bin/pytest tests/test_render_json.py tests/test_render_csv.py -q`
- `.venv/bin/python -c "import json; json.load(open('tests/fixtures/expected/report.json'))"`

**Commit:** `step-4: add stable machine renderers`

## STEP 5: Add Rich Terminal Renderer

**Goal:** Interactive users receive a concise colored report while redirected output remains clean.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 7 and 9; `PRD.md` US-1 and US-8.

**Tasks:**

1. Create `src/nginx_report/renderers/text.py` with summary, ranked, hourly, and User-Agent sections.
2. Escape all log-derived Rich markup and format percentages to two decimals.
3. Respect TTY detection, `--no-color`, and `NO_COLOR` without changing report data.
4. Create `tests/test_render_text.py` for section presence, escaping, empty tables, and ANSI behavior.

**Verification:**

- `.venv/bin/pytest tests/test_render_text.py -q`
- `.venv/bin/nginx-report tests/fixtures/combined.log --no-color | .venv/bin/python -c "import sys; assert '\\x1b[' not in sys.stdin.read()"`

**Commit:** `step-5: add safe terminal report`

## STEP 6: Integrate Streams, Diagnostics, and Exit Codes

**Goal:** The installed command implements file/stdin parity, atomic report output, stderr policy, and the full process contract.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 7; `PRD.md` US-2, US-5, US-6 and section 8.

**Tasks:**

1. Complete `src/nginx_report/cli.py` to select input and renderer, stream records, and delay stdout report emission until successful aggregation.
2. Map success to `0`, I/O/runtime failures to `1`, Click usage to `2`, non-empty zero-valid parse failure to `3`, and unique-cardinality exhaustion to `4`.
3. Ensure all nonzero exits leave stdout empty and concise diagnostics on stderr; suppress tracebacks for expected failures.
4. Extend `tests/test_cli.py` with file/stdin parity, empty input, partial-invalid success, all-invalid parsing failure, broken input/output, and explicit tests for `0/1/2/3/4`.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py -q`
- `.venv/bin/pytest -q --cov=nginx_report --cov-fail-under=90`

**Commit:** `step-6: integrate streams and exit semantics`

## STEP 7: Verify Performance and Memory Safety

**Goal:** Evidence demonstrates the 1 GB target and documents its hardware/input context; pathological cardinality fails safely.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 10; `PRD.md` NFR-1 through NFR-3.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically generate synthetic combined-format data with declared cardinalities and exact byte target.
2. Create `tests/test_performance.py` as an opt-in smoke/benchmark harness, excluded from ordinary unit runs.
3. Create `docs/PERFORMANCE.md` recording hardware, OS, Python, command, input size/cardinality, wall time, CPU time, and peak RSS.
4. Profile parser/aggregation hot paths if the target misses; optimize only measured bottlenecks without changing schemas.
5. Run a separate tiny-limit cardinality case and assert exit `4` with empty stdout.

**Verification:**

- `.venv/bin/python scripts/generate_benchmark_log.py --size-gib 1 --output /tmp/nginx-report-1g.log`
- `/usr/bin/time -v .venv/bin/nginx-report --json /tmp/nginx-report-1g.log > /dev/null`
- `.venv/bin/pytest tests/test_performance.py -m performance -q`

**Commit:** `step-7: verify throughput and memory bounds`

## STEP 8: Harden Quality and Packaging

**Goal:** A clean wheel installs and behaves consistently on the supported interpreter.

**Time:** ~1.5 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` release acceptance.

**Tasks:**

1. Add lint/type configuration in `pyproject.toml` and resolve findings without weakening checks.
2. Add package include/exclude metadata and license notices.
3. Create a package smoke test that builds a wheel, installs it into a fresh Python 3.11 venv, and invokes a fixture through file and stdin.
4. Audit runtime dependencies and ensure no telemetry/network behavior is introduced.

**Verification:**

- `.venv/bin/ruff check src tests scripts`
- `.venv/bin/mypy src/nginx_report`
- `.venv/bin/python -m build && .venv/bin/twine check dist/*`
- `python3.11 -m venv /tmp/nginx-report-smoke && /tmp/nginx-report-smoke/bin/pip install dist/*.whl && /tmp/nginx-report-smoke/bin/nginx-report --help`

**Commit:** `step-8: harden package quality`

## STEP 9: Reconcile Documentation and Release Evidence

**Goal:** Specs, user instructions, schemas, tests, and benchmark evidence describe the same releasable behavior.

**Time:** ~1 hour

**Context:** All blueprint documents and the Definition of Done.

**Tasks:**

1. Update `README.md` with verified install, examples, schemas, supported input, metric definitions, and exit codes.
2. Reconcile any behavior change back into `PRD.md` and `PROJECT_ARCHITECTURE.md` before release.
3. Confirm `CLAUDE.md` step status and record verification commands/evidence through the repository's Idea to Deploy state workflow.
4. Run the complete suite and fresh-install smoke test against the exact release candidate.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_report --cov-fail-under=90`
- `.venv/bin/ruff check src tests scripts && .venv/bin/mypy src/nginx_report`
- `.venv/bin/python -m build && .venv/bin/twine check dist/*`
- `test -s STRATEGIC_PLAN.md && test -s PROJECT_ARCHITECTURE.md && test -s PRD.md && test -s IMPLEMENTATION_PLAN.md && test -s CLAUDE_CODE_GUIDE.md && test -s CLAUDE.md`

**Commit:** `step-9: reconcile release documentation`

## 3. Weekend Boundaries

| Boundary | Steps | Goal | Planned duration |
|---|---|---|---:|
| Saturday AM | 1–2 | Installable contract and parser | 3.5 h |
| Saturday PM | 3–4 | Exact metrics and machine formats | 4.0 h |
| Sunday AM | 5–6 | Terminal UX and end-to-end behavior | 3.5 h |
| Sunday PM | 7–9 | Performance, packaging, release evidence | 4.5 h |

Total planned effort is approximately 15.5 hours. If time compresses, preserve every P0 requirement and defer P1 polish before weakening correctness, schemas, exit semantics, or performance evidence.

## 4. Completion Gate

Completion requires current evidence from the exact candidate: full tests and coverage, lint/type checks, wheel validation and fresh install, representative performance/RSS measurement, machine-output golden tests, and explicit end-to-end coverage of exit codes `0/1/2/3/4`. A narrated or partial pass is not sufficient.
