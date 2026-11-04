# Implementation Plan: Nginx Lens

Planning only: none of these steps has been implemented. [Architecture](PROJECT_ARCHITECTURE.md) controls interfaces; [PRD](PRD.md) controls acceptance. [Strategy](STRATEGIC_PLAN.md) supplies priorities. Prompts are in [guide](CLAUDE_CODE_GUIDE.md); agent rules are in [CLAUDE.md](CLAUDE.md).

## Architectural Runway
| Item | Why first | Effort |
|---|---|---|
| Package skeleton and test runner | All work needs an installable entry point | 1 h |
| Report/error contracts | Highest RICE diagnostics depend on stable semantics | 1 h |
No database, auth, containers, or infrastructure setup. Work within 16 hours; Should/Could work is deferred. RICE order is adjusted for parser/report dependencies before terminal integration.

## Shared exit-code contract
Every step preserves: 0 success/help/version; 1 IO/output/runtime failure; 2 usage error; 3 invalid log data; 4 unique-cardinality exhaustion. Never remap or omit 4. All verification commands below are future implementation checks, not executed blueprint evidence. Commit labels are suggestions, not instructions to commit or publish now.

## Step 1: Package and error contracts
**Goal:** Installable entry point with documented error mapping.
**Time:** 1 hour.
**Context:** Architecture CLI Interface and packaging.
**Tasks:** Create `pyproject.toml`, `src/nginx_lens/__init__.py`, `src/nginx_lens/cli.py`, `src/nginx_lens/errors.py`, `tests/test_cli_contract.py`. Define version, Click dependencies, pytest development extra, and console entry. Test help and mutually exclusive output options; preserve codes 0/1/2/3/4.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_cli_contract.py`; `nginx-lens --help`.
**Commit:** `step-1: package and CLI contracts`.

## Step 2: Fixtures and report model
**Goal:** Replayable expected outputs before analytics.
**Time:** 1 hour.
**Context:** Architecture data model and output schema.
**Tasks:** Create `src/nginx_lens/models.py`, `tests/fixtures/combined.log`, `tests/fixtures/expected.json`, `tests/test_models.py`. Hand-calculate counts, ties, UTC buckets, missing UA, and empty-input behavior. Specify safe diagnostics without raw lines.
**Verification:** `python -m pytest tests/test_models.py`.
**Commit:** `step-2: report model and golden fixtures`.

## Step 3: Bounded streaming parser
**Goal:** Yield validated records without retaining input.
**Time:** 3 hours.
**Context:** Architecture input semantics.
**Tasks:** Create `src/nginx_lens/reader.py`, `src/nginx_lens/parser.py`, `tests/test_reader.py`, `tests/test_parser.py`. Cover escaped quotes, IPv6, UTF-8 failures, oversized-line draining, timestamp rollover, query removal, malformed lines, EOF without newline, and stdin ownership.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.
**Commit:** `step-3: bounded combined-log parser`.

## Step 4: Exact analytics and caps
**Goal:** Produce all four analytics with deterministic limits.
**Time:** 3 hours.
**Context:** Architecture exactness and formulas.
**Tasks:** Create `src/nginx_lens/aggregate.py`, `tests/test_aggregate.py`. Test exact top ten with late-arriving winners, separate 4xx/5xx counts, lexical tie breaks, all UTC hours, unique share denominator, zero denominator, repeated keys at cap, and cap+1 for each collection returning 4. Check insertion before mutation.
**Verification:** `python -m pytest tests/test_aggregate.py`.
**Commit:** `step-4: exact bounded analytics`.

## Step 5: Terminal and CLI integration
**Goal:** Default colored summary with safe diagnostics.
**Time:** 2 hours.
**Context:** Architecture CLI Interface and terminal rendering.
**Tasks:** Create `src/nginx_lens/render.py`, `tests/test_terminal.py`; extend `cli.py` and `tests/test_cli_contract.py`. Wire EOF report, strict/default modes and no-valid-record behavior. Verify TTY, NO_COLOR, no-color, markup/control escaping, input failures, and stdout silence on fatal parsing/cap errors.
**Verification:** `python -m pytest tests/test_terminal.py tests/test_cli_contract.py`.
**Commit:** `step-5: terminal workflow`.

## Step 6: Machine exports
**Goal:** Stable JSON and CSV pipeline contracts.
**Time:** 2 hours.
**Context:** Architecture output schema.
**Tasks:** Extend `render.py`; create `tests/test_exports.py`, `tests/fixtures/expected.csv`. Validate schema, quoting commas/newlines, Unicode, section order, all hours, no ANSI, stderr separation, and broken-pipe mapping to 1. Compare every format against the same Report.
**Verification:** `python -m pytest tests/test_exports.py`; `nginx-lens --json tests/fixtures/combined.log`.
**Commit:** `step-6: JSON and CSV exports`.

## Step 7: Performance and resource validation
**Goal:** Measure the target rather than infer it.
**Time:** 2 hours.
**Context:** Architecture performance validation.
**Tasks:** Create `benchmarks/generate.py`, `benchmarks/run.py`, `benchmarks/RESULTS.md`, `tests/test_resource_limits.py`. Runner generates/reads 1,000,000,000 bytes with a fixed seed and records laptop/OS/runtime, cache state, distinct keys, elapsed time, RSS and result correctness per format. Test adversarial cardinality and long lines separately. Profile if target fails; do not remove exactness or claim success.
**Verification:** `python -m pytest tests/test_resource_limits.py`; `python benchmarks/run.py --bytes 1000000000 --repeats 3 --formats terminal,json,csv`.
**Commit:** `step-7: performance evidence and bounds`.

## Step 8: Local release readiness
**Goal:** Verified wheel, help and documentation agree.
**Time:** 2 hours.
**Context:** All specifications.
**Tasks:** Update `README.md`, add `LICENSE`, `tests/test_install.py`; declare build and coverage development dependencies in `pyproject.toml`. Build wheel, install into isolated local environment and run all exit-code cases 0/1/2/3/4. Record coverage and smoke evidence; review differences against PRD. Do not upload or deploy.
**Verification:** `python -m pytest --cov=nginx_lens --cov-branch --cov-fail-under=90`; `python -m build`; `python -m pytest tests/test_install.py`.
**Commit:** `step-8: local wheel readiness`.

## Delivery boundaries
Saturday: steps 1–4 (8 hours). Sunday: steps 5–8 (8 hours). If performance cannot meet the target after bounded profiling, document failure and renegotiate scope/runtime; never silently substitute approximate analytics. Gzip and completions remain deferred. No sprint machinery is needed for eight weekend steps.
