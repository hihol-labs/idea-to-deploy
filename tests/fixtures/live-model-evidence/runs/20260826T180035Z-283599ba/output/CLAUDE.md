# Project Instructions: Nginx Stream Analytics CLI

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx access logs and reports top client IPs, top error URLs, hourly request percentages, and exact unique User-Agent share. The default is colored terminal text; JSON and CSV support pipelines. Planning sources are `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md`.

## Non-Negotiable Rules

- Do not add authentication, a database, an HTTP API, a server, cloud integration, Docker/Kubernetes, or runtime persistence.
- Maintain a single-process, one-pass streaming design and the target of 1 GB under 30 seconds on the reference laptop.
- Use Python 3.11, Click, Rich, dataclasses, and pip packaging.
- Treat the specification as source: change the documents before intentionally changing behavior.
- Preserve deterministic rankings and machine-readable schemas.
- Use `100 × hourly_request_count / total_valid_requests` for hourly percentage.
- Preserve exit codes `0/1/2/3/4`: success, I/O failure, usage error, no valid records, and unique-cardinality exhaustion.
- Do not claim a step complete without running its named verification.
- At the end of every session or meaningful block of work, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Intended Structure

```text
src/nginx_stream_report/{cli,errors,models,parser,aggregate,render_text,render_json,render_csv}.py
tests/{test_cli,test_parser,test_aggregate,test_renderers,test_performance}.py
```

## Work Sequence and Status

Only one row may be in progress.

| Step | Outcome | Status |
|---:|---|---|
| 1 | Package skeleton and CLI contract | Not started |
| 2 | Streaming nginx parser | Not started |
| 3 | Top IP and error-URL aggregations | Not started |
| 4 | Hourly and unique User-Agent metrics | Not started |
| 5 | Rich terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | Complete error and exit-code behavior | Not started |
| 8 | Performance and memory evidence | Not started |
| 9 | Packaging and release documentation | Not started |

## Definition of Done

A step is done only when its changes are scoped, its listed tests have run successfully, its acceptance evidence is recorded, and all documents still agree. Product completion additionally requires the measured performance target and a clean wheel installation on Python 3.11.

