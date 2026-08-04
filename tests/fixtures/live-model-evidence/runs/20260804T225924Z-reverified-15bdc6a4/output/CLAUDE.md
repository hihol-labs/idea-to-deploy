# Project Memory: Nginx Stream Insights

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined/common access logs and reports:

1. Top 10 client IPs.
2. Top 10 request targets among 4xx/5xx responses.
3. Hourly request distribution as `100 × hourly_request_count / total_valid_requests`.
4. Exact unique User-Agent share as a percentage of valid requests.

Default output is colored terminal text; `--json` and `--csv` support pipelines. The performance acceptance target is a fixed representative 1 GB log in under 30 seconds on a documented laptop. Budget is $0 and intended delivery is one weekend.

## Source of Truth

Read these before implementation:

1. `PRD.md` — observable requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — normative components, metrics, schemas, and CLI contract.
3. `IMPLEMENTATION_PLAN.md` — ordered WIP=1 steps and verification commands.
4. `STRATEGIC_PLAN.md` — priorities, KPIs, risks, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for each step.
6. `AGENTS.md`, `.itd/`, and `.itd-memory/` — methodology and current execution state.

When behavior changes, update the PRD/architecture first. Do not let implementation become the only specification.

## Non-Negotiable Architecture

Use **no database — stateless streaming processing; no HTTP API — CLI-only tool**. There is also no authentication, background server, cloud dependency, Docker, or Kubernetes. The one-process flow is input iterator → parser → accumulator → immutable report → selected renderer. Do not retain individual parsed requests.

The approved stack is Python 3.11, Click, Rich, and dataclasses, installed through pip using a `src/` package layout.

## User-Facing Contracts

- Valid records alone contribute to metrics and denominators; always expose valid/malformed totals.
- Hourly output contains all 24 hours and uses the 0–100 percentage formula exactly.
- Top rankings are deterministic: count descending, then key ascending.
- JSON and CSV represent the same report as terminal output; successful machine stdout contains no ANSI or diagnostics.
- Exact User-Agent cardinality is guarded. Never silently sample or approximate it.
- Exit codes are immutable: `0` success, `1` operational I/O failure, `2` usage/option error, `3` input-data failure/no valid requests, `4` unique-cardinality exhaustion. Never omit or remap `4`.

## Engineering Rules

- Preserve WIP=1: execute only one `IMPLEMENTATION_PLAN.md` step at a time.
- Before edits, update `.itd/SCOPE_LOCK.md` and reconcile the active unit in `.itd-memory/STATE.json` or `.itd-memory/GOAL.json`.
- Use typed domain exceptions and translate them once at the CLI boundary.
- Keep core models/parser/aggregation independent from Click and Rich.
- Treat log content as untrusted data; do not render it as Rich markup or echo rejected raw lines by default.
- Add tests for every user-visible error path, including all exit codes.
- Profile before optimizing and preserve semantics through performance changes.
- Exclude undeclared untracked/ignored overlays from verification; bind any necessary non-Git input explicitly.
- Freeze the exact staged candidate, run its machine oracle, and require the current risk-tier adjudication receipt before accepting completion.
- Do not publish packages, push changes, create releases, or tag without explicit authorization.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Expected Project Structure

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  cli.py
  models.py
  parser.py
  io.py
  aggregate.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  renderers/
benchmarks/
  generate_log.py
  run.sh
scripts/
  smoke-dist.sh
```

This structure is a future target, not authorization to create product code during blueprint work.

## Implementation Status

| Step | Scope | Status | Acceptance evidence |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete | Document-only validation; no product code |
| 1 | Package skeleton and quality baseline | Not started | Install/help/lint/type/test commands in plan |
| 2 | Models and golden contracts | Not started | Focused model/contract tests |
| 3 | Parser and input boundary | Not started | Parser/I/O tests and branch coverage |
| 4 | Aggregation and metric safety | Not started | Aggregation tests and branch coverage |
| 5 | Terminal renderer | Not started | Renderer tests and no-color smoke command |
| 6 | JSON/CSV renderers | Not started | Schema and equivalence tests |
| 7 | Complete CLI and exit codes | Not started | CLI tests covering `0/1/2/3/4` |
| 8 | Performance and robustness | Not started | 1 GB median/runtime/RSS evidence |
| 9 | Packaging and release candidate | Not started | Build, clean install, full oracle, adjudication receipt |

## Current Handoff

Blueprint planning is the only completed unit. The next authorized implementation action, when explicitly requested, is Step 1 from `IMPLEMENTATION_PLAN.md`. No product source code exists as part of this blueprint.
