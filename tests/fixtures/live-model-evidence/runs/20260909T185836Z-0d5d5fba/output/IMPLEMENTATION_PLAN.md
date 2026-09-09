# Implementation Plan: Nginx Pulse

This is a one-weekend, eight-step plan. Steps are dependency ordered; within a dependency layer, the RICE ordering from `STRATEGIC_PLAN.md` determines sequence. Product behavior is governed by `PRD.md`, and types/interfaces by `PROJECT_ARCHITECTURE.md`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package and console-script skeleton | Every executable slice needs a stable import and invocation path | 1 hour |
| 2 | Domain dataclasses and fixture conventions | Parser, aggregator, and renderers must share one result contract | 1 hour |
| 3 | CI-quality commands in `pyproject.toml` | Each later step needs repeatable lint, type, and test checks | 1 hour |
| 4 | Generated benchmark fixture contract | Performance must be measured reproducibly before late optimization | 1 hour |

No database schema, authentication layer, API scaffold, Docker setup, or deployment infrastructure belongs in the runway because the approved product has none.

## STEP 1: Package and CLI Contract Skeleton

**Goal:** A wheel installs an `nginx-pulse` command with help, version, option validation, and placeholder orchestration boundaries, without implementing analytics.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3 and `## CLI Interface`; `PRD.md` FR-001, FR-008–FR-011.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, console script, and quality-tool configuration.
2. Create `src/nginx_pulse/__init__.py` and `src/nginx_pulse/__main__.py` for version and module invocation.
3. Create `src/nginx_pulse/cli.py` with the documented arguments/options, mutual exclusion, and stream-ownership boundary.
4. Create `tests/integration/test_cli_contract.py` for help, version, invalid flags, and stdin/path selection.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/integration/test_cli_contract.py -q`
- `python3.11 -m nginx_pulse --help`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Domain Models and Combined-Log Parser

**Goal:** Supported combined-log lines become validated immutable records, and malformed/encoding cases are classified consistently.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5–6; `PRD.md` FR-002–FR-003 and edge cases.

**Tasks:**

1. Create `src/nginx_pulse/models.py` with `LogRecord`, `RankedItem`, and `AnalysisResult` dataclasses.
2. Create `src/nginx_pulse/parser.py` with quoted-field handling, request splitting, strict timestamp/status validation, and typed parse failures.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with IPv4, IPv6, escaping, placeholders, error statuses, and a final line without newline.
4. Create `tests/unit/test_parser.py` to lock every valid and malformed parser case.

**Verification:**

- `python3.11 -m pytest tests/unit/test_parser.py -q`
- `python3.11 -m mypy src/nginx_pulse/parser.py src/nginx_pulse/models.py`

**Commit:** `step-2: parse nginx combined logs`

## STEP 3: Streaming Aggregation and Rankings

**Goal:** One pass produces exact totals, deterministic top-IP/error-URL rankings, 24 hourly percentages, and exact User-Agent share.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 5, and 7; `PRD.md` FR-003–FR-007.

**Tasks:**

1. Create `src/nginx_pulse/aggregate.py` with ephemeral counters, a User-Agent set, cardinality guard, and immutable result finalization.
2. Create `tests/unit/test_aggregate.py` for deterministic top ten, error status boundaries, query-string identity, empty input, and malformed exclusion.
3. Add a distribution invariant asserting all 24 buckets use `100 × hourly_request_count / total_valid_requests` and sum to approximately 100 for non-empty valid input.
4. Add a cardinality regression asserting the would-be excess value causes the typed exhaustion outcome before mutation.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregate.py -q`
- `python3.11 -m pytest tests/unit/test_aggregate.py --cov=nginx_pulse.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-3: implement streaming metrics`

## STEP 4: JSON and CSV Pipeline Renderers

**Goal:** Stable, ANSI-free JSON and CSV serialize the same analysis result with deterministic ordering.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` output schemas; `PRD.md` JSON/CSV stories and FR-008–FR-009.

**Tasks:**

1. Create `src/nginx_pulse/render/__init__.py` with the renderer protocol.
2. Create `src/nginx_pulse/render/json.py` with schema version 1 and a trailing newline.
3. Create `src/nginx_pulse/render/csv.py` with the long-form RFC 4180 schema and fixed section ordering.
4. Create `tests/unit/test_render_json.py`, `tests/unit/test_render_csv.py`, and golden files under `tests/fixtures/expected/`.
5. Wire `--json` and `--csv` in `src/nginx_pulse/cli.py` without duplicating aggregation logic.

**Verification:**

- `python3.11 -m pytest tests/unit/test_render_json.py tests/unit/test_render_csv.py -q`
- `python3.11 -m nginx_pulse --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-4: add stable pipeline renderers`

## STEP 5: Rich Terminal Renderer

**Goal:** Default invocation produces a concise, colored interactive report and clean redirected text.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` terminal-output story and FR-008.

**Tasks:**

1. Create `src/nginx_pulse/render/text.py` with summary and metric tables using Rich.
2. Wire terminal detection and `--color/--no-color` in `src/nginx_pulse/cli.py`.
3. Create `tests/unit/test_render_text.py` for content, ordering, forced color, and redirected no-color behavior.
4. Add `tests/fixtures/expected/report.txt` as the no-color golden report.

**Verification:**

- `python3.11 -m pytest tests/unit/test_render_text.py -q`
- `python3.11 -m nginx_pulse --no-color tests/fixtures/combined.log > /tmp/nginx-pulse-report.txt`

**Commit:** `step-5: render terminal report`

## STEP 6: End-to-End Errors and Exit Codes

**Goal:** The installed command honors stdout/stderr separation and the complete exit-code contract under real subprocess execution.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` exit codes; `PRD.md` section 5.

**Tasks:**

1. Complete exception-to-exit mapping in `src/nginx_pulse/cli.py` with precedence documented by architecture.
2. Create `tests/integration/test_exit_codes.py` covering the full `0/1/2/3/4` contract: 0 complete success, 1 runtime/input-output failure, 2 usage error, 3 partial result after malformed lines, and 4 unique-cardinality exhaustion.
3. Create `tests/integration/test_streams.py` to assert normal output is stdout-only and diagnostics are stderr-only.
4. Confirm code 4 emits no normal report and uses the exact cardinality limit from the option.

**Verification:**

- `python3.11 -m pytest tests/integration/test_exit_codes.py tests/integration/test_streams.py -q`
- `python3.11 -m nginx_pulse --json tests/fixtures/malformed.log >/tmp/nginx-pulse.json; test $? -eq 3`

**Commit:** `step-6: enforce stream and exit contracts`

## STEP 7: Performance and Resource Guardrails

**Goal:** The reference 1 GB run is reproducible, completes under 30 seconds, and reports peak memory without weakening exactness.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 7; `PRD.md` NFR-001, NFR-002, and NFR-008.

**Tasks:**

1. Create `tests/performance/generate_log.py` to deterministically generate the bounded-cardinality reference fixture and record its content digest.
2. Create `tests/performance/run_benchmark.py` to invoke the installed CLI, redirect output, and record runtime metadata and peak resident memory.
3. Create `tests/performance/test_streaming.py` for a smaller CI-safe fixture and cardinality boundary.
4. Profile `src/nginx_pulse/parser.py` and `src/nginx_pulse/aggregate.py`; make only evidence-led hot-path adjustments that preserve prior tests.

**Verification:**

- `python3.11 -m pytest tests/performance/test_streaming.py -q`
- `python3.11 tests/performance/generate_log.py --size-gib 1 --output /tmp/nginx-pulse-1g.log`
- `python3.11 tests/performance/run_benchmark.py /tmp/nginx-pulse-1g.log --max-seconds 30`

**Commit:** `step-7: prove performance and memory bounds`

## STEP 8: Release Quality and Documentation

**Goal:** A clean source distribution and wheel install on Python 3.11, all acceptance checks pass, and users can run the CLI in under 30 seconds after installation.

**Time:** ~3 hours

**Context:** All architecture sections; `PRD.md` release acceptance; `README.md`; `CLAUDE_CODE_GUIDE.md`.

**Tasks:**

1. Finalize `README.md` with install, examples, schemas, supported format, and limitations.
2. Create `CHANGELOG.md` and `LICENSE` using the chosen open-source license and initial release notes.
3. Create `tests/integration/test_installed_wheel.py` to build/install the wheel in isolation and run a golden fixture.
4. Run the complete quality, acceptance, and packaging matrix; record benchmark environment in release notes.

**Verification:**

- `python3.11 -m ruff check src tests`
- `python3.11 -m mypy src/nginx_pulse`
- `python3.11 -m pytest --cov=nginx_pulse --cov-branch --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`

**Commit:** `step-8: prepare verified MVP release`

## Weekend Boundaries

| Block | Steps | Outcome |
|---|---|---|
| Saturday morning | 1–2 | Installable interface and trustworthy parsing |
| Saturday afternoon | 3–4 | Core metrics and pipeline formats |
| Sunday morning | 5–6 | Operator UI and complete failure semantics |
| Sunday afternoon | 7–8 | Measured performance and releasable package |

## Cross-Step Acceptance Rules

- WIP remains one step: begin the next step only after the current verification commands pass and evidence is recorded.
- The executable exit-code contract is always `0/1/2/3/4`; code 4 always means unique-cardinality exhaustion and is never remapped.
- Changes to behavior begin in `PRD.md` and `PROJECT_ARCHITECTURE.md`, then flow into implementation and tests.
- The performance claim is made only from a current run on the documented reference fixture and machine.
- The external adversarial architecture review is outside this plan execution and must not be represented as completed by implementation evidence.
