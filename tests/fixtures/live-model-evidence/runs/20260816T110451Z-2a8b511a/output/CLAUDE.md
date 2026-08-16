# Project Memory: nginx-stream-stats

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams conventional nginx combined-format access logs and reports:

1. top-10 client IPs by valid request count;
2. top-10 request targets by combined 4xx/5xx count;
3. 24 hourly request percentages using `100 × hourly_request_count / total_valid_requests`;
4. exact unique User-Agent count and share.

Default output is colored Rich terminal text. `--json` and `--csv` are stable pipeline modes. The product is installable with pip, costs $0, targets a one-weekend delivery, and must demonstrate representative 1 GB processing under 30 seconds on documented laptop hardware.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, src-layout pip package.
- One local process and one streaming pass; no raw-record retention.
- No authentication, database, HTTP API, server, cloud, Kubernetes, or telemetry.
- Exact results up to a per-dimension cardinality limit; fail closed rather than approximate.
- Top-list ties sort by count descending, then string key ascending.
- JSON/CSV report data goes only to stdout; diagnostics go to stderr.
- Complete exit contract: `0` success, `1` runtime/input/output failure, `2` usage/configuration error, `3` zero valid requests, `4` unique-cardinality exhaustion.
- Code 4 specifically means exhaustion while tracking exact distinct IPs, error URLs, or User-Agents; never omit or remap it.
- Specs are the source of truth: change `PRD.md` and `PROJECT_ARCHITECTURE.md` before changing promised behavior.
- Preserve WIP=1 and use the current Idea to Deploy exact-candidate verification protocol for implementation acceptance.
- Do not create `DEVILS_ADVOCATE_REVIEW.md` except through the separately authorized external review session.

## Planned Structure

```text
src/nginx_stream_stats/{cli,inputs,parser,models,aggregate}.py
src/nginx_stream_stats/renderers/{terminal,json,csv}.py
tests/{fixtures,test_models,test_parser,test_inputs,test_aggregate,test_cli,test_output_contracts,test_performance}.py
scripts/benchmark.sh
pyproject.toml
```

No product source exists at blueprint completion; this tree is a plan, not current-state documentation.

## Sources of Truth

| Document | Authority |
|---|---|
| `STRATEGIC_PLAN.md` | Audience, alternatives, business constraints, priorities, risks, Definition of Done |
| `PROJECT_ARCHITECTURE.md` | Parsing, data semantics, CLI interface, schemas, resource boundaries, ADRs |
| `PRD.md` | User stories, priorities, acceptance criteria, kill criteria |
| `IMPLEMENTATION_PLAN.md` | Dependency order, files, commands, weekend boundaries |
| `CLAUDE_CODE_GUIDE.md` | Bounded prompt for each implementation step |
| `.itd/` and `.itd-memory/` | Active scope, verification contract, and durable execution state |

If documents conflict, architecture governs current technical semantics, but reconcile the conflict in all documents before implementation.

## Implementation Status

| Step | Status | Evidence/next action |
|---:|---|---|
| Blueprint documents | Complete | Static document validation recorded in `.itd-memory/STATE.json` |
| 1. Package skeleton | Not started | Run Guide 1 |
| 2. Models and failures | Not started | Blocked by Step 1 |
| 3. Parser and inputs | Not started | Blocked by Step 2 |
| 4. Aggregation | Not started | Blocked by Step 3 |
| 5. Terminal renderer | Not started | Blocked by Step 4 |
| 6. JSON/CSV renderers | Not started | Blocked by Step 4 |
| 7. CLI orchestration | Not started | Blocked by Steps 3–6 |
| 8. Acceptance/performance | Not started | Blocked by Step 7 |
| 9. Gzip/release handoff | Not started | P1 after P0 acceptance |

## Working Rules

1. Read the applicable repository-local Idea to Deploy skill and current `.itd/SCOPE_LOCK.md` before edits.
2. Keep a single active implementation unit. Do not bundle P2 work into P0/P1 steps.
3. Preserve unrelated user changes and never weaken tests or gates to obtain a pass.
4. Run the exact verification commands for the step and record observed evidence, not expected outcomes.
5. Before acceptance, freeze the exact staged candidate, run its machine oracle, and obtain a current risk-tier adjudication receipt. No standalone `PASSED` text is sufficient.
6. Do not bind undeclared ignored/untracked overlays into the oracle; explicitly declare and hash any necessary non-Git input.
7. Update status and next action after each significant block.
8. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Current Handoff

The blueprint is planning-only. The next authorized action, if requested, is Guide 1: package and quality skeleton. Do not infer authorization to implement product code from the existence of this plan.
