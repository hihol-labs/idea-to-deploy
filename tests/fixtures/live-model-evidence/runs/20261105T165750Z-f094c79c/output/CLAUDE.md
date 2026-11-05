# Nginx Lens — Project Memory

## Context and Sources

Planning-only blueprint for a local nginx combined-log CLI. Product code has not been implemented. Python 3.11, Click, Rich, dataclasses; pip installation; $0 cash budget; one weekend. One process streams records and retains bounded exact aggregates, with no durable state.

Read [PRD.md](PRD.md) for acceptance criteria, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for the interface and semantics, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for execution. [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) provides step prompts; [README.md](README.md) is the user entry point. Amend the specification before changing behavior; reconcile inconsistencies before implementing.

## Working Rules

- WIP=1; implement one plan step at a time with tests and actual verification output.
- No auth, database, HTTP API, server, cloud or Kubernetes. Do not add dependencies beyond the documented scope without a reasoned decision.
- Preserve exit codes 0/1/2/3/4: success, I/O/runtime failure, usage error, interruption, unique-cardinality exhaustion. Never silently emit approximate or truncated results.
- Hourly request percentage is `100 × hourly_request_count / total_valid_requests`; use UTC buckets. UA share uses the nonmissing-UA request denominator.
- Do not expose production logs or secrets, retain raw records, or introduce telemetry. Use clearly labeled synthetic fixtures.
- Require explicit human confirmation for publishing, push/PR, deployment, destructive operations and other external actions. Local tests and reversible edits are authorized by implementation tasks.
- Keep agent instructions in this file; do not scatter alternative rules among task prompts.
- At the end of every session or significant block of work, save context through /session-save.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

`pyproject.toml`; `src/nginx_lens/{__init__,cli,reader,parser,models,aggregate,render}.py`; `tests/` with synthetic fixtures and process/distribution checks; `benchmarks/run.py` and measured `benchmarks/RESULTS.md`; `LICENSE`. These are planned paths, not existing implementation files.

## Step Status

| Step | Work | Status | Evidence |
|---|---|---|---|
| 1 | Package and contracts | Not started | No code/tests run |
| 2 | Reader/parser | Not started | No code/tests run |
| 3 | Exact aggregates | Not started | No code/tests run |
| 4 | JSON/CSV | Not started | No code/tests run |
| 5 | Rich text | Not started | No code/tests run |
| 6 | Failure semantics | Not started | No code/tests run |
| 7 | Performance/correctness | Not started | Target unmeasured |
| 8 | Local release readiness | Not started | No wheel built |

## Review and Next Action

The adversarial review is deferred to the external harness in a fresh session; no independent reviewer ran here. Next product action, after planning acceptance and any external findings: execute implementation step 1. No code execution, release or publication is implied by the blueprint.
