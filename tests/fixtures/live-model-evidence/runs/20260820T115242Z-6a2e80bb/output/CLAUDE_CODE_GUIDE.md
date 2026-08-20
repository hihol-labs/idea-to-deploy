# Claude Code Implementation Guide: nginx-insight

Use this guide after the blueprint is accepted. It contains prompts for a future implementation session; it does not itself authorize skipping tests, changing the specifications, or implementing out of order. Preserve WIP=1: complete and verify one step before starting the next.

## Source-of-Truth Order

1. `PRD.md` defines observable behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines boundaries, schemas, and the CLI interface.
3. `IMPLEMENTATION_PLAN.md` defines dependency order and verification commands.
4. `STRATEGIC_PLAN.md` defines scope, risk, and Definition of Done.

When a behavior changes, update the specification first. Do not silently reinterpret “hourly distribution,” unique User-Agent share, structured schemas, or an exit status.

## Global Implementation Constraints

- Python 3.11, Click, Rich, and dataclasses; install through pip with a `src/` layout.
- Single local process, one pass over raw lines, and no retention of raw records.
- No authentication, database, HTTP API, server, network call, cloud resource, Docker requirement, or Kubernetes artifact.
- Default terminal output; exactly one of terminal, `--json`, or `--csv` per run.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Complete exit-code contract: `0` success; `1` processing/data failure; `2` CLI usage failure; `3` input I/O or UTF-8 decoding failure; `4` unique-cardinality exhaustion. Code `4` specifically means the exact User-Agent cardinality would exceed the configured maximum and must never be omitted or remapped.
- No partial JSON or CSV on any nonzero exit. stdout is report data; stderr is diagnostics.
- Do not claim the 1 GB / 30 s target without a reproducible run on documented hardware.

## Prompt 1: Package and CLI Contract

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Read PRD.md and the entire
PROJECT_ARCHITECTURE.md CLI Interface first. Create pyproject.toml, the
src/nginx_insight package entry points, and the initial Click command plus tests.
Keep business logic out of cli.py. Support help, version, and parse-time validation
for mutually exclusive --json/--csv and a positive --max-unique-user-agents.
Preserve exit codes 0/1/2/3/4 as the project-wide contract even though this step
directly exercises only 0 and 2. Run every STEP 1 verification command, report the
actual results, and stop before STEP 2.
```

Expected evidence: editable install succeeds; help/version exit 0; invalid format combinations and non-positive cardinality limits exit 2.

## Prompt 2: Models and Domain Errors

```text
Implement STEP 2 only. Create all dataclasses and typed domain exceptions exactly
as specified in PROJECT_ARCHITECTURE.md. Keep models independent of Click and Rich.
At the CLI boundary, map success to 0, processing/data failure to 1, usage failure
to 2, input I/O or decoding failure to 3, and unique-cardinality exhaustion to 4.
Code 4 must remain a distinct domain condition. Add focused invariant and status
tests, run the STEP 2 commands, report actual evidence, and stop.
```

Expected evidence: model invariants have positive and negative cases; tests name and exercise every status `0/1/2/3/4` even if later steps provide their final end-to-end triggers.

## Prompt 3: Input and Parser

```text
Implement STEP 3 only. Build a line iterator for ordered files or stdin and a strict
UTF-8 nginx combined-log parser. Do not buffer complete files. Parse timestamp offset,
request components, status, optional byte count, and User-Agent into AccessRecord.
Default malformed-line policy is classification for later skipping; --strict will
turn it into exit 1 at orchestration. Missing/unreadable/directory/invalid-UTF-8 input
maps to exit 3. Never echo a complete sensitive bad line. Add the named fixtures and
tests, execute STEP 3 verification, and stop.
```

Expected evidence: parser covers spaces/escaping permitted by the supported grammar, query strings, `-` byte counts, malformed syntax, stdin, multiple sources, and invalid UTF-8.

## Prompt 4: Streaming Aggregation

```text
Implement STEP 4 only. Create one ReportAccumulator that updates all four metrics in
one call per valid record and never retains AccessRecord instances. Rank exact IP and
4xx/5xx URL counts by count descending then value ascending, limited to 10. Emit all
24 hours and calculate each with the literal formula
100 × hourly_request_count / total_valid_requests, using 0.0 for zero valid input.
Calculate unique User-Agent share as 100 × unique_user_agent_count /
total_valid_requests. Enforce exact UA cardinality before insertion; exhaustion is
exit 4, not approximation or exit 1. Run STEP 4 tests and stop.
```

Expected evidence: deterministic ties, mixed statuses, 24 buckets, percentage reconciliation, empty input, and a tiny configured limit that produces the code-4 exception.

## Prompt 5: Renderers

```text
Implement STEP 5 only. Render the same immutable Report through separate terminal,
JSON, and CSV modules. Rich output has four readable sections and treats log values as
plain text, never markup. JSON follows the exact key schema and CSV follows the exact
normalized columns in PROJECT_ARCHITECTURE.md. Structured output contains no ANSI,
warnings, or progress text. Do not recalculate a metric in a renderer. Add structural
and cross-format reconciliation tests, run STEP 5 verification, and stop.
```

Expected evidence: valid JSON, standards-based CSV quoting, deterministic order, safe terminal values, and equal counts/percentages across formats.

## Prompt 6: CLI Integration

```text
Implement STEP 6 only. Wire input, parser, accumulator, and renderer in cli.py while
preserving their boundaries. No file means stdin; multiple files form one report.
Default mode skips and counts malformed records; --strict fails at the first with 1.
Normalize Click usage errors to 2, I/O/decode/interrupt errors to 3, and exact
User-Agent cardinality exhaustion to 4; success is 0. Buffer only the final serialized
structured report as needed so a nonzero run cannot emit partial JSON/CSV. Keep all
diagnostics on stderr. Run the full exit and CLI tests, show actual results, and stop.
```

Expected evidence: end-to-end cases for `0/1/2/3/4`, stdin, multiple files, empty data, strict/non-strict data, clean stdout, and failure atomicity.

## Prompt 7: Quality and Performance

```text
Implement STEP 7 only. Add safety fixtures, reproducible benchmark generation and
execution, lint/type/coverage configuration, and benchmark documentation. Generate
large data locally; do not commit a 1 GB file. Record Python/OS/CPU/RAM/storage, cache
condition, command, valid/malformed counts, wall time, and peak RSS. Benchmark parsing
and aggregation without terminal rendering. Profile before optimizing and retain the
single-process design. Run every STEP 7 command. State whether the <30 s target passed
from observed evidence; do not infer it. Preserve all exits 0/1/2/3/4.
```

Expected evidence: formatter/linter/type checks, coverage at least 90% for core modules, security fixtures, and a reproducible benchmark result.

## Prompt 8: Release Readiness

```text
Implement STEP 8 only after Steps 1-7 are verified. Reconcile README examples with the
installed behavior, add an open-source license, build sdist/wheel, check metadata, and
install the wheel in a clean Python 3.11 environment. Run the complete suite and smoke
test help plus all three output modes. Reconfirm exit codes: 0 success, 1 processing,
2 usage, 3 input I/O/decode, 4 unique-cardinality exhaustion. Update CLAUDE.md's status
table with evidence. Do not publish a package or create remote resources unless the
user separately authorizes that external action.
```

Expected evidence: clean build, metadata check, clean-environment install, passing suite, and installed-command smoke tests.

## Final Acceptance Prompt

```text
Review the exact implementation candidate against every P0 criterion in PRD.md and the
Definition of Done in STRATEGIC_PLAN.md. Run, do not merely describe, the formatter,
linter, type checker, tests, coverage, build, clean-wheel smoke tests, and documented
benchmark. Reconcile structured metrics across JSON and CSV. Verify exit statuses
0/1/2/3/4, with code 4 meaning unique-cardinality exhaustion. Report failures as
failures and leave an explicit next action; do not weaken a check to obtain a pass.
```

