# Implementation Plan: Nginx Lens

Status: planned only. Follow [architecture](PROJECT_ARCHITECTURE.md), [PRD](PRD.md), [strategy](STRATEGIC_PLAN.md), and step prompts in [guide](CLAUDE_CODE_GUIDE.md). Eight steps, approximately 16 hours across one weekend. Commit messages below are suggestions, not actions performed by this blueprint.

## Architectural Runway
| Item | Why first | Effort |
|---|---|---|
| pyproject and test harness | Reproducible Python 3.11 install | Included in step 1 |
| Golden fixtures and benchmark protocol | Define correctness and expose throughput risk early | Included in steps 1–3 |
| Dataclass and failure contracts | Keep serializers consistent | Included in steps 1–3 |
No database, auth, Docker or deployment runway is needed. RICE makes performance scaffolding the first concern; executable measurement depends on completed parsing and aggregation. Remaining Must features follow their RICE ranking with packaging prerequisites first. Should/Could features are deferred.

## STEP 1: Package and verification scaffold
**Goal:** Install a local development package and define repeatable measurements.
**Time:** ~1.5 hours.
**Context:** Architecture: Packaging and Execution Environment; Streaming, Limits and Performance.
**Tasks:** Create `pyproject.toml` with Click/Rich runtime and pytest/build development dependencies; `src/nginx_lens/__init__.py`, `models.py`, `errors.py`; `tests/conftest.py`; `benchmarks/README.md` and `benchmarks/generate.py` specifying deterministic 1 GB synthetic combined logs, seed and cardinalities. No external downloads in tests.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_models.py` after adding that test. Check synthetic fixture size independently.
**Commit:** `step-1: package and verification scaffold`.

## STEP 2: Bounded combined-log parser
**Goal:** Stream valid records with explicit rejection accounting.
**Time:** ~2.5 hours.
**Context:** Architecture: Input and Parsing Contract.
**Tasks:** Create `reader.py`, `parser.py`, `tests/test_reader.py`, `tests/test_parser.py`, `tests/fixtures/combined.log`. Cover escaped quotes, IPv6, timezone rollover, malformed requests, overlong lines, invalid UTF-8 and final unterminated records. Drain oversized records without whole-line allocation.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.
**Commit:** `step-2: bounded combined log parsing`.

## STEP 3: Exact bounded aggregation
**Goal:** Compute all four summaries with deterministic rankings.
**Time:** ~3 hours.
**Context:** Architecture: In-Memory Data Model; Streaming, Limits and Performance.
**Tasks:** Create `aggregate.py`, `tests/test_aggregate.py`, `benchmarks/run.py`. Implement exact counts, UTC bins, percentages, cap preflight and top-10 heap selection. Benchmark parser/aggregate now to discover throughput risk before rendering work; save results without asserting final CLI performance.
**Verification:** `python -m pytest tests/test_aggregate.py`; `python benchmarks/run.py --input /tmp/nginx-lens-1gb.log --mode aggregate` after fixture generation per benchmark README. Compare expected counts independently from generator metadata.
**Commit:** `step-3: exact bounded metrics`.

## STEP 4: File and stdin command
**Goal:** Route input, options and failures predictably.
**Time:** ~2 hours.
**Context:** Architecture: CLI Interface.
**Tasks:** Create `cli.py`, `tests/test_cli.py`. Wire console script, input ownership, mutually exclusive exports and positive cap validation. Use a minimal report adapter until step 5. Add subprocess checks of every exit status and stdout/stderr separation.
**Verification:** `python -m pytest tests/test_cli.py`; `nginx-lens --help`.
**Commit:** `step-4: CLI and failure contract`.

## STEP 5: Colored terminal output
**Goal:** Default human-readable report with safe log text.
**Time:** ~2 hours.
**Context:** Architecture: CLI Interface output rules.
**Tasks:** Create `render.py` terminal writer and `tests/test_render_text.py`. Render all bins, rankings and summary counts; escape Rich markup and sanitize terminal controls. Cover TTY, redirect, NO_COLOR and --no-color.
**Verification:** `python -m pytest tests/test_render_text.py`; `nginx-lens tests/fixtures/combined.log --no-color`.
**Commit:** `step-5: terminal summaries`.

## STEP 6: JSON and CSV serializers
**Goal:** Stable pipeline schemas with matching numbers.
**Time:** ~2 hours.
**Context:** Architecture: CLI Interface schema v1.
**Tasks:** Extend `render.py`; create `tests/test_exports.py` and golden expected exports in `tests/fixtures/`. Test CSV quoting, Unicode, empty input, deterministic ties, no ANSI and JSON/CSV parity. Preserve exact URL keys, including potentially unsafe spreadsheet strings.
**Verification:** `python -m pytest tests/test_exports.py`; `nginx-lens --json tests/fixtures/combined.log` and `nginx-lens --csv tests/fixtures/combined.log` compared with golden files.
**Commit:** `step-6: stable JSON and CSV exports`.

## STEP 7: Failure and acceptance integration
**Goal:** Prove P0 edge behavior across installed entry point.
**Time:** ~1.5 hours.
**Context:** PRD: User Stories and Acceptance Fixture; architecture exit contract.
**Tasks:** Create `tests/test_acceptance.py`, `tests/test_exit_codes.py`; exercise stdin, errors, cap boundary and output write failures. Confirm complete contract: 0 success, 1 I/O/internal failure, 2 usage, 3 nonempty all-invalid input, 4 unique-cardinality exhaustion. No partial success report on cap exhaustion.
**Verification:** `python -m pytest`; `python -m pytest --cov=nginx_lens --cov-branch --cov-report=term-missing` with pytest-cov declared in development dependencies; inspect core branch coverage >=90%.
**Commit:** `step-7: acceptance and failure coverage`.

## STEP 8: Performance and local release candidate
**Goal:** Validate installability and the measured performance envelope.
**Time:** ~1.5 hours.
**Context:** Strategy: KPIs and Definition of Done.
**Tasks:** Extend `benchmarks/run.py` to invoke the actual installed CLI and capture elapsed time/peak RSS in three runs per output mode; write `benchmarks/RESULTS.md` with environment, fixture metadata and raw timings. Tune only measured hot paths. Update `README.md`, `CLAUDE.md` and contract documents if behavior is deliberately changed first. Build wheel locally; no publication or deployment.
**Verification:** `python -m pytest`; `python -m build`; `python benchmarks/run.py --input /tmp/nginx-lens-1gb.log --mode all`. Install built wheel in a clean venv and run `nginx-lens --version` and golden acceptance commands. Do not claim the performance goal if any required run fails.
**Commit:** `step-8: measured local release candidate`.

## Delivery Control
Preserve the complete exit-code contract 0/1/2/3/4: success, I/O/internal failure, usage error, nonempty all-invalid input, and unique-cardinality exhaustion respectively.

Do not exceed weekend scope to add gzip, arbitrary formats or dashboards. If exact metrics and the target cannot coexist in this stack, record the benchmark and missed criterion; do not switch language or approximate silently. Publication, push and PR remain separate approval steps. No implementation checks above were executed during blueprint creation.
