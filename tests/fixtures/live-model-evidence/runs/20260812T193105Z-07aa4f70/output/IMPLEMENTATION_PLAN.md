# Implementation Plan: nginx-report

## 1. Delivery Rules

This is a planning document; no product code is included. Execute one step at a time, update the specifications before changing behavior, and accept a step only with its listed evidence. The dependency order refines RICE priority: packaging and parsing unblock all higher-value metrics and renderers.

Every implementation step must preserve the complete exit-code contract: `0` success, `1` I/O failure, `2` CLI usage/configuration error, `3` malformed log data, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or collapsed into code 1 or 3.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python 3.11 package and console entry-point skeleton | All tests and features need an installable boundary | 1 hour |
| 2 | Canonical dataclasses and typed error/exit model | Keeps parser, aggregation, and renderers decoupled | 1 hour |
| 3 | Representative fixtures and benchmark protocol | Correctness and the 1 GB/30 s constraint must shape the hot path early | 1.5 hours |
| 4 | CI-style local quality command | Every later step needs one repeatable gate | 0.5 hour |

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–2 | Package contracts and fast, correct parser | Saturday morning |
| Weekend block 2 | 3–4 | Complete single-pass metric engine | Saturday afternoon |
| Weekend block 3 | 5–7 | Text and pipeline interfaces with stable failures | Sunday morning |
| Weekend block 4 | 8–9 | Performance evidence, compatibility, and release handoff | Sunday afternoon |

## STEP 1: Package, Models, and Contract Tests

**Goal:** An installable Python 3.11 package exposes `nginx-report`, and the report/exit contracts exist as testable types.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Internal Components and Files,” and “Data Model and Streaming State.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, the `src` package layout, `nginx-report` console script, and test/lint configuration.
2. Create `src/nginx_report/__init__.py` and `src/nginx_report/__main__.py` with package metadata and module execution delegation.
3. Create `src/nginx_report/models.py` with immutable `ParsedRequest`, `Report`, `RankedMetric`, `HourlyMetric`, and `UniqueAgentMetric` dataclasses.
4. Create `src/nginx_report/errors.py` with typed expected failures and a single enum for codes `0/1/2/3/4`.
5. Create `tests/test_models.py` and `tests/test_exit_codes.py` to freeze invariants and the complete mapping.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_models.py tests/test_exit_codes.py -q`
- `python3.11 -m nginx_report --help`

**Commit:** `step-1: establish package and report contracts`

## STEP 2: Combined-Log Parser and Early Throughput Gate

**Goal:** Valid nginx combined records parse deterministically from bytes, malformed records fail atomically, and early throughput is measured before feature layering.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Parsing and Aggregation Rules,” “Performance Architecture,” and “Testing Strategy.”

**Tasks:**

1. Create `src/nginx_report/parser.py` with a byte-oriented combined-log parser returning `ParsedRequest` without retaining source lines.
2. Create `tests/fixtures/combined_valid.log` and `tests/fixtures/combined_invalid.log` covering IPv4/IPv6, offsets, escaped quotes, non-ASCII bytes, statuses, malformed timestamps, and missing request targets.
3. Create `tests/test_parser.py` for field extraction, invalid classifications, control-character handling, and no partial output.
4. Create `bench/generate_log.py` as a deterministic development-only corpus generator and `bench/run_benchmark.py` to record elapsed time, byte count, throughput, hardware notes, and peak RSS.
5. Record the initial parser-only benchmark command and result in `bench/README.md`; do not claim the final target before the complete pipeline exists.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 bench/generate_log.py --bytes 104857600 --output /tmp/nginx-report-100mb.log`
- `python3.11 bench/run_benchmark.py --parser-only /tmp/nginx-report-100mb.log`

**Commit:** `step-2: parse combined logs in a streaming hot path`

## STEP 3: Core IP and Hourly Aggregation

**Goal:** One pass computes valid/invalid totals, top IPs, and 24 hourly percentages without storing requests.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Streaming State” and “Parsing and Aggregation Rules”; `PRD.md` P0 metric requirements.

**Tasks:**

1. Create `src/nginx_report/aggregate.py` with an aggregate-state dataclass and atomic `accept` operation.
2. Add IP counters and the fixed 24-element hour array.
3. Implement deterministic top-10 finalization: count descending, key bytewise ascending.
4. Calculate hourly percentages with exactly `100 × hourly_request_count / total_valid_requests`, returning 0.0 for every hour when there are no valid requests.
5. Create `tests/test_aggregate_core.py` for empty input, ties, offsets, invalid atomicity, denominators, and round-half-up behavior.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate_core.py -q`
- `python3.11 -m pytest tests/test_parser.py tests/test_aggregate_core.py --cov=nginx_report.parser --cov=nginx_report.aggregate --cov-fail-under=90`

**Commit:** `step-3: aggregate top IPs and hourly distribution`

## STEP 4: Error URLs and Exact User-Agent Cardinality

**Goal:** The aggregate engine adds deterministic top error URLs and exact unique User-Agent share with a hard exhaustion boundary.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs,” “Exit codes,” and “Data Model and Streaming State.”

**Tasks:**

1. Extend `src/nginx_report/aggregate.py` to count URLs only for statuses 400–599 and finalize the top 10 deterministically.
2. Track exact raw User-Agent identities with a configurable positive ceiling.
3. Raise the code-4 typed failure before accepting the first distinct value beyond the ceiling; do not return an approximate or complete-looking report.
4. Calculate unique User-Agent share as a percentage of total valid requests with the specified zero-input behavior.
5. Create `tests/test_aggregate_errors.py` and `tests/test_cardinality.py` for status boundaries, tie order, duplicates, `-`, ceiling-at-limit, and ceiling-plus-one.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate_errors.py tests/test_cardinality.py -q`
- `python3.11 -m pytest tests/test_aggregate_core.py tests/test_aggregate_errors.py tests/test_cardinality.py --cov=nginx_report.aggregate --cov-fail-under=90`

**Commit:** `step-4: add error URL and exact user-agent metrics`

## STEP 5: Rich Terminal Renderer

**Goal:** The default report is readable colored terminal text and remains clean when redirected or color is disabled.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs,” “Security and Privacy Boundaries,” and “Internal Components and Files.”

**Tasks:**

1. Create `src/nginx_report/render_text.py` with Rich tables for summary, top IPs, top error URLs, hourly distribution, and unique User-Agent share.
2. Implement auto-TTY color plus explicit `--color/--no-color` control at the renderer boundary.
3. Escape Rich markup and sanitize terminal control characters in untrusted keys.
4. Create `tests/golden/text_plain.txt`, `tests/test_render_text.py`, and terminal capability cases for deterministic layout and ANSI containment.

**Verification:**

- `python3.11 -m pytest tests/test_render_text.py -q`
- `python3.11 -m pytest tests/test_render_text.py --cov=nginx_report.render_text --cov-fail-under=90`

**Commit:** `step-5: render safe rich terminal reports`

## STEP 6: Stable JSON and CSV Renderers

**Goal:** Pipeline users receive versioned, ANSI-free JSON and RFC 4180 CSV matching the architecture contract.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface,” especially output schemas and ordering.

**Tasks:**

1. Create `src/nginx_report/render_json.py` with schema version 1, numeric percentages, UTF-8 output, and a final newline.
2. Create `src/nginx_report/render_csv.py` with the fixed five-column header, canonical row order, standard quoting, and formula-leading cell safety.
3. Create `tests/golden/report.json` and `tests/golden/report.csv` from one canonical report fixture.
4. Create `tests/test_render_json.py` and `tests/test_render_csv.py` for empty reports, Unicode, quoting, percentage precision, ordering, and no ANSI bytes.

**Verification:**

- `python3.11 -m pytest tests/test_render_json.py tests/test_render_csv.py -q`
- `python3.11 -m pytest tests/test_render_json.py tests/test_render_csv.py --cov=nginx_report.render_json --cov=nginx_report.render_csv --cov-fail-under=90`

**Commit:** `step-6: add versioned json and csv outputs`

## STEP 7: CLI Orchestration and Exit-Code Integration

**Goal:** Files and stdin flow through the complete pipeline, output streams are separated correctly, and every expected outcome maps to `0/1/2/3/4`.

**Time:** ~3 hours

**Context:** Entire `PROJECT_ARCHITECTURE.md` “CLI Interface” section.

**Tasks:**

1. Create `src/nginx_report/cli.py` with Click arguments/options, `--json`/`--csv` exclusion, positive ceiling validation, and renderer selection.
2. Implement binary file/stdin lifecycle, multiple-input ordering, duplicate-stdin rejection, and safe path/read/write diagnostics.
3. Implement default malformed-line skipping with final code 3 and `--strict` first-error stopping.
4. Translate expected domain errors into the full mapping: `0` success, `1` I/O, `2` usage/configuration, `3` malformed data, `4` unique-cardinality exhaustion.
5. Create `tests/test_cli.py` and `tests/test_exit_code_integration.py` covering stdout/stderr separation, empty input, every code, partial-output rules, broken pipes, color, JSON, and CSV.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py tests/test_exit_code_integration.py -q`
- `python3.11 -m nginx_report tests/fixtures/combined_valid.log --json | python3.11 -m json.tool >/dev/null`
- `python3.11 -m nginx_report tests/fixtures/combined_valid.log --csv | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: integrate cli streams and complete exit contract`

## STEP 8: Full Performance, Robustness, and Security Gate

**Goal:** The exact complete candidate meets the 1 GB/30 s target on the documented laptop and resists malformed/untrusted input without contract drift.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Security and Privacy Boundaries,” “Performance Architecture,” and the self-critique conditions.

**Tasks:**

1. Extend `bench/run_benchmark.py` to invoke the installed CLI with text rendering disabled from timing noise via `--json` redirected to a file.
2. Create `tests/test_fuzz_parser.py` using deterministic arbitrary-byte cases or a property-test dependency selected in `pyproject.toml`.
3. Add regression cases for huge fields, terminal markup, control bytes, CSV formulas, high key cardinality, and write failures.
4. Profile the full pipeline; optimize only measured bottlenecks without changing schemas or accuracy.
5. Record reference hardware, OS, Python version, cache state, command, elapsed time, throughput, and peak RSS in `bench/RESULTS.md`.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_report --cov-fail-under=90`
- `python3.11 bench/generate_log.py --bytes 1073741824 --output /tmp/nginx-report-1gb.log`
- `python3.11 bench/run_benchmark.py --max-seconds 30 /tmp/nginx-report-1gb.log`

**Commit:** `step-8: prove robustness and one-gigabyte performance`

## STEP 9: Documentation, Installation, and Release Candidate

**Goal:** A fresh local Python 3.11 environment can install and use the exact documented CLI, and the staged candidate is handoff-ready.

**Time:** ~2 hours

**Context:** All specification documents, especially `PRD.md` acceptance criteria and `CLAUDE.md` status rules.

**Tasks:**

1. Update `README.md` with pip/pipx quick start, stdin/file examples, text/JSON/CSV examples, schemas, limits, privacy, and exit codes.
2. Create `CHANGELOG.md` with the initial schema/CLI compatibility contract and `LICENSE` with the selected open-source license.
3. Create `tests/test_installed_package.py` to build a wheel, install it in a clean environment, invoke `nginx-report`, and validate entry-point metadata.
4. Reconcile `CLAUDE.md` step status and record all evidence without marking deferred Should/Could features complete.
5. Freeze the exact staged candidate, run the repository verification oracle, and apply the required risk-tier checker before accepting release readiness.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest -q --cov=nginx_report --cov-fail-under=90`
- `python3.11 -m venv /tmp/nginx-report-release-venv && /tmp/nginx-report-release-venv/bin/pip install dist/*.whl && /tmp/nginx-report-release-venv/bin/nginx-report --version`
- Run the current `.itd/VERIFICATION_CONTRACT.json` machine oracle against the frozen staged candidate and require a current passing adjudication receipt.

**Commit:** `step-9: prepare verified release candidate`

## Deferred Roadmap

Only after the MVP passes all P0 acceptance criteria may a new scoped plan add `--follow`, configurable formats, compressed-file convenience, or configurable top-N. Database, HTTP API, server, authentication, cloud, Kubernetes, and approximate cardinality remain out of scope unless the product specifications are explicitly revised.
