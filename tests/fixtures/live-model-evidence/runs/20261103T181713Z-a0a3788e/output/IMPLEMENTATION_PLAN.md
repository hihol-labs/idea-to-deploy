# Implementation Plan: Nginx Pulse

Planning only. All steps below are pending. [Architecture](PROJECT_ARCHITECTURE.md) owns parsing, metrics, schema and limits; [PRD](PRD.md) supplies acceptance cases. [Strategy](STRATEGIC_PLAN.md) supplies MoSCoW/RICE. Work in priority order subject to dependencies: parser → metrics → diagnostics → terminal → exports → packaging/performance. Do not implement Should/Could work before Must acceptance.

## Architectural Runway
| Item | Why first | Effort |
|---|---|---|
| Package and test scaffolding | Runnable tests before features | 1 hour, step 1 |
| Record/report contracts and synthetic fixtures | Every feature shares these definitions | 2 hours, step 2 |
| Bounded reader and resource exception design | Exact metrics require safe failure behavior | Included in steps 2–3 |
No schema migration, auth, Docker, cloud or deployment runway is needed.

## Implementation Contract
Every step preserves exit codes **0/1/2/3/4**: 0 success/help/version; 1 I/O failure; 2 usage error; 3 no valid input, interruption or processing failure; 4 unique-cardinality exhaustion. Never drop or remap code 4. A failed resource limit produces no final report. This applies to all prompts in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).

Commands below are future verification commands, not results from this blueprint session. Tests are created in the named steps. Run each step's focused checks, then the full suite before a proposed commit. Suggested commit messages are labels only; do not push, publish or delete without explicit human authorization.

## Step 1: Package and test scaffold
**Goal:** Python 3.11 package can be installed locally and tests can import it.
**Time:** 1 hour.
**Context:** Architecture / Packaging; PRD / Scope.
**Tasks:** Create `pyproject.toml`, `src/nginx_pulse/__init__.py`, `tests/test_package.py`, `tests/conftest.py`, `LICENSE` (MIT after owner metadata is supplied). Declare Click/Rich runtime and pytest/build/coverage development dependencies. Do not invent an owner identity or publish a distribution.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_package.py`; `python -m pytest`.
**Commit:** `step-1: establish Python package and test scaffold`.

## Step 2: Bounded input and combined parser
**Goal:** Each supported line yields a typed record or one counted rejection.
**Time:** 2 hours.
**Context:** Architecture / Input and Parsing Contract; PRD story S1.
**Tasks:** Create `src/nginx_pulse/reader.py`, `parser.py`, `models.py`; `tests/test_reader.py`, `tests/test_parser.py`, and synthetic `tests/fixtures/combined.log`. Cover escaped quotes, IPv6, CRLF, invalid bytes, invalid calendar dates, unsupported formats, missing UA, oversized lines and bounded draining. Keep only the current line/record.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`; `python -m pytest`.
**Commit:** `step-2: parse bounded nginx combined input`.

## Step 3: Exact metrics and cardinality guards
**Goal:** Four exact summaries and safe budget failure.
**Time:** 2.5 hours.
**Context:** Architecture / Metrics, Resource Contract; PRD stories S2–S4, S7.
**Tasks:** Create `src/nginx_pulse/aggregate.py`, extend `models.py`; create `tests/test_aggregate.py`. Implement deterministic top-ten selection, 24 local-hour buckets, missing-UA denominator semantics, and preflight slot/byte budgeting before updating a record. Test key duplicates across containers, exact boundary, one over boundary, mixed errors, tie at tenth, multi-date/mixed-offset data and no silent approximation.
**Verification:** `python -m pytest tests/test_aggregate.py`; `python -m pytest`.
**Commit:** `step-3: compute exact metrics with resource guards`.

## Step 4: CLI input and complete failure mapping
**Goal:** File/stdin processing has stable stdout/stderr and all exit codes.
**Time:** 1.5 hours.
**Context:** Architecture / CLI Interface; PRD S1, S5, S7.
**Tasks:** Create `src/nginx_pulse/cli.py`, `tests/test_cli.py`, `tests/test_process.py`. Wire the console entry point, exclusive format flags, positive limit validation, finite stdin, file type checks, warnings and exception mapping. Test codes 0/1/2/3/4 using Click runner plus subprocess checks for broken pipe, interruption and installed command behavior. Never print a success summary on code 4.
**Verification:** `python -m pytest tests/test_cli.py tests/test_process.py`; `python -m pytest`.
**Commit:** `step-4: connect streaming CLI and exit contract`.

## Step 5: Colored terminal report
**Goal:** Operators can read the complete four-view snapshot.
**Time:** 1 hour.
**Context:** Architecture / CLI output; PRD S5.
**Tasks:** Create `src/nginx_pulse/render.py`, `tests/test_terminal.py`. Render totals, top-ten tables, error empty state, hourly percentages and unique-UA share. Treat input strings as literal Rich text; escape controls. Test TTY, redirection, `NO_COLOR`, `--no-color`, markup-looking paths and empty error tables. Machine modes must bypass Rich rendering entirely.
**Verification:** `python -m pytest tests/test_terminal.py`; `python -m pytest`.
**Commit:** `step-5: render operator report safely`.

## Step 6: JSON and CSV pipelines
**Goal:** Both machine formats express the same report deterministically.
**Time:** 1.5 hours.
**Context:** Architecture / Output Schema v1; PRD S6.
**Tasks:** Extend `render.py`; create `tests/test_exports.py`, `tests/fixtures/expected.json`, `tests/fixtures/expected.csv`. Test actual schema, round trips, quoting, six-decimal percentages, row ordering, no ANSI/prose on stdout and parity with terminal/report counts. Use an independently hand-calculated small fixture oracle rather than reusing aggregation code to generate expectations.
**Verification:** `python -m pytest tests/test_exports.py`; `nginx-pulse --json tests/fixtures/combined.log`; `nginx-pulse --csv tests/fixtures/combined.log`; `python -m pytest`.
**Commit:** `step-6: add deterministic JSON and CSV exports`.

## Step 7: Measure and tune throughput
**Goal:** Validate the performance target instead of assuming it.
**Time:** 2 hours.
**Context:** Architecture / Performance and Validation; PRD / Nonfunctional Requirements.
**Tasks:** Create `benchmarks/generate_log.py`, `benchmarks/run.py`, `benchmarks/RESULTS.md`, `tests/test_benchmark_oracle.py`. The generator accepts `--bytes 1000000000 --seed 42 --output PATH` and creates exactly that many bytes of valid newline-terminated combined records with independently known aggregates. The runner accepts `--input PATH --runs 3 --output PATH`, invokes the installed JSON command, measures wall time and peak child RSS on the documented OS, validates its metrics and fails if any run misses the targets. Record corpus, versions, hardware and warm/cold cache conditions. Profile before changing algorithms; preserve exact results. If target fails, record failure and keep release blocked rather than swapping stack or weakening semantics.
**Verification:** `python -m pytest tests/test_benchmark_oracle.py`; `python benchmarks/generate_log.py --bytes 1000000000 --seed 42 --output /tmp/nginx-pulse-bench.log`; `python benchmarks/run.py --input /tmp/nginx-pulse-bench.log --runs 3 --output benchmarks/RESULTS.md`; `python -m pytest`.
**Commit:** `step-7: validate streaming performance and accuracy`.

## Step 8: Local wheel and handoff
**Goal:** A clean environment can use all documented modes.
**Time:** 2.5 hours.
**Context:** Strategy / Definition of Done; PRD / Release and Kill Criteria.
**Tasks:** Update `README.md`, `CLAUDE.md`, `CLAUDE_CODE_GUIDE.md`; create `tests/test_wheel_smoke.py`. Build a wheel, install it in a temporary clean Python 3.11 venv and run help, file/stdin, text/JSON/CSV and the exit matrix. Smoke test must use the installed wheel, not the editable source tree. Record limitations and review/performance evidence. No PyPI upload, remote CI creation or deployment is included.
**Verification:** `python -m pytest --cov=nginx_pulse.parser --cov=nginx_pulse.aggregate --cov-branch --cov-fail-under=90`; `python -m build`; `python -m pytest tests/test_wheel_smoke.py`; `python -m pytest`.
**Commit:** `step-8: verify local wheel and finalize operator docs`.

## Weekend Boundaries
Saturday: steps 1–4, 7 hours. Sunday: steps 5–8, 7 hours. Eight steps do not require multi-sprint PI planning. If work overruns, defer Should/Could features; do not remove Must exports, tests, safety or code 4.

## Current Evidence and Next Action
No product implementation, unit suite, wheel or benchmark exists yet. Next implementation action after external blueprint review: step 1. Product release remains contingent on all PRD acceptance checks.
