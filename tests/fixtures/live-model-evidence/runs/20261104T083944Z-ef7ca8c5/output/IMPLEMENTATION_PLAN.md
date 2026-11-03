# Implementation Plan: nginx-logstats

This is a future implementation plan, not completed work. Product scope and priorities are pre-approved in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md); observable acceptance lives in [PRD.md](PRD.md). Follow [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) when implementing interfaces. No commits, publication, or product code are part of this blueprint session.

## Architectural Runway
| Prerequisite | Why first | Effort |
|---|---|---|
| Package and isolated test skeleton | Verify the installed CLI rather than imports alone | 1 hour |
| Golden fixture and data contracts | Establish exact independent metric expectations | 1 hour within step 2 |
| Exit mapping and bounded-state policy | Prevent silent partial or approximate results | Defined here; implemented in steps 3–4 |

No database, authentication, Docker, HTTP infrastructure, deployment pipeline, or migration runway is applicable. All paths and commands below describe artifacts to create later. Use WIP=1; complete verification before the next step. Commit messages are suggestions only; committing requires a green suite and any applicable project gate.

## Shared Exit-Code Contract
Every step preserves `0/1/2/3/4`: 0 = clean success including empty input/help/version; 1 = I/O or runtime failure including broken pipe/interrupt; 2 = usage failure; 3 = complete report with malformed input skipped; 4 = unique-cardinality exhaustion with no report. Terminal failures override accumulated malformed lines; output failure returns 1. Never remap code 4. Check diagnostics on stderr and machine data on stdout independently.

## Step 1: Package and Test Runway
**Goal:** A local wheel exposes the command and module entry point.
**Time:** 1 hour.
**Context:** Architecture: Components and CLI Interface.
**Tasks:** Create `pyproject.toml` with Python >=3.11, Click/Rich dependencies, setuptools backend, pytest/coverage development extras, and `nginx-logstats` console script. Create `src/nginx_logstats/__init__.py`, `__main__.py`, initial `cli.py`, and `tests/test_package.py`. Begin with help/version only. Record the proposed MIT license in `LICENSE` after checking contributor ownership.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_package.py`; `nginx-logstats --help`; `python -m nginx_logstats --version`.
**Suggested commit:** `step-1: add installable CLI runway`.

## Step 2: Combined Parser and Independent Fixtures
**Goal:** Valid records become typed data and malformed records are identifiable.
**Time:** 2.5 hours.
**Context:** Architecture: Input and Parsing Contract; PRD story 1.
**Tasks:** Create `models.py`, `parser.py`, `tests/test_parser.py`, `tests/fixtures/combined.log`, and `tests/fixtures/expected.json`. Hand-calculate expectations without importing the implementation. Cover IPv4/IPv6, escaped fields, timezone validation, final unterminated lines, status boundaries, request parsing, and malformed cases.
**Verification:** `python -m pytest tests/test_parser.py`.
**Suggested commit:** `step-2: parse documented nginx combined records`.

## Step 3: Exact Metrics and Cardinality Guard
**Goal:** Accumulate all four metrics with deterministic ties and atomic exhaustion.
**Time:** 2.5 hours.
**Context:** Architecture: In-memory Data Contracts and Cardinality; PRD stories 2 and 6.
**Tasks:** Create `aggregate.py`, `tests/test_aggregate.py`, `tests/test_limits.py`. Add per-IP/error-URL counts, 24 hours, exact User-Agent set, percent denominators, bounded top-10 selection, and combined key limit. Test K at limit and one record adding multiple keys past the limit. Assert rejected records do not partially mutate state. Test zero denominator and more than ten tied keys.
**Verification:** `python -m pytest tests/test_aggregate.py tests/test_limits.py`.
**Suggested commit:** `step-3: add exact bounded aggregation`.

## Step 4: Streaming Reader and Command Orchestration
**Goal:** Process a file or stdin to EOF and enforce all failure codes.
**Time:** 2 hours.
**Context:** Architecture: Input, CLI Interface and Exit Codes; PRD story 3.
**Tasks:** Create `reader.py`, `tests/test_reader.py`, `tests/test_cli_errors.py`; extend `cli.py`. Bound line buffering, drain oversized records, count malformed lines, validate conflicting flags and positive limits before input. Use subprocess tests for missing file, injected read failure, broken pipe, keyboard interruption, and cardinality exhaustion. Do not echo raw log data in diagnostics.
**Verification:** `python -m pytest tests/test_reader.py tests/test_cli_errors.py`.
**Suggested commit:** `step-4: connect streaming input and failure contract`.

## Step 5: Terminal Report
**Goal:** Default output makes the four metrics readable and safe to display.
**Time:** 1.5 hours.
**Context:** Architecture: Outputs; PRD story 4.
**Tasks:** Create terminal rendering in `render.py` and `tests/test_terminal.py`. Include valid/malformed counts, top lists, every hour, distinct-agent share, two-decimal percentages, TTY color detection, and `--no-color`. Treat Rich markup and control characters as untrusted data.
**Verification:** `python -m pytest tests/test_terminal.py`; `nginx-logstats --no-color tests/fixtures/combined.log` (golden fixture is valid, exit 0).
**Suggested commit:** `step-5: render terminal metric summary`.

## Step 6: JSON and CSV Serialization
**Goal:** Pipeline reports agree exactly on counts and schema.
**Time:** 2 hours.
**Context:** Architecture: CLI Outputs; PRD story 5.
**Tasks:** Extend `render.py`; create `tests/test_exports.py`, `tests/test_cli.py`. Test independent golden JSON, explicit CSV rows/columns, quoting, non-ASCII keys, no ANSI or stderr pollution, valid-only output with code 3, and no report on code 4. Verify all exit codes through installed-command subprocesses.
**Verification:** `python -m pytest tests/test_exports.py tests/test_cli.py`; `nginx-logstats --json tests/fixtures/combined.log`; `nginx-logstats --csv tests/fixtures/combined.log`.
**Suggested commit:** `step-6: add stable machine-readable reports`.

## Step 7: Laptop Throughput and Resource Acceptance
**Goal:** Measure the 1 GB objective and default resource envelope.
**Time:** 3 hours.
**Context:** Architecture: Complexity and Performance; PRD nonfunctional requirements.
**Tasks:** Create `benchmarks/generate.py`, `benchmarks/run.py`, `benchmarks/README.md`, and `tests/test_streaming.py`. Generator takes `--bytes 1000000000 --output benchmarks/input.log`, produces exactly that byte size using complete valid combined records, and writes independent expected counters. Use bounded cardinality with a separate near-cap scenario, plus mixed errors, varied hours, and User-Agents. Do not include input generation in timing. Runner takes `--input`, `--runs`, `--output`, times the installed CLI from launch through JSON serialization/exit, checks outputs each run, and records peak RSS and environment. Measure one cold-cache run separately and three warm-cache runs; all three warm runs must be under 30 seconds and at most 512 MiB peak RSS on a recorded laptop with SSD and at least 8 GiB RAM. Record CPU, RAM, OS, Python/dependency versions, cache policy, fixture bytes and K. A target met on this fixture is not a guarantee for all laptops or key distributions. Also exercise an over-cap fixture expecting code 4. Profile failures; reduce allocations without weakening exactness or limits.
**Verification:** `python -m pytest tests/test_streaming.py`; `python benchmarks/generate.py --bytes 1000000000 --output benchmarks/input.log`; `python benchmarks/run.py --input benchmarks/input.log --runs 3 --output benchmarks/results.json`.
**Suggested commit:** `step-7: verify throughput and bounded memory`.

## Step 8: Installed Release Candidate and Documentation
**Goal:** A local wheel and documentation support a repeatable handoff.
**Time:** 1.5 hours.
**Context:** Strategic Definition of Done and all P0 acceptance criteria.
**Tasks:** Update `README.md`, `CLAUDE.md`, and `benchmarks/README.md` with measured evidence. Create `tests/test_installed_cli.py` and test a wheel in `.venv-release`. Run the full suite and core branch coverage, inspect distribution contents for logs/secrets, and perform local dry runs. Record unfulfilled criteria honestly. Independent review remains a separate gate; package publication, push, and deployment require approval.
**Verification:** `python -m pytest --cov=nginx_logstats --cov-branch --cov-fail-under=90`; `python -m pip wheel . --no-deps -w dist`; `python -m venv .venv-release`; `.venv-release/bin/python -m pip install dist/nginx_logstats-0.1.0-py3-none-any.whl`; `.venv-release/bin/python -m pytest tests/test_installed_cli.py` (install test tooling in that environment first). Final wheel version and path must match `pyproject.toml`; 0.1.0 is the initial planned version.
**Suggested commit:** `step-8: prepare verified local release candidate`.

## Schedule and Handoff
Steps total 16 hours, split over one weekend. Package runway precedes RICE-ranked Must features; throughput acceptance follows functioning output. Additional formats and shell completion remain deferred. Use [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for step prompts and [CLAUDE.md](CLAUDE.md) for status. Save session context at milestones. No implementation steps have been executed in this blueprint session.
