# Claude Code Guide: nginx-streamtop

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts.
Run one prompt at a time (WIP=1). Before each step, read `CLAUDE.md`, the active
Idea to Deploy state/contracts, `PRD.md`, and the referenced architecture
sections. Do not accept narration as completion: freeze the exact candidate,
run the current machine oracle, and retain a valid adjudication receipt.

Do not start implementation merely because this guide exists; the blueprint
request itself is planning-only.

## Prompt 1 — Package and CLI contract

```text
Execute STEP 1 from IMPLEMENTATION_PLAN.md only. Establish the Python 3.11
package, Click command surface, build metadata, initial CLI tests, and CI check
commands. Do not implement parsing or metrics. Preserve every option and exit
contract under PROJECT_ARCHITECTURE.md `## CLI Interface`, including mutual
exclusion and help/version behavior. Run the step's checks and reconcile the
active Idea to Deploy evidence before reporting completion.
```

## Prompt 2 — Typed domain models and fixtures

```text
Execute STEP 2 only. Add the dataclasses and representative combined/malformed
fixtures specified by the architecture. Make ties, time offsets, request `-`,
query strings, escapes, IPv4/IPv6, and zero-input cases explicit. Do not add a
parser or renderer. Run model, lint, and type checks and attach exact-candidate
verification evidence.
```

## Prompt 3 — Streaming inputs

```text
Execute STEP 3 only. Implement bounded line-by-line file/stdin ownership using
the selected encoding for both sources, including invalid codec, decode/read
failures, 1 MiB logical-line boundary plumbing, and exit-code separation. Do
not parse nginx fields yet. Prove that raw input is not materialized and run
the listed checks.
```

## Prompt 4 — Combined-log parser

```text
Execute STEP 4 only. Implement the deterministic scanner for exactly the
grammar frozen in PROJECT_ARCHITECTURE.md section 7. Cover nginx quoting,
request `-`, IPv4/IPv6, timezone-aware timestamps, status/bytes invariants,
trailing-field rejection, safe error messages, tolerant mode, and --strict.
Do not broaden support to custom log_format. Run parser/CLI tests and record
verification evidence.
```

## Prompt 5 — Single-pass aggregation and early gate

```text
Execute STEP 5 only, including the architecture's early 100 MB performance
spike before renderer development. Produce all four exact metrics in one pass,
deterministic top-10 ties, source-offset hourly bucket ordering, processing
counts, and the --max-distinct guard with exit 5/no partial report. If the
spike lacks 20% extrapolated margin for 1 GB/30 s, profile and implement the
specified allocation-conscious path without changing Report semantics. Record
measurements; do not claim the 1 GB target from extrapolation alone.
```

## Prompt 6 — Rich terminal renderer

```text
Execute STEP 6 only. Render the four report sections and processing statistics
with Rich. Disable markup for log data, visibly escape C0/C1/ESC controls, obey
TTY and --no-color behavior, and keep domain values unchanged. Add focused
malicious-value and captured-console tests. Do not implement JSON or CSV.
```

## Prompt 7 — JSON renderer

```text
Execute STEP 7 only. Map Report explicitly to the public JSON fields under the
CLI contract, with deterministic ordering, numeric types, ISO hour labels, a
trailing newline, no ANSI, and strict stdout/stderr separation. Add schema and
golden tests. Do not reuse terminal-rendered text.
```

## Prompt 8 — CSV renderer

```text
Execute STEP 8 only. Emit the fixed section,key,count,value header and exactly
the row mapping enumerated under PROJECT_ARCHITECTURE.md `## CLI Interface`.
Use the standard csv module, preserve raw machine values, document spreadsheet
formula risk, and test quoting/special characters and zero input. Do not
silently sanitize cells.
```

## Prompt 9 — Performance and resource evidence

```text
Execute STEP 9 only. Generate deterministic out-of-tree benchmark logs, bind
their hashes/cardinality profiles, measure the declared 1 GB command using
documented hardware and peak RSS, and test high-cardinality safety. Profile
before optimizing; preserve parser and report semantics. If the target fails,
record RECOVERY_REQUIRED and the measured bottleneck rather than weakening the
acceptance threshold.
```

## Prompt 10 — Release verification

```text
Execute STEP 10 only. Complete user documentation, golden cases, changelog,
lint/type/test/coverage checks, build metadata inspection, and a clean-wheel
install smoke test for file/stdin and all formats. Do not upload or publish the
package without separate authorization. Reconcile CLAUDE.md and the current
Idea to Deploy state; accept completion only with a current adjudication
receipt.
```

## Review Prompt

```text
Review the current exact candidate against PRD.md, PROJECT_ARCHITECTURE.md, and
the active step in IMPLEMENTATION_PLAN.md. Prioritize correctness of parser
grammar, output/exit compatibility, bounded input handling, injection safety,
and performance evidence. Report findings by severity with file/line evidence.
Do not modify code during a review-only request.
```

## Session Handoff Prompt

```text
Reconcile the active WIP=1 unit, record commands and results, list changed
files, identify unresolved risks, and state exactly one next action. Save the
session context through /session-save. Do not mark a step complete without the
verification evidence required by the current repository contracts.
```

