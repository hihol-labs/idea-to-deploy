# Implementation Plan: nginx-stream-report

## Plan Contract

This is a planning artifact; it does not authorize product-code implementation. Steps are ordered by dependencies and RICE value. Each step names the files an implementer should create and the evidence needed before proceeding. The complete exit contract applies throughout: `0` success, `1` internal/output failure, `2` CLI usage failure, `3` input/open/read/decode failure, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, treated as code 1, or remapped.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Packaging and console entry point | Establishes install/import boundaries and Python 3.11 constraint | 1 hour |
| 2 | Golden combined-log fixtures and output schemas | Freezes observable behavior before implementation | 1 hour |
| 3 | Benchmark fixture generator and protocol | Prevents late discovery of performance failure | 1 hour |
| 4 | Test/lint configuration | Enables evidence for every subsequent slice | 1 hour |

## Step 1: Freeze package and interface contracts

**Goal:** An installable skeleton exposes help/version and all options with no analytics behavior.

**Time:** ~1.5 hours.

**Context:** `PROJECT_ARCHITECTURE.md` → `CLI Interface`, `Packaging and Deployment`.

**Files:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, test extras, and the console entry point.
2. Create `src/nginx_stream_report/__init__.py` and `src/nginx_stream_report/cli.py` with only interface wiring.
3. Create `src/nginx_stream_report/errors.py` with named domain errors and the full exit mapping.
4. Create `tests/test_cli_contract.py` for help, version, conflicts, invalid limits, and status 2.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `nginx-stream-report --help`

**Commit:** `step-1: freeze package and CLI contracts`

## Step 2: Implement the combined-log parser

**Goal:** Individual UTF-8 text lines become validated immutable records or typed invalid results.

**Time:** ~2 hours.

**Context:** `PROJECT_ARCHITECTURE.md` → `Input record contract`, `Data Model and State Bounds`.

**Files:**

1. Create `src/nginx_stream_report/models.py` with frozen `AccessRecord` and report dataclasses.
2. Create `src/nginx_stream_report/parser.py` with a once-compiled standard-combined grammar and timezone-aware timestamp parsing.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with documented expected classifications.
4. Create `tests/test_parser.py` for quoting, Unicode text, IPv4/IPv6 strings, timestamps, status bounds, and malformed lines.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_report.parser --cov-fail-under=90`

**Commit:** `step-2: parse standard nginx combined logs`

## Step 3: Build streaming aggregation and cardinality safety

**Goal:** One-pass aggregation produces exact counters, 24 hour buckets, and bounded exact User-Agent state.

**Time:** ~2.5 hours.

**Context:** `PROJECT_ARCHITECTURE.md` → `Metric semantics`, `Parsing and Processing Sequence`.

**Files:**

1. Create `src/nginx_stream_report/aggregate.py` with `consume` and immutable `finalize` operations.
2. Extend `src/nginx_stream_report/models.py` with `RankedCount`, `HourlyBucket`, `UserAgentSummary`, and `Report`.
3. Extend `src/nginx_stream_report/errors.py` with `UniqueCardinalityExhausted` mapped only to 4.
4. Create `tests/test_aggregate.py` for ranking ties, 400/599 boundaries, the literal formula `100 × hourly_request_count / total_valid_requests`, zero input, duplicates at the limit, and first new value beyond the limit.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `PYTHONHASHSEED=random python3.11 -m pytest tests/test_aggregate.py -q`

**Commit:** `step-3: aggregate metrics with cardinality guard`

## Step 4: Add colored terminal rendering

**Goal:** Default output is a safe, readable four-section Rich report with correct TTY color behavior.

**Time:** ~1.5 hours.

**Context:** `PROJECT_ARCHITECTURE.md` → `Output contracts`, `Failure, Security, and Privacy Model`.

**Files:**

1. Create `src/nginx_stream_report/renderers/__init__.py` and `src/nginx_stream_report/renderers/text.py`.
2. Create `tests/golden/report.txt` and `tests/test_text_renderer.py` for order, zero values, escaping, and color/no-color behavior.
3. Wire the renderer selection in `src/nginx_stream_report/cli.py` without adding parsing logic there.

**Verification:**

- `python3.11 -m pytest tests/test_text_renderer.py -q`
- `nginx-stream-report --no-color tests/fixtures/combined.log`

**Commit:** `step-4: render terminal report safely`

## Step 5: Add deterministic JSON output

**Goal:** `--json` emits one schema-version-1 object with no diagnostic contamination.

**Time:** ~1.5 hours.

**Context:** `PROJECT_ARCHITECTURE.md` → `Output contracts`.

**Files:**

1. Create `src/nginx_stream_report/renderers/json.py` using the shared `Report` only.
2. Create `tests/golden/report.json` and `tests/test_json_renderer.py` for schema, ordering, escaping, finite numbers, and two-decimal percentages.
3. Extend `tests/test_cli_contract.py` to assert stdout/stderr separation and absence of ANSI sequences.

**Verification:**

- `python3.11 -m pytest tests/test_json_renderer.py tests/test_cli_contract.py -q`
- `nginx-stream-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add JSON schema v1 output`

## Step 6: Add deterministic CSV output

**Goal:** `--csv` emits the documented normalized record stream with safe escaping.

**Time:** ~1.5 hours.

**Context:** `PROJECT_ARCHITECTURE.md` → `Output contracts`, CSV security note.

**Files:**

1. Create `src/nginx_stream_report/renderers/csv.py` with standard-library CSV serialization and formula-cell neutralization.
2. Create `tests/golden/report.csv` and `tests/test_csv_renderer.py` for header, row types/order, CRLF, quoting, Unicode, and formula-leading values.
3. Extend `src/nginx_stream_report/cli.py` to select exactly one renderer.

**Verification:**

- `python3.11 -m pytest tests/test_csv_renderer.py tests/test_cli_contract.py -q`
- `nginx-stream-report --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.reader(sys.stdin))'`

**Commit:** `step-6: add pipeline-safe CSV output`

## Step 7: Complete streaming I/O and failure semantics

**Goal:** File/stdin processing, diagnostics, atomic machine output, and all five exit statuses work end to end.

**Time:** ~2 hours.

**Context:** `PROJECT_ARCHITECTURE.md` → entire `CLI Interface` and `Failure, Security, and Privacy Model`.

**Files:**

1. Complete `src/nginx_stream_report/cli.py` with stream ownership, strict UTF-8 reading, invalid-line accounting, deferred rendering, and exception mapping.
2. Create `tests/test_cli_integration.py` covering paths, omitted stdin, `-`, empty/all-invalid input, read/decode failure, simulated writer failure, and cardinality exhaustion.
3. Add fixtures under `tests/fixtures/` for invalid UTF-8 and cardinality limits.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py -q`
- `python3.11 -m pytest -q` and assert explicit cases for `0/1/2/3/4`

**Commit:** `step-7: enforce streaming and complete exit semantics`

## Step 8: Benchmark, harden, and package

**Goal:** The candidate satisfies correctness, security, installation, and 1 GB performance release gates.

**Time:** ~3 hours plus benchmark runtime.

**Context:** `STRATEGIC_PLAN.md` → `Definition of Done`; `PRD.md` → `Non-Functional Requirements`.

**Files:**

1. Create `bench/generate_log.py` as a deterministic fixture generator and `bench/README.md` with baseline-machine recording rules.
2. Create `tests/test_package.py` for wheel install/console entry behavior.
3. Update `README.md` with verified install, examples, supported grammar, metrics, exit codes, and benchmark results.
4. Add `.github/workflows/ci.yml` for Python 3.11 tests, lint/type checks if selected, build, and artifact smoke test.

**Verification:**

- `python3.11 -m pytest --cov=nginx_stream_report --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 bench/generate_log.py --bytes 1073741824 --output /tmp/nginx-stream-report-1gb.log`
- `/usr/bin/time -v nginx-stream-report --json /tmp/nginx-stream-report-1gb.log >/dev/null` and record wall time under 30 seconds plus peak RSS and machine details

**Commit:** `step-8: verify performance and release package`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable interface and trustworthy parser | ~3.5 hours |
| Saturday PM | 3–4 | All metrics and terminal experience | ~4 hours |
| Sunday AM | 5–7 | Machine formats and end-to-end failures | ~5 hours |
| Sunday PM | 8 | Benchmark, hardening, packaging, docs | ~3 hours |

## Release Evidence Checklist

- [ ] Parser, aggregate, renderer, and CLI suites pass on Python 3.11.
- [ ] Golden results agree across text, JSON, and CSV.
- [ ] Explicit integration cases demonstrate `0/1/2/3/4`, including code 4 for unique-cardinality exhaustion.
- [ ] Wheel install and console entry point work in a clean environment.
- [ ] Coverage meets the 90% target for core modules.
- [ ] The 1 GB benchmark evidence records wall time under 30 seconds and peak RSS on the named laptop.
- [ ] Documentation reflects implemented behavior; deferred P1/P2 work is not presented as shipped.
