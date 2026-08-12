# Implementation Plan: nginx-stream-stats

## Planning Rules

This is an eight-step, one-weekend plan. Steps are ordered by dependency while preserving the RICE priority from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md): data contracts and parser unlock every metric; aggregators precede output; safety and performance gates precede release polish. Only one step is active at a time.

Every step must preserve the CLI exit-code contract: `0` success, `1` input/runtime failure, `2` CLI usage error, `3` zero valid supported records, and `4` unique-cardinality exhaustion. Code `4` must never be remapped to a generic runtime or usage failure.

## Architectural Runway

Infrastructure here means local project foundations, not deployed services.

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml`, `src/`, and pytest layout | All modules and verification commands depend on import/package structure | 0.5 h |
| 2 | Typed records and error taxonomy | Prevents renderer, analyzer, and CLI semantics from drifting | 0.5 h |
| 3 | Golden combined-log fixtures | Enables parser-first correctness before feature integration | 0.5 h |
| 4 | Benchmark protocol | Makes the 1 GB/30 s constraint an acceptance gate, not an afterthought | 0.5 h |

No database schema, authentication, Docker, CI service, or deployment environment belongs in the runway because [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) explicitly excludes them.

## STEP 1: Package Skeleton and Contracts

**Goal:** A Python 3.11 package imports, exposes the future console entry point, and has typed domain/error contracts.  
**Time:** ~1 hour  
**Context:** PROJECT_ARCHITECTURE.md sections 4–6; PRD FR-1, FR-7, NFR-4.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11`, Click, Rich, build metadata, pytest/test tooling, and the `nginx-stream-stats` console script.
2. Create `src/nginx_stream_stats/__init__.py` with one version source.
3. Create `src/nginx_stream_stats/models.py` with dataclasses for `LogRecord`, `AnalysisConfig`, ranked values, hourly buckets, diagnostics, and `Report`.
4. Create `src/nginx_stream_stats/errors.py` with typed failures mapped once to exit codes `1`, `3`, and `4`; leave Click to own usage code `2`.
5. Create `tests/test_models.py` and `tests/test_errors.py` for invariants and the full `0/1/2/3/4` mapping.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/python -m pytest tests/test_models.py tests/test_errors.py`
- `.venv/bin/nginx-stream-stats --help`

**Commit:** `step-1: establish package and domain contracts`

## STEP 2: Combined-Format Streaming Parser

**Goal:** Supported log lines become `LogRecord` values incrementally, with bounded safe diagnostics for malformed lines.  
**Time:** ~2 hours  
**Context:** PROJECT_ARCHITECTURE.md sections 5, 7, and 8; PRD FR-1 and FR-6.

**Tasks:**

1. Create `src/nginx_stream_stats/parser.py` with a precompiled nginx combined-format matcher, timestamp/status validation, quoted-field unescaping, and request-target extraction.
2. Create `tests/fixtures/combined.log` covering IPv4, IPv6, query strings, timezone offsets, `-` User-Agent, and 4xx/5xx boundaries.
3. Create `tests/fixtures/mixed-invalid.log` without real credentials or personal data.
4. Create `tests/test_parser.py` for valid records, malformed reason categories, safe line-number-only diagnostics, and lazy iteration.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py`
- `.venv/bin/python -m pytest tests/test_parser.py -k 'lazy or malformed or timezone'`

**Commit:** `step-2: parse nginx combined logs incrementally`

## STEP 3: Core Metrics and Cardinality Guard

**Goal:** One pass produces all four exact metrics and deterministic top-10 results within the configured unique-key ceiling.  
**Time:** ~2.5 hours  
**Context:** PROJECT_ARCHITECTURE.md sections 5 and 7; PRD FR-2 through FR-6.

**Tasks:**

1. Create `src/nginx_stream_stats/analyzer.py` with IP and error-URL counters, 24 hour bins, non-missing User-Agent set, and validity counters.
2. Implement top-10 sorting as count descending then key ascending.
3. Implement hourly percentages using exactly `100 × hourly_request_count / total_valid_requests` and unique-agent share using the PRD numerator/denominator.
4. Enforce the shared `--max-unique` ceiling before new insertions and raise the typed exhaustion failure mapped to `4`.
5. Create `tests/test_analyzer.py` for golden metrics, ties, all status classes, missing agents, rounding boundaries, zero-valid exit `3`, and exhaustion exit `4`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_analyzer.py`
- `.venv/bin/python -m pytest tests/test_analyzer.py -k 'top or hourly or user_agent or exhaustion'`

**Commit:** `step-3: calculate exact streaming metrics`

## STEP 4: Stable JSON and CSV Renderers

**Goal:** The same `Report` serializes into versioned, ANSI-free pipeline formats.  
**Time:** ~1.5 hours  
**Context:** PROJECT_ARCHITECTURE.md CLI Interface and section 6; PRD FR-8 and FR-9.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/__init__.py` with a renderer protocol/dispatch type.
2. Create `src/nginx_stream_stats/renderers/json.py` for the documented `schema_version: 1` object and numeric counts/percentages.
3. Create `src/nginx_stream_stats/renderers/csv.py` for the long-form six-column schema and deterministic row ordering.
4. Create `tests/test_renderers.py` with parsed JSON assertions, CSV round-trip assertions, empty-field rules, escaping, and no-ANSI checks.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -k 'json or csv'`
- `.venv/bin/python -m pytest tests/test_renderers.py -k no_ansi`

**Commit:** `step-4: add pipeline-safe report formats`

## STEP 5: Rich Terminal Renderer

**Goal:** Interactive users receive readable colored tables without changing report semantics or polluting non-TTY output.  
**Time:** ~1 hour  
**Context:** PROJECT_ARCHITECTURE.md CLI Interface and section 8; PRD FR-10.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/text.py` with summary, ranked IP/error URL tables, 24-hour distribution, and User-Agent summary.
2. Escape/sanitize values before Rich markup and make color policy injectable for tests.
3. Extend `tests/test_renderers.py` with forced-color, no-color, control-character, deterministic-order, and narrow-terminal cases.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -k text`
- `COLUMNS=80 .venv/bin/python -m pytest tests/test_renderers.py -k narrow`

**Commit:** `step-5: render safe colored terminal report`

## STEP 6: Click CLI and End-to-End Contract

**Goal:** File and stdin flows expose the approved options, clean stdout/stderr, and exact exit codes.  
**Time:** ~2 hours  
**Context:** PROJECT_ARCHITECTURE.md CLI Interface; PRD FR-7 through FR-11.

**Tasks:**

1. Create `src/nginx_stream_stats/cli.py` with `analyze`, `INPUT`, mutually exclusive `--json`/`--csv`, color flags, positive `--max-unique`, `--show-malformed`, version, and help.
2. Centralize failure-to-message/exit conversion while preserving `0/1/2/3/4`; make code `4` uniquely identify cardinality exhaustion.
3. Handle stdin ownership and broken stdout pipes according to architecture.
4. Create `tests/test_cli.py` using Click `CliRunner` for file/stdin parity, every option, stdout/stderr separation, and every exit code.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py`
- `.venv/bin/nginx-stream-stats analyze --json tests/fixtures/combined.log | .venv/bin/python -m json.tool`
- `.venv/bin/nginx-stream-stats analyze --csv tests/fixtures/combined.log | sed -n '1,3p'`

**Commit:** `step-6: integrate click command and exit contract`

## STEP 7: Performance and Robustness Gate

**Goal:** The exact candidate demonstrates the 1 GB/30 s target, bounded unique-key failure, and acceptable peak memory on a documented laptop.  
**Time:** ~2 hours  
**Context:** PROJECT_ARCHITECTURE.md sections 7, 8, and 10; PRD NFR-1 through NFR-3 and kill criteria.

**Tasks:**

1. Create `tests/fixtures/generate_benchmark.py` as a deterministic fixture generator; label its output synthetic test data.
2. Create `tests/test_performance.py` with a small default performance regression and an opt-in 1 GB acceptance test.
3. Create `docs/PERFORMANCE.md` recording CPU, RAM, storage, OS, Python version, command, input bytes/lines, wall time, and peak RSS.
4. Profile only if the first target run fails; optimize measured parser/allocation hotspots without adding concurrency or approximation.
5. Exercise `--max-unique` below fixture cardinality and assert exit `4` with no success report.

**Verification:**

- `.venv/bin/python tests/fixtures/generate_benchmark.py --bytes 1073741824 /tmp/nginx-stream-stats-1gb.log`
- `/usr/bin/time -v .venv/bin/nginx-stream-stats analyze --json /tmp/nginx-stream-stats-1gb.log >/tmp/nginx-stream-stats-report.json`
- `.venv/bin/python -m pytest tests/test_performance.py -m performance`
- `.venv/bin/python -m pytest tests/test_cli.py -k cardinality_exhaustion`

**Commit:** `step-7: prove performance and memory boundaries`

## STEP 8: Release Quality, Packaging, and Documentation

**Goal:** A clean Python 3.11 environment can build, install, understand, and run the release candidate.  
**Time:** ~2 hours  
**Context:** STRATEGIC_PLAN.md Definition of Done; PRD release criteria; README.md.

**Tasks:**

1. Finalize `README.md` with Quick Start, metric definitions, format examples, privacy boundary, and exit codes `0/1/2/3/4`, including `4` for unique-cardinality exhaustion.
2. Add `LICENSE` using an approved open-source license and `CHANGELOG.md` with the initial schema/CLI contract.
3. Add `.github/workflows/ci.yml` for Python 3.11 tests, coverage, build, and install smoke test; it is optional hosted automation, not product cloud infrastructure.
4. Build wheel/sdist, check metadata, install the wheel into a clean venv, and run file/stdin smoke tests.
5. Run the full suite and reconcile all blueprint documents with shipped behavior before tagging.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_stream_stats --cov-fail-under=90`
- `.venv/bin/python -m build && .venv/bin/twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-stats-smoke && /tmp/nginx-stream-stats-smoke/bin/pip install dist/*.whl`
- `/tmp/nginx-stream-stats-smoke/bin/nginx-stream-stats analyze tests/fixtures/combined.log`

**Commit:** `step-8: prepare verified installable release`

## Sprint Boundaries

For a one-weekend delivery, “sprint” means a focused half-day boundary rather than a multi-week ceremony.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Contracts and supported parser | Half day |
| Saturday PM | 3–4 | Metrics and pipeline formats | Half day |
| Sunday AM | 5–6 | Human UI and complete CLI | Half day |
| Sunday PM | 7–8 | Performance proof and release readiness | Half day |

## Completion Handoff

Record test and benchmark evidence with the exact candidate. If a gate fails, leave the active step incomplete and state the next corrective action. Do not begin a later step to mask an earlier failure. The acceptance source of truth is [PRD.md](PRD.md), and architectural conflicts resolve in favor of [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).
