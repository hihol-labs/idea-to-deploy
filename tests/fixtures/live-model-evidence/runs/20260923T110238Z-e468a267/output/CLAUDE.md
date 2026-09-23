# Project Memory: nginx-stream-insights

## Context

This repository is currently documentation-only. The planned product is a local Python 3.11 CLI for DevOps/SRE users that streams nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx count, 24 hourly request percentages, and unique User-Agent share. Default output is colored terminal text; JSON and CSV are pipeline contracts.

Read in this order before implementation:

1. `PRD.md` — behavior, priorities, acceptance criteria, and exclusions.
2. `PROJECT_ARCHITECTURE.md` — selected architecture, data/output schemas, and CLI contract.
3. `IMPLEMENTATION_PLAN.md` — eight bounded steps and verification commands.
4. `CLAUDE_CODE_GUIDE.md` — ready-to-run prompts and release checklist.
5. `STRATEGIC_PLAN.md` — product rationale, roadmap, KPIs, risks, and Definition of Done.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, a `src/` layout, and pip packaging.
- Preserve a single-process, stateless, streaming design.
- Add no authentication, database, HTTP API, server, cloud service, network call, Docker/Kubernetes asset, telemetry, or persistence.
- Use `100 × hourly_request_count / total_valid_requests` for every hourly percentage.
- Preserve exact exit meanings: `0` success; `1` unexpected runtime/output failure; `2` usage/configuration error; `3` input/read/decode/gzip failure or zero valid records; `4` unique-cardinality exhaustion.
- Keep diagnostics on stderr and emit no partial stdout on fatal failure.
- Treat log fields as untrusted data; never interpret them as terminal markup, formulas, code, or shell input.
- Change specifications and acceptance tests before intentionally changing behavior.
- Preserve WIP=1: finish and verify one implementation-plan step before starting another.
- At the end of every session or significant block of work, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  aggregate.py
  cli.py
  errors.py
  input.py
  models.py
  parser.py
  renderers.py
tests/
  fixtures/
  snapshots/
  test_aggregate.py
  test_cardinality.py
  test_cli_contract.py
  test_csv_output.py
  test_end_to_end.py
  test_input.py
  test_json_output.py
  test_parser.py
  test_terminal_output.py
benchmarks/
  generate_log.py
  run.py
```

This tree is a plan, not evidence that code exists.

## Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI contracts | Not started | install, help, CLI contract tests |
| 2 | Streaming input and parser | Not started | input/parser tests and parse smoke check |
| 3 | Core aggregation | Not started | aggregation tests including hourly formula |
| 4 | User-Agent guard and exit codes | Not started | cardinality and `0/1/2/3/4` subprocess tests |
| 5 | Terminal renderer | Not started | snapshots and manual no-color smoke output |
| 6 | JSON and CSV | Not started | parse-based machine-output tests |
| 7 | Robust input and gzip | Not started | end-to-end failure/input tests |
| 8 | Performance and packaging | Not started | full gates, clean-wheel smoke, recorded 1 GB benchmark |

Update this table only from actual evidence. Do not claim an external, independent, or adversarial review unless its artifact was produced by the named reviewer in its own run.

## Current Next Action

Begin Step 1 using Prompt 1 in `CLAUDE_CODE_GUIDE.md`. Do not implement product code during the blueprint phase.
