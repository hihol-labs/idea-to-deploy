# Implementation Plan: nginx-stream-stats

## Planning Rules

This is a dependency-ordered one-weekend plan derived from `PRD.md` and `PROJECT_ARCHITECTURE.md`. It creates a single Python 3.11 process and no database, HTTP API, authentication, server, cloud, or Kubernetes component. Complete one step and attach its evidence before beginning the next (WIP=1).

The implementation must preserve this complete exit-code contract in every step that touches CLI behavior:

| Code | Meaning |
|---:|---|
| `0` | Successful report, even when some lines are malformed |
| `1` | Runtime/input/output failure |
| `2` | Usage/configuration error |
| `3` | Zero valid requests |
| `4` | Unique-cardinality exhaustion for exact IP, error-URL, or User-Agent tracking |

## Architectural Runway

These items precede feature work because every metric and renderer depends on them.

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | PEP 621 package, Python 3.11 CI, test/coverage configuration | Establishes install, console entry, and evidence commands | 1.0 h |
| 2 | Typed dataclasses and error taxonomy | Prevents renderers and CLI from inventing incompatible semantics | 1.0 h |
| 3 | Combined-format fixture corpus | Gives parser work executable acceptance examples | 0.5 h |
| 4 | Benchmark fixture generator and measurement protocol | Tests the 30-second risk before polish | 1.0 h |

No schema migration, auth, Docker, or deployment infrastructure belongs in the runway because the architecture explicitly excludes those systems.

## Step 1: Package and Quality Skeleton

**Goal:** A clean Python 3.11 environment can install the project and invoke an empty, tested console entry without implementing analytics.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Technology Stack,” “Component Boundaries,” and “Deployment and Packaging.”

**Tasks:**

1. Create `pyproject.toml` with PEP 621 metadata, Python `>=3.11,<3.12`, Click/Rich dependencies, pytest/coverage development extras, src layout, and console entry point.
2. Create `src/nginx_stream_stats/__init__.py` containing package version metadata only.
3. Create `src/nginx_stream_stats/cli.py` with the Click command boundary and version/help behavior, leaving product work for later steps.
4. Create `tests/test_cli.py` with install/help/version smoke tests.
5. Create `.github/workflows/ci.yml` for Python 3.11 install and test commands if hosted CI is enabled.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-stats --help`
- `.venv/bin/python -m pytest tests/test_cli.py -q`

**Commit:** `step-1: establish installable CLI skeleton`

## Step 2: Domain Models and Failure Taxonomy

**Goal:** Parser, aggregation, report, and typed failure contracts exist independently of presentation.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Domain and Data Model,” “Streaming and Resource Contract,” and “CLI Interface.”

**Tasks:**

1. Create `src/nginx_stream_stats/models.py` with frozen `AccessRecord`, `RankedCount`, `HourlyShare`, `Report`, and validated `AggregationConfig` dataclasses.
2. Define typed parse rejection and cardinality-exhaustion exceptions; exhaustion must carry the exact dimension name.
3. Add `tests/test_models.py` for invalid cardinality values, tuple/report invariants, and error metadata.

**Verification:**

- `.venv/bin/python -m pytest tests/test_models.py -q`
- `.venv/bin/python -m compileall -q src/nginx_stream_stats`

**Commit:** `step-2: define analytics domain contracts`

## Step 3: Combined-Format Parser and Inputs

**Goal:** Plain files and stdin yield valid records incrementally while malformed lines are distinguishable and counted upstream.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Parsing Contract”; `PRD.md` US-1 and FR-002/FR-003.

**Tasks:**

1. Create `src/nginx_stream_stats/parser.py` with one compiled combined-format parser, timezone-aware timestamp parsing, and request-target extraction.
2. Create `src/nginx_stream_stats/inputs.py` with lazy strict-decoding stream contexts for paths and stdin; never close caller-owned stdin.
3. Add valid IPv4/IPv6, escaped/space-bearing User-Agent, error, malformed, blank, and bad-timestamp examples under `tests/fixtures/`.
4. Create `tests/test_parser.py` and `tests/test_inputs.py` covering fixtures, multiple-file ordering, strict decode/open errors, and no `read()`/`readlines()` use.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py tests/test_inputs.py -q`
- `.venv/bin/python -m pytest tests/test_inputs.py -q --maxfail=1`

**Commit:** `step-3: stream and parse nginx combined logs`

## Step 4: Streaming Aggregation and Exactness Guard

**Goal:** One pass computes all four required metrics deterministically and refuses unsafe cardinality growth.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Domain and Data Model” and “Streaming and Resource Contract”; `PRD.md` US-2 through US-5.

**Tasks:**

1. Create `src/nginx_stream_stats/aggregate.py` to count IPs, 400–599 request targets, 24 logged-time hours, exact User-Agents, valid lines, and malformed lines.
2. Implement deterministic top-10 sorting by count descending and key ascending.
3. Compute hourly percentages with exactly `100 × hourly_request_count / total_valid_requests` and User-Agent share with its specified percentage formula.
4. Check the per-dimension ceiling before retaining a new distinct value; raise the typed exhaustion error rather than truncate or approximate.
5. Create `tests/test_aggregate.py` for boundaries (399/400/599), ties, zero hours, malformed exclusions, percentage/count consistency, and each exhaustion dimension.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_stream_stats.aggregate --cov-fail-under=95 -q`

**Commit:** `step-4: implement exact bounded streaming metrics`

## Step 5: Rich Terminal Renderer

**Goal:** The default report is readable, colored terminal text with all metrics and no calculation logic.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` “Output Consistency” and CLI outputs; `PRD.md` US-6.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/__init__.py`.
2. Create `src/nginx_stream_stats/renderers/terminal.py` with summary, ranked tables, 24-hour distribution, and User-Agent exact count/share.
3. Add terminal golden cases to `tests/test_output_contracts.py`, normalizing color only in assertions intended to compare data.

**Verification:**

- `.venv/bin/python -m pytest tests/test_output_contracts.py -q -k terminal`
- `NO_COLOR=1 .venv/bin/nginx-stream-stats tests/fixtures/mixed.log`

**Commit:** `step-5: render rich terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Machine modes emit schema-version-1 output equivalent to the terminal report and nothing else on stdout.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” output schemas; `PRD.md` US-7.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/json.py` with the exact JSON v1 shape and numeric rounding policy.
2. Create `src/nginx_stream_stats/renderers/csv.py` with header `schema_version,row_type,rank,key,count,percentage`, stable row order, standard quoting, and `\n` endings.
3. Extend `tests/test_output_contracts.py` to parse both formats and compare ranks, counts, all 24 hours, percentages, and User-Agent metrics against the same expected report.

**Verification:**

- `.venv/bin/python -m pytest tests/test_output_contracts.py -q -k 'json or csv or equivalent'`
- `.venv/bin/nginx-stream-stats --json tests/fixtures/mixed.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV schemas`

## Step 7: CLI Orchestration and Complete Exit Contract

**Goal:** The command wires input → parser → aggregation → one renderer and maps every expected outcome to `0/1/2/3/4`.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` exact `## CLI Interface`; `PRD.md` FR-009 through FR-011 and exit matrix.

**Tasks:**

1. Complete `src/nginx_stream_stats/cli.py` with `[INPUT]...`, `--json`, `--csv`, `--no-color`, `--encoding`, and positive `--max-unique`.
2. Reject mutually exclusive modes, repeated stdin, unknown encodings, and invalid cardinality as Click usage failures (2).
3. Map runtime/input/output failures to 1, zero-valid results to 3, and typed exact-cardinality exhaustion to 4; success is 0.
4. Ensure report data alone uses stdout and concise diagnostics use stderr, with no partial JSON/CSV on codes 1/3/4.
5. Extend `tests/test_cli.py` with explicit cases for every code `0/1/2/3/4`, stdout/stderr separation, no ANSI in machine modes, multiple inputs, and closed-pipe behavior.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'exit or stdout or stderr'`

**Commit:** `step-7: enforce CLI and exit-code contracts`

## Step 8: Performance, Memory, and Package Acceptance

**Goal:** The exact candidate has reproducible evidence for correctness, pip installation, bounded-cardinality memory behavior, and the 1 GB/<30-second target.

**Time:** ~2 hours plus fixture generation

**Context:** `PRD.md` NFR-001 through NFR-005 and Release Acceptance; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Create `tests/fixtures/generate_benchmark.py` to deterministically generate or stream a declared 1 GB combined-format fixture with documented cardinalities; do not commit the generated log.
2. Create `tests/test_performance.py` for a smaller CI performance guard and streaming memory-growth checks.
3. Create `scripts/benchmark.sh` to record Python version, hardware/OS summary, fixture size/hash, cache condition, command, elapsed time, and peak RSS.
4. Run full tests with coverage, build wheel/sdist, install the wheel into a fresh temporary virtualenv, and smoke-test all three outputs.
5. Run the 1 GB benchmark on the target laptop and preserve its evidence in the project-designated verification record.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_stream_stats --cov-report=term-missing --cov-fail-under=90 -q`
- `.venv/bin/python -m build`
- `sh scripts/benchmark.sh`

**Commit:** `step-8: prove correctness packaging and performance`

## Step 9: P1 Gzip and Release Documentation

**Goal:** If the weekend budget remains, gzip works without semantic changes and release documentation is complete; otherwise gzip is explicitly deferred without blocking P0.

**Time:** ~1 hour

**Context:** `PRD.md` US-8; `PROJECT_ARCHITECTURE.md` input and deployment contracts.

**Tasks:**

1. Extend `src/nginx_stream_stats/inputs.py` with streaming `.gz` selection using `gzip.open` and identical strict decoding.
2. Add a matching compressed fixture and parity cases to `tests/test_inputs.py` and `tests/test_cli.py`.
3. Update `README.md` with Quick Start, examples, supported format, schemas, exits `0/1/2/3/4`, cardinality behavior, privacy, and performance methodology.
4. Reconcile `CLAUDE.md` status and the Idea to Deploy unit state with actual evidence.

**Verification:**

- `.venv/bin/python -m pytest -q`
- `.venv/bin/nginx-stream-stats --json tests/fixtures/mixed.log.gz | .venv/bin/python -m json.tool >/dev/null`
- `git diff --check`

**Commit:** `step-9: add gzip parity and release documentation`

## Sprint Boundaries

The weekend uses short integration boundaries rather than multi-week sprints.

| Boundary | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable foundation and reliable input contract | ~4 h |
| Saturday PM | 4–5 | Complete metrics and human report | ~3 h |
| Sunday AM | 6–7 | Pipeline schemas and all operational exits | ~3.5 h |
| Sunday PM | 8–9 | Performance/package evidence, P1 if capacity, handoff | ~3 h + benchmark generation |

## Dependency and Priority Notes

RICE orders value, but parser/model runway precedes higher-scoring metrics because they cannot be implemented or verified safely without records and fixtures. P0 steps 1–8 are the release path. Step 9's gzip portion is P1 and may be deferred; its documentation and state-reconciliation tasks remain required. P2 top-N and custom formats are outside the weekend plan.

## Final Verification Loop

Before accepting implementation—not during this blueprint-only session—freeze the exact staged candidate, exclude undeclared ignored/untracked overlays, run the configured machine oracle, and obtain the current risk-tier adjudication receipt required by `.itd/VERIFICATION_CONTRACT.json`. A standalone test log or prose “passed” statement is insufficient. If no active executable verification contract is configured, status remains recovery-required until one is established.
