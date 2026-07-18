# Claude Code Guide: nginx-log-report

## Purpose

Use these prompts only after an implementation workflow is authorized. They translate the nine units in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) into bounded coding sessions. Product behavior comes from [PRD.md](PRD.md); architecture and schemas come from [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). When documents disagree, pause and reconcile the durable specification before coding.

## Session protocol

For every step:

1. Read `CLAUDE.md`, the named implementation-plan step, and its referenced architecture/PRD sections.
2. Keep WIP at one step; do not begin later features.
3. Preserve stdout/stderr, exactness, resource, and no-service boundaries.
4. Run every verification command for the step and include actual output in the handoff.
5. Mark anything not run as `NOT VERIFIED` with a reason; do not infer success.
6. Update the status table in `CLAUDE.md` only from evidence.

## Prompt 1 — Package skeleton and CLI surface

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. Create the Python 3.11 src-layout package, Click console entry point, all approved options including the distinct-value guard option, and CLI contract tests. Do not implement parsing, aggregation, or rendering. Keep --json/--csv mutually exclusive. Run the three Step 1 verification commands, report their output, reconcile CLAUDE.md status, and save the session context.
```

## Prompt 2 — Canonical records and errors

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md. Add frozen/slotted dataclasses and explicit error/exit contracts exactly matching PROJECT_ARCHITECTURE.md Sections 6 and 8. Keep all I/O out of models. Test every invariant, including a nullable URL only for a dash request. Run the Step 2 checks, attach evidence, update status, and save session context.
```

## Prompt 3 — Byte-level nginx parser

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md. Build the byte-state-machine parser for the exact common/combined grammar in Architecture Section 7. Support only the named nginx escapes, limits, request forms, decoding semantics, and reason-only diagnostics. Reject custom trailing fields. Add all specified fixtures and collision/oversize tests. Run coverage and unit checks, attach evidence, update status, and save session context.
```

## Prompt 4 — Streaming aggregations

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md. Add exact counters, 24 source-hour buckets, User-Agent numerator/denominator, deterministic top-10 selection, and the pre-insertion summed distinct-value guard. Never approximate or retain source records. Cover status boundaries, ties, dash requests, zero denominator, and low-limit resource failure. Run Step 4 verification, attach evidence, update status, and save session context.
```

## Prompt 5 — JSON and CSV contracts

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md. Render the canonical Report to JSON schema v1 and the exact ordered seven-column CSV mapping in Architecture Section 9. Add golden files and hostile Unicode/quoting cases. No ANSI bytes or diagnostic prose may enter structured output. Run both verification commands, attach evidence, update status, and save session context.
```

## Prompt 6 — Safe Rich terminal output

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md. Create the Rich report and shared display sanitizer. Neutralize C0/C1, ANSI/OSC, line breaks, bidi formatting, and non-printing format characters; disable markup for derived values and truncate display cells without altering metrics. Cover TTY, redirected, and --no-color behavior. Run Step 6 checks, attach evidence, update status, and save session context.
```

## Prompt 7 — End-to-end CLI

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. Connect buffered binary input, parser, aggregator, renderer, bounded reason diagnostics, and every exit path. Discard state on late reads, pre-serialize the bounded report, handle output failures, and make BrokenPipeError quiet. Prove stdout/stderr isolation with Click integration tests and failing stream doubles. Run every Step 7 command, attach evidence, update status, and save session context.
```

## Prompt 8 — Real performance gate

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Create the deterministic exact-size 1 GiB generator and BENCHMARK.md protocol. Run one warm-up and five measured end-to-end JSON executions on the documented reference laptop, record every time and peak RSS, and add parser/high-cardinality component benchmarks. Optimize only measured hotspots without changing specifications. Do not pass this step unless median <30.0 s, every run <33.0 s, and RSS <512 MiB; otherwise mark recovery required. Attach evidence, update status, and save session context.
```

## Prompt 9 — Release candidate

```text
Implement only Step 9 of IMPLEMENTATION_PLAN.md after Steps 1–8 are evidence-green. Reconcile all docs, finalize metadata/changelog, run the full coverage gate, build wheel and sdist, install the wheel in a clean Python 3.11 environment, and smoke-test all output modes. Test the artifact rather than an editable install. Attach full command evidence, update CLAUDE.md status, and save session context. Do not publish or push without separate authorization.
```

## Review prompts

After Steps 3, 7, and 9, request a focused review using this boundary:

```text
Review the current completed step against PRD acceptance criteria and PROJECT_ARCHITECTURE.md. Prioritize parser correctness, untrusted-output safety, deterministic schemas, resource-limit behavior, stdout/stderr isolation, and verification gaps. Cite files and lines. Do not modify code during a review-only request.
```

## Recovery rule

If a check fails, keep the same step active. Record the failure, cause, and next smallest diagnostic action. Do not lower thresholds, delete tests, shrink the official 1 GiB fixture, or relabel unverified output as passing.
