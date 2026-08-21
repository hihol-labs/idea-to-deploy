# Implementation Plan: Nginx Stream Analyzer

## Planning Basis

This plan implements the P0 scope in `PRD.md` and the single-process design in `PROJECT_ARCHITECTURE.md`. It is documentation only; none of these steps has been executed. RICE order is adjusted for dependencies: stream/package contracts first, parser second, then aggregation, outputs, and acceptance.

The complete exit-code contract applies to every step and guide: `0` success, `1` malformed-log strict failure or analysis invariant failure, `2` CLI usage error, `3` input/output system error, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or collapsed into code 1.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package layout and console entry point | All tests and behaviors need an installable command | 1 h |
| 2 | Dataclass and serialization schema freeze | Keeps terminal/JSON/CSV interpretations aligned | 1 h |
| 3 | Representative combined-log fixtures | Parser and metric tests need shared evidence | 1 h |
| 4 | Benchmark generator and measurement protocol | Performance must be measured before late optimization | 1 h |

No database, authentication, HTTP API, Docker, cloud, or Kubernetes work belongs in the runway.

## Step 1: Package and CLI Contract

**Goal:** A Python 3.11 package installs with pip and exposes a Click command whose help, input selection, flags, and usage errors match the architecture.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Design,” “CLI Interface,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, pytest tooling, and the `nginx-analyzer` console script.
2. Create `src/nginx_stream_analyzer/__init__.py` with package version exposure.
3. Create `src/nginx_stream_analyzer/cli.py` with `PATH`, `--json`, `--csv`, `--color/--no-color`, `--strict`, `--max-unique`, `--version`, and `--help` declarations.
4. Create `src/nginx_stream_analyzer/errors.py` with domain error classes carrying codes 1, 3, and 4; leave Click usage validation mapped to 2.
5. Create `tests/test_cli_contract.py` for help/version, stdin selection, mutually exclusive formats, and positive `--max-unique` validation.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/nginx-analyzer --help`
- `.venv/bin/pytest -q tests/test_cli_contract.py`
- Explicitly assert the documented `0/1/2/3/4` mapping, including code 4 for unique-cardinality exhaustion.

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Domain Models and Combined-Log Parser

**Goal:** Individual combined-format lines become typed records or structured parse failures without leaking raw log content.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Design,” “Streaming Data Flow,” and “Data Model and Metric Definitions.”

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with frozen `AccessRecord`, `RankedCount`, `HourlyBucket`, and `AnalysisReport` dataclasses.
2. Create `src/nginx_stream_analyzer/parser.py` with a precompiled combined-format grammar and validation for address text, timestamp hour, request target, status, and User-Agent.
3. Create `tests/fixtures/access_combined.log` and `tests/fixtures/access_malformed.log` covering IPv4, IPv6, timezones, quotes, `-`, statuses 399/400/499/500/599/600, and malformed records.
4. Create `tests/test_parser.py` for successful field extraction and sanitized errors.

**Verification:**

- `.venv/bin/pytest -q tests/test_parser.py`
- `.venv/bin/python -m pytest -q tests/test_parser.py -k 'ipv4 or ipv6 or malformed'`
- Confirm parser failures route to code 1 only in strict mode; I/O remains 3, usage 2, cardinality 4, and successful non-strict completion 0.

**Commit:** `step-2: parse nginx combined records`

## Step 3: One-Pass Aggregation and Metric Semantics

**Goal:** A stream of records produces exact top IPs, error URLs, 24 hourly buckets, and User-Agent diversity within configured limits.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Streaming Data Flow,” “Data Model and Metric Definitions,” and “Cardinality and Resource Policy.”

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregator.py` with `StreamingAggregator.consume()` and `.finish()`.
2. Count all statuses for IP/hour/UA, but only 400–599 for error URLs.
3. Sort rankings by descending count then ascending key and truncate to 10.
4. Calculate each hour using `100 × hourly_request_count / total_valid_requests`; preserve full precision until rendering and return `0.0` for a zero denominator.
5. Calculate UA share as `100 × unique_user_agent_count / total_valid_requests` with the same zero rule.
6. Enforce `--max-unique` independently for IPs, error URLs, and User-Agents before new-key insertion; raise code-4 `CardinalityError` without partial output.
7. Create `tests/test_aggregator.py` with boundary, tie, denominator, and invariants tests.

**Verification:**

- `.venv/bin/pytest -q tests/test_aggregator.py`
- `.venv/bin/python -m pytest -q tests/test_aggregator.py -k cardinality`
- Confirm all 24 hourly counts sum to `total_valid_requests` and percentage behavior uses `100 × hourly_request_count / total_valid_requests`.
- Confirm the full `0/1/2/3/4` contract, especially exhaustion code 4 in each unique dimension.

**Commit:** `step-3: implement bounded streaming metrics`

## Step 4: Input Loop, Diagnostics, and Failure Mapping

**Goal:** File and stdin processing share one streaming path, malformed-line policy is observable, and every failure maps to its public code.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Error and Diagnostics Policy”; `PRD.md` US-1 and US-7.

**Tasks:**

1. Complete `src/nginx_stream_analyzer/cli.py` input ownership and line iteration without `read()`/`readlines()` over the complete source.
2. Add non-strict malformed counting and strict immediate failure behavior.
3. Sanitize stderr diagnostics so no raw URL or User-Agent value is echoed.
4. Map success to 0, strict malformed/invariant failure to 1, Click usage to 2, open/read/write errors to 3, and any unique-cardinality exhaustion to 4.
5. Create `tests/test_streaming.py` and `tests/test_exit_codes.py`, including file/stdin parity and simulated read/write errors.

**Verification:**

- `.venv/bin/pytest -q tests/test_streaming.py tests/test_exit_codes.py`
- `.venv/bin/pytest -q tests/test_exit_codes.py -k 'code_0 or code_1 or code_2 or code_3 or code_4'`
- Inspect tests to ensure no code 4 remapping and no successful partial stdout on codes 1, 3, or 4.

**Commit:** `step-4: connect streaming IO and exit behavior`

## Step 5: Rich Terminal Renderer

**Goal:** Default invocation renders readable, safe terminal tables for the four reports with correct color detection.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface — Outputs” and “Security and Privacy”; `PRD.md` FR-7 and FR-8.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` and `src/nginx_stream_analyzer/renderers/terminal.py`.
2. Render summary counts, top IPs, top error URLs, all 24 hourly buckets, and unique-UA count/share.
3. Escape or disable Rich markup for untrusted log values.
4. Auto-disable color for non-TTY stdout and `NO_COLOR`; honor explicit color options only in terminal mode.
5. Create `tests/test_terminal_output.py` with captured TTY/non-TTY and markup payload cases.

**Verification:**

- `.venv/bin/pytest -q tests/test_terminal_output.py`
- `.venv/bin/nginx-analyzer tests/fixtures/access_combined.log --no-color`
- Re-run exit tests to preserve `0/1/2/3/4`, including unique-cardinality code 4.

**Commit:** `step-5: render safe Rich terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive deterministic, versioned, ANSI-free JSON or normalized CSV with values equal to terminal output.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface — Outputs”; `PRD.md` US-6.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/json.py` with the documented object shape and `schema_version`.
2. Create `src/nginx_stream_analyzer/renderers/csv.py` with `schema_version,section,rank,key,count,percentage` and all four section types.
3. Wire renderer selection in `src/nginx_stream_analyzer/cli.py` before processing begins.
4. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_machine_output.py` for schema, quoting, ordering, rounding, stdout/stderr separation, and cross-format reconciliation.

**Verification:**

- `.venv/bin/pytest -q tests/test_machine_output.py`
- `.venv/bin/nginx-analyzer --json tests/fixtures/access_combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-analyzer --csv tests/fixtures/access_combined.log | .venv/bin/python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`
- Exercise and retain the full `0/1/2/3/4` matrix in both machine formats; code 4 emits no JSON/CSV success artifact.

**Commit:** `step-6: add deterministic JSON and CSV output`

## Step 7: Full Correctness, Packaging, and Security QA

**Goal:** The exact candidate is installable, internally consistent, and safe for untrusted log values.

**Time:** ~2 hours

**Context:** `PRD.md` “Release Acceptance”; `PROJECT_ARCHITECTURE.md` “Test Strategy” and “Security and Privacy.”

**Tasks:**

1. Add `tests/test_invariants.py` for count reconciliation and stable repeated output.
2. Add adversarial fixtures for terminal markup, control characters, CSV formulas/quotes, large fields, and invalid bytes.
3. Configure coverage, lint, formatting, and typing tools in `pyproject.toml` without adding runtime dependencies.
4. Build wheel and source distribution and install the wheel into a clean Python 3.11 environment.
5. Update `README.md` examples only after the CLI golden contract is fixed.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_stream_analyzer --cov-fail-under=90`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`
- Run configured formatter/linter/type-checker commands from `pyproject.toml`.
- Run a parameterized CLI test that proves exactly `0/1/2/3/4`; code 4 remains unique-cardinality exhaustion.

**Commit:** `step-7: harden tests and package artifacts`

## Step 8: Performance Gate and Release Handoff

**Goal:** The package meets the 1 GB/30 s target on a named reference laptop and the documentation is ready for release.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` KPIs/Definition of Done; `PROJECT_ARCHITECTURE.md` “Quality Attributes” and “Observability.”

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` for deterministic representative combined logs without checking a 1 GB fixture into source control.
2. Create `scripts/run_benchmark.sh` to record Python/package version, hardware/OS, input size/hash, wall time, throughput, and peak RSS.
3. Profile before changing implementation; optimize only measured parser/aggregation hot paths while preserving exact output.
4. Record reproducible benchmark results in `docs/BENCHMARK.md` and limitations in `README.md`.
5. Freeze the exact candidate and run the project’s required verification/review route before release acceptance.

**Verification:**

- `.venv/bin/python scripts/generate_benchmark_log.py --bytes 1000000000 --output /tmp/nginx-analyzer-benchmark.log`
- `scripts/run_benchmark.sh /tmp/nginx-analyzer-benchmark.log`
- `.venv/bin/pytest -q`
- Verify elapsed time is <30 s on the documented reference laptop and rerun the complete `0/1/2/3/4` contract, with code 4 meaning unique-cardinality exhaustion.

**Commit:** `step-8: verify performance and release readiness`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–2 | Installable skeleton and trustworthy parser | Saturday morning |
| Weekend block 2 | 3–4 | Exact bounded metrics and error semantics | Saturday afternoon |
| Weekend block 3 | 5–6 | Human and pipeline outputs | Sunday morning |
| Weekend block 4 | 7–8 | Quality, benchmark, and handoff | Sunday afternoon |

## Dependency and Scope Guardrails

- Do not begin renderers until dataclass and metric contracts pass tests.
- Do not optimize until a profiler identifies a hot path.
- Do not add gzip/custom-format/top-N work before all P0 acceptance gates pass.
- Do not introduce authentication, persistence, HTTP, a server, cloud integration, Docker, or Kubernetes.
- A performance miss triggers profiling/re-scope, not an undisclosed approximate algorithm.
