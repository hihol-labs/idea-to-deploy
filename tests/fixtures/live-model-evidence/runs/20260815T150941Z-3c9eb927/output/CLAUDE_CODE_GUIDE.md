# Claude Code Implementation Guide: nginx-insight

## How to Use This Guide

Run one prompt at a time in order. Preserve work-in-progress at one active step, update the status table in `CLAUDE.md`, and attach the verification output named by the step before advancing. Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md` before the first implementation change.

Every prompt inherits this non-negotiable exit-code contract:

- `0`: success, including an intentional downstream pipe close.
- `1`: operational, I/O, output, or unexpected internal failure.
- `2`: Click usage or option-validation error.
- `3`: no valid requests, or malformed input with `--fail-on-invalid`.
- `4`: unique-cardinality exhaustion after the configured distinct User-Agent ceiling is crossed.

Never omit or remap code 4. Codes 1–4 must not emit a partial report. Keep structured report data on stdout and diagnostics on stderr.

## Prompt 1: Package Skeleton and Models

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Read PROJECT_ARCHITECTURE.md sections CLI Interface, Package and Component Design, and Core Dataclasses, plus every P0 contract in PRD.md. Create the Python 3.11 src-layout package, Click console entry point, frozen/slot dataclasses, and focused tests. Do not implement parsing or metrics yet. Preserve exit codes 0/1/2/3/4 exactly, with 4 reserved for unique-cardinality exhaustion. Run all Step 1 verification commands, record the results, and stop after updating CLAUDE.md status.
```

## Prompt 2: Input and Parser

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Add sequential file/stdin iteration and parsing for nginx common and combined formats. Process incrementally; never read a full log into memory. Treat untrusted fields as data and distinguish blank, valid, and malformed lines. Add synthetic fixtures and the named input/parser tests. Preserve the complete 0/1/2/3/4 exit contract and do not emit partial reports. Run Step 2 checks and stop with evidence and CLAUDE.md status updated.
```

## Prompt 3: IP, Error URL, and Hourly Metrics

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Build exact IP and 400–599 raw request-target counters, deterministic top-10 sorting, and a fixed 24-hour distribution. Use the literal percentage formula 100 × hourly_request_count / total_valid_requests; do not store or display an unscaled fraction. Add all named aggregation tests, including ties and zero buckets. Preserve exit codes 0/1/2/3/4 with code 4 unchanged. Run Step 3 verification and stop after recording evidence.
```

## Prompt 4: User-Agent Cardinality

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Add exact distinct nonempty User-Agent tracking, share percentage, a configurable positive ceiling, and a dedicated exhaustion exception. Crossing the ceiling must map to exit code 4 and must discard the partial report; never approximate. Cover repeated, missing, boundary, and over-limit cases. Preserve codes 0 success, 1 operational, 2 usage, 3 input-data, and 4 unique-cardinality exhaustion. Run Step 4 checks and update status before stopping.
```

## Prompt 5: Rich Terminal Output

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Render the shared report model as four safe Rich sections with deterministic rows, two-decimal percentages, TTY-aware color, and --no-color behavior. Escape log-derived content so Rich cannot interpret it as markup. Do not implement separate metric logic in the renderer. Preserve the 0/1/2/3/4 exit contract and reserve code 4 for cardinality exhaustion. Run the golden and coverage checks named in Step 5, record results, and stop.
```

## Prompt 6: JSON and CSV

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Add the schema-version-1 JSON object and normalized RFC 4180 CSV output from the same report model used by terminal output. Ensure stdout contains no ANSI escapes or diagnostics and serializers safely quote untrusted values. Add shared golden fixtures and semantic equivalence tests. Preserve codes 0/1/2/3/4 exactly, especially 4 for unique-cardinality exhaustion. Run Step 6 verification and stop with recorded evidence.
```

## Prompt 7: CLI Integration and Failure Matrix

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Integrate files/stdin, parser, aggregator, and renderer in the Click analyze command. Enforce mutually exclusive --json/--csv, positive --max-unique-user-agents, --fail-on-invalid, --no-color, and stdin/path rules. Test subprocess outcomes for every code: 0 success or intentional broken pipe; 1 operational/output/internal failure; 2 usage error; 3 input-data failure; 4 unique-cardinality exhaustion. No code 1–4 path may emit a partial report. Run every Step 7 check and stop after updating status.
```

## Prompt 8: Performance and Release Readiness

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Add deterministic synthetic performance-fixture generation, an opt-in 1 GB test, full coverage/build checks, clean wheel installation verification, and final README release instructions. Record machine, Python, storage, fixture mix, exact command, wall time, and peak RSS. Acceptance requires under 30 seconds and at most 512 MiB on the reference laptop. Re-run the entire exit matrix 0/1/2/3/4 and ensure 4 still means only unique-cardinality exhaustion. Freeze and verify the exact candidate using the project verification contract; do not accept narration alone. Stop after reconciling CLAUDE.md status and evidence.
```

## Completion Checklist

- [ ] All eight steps have current command evidence.
- [ ] Every P0 criterion in `PRD.md` passes.
- [ ] Terminal, JSON, and CSV contain the same metric values.
- [ ] Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- [ ] The complete `0/1/2/3/4` exit matrix passes and code 4 remains unique-cardinality exhaustion.
- [ ] The clean wheel install and documented 1 GB benchmark pass.
- [ ] The exact candidate has a current verification receipt required by `.itd/VERIFICATION_CONTRACT.json`.

