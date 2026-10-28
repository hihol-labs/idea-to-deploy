# Project Memory: nginx-stream-insights

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx access logs and reports top-10 IPs, top-10 4xx/5xx URLs, hourly request percentages, and unique User-Agent share. Default output is colored terminal text; JSON and CSV support pipelines. Budget is $0 and delivery is one weekend.

The durable specification is `PRD.md`; `PROJECT_ARCHITECTURE.md` owns interfaces; `IMPLEMENTATION_PLAN.md` owns execution order. Change the specification before changing behavior.

## Non-Negotiable Rules

- WIP=1: implement one numbered step at a time.
- No database, HTTP API, server, authentication, cloud, Kubernetes, or product code outside the approved plan.
- Preserve single-process streaming; never read a whole log into memory.
- Use Python 3.11, Click, Rich, dataclasses, src layout, and pip packaging.
- Hourly share is `100 × hourly_request_count / total_valid_requests`.
- Preserve exit codes `0/1/2/3/4`; code 4 is unique-cardinality exhaustion.
- Add tests with new code and run the relevant suite before any commit.
- Record observed failures honestly; documentation is not runtime evidence.
- Never expose secrets or send log data outside the machine.
- Publishing, pushing, PR creation, deployment, deletion, and other external/irreversible actions require explicit human approval.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Structure

```text
src/nginx_stream_insights/{cli,models,parser,aggregator}.py
src/nginx_stream_insights/renderers/{text,json,csv}.py
tests/{fixtures,unit,integration,performance}/
pyproject.toml
```

## Status

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| 1 | Package skeleton | Not started | — |
| 2 | nginx parser | Not started | — |
| 3 | Streaming aggregation | Not started | — |
| 4 | Terminal renderer | Not started | — |
| 5 | JSON/CSV renderers | Not started | — |
| 6 | CLI integration and exit codes | Not started | — |
| 7 | Quality/performance gate | Not started | — |
| 8 | Release candidate docs | Not started | — |

## Working Protocol

Before a step, read its section in `IMPLEMENTATION_PLAN.md` and the referenced architecture/PRD sections. After editing, run the exact step verification and record only grounded results in the table. Keep off-scope discoveries in a backlog instead of expanding the current diff. A final release candidate requires the full green suite, build/install smoke test, measured 1 GB benchmark, and human review.

