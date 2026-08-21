# Claude Code Guide: logpulse

> Copy-paste prompts to build logpulse with Claude Code, one step at a time.
> Follows [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); grounded in
> [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and [PRD.md](PRD.md).
> Run each prompt, verify, commit, then move to the next (WIP=1).

## Ground rules for every prompt

- Stack is fixed: Python 3.11, Click, Rich, dataclasses, pip. Do not add other deps.
- Stateless single-pass streaming. No database, no server, no HTTP API.
- After each step: run the verification command, then commit with the given message.

## Exit-code contract (`0/1/2/3/4`) — reference for all prompts

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Unexpected internal error |
| `2` | Usage error (invalid arguments/options) |
| `3` | Input error (missing/unreadable file, or zero valid requests) |
| `4` | unique-cardinality exhaustion (unique-User-Agent cap reached) |

Every prompt that touches the CLI or aggregators must implement this full `0/1/2/3/4`
contract. Do not omit or remap code `4`. Code `4` is raised on:

unique-cardinality exhaustion

---

## Prompt 1 — Package skeleton, data model, exit codes

```
Create a pip-installable Python 3.11 package `logpulse`.
- pyproject.toml: deps click, rich; dev dep pytest; console entry point
  `logpulse = "logpulse.cli:main"`.
- logpulse/models.py: dataclasses (slots=True) LogRecord, Report, HourlyBucket exactly
  as in PROJECT_ARCHITECTURE.md "Data model".
- logpulse/errors.py: EXIT_OK=0, EXIT_INTERNAL=1, EXIT_USAGE=2, EXIT_INPUT=3,
  EXIT_CARDINALITY=4, plus InputError and CardinalityExhausted exceptions.
- logpulse/cli.py: Click group stub with --version.
Do not implement metrics yet.
```
**Verify:** `pip install -e . && logpulse --version` → exits `0`.
**Commit:** `step-1: package skeleton, dataclasses, exit-code constants`

## Prompt 2 — Streaming reader

```
Add logpulse/input.py with a generator read_lines(source) that streams lines from a file
path, or from stdin when source is "-" or None. Use buffered IO and errors="replace".
Raise InputError (maps to exit 3) when a path is missing or unreadable. Never read the
whole file into memory.
```
**Verify:** `printf 'a\nb\n' | python -c "from logpulse.input import read_lines; print(sum(1 for _ in read_lines('-')))"` → `2`.
**Commit:** `step-2: streaming file/stdin reader`

## Prompt 3 — Parser

```
Add logpulse/parser.py: module-level compiled regex for nginx combined (default) and
common formats. parse(line) -> LogRecord | None. Parse the [10/Oct/2000:13:55:36 -0700]
timestamp into a datetime; strip the query string from the URL for grouping. Return None
for unparseable lines. Add tests/test_parser.py covering a valid line and a malformed line.
```
**Verify:** `pytest tests/test_parser.py` green.
**Commit:** `step-3: combined/common format parser`

## Prompt 4 — Aggregators

```
Add logpulse/aggregate.py with an Aggregator that folds records in ONE pass:
- Counter for IPs
- Counter for error URLs, incremented only when 400 <= status <= 599
- list[int] length 24 bucketed by timestamp.hour
- a bounded set for User-Agents with max_unique; on breach set truncated=True and stop
  inserting (this drives exit code 4)
Track valid_requests and skipped_lines. Add tests/test_aggregate.py.
```
**Verify:** `pytest tests/test_aggregate.py` green (error URLs exclude 2xx/3xx; cap sets truncated).
**Commit:** `step-4: single-pass metric aggregators`

## Prompt 5 — Report builder + hourly percentage

```
Add logpulse/report.py: build(aggregator, top) -> Report. Compute each hourly bucket
percent using the literal formula: 100 × hourly_request_count / total_valid_requests
(NOT an unscaled fraction). If total_valid_requests == 0, raise InputError (exit 3).
Compute top_ips/top_error_urls via most_common(top) with a deterministic tie-break
(count desc, key asc), and unique_ua_share = unique_user_agents / valid_requests.
```
**Verify:** `pytest -k report` — 24 percentages sum to ~100; zero valid requests → input error.
**Commit:** `step-5: report builder with hourly percentage`

## Prompt 6 — Renderers

```
Add logpulse/render/rich_out.py (colored Rich tables + hourly bars, honoring --no-color
and NO_COLOR), logpulse/render/json_out.py (dump Report as one JSON object to stdout),
and logpulse/render/csv_out.py (section-delimited CSV to stdout). Diagnostics go to stderr.
```
**Verify:** `logpulse analyze --json tests/fixtures/sample_access.log | python -m json.tool` succeeds.
**Commit:** `step-6: rich/json/csv renderers`

## Prompt 7 — CLI wiring + exit codes

```
Flesh out logpulse/cli.py: `analyze` command with positional LOGFILE (default stdin via
"-"), --json/--csv (mutually exclusive → exit 2), --top (default 10), --format
(combined/common), --max-unique (default 2000000 or LOGPULSE_MAX_UNIQUE), --no-color.
Map outcomes to the full 0/1/2/3/4 exit-code contract:
  0 success; 1 unexpected error; 2 usage error; 3 input error;
  4 unique-cardinality exhaustion (print the truncated report, then exit 4).
All diagnostics to stderr.
```
**Verify:**
- `logpulse analyze tests/fixtures/sample_access.log; echo $?` → `0`
- `logpulse analyze --json --csv x; echo $?` → `2`
- `logpulse analyze /nope; echo $?` → `3`
- `logpulse analyze --max-unique 1 tests/fixtures/sample_access.log; echo $?` → `4`
**Commit:** `step-7: cli wiring and 0/1/2/3/4 exit codes`

## Prompt 8 — Tests, performance, packaging

```
Complete tests (parser, aggregate, cli exit codes) with tests/fixtures/sample_access.log,
>= 80% coverage on parser + aggregators. Add a benchmark that generates a ~1 GB synthetic
nginx log and times `logpulse analyze`; ensure it finishes in < 30 s with bounded (flat)
memory. Finalize README and pyproject.toml; verify `pip install .` in a clean venv.
```
**Verify:** `pytest` all green; benchmark: 1 GB < 30 s.
**Commit:** `step-8: tests, perf pass, packaging`

## Final review

Run `/review` and confirm the six blueprint documents and the code agree, especially the
`0/1/2/3/4` exit-code contract and the hourly-percentage formula. Then run `/session-save`.
