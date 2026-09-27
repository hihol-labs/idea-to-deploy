# Project Memory: Nginx Stream Analyzer

## Context

This repository is planned as a local Python 3.11 CLI for DevOps/SRE nginx access-log triage. It streams a file or stdin once and reports top-10 IPs, top-10 URLs by 4xx/5xx count, hourly request percentages, and exact unique User-Agent share. Default output is colored terminal text; JSON and CSV serve pipelines.

## Source of Truth

1. `PRD.md` defines user-visible behavior and acceptance.
2. `PROJECT_ARCHITECTURE.md` defines data, CLI, output, and exit contracts.
3. `IMPLEMENTATION_PLAN.md` defines the dependency-ordered work and verification.
4. `STRATEGIC_PLAN.md` defines scope, priorities, performance, and release gates.
5. `CLAUDE_CODE_GUIDE.md` supplies bounded implementation prompts.

When behavior changes, update the specifications before implementation. Do not scatter project instructions into additional agent-memory files.

## Non-Negotiable Rules

- Python 3.11, Click, Rich, and dataclasses; install through pip.
- Single local process; no authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Stateless, one-pass processing; never retain raw lines or request records.
- Target 1 GB in under 30 seconds on a documented laptop; claim it only with measured evidence.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Exit codes are 0 success, 1 operational failure, 2 usage error, 3 malformed input, and 4 unique-cardinality exhaustion.
- JSON and CSV are stable, ANSI-free contracts. Diagnostics use stderr.
- Treat all log-derived content as untrusted plain data.
- Keep WIP=1 and finish verification for the active implementation step before moving on.
- Do not claim an external, adversarial, or independent review unless it actually ran in a separate review session.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Structure

```text
src/nginx_stream_analyzer/{cli,models,parser,aggregate,inputs}.py
src/nginx_stream_analyzer/outputs/{terminal,json_output,csv_output}.py
tests/fixtures/
tests/test_{parser,aggregate,inputs,outputs,cli,exit_codes,end_to_end,performance}.py
scripts/generate_benchmark_log.py
pyproject.toml
```

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Editable install + CLI tests |
| 2 | Parser and models | Not started | Parser fixtures, tests, coverage |
| 3 | Streaming input/error policy | Not started | File/stdin/error tests |
| 4 | IP/error/hour aggregation | Not started | Known-answer aggregation tests |
| 5 | User-Agent guard | Not started | Boundary tests and exit 4 proof |
| 6 | Terminal/JSON/CSV output | Not started | Schema, ANSI, stream tests |
| 7 | End-to-end/performance | Not started | Full suite + timed 1 GB run |
| 8 | Packaging/release docs | Not started | Build + clean-wheel smoke test |

## Current Next Action

Begin only `IMPLEMENTATION_PLAN.md` Step 1 when implementation is explicitly authorized. This blueprint session does not authorize product code.

