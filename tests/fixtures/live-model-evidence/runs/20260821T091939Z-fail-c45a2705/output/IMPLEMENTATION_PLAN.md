# Implementation Plan: nginx-insight

This is a planning artifact; no product code is implemented by this blueprint.
Steps are dependency-ordered while preserving the RICE priorities in
`STRATEGIC_PLAN.md`. Estimated focused effort is approximately 15 hours over
one weekend.

## Contract That Applies to Every Step

The CLI exit-code contract is immutable across implementation and tests:

| Code | Required meaning |
|---:|---|
| `0` | Success, including help/version |
| `1` | Unexpected internal/runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Input open/read/decode failure, or no valid records |
| `4` | Unique-cardinality exhaustion |

Code 4 must never be omitted, remapped, or downgraded to partial success.
Every step must preserve stateless single-process streaming and must not add a
database, HTTP API, authentication, server, cloud, or Kubernetes.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and test skeleton | All modules and the installed command depend on import/build conventions | 1.0 h |
| 2 | Frozen data/output contracts and fixtures | Prevent renderer and parser implementations from drifting | 1.0 h |
| 3 | Quality commands and benchmark protocol | Gives each feature an executable acceptance path | 0.5 h |

## STEP 1: Establish the Installable Package and Quality Gates

**Goal:** A Python 3.11 package can be built, installed, invoked, and checked
before business logic is added.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Boundaries” and
“Packaging and Runtime”; `PRD.md` P0 requirement 10.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, the
   `nginx-insight` console script, and pytest/Ruff/mypy development settings.
2. Create `src/nginx_insight/__init__.py`, `src/nginx_insight/__main__.py`, and
   `src/nginx_insight/cli.py` with only the command boundary needed for a smoke test.
3. Create `tests/test_cli_smoke.py` for help, version, and installed invocation.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_smoke.py -q`
- `python3.11 -m nginx_insight --help`
- `nginx-insight --version`

**Commit:** `step-1: establish package and CLI skeleton`

## STEP 2: Freeze Models, Fixtures, and Parser Contract

**Goal:** Representative combined-format lines parse into typed dataclasses and
malformed lines are classified without retaining input.

**Time:** ~2 hours

**Context:** Architecture “Data Model and Algorithms”; PRD US-1, US-6.

**Tasks:**

1. Create `src/nginx_insight/models.py` with frozen `AccessRecord`, ranking,
   hourly-bin, and `AnalysisReport` dataclasses.
2. Create `src/nginx_insight/parser.py` with one precompiled combined-format
   grammar and timestamp/status/request-target conversion.
3. Create `tests/fixtures/access.log` and `tests/fixtures/malformed.log` covering
   IPv4, IPv6, escaped quotes, `-`, query strings, blank input, and bad records.
4. Create `tests/test_parser.py` with positive and negative table-driven cases.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m ruff check src/nginx_insight/models.py src/nginx_insight/parser.py tests/test_parser.py`
- `python3.11 -m mypy src/nginx_insight/models.py src/nginx_insight/parser.py`

**Commit:** `step-2: define log parser and typed records`

## STEP 3: Implement Streaming Aggregations and Rankings

**Goal:** One pass produces exact counts, top-10 IP/error URL rankings, hourly
percentages, and User-Agent share.

**Time:** ~2.5 hours

**Context:** Architecture “Data Model and Algorithms”; PRD US-1 through US-4.

**Tasks:**

1. Create `src/nginx_insight/aggregate.py` with counters, the fixed 24-bin
   array, the exact bounded User-Agent set, and report finalization.
2. Implement deterministic count-descending/key-ascending top-10 selection.
3. Apply `100 × hourly_request_count / total_valid_requests` to each hourly bin
   and the documented User-Agent percentage formula.
4. Create `tests/test_aggregate.py` for boundaries 399/400/599/600, ties, 24
   bins, empty error rankings, duplicate User-Agents, and mixed offsets.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_parser.py tests/test_aggregate.py --cov=nginx_insight --cov-report=term-missing`

**Commit:** `step-3: add exact streaming analytics`

## STEP 4: Enforce Failures and Cardinality Guard

**Goal:** All expected failures map to the exact `0/1/2/3/4` contract, and
cardinality exhaustion cannot produce partial success.

**Time:** ~1.5 hours

**Context:** Architecture “CLI Interface” and “Error Handling”; PRD US-4, US-6.

**Tasks:**

1. Create `src/nginx_insight/errors.py` with typed input and cardinality errors.
2. Complete `src/nginx_insight/cli.py` input opening, stdin handling, positive
   ceiling validation, malformed accounting, and top-level error mapping.
3. Create `tests/test_exit_codes.py` that triggers and asserts codes 0, 1, 2,
   3, and 4 plus empty stdout for failed analyses.

**Verification:**

- `python3.11 -m pytest tests/test_exit_codes.py -q`
- `python3.11 -m pytest tests/test_exit_codes.py -q --maxfail=1`

**Commit:** `step-4: enforce complete exit contract`

## STEP 5: Add Rich Terminal Rendering

**Goal:** Interactive users receive readable, safely escaped colored tables
without ANSI leakage to non-TTY output.

**Time:** ~1.5 hours

**Context:** Architecture “CLI Interface / Outputs” and “Security and Trust
Boundaries”; PRD P0 requirement 5.

**Tasks:**

1. Create `src/nginx_insight/render/__init__.py` and
   `src/nginx_insight/render/terminal.py` for the five ordered report sections.
2. Wire automatic TTY color and `--no-color` in `src/nginx_insight/cli.py`.
3. Create `tests/test_terminal_output.py` for ordering, no-color, non-TTY,
   zero-hour bins, empty errors, and markup/control-text escaping.

**Verification:**

- `python3.11 -m pytest tests/test_terminal_output.py -q`
- `nginx-insight --no-color tests/fixtures/access.log`

**Commit:** `step-5: render safe Rich terminal report`

## STEP 6: Add Stable JSON and CSV Pipeline Formats

**Goal:** Machine consumers receive deterministic output conforming exactly to
the documented schemas.

**Time:** ~2 hours

**Context:** Architecture “CLI Interface / Outputs”; PRD US-5.

**Tasks:**

1. Create `src/nginx_insight/render/json_output.py` with schema version 1.0 and
   numeric percentages.
2. Create `src/nginx_insight/render/csv_output.py` using `csv.writer` and the
   stable `section,rank,key,count,percentage` columns.
3. Update `src/nginx_insight/cli.py` with mutually exclusive `--json`/`--csv`.
4. Create `tests/test_pipeline_output.py` to parse both formats and compare
   their metrics against the same expected report.

**Verification:**

- `python3.11 -m pytest tests/test_pipeline_output.py -q`
- `nginx-insight --json tests/fixtures/access.log | python3.11 -m json.tool >/dev/null`
- `nginx-insight --csv tests/fixtures/access.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add stable JSON and CSV renderers`

## STEP 7: Prove End-to-End Behavior

**Goal:** File and stdin workflows produce equivalent metrics and every P0
acceptance criterion has an integration-level assertion.

**Time:** ~1.5 hours

**Context:** All PRD P0 stories; full Architecture CLI contract.

**Tasks:**

1. Create `tests/test_end_to_end.py` covering file/stdin equivalence,
   diagnostics separation, deterministic ties, and all three formats.
2. Create `tests/fixtures/expected_report.json` as the human-reviewable golden
   aggregate for the representative small input.
3. Add a traceability table to `tests/README.md` mapping US-1 through US-6 and
   exit codes `0/1/2/3/4` to test cases.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_insight --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m ruff check .`
- `python3.11 -m mypy src/nginx_insight`

**Commit:** `step-7: verify end-to-end CLI contracts`

## STEP 8: Measure and Tune the 1 GB Path

**Goal:** The performance claim is supported by reproducible elapsed-time,
peak-RSS, correctness, and environment evidence.

**Time:** ~1.5 hours

**Context:** Architecture “Performance and Resource Contract”; PRD US-7.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically stream a documented
   distribution into a 1 GB fixture without checking it into source control.
2. Create `benchmarks/run_benchmark.sh` to run installed JSON mode with
   `/usr/bin/time`, record environment metadata, and compare expected totals.
3. Create `benchmarks/README.md` with reference laptop and cold/warm-cache procedure.
4. Profile first and make only measured, behavior-preserving changes to parser
   or aggregation modules if the target is missed.

**Verification:**

- `python3.11 benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-insight-1g.log`
- `bash benchmarks/run_benchmark.sh /tmp/nginx-insight-1g.log`
- `python3.11 -m pytest -q`

**Commit:** `step-8: establish laptop-scale performance evidence`

## STEP 9: Validate Distribution and Release Readiness

**Goal:** A clean Python 3.11 environment can install the artifact and run the
documented command with all contracts intact.

**Time:** ~1 hour

**Context:** Strategic Definition of Done; PRD “Release Acceptance.”

**Tasks:**

1. Create/update `README.md` with under-30-second quick start, input contract,
   example terminal/JSON/CSV commands, and exit codes `0/1/2/3/4`.
2. Create `CHANGELOG.md` with the initial 1.0 contract.
3. Build wheel/sdist, install the wheel in a clean temporary virtual
   environment, and run fixture smoke tests.
4. Freeze the exact candidate and execute the current Idea to Deploy machine
   oracle and risk-tier checker before accepting release readiness.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest -q`
- `python3.11 -m ruff check . && python3.11 -m mypy src/nginx_insight`
- Run the repository's current exact-candidate Idea to Deploy verification command and retain its adjudication receipt.

**Commit:** `step-9: validate installable release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–2 | Architectural runway, package, parser contract | Friday evening |
| Weekend block 2 | 3–4 | Exact analytics and failure semantics | Saturday morning |
| Weekend block 3 | 5–7 | All outputs and end-to-end acceptance | Saturday afternoon–Sunday morning |
| Weekend block 4 | 8–9 | Performance evidence and distribution | Sunday afternoon |

## Requirements Traceability

| Requirement | Primary steps |
|---|---|
| US-1 top IPs | 2, 3, 7 |
| US-2 top error URLs | 3, 7 |
| US-3 hourly percentage | 3, 7 |
| US-4 exact User-Agent share / exit 4 | 3, 4, 7 |
| US-5 Rich/JSON/CSV | 5, 6, 7 |
| US-6 malformed input | 2, 4, 7 |
| US-7 performance | 8 |
| pip installation | 1, 9 |

## Completion Gate

Narration, a green command in isolation, or a standalone `PASSED` label is not
sufficient. Completion requires all P0 criteria, the benchmark evidence, the
packaging smoke test, and a current exact-candidate adjudication receipt under
the repository's Idea to Deploy contracts. The future external Devil's
Advocate review remains separate from these implementation steps.
