# Claude Code Guide: nginx Log Top

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. It does not authorize implementation during the blueprint unit. Start a fresh work unit for each step, preserve WIP=1, and require the verification evidence named by the project’s `.itd/` contracts.

## Shared Preamble for Every Step

Use this before the step-specific prompt:

```text
Read AGENTS.md, CLAUDE.md, .itd/SCOPE_LOCK.md, .itd/VERIFICATION_CONTRACT.json,
PROJECT_ARCHITECTURE.md, PRD.md, and the matching section of
IMPLEMENTATION_PLAN.md. Preserve WIP=1. Do not broaden scope or change the
frozen CLI/data contracts without first updating the specs and scope lock.
Implement only the named step, run its verification commands, record actual
evidence, and finish handoff-ready. Do not claim completion without a current
exact-candidate adjudication receipt when the active contract requires one.
```

## Prompt 1 — Packaging and CLI shell

```text
Implement Step 1 only. Create pyproject.toml, package __init__.py, cli.py, and
the help/version/option-exclusivity tests. Keep analysis behavior unimplemented
behind explicit boundaries. Verify clean editable installation, --help,
--version, and the targeted tests. Update the Step 1 status in CLAUDE.md.
```

Expected evidence: install command, help invocation, and `tests/test_cli.py` output.

## Prompt 2 — Domain contracts and fixtures

```text
Implement Step 2 only. Encode the exact dataclasses and report invariants from
PROJECT_ARCHITECTURE.md Section 5 and CLI Interface. Add common, combined,
malformed, tie, hostile-control, and empty fixtures. Do not write parser or
renderer behavior yet. Verify model tests and compilation.
```

Expected evidence: model-test output and fixture inventory.

## Prompt 3 — Streaming parser

```text
Implement Step 3 only. Follow the Supported Grammar literally. Use a
linear scanner or prove the anchored parser cannot catastrophically backtrack.
Cover every acceptance/rejection clause, request "-", escaped quoted fields,
IPv4/IPv6 strings, timestamps, invalid statuses, extra fields, controls, and
long malformed lines. Run parser tests and static checks.
```

Expected evidence: parser tests including adversarial cases and Ruff output.

## Prompt 4 — Input and error boundary

```text
Implement Step 4 only. Stream buffered bytes from a read-only path or
stdin.buffer, decode per line with replacement, and map input, interrupt,
malformed-only, and broken-pipe outcomes to the frozen exit contract. Retain
only bounded sanitized diagnostic metadata; never a full raw malformed line.
Prove stdin/path metric equivalence.
```

Expected evidence: targeted CLI tests and observed exit 3/4/broken-pipe behavior.

## Prompt 5 — Exact aggregation

```text
Implement Step 5 only. Compute all four metrics in one pass with exact maps,
24 buckets, and a User-Agent set. Enforce status 400-599, tie ordering,
timestamp-hour semantics, common-format UA "-", and empty-input semantics.
Be explicit that memory is cardinality-dependent. Run coverage at >=90% for
aggregate.py and reports.py.
```

Expected evidence: aggregation test and coverage output.

## Prompt 6 — JSON

```text
Implement Step 6 only. Map AnalysisReport explicitly to JSON schema_version 1.
Emit one document on stdout with no ANSI, warnings, or progress text. Preserve
logical strings with standard JSON escaping and test exact schema, ordering,
zero values, and stderr isolation.
```

Expected evidence: JSON golden tests and successful `python -m json.tool`.

## Prompt 7 — Terminal

```text
Implement Step 7 only. Render four labeled Rich tables and diagnostics. Before
Rich markup escaping, visibly neutralize C0/C1, ESC, DEL, CR/LF, and bidi
override/isolate controls. Implement TTY color, --no-color, and NO_COLOR
precedence. Test hostile values without brittle width snapshots.
```

Expected evidence: terminal tests and a captured no-color sample.

## Prompt 8 — CSV

```text
Implement Step 8 only. Emit report,key,count,value with the exact discriminators
in PROJECT_ARCHITECTURE.md. Use Python csv quoting and apply the documented
single-quote protection to cells beginning =, +, -, or @. Test embedded commas,
quotes, newlines, formula-like cells, every report, and stdout cleanliness.
```

Expected evidence: CSV golden tests and successful DictReader parsing.

## Prompt 9 — Integrated quality

```text
Implement Step 9 only. Complete the exit/option matrix, prove no created files
or network connections, configure Ruff/mypy/pytest/coverage, build wheel+sdist,
and smoke-test the wheel in a fresh environment. Fix only defects within the
frozen requirements; route spec changes back to planning.
```

Expected evidence: lint, type, coverage, build, and clean-wheel smoke output.

## Prompt 10 — Performance and release candidate

```text
Implement Step 10 only. Build deterministic representative, high-cardinality,
and parser-stress generators matching PROJECT_ARCHITECTURE.md Section 11.
Record generator version/seed/cardinalities/line sizes, wheel hash, hardware,
commands, cold/warm time, RSS, exit, and output hashes. The representative
1 GiB gate is <30 seconds and <512 MiB RSS. Reconcile docs, freeze the exact
staged candidate, run its machine oracle, apply the risk-tier checker, and
accept only a current revalidated adjudication receipt.
```

Expected evidence: all three benchmark records, full quality suite, package smoke, and exact-candidate receipt.

## Recovery Prompt

```text
The current step failed verification. Do not advance status. Record the failed
command and output as recovery evidence, isolate the smallest causal defect,
and propose or apply only an in-scope correction. Re-run the failed check and
the narrow regression set. If the fix changes documented behavior, stop and
return to PRD/architecture before editing code.
```

## Review Prompt

```text
Review the exact candidate against PRD P0/P1 acceptance criteria,
PROJECT_ARCHITECTURE.md CLI/grammar/security/performance contracts, and the
active .itd scope. Check parser worst cases, cardinality-dependent memory,
stdout/stderr separation, terminal/CSV injection defenses, package install,
and benchmark provenance. Return machine-readable verdict evidence; narration
alone cannot accept the unit.
```
