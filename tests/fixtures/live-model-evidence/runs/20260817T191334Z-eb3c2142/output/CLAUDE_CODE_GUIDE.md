# Claude Code Implementation Guide: nginx-stream-stats

## How to Use This Guide

This file contains one bounded prompt per step in `IMPLEMENTATION_PLAN.md`.
Start each step in a clean session, read the named source-of-truth documents,
inspect the current repository state, implement only that step, run its checks,
and record evidence before moving on. Preserve WIP=1: never work ahead while a
step is failing.

These prompts authorize future product implementation; this blueprint session
creates documentation only. `PRD.md` defines behavior,
`PROJECT_ARCHITECTURE.md` defines interfaces and boundaries, and
`IMPLEMENTATION_PLAN.md` defines sequence. If they conflict, stop and reconcile
the documents before changing code.

## Non-Negotiable Contract for Every Step

- Stack: Python 3.11, Click, Rich, dataclasses, pip-installable package.
- Architecture: one local process, streaming and stateless; no database, HTTP
  API, authentication, server, cloud, Docker, or Kubernetes.
- Hourly percentage formula:
  `100 × hourly_request_count / total_valid_requests`.
- Exact exit codes, with no omissions or remapping:

  - `0`: success, including report output, help, and version.
  - `1`: unexpected runtime or non-pipe output failure.
  - `2`: CLI usage or configuration error.
  - `3`: input or log-data error.
  - `4`: unique-cardinality exhaustion.

- Never silently approximate User-Agent share or any top list.
- Do not claim the 1 GB/<30 s target without a real, documented benchmark.
- Do not proceed on failing formatting, lint, types, tests, or step-specific
  verification.

## Prompt 1: Package and domain contracts

```text
Implement only STEP 1 from IMPLEMENTATION_PLAN.md.

First read PRD.md, PROJECT_ARCHITECTURE.md, IMPLEMENTATION_PLAN.md, CLAUDE.md,
and the repository's Idea to Deploy contracts. Confirm the change scope is
limited to packaging, domain models, typed errors, the CLI help/version shell,
and their tests. Do not implement parsing, aggregation, or rendering yet.

Create the exact files listed in STEP 1. Use Python 3.11, Click, Rich,
dataclasses, a src layout, and a pip console entry point. Model the complete
future exit taxonomy now: 0 success, 1 unexpected runtime/output failure,
2 usage/configuration error, 3 input/log-data error, and 4 unique-cardinality
exhaustion. Code 4 must remain distinct even though its runtime behavior arrives
later.

Run every STEP 1 verification command. Report changed files and command
outcomes, update the active Idea to Deploy state, and stop. Do not start STEP 2.
```

## Prompt 2: Combined-log parser

```text
Implement only STEP 2 from IMPLEMENTATION_PLAN.md after confirming STEP 1 is
green. Read the Inputs, Domain Model, Processing Semantics, and Security
sections of PROJECT_ARCHITECTURE.md plus PRD US-1 and US-8.

Build an incremental nginx combined-format parser and safe file/stdin input
ownership. Treat logs as untrusted data. Validate request/status/timestamp,
normalize URL paths exactly as documented, preserve the User-Agent placeholder,
and return safe reason codes without echoing raw log content. Do not aggregate,
render, add gzip, or broaden format support.

Preserve the full exit taxonomy for the later CLI mapping: 0 success,
1 unexpected runtime/output failure, 2 usage/configuration error, 3 input or
log-data error, 4 unique-cardinality exhaustion. Parser/data failures belong to
3, never 2 or 4.

Create the listed fixtures and tests, run all STEP 2 checks, record evidence,
and stop before STEP 3.
```

## Prompt 3: Core aggregations

```text
Implement only STEP 3 from IMPLEMENTATION_PLAN.md. Read PRD US-2 through US-4
and the architecture's Processing Semantics and Performance contract.

Create one-pass aggregation for valid/malformed totals, exact IP counts,
statuses 400-599 by normalized error URL, fixed hours 00-23, and deterministic
top-10 ordering by count descending then key ascending. Keep raw records
ephemeral and return only the shared AnalysisReport. Do not add renderers, CLI
integration, gzip, or User-Agent cardinality work from STEP 4.

Do not weaken the universal exit contract: 0 success; 1 unexpected
runtime/output failure; 2 usage/configuration error; 3 input/log-data error;
4 unique-cardinality exhaustion. The hourly percentage to be finalized next is
exactly 100 × hourly_request_count / total_valid_requests, never a fraction.

Run every STEP 3 verification command, capture results, update state, and stop.
```

## Prompt 4: Percentages and cardinality guardrails

```text
Implement only STEP 4 from IMPLEMENTATION_PLAN.md. Read ADR-002, the CLI Output
contract, PRD US-4/US-5, and existing aggregation tests.

Add exact User-Agent distinct tracking, per-domain max-cardinality checks for
IP/error-URL/User-Agent keys, and report finalization. Compute hourly percentage
with the literal formula 100 × hourly_request_count / total_valid_requests and
UA share as 100 × unique_user_agent_count / total_valid_requests. Do not round
until serialization. Exceeding a bound must fail before insertion through the
typed unique-cardinality error.

Enforce all meanings: 0 success; 1 unexpected runtime/output failure; 2 usage
or configuration error; 3 input/log-data error including zero valid requests;
4 unique-cardinality exhaustion. Never remap code 4 to 1 or 3 and never return
an approximate result.

Run all STEP 4 tests including at-limit and one-over-limit cases. Record exact
command outcomes and stop before renderers.
```

## Prompt 5: Output renderers

```text
Implement only STEP 5 from IMPLEMENTATION_PLAN.md. Read the architecture Outputs,
ADR-003, Security boundaries, and PRD US-6/US-7.

Create isolated Rich text, schema-v1 JSON, and RFC 4180 long-form CSV renderers
that consume only AnalysisReport. Match all fields, ordering, 24 hour rows,
six-decimal serialized percentages, final newline, and text color rules. Disable
Rich markup for log-derived strings. Machine output must contain no ANSI or
diagnostics. Do not alter aggregation semantics or integrate Click yet.

All renderers must remain compatible with the full CLI exit contract: 0 success,
1 unexpected runtime/non-pipe output failure, 2 usage/configuration error,
3 input/log-data error, and 4 unique-cardinality exhaustion. A renderer must not
catch or relabel code-4 failures.

Create golden fixtures, run every STEP 5 verification command, record evidence,
and stop before CLI integration.
```

## Prompt 6: CLI integration and all exit codes

```text
Implement only STEP 6 from IMPLEMENTATION_PLAN.md. Treat
PROJECT_ARCHITECTURE.md section 'CLI Interface' as an exact public contract.

Connect input, parser, aggregator, and selected renderer in cli.py. Implement
INPUT/stdin, --json, --csv, --strict, --max-cardinality, color, help, and version.
Keep stdout empty on failures and diagnostics on stderr. Treat normal broken pipe
as quiet success. Use Click for syntax and configuration validation.

Black-box test every code with exactly these meanings: 0 success/help/version;
1 unexpected runtime or non-pipe output failure; 2 CLI usage/configuration
error; 3 input/log-data error; 4 unique-cardinality exhaustion. Code 4 must be
triggered by a deterministic low-limit fixture and must never be omitted,
collapsed into 3, or remapped.

Run every STEP 6 verification command plus formatting, lint, and types. Record
results and stop before performance work.
```

## Prompt 7: Release-quality verification and benchmark

```text
Implement only STEP 7 from IMPLEMENTATION_PLAN.md. Read all P0 acceptance
criteria, architecture Performance/Security/Verification sections, and the
Strategic Plan Definition of Done.

Add parity, machine-output cleanliness, untrusted-output, and performance
verification. Generate a deterministic representative 1 GB fixture with
realistic line lengths and cardinality; do not use a repeated trivial line.
Benchmark a release-like installed command, recording CPU, RAM, OS, storage,
Python version, fixture digest/shape, wall time, peak RSS, valid count, command,
and status. Write actual results to docs/PERFORMANCE_BASELINE.md. If the result
is not under 30 seconds, profile and perform at most one behavior-preserving
hot-path optimization cycle, then rerun; never fabricate a pass.

The integration suite must still prove 0 success, 1 unexpected runtime/output
failure, 2 usage/configuration error, 3 input/log-data error, and 4
unique-cardinality exhaustion. Run every STEP 7 command, record evidence, and
stop before packaging.
```

## Prompt 8: Distribution and documentation

```text
Implement only STEP 8 from IMPLEMENTATION_PLAN.md after every P0 gate is green.
Read README.md, PRD release criteria, architecture Packaging, and the measured
performance baseline.

Build the source distribution and pure-Python wheel, install the wheel into a
clean Python 3.11 virtual environment, and smoke-test the console command. Make
README examples and benchmark statements match observed behavior. Add an
approved permissive license. Gzip file-path support is optional P1: attempt it
only after P0 completion and drop it if the weekend timebox is threatened.

The installed artifact must preserve the complete contract: 0 success;
1 unexpected runtime or non-pipe output failure; 2 usage/configuration error;
3 input/log-data error; 4 unique-cardinality exhaustion. Explicitly run the
black-box 0/1/2/3/4 tests after installing the built wheel; code 4 is mandatory.

Run every STEP 8 verification command and the final full suite. Reconcile Idea
to Deploy state and report artifacts plus measured evidence. Do not publish or
push unless the user separately authorizes that external action.
```

## Final Handoff Checklist

- All eight steps were completed in order with WIP=1.
- The current exact candidate passed its project-defined verification gate.
- P0 acceptance criteria and exit codes `0/1/2/3/4` have runtime evidence.
- The under-30-second claim points to a real representative 1 GB report.
- Build artifacts install in a clean Python 3.11 environment.
- P1/P2 omissions are documented and do not weaken P0.
- The repository contains no forbidden database, API, auth, server, cloud,
  Docker, or Kubernetes implementation.
