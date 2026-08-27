# Claude Code Implementation Guide: nginx Stream Analytics CLI

## Purpose

Use this guide only after the blueprint is accepted and implementation is
authorized. It turns each step of `IMPLEMENTATION_PLAN.md` into a bounded,
replayable work prompt. Run one prompt at a time, preserve WIP=1, and stop if
the specification documents disagree.

The durable sources of truth are, in order:

1. `PRD.md` for product behavior and acceptance criteria;
2. `PROJECT_ARCHITECTURE.md` for boundaries, schemas, and CLI contracts;
3. `IMPLEMENTATION_PLAN.md` for dependency order and verification;
4. `STRATEGIC_PLAN.md` for scope, priority, budget, and release goals.

## Non-negotiable Contract

- Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- Local single-process streaming; never accumulate raw input or all parsed
  records.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Default Rich text plus mutually exclusive `--json` and `--csv`.
- Hourly percentage uses exactly
  `100 × hourly_request_count / total_valid_requests`.
- Exit codes are complete and stable: `0` success; `1` unexpected/runtime
  processing failure; `2` CLI usage error; `3` input, decoding, or strict
  malformed-line failure; `4` unique-cardinality exhaustion.
- Code 4 must remain unique-cardinality exhaustion and must never be omitted,
  remapped, approximated, or converted to a successful partial report.
- Do not claim the 1 GB / 30 second target until the documented benchmark has
  actually run on a named reference machine.

## Session Protocol

Before each step, read its PRD acceptance criteria and architecture sections,
inspect current repository state, and write a short bounded plan. Implement
only that step. Add or update the specified tests, run the exact verification
commands, and record the observed result. Do not weaken tests or change the
specification merely to obtain green output. If the behavior needs to change,
pause and request a spec update first.

At the end of a step, report changed files, verification commands and results,
remaining risks, and the next step. Do not mark a step complete from narration
alone.

## Prompt 1 — Installable CLI Skeleton

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Read PRD.md and the CLI
Interface and Component Boundaries sections of PROJECT_ARCHITECTURE.md first.
Create the Python 3.11 src-layout package, pyproject metadata, Click entry
point, version/help behavior, and the initial CLI contract tests. Do not
implement parsing or metrics. Keep runtime dependencies limited to Click and
Rich. Run every Step 1 verification command and report observed output and
changed files. Stop after Step 1 is verified.
```

## Prompt 2 — Models, Errors, and Fixtures

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Preserve the public
0/1/2/3/4 exit mapping even though the CLI will connect it later. Add frozen
dataclasses for records and the canonical report, typed domain failures, and
small hand-auditable common/combined/malformed fixtures. Keep models free of
rendering and Click concerns. Run the Step 2 verification commands and report
actual results. Stop after Step 2 is verified.
```

## Prompt 3 — Streaming Input and Parser

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Read PRD parsing rules and
architecture input contracts. Make file and stdin reading lazy, never close
stdin, and attach safe line-number context to failures. Parse only the declared
common and combined nginx formats, including IPv4/IPv6, timestamp hour,
request target, status, and optional User-Agent. Add all listed boundary and
malformed tests. Run the Step 3 verification commands and report evidence.
Stop after Step 3 is verified.
```

## Prompt 4 — Rankings and Hourly Distribution

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Build one-pass aggregation
for top client IPs, top request targets with statuses 400 through 599, and all
24 hour buckets. Deterministic ties sort lexically after descending count.
Calculate hourly percentages using exactly
100 × hourly_request_count / total_valid_requests, with explicit zero-total
behavior. Do not render output yet. Run every listed Step 4 test and report
actual results. Stop after Step 4 is verified.
```

## Prompt 5 — User-Agent Cardinality

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Count exact distinct
normalized non-missing User-Agent values and calculate their share against all
valid requests. Enforce the configurable cap only when a new distinct value
would exceed it; duplicates at the cap remain valid. Raise the typed failure
that will map to exit code 4, never approximate. Add the complete boundary test
matrix, run the Step 5 verification commands, and report evidence. Stop after
Step 5 is verified.
```

## Prompt 6 — Three Renderers

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Consume the immutable Report
dataclass; never recalculate metrics in a renderer. Add Rich terminal tables,
the exact JSON schema, and long-form CSV columns from PROJECT_ARCHITECTURE.md.
Make machine output UTF-8, deterministic, newline-terminated, and free of ANSI
escapes. Safely encode untrusted log fields. Add golden tests, run every Step 6
verification command, and report observed results. Stop after Step 6 is
verified.
```

## Prompt 7 — CLI Integration and Exit Codes

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Connect Click options,
streaming input, parser, aggregator, and renderer dispatch. Keep diagnostics on
stderr and do not write a plausible partial report before successful
finalization. Integration-test the full mapping: 0 success, 1 unexpected or
runtime processing failure, 2 usage error, 3 input/decoding/strict malformed
line, and 4 unique-cardinality exhaustion. Test file/stdin parity and every
output mode. Run all Step 7 commands and report actual exit statuses. Stop
after Step 7 is verified.
```

## Prompt 8 — Correctness, Safety, and Benchmark

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Add end-to-end hand-checked
fixtures, renderer safety cases, a deterministic streaming 1 GiB fixture
generator, and a benchmark runner that validates output and records elapsed
time plus peak RSS. Run the full test suite and the benchmark. If the benchmark
misses 30 seconds, profile before changing code and report before/after
evidence; do not invent a passing result. Keep the generated 1 GiB file out of
the repository. Stop after Step 8 evidence is recorded.
```

## Prompt 9 — Package and Release Documentation

```text
Implement Step 9 from IMPLEMENTATION_PLAN.md only. Write operator-facing
README and changelog content from the accepted PRD and architecture, finalize
package inclusion, build wheel and sdist, inspect artifacts, install the wheel
in a clean Python 3.11 environment, and run the smoke test. Record the real
benchmark environment/result without committing the large fixture. Run every
Step 9 and final acceptance command. Report changed files and observed
results; do not claim release readiness if any P0 or performance gate is open.
```

## Verification Matrix

| Concern | Required evidence |
|---|---|
| Parsing | Unit cases for every declared syntax and malformed boundary |
| Rankings | Hand-calculated counts, top-10 truncation, lexical ties |
| Hourly percentage | Counts and `100 × hourly_request_count / total_valid_requests` checks |
| User-Agent share | Missing, duplicate, exact cap, over-cap, and zero-total cases |
| Output parity | Canonical report checked through text, JSON, and CSV |
| Exit contract | Integration evidence for each of `0/1/2/3/4` |
| Streaming | Lazy-reader test and recorded peak RSS |
| Performance | Real 1 GB generated fixture below 30 seconds on documented laptop |
| Packaging | Clean Python 3.11 wheel install and CLI smoke test |

## Completion Handoff

A handoff must name the active implementation step, list changed files, quote
commands actually run with pass/fail outcomes, identify unverified claims, and
state the next action. It must not claim an independent or adversarial review
unless the external review artifact actually exists and is current.

