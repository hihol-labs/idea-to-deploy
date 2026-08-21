# Implementation Plan: logpulse

> Ordered build plan. Cross-references:
> [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md),
> [PRD.md](PRD.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).

Steps are ordered by RICE score (highest-value first) subject to the hard dependency that
the parser and data model land before any aggregator. Package layout:

```
logpulse/
  __init__.py
  cli.py            # Click entry point, option wiring, exit codes
  input.py          # streaming reader (file / stdin)
  parser.py         # regex parse -> LogRecord | None
  models.py         # dataclasses: LogRecord, Report, HourlyBucket
  aggregate.py      # single-pass folder for all four metrics
  report.py         # build Report from aggregates
  render/
    rich_out.py     # colored terminal renderer
    json_out.py     # --json renderer
    csv_out.py      # --csv renderer
  errors.py         # exit-code constants + typed exceptions
tests/
  test_parser.py
  test_aggregate.py
  test_cli.py
  fixtures/sample_access.log
pyproject.toml
```

## Architectural Runway

Infrastructure/architecture work required BEFORE feature development:

| # | Item | Why first | Effort |
|---|------|-----------|--------|
| 1 | `pyproject.toml` + package skeleton + console entry point | Everything imports from the package; entry point needed to run | 0.25 day |
| 2 | Data model (`models.py` dataclasses) | Parser and aggregators depend on the record/report shapes | 0.25 day |
| 3 | Exit-code constants (`errors.py`) | CLI and aggregators reference the `0/1/2/3/4` contract everywhere | 0.1 day |

## Exit-code contract (`0/1/2/3/4`) — used throughout this plan

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Unexpected internal error |
| `2` | Usage error (invalid arguments/options) |
| `3` | Input error (missing/unreadable file, or zero valid requests) |
| `4` | unique-cardinality exhaustion (unique-User-Agent cap reached) |

Every step below wires against this exact contract; code `4` must not be omitted or remapped.

---

## STEP 1: Package skeleton, data model, exit codes
**Goal:** `pip install -e .` works and `logpulse --version` runs.
**Time:** ~1.5 hours
**Context:** PROJECT_ARCHITECTURE.md — "Data model", "Packaging & deployment", "Exit-code contract".
**Tasks:**
1. Create `pyproject.toml` — deps `click`, `rich`; dev `pytest`; entry point `logpulse = "logpulse.cli:main"`.
2. Create `logpulse/models.py` — `LogRecord`, `Report`, `HourlyBucket` dataclasses (`slots=True`).
3. Create `logpulse/errors.py` — constants `EXIT_OK=0`, `EXIT_INTERNAL=1`, `EXIT_USAGE=2`, `EXIT_INPUT=3`, `EXIT_CARDINALITY=4`, plus `InputError` and `CardinalityExhausted` exceptions.
4. Create `logpulse/cli.py` stub with a Click group and `--version`.
**Verification:**
- `pip install -e . && logpulse --version` prints a version and exits `0`.
- `python -c "import logpulse.models, logpulse.errors"` succeeds.
**Commit:** "step-1: package skeleton, dataclasses, exit-code constants"

## STEP 2: Streaming input reader
**Goal:** Read lines from a file or stdin without loading the whole file.
**Time:** ~1 hour
**Context:** PROJECT_ARCHITECTURE.md — "Component design", "CLI Interface / Positional input".
**Tasks:**
1. Create `logpulse/input.py` — `read_lines(source)` generator: opens the path with buffered IO, or reads `sys.stdin` when `source` is `-`/`None`; `errors="replace"` for encoding safety.
2. Raise `InputError` (→ exit `3`) when a path is missing/unreadable.
**Verification:**
- `printf 'a\nb\n' | python -c "from logpulse.input import read_lines; print(sum(1 for _ in read_lines('-')))"` prints `2`.
- Missing path raises `InputError`.
**Commit:** "step-2: streaming file/stdin reader"

## STEP 3: Log line parser
**Goal:** Turn a combined-format line into a `LogRecord`; skip bad lines.
**Time:** ~2 hours
**Context:** PROJECT_ARCHITECTURE.md — "Data model", metric definitions.
**Tasks:**
1. Create `logpulse/parser.py` — module-level compiled regex for nginx `combined` (and `common`); `parse(line) -> LogRecord | None`.
2. Parse the `[10/Oct/2000:13:55:36 -0700]` timestamp into a `datetime`; strip query string from the URL for grouping.
3. Return `None` for unparseable lines (caller counts them as skipped).
**Verification:**
- `pytest tests/test_parser.py` — valid line parses all fields; malformed line returns `None`.
**Commit:** "step-3: combined/common format parser"

## STEP 4: Single-pass aggregators
**Goal:** Fold records into all four metrics in one pass with bounded memory.
**Time:** ~2 hours
**Context:** PROJECT_ARCHITECTURE.md — "Aggregators", ADR-002; PRD FR-2..FR-5.
**Tasks:**
1. Create `logpulse/aggregate.py` — `Aggregator` holding `Counter` for IPs, `Counter` for error URLs, `list[int]` of length 24, and a bounded `set` for User-Agents plus `max_unique`.
2. `add(record)` increments IP counter, increments error-URL counter only when `400 <= status <= 599`, buckets by `timestamp.hour`, and inserts the UA until the cap; on cap breach set `truncated=True` and stop inserting.
3. Track `valid_requests` and `skipped_lines`.
**Verification:**
- `pytest tests/test_aggregate.py` — error URLs exclude 2xx/3xx; hourly buckets correct; UA cap sets `truncated`.
**Commit:** "step-4: single-pass metric aggregators"

## STEP 5: Report builder + hourly percentage
**Goal:** Produce a typed `Report`, computing hourly percentages.
**Time:** ~1 hour
**Context:** PROJECT_ARCHITECTURE.md — "Metric definitions"; PRD FR-4.
**Tasks:**
1. Create `logpulse/report.py` — `build(aggregator, top) -> Report`.
2. Compute each hourly bucket percent with the literal formula `100 × hourly_request_count / total_valid_requests` (guard `total_valid_requests == 0` → raise `InputError`/exit `3`).
3. Compute `top_ips`/`top_error_urls` via `most_common(top)` with deterministic tie-break; compute `unique_ua_share`.
**Verification:**
- `pytest -k report` — 24 percentages sum to ~100; zero valid requests raises the input error.
**Commit:** "step-5: report builder with hourly percentage"

## STEP 6: Renderers (Rich / JSON / CSV)
**Goal:** Emit the report as colored tables, JSON, or CSV.
**Time:** ~2 hours
**Context:** PROJECT_ARCHITECTURE.md — "Outputs"; PRD FR-6/FR-7/FR-8.
**Tasks:**
1. Create `logpulse/render/rich_out.py` — colored tables + hourly bars; honor `--no-color`/`NO_COLOR`.
2. Create `logpulse/render/json_out.py` — dump the `Report` as one JSON object to stdout.
3. Create `logpulse/render/csv_out.py` — section-delimited CSV blocks to stdout.
**Verification:**
- `logpulse analyze --json tests/fixtures/sample_access.log | python -m json.tool` succeeds.
- `--csv` output parses with `csv.reader`.
**Commit:** "step-6: rich/json/csv renderers"

## STEP 7: CLI wiring + exit-code enforcement
**Goal:** `logpulse analyze` runs end-to-end and returns the correct exit code.
**Time:** ~1.5 hours
**Context:** PROJECT_ARCHITECTURE.md — "CLI Interface", "Exit-code contract".
**Tasks:**
1. Flesh out `logpulse/cli.py` — `analyze` command with `LOGFILE`, `--json/--csv` (mutually exclusive → exit `2`), `--top`, `--format`, `--max-unique`, `--no-color`.
2. Map outcomes to exit codes: success `0`; `InputError`→`3`; `CardinalityExhausted`→`4` (still print the truncated report); unexpected exception→`1`; Click usage errors→`2`.
3. Send all diagnostics to stderr.
**Verification:**
- `logpulse analyze tests/fixtures/sample_access.log; echo $?` → `0`.
- `logpulse analyze --json --csv x; echo $?` → `2`.
- `logpulse analyze /nope; echo $?` → `3`.
- Cap breach via `--max-unique 1` on a multi-UA log → `4`.
**Commit:** "step-7: cli wiring and 0/1/2/3/4 exit codes"

## STEP 8: Tests, performance pass, packaging
**Goal:** Green tests and 1 GB < 30 s on the dev laptop.
**Time:** ~2 hours
**Context:** STRATEGIC_PLAN.md Definition of Done; PRD kill criteria.
**Tasks:**
1. Complete `tests/` (parser, aggregate, cli exit codes) with `tests/fixtures/sample_access.log`; target >= 80% coverage on parser + aggregators.
2. Add a benchmark script that generates a ~1 GB synthetic log and times `analyze`; profile and remove per-line hot-path allocations if needed.
3. Finalize README and `pyproject.toml`; verify `pip install .` from a clean venv.
**Verification:**
- `pytest` all green.
- Benchmark: 1 GB processed in < 30 s; peak memory stays bounded (flat, not O(lines)).
**Commit:** "step-8: tests, perf pass, packaging"

## Sprint boundaries (one weekend)

| Sprint | Steps | Goal | Duration |
|--------|-------|------|----------|
| Sat AM | 1–3 | Skeleton, model, reader, parser | half day |
| Sat PM | 4–5 | Aggregators + report/percentage | half day |
| Sun AM | 6–7 | Renderers + CLI + exit codes | half day |
| Sun PM | 8 | Tests, perf, packaging | half day |
