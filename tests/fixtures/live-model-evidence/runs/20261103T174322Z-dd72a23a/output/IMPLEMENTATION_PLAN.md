# Implementation Plan: Nginx Log Lens

Planning only: every step below is pending. Eight steps, approximately 16 hours across one weekend. Product decisions and MoSCoW priorities are approved; no product code is created in this blueprint.

Read [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for normative semantics, [PRD.md](PRD.md) for acceptance, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for RICE, [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for execution prompts, [CLAUDE.md](CLAUDE.md) for agent rules, and [README.md](README.md) for intended usage.

## Shared implementation contract
Every step preserves exit codes **0/1/2/3/4**: 0 success/help/version; 1 I/O or runtime failure; 2 usage error; 3 no valid requests; 4 unique-cardinality exhaustion. No remapping of code 4. No partial report on parsing/cardinality failures. Output-write failures may leave bytes and must exit 1. Percentages and exact bounded counters follow the architecture. No auth, database, HTTP API, server, cloud or Kubernetes.

## Architectural Runway
| Item | Why first | Effort within steps |
|---|---|---|
| Package and test layout | Imports and isolated CLI invocation must work | Step 1, 1 hour |
| Shared records, report schema and error taxonomy | Parser/aggregates/renderers need stable boundaries | Steps 1–2, 1 hour |
| Hand-calculated fixture and cardinality guards | Correctness and memory bounds precede report polish | Steps 2–3, included |
No database migrations, auth infrastructure, Docker or CI deployment is needed. RICE orders user value; scaffolding and cardinality guards move earlier only where required by dependencies.

## Step 1: Package and interface skeleton
**Goal:** Establish a testable Python 3.11 package and the approved CLI contract.
**Time:** ~1.5 hours.
**Context:** Architecture sections CLI Interface and source structure; PRD F8.
**Tasks:**
1. Create `pyproject.toml`, `src/nginx_log_lens/__init__.py`, `cli.py` and `models.py`; expose `nginx-log-lens` entry point with Click/Rich runtime dependencies and pytest development extras.
2. Create `tests/test_cli.py` covering help/version, conflicting formats, unknown flags, input arity and max-unique range. Define controlled exception types without concealing code 4.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_cli.py -q`.
**Proposed commit:** `step-1: establish package and CLI contract`.

## Step 2: Bounded reader and combined parser
**Goal:** Parse valid records from files/stdin, skip/count malformed records, retain no complete input.
**Time:** ~3 hours.
**Context:** Architecture input/parsing and in-memory models; PRD F1.
**Tasks:**
1. Create `reader.py` and `parser.py`; bound line reads, drain overlong lines, decode UTF-8 and nginx hex escapes, validate timestamp/IP/status/request, canonicalize IPs, strip query strings.
2. Create `tests/test_reader.py`, `tests/test_parser.py` and `tests/fixtures/combined.log` with independently calculated expected records; cover blank/invalid/oversized and unterminated lines, offset and escape edge cases.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py -q`.
**Proposed commit:** `step-2: stream and validate combined records`.

## Step 3: Exact IP and error URL rankings
**Goal:** Compute deterministic top ten IPs and failing paths with bounded exact counters.
**Time:** ~2 hours.
**Context:** Architecture metrics and memory bounds; PRD F2/F3/F7.
**Tasks:**
1. Create `aggregate.py` with per-dimension cap checks before inserting keys; IP counts cover all valid requests, URL counters cover only 4xx/5xx.
2. Create `tests/test_rankings.py`; test >10 keys, lexical ties, 399/400/499/500/599 boundaries and independent IP/URL cap exhaustion. A repeated key at capacity must succeed.
**Verification:** `python -m pytest tests/test_rankings.py -q`.
**Proposed commit:** `step-3: add bounded exact traffic and error rankings`.

## Step 4: Hourly percentages and unique UA share
**Goal:** Complete the four analytics using the documented denominators.
**Time:** ~1.5 hours.
**Context:** Architecture metrics; PRD F4/F5.
**Tasks:**
1. Extend `aggregate.py` and `models.py` with hour/UA state, independent caps, UTC-instant bucket ordering and report finalization.
2. Create `tests/test_metrics.py`; assert `100 × hourly_request_count / total_valid_requests`, six-place serialization expectations, A/A/B UA share, missing-UA denominator, DST offsets and empty-input handling.
**Verification:** `python -m pytest tests/test_metrics.py tests/test_rankings.py -q`.
**Proposed commit:** `step-4: implement hourly and client diversity metrics`.

## Step 5: Human and machine reports
**Goal:** Render default Rich text and schema-stable JSON/CSV.
**Time:** ~2 hours.
**Context:** Architecture CLI output schemas; PRD F6.
**Tasks:**
1. Create `render.py`; escape terminal controls/markup, disable ANSI for non-TTY and machine modes, preserve machine-field values with valid serialization.
2. Create `tests/test_render.py` with JSON parsing and CSV readback assertions, explicit summary rows, empty error ranking, Unicode, quoted cells and ordering. Check color behavior without relying only on snapshots.
**Verification:** `python -m pytest tests/test_render.py -q`.
**Proposed commit:** `step-5: render deterministic terminal JSON and CSV reports`.

## Step 6: End-to-end failure contract
**Goal:** Wire the full stream lifecycle with precise stdout/stderr and exit behavior.
**Time:** ~2 hours.
**Context:** Architecture CLI Interface; every P0 story.
**Tasks:**
1. Complete `cli.py` input ownership, EOF finalization, diagnostic summaries and controlled exception mapping, including broken pipes and interruption.
2. Extend `tests/test_cli.py` and create `tests/test_pipeline.py`; cover complete 0/1/2/3/4 behavior, each capped dimension, file/stdin equivalence, unreadable input, all-malformed input, mid-read failures and failing output streams.
**Verification:** `python -m pytest tests/test_cli.py tests/test_pipeline.py -q`.
**Proposed commit:** `step-6: enforce complete CLI failure and pipeline contract`.

## Step 7: Performance qualification
**Goal:** Measure the 1 GB target and bounded-memory behavior before claiming readiness.
**Time:** ~2.5 hours.
**Context:** Architecture performance envelope; strategic release gates.
**Tasks:**
1. Create `benchmarks/generate.py`, `benchmarks/run.py`, `tests/test_benchmark_fixture.py` and `benchmarks/RESULTS.md`. Generator accepts `--bytes 1000000000 --output PATH`, emits complete lines totaling at least that size, and reports actual bytes and cardinalities. Runner accepts `--input PATH --runs 3`, executes the installed CLI with JSON output consumed by a sink, records wall time/peak RSS and platform metadata.
2. Use baseline-valid combined lines with bounded IP/path/UA/hour dimensions; label them synthetic. Test generator summary independently against a small hand-calculated sample. Profile bottlenecks if needed without changing semantics. Separately exercise high cardinality and maximum-length input.
**Verification:** `python -m pytest tests/test_benchmark_fixture.py -q`; `python benchmarks/generate.py --bytes 1000000000 --output /tmp/nginx-log-lens-benchmark.log`; `python benchmarks/run.py --input /tmp/nginx-log-lens-benchmark.log --runs 3`.
**Proposed commit:** `step-7: qualify throughput and bounded resource behavior`.
Benchmark files remain local. If time runs out before meeting targets, record failure and stop release; do not silently widen the benchmark envelope.

## Step 8: Package, documentation and local release candidate
**Goal:** Produce a reproducible local installation with all Must gates checked.
**Time:** ~1.5 hours.
**Context:** Strategy Definition of Done; architecture installation.
**Tasks:**
1. Add `LICENSE` (MIT), `tests/test_package.py` and build extras in `pyproject.toml`; update `README.md`, this plan, PRD and guide with actual verified behavior and limitations.
2. Build a wheel, install it in an isolated environment, run stdin/file/text/JSON/CSV smoke tests and the entire test suite with branch coverage. Record results, obtain implementation review and check security handling. Do not publish or push without separate human authorization.
**Verification:** `python -m pytest --cov=nginx_log_lens --cov-branch --cov-report=term-missing --cov-fail-under=90`; `python -m build`; `python -m pytest tests/test_package.py -q`.
**Proposed commit:** `step-8: verify local package and document release candidate`.
The package test must create a temporary venv, install the built wheel, invoke its console entry point, and check all output modes. Proposed commits are future actions, not commits performed in this session.

## Schedule and tracking
Saturday: steps 1–4 (8 hours). Sunday: steps 5–8 (8 hours). All steps pending. Eight steps do not require the skill's >8-step multi-sprint cadence. Deferred gzip/custom-format features are excluded from the weekend total.
