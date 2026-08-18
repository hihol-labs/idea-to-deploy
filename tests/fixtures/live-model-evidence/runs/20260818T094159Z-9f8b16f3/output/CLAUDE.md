# Project Memory: Nginx Stream Insights

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs and reports top-10 IPs, top-10 URLs with 4xx/5xx statuses, 24-hour request percentages, and exact unique User-Agent share. Text is default; JSON and CSV are stable pipeline interfaces. Target: a representative 1 GB log in under 30 seconds on a documented laptop.

## Sources of Truth

1. `PRD.md` defines behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines component, CLI, metric, schema, and failure contracts.
3. `IMPLEMENTATION_PLAN.md` defines delivery order and verification commands.
4. `STRATEGIC_PLAN.md` defines scope, priorities, risks, and success/kill criteria.
5. `.itd/` contracts and `.itd-memory/` state govern active execution and completion evidence.

Change the specification before changing behavior. Preserve WIP=1 and the exact-candidate Verification Loop. A test run or prose verdict alone is not completion.

## Hard Rules

- Use Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- Keep one local process and streaming input; do not load entire logs.
- Do not add authentication, database, HTTP API, server, cloud, Kubernetes, or telemetry upload.
- Keep stdout as report data and stderr as diagnostics; never style JSON/CSV.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Preserve the complete exit contract: `0` success, `1` internal/runtime failure, `2` usage error, `3` input failure, `4` unique-cardinality exhaustion. Never omit or remap code 4.
- Keep deterministic tie ordering and stable machine schemas.
- Profile before performance optimization; record the 1 GB fixture and machine context.
- Do not write `DEVILS_ADVOCATE_REVIEW.md` unless a real, explicitly invoked reviewer workflow owns that artifact.
- At the end of every session or significant block of work, save context via `/session-save`.

## Planned Structure

```text
src/nginx_stream_insights/
  cli.py input.py parser.py models.py aggregate.py errors.py
  renderers/{text,json,csv}.py
tests/{fixtures,unit,integration,performance}/
```

## Status

| Step | State | Acceptance gate |
|---:|---|---|
| Blueprint documentation | Complete | Required planning files present and structurally validated |
| 1. Package/contracts | Not started | Clean install, help/version tests |
| 2. Parser/models | Not started | Parser fixture tests |
| 3. Streaming aggregation | Not started | Four metric families and coverage gate |
| 4. Rich text | Not started | TTY/output integration tests |
| 5. JSON/CSV | Not started | Schema golden tests |
| 6. Failures/cardinality | Not started | Exit codes `0/1/2/3/4` tested |
| 7. Performance | Not started | Documented 1 GB run < 30 s |
| 8. Release candidate | Not started | Package checks and current adjudication receipt |
| 9. Gzip (P1) | Deferred | Only after MVP gates pass |

## Current Next Action

When implementation is authorized, begin only Step 1 using the first prompt in `CLAUDE_CODE_GUIDE.md`. This blueprint session does not authorize product code.
