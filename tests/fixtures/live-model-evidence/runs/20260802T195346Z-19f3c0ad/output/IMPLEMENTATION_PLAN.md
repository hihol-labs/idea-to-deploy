# Implementation Plan: nginx-log-report

This plan delivers the P0 scope in [PRD.md](PRD.md) using the decisions in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). It contains nine dependency-ordered steps sized for one weekend. Product code is not part of this blueprint; paths below describe future work.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` and `src/` package skeleton | Every test and feature needs an installable import/CLI boundary | 1 h |
| 2 | Typed domain and error contracts | Parser, aggregator, and renderers need stable interfaces | 1 h |
| 3 | Fixed representative and benchmark fixtures | Correctness and the 30-second target need reproducible evidence | 1 h |

There is no database schema, auth system, API framework, Docker environment, or deployment pipeline runway because the architecture explicitly excludes those systems.

## Step 1: Package and CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the project and invoke a Click command with help/version behavior.

**Time:** ~1 hour

**Context:** Architecture sections 3, CLI Interface, and 10.

**Tasks:**

1. Create `pyproject.toml` with Python bounds, Click/Rich dependencies, build metadata, and `nginx-log-report` entry point.
2. Create `src/nginx_log_report/__init__.py`, `src/nginx_log_report/__main__.py`, and `src/nginx_log_report/cli.py`.
3. Create `tests/test_cli.py` for `--help`, `--version`, invalid option combinations, and `--top` bounds.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-log-report --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Domain Models and Error Contract

**Goal:** Parser, aggregation, and reporting boundaries have typed immutable records and explicit error mapping.

**Time:** ~1 hour

**Context:** Architecture sections 4 and CLI Interface exit codes.

**Tasks:**

1. Create `src/nginx_log_report/models.py` with `AccessRecord`, `RankedItem`, and `ReportSnapshot` dataclasses.
2. Create `src/nginx_log_report/errors.py` with input/no-valid-record domain exceptions and exit constants.
3. Create `tests/test_models.py` to check invariants, tuple snapshots, and zero/invalid values.

**Verification:**

- `python3.11 -m pytest tests/test_models.py -q`
- `python3.11 -m mypy src/nginx_log_report`

**Commit:** `step-2: define domain and exit contracts`

## Step 3: Streaming Combined-Log Parser

**Goal:** Valid nginx combined-format lines become `AccessRecord` values without loading the input file.

**Time:** ~2 hours

**Context:** Architecture sections 5 and 8; PRD FR-1 and FR-2.

**Tasks:**

1. Create `src/nginx_log_report/parser.py` with a linear field scanner and timestamp/status validation.
2. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` covering IPv4, IPv6, escapes, Unicode, `-` request, and invalid fields.
3. Create `tests/test_parser.py` for valid records, malformed outcomes, raw-byte identity/presentation mapping, and adversarial long fields.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --durations=5 -q`

**Commit:** `step-3: parse nginx combined logs incrementally`

## Step 4: Exact Streaming Aggregation

**Goal:** One pass computes deterministic IP/error rankings, 24 hour buckets, and exact User-Agent diversity.

**Time:** ~2 hours

**Context:** Architecture sections 3, 4, and 7; PRD FR-3 through FR-6.

**Tasks:**

1. Create `src/nginx_log_report/aggregate.py` with counter/set updates and snapshot finalization.
2. Create `tests/test_aggregate.py` for 399/400/499/500/599/600 boundaries, top-N ties, all hours, empty UA, and exact share math.
3. Add `tests/fixtures/known-report.log` with a hand-calculated expected snapshot.
4. Create `scripts/generate_benchmark_log.py` and freeze `tests/performance/corpus-manifest.json` with both corpus profiles, content hashes, cardinalities, and expected snapshot hashes before renderer work begins.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_log_report.aggregate --cov-fail-under=95 -q`
- `python3.11 scripts/generate_benchmark_log.py --profile representative --bytes 1000000000 /tmp/nginx-1gb.log --verify-manifest tests/performance/corpus-manifest.json`

**Commit:** `step-4: implement exact report aggregation`

## Step 5: Terminal Renderer

**Goal:** Default output is a readable, TTY-aware Rich report whose meaning does not depend on color.

**Time:** ~1.5 hours

**Context:** Architecture CLI Interface default output and section 8; PRD FR-7.

**Tasks:**

1. Create `src/nginx_log_report/renderers/__init__.py` and `src/nginx_log_report/renderers/text.py`.
2. Escape untrusted log values and implement title, summary, rankings, hourly rows, and User-Agent summary.
3. Create `tests/test_text_renderer.py` with terminal/non-terminal golden output and Rich-markup/control-character cases.

**Verification:**

- `python3.11 -m pytest tests/test_text_renderer.py -q`
- `NO_COLOR=1 nginx-log-report tests/fixtures/known-report.log > /tmp/nginx-log-report.txt`

**Commit:** `step-5: render safe colored terminal reports`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive stable schema-versioned JSON or RFC 4180 long-form CSV with no ANSI or diagnostics on stdout.

**Time:** ~2 hours

**Context:** Architecture CLI Interface JSON/CSV contracts; PRD FR-8 and FR-9.

**Tasks:**

1. Create `src/nginx_log_report/renderers/json.py` with the schema-version-1 document.
2. Create `src/nginx_log_report/renderers/csv.py` with the five-column long-form schema.
3. Create `tests/test_json_renderer.py`, `tests/test_csv_renderer.py`, and golden files under `tests/golden/`.

**Verification:**

- `python3.11 -m pytest tests/test_json_renderer.py tests/test_csv_renderer.py -q`
- `nginx-log-report --json tests/fixtures/known-report.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-report --csv tests/fixtures/known-report.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add stable JSON and CSV contracts`

## Step 7: End-to-End Stream and Failure Behavior

**Goal:** File/stdin ownership, malformed-line disclosure, stderr separation, and every exit code work end to end.

**Time:** ~1.5 hours

**Context:** Architecture CLI Interface and section 8; PRD FR-10 and NFR-3.

**Tasks:**

1. Complete `src/nginx_log_report/cli.py` orchestration without closing stdin or emitting partial structured reports.
2. Extend `tests/test_cli.py` for file, `-`, implicit stdin, unreadable path, zero-valid input, SIGINT mapping, and broken pipe.
3. Create `tests/test_end_to_end.py` to assert equivalent semantic results across all three output modes.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py tests/test_end_to_end.py -q`
- `nginx-log-report --json tests/fixtures/malformed.log >/tmp/report.json 2>/tmp/report.err; test $? -eq 4`

**Commit:** `step-7: enforce stream and exit-code behavior`

## Step 8: Performance and Robustness Gate

**Goal:** The exact release candidate processes the frozen decimal 1 GB corpus in under 30 seconds and <=2.0 GiB RSS on the recorded reference laptop, passes the <=3.0 GiB high-cardinality gate, and survives hostile text safely.

**Time:** ~2 hours

**Context:** Architecture sections 8, 9, and 11; PRD NFR-1 through NFR-5.

**Tasks:**

1. Finalize `scripts/generate_benchmark_log.py` to deterministically generate, but never commit, the representative and high-cardinality decimal 1 GB logs described by architecture.
2. Create `tests/performance/corpus-manifest.json` with generator version, seed, exact byte count, SHA-256, line/cardinality distribution, and expected snapshot SHA-256 before renderer optimization.
3. Create `tests/performance/test_one_gb.py` as an opt-in benchmark that records median wall time, peak RSS, and environment metadata for both corpora.
4. Create `tests/test_robustness.py` for long fields, control bytes, markup strings, invalid-octet identity, random malformed data, and bounded diagnostic excerpts.
5. Profile and change only measured parser/aggregation hot paths if a target fails.

**Verification:**

- `python3.11 -m pytest tests/test_robustness.py -q`
- `python3.11 scripts/generate_benchmark_log.py --profile representative --bytes 1000000000 /tmp/nginx-1gb.log`
- `python3.11 -m pytest tests/performance/test_one_gb.py --benchmark-log /tmp/nginx-1gb.log -q`

**Commit:** `step-8: meet performance and robustness gates`

## Step 9: Packaging, Documentation, and Release Candidate

**Goal:** A wheel/sdist installs cleanly and the documented examples match actual output and contracts.

**Time:** ~1 hour

**Context:** Architecture sections 10–13; all P0 PRD criteria.

**Tasks:**

1. Finalize `README.md` with real install, stdin/file, JSON, and CSV examples.
2. Add `CHANGELOG.md`, `LICENSE`, and package metadata required for an open-source release.
3. Add `tests/test_packaging.py` or a release script that builds artifacts and smoke-tests the installed console command in a clean venv.
4. Reconcile completion status in `CLAUDE.md` only after all checks pass.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_report --cov-fail-under=85 -q`
- `python3.11 -m ruff check . && python3.11 -m mypy src/nginx_log_report`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-log-report-smoke && /tmp/nginx-log-report-smoke/bin/pip install dist/*.whl && /tmp/nginx-log-report-smoke/bin/nginx-log-report --help`

**Commit:** `step-9: prepare verified release candidate`

## Sprint Boundaries

For the one-weekend constraint, “sprint” means a focused delivery block rather than a calendar week.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Block 1 | 1–3 | Installable boundary, models, parser | ~4 h |
| Block 2 | 4–6 | All report calculations and formats | ~5.5 h |
| Block 3 | 7–9 | Integration, performance, packaging | ~4.5 h |

## Plan Completion Gate

Do not mark the plan complete from individual test output alone. Freeze the exact staged candidate, run the repository's Verification Loop machine oracle, apply its risk-tier checker, and require a current revalidated adjudication receipt as specified by `.itd/VERIFICATION_CONTRACT.json`. Record benchmark hardware, corpus hash, commands, outputs, and the next action in the handoff.
