# Project Memory: nginx-log-top

## Context

This repository is planned as a local Python 3.11 CLI for DevOps/SRE engineers. It streams one nginx combined access log and reports top client IPs, error-producing URLs, hourly percentages, and exact unique User-Agent share. Text is default; JSON and CSV are pipeline interfaces. The performance target is 1 GB in under 30 seconds on a documented laptop.

The current repository state is blueprint-only. Do not infer that product code, tests, or packaging already exist.

## Sources of Truth

1. `PRD.md` defines behavior, priority, acceptance, and scope.
2. `PROJECT_ARCHITECTURE.md` defines metric semantics, modules, schemas, CLI, and exit codes.
3. `IMPLEMENTATION_PLAN.md` defines dependency order and checks.
4. `STRATEGIC_PLAN.md` defines goals, roadmap, risks, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` provides bounded implementation prompts.

If behavior must change, update the relevant source-of-truth document before implementation.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, a `src/` layout, and pip packaging.
- Keep a single-process, stateless, streaming architecture.
- Do not add authentication, a database, HTTP API, server, cloud, Docker, or Kubernetes.
- Never materialize the full input or retain parsed records after aggregation.
- Preserve deterministic rank ordering and one canonical result across renderers.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Preserve exit codes `0/1/2/3/4`; code 4 is exact User-Agent cardinality exhaustion.
- stdout is report-only; stderr is diagnostics-only.
- Treat all log content as untrusted data and escape terminal control/markup characters.
- Work on one implementation-plan step at a time and record real verification evidence.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Structure

```text
src/nginx_log_top/       application package
src/nginx_log_top/renderers/ presentation-only adapters
tests/                   unit, integration, golden, performance tests
tests/fixtures/          compact deterministic log inputs
scripts/                 benchmark fixture generator
docs/PERFORMANCE.md      reproducible measurement record
```

## Status

| Step | State | Acceptance evidence |
|---:|---|---|
| Blueprint documents | Complete | Document-presence and contract checks |
| 1. Package and CLI contract | Not started | None |
| 2. Parser and models | Not started | None |
| 3. Aggregation | Not started | None |
| 4. Rich text | Not started | None |
| 5. JSON and CSV | Not started | None |
| 6. CLI integration | Not started | None |
| 7. Performance gate | Not started | None |
| 8. Release candidate | Not started | None |

## Next Action

Begin STEP 1 only when implementation is explicitly requested. Use the corresponding prompt in `CLAUDE_CODE_GUIDE.md`; do not implement product code as part of blueprint work.
