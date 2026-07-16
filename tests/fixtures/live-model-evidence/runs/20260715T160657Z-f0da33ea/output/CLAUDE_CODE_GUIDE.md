# Claude Code Guide: Nginx Stream Analytics CLI

## Purpose

This guide provides bounded prompts for implementing [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Use one prompt at a time and preserve WIP=1. Before each step, read [PRD.md](PRD.md), the named architecture sections, the repository `AGENTS.md`, `.itd/` contracts, and current `.itd-memory/` state. Do not widen scope without updating the specification and scope lock first.

For every step, require actual command output as evidence; an unrun check remains unverified. Do not introduce authentication, a database, HTTP API, service, cloud, Docker, or Kubernetes.

## Session Start Prompt

```text
Read AGENTS.md, CLAUDE.md, .itd/SCOPE_LOCK.md, .itd/VERIFICATION_CONTRACT.json,
.itd-memory/STATE.json if present, PRD.md, PROJECT_ARCHITECTURE.md, and
IMPLEMENTATION_PLAN.md. Identify the first incomplete implementation step and
work only on that step. Before edits, make its file scope and verification
evidence explicit. Preserve all user changes and do not implement later steps.
```

## Step 1 Prompt — Package and CLI Skeleton

```text
Execute IMPLEMENTATION_PLAN.md Step 1 only. Create pyproject.toml, package
initialization, Click CLI option/argument skeleton, and focused CLI tests.
Honor Python 3.11, the nginx-stats console script, mutual exclusion of --json
and --csv, and architecture exit-code contracts. Do not implement parsing or
metrics yet. Run the three Step 1 verification commands and record outputs.
```

## Step 2 Prompt — Domain Contracts

```text
Execute Step 2 only. Implement the exact dataclasses and invariants from
PROJECT_ARCHITECTURE.md section 5 plus their tests. Keep models independent of
Click and Rich. Ensure Report is an immutable renderer boundary and hour state
always has 24 buckets. Run pytest and mypy evidence before marking complete.
```

## Step 3 Prompt — Streaming Parser

```text
Execute Step 3 only. Implement the standard nginx combined-format parser,
line-by-line file/stdin iteration, strict per-line UTF-8 decoding, nginx escape
grammar, direct hour extraction, and lenient vs --strict malformed-line
behavior. Add all specified fixtures and parser/CLI tests, including long
fields, invalid UTF-8, and IPv6. Do not render metrics.
Demonstrate the parser and lint checks from the plan.
```

## Step 4 Prompt — Aggregation

```text
Execute Step 4 only. Implement one-pass exact aggregates for client IPs,
status-400..599 exact request targets, 24 logged-hour buckets, and distinct
non-empty User-Agent strings. Apply deterministic count-desc/key-asc top-ten
ordering, the PRD share formula, and the combined --max-unique guard. Add
edge/tie/empty/guard tests and meet coverage and mypy gates. The production
loop must allocate no AccessRecord or datetime per line.
```

## Step 5 Prompt — JSON

```text
Execute Step 5 only. Implement schema-versioned JSON exactly as architecture
section 9 specifies. Keep stdout to one JSON document plus newline, include all
24 hours, and keep values numeric and deterministic. Add golden and CLI tests,
then run json.tool and pytest verification from the plan.
```

## Step 6 Prompt — CSV

```text
Execute Step 6 only. Implement normalized CSV using the standard csv module
with columns schema_version,metric,rank,key,count,value. Emit every required
section in deterministic order and preserve UTF-8/quoted data correctly. Add
the golden fixture and edge cases and run both Step 6 verification commands.
```

## Step 7 Prompt — Terminal and Diagnostics

```text
Execute Step 7 only. Implement four safe Rich sections plus parsed/skipped
summary. Escape log-derived markup; enforce TTY, NO_COLOR, and --no-color
rules; keep structured stdout clean; implement broken-pipe and exit behavior.
Add focused renderer/CLI tests and run the listed verification commands.
```

## Step 8 Prompt — Performance and Hardening

```text
Execute Step 8 only. Add a deterministic seeded benchmark generator and
adversarial tests. Generate the 1 GiB reference fixture, record exact hardware,
checksum/profile, warm and cold wall times, and peak RSS. If the <30 s or
<250 MB gate fails, profile before changing code and preserve red/green
correctness evidence. Never hide failure by approximating or adding storage.
```

## Step 9 Prompt — Release Handoff

```text
Execute Step 9 only after Steps 1-8 have evidence. Reconcile README behavior
with the implemented CLI, add the approved open-source license and changelog,
add non-publishing CI checks, build artifacts, and verify a wheel in a fresh
Python 3.11 environment. Run lint, type, test, build, twine, and fresh-install
commands; record any unavailable check as unverified rather than passing it.
```

## Review Prompt

```text
Review the completed step against its PRD acceptance criteria, architecture
contracts, exact allowed file scope, and verification outputs. Look for full
input materialization, unstable ties, output contamination, unsafe Rich
markup, schema drift, incorrect 4xx/5xx bounds, timezone conversion, and
unmeasured performance claims. Return a machine-readable pass, pass-with-
warnings, or blocked verdict and cite evidence.
```

## Session Close Prompt

```text
Re-run the active step's verification, record evidence and unresolved risks,
reconcile .itd-memory state with actual files, and name exactly one next action.
Do not mark incomplete or unverified work complete. At the end of every session
or meaningful work block, save context through /session-save.
```
