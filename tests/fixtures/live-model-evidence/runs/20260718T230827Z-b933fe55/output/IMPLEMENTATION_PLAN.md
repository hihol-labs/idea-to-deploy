# Implementation Plan: Nginx Stream Analyzer

This plan implements the P0 scope in [PRD.md](PRD.md) using the boundaries in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). It contains planning only; no product code is part of this blueprint.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Packaging and console entry point | Every later CLI test needs an installable command | 1 hour |
| 2 | Domain/output contracts | Parser, aggregator, and renderers need stable types | 1 hour |
| 3 | Representative fixtures and benchmark oracle | Correctness and performance need reproducible evidence | 1.5 hours |
| 4 | Quality configuration | Fast feedback is needed before feature work | 0.5 hour |

No database schema, authentication system, Docker setup, or CI deployment is runway work because the approved architecture contains none of those components.

## STEP 1: Package Skeleton and CLI Contract

**Goal:** A Python 3.11 package installs and exposes the documented command, options, help, and version.

**Time:** ~1.5 hours

**Context:** PROJECT_ARCHITECTURE.md Sections 4, 8, and 10.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, pytest tooling, and the `nginx-stream-analyzer` console script.
2. Create `src/nginx_stream_analyzer/__init__.py` with package version access.
3. Create `src/nginx_stream_analyzer/cli.py` with the positional `INPUT`, `--json`, `--csv`, `--no-color`, `--version`, and `--help` contract; reject simultaneous machine formats.
4. Create `tests/test_cli.py` to cover help, version, default stdin, mutual exclusion, and missing-file exits.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `nginx-stream-analyzer --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold package and CLI contract`

## STEP 2: Domain Models and Output Contract Tests

**Goal:** Immutable report types encode all cross-module invariants and stable machine schemas are test-first fixtures.

**Time:** ~1.5 hours

**Context:** PROJECT_ARCHITECTURE.md Sections 5 and 9; PRD.md FR-08 through FR-10.

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with `LogRecord`, `RankedCount`, `HourCount`, and `Report` dataclasses.
2. Create `tests/fixtures/representative.log` with valid IPv4/IPv6, 2xx/4xx/5xx, every relevant quoting case, and a malformed line.
3. Create `tests/fixtures/expected_report.json` as the oracle for the representative fixture.
4. Extend `tests/test_aggregate.py` with deterministic tie, empty-report, and ratio invariants before aggregation code exists.

**Verification:**

- `pytest -q tests/test_aggregate.py --collect-only`
- `python3.11 -m json.tool tests/fixtures/expected_report.json >/dev/null`

**Commit:** `step-2: define domain and report contracts`

## STEP 3: Combined-Log Streaming Parser

**Goal:** Supported nginx lines become typed records without buffering the input; malformed lines are classified safely.

**Time:** ~2.5 hours

**Context:** PROJECT_ARCHITECTURE.md Section 6; PRD.md FR-01 and FR-07.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with bounded binary reads, a 64 KiB logical-line limit, strict UTF-8, bounded oversized-line draining, a linear quoted-field scanner, and explicit field validation.
2. Create `tests/test_parser.py` for IPv4, IPv6, offsets, quoted escapes, dash values, 400/599 boundaries, invalid UTF-8, oversized/pathological lines, malformed timestamps/status/request triples, and sensitive diagnostic behavior.
3. Ensure parser APIs accept one bounded line at a time, store only the validated logged hour, and never retain the source line after returning.

**Verification:**

- `pytest -q tests/test_parser.py`
- `ruff check src/nginx_stream_analyzer/parser.py tests/test_parser.py`

**Commit:** `step-3: parse nginx combined logs safely`

## STEP 4: Exact One-Pass Aggregation

**Goal:** One traversal produces exact top IPs, top error URLs, 24 hourly buckets, and unique User-Agent share.

**Time:** ~2 hours

**Context:** PROJECT_ARCHITECTURE.md Sections 5 and 7; PRD.md FR-02 through FR-06.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with process-local counters, hour buckets, the User-Agent set, and the architecture-specified `nsmallest` ordering.
2. Create `src/nginx_stream_analyzer/service.py` to join line iteration, parsing, malformed-line accounting, and report finalization.
3. Complete `tests/test_aggregate.py` for top-10 truncation, an equal-count tie spanning rank 10, status boundaries, all 24 hours, duplicates, empty input, and exact ratios.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q --cov=nginx_stream_analyzer --cov-report=term-missing`

**Commit:** `step-4: aggregate all required metrics in one pass`

## STEP 5: JSON Renderer

**Goal:** `--json` emits the stable, ANSI-free schema for pipelines.

**Time:** ~1 hour

**Context:** PROJECT_ARCHITECTURE.md Section 9; PRD.md US-02 and FR-09.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` with renderer protocol/type aliases.
2. Create `src/nginx_stream_analyzer/renderers/json.py` using the standard JSON encoder and finite numeric values.
3. Create `tests/test_renderers.py` assertions for schema keys, all hour rows, UTF-8 values, no ANSI bytes, and empty input.

**Verification:**

- `pytest -q tests/test_renderers.py -k json`
- `nginx-stream-analyzer --json tests/fixtures/representative.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable JSON report`

## STEP 6: CSV Renderer

**Goal:** `--csv` emits one normalized, safely quoted table for all report sections.

**Time:** ~1.25 hours

**Context:** PROJECT_ARCHITECTURE.md Sections 9 and 12; PRD.md US-03 and FR-10.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/csv.py` with `report,rank,key,value` columns.
2. Add formula-prefix neutralization for log-derived keys and test commas, quotes, newlines, Unicode, and spreadsheet formula prefixes.
3. Extend `tests/test_renderers.py` to parse output back through `csv.DictReader` and validate every report family.

**Verification:**

- `pytest -q tests/test_renderers.py -k csv`
- `nginx-stream-analyzer --csv tests/fixtures/representative.log | sed -n '1,5p'`

**Commit:** `step-6: add normalized CSV report`

## STEP 7: Rich Terminal Report and Error UX

**Goal:** Default output is readable colored terminal text while redirection, diagnostics, and broken pipes remain clean.

**Time:** ~2 hours

**Context:** PROJECT_ARCHITECTURE.md Sections 8 and 12; PRD.md US-01, US-04, and FR-08.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/terminal.py` with four Rich report sections, a concise summary, and presentation-only escaping of C0/C1, DEL, ESC, CR/LF, and bidi-format controls.
2. Wire all renderers and file/stdin handling in `src/nginx_stream_analyzer/cli.py`.
3. Extend `tests/test_cli.py` for TTY/non-TTY color, `NO_COLOR`, `--no-color`, stdout/stderr separation, partial malformed input, unreadable files, and broken pipes.
4. Ensure untrusted fields render with markup disabled.

**Verification:**

- `pytest -q tests/test_cli.py tests/test_renderers.py`
- `NO_COLOR=1 nginx-stream-analyzer tests/fixtures/representative.log`

**Commit:** `step-7: complete terminal UX and failure behavior`

## STEP 8: Quality, Performance, and Release Documentation

**Goal:** The package passes the full quality suite, demonstrates the 1 GB target, and is installable from the documented path.

**Time:** ~3 hours plus benchmark generation time

**Context:** PROJECT_ARCHITECTURE.md Sections 11–12; STRATEGIC_PLAN.md Definition of Done.

**Tasks:**

1. Create `tests/test_performance.py` as a non-default throughput smoke test with deterministic generated lines.
2. Create `scripts/generate_benchmark_log.py` with a fixed seed and versioned profiles/oracles for the specified representative and high-cardinality 1 GB fixtures outside version control.
3. Update `README.md` with actual install, examples, schema notes, supported format, benchmark environment/result, and limitations.
4. Configure ruff and coverage in `pyproject.toml`; run a clean virtual-environment installation.
5. Record three measured representative runs and peak RSS for both profiles in the release notes or README; require representative median <30 seconds and both profiles ≤512 MiB, and do not claim either target from estimates.

**Verification:**

- `ruff check src tests scripts`
- `pytest -q --cov=nginx_stream_analyzer --cov-fail-under=90`
- `python3.11 -m build`
- `/usr/bin/time -v nginx-stream-analyzer --json /path/to/1gb-access.log >/dev/null`

**Commit:** `step-8: verify performance and package release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable contract and correct parser | Saturday morning |
| Weekend block 2 | 4–6 | Exact metrics and machine formats | Saturday afternoon |
| Weekend block 3 | 7 | Terminal UX and operational errors | Sunday morning |
| Weekend block 4 | 8 | Quality, benchmark, and release readiness | Sunday afternoon |

## Dependency and Priority Notes

The parser and report contract precede metrics despite some metrics having higher standalone RICE scores: they are hard dependencies. Within each dependency layer, error URLs and IPs are implemented before lower-scoring summaries, and JSON precedes CSV. P1/P2 work begins only after every P0 acceptance criterion and the performance gate pass.

## Completion Gate

The implementation is complete only with recorded command output for the full test, lint, build, clean-install, and benchmark checks. A missing benchmark run is “not verified,” not a performance pass.
