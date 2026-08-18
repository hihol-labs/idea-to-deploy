# nginx-logtop Project Memory

## Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly request distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV support pipelines. The cash budget is $0 and delivery is one weekend.

The blueprint phase is complete when the six required planning files exist. Product implementation has not started. The external harness owns the separate Devil's Advocate review; do not simulate or claim it here.

## Source of Truth

Read in this order:

1. `.itd/` contracts and `.itd-memory/` active state, when populated.
2. `PRD.md` for user-visible behavior and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` for calculations, CLI, schemas, components, and decisions.
4. `IMPLEMENTATION_PLAN.md` for WIP=1 step order and verification commands.
5. `CLAUDE_CODE_GUIDE.md` for bounded implementation prompts.
6. `STRATEGIC_PLAN.md` for scope, priorities, risks, and success measures.

If documents conflict, preserve explicit user constraints, then update the specification before product code. Never silently reinterpret a metric or output schema.

## Non-Negotiable Rules

- Planning and implementation are separate. The blueprint session writes documentation only.
- Use Python 3.11, Click, Rich, dataclasses, a source-layout pip package, and a single synchronous process.
- Keep **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- Do not add authentication, server, cloud, Docker, Kubernetes, telemetry, or network egress.
- Do not retain parsed requests; only aggregate state and the bounded exact User-Agent set may grow.
- Define hourly percentages with `100 × hourly_request_count / total_valid_requests`.
- Preserve exact rankings, lexical tie-breaks, and machine schemas from `PROJECT_ARCHITECTURE.md`.
- Preserve the complete exit-code contract: `0` success, `1` unexpected internal error, `2` CLI usage error, `3` input/data error, `4` unique-cardinality exhaustion.
- Code `4` must never be omitted, remapped, or replaced by an approximate success.
- Keep WIP=1. Complete and verify one implementation step before starting another.
- Use the Idea to Deploy Verification Loop: freeze the exact candidate, run the machine oracle, apply the risk-tier checker, and require a current revalidated adjudication receipt when mandated.
- Do not mark completion from narration alone. Record tests, reconcile state, and leave one explicit next action.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Repository Structure

```text
src/nginx_logtop/
  __init__.py
  __main__.py
  aggregate.py
  cli.py
  errors.py
  inputs.py
  models.py
  parser.py
  render_csv.py
  render_json.py
  render_terminal.py
tests/
  fixtures/
  test_aggregate.py
  test_cli_contract.py
  test_e2e.py
  test_inputs.py
  test_parser.py
  test_render_csv.py
  test_render_json.py
  test_render_terminal.py
benchmarks/
  README.md
  generate_fixture.py
  run.py
pyproject.toml
```

This tree is planned, not currently implemented.

## Status

| Step | Scope | Status | Required proof |
|---:|---|---|---|
| Blueprint | Six required project documents | Complete | Root-file presence and structural checks |
| 1 | Packaging and quality gates | Not started | Build/install/help commands |
| 2 | CLI, errors, and models | Not started | CLI contract tests; exit map `0/1/2/3/4` |
| 3 | Inputs and parser | Not started | Parser/input tests and lint |
| 4 | Streaming aggregates | Not started | Aggregate tests and coverage |
| 5 | Terminal renderer | Not started | Golden and injection tests |
| 6 | JSON and CSV renderers | Not started | Schema and semantic-equivalence tests |
| 7 | End-to-end contract | Not started | Full exit and coverage tests |
| 8 | Performance | Not started | Recorded 1 GB under-30-second benchmark |
| 9 | Release readiness | Not started | Lint, tests, build, artifact check, clean install |

## Current Next Action

Run the external Devil's Advocate architecture review in its separate fresh session. After any accepted specification corrections are incorporated, start only Step 1 from `IMPLEMENTATION_PLAN.md`.
