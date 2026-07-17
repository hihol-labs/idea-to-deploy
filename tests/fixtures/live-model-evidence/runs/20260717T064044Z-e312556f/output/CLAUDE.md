# Nginx Stream Report Project Memory

## Context

Build a local pip-installable Python 3.11 CLI for DevOps/SRE engineers that streams standard nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly request distribution, and exact unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` serve pipelines. The performance release gate is 1 GiB in under 30 seconds on a documented laptop.

## Non-negotiable rules

- Read `AGENTS.md`, applicable repository-local Idea to Deploy skills, `.itd/` contracts, and `.itd-memory/` state before work.
- Preserve WIP=1 and execute `IMPLEMENTATION_PLAN.md` in dependency order.
- No authentication, database, persistence, HTTP API, server, cloud, Docker, or Kubernetes.
- Use Python 3.11, Click, Rich, dataclasses, standard-library aggregation, and pip packaging.
- Stream input; never retain the raw log or read it wholly into memory.
- stdout contains reports; stderr contains diagnostics; JSON/CSV never contain ANSI or progress text.
- Treat log contents as untrusted and sensitive; make no network or telemetry calls.
- Change `PRD.md` acceptance criteria before changing intended behavior.
- Do not mark work Done from narration; attach the evidence required by `.itd/VERIFICATION_CONTRACT.json` and the active task contract.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Source-of-truth order

1. `AGENTS.md` and `.itd/` project/verification contracts.
2. `.itd-memory/` active state and unit contract.
3. `PRD.md` behavior and acceptance criteria.
4. `PROJECT_ARCHITECTURE.md` technical decisions and public interfaces.
5. `IMPLEMENTATION_PLAN.md` sequencing and commands.
6. `STRATEGIC_PLAN.md` priorities and product boundaries.

## Planned package structure

```text
src/nginx_stream_report/
  cli.py
  models.py
  parser.py
  stats.py
  formatters/{terminal,json_output,csv_output}.py
tests/{fixtures,test_parser.py,test_stats.py,test_cli.py,test_performance.py}
```

## Step status

| Step | Name | Status | Completion evidence |
|---:|---|---|---|
| 1 | packaging and public contracts | Not started | plan commands not run |
| 2 | fixtures and benchmark harness | Not started | plan commands not run |
| 3 | combined-log parser | Not started | plan commands not run |
| 4 | streaming aggregation | Not started | plan commands not run |
| 5 | file/stdin pipeline | Not started | plan commands not run |
| 6 | Rich terminal output | Not started | plan commands not run |
| 7 | JSON and CSV output | Not started | plan commands not run |
| 8 | hardening and quality | Not started | plan commands not run |
| 9 | 1 GiB performance proof | Not started | plan commands not run |
| 10 | package/release candidate | Not started | plan commands not run |

## Current handoff

Blueprint documentation is the only completed scope. Product implementation has not begun. The next action is to create and verify the Step 1 task/unit contract, then execute only Step 1 from `IMPLEMENTATION_PLAN.md`.

