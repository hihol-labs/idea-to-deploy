# Claude Code Implementation Guide: nginx-log-report

This guide supplies bounded prompts for executing [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) later. It does not authorize implementation during the blueprint phase. Run one prompt at a time (WIP=1), preserve the scope lock, and do not advance without the named evidence.

## Shared Prefix for Every Step

```text
Read AGENTS.md, CLAUDE.md, .itd/SCOPE_LOCK.md, .itd/VERIFICATION_CONTRACT.json,
PROJECT_ARCHITECTURE.md, PRD.md, and the named IMPLEMENTATION_PLAN.md step.
Treat PRD acceptance criteria as source. Keep WIP=1. Do not add a database,
HTTP API, auth, server, cloud, Docker, or Kubernetes. Before editing, update the
active scope/unit state as required by Idea to Deploy. Use Verification Loop:
freeze the exact staged candidate, run its machine oracle, apply the risk-tier
checker, and accept only a current revalidated adjudication receipt. Preserve
unrelated user changes and finish with tests/evidence, reconciled state, and an
explicit next action.
```

## Prompt 1: Package and CLI Skeleton

```text
Execute only Implementation Plan Step 1. Create the pip-installable Python 3.11
src-layout skeleton, Click entry point, help/version behavior, and focused CLI
tests. Do not implement parsing or reports. Verify editable install, help, and
the named test file. Reconcile the exact-candidate receipt before reporting.
```

## Prompt 2: Domain Models and Errors

```text
Execute only Step 2. Implement the architecture's AccessRecord, RankedItem, and
ReportSnapshot dataclasses plus domain error/exit constants. Make invalid states
explicit and keep snapshots renderer-neutral. Add only the named tests, run
pytest and mypy, then complete the Verification Loop receipt.
```

## Prompt 3: Combined-Format Parser

```text
Execute only Step 3. Implement incremental parsing for the exact combined-format
contract, including timestamps, escapes, request "-", invalid UTF-8 policy, and
malformed outcomes. Treat input as untrusted and avoid catastrophic regex paths.
Add representative fixtures/tests. Run the named parser checks and exact-candidate
Verification Loop. Do not aggregate or render yet.
```

## Prompt 4: Streaming Aggregator

```text
Execute only Step 4. Implement one-pass exact aggregation and deterministic
snapshot finalization. Cover error status boundaries, ties, all 24 hours, empty
User-Agent, and exact diversity math. Before renderer work, freeze the deterministic
representative and high-cardinality corpus manifest with content/cardinality/snapshot
hashes. Keep rendering out of the hot loop. Run the focused tests/coverage and
exact-candidate Verification Loop.
```

## Prompt 5: Terminal Renderer

```text
Execute only Step 5. Build the Rich text renderer from ReportSnapshot. Color must
be optional and meaning-independent. Escape log-derived text and control bytes;
never interpret it as Rich markup. Add terminal and redirected golden tests. Run
the named checks and exact-candidate Verification Loop.
```

## Prompt 6: JSON and CSV

```text
Execute only Step 6. Implement the architecture's version-1 JSON schema and the
five-column RFC 4180 CSV schema. Keep stdout data-only, stderr diagnostic-only,
with no ANSI. Add golden and parser-based validation tests. Run the named checks
and exact-candidate Verification Loop.
```

## Prompt 7: CLI Integration and Failures

```text
Execute only Step 7. Connect input, parser, aggregator, and renderer while
preserving stdin ownership and atomic structured output. Implement all documented
exit codes, bounded malformed diagnostics, SIGINT, and broken-pipe behavior. Add
file/stdin/end-to-end tests. Run the named checks and Verification Loop receipt.
```

## Prompt 8: Performance and Robustness

```text
Execute only Step 8. First create deterministic benchmark generation and hostile
input tests. Measure the unchanged candidate on exactly 1,000,000,000 bytes, three runs, and
record median, peak RSS, hardware, corpus hash, and command. If over 30 seconds,
profile before changing code and limit optimization to measured single-process
hot paths. Run robustness checks and obtain the risk-tier Verification Loop
receipt. Do not claim the target from estimates.
```

## Prompt 9: Release Candidate

```text
Execute only Step 9. Update README examples from actual behavior, add the selected
open-source license/changelog, build wheel and sdist, and smoke-test the wheel in
a clean venv. Run the full test, coverage, lint, type, package, and benchmark gates.
Freeze the exact staged candidate and require a current adjudication receipt.
Only then update CLAUDE.md status and state the next release action.
```

## Cross-Cutting Review Prompt

```text
Review the frozen candidate against PROJECT_ARCHITECTURE.md and every P0 PRD
criterion. Check especially parser ambiguity, structured stdout contamination,
untrusted Rich markup/control data, status boundary 400–599, deterministic ties,
User-Agent denominator semantics, stdin ownership, memory cardinality, and the
1 GiB benchmark method. Return findings with file/line evidence; do not edit.
Accept only through the repository's current risk-tier adjudication receipt.
```

## Session Handoff

At the end of each step, record commands and outputs, candidate identity, receipt status, incomplete risks, and the single next action. Never mark later steps complete speculatively.
