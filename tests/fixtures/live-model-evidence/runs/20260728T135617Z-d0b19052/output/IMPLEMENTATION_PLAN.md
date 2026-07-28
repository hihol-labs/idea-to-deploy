# Implementation Plan: nginx-log-top

This plan covers the one-weekend MVP only. It orders prerequisites before feature work and, within dependency layers, follows the RICE ranking in `STRATEGIC_PLAN.md`. Product code is not part of this blueprint.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console contract | Every test and feature depends on reproducible installation/imports | 1 hour |
| 2 | Domain dataclasses and error taxonomy | Parser, aggregator, renderers, and exit mapping need stable types | 1 hour |
| 3 | Fixture and benchmark strategy | Correctness and 1 GB/30 s risk must be measurable before optimization | 1 hour |
| 4 | CI quality commands | Each later step needs the same automated gate | 1 hour |

No database schema, migrations, auth system, Docker setup, HTTP API, or deployment pipeline belongs in the runway; `PROJECT_ARCHITECTURE.md` explicitly excludes them.

## STEP 1: Freeze package and CLI contracts

**Goal:** A Python 3.11 package installs locally and exposes an inert, documented Click entry point.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, CLI Interface, 8, and 9; `PRD.md` FR-01, FR-11, FR-12.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11`, Click, Rich, pytest tooling, `src/` discovery, and `nginx-log-top = nginx_log_top.cli:main`.
2. Create `src/nginx_log_top/__init__.py` with package version metadata.
3. Create `src/nginx_log_top/cli.py` with Click argument/options and mutual-exclusion validation, but no reporting behavior yet.
4. Create `tests/test_cli.py` for help, version, option bounds, and conflicting formats.

**Verification:**

- `python3.11 -m pip install -e .`
- `nginx-log-top --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Implement typed parsing boundary

**Goal:** Valid combined-log lines become typed events; malformed lines have explicit outcomes.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5–7; `PRD.md` US-1 and FR-02/FR-03.

**Tasks:**

1. Create `src/nginx_log_top/models.py` with frozen/slotted `AccessLogEvent` and snapshot dataclasses.
2. Create `src/nginx_log_top/errors.py` with input and strict-parse error types.
3. Create `src/nginx_log_top/parser.py` with a bounded 1 MiB physical-line reader, one compiled combined-format parser, request-target extraction, aware timestamps, and missing-UA normalization.
4. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with representative, synthetic, non-sensitive records.
5. Create `tests/test_parser.py` for IPv4/IPv6, escaped fields, time offsets, status boundaries, and malformed input.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m compileall -q src`

**Commit:** `step-2: add combined-log parser and typed events`

## STEP 3: Build streaming aggregation

**Goal:** One pass produces correct IP, error-URL, hourly, and User-Agent state without retaining raw events.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5, 6, and 10; `PRD.md` US-2 through US-5.

**Tasks:**

1. Create `src/nginx_log_top/aggregate.py` with counters, exact UA set, malformed count, and snapshot finalization.
2. Implement deterministic top-N ordering using descending count then lexical key.
3. Implement 400–599 filtering, `HourBucket(local_date, hour, offset_minutes)` identity and UTC-based ordering, and empty-input share semantics.
4. Create `tests/test_aggregate.py` with ties, duplicate agents, mixed status classes, multiple offsets/hours, empty input, and invariants.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py -q --cov=nginx_log_top --cov-report=term-missing`

**Commit:** `step-3: implement exact streaming aggregations`

## STEP 4: Deliver JSON and CSV pipeline outputs

**Goal:** Automation can consume stable, ANSI-free, deterministic schemas.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface outputs; `PRD.md` US-7 and FR-09/FR-10.

**Tasks:**

1. Create `src/nginx_log_top/renderers.py` with immutable snapshot-to-JSON and snapshot-to-CSV functions.
2. Use the standard `json` and `csv` modules to preserve escaping and RFC 4180 quoting; add a separate terminal-safe control-character transformation with Rich markup disabled.
3. Wire `--json`, `--csv`, and `--top` through `src/nginx_log_top/cli.py`.
4. Create `tests/test_renderers.py` with golden schemas, Unicode/commas/quotes, ordering, numeric share precision, and ANSI exclusion.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py tests/test_cli.py -q`
- `nginx-log-top --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-4: add stable JSON and CSV report schemas`

## STEP 5: Deliver Rich terminal report

**Goal:** Interactive users get a readable colored summary without compromising redirected output.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface outputs; `PRD.md` US-6 and FR-08.

**Tasks:**

1. Extend `src/nginx_log_top/renderers.py` with Rich summary and metric tables.
2. Wire default terminal mode and `--no-color` through `src/nginx_log_top/cli.py`.
3. Respect stdout TTY detection and `NO_COLOR`; keep diagnostics on stderr.
4. Extend `tests/test_renderers.py` and `tests/test_cli.py` with forced-color, no-color, redirected-output, and empty-report cases.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py tests/test_cli.py -q`
- `NO_COLOR=1 nginx-log-top tests/fixtures/combined.log`

**Commit:** `step-5: add TTY-aware Rich terminal report`

## STEP 6: Complete input/error lifecycle

**Goal:** File/stdin parity, malformed-line policy, broken pipes, interrupts, and exit codes match the documented CLI contract.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and section 10; `PRD.md` US-1, US-8, and FR-11.

**Tasks:**

1. Complete lazy file/stdin ownership in `src/nginx_log_top/cli.py`.
2. Implement lenient malformed counting and strict first-error behavior.
3. Map missing/unreadable input, strict failures, and unexpected failures to exit codes 3, 4, and 1.
4. Handle broken pipes and keyboard interrupts without ordinary tracebacks.
5. Expand `tests/test_cli.py` for file/stdin equivalence, unreadable input, strict/lenient behavior, stderr isolation, and every exit code.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `cat tests/fixtures/combined.log | nginx-log-top --json - | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: enforce streaming input and exit-code lifecycle`

## STEP 7: Prove quality and performance

**Goal:** Current evidence establishes correctness, coverage, security boundaries, and the 1 GB/30 s target.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 7, 10, and 11; all P0 criteria in `PRD.md`.

**Tasks:**

1. Create `tests/test_performance.py` with an opt-in benchmark that times only processing of deterministic normal- and high-cardinality 1 GiB fixtures.
2. Create `tests/benchmark-manifest.json` with the BR-1 hardware/software profile, generator seed/hash, distribution, five-run median protocol, and 1.5 GiB normal-profile RSS ceiling.
3. Create `docs/PERFORMANCE.md` to record fixture hash/size, Python, CPU, storage, five elapsed runs, median seconds, MB/s, and peak RSS.
4. Add parser fuzz/property cases to `tests/test_parser.py` without requiring network access.
5. Configure coverage and static checks in `pyproject.toml`.
6. Review dependencies and code for network calls, persistence, log-content execution, accidental record retention, and terminal control injection.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_log_top --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m pytest tests/test_performance.py -m performance -q`
- `python3.11 -m pip check`

**Commit:** `step-7: record acceptance and performance evidence`

## STEP 8: Package and hand off the MVP

**Goal:** A clean Python 3.11 environment can build, install, invoke, and understand the release.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` release acceptance; `PROJECT_ARCHITECTURE.md` section 9.

**Tasks:**

1. Update `README.md` with final installation, examples, schemas, format boundary, and troubleshooting.
2. Reconcile `CLAUDE.md`, `PRD.md`, and `PROJECT_ARCHITECTURE.md` with implemented CLI help.
3. Build wheel and source distribution into `dist/`.
4. Install the wheel in a clean Python 3.11 virtual environment and smoke-test file/stdin plus three output modes.
5. Record the full test, coverage, benchmark, review, and security evidence in the handoff.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest -q --cov=nginx_log_top --cov-fail-under=90`

**Commit:** `step-8: package and hand off weekend MVP`

## Sprint Boundaries

For this one-weekend project, “sprints” are half-day execution blocks:

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable contract and trustworthy parsing | Half day |
| Saturday PM | 3–4 | Core metrics and machine outputs | Half day |
| Sunday AM | 5–6 | Operator UX and robust lifecycle | Half day |
| Sunday PM | 7–8 | Evidence, packaging, and handoff | Half day |

## Dependency and WIP Policy

```text
Step 1 -> Step 2 -> Step 3 -> Step 4 -> Step 5 -> Step 6 -> Step 7 -> Step 8
```

Maintain WIP=1. A step moves to Done only with its listed commands and the applicable acceptance evidence. If performance fails in Step 7, return to the smallest measured bottleneck rather than starting deferred features.

## Deferred Backlog

P1 controls are included late in the MVP only after P0 behavior. gzip and custom formats remain P2 and require a new scope decision. Database, HTTP API, authentication, server, cloud, Kubernetes, live dashboard, and durable history remain explicitly out of scope.
