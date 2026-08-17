# Implementation Plan: nginx-stream-stats

## Scope and Delivery Rules

This is an eight-step, approximately 16-hour one-weekend plan for the P0 MVP.
Steps are ordered by value and technical dependency. P1 gzip support is isolated
at the end and may be dropped before any P0 criterion. Product code must conform
to `PROJECT_ARCHITECTURE.md`; behavior changes begin by updating `PRD.md`.

The complete exit-code contract applies throughout implementation and must be
tested without omission or remapping:

| Code | Required meaning |
|---:|---|
| `0` | Success, including report output, help, and version |
| `1` | Unexpected runtime or non-pipe output failure |
| `2` | CLI usage or configuration error |
| `3` | Input or log-data error |
| `4` | Unique-cardinality exhaustion |

No database, HTTP endpoint, auth flow, server, cloud resource, Docker asset, or
Kubernetes manifest is part of any step.

## Architectural Runway

These foundations precede feature implementation:

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package and console entry point | Establishes install/import/CLI boundaries | 0.75 h |
| 2 | Typed models and errors | Gives parser, aggregator, renderers, and exit mapping one contract | 0.75 h |
| 3 | Representative fixture corpus | Makes parsing and output behavior replayable before optimization | 0.50 h |
| 4 | Quality commands | Keeps formatting, lint, types, tests, and coverage consistent | 0.50 h |

## Weekend Boundaries

| Window | Steps | Goal | Duration |
|---|---|---|---:|
| Saturday morning | 1–2 | Installable structure and trusted parser | ~4 h |
| Saturday afternoon | 3–4 | Exact bounded streaming metrics | ~4 h |
| Sunday morning | 5–6 | Three output modes and complete CLI contract | ~4.5 h |
| Sunday afternoon | 7–8 | Release evidence, packaging, and documentation | ~3.5 h |

## STEP 1: Establish package, models, and verification skeleton

**Goal:** A clean Python 3.11 environment can install the project, invoke the
console entry point, and import domain contracts without implementing metrics.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Module and Package Structure,”
“Domain Model,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build-system,
   console script, pytest, coverage, Ruff, and mypy configuration.
2. Create `src/nginx_stream_stats/__init__.py` with the package version surface.
3. Create `src/nginx_stream_stats/models.py` with typed dataclasses
   `LogRecord`, `RankedCount`, `HourBucket`, and immutable `AnalysisReport`.
4. Create `src/nginx_stream_stats/errors.py` with typed usage, input/data,
   cardinality, and internal failure categories; cardinality maps only to 4.
5. Create `src/nginx_stream_stats/cli.py` with a Click entry-point shell and
   help/version behavior; do not add analysis logic here.
6. Create `tests/unit/test_models.py` and `tests/integration/test_cli_smoke.py`.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-stats --help`
- `.venv/bin/nginx-stream-stats --version`
- `.venv/bin/python -m pytest tests/unit/test_models.py tests/integration/test_cli_smoke.py -q`
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`

**Commit:** `step-1: establish package and domain contracts`

## STEP 2: Implement and validate combined-log streaming parser

**Goal:** Combined-format binary lines become validated `LogRecord` instances,
and failures carry safe reasons and line numbers without raw log content.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Inputs,” “Domain Model,”
“Processing Semantics,” and “Security and Privacy Boundaries”; PRD US-1/US-8.

**Tasks:**

1. Create `src/nginx_stream_stats/parser.py` with a compiled/scanner-based
   combined-format parser, UTF-8 handling, timestamp validation, status bounds,
   request-line extraction, and query-free URL normalization.
2. Create `src/nginx_stream_stats/inputs.py` with context-managed file/stdin
   binary iterators and correct ownership (never close caller-owned stdin).
3. Create safe parse-reason codes in `src/nginx_stream_stats/errors.py`.
4. Add valid, IPv4, IPv6, escaped-quote, unknown User-Agent, absolute-target,
   malformed, decode-error, and blank-line fixtures under `tests/fixtures/`.
5. Create `tests/unit/test_parser.py`, `tests/unit/test_inputs.py`, and
   `tests/unit/test_url_normalization.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/unit/test_parser.py tests/unit/test_inputs.py tests/unit/test_url_normalization.py -q`
- `.venv/bin/python -m pytest tests/unit/test_parser.py --cov=nginx_stream_stats.parser --cov-fail-under=95 -q`
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`

**Commit:** `step-2: parse nginx combined logs safely`

## STEP 3: Build the one-pass core traffic aggregations

**Goal:** One iterator pass produces exact valid/malformed totals, top IPs, top
error URLs, and 24 hourly request counts with deterministic ranking.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Processing Semantics” and “Performance
and Resource Contract”; PRD US-2, US-3, and US-4.

**Tasks:**

1. Create `src/nginx_stream_stats/aggregator.py` with `StreamingAggregator` and
   fixed 24-hour counters.
2. Count all valid IPs and statuses 400–599 by normalized path; exclude other
   statuses from error URL ranking.
3. Implement top-10 sorting by count descending then key ascending.
4. Keep parser records ephemeral and expose only `AnalysisReport` on finalize.
5. Create `tests/unit/test_aggregator_rankings.py` and
   `tests/unit/test_hour_buckets.py` with tie, boundary, and empty-hour cases.

**Verification:**

- `.venv/bin/python -m pytest tests/unit/test_aggregator_rankings.py tests/unit/test_hour_buckets.py -q`
- `.venv/bin/python -m pytest tests/unit --cov=nginx_stream_stats.aggregator --cov-fail-under=95 -q`
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`

**Commit:** `step-3: aggregate core traffic metrics`

## STEP 4: Add exact User-Agent share and cardinality guardrails

**Goal:** The final report computes all percentage metrics exactly and stops
safely with code 4 before any exact distinct collection exceeds its bound.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` ADR-002 and “Outputs”; PRD US-4/US-5.

**Tasks:**

1. Extend `src/nginx_stream_stats/aggregator.py` with the exact User-Agent set
   and per-domain `max_cardinality` insertion checks for IP, error URL, and UA.
2. Implement hourly percentages using the literal formula
   `100 × hourly_request_count / total_valid_requests`.
3. Implement UA share as
   `100 × unique_user_agent_count / total_valid_requests`.
4. Reject zero-valid finalization as a data error (code 3) and cardinality
   exhaustion as its distinct typed error (code 4).
5. Create `tests/unit/test_user_agents.py`,
   `tests/unit/test_percentages.py`, and `tests/unit/test_cardinality.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/unit/test_user_agents.py tests/unit/test_percentages.py tests/unit/test_cardinality.py -q`
- `.venv/bin/python -m pytest tests/unit/test_cardinality.py -q` verifies the insertion at the limit succeeds and the next new key raises the code-4 category
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`

**Commit:** `step-4: bound exact cardinality metrics`

## STEP 5: Implement text, JSON, and CSV renderers

**Goal:** One immutable report renders as readable Rich text or stable,
pipeline-safe JSON/CSV without duplicating metric logic.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and ADR-003; PRD US-6/US-7.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/__init__.py` with renderer protocol
   selection but no CLI parsing.
2. Create `src/nginx_stream_stats/renderers/text.py` with summary and tables,
   TTY/`NO_COLOR` behavior, and Rich markup disabled for untrusted values.
3. Create `src/nginx_stream_stats/renderers/json.py` with schema version 1,
   deterministic key/list ordering, six-decimal percentage serialization, and
   one trailing newline.
4. Create `src/nginx_stream_stats/renderers/csv.py` with the documented header,
   summary/top/hour rows, standard CSV quoting, and all 24 hours.
5. Create `tests/unit/test_text_renderer.py`,
   `tests/unit/test_json_renderer.py`, and `tests/unit/test_csv_renderer.py`.
6. Add golden files under `tests/fixtures/expected/` for all three formats.

**Verification:**

- `.venv/bin/python -m pytest tests/unit/test_text_renderer.py tests/unit/test_json_renderer.py tests/unit/test_csv_renderer.py -q`
- `.venv/bin/python -m pytest tests/unit --cov=nginx_stream_stats.renderers --cov-fail-under=90 -q`
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`

**Commit:** `step-5: render stable text json and csv reports`

## STEP 6: Integrate the complete CLI and exit contract

**Goal:** The installed command connects input, parser, aggregator, and renderer
while keeping stdout clean and implementing codes `0/1/2/3/4` exactly.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; PRD US-1, US-7, US-8.

**Tasks:**

1. Complete `src/nginx_stream_stats/cli.py` with optional `INPUT`, `--json`,
   `--csv`, `--strict`, `--max-cardinality`, color, help, and version options.
2. Validate mutual exclusion and positive limits as usage/configuration code 2.
3. Map success to 0, unexpected runtime/output failures to 1, usage/config to
   2, input/log-data failures to 3, and unique-cardinality exhaustion to 4.
4. Handle broken downstream pipes as quiet success and keep stderr diagnostics
   out of JSON/CSV stdout.
5. Create `tests/integration/test_cli_inputs.py`,
   `tests/integration/test_cli_outputs.py`, and
   `tests/integration/test_exit_codes.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/integration -q`
- `.venv/bin/python -m pytest tests/integration/test_exit_codes.py -q` covers each of `0/1/2/3/4` and asserts empty stdout for failures 2/3/4
- `.venv/bin/nginx-stream-stats --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-stream-stats --csv tests/fixtures/combined.log | .venv/bin/python -c 'import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert rows'`
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`

**Commit:** `step-6: integrate cli and all exit codes`

## STEP 7: Prove correctness, security boundaries, and performance

**Goal:** Release gates demonstrate contract coverage and the representative
1 GB workload completes under 30 seconds on a recorded laptop baseline.

**Time:** ~2.5 hours

**Context:** `STRATEGIC_PLAN.md` KPIs/DoD; `PROJECT_ARCHITECTURE.md` performance,
security, and verification sections; all P0 PRD acceptance criteria.

**Tasks:**

1. Create `tests/integration/test_file_stdin_parity.py` and
   `tests/integration/test_machine_output_cleanliness.py`.
2. Create `tests/unit/test_untrusted_output.py` with ANSI, Rich markup,
   spreadsheet-formula-like, quote, comma, and newline-bearing values.
3. Create `tests/performance/generate_fixture.py` as a deterministic generator
   for a representative 1 GB file with realistic field lengths/cardinalities.
4. Create `tests/performance/benchmark_1gb.py` to record fixture digest,
   environment, elapsed wall time, peak RSS, valid count, and exit status.
5. Create `docs/PERFORMANCE_BASELINE.md` from an actual run; never prefill a
   passing number.
6. Run coverage and profile the parser only if the measured gate fails; permit
   one behavior-preserving optimization cycle.

**Verification:**

- `.venv/bin/python -m pytest -q --cov=nginx_stream_stats --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python tests/performance/generate_fixture.py --size-gib 1 --output .bench/representative-1gb.log`
- `.venv/bin/python tests/performance/benchmark_1gb.py --input .bench/representative-1gb.log --max-seconds 30 --report docs/PERFORMANCE_BASELINE.md`
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`

**Commit:** `step-7: verify correctness and one-gigabyte performance`

## STEP 8: Build, install, document, and optionally add gzip input

**Goal:** A clean Python 3.11 environment installs the wheel, matches README
examples, and is ready for an open-source release; gzip is included only if all
P0 gates are already green.

**Time:** ~1.5 hours P0, plus ~1 hour optional P1

**Context:** `PROJECT_ARCHITECTURE.md` packaging section; PRD release criteria
and US-9; `README.md` target quick start.

**Tasks:**

1. Finalize `README.md` with install, file/stdin, text/JSON/CSV examples,
   schemas, full exit code table, limitations, benchmark baseline, and license.
2. Add `LICENSE` with an approved permissive open-source license and update
   `pyproject.toml` metadata/classifiers.
3. Create `tests/integration/test_installed_wheel.py` or a shell-free test
   helper that installs the built wheel in a temporary virtual environment.
4. Build sdist/wheel using `python -m build`, inspect metadata, and smoke-test
   the installed console command against a fixture.
5. If and only if P0 is complete, extend `src/nginx_stream_stats/inputs.py` and
   `tests/integration/test_gzip_input.py` for streaming `.gz` paths and corrupt
   gzip exit code 3.
6. Re-run all gates, including explicit `0/1/2/3/4` integration coverage and
   the release performance command after any gzip-related refactor.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/python -m pytest -q --cov=nginx_stream_stats --cov-fail-under=90`
- `.venv/bin/python -m pytest tests/integration/test_exit_codes.py tests/integration/test_installed_wheel.py -q`
- `.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src`
- `python3.11 -m venv .release-venv && .release-venv/bin/python -m pip install dist/*.whl && .release-venv/bin/nginx-stream-stats --json tests/fixtures/combined.log`
- `.release-venv/bin/python -m json.tool < <(.release-venv/bin/nginx-stream-stats --json tests/fixtures/combined.log) >/dev/null`

**Commit:** `step-8: package and document the verified cli`

## Completion Checklist

- [ ] P0 stories US-1 through US-8 meet every acceptance criterion.
- [ ] Codes `0/1/2/3/4` have black-box integration evidence; code 4 means only
  unique-cardinality exhaustion.
- [ ] File and stdin metrics match; text, JSON, and CSV share one report model.
- [ ] The recorded representative 1 GB run is under 30 seconds.
- [ ] Clean wheel install and console-command smoke test pass on Python 3.11.
- [ ] No database, HTTP API, auth, server, cloud, Docker, or Kubernetes assets
  entered the change set.
- [ ] Docs contain no placeholder claims and reflect actual measured evidence.

## Rollback and Scope Control

Each step is a dependency-complete commit. If a step fails its checks, fix or
revert that step before continuing. Drop optional gzip and all P2 work first.
Do not trade exact metric definitions, output schemas, cardinality exit code 4,
or the performance release gate for extra features.
