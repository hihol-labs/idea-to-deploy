# Claude Code Implementation Guide

## How to Use This Guide

Run one prompt at a time in the order below. Before each step, read `PRD.md`, the named `PROJECT_ARCHITECTURE.md` sections, `.itd/SCOPE_LOCK.md`, and the matching section of `IMPLEMENTATION_PLAN.md`. Keep WIP at one step, update the scope/state contracts when required by Idea to Deploy, and attach executable evidence before marking a step complete.

This guide never authorizes scope beyond the current step. It does not authorize publishing, deployment, or destructive changes. Product behavior is spec-first: update `PRD.md` before changing an approved contract.

## Non-Negotiable Contract for Every Prompt

- Python 3.11; Click; Rich; dataclasses; pip installation.
- Single-process, one-pass local streaming; no authentication, database, HTTP API, server, cloud, Docker runtime, or Kubernetes.
- All formats derive from one immutable summary and use deterministic tie ordering.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- The complete exit contract is `0` success, `1` input/runtime I/O failure, `2` CLI usage error, `3` strict parse failure, and `4` unique-cardinality exhaustion. Code 4 must not be omitted or remapped. Codes 1–4 emit no partial report.
- Never claim the 1 GiB/30-second target without a current measured run on documented hardware.
- Do not create `DEVILS_ADVOCATE_REVIEW.md`; that separate review is outside implementation prompts.

## Prompt 1: Package and CLI Skeleton

```text
Execute only Step 1 of IMPLEMENTATION_PLAN.md. Create the Python 3.11 src-layout package, pyproject metadata, Click entry point, option validation, and initial CLI tests. Preserve the complete 0/1/2/3/4 exit-code contract even where later domain failures are not implemented yet; Click usage errors are code 2. Do not implement parsing, aggregation, or rendering early. Run the Step 1 verification commands, report evidence, reconcile Idea to Deploy state, and stop.
```

## Prompt 2: Domain Models and Errors

```text
Execute only Step 2 of IMPLEMENTATION_PLAN.md. Implement the frozen dataclasses and typed expected-error taxonomy exactly as PROJECT_ARCHITECTURE.md specifies. Wire only the failure mapping needed for 0 success, 1 input/runtime I/O failure, 2 CLI usage error, 3 strict parse failure, and 4 unique-cardinality exhaustion. Add model and mapping tests, run the Step 2 checks, record evidence, reconcile state, and stop.
```

## Prompt 3: Combined-Log Parser

```text
Execute only Step 3 of IMPLEMENTATION_PLAN.md. Implement a bounded conventional nginx combined-log parser and the synthetic fixture corpus. Treat every input field as untrusted data; avoid catastrophic regex behavior and remote/log-derived side effects. Cover every listed valid and malformed case. Preserve the complete exit contract 0/1/2/3/4, but do not add aggregation or renderers. Run the parser checks, record evidence, reconcile state, and stop.
```

## Prompt 4: Streaming Aggregations

```text
Execute only Step 4 of IMPLEMENTATION_PLAN.md. Implement the single-pass accumulator, four exact metrics, deterministic top-10 ordering, zero-input behavior, and the exact User-Agent cardinality cap. Use the literal hourly formula 100 × hourly_request_count / total_valid_requests. Crossing the unique limit must raise the domain failure mapped to code 4; do not approximate silently. Preserve codes 0/1/2/3/4, run all Step 4 checks, record evidence, reconcile state, and stop.
```

## Prompt 5: JSON and CSV

```text
Execute only Step 5 of IMPLEMENTATION_PLAN.md. Implement JSON schema version 1 and normalized RFC 4180 CSV from the immutable Summary only. Do not recalculate metrics in either renderer. Ensure diagnostics never corrupt stdout and codes 1/2/3/4 emit no partial output; 4 remains unique-cardinality exhaustion. Run renderer reconciliation and CLI checks, record evidence, reconcile state, and stop.
```

## Prompt 6: Rich Terminal Output

```text
Execute only Step 6 of IMPLEMENTATION_PLAN.md. Implement the four-section Rich report and quality footer. Escape or disable markup for log-derived text, implement TTY/--no-color/NO_COLOR behavior, and preserve one Summary as the source. Retain the complete exit contract: 0 success, 1 I/O, 2 usage, 3 strict parse, 4 unique-cardinality exhaustion. Run the Step 6 checks, record evidence, reconcile state, and stop.
```

## Prompt 7: End-to-End CLI Semantics

```text
Execute only Step 7 of IMPLEMENTATION_PLAN.md. Complete buffered file/stdin orchestration and integration tests. Prove the full matrix: 0 complete success; 1 input/runtime I/O failure; 2 CLI usage error; 3 strict parse failure; 4 unique-cardinality exhaustion. Codes 1-4 must emit no partial report. Cover broken pipes without tracebacks. Run the listed suite and coverage gate, record evidence, reconcile state, and stop.
```

## Prompt 8: Performance and Quality

```text
Execute only Step 8 of IMPLEMENTATION_PLAN.md. Build the deterministic on-disk benchmark generator and opt-in performance test, then measure exactly 1,073,741,824 bytes on the documented laptop. Profile before optimizing. Preserve all output semantics and codes 0/1/2/3/4, especially code 4 for unique-cardinality exhaustion. Record environment, wall time, throughput, peak RSS, and exact result assertions in docs/PERFORMANCE.md. Run every listed quality check, attach current evidence, reconcile state, and stop. If the target fails, report recovery-required rather than success.
```

## Prompt 9: Release Candidate

```text
Execute only Step 9 of IMPLEMENTATION_PLAN.md. Finish user documentation, license/changelog, build metadata validation, clean-wheel installation, and P0 acceptance evidence. Document 0 success, 1 input/runtime I/O failure, 2 CLI usage error, 3 strict parse failure, and 4 unique-cardinality exhaustion everywhere exit behavior appears. Do not publish or deploy without separate authorization. Freeze the exact candidate, run the repository machine oracle and risk-tier checker, reconcile Idea to Deploy state, and stop with the receipt outcome; narration alone is not completion.
```

## Review Checklist for Every Step

- Scope matches exactly one implementation-plan step.
- Required files and tests exist; unrelated user changes are preserved.
- Commands were actually run and their current results recorded.
- No placeholder behavior, silent approximation, remote access, persistence, or service layer was introduced.
- Specs, implementation, tests, and all three renderers agree.
- The active exact candidate has the evidence required by `.itd/VERIFICATION_CONTRACT.json` before acceptance.
