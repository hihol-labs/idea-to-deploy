# Implementation Plan: Nginx Stream Analytics CLI

## 1. Scope and Delivery Rule

This plan implements only the P0 local Python 3.11 CLI in `PRD.md`. Each step must end with its listed verification evidence before the next begins (WIP=1). No database, HTTP API, authentication, server, cloud, Docker, or Kubernetes work is authorized.

The complete exit-code contract applies throughout: `0` success/help/version; `1` unexpected internal/runtime failure; `2` CLI usage or unreadable input; `3` decode/parse failure; `4` unique-cardinality exhaustion. Code 4 must remain dedicated to exact IP, error-URL, or User-Agent cardinality ceiling failure.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and console entry point | Every CLI and clean-install check depends on import/install structure | 1 h |
| 2 | Domain/error contracts | Parser, aggregator, and renderers need shared types and stable exits | 1 h |
| 3 | Representative fixtures and test configuration | Correctness needs executable examples before implementation | 1 h |
| 4 | Performance fixture specification | Prevents unverifiable performance claims late in delivery | 0.5 h |

## Step 1: Freeze Packaging and Public Contracts

**Goal:** A Python 3.11 package skeleton can be built and exposes a placeholder-free console entry point contract.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4 and 10; `PRD.md` FR-01 and NFR-03.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, test/lint extras, build backend, and `nginx-stream-analytics` console script.
2. Create `src/nginx_stream_analytics/__init__.py` with package version access.
3. Create `src/nginx_stream_analytics/cli.py` with the Click command signature from the CLI contract; defer behavior behind typed interfaces rather than fake output.
4. Create `tests/test_packaging.py` to verify import metadata and the console entry point.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m build`
- `python3.11 -m pytest tests/test_packaging.py`
- `nginx-stream-analytics --help`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: Define Models, Errors, and Fixtures

**Goal:** Shared immutable data models and all five exit meanings are executable test contracts.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4, 8, and `## CLI Interface`; `PRD.md` failure criteria.

**Tasks:**

1. Create `src/nginx_stream_analytics/models.py` with frozen `LogRecord`, `RankedMetric`, and `AnalysisReport` dataclasses.
2. Create `src/nginx_stream_analytics/errors.py` with parse, input, cardinality, and internal error boundaries plus centralized mapping to `0/1/2/3/4`.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, `tests/fixtures/empty.log`, and an invalid-UTF-8 binary fixture with manually enumerated expected metrics.
4. Create `tests/test_models.py` and `tests/test_errors.py`, including the invariant that exit 4 means only unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_models.py tests/test_errors.py -q`
- `python3.11 -m mypy src/nginx_stream_analytics/models.py src/nginx_stream_analytics/errors.py`

**Commit:** `step-2: define domain and failure contracts`

## Step 3: Implement Combined Log Parser

**Goal:** Each valid physical line becomes exactly one immutable record; invalid data fails at the correct line.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 5; `PRD.md` FR-02.

**Tasks:**

1. Create `src/nginx_stream_analytics/parser.py` with one compiled Combined Log Format expression, strict status/timestamp parsing, and an iterator accepting a text stream.
2. Create `tests/test_parser.py` for IPv4/IPv6, spaces and escapes in User-Agent, queries, timezone offsets, absent fields, invalid status/timestamp/request, malformed line numbers, empty input, and invalid UTF-8 at the input boundary.
3. Ensure parsed source timezone is retained and machine-local timezone does not alter the source hour.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `TZ=UTC python3.11 -m pytest tests/test_parser.py -q`
- `TZ=Pacific/Auckland python3.11 -m pytest tests/test_parser.py -q`

**Commit:** `step-3: parse combined nginx logs deterministically`

## Step 4: Implement Streaming Aggregation and Cardinality Guard

**Goal:** One pass produces exact, deterministic metrics while bounded distinct-key state fails closed.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4–6 and ADR-002; `PRD.md` FR-03 through FR-07 and FR-09.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with `StreamingAggregator.consume()` and `finalize()`.
2. Count all valid requests by IP/hour/User-Agent and only statuses 400–599 by URL.
3. Enforce `--max-unique` independently before adding a new key to each exact structure and raise the typed code-4 error without returning a report.
4. Create `tests/test_aggregate.py` for deterministic ties, fewer/more than ten keys, all status classes, 24 hours, empty input, exact percentages, and each collection's exhaustion boundary.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_analytics.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: aggregate exact streaming metrics`

## Step 5: Implement Three Renderers

**Goal:** One report produces equivalent colored terminal, JSON, and CSV representations.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4 and `## CLI Interface`; `PRD.md` output acceptance criteria.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/terminal.py` with four Rich sections, safe log-derived text, and `auto|always|never` color.
2. Create `src/nginx_stream_analytics/renderers/json.py` with schema `1.0`, ordered 24-hour array, and numeric percentage points.
3. Create `src/nginx_stream_analytics/renderers/csv.py` with long-form `report,rank,key,count,percentage` rows through the standard `csv` module.
4. Create `tests/test_renderers.py` to parse JSON/CSV back and compare every value against the report model; assert no ANSI in structured formats.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest tests/test_renderers.py --cov=nginx_stream_analytics.renderers --cov-branch --cov-fail-under=90`

**Commit:** `step-5: render equivalent terminal json and csv reports`

## Step 6: Integrate CLI and Exit Semantics

**Goal:** File/stdin analysis, options, stream separation, and every exit code work end to end.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` and Section 8; `PRD.md` FR-01, FR-08, FR-10.

**Tasks:**

1. Complete `src/nginx_stream_analytics/cli.py` orchestration and resource cleanup.
2. Add `--json`, `--csv`, `--color`, `--max-unique`, `--version`, input path, and stdin behavior exactly as specified.
3. Ensure report data uses stdout, diagnostics use stderr, expected failures omit tracebacks, parse/cardinality errors emit no partial report, and broken pipes finish cleanly.
4. Create `tests/test_cli.py` using Click's runner and subprocess tests for file/stdin equivalence and codes `0/1/2/3/4`.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-analytics tests/fixtures/combined.log --json | python3.11 -m json.tool >/dev/null`
- `nginx-stream-analytics --json --csv tests/fixtures/combined.log; test $? -eq 2`

**Commit:** `step-6: integrate CLI streams options and exits`

## Step 7: Validate Performance and Resource Bounds

**Goal:** Reproducible evidence proves or falsifies the 1 GB/30 s target and cardinality behavior.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 6; `PRD.md` NFR-01/NFR-02.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate a content-described 1 GB valid fixture outside the repository.
2. Create `benchmarks/run.py` to record command, fixture size/hash, Python/platform/CPU/storage context, wall time, throughput, and peak RSS without importing test-side shortcuts.
3. Create `tests/test_performance.py` for a small CI-sized streaming regression threshold and a marker for the manual 1 GB gate.
4. Profile only if the gate fails; optimize the measured bottleneck without changing parser/output contracts.

**Verification:**

- `python3.11 benchmarks/generate_log.py --size-bytes 1073741824 --output /tmp/nginx-stream-analytics-1gb.log`
- `python3.11 benchmarks/run.py --input /tmp/nginx-stream-analytics-1gb.log --runs 3 --max-seconds 30`
- `python3.11 -m pytest tests/test_performance.py -q`

**Commit:** `step-7: verify throughput and bounded cardinality`

## Step 8: Release Quality and Handoff

**Goal:** The exact candidate is installable, documented, tested, and ready for a tagged open-source release.

**Time:** ~3 hours

**Context:** all architecture sections; all P0 acceptance criteria; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Update `README.md` with actual install, examples, format schemas, supported log format, privacy warning, and exit table.
2. Add `LICENSE`, `CHANGELOG.md`, and CI configuration for Python 3.11 lint/type/test/build checks.
3. Run security/license audits and remove undeclared or unused dependencies.
4. Build wheel/sdist, install the wheel into a fresh environment, and exercise help/version plus file/stdin across terminal/JSON/CSV.
5. Freeze and adjudicate the exact release candidate through the repository's Verification Loop before accepting completion.

**Verification:**

- `python3.11 -m ruff check . && python3.11 -m mypy src && python3.11 -m pytest --cov=nginx_stream_analytics --cov-branch --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m pip install --force-reinstall dist/*.whl && nginx-stream-analytics --version`

**Commit:** `step-8: complete release verification and handoff`

## Sprint Boundaries

The one-weekend constraint uses short delivery blocks rather than multi-week sprints.

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Friday | 1–2 | Package, models, errors, fixtures | ~3.5 h |
| Saturday morning | 3–4 | Correct parser and streaming metrics | ~6 h |
| Saturday afternoon | 5–6 | Formats and integrated CLI | ~6 h |
| Sunday | 7–8 | Performance, quality, packaging, handoff | ~6 h |

## Requirement Traceability

| Requirement group | Steps |
|---|---|
| Input and parsing (FR-01–03) | 1–4, 6 |
| Four analytics (FR-04–07) | 4–5 |
| Formats and cardinality (FR-08–10) | 2, 4–6 |
| Performance/install/security (NFR-01–06) | 1, 3–8 |

P1/P2 features remain excluded until the MVP gates pass and the PRD is deliberately revised.
