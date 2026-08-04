# Claude Code Guide: Nginx Log Stats

## How to Use This Guide

Run one implementation prompt at a time in order. Before each prompt, read `CLAUDE.md`, the named specification sections, `.itd/SCOPE_LOCK.md`, and current `.itd-memory/STATE.json`. Preserve WIP=1. These prompts authorize only their named step; they do not authorize publication, scope expansion, servers, databases, or other deferred features.

For every step, freeze the exact staged candidate, run its listed machine checks, apply the Idea to Deploy risk-tier checker, and retain the current adjudication receipt. If a check cannot run or fails, report recovery status and stop instead of declaring completion.

## Prompt 1: Package, Models, and Fixtures

```text
Implement only IMPLEMENTATION_PLAN.md Step 1. Read PRD.md US-1/FR-1/FR-2/NFR-4 and PROJECT_ARCHITECTURE.md Component Design, Processing and Data Model, and Packaging and Deployment first. Create the exact package/model/fixture/test files named by the step. Do not implement analytics or renderers. Run every Step 1 verification command and attach outputs to the active Idea to Deploy evidence. Reconcile CLAUDE.md and .itd-memory state; leave Step 2 as the single next action.
```

## Prompt 2: Streaming Parser and Metrics

```text
Implement only IMPLEMENTATION_PLAN.md Step 2. Treat binary physical-line decoding, the 1 MiB line guard, default nginx escaping, exact status/hour/User-Agent semantics, deterministic ties, and the 250,000 combined-cardinality default as contracts. Add the named parser/input/aggregate/error modules and tests. Do not build renderers. Run all Step 2 verification commands and retain exact-candidate evidence. If any grammar ambiguity appears, update PRD.md and PROJECT_ARCHITECTURE.md before code.
```

## Prompt 3: Performance Spike

```text
Implement only IMPLEMENTATION_PLAN.md Step 3. Generate the deterministic fixture outside the repository, record its manifest, establish the correctness-first expected report, and measure elapsed time plus peak RSS. Add a fast path only if profiling shows it is needed, and require differential equality with the reference parser. The gate is correct output, <30 seconds, and <=512 MiB on the declared reference laptop. Do not soften or fabricate the gate. Record the environment and mark the step recovery_required if evidence does not pass.
```

## Prompt 4: CLI and Exit Codes

```text
Implement only IMPLEMENTATION_PLAN.md Step 4 and the exact PROJECT_ARCHITECTURE.md CLI Interface. Complete Click options, file/stdin routing, stdout/stderr separation, and codes 0/1/2/3/4. Infinite streams and successful partial SIGINT reports remain out of scope. Add all named tests, run the verification commands, and preserve the passing performance path from Step 3.
```

## Prompt 5: Rich Terminal Renderer

```text
Implement only IMPLEMENTATION_PLAN.md Step 5. Build the four-section Rich terminal report and sanitization boundary. Logged values are untrusted: disable/escape markup, make controls harmless, respect --no-color/NO_COLOR/terminal capability, and never change the renderer-neutral Report semantics. Add snapshots and adversarial terminal cases. Run all Step 5 checks and attach exact-candidate evidence.
```

## Prompt 6: JSON and CSV

```text
Implement only IMPLEMENTATION_PLAN.md Step 6. Follow the JSON schema-version-1 and CSV section,key,value,rank contracts literally. Preserve deterministic ordering, UTF-8, trailing newline behavior, lossless values, RFC 4180 quoting, stdout purity, and zero ANSI escapes. Document that CSV is machine data and formula-leading values require text import. Run schema/golden/end-to-end checks and retain their outputs.
```

## Prompt 7: Hardening and Acceptance

```text
Implement only IMPLEMENTATION_PLAN.md Step 7. Build the US-1..US-7 acceptance trace plus adversarial and streaming-memory tests. Exercise decode failures, extreme lines/cardinality, control sequences, CSV formula-leading text, broken pipes, and every boundary code. Run pytest coverage >=90%, ruff, mypy, and dependency audit. Address Critical/High issues; unresolved evidence means recovery, never acceptance.
```

## Prompt 8: Release Candidate Verification

```text
Implement only IMPLEMENTATION_PLAN.md Step 8. Finalize user/release documentation, build the wheel, smoke-install it in a clean temporary environment, and rerun the complete suite, audit, golden schemas, and deterministic 1 GB benchmark on the exact staged candidate. Record fixture hash, hardware, OS, Python, elapsed time, and peak RSS. Reconcile Idea to Deploy state and request a current adjudication receipt. Do not publish or push without a separate explicit user request.
```

## Review Prompts

After each implementation step, use this bounded review request:

```text
Review only the active step's exact candidate against its PRD acceptance criteria, architecture contract, and verification commands. Prioritize correctness, false-success paths, stream/resource boundaries, unsafe rendering, machine-schema compatibility, and regression risk. Return file/line findings with severity and a machine-readable verdict. Do not broaden scope or edit code unless separately asked.
```

For the final candidate, also replay the Architecture Decision Record conditions in `PROJECT_ARCHITECTURE.md`; all performance and compatibility claims require runtime evidence.

