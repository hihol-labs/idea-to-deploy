# Project Memory: Nginx Stream Insights

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx access logs and reports top-10 IPs, top-10 4xx/5xx URLs, hourly distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV are pipeline-safe alternatives. Budget is $0 and delivery is one weekend.

## Binding rules

- `PRD.md` and its acceptance criteria are the behavioral source of truth.
- Follow `PROJECT_ARCHITECTURE.md`: one local process, sequential streaming, exact aggregates, no raw-record retention.
- Do not add authentication, a database, an HTTP API, a server, cloud resources, Docker, or Kubernetes.
- Stack: Python 3.11, Click, Rich, dataclasses, pip-standard packaging.
- Keep WIP=1 and update `.itd-memory/STATE.json` before changing units or scope.
- Attach the evidence required by `.itd/VERIFICATION_CONTRACT.json`; narration alone is not completion.
- Preserve stdout for selected report data and stderr for diagnostics.
- Update the specification before intentionally changing product behavior.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned structure

`src/nginx_stream_insights/` contains CLI, input, parser, models, aggregation, and three renderers. `tests/` contains unit/integration tests and golden fixtures. `benchmarks/` contains a generator, instructions, and recorded results, but not generated 1 GB logs.

## Status

| Step | Name | Status |
|---:|---|---|
| 0 | Full blueprint | Complete |
| 1 | Package skeleton | Not started |
| 2 | Models and golden contracts | Not started |
| 3 | Parser and input | Not started |
| 4 | Streaming aggregation | Not started |
| 5 | Terminal renderer | Not started |
| 6 | JSON renderer | Not started |
| 7 | CSV renderer | Not started |
| 8 | Golden-flow integration | Not started |
| 9 | Packaging and performance | Not started |

## Next action

Begin Step 1 only when explicitly requested. The validated blueprint is complete; keep the repository planning-only until then.
