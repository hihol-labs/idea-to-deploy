# Implementation Plan: Nginx Log Lens

## 1. Delivery Rules

This is a planning document; no product code is included. Implement one step at
a time, preserve a runnable main branch, and treat `PRD.md` plus
`PROJECT_ARCHITECTURE.md` as the behavior source of truth. Each step is complete
only after its listed commands pass and evidence is recorded.

The public exit-code contract applies throughout:

| Code | Meaning |
|---:|---|
| `0` | Success, help, or version |
| `1` | Operational input/output/internal failure |
| `2` | CLI usage error |
| `3` | Strict parsing failure or no valid records |
| `4` | Unique-cardinality exhaustion |

Never omit, reuse, or remap code `4`; it exclusively means exact
unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` packaging and console entry point | Every integration test and renderer needs an installable command | 1 hour |
| 2 | Immutable dataclasses and error taxonomy | Parser, aggregator, renderers, and CLI need a shared contract | 1 hour |
| 3 | Golden log fixtures and output schema fixtures | Prevents three output modes from defining behavior independently | 1 hour |
| 4 | Benchmark harness design | Makes streaming and timing constraints testable before optimization | 1 hour |

No database schema, auth system, Docker setup, API scaffold, or CI/CD service is
part of the runway because none exists in the selected local CLI architecture.

## Step 1: Package Skeleton and CLI Contract

**Goal:** a wheel installs on Python 3.11 and exposes a Click command whose
help, version, arguments, and option-validation behavior match the architecture.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4, `CLI Interface`, and 9;
`PRD.md` FR-01, FR-09, FR-11, FR-14.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, dev extras, build backend, and `nginx-log-lens` entry point.
2. Create `src/nginx_log_lens/__init__.py` with version exposure.
3. Create `src/nginx_log_lens/cli.py` with the `analyze` command signature and mutually exclusive output validation, leaving analysis calls as the next-step seam.
4. Create `src/nginx_log_lens/errors.py` with the authoritative `ExitCode` values `0/1/2/3/4` and typed domain errors.
5. Create `tests/test_cli_contract.py` for help, version, missing/extra arguments, conflicting flags, and option range validation.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-log-lens --help`
- `.venv/bin/pytest tests/test_cli_contract.py -q`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Domain Models and Supported Log Parser

**Goal:** common and combined nginx lines become validated `AccessRecord`
instances without retaining the input stream.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4–5; `PRD.md` FR-02 and edge cases.

**Tasks:**

1. Create `src/nginx_log_lens/models.py` with frozen `AccessRecord`, `RankedCount`, `HourlyBucket`, and `AnalysisSummary` dataclasses.
2. Create `src/nginx_log_lens/parser.py` with the finite common/combined grammar, escape handling, timestamp parsing, status validation, and sanitized `ParseError`.
3. Create `tests/fixtures/access_common.log`, `tests/fixtures/access_combined.log`, and `tests/fixtures/access_malformed.log` with non-sensitive synthetic records.
4. Create `tests/test_parser.py` covering IPv4/IPv6, timezone offsets, escaped fields, missing User-Agent, status bounds, request targets, excessive line length, and unsupported formats.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/ruff check src/nginx_log_lens/parser.py src/nginx_log_lens/models.py tests/test_parser.py`

**Commit:** `step-2: parse supported nginx records`

## Step 3: One-Pass Core Aggregations

**Goal:** one iterable pass produces deterministic top IPs, error URLs, and all
24 hourly count/percentage buckets.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 6; `PRD.md` FR-03–FR-05 and US-1–US-3.

**Tasks:**

1. Create `src/nginx_log_lens/aggregate.py` with counters and a fixed 24-slot hour array.
2. Implement stable top-10 ordering by descending count and ascending key.
3. Implement hourly percentages using exactly `100 × hourly_request_count / total_valid_requests` while preserving raw counts.
4. Create `tests/test_aggregate_core.py` for ties, boundary statuses, no-error input, mixed timezones, zero buckets, and percentage totals.
5. Add a non-materializing generator test that fails if the aggregator requests a second iteration.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate_core.py -q`
- `.venv/bin/mypy src/nginx_log_lens/models.py src/nginx_log_lens/aggregate.py`

**Commit:** `step-3: aggregate traffic and error metrics`

## Step 4: Exact User-Agent Share and Exhaustion Boundary

**Goal:** User-Agent diversity is exact below a configured limit and fails
atomically with exit code `4` when exact computation cannot continue.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` Section 6; `PRD.md` FR-06, FR-07, and US-4.

**Tasks:**

1. Extend `src/nginx_log_lens/aggregate.py` with a guarded set of non-missing User-Agent values.
2. Add `UniqueCardinalityExhausted` to `src/nginx_log_lens/errors.py` and map only that condition to `4` in `src/nginx_log_lens/cli.py`.
3. Ensure the aggregator does not return a partial `AnalysisSummary` after exhaustion.
4. Create `tests/test_user_agent_cardinality.py` for repeated, missing, exact-limit, over-limit, and denominator behavior.
5. Extend `tests/test_cli_contract.py` to assert stderr sanitation, empty stdout, and process exit `4` on exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_user_agent_cardinality.py tests/test_cli_contract.py -q`
- `.venv/bin/nginx-log-lens analyze --max-unique-user-agents 1 tests/fixtures/access_combined.log; test $? -eq 4`

**Commit:** `step-4: guard exact user-agent cardinality`

## Step 5: Rich Terminal Renderer

**Goal:** the default command displays readable, colored sections without
making color the only carrier of information.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` outputs;
`PRD.md` FR-08 and US-1.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/__init__.py` for renderer selection.
2. Create `src/nginx_log_lens/renderers/rich.py` with summary, top-IP, error-URL, hourly, and User-Agent sections.
3. Wire default and `--no-color` paths in `src/nginx_log_lens/cli.py`.
4. Create `tests/test_rich_renderer.py` with fixed-width console snapshots and ANSI-stripped semantic assertions.

**Verification:**

- `.venv/bin/pytest tests/test_rich_renderer.py -q`
- `.venv/bin/nginx-log-lens analyze --no-color tests/fixtures/access_combined.log`

**Commit:** `step-5: render default terminal report`

## Step 6: JSON and CSV Pipeline Renderers

**Goal:** automation can consume stable, equivalent JSON and CSV without
terminal decoration or stderr contamination.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` outputs;
`PRD.md` FR-09 and US-5.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/json.py` with schema version `1` and canonical key/row order.
2. Create `src/nginx_log_lens/renderers/csv.py` with header `record_type,rank,key,count,percentage` and all documented record types.
3. Complete output selection in `src/nginx_log_lens/cli.py`; keep warnings and failures on stderr only.
4. Create `tests/schemas/analysis-v1.schema.json` for machine validation.
5. Create `tests/test_machine_renderers.py` to parse both formats, compare canonical values, assert six-decimal percentages, and reject ANSI/progress text.

**Verification:**

- `.venv/bin/pytest tests/test_machine_renderers.py -q`
- `.venv/bin/nginx-log-lens analyze --json tests/fixtures/access_combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: Input Diagnostics and Complete Exit Matrix

**Goal:** file, stdin, malformed data, I/O failure, usage errors, and
cardinality failure obey one tested `0/1/2/3/4` contract.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5, 8 and `CLI Interface` exit
codes; `PRD.md` US-2, US-6, FR-10–FR-13.

**Tasks:**

1. Complete stream ownership and context-manager paths in `src/nginx_log_lens/cli.py`.
2. Add bounded invalid-line diagnostics and strict-mode termination without echoing complete records.
3. Map unreadable input/output/internal operational failures to `1`, leave Click usage failures as `2`, map strict/no-valid data to `3`, and preserve User-Agent exhaustion as `4`.
4. Create `tests/test_input_modes.py` for path/stdin equivalence, stdin ownership, empty input, mixed malformed input, strict mode, unreadable paths, and simulated output failure.
5. Create `tests/test_exit_codes.py` with at least one process-level assertion for every code `0`, `1`, `2`, `3`, and `4`.

**Verification:**

- `.venv/bin/pytest tests/test_input_modes.py tests/test_exit_codes.py -q`
- `.venv/bin/pytest tests/test_exit_codes.py --junitxml=.artifacts/exit-codes.xml`

**Commit:** `step-7: enforce diagnostics and exit codes`

## Step 8: Quality, Packaging, and Performance Gate

**Goal:** the exact release candidate is typed, linted, tested, installable, and
measured against the 1 GB target without hiding memory growth.

**Time:** ~2.5 hours plus benchmark runtime

**Context:** `PROJECT_ARCHITECTURE.md` Section 11; `PRD.md` NFR-01–NFR-07 and release acceptance.

**Tasks:**

1. Create `tests/test_end_to_end.py` for the golden flow across all renderers.
2. Create `benchmarks/generate_access_log.py` with deterministic seed and configurable bytes/cardinalities.
3. Create `benchmarks/run_1gb.sh` to record Python/OS/hardware metadata, fixture settings, wall time, throughput, and peak RSS.
4. Finalize Ruff, mypy, pytest, and coverage configuration in `pyproject.toml`.
5. Build sdist/wheel and install the wheel—not the working tree—into a clean temporary virtual environment for smoke tests.

**Verification:**

- `.venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest --cov=nginx_log_lens --cov-fail-under=90`
- `.venv/bin/python -m build && benchmarks/run_1gb.sh`
- `test "$(find dist -maxdepth 1 -name '*.whl' | wc -l)" -eq 1`

**Commit:** `step-8: prove package quality and performance`

## Step 9: Documentation and Release Readiness

**Goal:** a new user can install and run the tool in under 30 seconds, while a
maintainer can reproduce every acceptance check.

**Time:** ~1 hour

**Context:** all blueprint documents; `PRD.md` release acceptance.

**Tasks:**

1. Update `README.md` with actual package/install commands, sample outputs, schemas, supported format, exit codes, limitations, and benchmark environment/result.
2. Update `CLAUDE.md` status only from recorded command evidence.
3. Add `CHANGELOG.md` with the initial public contract and `LICENSE` with the selected open-source license.
4. Verify `CLAUDE_CODE_GUIDE.md` prompts still name the actual paths and complete `0/1/2/3/4` exit mapping.
5. Run the release checklist against an exact built artifact and record results in `docs/RELEASE_CHECKLIST.md`.

**Verification:**

- `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/mypy src`
- `tmp_venv="$(mktemp -d)/venv"; python3.11 -m venv "$tmp_venv" && "$tmp_venv/bin/pip" install dist/*.whl && "$tmp_venv/bin/nginx-log-lens" --help`
- `rg -n '0/1/2/3/4|code `4`|exit `4`' README.md CLAUDE_CODE_GUIDE.md CLAUDE.md docs/RELEASE_CHECKLIST.md`

**Commit:** `step-9: document and freeze release candidate`

## Sprint Boundaries

For the one-weekend timebox, “Sprint” means a focused half-day delivery block,
not a multi-week ceremony.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable contract and correct parser | Half day |
| Saturday PM | 3–4 | All canonical aggregations and exactness boundary | Half day |
| Sunday AM | 5–7 | Three output modes and complete failures contract | Half day |
| Sunday PM | 8–9 | Quality, benchmark, package, and handoff | Half day |

## Dependency and Rollback Strategy

Steps are dependency-ordered even where a leaf feature has a higher RICE score.
Each commit should be independently reviewable. If a step fails its verification,
do not advance the status table or weaken acceptance criteria; correct the step
or revert only that step through normal version-control review. Performance
optimization may change parser/aggregation internals but not schemas, formulas,
tie-breaking, or exit codes without first updating the specifications.

## Final Acceptance Checklist

- [ ] Golden values match `PRD.md` for all four metrics.
- [ ] Hour percentages use `100 × hourly_request_count / total_valid_requests`.
- [ ] JSON/CSV parse cleanly and equal the canonical summary.
- [ ] Exit codes `0/1/2/3/4` each have a process-level passing test; code `4` remains unique-cardinality exhaustion.
- [ ] Wheel installs and runs under Python 3.11.
- [ ] Coverage, Ruff, and mypy gates pass.
- [ ] The declared 1 GB benchmark finishes under 30 seconds on the reference laptop.
- [ ] No database, auth, HTTP API, server, cloud, or Kubernetes implementation exists.
