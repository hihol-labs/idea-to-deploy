# Implementation Plan: StreamSift

## 1. Delivery Rules

This plan implements the contracts in `PRD.md` and `PROJECT_ARCHITECTURE.md` without adding a database, service, network call, or product code outside the documented single-process CLI. Work in order and keep one active step at a time. Each step ends only when its listed checks pass and its documentation implications are reconciled.

The complete process contract used by every step is:

| Exit | Meaning |
|---:|---|
| `0` | Successful analysis with complete output |
| `1` | Input/output runtime failure |
| `2` | CLI usage/validation error |
| `3` | Log-data failure: strict malformed record or no valid requests |
| `4` | Unique-cardinality exhaustion |

## 2. Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package skeleton and Python 3.11 tooling | Every test and command needs an installable entry point | 1.0 h |
| 2 | Typed result and error contracts | Parser, aggregator, CLI, and renderers must agree | 1.0 h |
| 3 | Golden log/output fixtures | Prevents implementation from inventing ambiguous semantics | 1.0 h |
| 4 | Benchmark protocol | Performance must be designed in, not asserted at the end | 0.5 h |

No database schema, API, authentication, Docker, or deployment infrastructure belongs in the runway.

## STEP 1: Package, Contracts, and CLI Shell

**Goal:** a pip-installable Python 3.11 package exposes `streamsift`, help/version work, formats are mutually exclusive, and canonical exit constants exist.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Module and File Boundaries” and “CLI Interface”; `PRD.md` FR-1, FR-7, FR-9.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, console script, pytest, coverage, and lint configuration.
2. Create `src/streamsift/__init__.py`, `src/streamsift/__main__.py`, and `src/streamsift/errors.py`.
3. Create `src/streamsift/cli.py` with argument/option declarations only; map Click validation to exit `2`.
4. Create `tests/test_cli.py` cases for help, version, conflicting `--json --csv`, and invalid cardinality.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `streamsift --help`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Parser and Input Adapters

**Goal:** file and stdin iterators produce typed `AccessRecord` values from the documented grammar without retaining input.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and State” and “Parsing and Failure Policy”; `PRD.md` FR-1, FR-2, FR-10.

**Tasks:**

1. Create `src/streamsift/model.py` with typed record/result dataclasses.
2. Create `src/streamsift/parser.py` with once-compiled parsing machinery and timestamp-offset handling.
3. Create `tests/fixtures/basic.log`, `malformed.log`, and `empty.log` with hand-verifiable data.
4. Create `tests/test_parser.py` covering quoted fields, `-` User-Agent, query strings, invalid status/timestamp/request, UTF-8 replacement, blank lines, and line-number diagnostics.
5. Wire read-only buffered file/stdin selection in `cli.py`; map I/O failures to `1` and strict/no-valid-data failures to `3`.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_cli.py -q`
- `printf '%s\n' 'malformed' | streamsift --strict - >/dev/null; test $? -eq 3`

**Commit:** `step-2: parse nginx input streams`

## STEP 3: Streaming Aggregation and Cardinality Guard

**Goal:** a single pass produces exact integer state for all four metrics and aborts before aggregate distinct-key state exceeds its cap.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Model and Data Flow” and “Metric Semantics”; `PRD.md` US-1 through US-4 and US-6.

**Tasks:**

1. Create `src/streamsift/aggregate.py` with IP/error-URL counters, a fixed 24-element hour array, a User-Agent set, and one insertion-budget guard.
2. Finalize top 10 using count-descending/key-ascending ordering.
3. Calculate hourly percentages from `100 × hourly_request_count / total_valid_requests` after EOF, without rounding internal state.
4. Calculate exact nonempty unique User-Agent count/share after EOF.
5. Create `tests/test_aggregate.py` for filtering, repeated agents, all buckets, ties, query-string identity, invariants, and pre-insertion cardinality exit `4`.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=streamsift.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-3: implement bounded streaming metrics`

## STEP 4: Rich Terminal Renderer

**Goal:** the default human report displays four clear sections, counts, and diagnostics with safe TTY-aware color.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and “Packaging, Security, and Deployment”; `PRD.md` US-1 through US-4.

**Tasks:**

1. Create `src/streamsift/render.py` and implement a Rich renderer for ranked tables, all hourly buckets, and User-Agent summary.
2. Escape untrusted fields so Rich markup and control sequences cannot alter the report.
3. Implement `--color/--no-color` and automatic non-TTY suppression.
4. Extend `tests/test_cli.py` with terminal golden output, malicious field text, TTY/non-TTY, malformed count, and stdout/stderr separation.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q -k 'terminal or color or escape'`
- `streamsift --no-color tests/fixtures/basic.log`

**Commit:** `step-4: render safe terminal summaries`

## STEP 5: JSON and CSV Pipeline Renderers

**Goal:** both pipeline modes exactly implement their versioned schemas and never mix diagnostics or ANSI codes into stdout.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and “Output Compatibility”; `PRD.md` US-5.

**Tasks:**

1. Add JSON serialization with `schema_version: 1`, stable keys, all 24 hours, and numeric percentages.
2. Add CSV serialization using `csv` with `metric,dimension,count,percentage` and the four metric discriminators.
3. Ensure write/broken-pipe failures map to exit `1`; no error path emits a complete-looking partial payload.
4. Add `tests/fixtures/expected-basic.json` and `expected-basic.csv` plus parse/round-trip, escaping, encoding, and stderr-separation tests.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q -k 'json or csv or stdout or broken_pipe'`
- `streamsift --json tests/fixtures/basic.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable pipeline formats`

## STEP 6: End-to-End Failure and Contract Matrix

**Goal:** every supported input source, mode, and failure yields exactly the documented output and complete `0/1/2/3/4` exit contract.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Exit Codes”; `PRD.md` sections “Input, Output, and Exit Contract” and “Release Criteria”.

**Tasks:**

1. Extend `tests/test_cli.py` with file/stdin equivalence for terminal, JSON, and CSV.
2. Add subprocess tests for success `0`, missing/unreadable input or write failure `1`, invalid CLI `2`, strict/no-valid-data `3`, and cardinality exhaustion `4`.
3. Assert fatal paths have actionable stderr, no traceback, and no successful payload.
4. Add property/invariant tests for ranking limits, stable ties, hourly count totals, formula inputs, and record counters.

**Verification:**

- `python3.11 -m pytest -q --cov=streamsift --cov-branch --cov-fail-under=90`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-6: close CLI and failure contracts`

## STEP 7: Performance and Memory Release Gate

**Goal:** measured evidence demonstrates the 1 GB/30 s requirement and validates streaming/cardinality behavior on a documented laptop.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance Strategy”; `STRATEGIC_PLAN.md` success metrics and risks.

**Tasks:**

1. Create `tests/test_performance.py` with an opt-in deterministic generator that writes outside the repository and varies IP, error URL, hour, and User-Agent cardinality.
2. Add a small CI-safe performance smoke test and a separately marked 1 GB release benchmark.
3. Record Python version, OS, CPU, storage, input size/line count/cardinality, command, wall time, and peak RSS.
4. Compare equal-cardinality inputs of different line counts to verify memory is not proportional to retained records; trigger and validate exit `4` above the cap.
5. Profile parsing/aggregation only if the gate fails; do not introduce multiprocessing without revising the architecture.

**Verification:**

- `python3.11 -m pytest tests/test_performance.py -q -m 'not benchmark'`
- `python3.11 -m pytest tests/test_performance.py -q -m benchmark --run-benchmark`

**Commit:** `step-7: prove performance and memory bounds`

## STEP 8: Packaging, Documentation, and Release Rehearsal

**Goal:** a clean Python 3.11 environment can build, install, understand, and execute the completed CLI with matching documentation.

**Time:** ~3 hours

**Context:** all planning documents; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Create user `README.md` with installation, input grammar, examples for all formats, metric formulas, schemas, limitations, and `0/1/2/3/4` exit table.
2. Add `LICENSE`, package metadata, and repository `.gitignore` as required for open-source distribution.
3. Build wheel and sdist and inspect their contents; install the wheel into a fresh virtual environment.
4. Run golden smoke commands from file and stdin in all three output modes.
5. Reconcile behavior changes into `PRD.md`, `PROJECT_ARCHITECTURE.md`, `CLAUDE_CODE_GUIDE.md`, and `CLAUDE.md` before tagging.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest -q --cov=streamsift --cov-branch --cov-fail-under=90`
- `streamsift --json tests/fixtures/basic.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-8: prepare reproducible local release`

## 3. Weekend Boundaries

| Work block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday morning | 1–2 | Installable shell and trustworthy parsing | ~5 h |
| Saturday afternoon | 3–4 | Complete metrics and human output | ~6 h |
| Sunday morning | 5–6 | Pipeline contracts and failure matrix | ~6 h |
| Sunday afternoon | 7–8 | Performance proof and releasable package | ~6 h |

The estimate is deliberately tight. Gzip (P1) and configurable top-N (P2) are excluded from the weekend MVP if any P0 gate is at risk.

## 4. Dependency and Traceability Matrix

| Requirement group | Implemented in | Verified in |
|---|---|---|
| Input and parsing | Steps 1–2 | Parser/CLI fixtures |
| Four metrics | Step 3 | Aggregation unit/property tests |
| Terminal output | Step 4 | Terminal golden/TTY tests |
| JSON/CSV | Step 5 | Schema parse and golden tests |
| `0/1/2/3/4` contract | Steps 1–6 | Subprocess failure matrix |
| Performance/memory | Step 7 | Recorded benchmark and peak RSS |
| Installability/docs | Step 8 | Clean wheel rehearsal |

## 5. Final Acceptance Checklist

- [ ] All eight step verification blocks have current recorded evidence.
- [ ] Every P0 acceptance criterion in `PRD.md` is mapped to a passing test.
- [ ] The exact staged/release candidate, not an undeclared overlay, produced the evidence.
- [ ] The 1 GB performance run and memory evidence name the reference environment.
- [ ] All five exit codes are exercised end to end.
- [ ] No P1/P2 work displaced a P0 release gate.
- [ ] Product behavior and all project documents are reconciled.

