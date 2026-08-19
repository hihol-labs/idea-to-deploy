# Implementation Plan: nginx-logtop

## Plan Contract

This is an eight-step, one-weekend implementation sequence. It describes future work; this blueprint does not create product code. Steps follow dependencies first and RICE value second. A step is complete only after its listed checks run against the exact candidate and the Idea to Deploy verification evidence is current.

The implementation must preserve this complete exit-code contract in every step that touches the CLI or a failure boundary:

| Code | Required meaning |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Operational I/O/output/internal runtime failure |
| `2` | Invalid CLI usage or option combination |
| `3` | Input/data-format failure, including empty input or no valid records |
| `4` | Unique-cardinality exhaustion while tracking exact User-Agent values |

No implementation step may omit, remap, or reuse code `4`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package skeleton and Python 3.11 tool configuration | Every module and check depends on import/install behavior | 1.0 h |
| 2 | Golden combined-log fixtures and expected metric manifest | Parser and aggregators need a shared executable truth source | 0.5 h |
| 3 | Domain records and typed failure taxonomy | Prevents CLI concerns from leaking into core computation | 0.5 h |
| 4 | Performance fixture generator and benchmark command | Makes the 1 GB constraint testable before late optimization | 0.5 h |

There is intentionally no database schema, auth system, API framework, Docker setup, or CI deployment runway. Those would contradict `PROJECT_ARCHITECTURE.md`.

## Step 1: Package and Verification Skeleton

**Goal:** A clean Python 3.11 environment can install the package, invoke a placeholder Click entry point, and run the empty test suite configuration.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Technology Stack” and “Packaging and Deployment”; `PRD.md` packaging requirements.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11`, Click, Rich, build metadata, console script `nginx-logtop`, pytest settings, coverage settings, and lint/type-check tooling.
2. Create `src/nginx_logtop/__init__.py` with the package version.
3. Create `src/nginx_logtop/cli.py` with the Click command boundary only; do not invent behavior beyond the frozen CLI contract.
4. Create `tests/conftest.py` and `tests/test_package.py` for import, version, help, and installation smoke checks.
5. Create `tests/fixtures/combined_small.log` and `tests/fixtures/combined_expected.json` containing valid, malformed, 4xx, 5xx, tied-count, timezone, query-string, IPv4, IPv6, and User-Agent cases.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/python -m pytest tests/test_package.py -q`
- `.venv/bin/nginx-logtop --help`

**Commit:** `step-1: establish package and verification skeleton`

## Step 2: Domain Models and Combined-Log Parser

**Goal:** Each supported input line becomes an exact `AccessRecord`, while malformed or invalid UTF-8 input is represented by typed data errors without leaking line contents.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and In-Memory State,” “Log Parsing Contract,” and “Error Handling and Security.”

**Tasks:**

1. Create `src/nginx_logtop/models.py` with `AccessRecord`, final report dataclasses, `InputError`, `DataFormatError`, and `UniqueCardinalityExhausted`.
2. Create `src/nginx_logtop/parser.py` with one compiled, anchored Combined Log Format parser and request-target path normalization.
3. Create `tests/test_parser.py` covering quoted fields, `-` markers, IPv4/IPv6 text, status/bytes bounds, timestamp offsets, query removal, bad requests, malformed quotes, blank lines, and strict UTF-8 policy.
4. Update `tests/fixtures/combined_expected.json` only if the specification—not implementation convenience—requires a clarified golden result.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_logtop.parser --cov=nginx_logtop.models --cov-report=term-missing`

**Commit:** `step-2: parse nginx combined log records`

## Step 3: One-Pass Aggregation and Cardinality Guard

**Goal:** A record stream produces all four exact metrics deterministically, and crossing the User-Agent uniqueness ceiling raises the dedicated code-`4` domain failure.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and In-Memory State,” “Log Parsing Contract,” “Output Determinism,” and “Performance and Resource Model.”

**Tasks:**

1. Create `src/nginx_logtop/aggregate.py` with `AggregationState.update()` and `finalize()`.
2. Implement top-IP counts, combined 4xx/5xx path counts, 24 clock-hour counters, and exact User-Agent set tracking in that module.
3. Calculate hourly percentages only as `100 × hourly_request_count / total_valid_requests`; calculate User-Agent share as `100 × distinct_user_agent_count / total_valid_requests`.
4. Apply descending-count/ascending-key tie-breaking and top-ten truncation during finalization.
5. Create `tests/test_aggregate.py` for all metrics, zero buckets, ties, mixed timezone offsets, denominator correctness, and the exact boundary/overflow behavior of `max_unique_user_agents`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py -k 'cardinality or hourly' -q`

**Commit:** `step-3: add exact streaming aggregations`

## Step 4: Streaming Input and Failure Accounting

**Goal:** stdin and ordered file arguments feed records without whole-file buffering; malformed-line and source I/O policies produce enough structured information for exit codes `1`, `3`, and `4`.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Boundaries,” “Log Parsing Contract,” “CLI Interface,” and “Error Handling and Security.”

**Tasks:**

1. Create `src/nginx_logtop/input.py` with context-managed iterators for stdin and regular UTF-8 files, source names, and line numbers.
2. Reject directories/special named inputs, repeated `-`, unreadable paths, and decoding failures according to the architecture contract.
3. Add invalid-line accounting without printing raw line data.
4. Create `tests/test_input.py` for stdin, multiple ordered files, unreadable/missing files, directories, decoding errors, empty streams, mixed valid/invalid streams, and proof that reads are incremental.

**Verification:**

- `.venv/bin/python -m pytest tests/test_input.py -q`
- `.venv/bin/python -m pytest tests/test_input.py -k incremental -q`

**Commit:** `step-4: stream files and stdin safely`

## Step 5: Stable Text, JSON, and CSV Renderers

**Goal:** One finalized report renders as readable colored text or as deterministic, ANSI-free JSON/CSV without recalculating metrics.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Output Determinism”; `PRD.md` output acceptance criteria.

**Tasks:**

1. Create `src/nginx_logtop/renderers/__init__.py` with the renderer protocol/selection boundary.
2. Create `src/nginx_logtop/renderers/text.py` with Rich summary and four report sections; escape all log-derived markup.
3. Create `src/nginx_logtop/renderers/json.py` with the versioned JSON schema and terminal newline.
4. Create `src/nginx_logtop/renderers/csv.py` with the exact `section,rank,key,count,percentage` schema.
5. Create `tests/test_renderers.py` and golden files under `tests/fixtures/expected/` for no-color text, JSON, and CSV, including escaping and terminal-width independence.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -q`
- `.venv/bin/python -m pytest tests/test_renderers.py -k 'json or csv or ansi or escape' -q`

**Commit:** `step-5: render deterministic text json and csv`

## Step 6: Complete CLI and Exit-Code Contract

**Goal:** The installed command implements all documented options, preserves stdout/stderr separation, and maps every documented result to exactly `0/1/2/3/4`.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` exact `## CLI Interface` section.

**Tasks:**

1. Complete `src/nginx_logtop/cli.py` to compose input, parser, aggregator, and one renderer.
2. Implement `--json`, `--csv`, `--color/--no-color`, `--max-unique-user-agents`, `--version`, file inputs, and stdin default.
3. Centralize mappings: `0` success/help/version, `1` operational I/O/output/internal failure, `2` usage failure, `3` input/data-format/no-valid-record failure, and `4` unique-cardinality exhaustion.
4. Handle broken downstream pipes as documented while keeping other output failures at `1`.
5. Create `tests/test_cli.py` with Click's isolated runner and subprocess coverage for stdout, stderr, each option combination, and every exit code, explicitly forcing the cardinality ceiling to prove `4`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/python -m pytest tests/test_cli.py -k 'exit_code or cardinality' -q`
- `.venv/bin/nginx-logtop --json tests/fixtures/combined_small.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: integrate cli and exit semantics`

## Step 7: Performance, Robustness, and Quality Gates

**Goal:** The exact release candidate meets the 1 GB / 30 s target on the recorded reference laptop and passes correctness, coverage, lint, type, and security-oriented input tests.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Performance and Resource Model” and “Error Handling and Security”; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Create `tests/tools/generate_benchmark_log.py` to deterministically generate a valid 1 GB fixture outside Git with known aggregate answers and bounded cardinality.
2. Create `tests/test_performance.py` as a separately marked smoke/performance check; keep the 1 GB release measurement out of routine unit tests.
3. Create `docs/BENCHMARK.md` recording fixture seed/size, reference hardware, Python version, command, wall time, peak RSS, and known-answer validation.
4. Profile before changing `src/nginx_logtop/parser.py` or `aggregate.py`; preserve golden outputs after any optimization.
5. Add tests for very long fields, Rich markup payloads, huge query strings, all-malformed input, and ceiling exhaustion.

**Verification:**

- `.venv/bin/python -m pytest -q --cov=nginx_logtop --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m mypy src/nginx_logtop`
- `/usr/bin/time -v .venv/bin/nginx-logtop --json /absolute/path/to/generated-1gb.log > /tmp/nginx-logtop-benchmark.json`

**Commit:** `step-7: prove correctness robustness and performance`

## Step 8: Packaging and Release Handoff

**Goal:** A clean Python 3.11 environment can build, install, run, and understand the release artifact, with documentation matching the tested interfaces.

**Time:** ~1.5 hours

**Context:** all blueprint documents; especially `README.md`, `CLAUDE_CODE_GUIDE.md`, and the Definition of Done.

**Tasks:**

1. Finalize `README.md` quick start, input grammar, examples, output schemas, exit codes, performance-method disclaimer, and privacy statement.
2. Add `LICENSE` and package metadata/files required for source and wheel distributions.
3. Build distributions into `dist/` and inspect their contents; do not publish without a separate explicit release authorization.
4. Install the wheel into a fresh virtual environment and run terminal, JSON, CSV, and code-`4` cardinality smoke cases.
5. Reconcile Idea to Deploy state, exact-candidate verification, and handoff evidence.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/python -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-logtop-release-venv && /tmp/nginx-logtop-release-venv/bin/pip install dist/*.whl`
- `/tmp/nginx-logtop-release-venv/bin/nginx-logtop --json tests/fixtures/combined_small.log`

**Commit:** `step-8: prepare verified release artifact`

## Weekend Boundaries

| Boundary | Steps | Goal | Duration |
|---|---|---|---|
| Saturday foundation | 1–3 | Installable skeleton, parser, all metric calculations | ~5 h |
| Saturday integration | 4–5 | Streaming sources and all presentations | ~3.5 h |
| Sunday acceptance | 6–8 | CLI contract, benchmark, package handoff | ~6 h |

## Traceability

| Requirement | Primary implementation steps | Evidence |
|---|---|---|
| Stream nginx logs locally | 2, 4, 6 | parser/input/CLI integration tests |
| Top-10 IP and error URL metrics | 3, 5 | aggregate and golden renderer tests |
| Hourly percentage formula | 3 | denominator-focused unit tests |
| Unique User-Agent share and exhaustion | 3, 6 | aggregation boundary test plus CLI exit `4` test |
| Colored text, JSON, CSV | 5, 6 | golden output and CLI tests |
| 1 GB under 30 seconds | 7 | benchmark log and machine record |
| pip installation | 1, 8 | clean-environment wheel smoke test |
