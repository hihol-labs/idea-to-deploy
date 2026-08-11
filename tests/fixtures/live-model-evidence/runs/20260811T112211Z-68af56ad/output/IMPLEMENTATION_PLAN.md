# Implementation Plan: Nginx Stream Insights

## 1. Delivery Rules

This plan covers only the P0 weekend MVP from `PRD.md`. Preserve work-in-progress at one implementation step. Before accepting a step, freeze and verify the exact candidate with the repository's Idea to Deploy Verification Loop and retain its current adjudication receipt. No product code is implemented by this blueprint.

The mandatory process-level contract in every step is:

| Exit code | Meaning |
|---:|---|
| `0` | Success/informational command |
| `1` | Unexpected runtime or output failure |
| `2` | CLI usage/configuration error |
| `3` | Input/read/decode/data failure, including zero valid records |
| `4` | Unique-cardinality exhaustion |

Code 4 must remain unique-cardinality exhaustion throughout the CLI, exception model, tests, and documentation; it may not be omitted or remapped.

## 2. Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and test layout | All executable and verification work needs stable imports and entry points | 1 hour |
| 2 | Canonical dataclasses and error taxonomy | Parser, aggregator, renderers, and CLI need one contract | 1 hour |
| 3 | Golden combined-log fixtures | Parsing and calculation work needs replayable examples | 1 hour |
| 4 | Benchmark protocol | Performance decisions must be measured before late optimization | 1 hour |

There is no database schema, authentication system, API scaffold, container topology, or deployment infrastructure in the runway because the architecture explicitly excludes them.

## STEP 1: Package Skeleton and Quality Gates

**Goal:** A Python 3.11 package installs in an isolated environment and exposes `nginx-insight --help` without implementing report behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 10; `PRD.md` FR-10.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, and the console entry point.
2. Create `src/nginx_insight/__init__.py` and `src/nginx_insight/cli.py` with the option surface from `## CLI Interface`.
3. Create `tests/conftest.py` and project configuration for pytest, coverage, linting, and type checking.
4. Create `tests/test_cli_contract.py` for `--help`, `--version`, incompatible formats, and invalid `--max-unique`.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_contract.py`
- `nginx-insight --help`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Domain Models, Errors, and Fixtures

**Goal:** All later components share typed immutable inputs/reports and the complete failure taxonomy.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 6, 8 and `## CLI Interface`.

**Tasks:**

1. Create `src/nginx_insight/models.py` with slotted dataclasses for `AccessRecord`, ranked rows, hourly rows, and the final report.
2. Create `src/nginx_insight/errors.py` with explicit internal, input/data, and cardinality failures mapped to 1, 3, and 4; leave Click usage failures at 2.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/hostile_fields.log` with declared expected values.
4. Extend `tests/test_cli_contract.py` to assert all `0/1/2/3/4` mappings, including code 4 without remapping.

**Verification:**

- `python3.11 -m pytest tests/test_cli_contract.py`
- `python3.11 -m mypy src/nginx_insight`

**Commit:** `step-2: define report and failure models`

## STEP 3: Streaming Input and Combined-Log Parser

**Goal:** Files and stdin yield valid `AccessRecord` values one at a time with bounded diagnostics for bad records.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 5, 8; `PRD.md` US-1.

**Tasks:**

1. Create `src/nginx_insight/input.py` for buffered ordered file/stdin iteration, UTF-8 decoding, repeated-stdin rejection, and source/line tracking.
2. Create `src/nginx_insight/parser.py` for the documented combined grammar and request-target extraction.
3. Create `tests/test_input.py` for order, stdin, unavailable input, decoding failure, and no whole-file reads.
4. Create `tests/test_parser.py` for valid IPv4/IPv6 text, offsets, escaped quoted fields, malformed requests, status boundaries, and hostile control text.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_parser.py`
- `python3.11 -m ruff check src/nginx_insight/input.py src/nginx_insight/parser.py tests/test_input.py tests/test_parser.py`

**Commit:** `step-3: stream and parse combined logs`

## STEP 4: Exact Aggregation and Cardinality Guard

**Goal:** One-pass aggregation produces all four exact metrics and fails predictably before distinct state exceeds its configured ceiling.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 6; `PRD.md` US-2 through US-5 and US-7.

**Tasks:**

1. Create `src/nginx_insight/aggregate.py` with IP/error-URL dictionaries, 24 fixed hour counters, User-Agent set, and valid/invalid totals.
2. Implement deterministic top-10 ordering and report finalization.
3. Compute hourly percentage exactly as `100 × hourly_request_count / total_valid_requests` and User-Agent share from the exact numerator/denominator.
4. Check `--max-unique` before each new distinct IP, error URL, or User-Agent and raise the dimension-specific code-4 failure.
5. Create `tests/test_aggregate.py` for status ranges, ties, 24 hours, percentages, ceiling boundary/exhaustion, and no partial result.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_insight.aggregate --cov-fail-under=95`

**Commit:** `step-4: add bounded exact aggregations`

## STEP 5: Default Rich Text Renderer

**Goal:** Interactive users receive a readable four-section report while redirected output remains plain and safe.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 7–9; `PRD.md` US-6.

**Tasks:**

1. Create `src/nginx_insight/render_text.py` with totals, top-IP, error-URL, hourly, and User-Agent sections.
2. Implement TTY-aware color, `NO_COLOR`, `--color`, and `--no-color` precedence.
3. Escape Rich markup and terminal control characters in untrusted fields.
4. Create `tests/test_render_text.py` for content parity, color modes, redirection, zero hours, and hostile fields.

**Verification:**

- `python3.11 -m pytest tests/test_render_text.py`
- `NO_COLOR=1 nginx-insight tests/fixtures/combined.log`

**Commit:** `step-5: render safe terminal report`

## STEP 6: JSON and CSV Renderers

**Goal:** Pipeline users receive deterministic, standards-encoded representations of the same report model.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` US-6 and section 6.

**Tasks:**

1. Create `src/nginx_insight/render_json.py` for `schema_version: 1` and the canonical object shape.
2. Create `src/nginx_insight/render_csv.py` for `metric,key,count,percentage` and all metric discriminator rows.
3. Create `tests/test_render_json.py` and `tests/test_render_csv.py` for schemas, quoting, Unicode, no ANSI, 24 hours, and value parity with text/report models.
4. Add golden expected outputs under `tests/fixtures/expected/`.

**Verification:**

- `python3.11 -m pytest tests/test_render_json.py tests/test_render_csv.py`
- `nginx-insight --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: add stable pipeline renderers`

## STEP 7: CLI Integration and Failure Semantics

**Goal:** The installed command composes all components, preserves stdout/stderr separation, and enforces every acceptance criterion and exit code.

**Time:** ~2.5 hours

**Context:** Entire `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` P0 requirements.

**Tasks:**

1. Complete `src/nginx_insight/cli.py` orchestration without duplicating calculations in renderers.
2. Map success to 0, unexpected/output failure to 1, Click usage to 2, input/data failure to 3, and unique-cardinality exhaustion to 4.
3. Handle normal downstream pipe closure quietly and suppress tracebacks for expected failures.
4. Create `tests/test_cli_integration.py` covering files, stdin, malformed mixtures, zero-valid input, mutually exclusive formats, renderer parity, stderr isolation, and all `0/1/2/3/4` exits.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py`
- `nginx-insight --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: integrate CLI and exit semantics`

## STEP 8: Quality, Performance, and Release Evidence

**Goal:** The exact release candidate is installable, correct, safe, documented, and measured against the 1 GB target.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` sections 8–10; `PROJECT_ARCHITECTURE.md` sections 9–11.

**Tasks:**

1. Create `tests/test_end_to_end.py` for golden reports and install/entry-point behavior.
2. Create `benchmarks/generate_log.py` for a deterministic declared 1 GB fixture and `benchmarks/README.md` for hardware, command, time, and RSS recording.
3. Create user-facing `README.md` during implementation with install, examples, format schemas, formulas, cardinality limit, privacy, and the full exit table.
4. Run profiling only if the baseline misses the target; record measured changes rather than speculative optimizations.
5. Build wheel/sdist, install the wheel in a clean Python 3.11 environment, freeze the exact candidate, run the repository oracle, and apply the required risk-tier checker.

**Verification:**

- `python3.11 -m ruff check . && python3.11 -m mypy src/nginx_insight && python3.11 -m pytest --cov=nginx_insight --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `/usr/bin/time -v nginx-insight --json benchmarks/data/combined-1gb.log >/dev/null`
- Run the exact-candidate machine oracle and risk-tier checker named by `.itd/VERIFICATION_CONTRACT.json`; accept only a current revalidated adjudication receipt.

**Commit:** `step-8: verify performance and release candidate`

## 3. Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday foundation | 1–3 | Installable contract, models, input, and parser | ~6 hours |
| Saturday/Sunday core | 4–6 | Exact metrics and all renderers | ~7.5 hours |
| Sunday acceptance | 7–8 | End-to-end CLI, benchmark, and release evidence | ~5.5 hours |

## 4. Dependency and Scope Notes

- Steps are dependency-ordered even where a later feature has a higher raw RICE score.
- Gzip support is P1 and begins only after the exact MVP candidate is accepted.
- Custom formats, persistence, API/server behavior, auth, cloud, and Kubernetes are outside this plan.
- If the 30-second target fails, profile within Step 8; opening the multiprocess variant requires an explicit architecture and scope update.

## 5. Final Acceptance Checklist

- [ ] All P0 user-story criteria in `PRD.md` pass.
- [ ] Text, JSON, and CSV derive from one report and agree on values.
- [ ] Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- [ ] The full exit-code contract `0/1/2/3/4` is tested; code 4 remains unique-cardinality exhaustion.
- [ ] A clean Python 3.11 environment installs and runs the built wheel.
- [ ] The documented 1 GB benchmark finishes under 30 seconds on the declared laptop profile.
- [ ] Exact-candidate verification and the applicable risk-tier checker produce a current revalidated adjudication receipt.
