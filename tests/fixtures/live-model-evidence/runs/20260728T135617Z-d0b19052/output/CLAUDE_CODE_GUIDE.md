# Claude Code Guide: nginx-log-top

This guide turns `IMPLEMENTATION_PLAN.md` into bounded execution prompts. Use one prompt at a time, preserve WIP=1, and do not start the next step until the current step’s verification evidence is recorded. The durable behavior contract is `PRD.md`; architecture decisions and CLI schemas are in `PROJECT_ARCHITECTURE.md`.

## Session Start Prompt

```text
Read AGENTS.md, CLAUDE.md, PRD.md, PROJECT_ARCHITECTURE.md,
IMPLEMENTATION_PLAN.md, and STRATEGIC_PLAN.md. Report the active step from
CLAUDE.md and inspect the current working tree. Preserve WIP=1 and unrelated
user changes. Do not broaden scope. Before marking a step complete, run every
verification assigned to it and report exact commands/results.
```

## STEP 1 Prompt: Package and CLI contracts

```text
Execute only IMPLEMENTATION_PLAN.md STEP 1. Create the Python 3.11 package
metadata, src package, Click entry point, and contract-level CLI tests listed
there. Keep report behavior inert; do not pull later steps forward. Match the
command/options/exit contract in PROJECT_ARCHITECTURE.md under "CLI Interface".
Run the STEP 1 verification commands and update CLAUDE.md status/evidence.
```

Expected evidence: editable install succeeds; help lists the exact argument and options; CLI contract tests pass.

## STEP 2 Prompt: Typed parser

```text
Execute only IMPLEMENTATION_PLAN.md STEP 2. Implement frozen/slotted domain
dataclasses, typed errors, the bounded 1 MiB physical-line reader, and nginx
combined-format parser. Preserve the logged timestamp offset and normalize a
missing User-Agent exactly as specified. Add only synthetic fixtures. Cover
IPv4, IPv6, escaping, timestamps, malformed input, and oversized lines. Run
all STEP 2 verification commands and update CLAUDE.md status/evidence.
```

Expected evidence: parser tests and `compileall` pass; no database/network/service dependency appears.

## STEP 3 Prompt: Streaming aggregation

```text
Execute only IMPLEMENTATION_PLAN.md STEP 3. Build exact one-pass counters and
the immutable snapshot. Do not retain raw AccessLogEvent objects. Use
HourBucket(local_date, hour, offset_minutes), keeping equal-UTC-instant buckets
separate when their logged hour/offset differs. Implement deterministic ties,
400–599 filtering, and exact unique User-Agent share. Run STEP 3 verification
and update CLAUDE.md status/evidence.
```

Expected evidence: aggregation and coverage commands pass, including equal-instant/different-offset tests.

## STEP 4 Prompt: JSON and CSV

```text
Execute only IMPLEMENTATION_PLAN.md STEP 4. Implement the exact JSON object
and CSV union schema documented under PROJECT_ARCHITECTURE.md "CLI Interface".
Keep machine stdout free of ANSI, progress, and warnings. Preserve stable
ordering and serializer-safe quoting. Wire --json, --csv, and --top without
adding undocumented flags. Run STEP 4 verification and update CLAUDE.md.
```

Expected evidence: renderer/CLI tests pass and JSON validates through `json.tool`.

## STEP 5 Prompt: Rich terminal report

```text
Execute only IMPLEMENTATION_PLAN.md STEP 5. Add the default Rich report with
all required sections. Disable markup for untrusted values and visibly escape
ESC, C0/C1 controls, CR, LF, and NUL. Respect TTY detection, NO_COLOR, and
--no-color. Do not change the machine schemas. Run STEP 5 verification and
update CLAUDE.md status/evidence.
```

Expected evidence: interactive/no-color/redirected tests pass, including hostile fields.

## STEP 6 Prompt: Input and exit lifecycle

```text
Execute only IMPLEMENTATION_PLAN.md STEP 6. Complete lazy file/stdin handling,
strict and lenient malformed-line behavior, bounded oversized-line discard,
broken-pipe handling, interrupts, stderr separation, and exact exit mappings.
Do not emit normal tracebacks for documented user/input cases. Run every STEP
6 verification command and update CLAUDE.md status/evidence.
```

Expected evidence: file/stdin data equivalence, all exit-code cases, and JSON pipeline smoke test pass.

## STEP 7 Prompt: Quality and performance oracle

```text
Execute only IMPLEMENTATION_PLAN.md STEP 7. Freeze tests/benchmark-manifest.json
to BR-1 exactly as PROJECT_ARCHITECTURE.md specifies. Build deterministic
normal/high-cardinality fixture generation, time only processing, use one
warm-up plus five warm-cache runs, record median time and /usr/bin/time -v
peak RSS. Do not claim BR-1 acceptance from different hardware; label other
results secondary. Add fuzz/security/static evidence and run STEP 7 commands.
Update CLAUDE.md and docs/PERFORMANCE.md with exact evidence.
```

Expected evidence: ≥90% coverage, dependency check, benchmark manifest/hash, five timings, median <30.0 seconds, and normal-profile RSS ≤1.5 GiB on BR-1. If BR-1 is unavailable, explicitly mark performance acceptance unverified.

## STEP 8 Prompt: Package and handoff

```text
Execute only IMPLEMENTATION_PLAN.md STEP 8. Reconcile documentation with the
implemented CLI, build wheel/sdist, install the exact wheel in a clean Python
3.11 environment, and smoke-test file/stdin plus terminal/JSON/CSV modes. Run
the full acceptance suite and record review/security/performance evidence. Do
not publish externally unless separately authorized. Update CLAUDE.md so the
next action is explicit.
```

Expected evidence: build and metadata checks pass; clean-wheel install works; full test/coverage evidence and any unverified BR-1 gate are visible.

## Review Prompt

```text
Review the frozen candidate against PRD.md and PROJECT_ARCHITECTURE.md. Focus
on parser correctness, exact counter semantics, HourBucket identity, stdout
schema stability, terminal control injection, bounded physical lines, exit
codes, and the benchmark oracle. Classify findings by severity with file and
line evidence. Do not edit during this review.
```

## Handoff Prompt

```text
Summarize the current single active step, completed acceptance evidence,
unverified gates, working-tree state, and exact next action. Reconcile the
status table in CLAUDE.md. At the end of this session save context through
/session-save as required by CLAUDE.md.
```
