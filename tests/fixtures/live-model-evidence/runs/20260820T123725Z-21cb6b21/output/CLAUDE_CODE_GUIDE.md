# Claude Code Guide: nginx-analyzer

## Purpose

This guide turns `IMPLEMENTATION_PLAN.md` into replayable prompts for a future coding session. It does not authorize scope outside `PRD.md` or override the architecture. Run one prompt at a time, preserve WIP=1, and require its verification commands before advancing.

Read these files at the start of every step:

1. `CLAUDE.md`
2. `PRD.md`
3. `PROJECT_ARCHITECTURE.md`
4. `IMPLEMENTATION_PLAN.md`
5. `.itd/SCOPE_LOCK.md` and the active `.itd-memory/STATE.json`, when present

## Non-Negotiable Runtime Contract

Every implementation prompt must preserve and test the complete exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version output |
| `1` | Unexpected internal/runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Input/data failure, including unreadable input, strict malformed input, or zero valid records |
| `4` | Unique-cardinality exhaustion |

Code `4` must not be omitted, reused, or remapped. On codes 3 and 4, emit a safe stderr diagnostic and no partial report.

Other immutable semantics:

- Hourly distribution is a percentage using `100 × hourly_request_count / total_valid_requests`.
- User-Agent share is `100 × distinct_user_agent_count / total_valid_requests`.
- Top lists sort by descending count and ascending lexical key for ties.
- URLs include the logged query string; hours use the logged timestamp hour without timezone conversion.
- There is no database, HTTP API, server, authentication, cloud, Docker, or Kubernetes.

## Prompt 1: Package Scaffold

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. First read PRD.md and
PROJECT_ARCHITECTURE.md, then create the pip-installable Python 3.11 src-layout
package, Click console entry point, version/help behavior, and packaging smoke
test. Do not implement parsing or reports yet. Keep runtime dependencies to
Click and Rich. Run every Step 1 verification command, record actual results,
and stop if any command fails. Update durable Idea to Deploy state from
evidence before handing off.
```

Expected files: `pyproject.toml`, `src/nginx_analyzer/__init__.py`, `src/nginx_analyzer/__main__.py`, `src/nginx_analyzer/cli.py`, `tests/test_packaging.py`.

## Prompt 2: Models and Exit Codes

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md. Define frozen report
dataclasses and typed errors before adding features. Establish one CLI mapping
for all outcomes: 0 success, 1 unexpected failure, 2 usage error, 3 input/data
failure, and 4 unique-cardinality exhaustion. Code 4 is reserved and may not
be omitted or remapped. Add focused tests, run the Step 2 pytest and mypy
commands, record actual output, and update state only from evidence.
```

Expected files: `src/nginx_analyzer/models.py`, `src/nginx_analyzer/errors.py`, updates to `src/nginx_analyzer/cli.py`, and `tests/test_exit_codes.py`.

## Prompt 3: Streaming Parser

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md. Read one path or stdin as a
buffered byte stream and parse the documented nginx combined grammar. Cover
IPv4, IPv6, timezone offsets, escaped quoted fields, literal '-', invalid byte
sequences, empty lines, and malformed records. Never retain raw records or
echo raw malformed lines in diagnostics. Do not add aggregations or renderers.
Run every Step 3 verification command and stop on failure.
```

Expected files: `src/nginx_analyzer/input.py`, `src/nginx_analyzer/parser.py`, parser/input tests, and deterministic fixtures.

## Prompt 4: One-Pass Aggregation

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md. In one pass, count all valid
client IPs, exact request targets for statuses 400-599, 24 logged-hour buckets,
and exact distinct User-Agent values up to the configured ceiling. Compute
hourly percentages with the literal formula
100 × hourly_request_count / total_valid_requests, not an unscaled fraction.
Compute User-Agent share as a percentage. Apply deterministic top-10 tie
ordering. Raise the typed exhaustion error mapped to exit code 4 at ceiling+1;
never approximate or emit a partial report. Run all Step 4 checks.
```

Expected files: `src/nginx_analyzer/aggregate.py`, finalized report models, aggregate tests, and the golden report fixture.

## Prompt 5: Rich Output

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md. Render the shared final report
as a default Rich terminal summary plus four sections. Enable color only for a
TTY unless --no-color is set. Treat every log-derived value as plain untrusted
text: disable or escape markup and terminal controls. Do not calculate metrics
inside the renderer. Run the Rich tests and explicit no-ANSI verification.
```

Expected files: renderer package, `rich_text.py`, CLI selection updates, and `tests/test_rich_output.py`.

## Prompt 6: JSON and CSV

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md. Add schema-versioned JSON and
normalized CSV renderers over the same report model. Make --json and --csv
mutually exclusive so invalid use exits 2. Keep diagnostics on stderr and ANSI
out of machine formats. Add semantic parity tests across Rich, parsed JSON,
and parsed CSV. Run all Step 6 verification commands before handoff.
```

Expected files: `json_output.py`, `csv_output.py`, CLI option updates, and three renderer contract test files.

## Prompt 7: Complete CLI Failure Paths

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. Complete --strict, --encoding,
and --max-unique-user-agents validation plus file/stdin execution. Exercise
real subprocess cases for the full contract: 0 success, 1 unexpected internal
failure, 2 usage error, 3 input/data failure, and 4 unique-cardinality
exhaustion. Code 4 must remain unique and must produce no partial report.
Prove tolerant and strict malformed-line behavior. Run the focused suite, full
suite, and coverage gate; do not advance on narration alone.
```

Expected files: completed CLI/input/errors plus `tests/test_cli.py` and expanded exit tests.

## Prompt 8: Performance Proof

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Create a deterministic local
fixture generator and benchmark runner, then measure the canonical exact 1 GB
fixture after warm-up on the documented reference laptop. Record wall time,
peak RSS, interpreter, OS, CPU, and storage context. The gate is under 30
seconds and under 512 MiB peak RSS. Profile before optimizing and preserve all
golden semantics. Add ceiling+1 exhaustion coverage proving exit code 4. Do not
introduce multiprocessing, a native extension, persistence, or approximation
without first changing the architecture documents.
```

Expected files: benchmark generator/runner/readme, high-cardinality tests, and only evidence-driven parser/aggregator edits.

## Prompt 9: Release Acceptance

```text
Implement only Step 9 of IMPLEMENTATION_PLAN.md. Map every P0 criterion in
PRD.md to an automated or recorded acceptance check. Document supported input,
all output modes, exact metric semantics, and exit codes 0/1/2/3/4. Build a
wheel, install it in a clean Python 3.11 virtual environment, run a JSON smoke
analysis, run the full coverage suite, and rerun the canonical benchmark.
Treat any failed P0 check, code-4 omission/remap, partial error report, or
30-second performance miss as a blocker. Reconcile Idea to Deploy state from
current evidence and provide the explicit next action.
```

Expected files: `README.md`, `CHANGELOG.md`, acceptance tests, and finalized package metadata.

## Verification Handoff Format

At the end of each future implementation step, report:

- Scope completed and exact files changed.
- Verification commands actually run and whether each passed or failed.
- Any acceptance criterion still pending.
- Current WIP unit and the single next action.
- Whether specs changed; if behavior changed without a prior spec update, stop and reconcile the documents.

Do not report a step as complete from prose, an assumed test result, or a stale receipt. Follow the repository's current Idea to Deploy verification contract and risk route.
