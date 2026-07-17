# Claude Code Guide: Nginx Stream Report

This guide provides bounded prompts for executing `IMPLEMENTATION_PLAN.md`. Run only one prompt at a time. Each prompt requires reading `AGENTS.md`, `.itd/` contracts, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the named plan step before editing. Do not expand P0 scope; preserve WIP=1; never claim Done without command output.

## Session start prompt

```text
Open AGENTS.md and the Idea to Deploy contracts/state. Read PROJECT_ARCHITECTURE.md, PRD.md, STRATEGIC_PLAN.md, and IMPLEMENTATION_PLAN.md. Identify the single active implementation step and summarize its scope, exclusions, files, and verification command. Reconcile the task contract/state before edits. Do not implement a later step.
```

## Step 1 prompt — package and CLI contracts

```text
Execute only IMPLEMENTATION_PLAN.md Step 1. Create the Python 3.11 package metadata, console entry point, version, Click command contract, and focused CLI tests. Match PROJECT_ARCHITECTURE.md §§4, 6, 7, 12 and PRD FR-001/FR-008. Do not implement parsing or metrics yet. Run every Step 1 verification command, record exact output, and update Idea to Deploy state from evidence.
```

## Step 2 prompt — fixtures and benchmark harness

```text
Execute only IMPLEMENTATION_PLAN.md Step 2. Add deterministic combined-log fixtures, malformed cases, expected JSON report, and a reproducible opt-in 1 GiB benchmark harness. Do not claim the performance target until the real benchmark runs. Verify ordinary tests separately from the benchmark and record hardware/runtime metadata when the benchmark is invoked.
```

## Step 3 prompt — parser

```text
Execute only IMPLEMENTATION_PLAN.md Step 3. Implement the AccessRecord/report dataclasses and standard nginx combined-log parser. Treat each line as untrusted data, compile the pattern once, return timezone-aware timestamps, and avoid echoing full sensitive lines in diagnostics. Add focused valid/malformed tests, then run the exact parser and static checks from the plan.
```

## Step 4 prompt — aggregation

```text
Execute only IMPLEMENTATION_PLAN.md Step 4. Implement one-pass StreamingStats for top IPs, 4xx/5xx URLs, all 24 hour buckets, and exact unique User-Agent share. Use deterministic count-descending/key-ascending ordering and define empty-input behavior. Add all named boundary tests and supply coverage output.
```

## Step 5 prompt — input pipeline

```text
Execute only IMPLEMENTATION_PLAN.md Step 5. Connect file and stdin iterators to parser and aggregation without read(), readlines(), or raw-line retention. Implement malformed totals, stderr diagnostics, exit codes, and broken-pipe behavior exactly as specified. Prove file/stdin parity with CLI tests.
```

## Step 6 prompt — Rich terminal renderer

```text
Execute only IMPLEMENTATION_PLAN.md Step 6. Render the shared Report model using Rich summary and metric tables. Escape untrusted strings, support empty sections, honor TTY/NO_COLOR behavior, and do no per-record rendering. Add deterministic terminal assertions without coupling tests to irrelevant spacing.
```

## Step 7 prompt — JSON and CSV renderers

```text
Execute only IMPLEMENTATION_PLAN.md Step 7. Add versioned JSON and normalized CSV renderers over the same Report model. Enforce mutually exclusive flags and keep machine stdout free of ANSI/progress text. Add syntax, schema, quoting, ordering, and semantic-parity tests; run the plan's pipeline smoke commands.
```

## Step 8 prompt — hardening

```text
Execute only IMPLEMENTATION_PLAN.md Step 8. Configure and run lint, type checks, full tests, and >=90% coverage. Add adversarial parser inputs and audit stderr/terminal escaping for sensitive or untrusted log text. Fix findings within current scope; record anything unresolved as recovery rather than success.
```

## Step 9 prompt — performance

```text
Execute only IMPLEMENTATION_PLAN.md Step 9. Run the real representative 1 GiB benchmark on Python 3.11 and write BENCHMARK.md with hardware, input, elapsed time, throughput, valid/malformed records, and peak RSS. If >=30.0 seconds, profile first and optimize only measured hot paths. Keep the single-process architecture unless evidence justifies reopening ADR-001.
```

## Step 10 prompt — release candidate

```text
Execute only IMPLEMENTATION_PLAN.md Step 10. Replace README planning caveats with verified installation/use facts, document schemas/privacy/limitations, build wheel and sdist, inspect them, and install the wheel into a fresh Python 3.11 environment. Run terminal, JSON, and CSV smoke tests from the installed artifact. Do not publish externally without separate authorization.
```

## Review prompt

```text
Review the current step's diff against its task contract, PRD P0 acceptance criteria, PROJECT_ARCHITECTURE.md, and the forbidden areas in .itd/SCOPE_LOCK.md. Lead with findings by severity and cite exact files/lines. Require real verification evidence. If clean, state residual risks and the exact evidence reviewed; do not infer unrun tests.
```

## Session end prompt

```text
Re-run the active step's verification command, record the actual result, reconcile .itd-memory state and task contract, list changed files and remaining recovery items, and save context through /session-save. Leave one explicit next action and no ambiguous Done claim.
```

