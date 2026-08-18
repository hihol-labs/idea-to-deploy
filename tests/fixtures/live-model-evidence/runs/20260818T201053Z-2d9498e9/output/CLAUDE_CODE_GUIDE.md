# Implementation Guide: nginx-insights

## How to Use This Guide

This file supplies bounded prompts for a future coding session; this blueprint does not implement them. Execute prompts in order and finish one step before beginning the next. At the start of every prompt, read `PRD.md`, the cited section of `PROJECT_ARCHITECTURE.md`, and the corresponding step in `IMPLEMENTATION_PLAN.md`. If implementation evidence contradicts a specification, update and review the specification first.

## Non-Negotiable Contract for Every Prompt

- Python 3.11, Click, Rich, and dataclasses; installable with pip.
- One local process and one streaming pass; no retained records and no product code that performs network access.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- Default Rich terminal output plus clean `--json` and `--csv` pipeline output.
- Hourly percentages use exactly `100 × hourly_request_count / total_valid_requests`.
- The complete exit-code contract is: `0` success/help/version; `1` unexpected internal/runtime failure; `2` Click usage error; `3` input/parse failure, including unreadable input or zero valid records; `4` unique-cardinality exhaustion. Code `4` means exact unique User-Agent cardinality exceeded its configured limit and must never be omitted, swallowed, or remapped.
- Work in one implementation-plan step at a time. Run every named verification command and record actual output; never claim a test that was not run.

## Prompt 1: Package and CLI Skeleton

```text
Implement only STEP 1 of IMPLEMENTATION_PLAN.md. Read PRD.md and PROJECT_ARCHITECTURE.md, especially ## CLI Interface. Create the PEP 621 Python 3.11 package, console entry point, Click option surface, and help/version tests. Do not implement parsing, analysis, or rendering yet. Preserve the full exit contract 0/1/2/3/4 defined in this guide, even though this step directly exercises only success and usage behavior. Run every STEP 1 verification command and report files changed plus actual results. Stop after STEP 1.
```

## Prompt 2: Models and Failure Semantics

```text
Implement only STEP 2 of IMPLEMENTATION_PLAN.md. Define immutable dataclasses matching the complete report schema and typed expected failures. Wire and test the complete contract: 0 success/help/version, 1 unexpected runtime failure, 2 usage error, 3 input/parse failure, and 4 unique-cardinality exhaustion. Ensure code 4 is a distinct capacity outcome and is never remapped. Do not add parser or metric logic. Run all STEP 2 checks and stop.
```

## Prompt 3: nginx Parser

```text
Implement only STEP 3 of IMPLEMENTATION_PLAN.md and FR-01/FR-02 in PRD.md. Parse standard nginx common and combined formats one physical line at a time into AccessRecord. Use precompiled, non-pathological matching; treat logs as untrusted data. Return a structured invalid-line result rather than terminating on one malformed line. Do not support arbitrary log_format syntax. Preserve exit codes 0/1/2/3/4; orchestration will later use 3 for unreadable/no-valid input and 4 only for unique-cardinality exhaustion. Run the parser checks and stop.
```

## Prompt 4: Streaming Metrics

```text
Implement only STEP 4 and FR-03 through FR-07. In one pass, maintain exact IP and error-URL counters, 24 hourly counts, valid/skipped totals, and an exact non-null User-Agent set up to the configured cap. Do not retain AccessRecord objects. Use deterministic count-descending/key-ascending top-10 ordering. Compute every hourly percentage with the literal formula 100 × hourly_request_count / total_valid_requests and unique share over total valid requests. Exceeding the User-Agent cap must produce exit-semantic code 4, never approximation or code 1/3. Preserve the complete 0/1/2/3/4 contract. Run STEP 4 verification and stop.
```

## Prompt 5: Three Renderers

```text
Implement only STEP 5 and FR-08 through FR-10. All renderers must consume the same finalized AnalysisReport. Add Rich terminal tables, schema-versioned JSON, and normalized CSV with section,rank,key,count,percentage. JSON/CSV stdout must contain neither ANSI sequences nor diagnostics. Escape untrusted text. Do not recalculate metrics in a renderer. Preserve the complete exit mapping 0 success, 1 internal failure, 2 usage, 3 input/parse, 4 unique-cardinality exhaustion. Run structural renderer tests and stop.
```

## Prompt 6: End-to-End CLI

```text
Implement only STEP 6. Connect explicit paths and stdin to parser, analyzer, and renderer without loading input wholesale. Send reports to stdout and diagnostics to stderr. Test files, stdin, malformed-only input, mixed input, mutual output flags, broken pipes, and cardinality limits. Prove all codes: 0 success/help/version; 1 unexpected internal/runtime failure; 2 invalid CLI usage; 3 unreadable input, stream failure, or zero valid records; 4 exact unique User-Agent cardinality exhaustion. Code 4 must remain distinguishable in subprocess tests. Run STEP 6 checks and stop.
```

## Prompt 7: Performance and Quality Evidence

```text
Implement only STEP 7. Create a deterministic 1 GB fixture generator and a separately marked benchmark that checks correctness, wall time, and peak memory on a documented laptop. Profile the actual hot path before changing it. Keep the pre-approved single-process architecture unless the spec is revised with evidence. Run three timed analyses and require each to be under 30 seconds. Run the full test, coverage, formatting, lint, and type commands. Re-run the 0/1/2/3/4 exit suite, including 4 for unique-cardinality exhaustion. Record results without committing the generated log, then stop.
```

## Prompt 8: Package Release Candidate

```text
Implement only STEP 8. Add user-facing quick start and format/metric/exit documentation, license, changelog, and Python 3.11 CI. Build wheel and sdist, inspect them, install the exact wheel in a clean environment, and smoke-test terminal, JSON, and CSV. Document the full contract verbatim: 0 success/help/version, 1 unexpected internal/runtime failure, 2 usage error, 3 input/parse failure, 4 unique-cardinality exhaustion. Do not introduce auth, a database, an HTTP API, a server, cloud, or Kubernetes. Run all STEP 8 checks plus the final acceptance checklist and stop.
```

## Review Prompt

```text
Review the exact candidate against PRD.md, PROJECT_ARCHITECTURE.md, and IMPLEMENTATION_PLAN.md without modifying it. Check calculations, deterministic ordering, stream behavior, hostile input handling, stdout/stderr separation, schema consistency, pip installation, and the 1 GB benchmark evidence. Explicitly verify all exit outcomes 0/1/2/3/4 and that 4 exclusively means unique-cardinality exhaustion. Report findings by severity with file and line evidence; do not infer test success from code inspection.
```

## Handoff Template

At the end of a future implementation block, record:

1. Active implementation-plan step and requirements addressed.
2. Exact files changed.
3. Commands run and their actual outcomes.
4. Any unverified acceptance criterion or benchmark condition.
5. Current behavior for exit codes `0/1/2/3/4`, explicitly including code `4`.
6. The single next action; do not start it in the same WIP block.

