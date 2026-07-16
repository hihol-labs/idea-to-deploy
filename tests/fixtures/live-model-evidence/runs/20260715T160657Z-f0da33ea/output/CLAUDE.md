# Project Memory: Nginx Stream Analytics CLI

## Context

Build a pip-installable local Python 3.11 CLI for DevOps/SRE engineers. It streams standard nginx combined access logs and reports top-10 IPs, top-10 exact request targets with 4xx/5xx responses, 24 hourly request buckets, and exact distinct non-empty User-Agent count/share. Default output is Rich terminal text; JSON and CSV are stable pipeline formats.

The durable product specification is [PRD.md](PRD.md); [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is the technical source of truth; [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) defines delivery order and evidence.

## Non-negotiable Rules

- Python 3.11, Click, Rich, and dataclasses are the approved runtime stack.
- Use a single-process, line-by-line, stateless streaming pipeline.
- Do not add authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Never load the full input or retain all parsed records.
- Keep stdout exclusively in the selected output format; diagnostics use stderr.
- JSON/CSV changes require explicit schema compatibility review.
- Exact mode must never silently become approximate.
- Preserve deterministic count-descending/key-ascending rankings.
- Treat log content as untrusted data, including in Rich and CSV output.
- Preserve WIP=1 and attach actual verification evidence before changing a step status.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_stream_analytics/   CLI, models, parser, aggregation, renderers
tests/                        focused and integration tests, golden fixtures
benchmarks/                   deterministic generator and benchmark evidence
pyproject.toml                package and tool configuration
```

## Status

| Step | Scope | Status |
|---:|---|---|
| Blueprint | Six planning documents, project memory, gitignore | Complete when verification checklist passes |
| 1 | Package and CLI skeleton | Not started |
| 2 | Domain/output dataclasses | Not started |
| 3 | Combined-log streaming parser | Not started |
| 4 | Exact aggregation/rankings | Not started |
| 5 | JSON renderer | Not started |
| 6 | CSV renderer | Not started |
| 7 | Rich terminal and diagnostics | Not started |
| 8 | Performance and hardening | Not started |
| 9 | Release docs/package validation | Not started |

## Quality Gates

- Ruff, mypy, and pytest pass.
- Parser, aggregator, and renderers achieve at least 90% branch coverage.
- JSON and CSV golden outputs are deterministic.
- The recorded reference laptop processes the deterministic 1 GB fixture in under 30 seconds and under 250 MB peak RSS.
- A fresh Python 3.11 environment installs and runs the built wheel.

## Current Next Action

After blueprint acceptance, execute only Implementation Plan Step 1 under an active Idea to Deploy unit contract.
