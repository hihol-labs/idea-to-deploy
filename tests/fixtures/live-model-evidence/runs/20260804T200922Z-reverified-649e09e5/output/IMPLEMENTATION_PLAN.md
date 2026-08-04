# Implementation Plan: Nginx Stream Analytics CLI

## 1. Delivery Rules

This plan implements only the P0 local CLI from `PRD.md`. Preserve WIP=1: finish and verify each step before starting the next. Specifications are source-of-truth; update the relevant document before changing a public behavior. Product code is not part of this blueprint deliverable.

Every implementation step uses Python 3.11 and must preserve this complete exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Success, help, or version |
| `1` | Unexpected internal processing/rendering failure |
| `2` | Invalid CLI usage/options |
| `3` | Input/data failure, including unreadable input or zero valid requests |
| `4` | Unique-cardinality exhaustion; no partial report |

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Packaging and quality-tool configuration | Every later check needs an installable, repeatable environment | 1.0 h |
| 2 | Dataclasses, domain errors, and exit constants | Parser, aggregation, renderers, and CLI need one stable vocabulary | 1.0 h |
| 3 | Representative fixtures and benchmark generator | Correctness and performance require reproducible inputs before features | 1.0 h |

No database schema, authentication system, API framework, Docker setup, or deployment pipeline belongs in the runway because the architecture intentionally has none.

## STEP 1: Package and quality skeleton

**Goal:** a clean environment can install the package and invoke a placeholder-free Click command boundary.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 7; `PRD.md` FR-09/FR-10.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, console script, build backend, pytest, Ruff, mypy, and coverage configuration.
2. Create `src/nginx_stream_report/__init__.py`, `src/nginx_stream_report/cli.py`, and `tests/test_cli.py`.
3. Pin the package version source and verify that help/version are stdout-only successes.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-report --help && nginx-stream-report --version`

**Commit:** `step-1: establish installable CLI package`

## STEP 2: Domain models and failure taxonomy

**Goal:** all layers share typed immutable report models and one `0/1/2/3/4` mapping.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `AccessRecord`, ranking rows, hourly rows, summary, and `Report` dataclasses.
2. Create `src/nginx_stream_report/errors.py` with typed internal, input/data, and cardinality failures plus exit constants 0–4.
3. Create `tests/test_models.py` to assert invariants and immutable renderer inputs.

**Verification:**

- `python3.11 -m pytest tests/test_models.py -q`
- `python3.11 -m mypy src/nginx_stream_report/models.py src/nginx_stream_report/errors.py`

**Commit:** `step-2: define report model and exits`

## STEP 3: Combined-log parser and input stream

**Goal:** files and stdin yield validated records without retaining source lines.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 6, and 8; `PRD.md` US-01, US-06, US-07.

**Tasks:**

1. Create `src/nginx_stream_report/input.py` for ordered lazy sources, deterministic closing, stdin-at-most-once validation, and contextual read errors.
2. Create `src/nginx_stream_report/parser.py` with one compiled combined-log pattern, timezone-aware timestamp parsing, field validation, and malformed result signaling.
3. Add representative valid, malformed, quoting, IPv4, and IPv6 cases under `tests/fixtures/`.
4. Create `tests/test_parser.py` and `tests/test_input.py`.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_input.py -q`
- `python3.11 -m ruff check src/nginx_stream_report/input.py src/nginx_stream_report/parser.py tests/test_parser.py tests/test_input.py`

**Commit:** `step-3: stream and parse combined logs`

## STEP 4: Exact aggregation and cardinality guard

**Goal:** one pass produces exact counts, percentages, deterministic rankings, and safe resource failure.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 6, and 8; `PRD.md` US-02 through US-04 and US-07.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with IP/error counters, 24 hourly counters, User-Agent set, total/valid/malformed counts, and report finalization.
2. Check combined newly admitted distinct IP/URL/User-Agent keys against `--max-cardinality` before mutation and raise the typed exit-4 failure.
3. Implement deterministic top selection and the exact formulas from the architecture.
4. Create `tests/test_aggregate.py` for status boundaries, ties, all hours, malformed exclusion, percentage denominators, empty agents, and the limit boundary.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q --cov=nginx_stream_report.aggregate --cov-branch --cov-fail-under=90`
- `python3.11 -m mypy src/nginx_stream_report/aggregate.py`

**Commit:** `step-4: aggregate exact metrics safely`

## STEP 5: Rich terminal renderer

**Goal:** default output is a readable four-section report whose values cannot inject markup.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and section 8; `PRD.md` US-01.

**Tasks:**

1. Create `src/nginx_stream_report/render/__init__.py` and `render/text.py`.
2. Render summary, two rankings, all 24 hourly buckets, and User-Agent share with two-decimal percentages.
3. Implement `auto|always|never` color behavior and escape untrusted log values.
4. Add text golden cases to `tests/test_renderers.py`.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q -k text`
- `NO_COLOR=1 nginx-stream-report tests/fixtures/combined.log | python3.11 -c 'import sys; assert "\x1b[" not in sys.stdin.read()'`

**Commit:** `step-5: render safe terminal report`

## STEP 6: JSON and CSV renderers

**Goal:** pipelines receive versioned, uncolored, deterministic machine formats.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface output schemas; `PRD.md` US-05.

**Tasks:**

1. Create `src/nginx_stream_report/render/json.py` for the complete schema-version-1 document.
2. Create `src/nginx_stream_report/render/csv.py` for the normalized `section,key,count,percentage` rows using `csv.writer`.
3. Extend `tests/test_renderers.py` with schema, escaping, numeric-type, ordering, newline, and golden-output tests.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q -k 'json or csv'`
- `nginx-stream-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: add stable pipeline formats`

## STEP 7: Compose the complete CLI

**Goal:** every public option, source, renderer, diagnostic channel, and exit code works end to end.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; all P0 stories in `PRD.md`.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` composition without moving Click/Rich dependencies into domain modules.
2. Validate option exclusivity, top/cardinality ranges, and stdin occurrence before processing.
3. Map expected failures to 2/3/4, unexpected failures to 1, and complete results to 0; handle broken pipe without traceback.
4. Expand `tests/test_cli.py` for file/stdin/multiple sources, mixed malformed data, zero-valid input, output isolation, and all `0/1/2/3/4` exits.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-7: integrate CLI contracts`

## STEP 8: Performance and robustness gate

**Goal:** measured behavior meets the 1 GB/30-second constraint without weakening exactness.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` KPIs/kill criteria; `PROJECT_ARCHITECTURE.md` section 8; `PRD.md` release acceptance.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` for a deterministic, representative 1 GB combined-log fixture with bounded documented cardinality.
2. Create `tests/test_performance.py`, excluded from default tests, to validate output and threshold on a named reference machine.
3. Profile the installed command; optimize compiled parsing, allocations, and top selection only from evidence.
4. Record machine, Python, fixture recipe, command, cache condition, wall time, and peak RSS in `README.md`.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --size-gib 1 /tmp/nginx-benchmark.log`
- `/usr/bin/time -v nginx-stream-report --json /tmp/nginx-benchmark.log >/tmp/nginx-report.json`
- `python3.11 -m pytest tests/test_performance.py -m performance -q`

**Commit:** `step-8: prove performance and robustness`

## STEP 9: Release and clean-install acceptance

**Goal:** v0.1.0 artifacts install reproducibly and all specifications agree with observed behavior.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` release acceptance.

**Tasks:**

1. Finalize `README.md` quick start, supported format, metric definitions, examples, schemas, limits, and complete exit contract.
2. Build wheel/sdist and install the wheel in a new virtual environment.
3. Run all static, test, coverage, package-metadata, and smoke checks on the exact release candidate.
4. Reconcile documentation and help before tagging; do not ship P1 gzip behavior unless separately accepted.

**Verification:**

- `python3.11 -m ruff check . && python3.11 -m mypy src`
- `python3.11 -m pytest -q --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `tmpdir="$(mktemp -d)"; python3.11 -m venv "$tmpdir/venv"; "$tmpdir/venv/bin/pip" install dist/*.whl; "$tmpdir/venv/bin/nginx-stream-report" --help`

**Commit:** `step-9: prepare verified v0.1.0 release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Friday | 1–3 | Installable foundation, contracts, and trusted parsing | ~4.5 h |
| Saturday | 4–7 | Metrics, safety, renderers, and complete CLI | ~9 h |
| Sunday | 8–9 | Performance proof, packaging, and release acceptance | ~5 h |

## Dependency and Priority Rationale

The parser precedes the high-scoring metric features because all metrics depend on trustworthy records. Aggregation follows in descending operational value, but is implemented as one cohesive state update to keep one-pass semantics. Cardinality safety lands with aggregation, before any renderer can expose a partial result. Pipeline and text renderers then consume the same immutable report, preventing semantic drift.

## Deferred Work

P1 gzip support and P2 custom formats/approximation require their own acceptance criteria and implementation unit after v0.1. Authentication, databases, HTTP APIs, servers, cloud resources, and Kubernetes remain excluded.
