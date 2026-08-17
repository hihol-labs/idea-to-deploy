# Claude Code Implementation Guide: Nginx Stream Analyzer

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts for future
implementation sessions. It does not contain product code and does not mark
any implementation step complete. Run one prompt at a time in order (WIP=1),
preserve unrelated user changes, and attach the named verification evidence
before updating status in `CLAUDE.md`.

## Permanent Contract for Every Prompt

Before editing, read `AGENTS.md`, `.itd/SCOPE_LOCK.md`, `PRD.md`,
`PROJECT_ARCHITECTURE.md`, and the relevant step in `IMPLEMENTATION_PLAN.md`.
Treat the P0 acceptance criteria as the behavioral source of truth and the
architecture as the technical source of truth.

The process exit contract is always complete and must appear in tests:

- `0`: successful complete report, including non-strict runs with skipped lines.
- `1`: operational or I/O failure.
- `2`: Click usage error.
- `3`: log-data failure, strict parse failure, or zero valid records.
- `4`: unique-cardinality exhaustion; never omit, reuse, or remap code 4.

Never emit a partial report for codes 1–4. Keep diagnostics on stderr. Do not
introduce authentication, a database, an HTTP API, a server, cloud resources,
Docker as a runtime requirement, or Kubernetes. Maintain Python 3.11, Click,
Rich, dataclasses, pip installation, one process, and stateless streaming.

## Prompt 1 — Package and CLI Contract

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. Create the pyproject metadata,
src package, version, Click command/options, and initial CLI contract tests.
Do not implement parsing, aggregation, or renderers. The command must expose
the documented inputs/options and central exit constants 0/1/2/3/4, where 4
means unique-cardinality exhaustion. Run the Step 1 verification commands and
report changed files plus actual results. If a command fails, diagnose it and
leave the step in progress; do not claim completion.
```

Expected evidence: clean editable install, help output, and focused CLI tests.

## Prompt 2 — Domain and Error Models

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md. Add frozen dataclasses and
expected exception types with the invariants in PROJECT_ARCHITECTURE.md. Keep
models independent of Click and Rich. Represent common-format User-Agent share
as None, require exactly 24 hour buckets, and preserve the full exit mapping
0/1/2/3/4 for the later CLI boundary. Add focused tests and run pytest plus
mypy exactly as specified. Do not begin parser work.
```

Expected evidence: model invariant tests and a passing focused type check.

## Prompt 3 — Sources and Parser

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md and acceptance stories US-01
and US-02. Read files/stdin lazily, support combined/common grammar, preserve
raw targets, parse offset-aware timestamps, and sanitize diagnostics. Strict
parse/data failures map to 3; usage remains 2; I/O remains 1; reserve 4 for
unique-cardinality exhaustion. Add only the fixtures/tests listed in the step.
Run the focused pytest and Ruff commands and provide their actual output.
```

Expected evidence: parser/source tests including malformed, escape, IPv6, and
privacy cases; no full-file buffering.

## Prompt 4 — Streaming Aggregation

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md and stories US-03 through
US-06. Use exact counters/sets and enforce --max-cardinality before inserting
a new IP, error URL, or User-Agent. Compute every hourly percentage with the
literal formula 100 × hourly_request_count / total_valid_requests. Compute
User-Agent share from distinct nonempty values over total valid requests.
Apply deterministic ties. Exhaustion raises the dedicated failure later mapped
to exit 4; do not approximate or emit partial metrics. Run focused tests and
mypy, including limit and status-boundary cases.
```

Expected evidence: exact expected metric fixtures, deterministic ties, all 24
hours, and a limit+1 case that takes the code-4 path.

## Prompt 5 — Three Renderers

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md and stories US-07/US-08.
Render a finalized Report through Rich terminal, schema-v1 JSON, and the
specified long-form CSV. Do not recalculate metrics in renderers. Preserve
ordering, two-decimal values, common-format null semantics, stdout/stderr
separation, and control-character safety. Keep exit codes 0/1/2/3/4 unchanged;
code 4 is unique-cardinality exhaustion. Run golden and semantic-parity tests.
```

Expected evidence: stable golden outputs for all formats and no ANSI/prose in
machine formats.

## Prompt 6 — CLI Integration and Exit Codes

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md and story US-09. Wire sources,
parser, aggregator, and selected renderer in cli.py. Demonstrate all mappings:
0 success; 1 operational/I/O failure; 2 usage error; 3 malformed/unsupported
log data, strict parse failure, or no valid records; 4 unique-cardinality
exhaustion. Exits 1–4 must leave stdout without a partial report. Handle normal
downstream pipe closure without a traceback. Run subprocess tests and the
manual strict-input commands from the plan; report actual exit statuses.
```

Expected evidence: one focused test for each code 0/1/2/3/4, correct stderr,
and empty report stdout on failures.

## Prompt 7 — Quality and Performance Evidence

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. Add integration and opt-in
performance tests, complete static/test configuration, and create the benchmark
record from an actual installed-wheel run. Corpus creation is outside timing.
Measure the slowest supported renderer on a disclosed 1 GB corpus and record
hardware, Python, wall time, and peak RSS. Also prove fail-fast exit 4 on a
high-cardinality corpus. Run Ruff, mypy, coverage, and the explicit performance
command. Do not say the 30-second gate passed without the recorded run.
```

Expected evidence: lint/type/test output, >=90% coverage, measured benchmark,
and dependency/security review notes.

## Prompt 8 — Release Artifact and Handoff

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Bring README examples in sync
with the installed command, build wheel and sdist, check metadata, install the
wheel into a fresh temporary Python 3.11 environment, and run documented smoke
tests. Re-run the P0 suite and confirm the exit contract 0/1/2/3/4, including
4 for unique-cardinality exhaustion. Update CLAUDE.md status only from actual
evidence. Do not publish externally, create infrastructure, or start P2 work.
```

Expected evidence: successful build/check, clean-wheel smoke tests, current
README, and a reconciled status table.

## Verification and Handoff Rules

At the end of each future implementation session:

1. Record exact commands and outcomes; “should pass” is not evidence.
2. Keep only one implementation step In Progress.
3. Update `CLAUDE.md` with status, evidence location, blocker, and next action.
4. Do not mark performance complete from a small fixture or estimated speed.
5. Do not change specs silently; update PRD/architecture first when behavior changes.
6. Save continuity context through `/session-save` after status reconciliation.

The intended final checks are listed in Step 8 of `IMPLEMENTATION_PLAN.md`.
