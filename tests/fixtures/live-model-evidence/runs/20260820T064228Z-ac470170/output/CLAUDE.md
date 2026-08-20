# Nginx Stream Insights Project Instructions

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE users that streams
standard nginx combined access logs. It reports top 10 IPs, top 10 normalized
URLs by 4xx/5xx count, a 24-hour percentage distribution, and exact unique
User-Agent share. Default output is Rich terminal text; JSON and CSV support
pipelines. The performance acceptance target is 1 GB in under 30 seconds on a
documented laptop.

The specifications are `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`,
`PRD.md`, and `IMPLEMENTATION_PLAN.md`. `CLAUDE_CODE_GUIDE.md` supplies the
step prompts. When behavior changes, update the specification and acceptance
criteria before implementation.

## Non-Negotiable Architecture

- Python 3.11, Click, Rich, dataclasses, pip-installable `src/` package.
- One local process and one streaming pass; no persistence across runs.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- No network calls or telemetry; log data remains local.
- Exact User-Agent tracking has a hard configured ceiling and fails honestly.
- Hourly percentages use
  `100 × hourly_request_count / total_valid_requests`.

## Public CLI Contract

- `0` — successful report, help, or version.
- `1` — input/output or unexpected runtime error.
- `2` — invalid command usage or options.
- `3` — input contains zero valid records.
- `4` — unique-cardinality exhaustion; emit no partial report.

Rich text is the default. `--json` and `--csv` are mutually exclusive, stable,
and color-free. stdout carries report data; stderr carries diagnostics.
Rankings use count descending then key ascending.

## Planned Repository Structure

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  __main__.py
  cli.py
  errors.py
  io.py
  parser.py
  models.py
  aggregator.py
  report.py
  renderers/
    __init__.py
    rich_text.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  golden/
benchmarks/
```

These paths are planned, not present until their implementation step begins.
Do not create product code during blueprint work.

## Engineering Rules

1. Read `AGENTS.md`, `.itd/` contracts, `.itd-memory/` state, and the active
   plan step before editing.
2. Preserve WIP=1. Change only files allowed by the active scope lock.
3. Treat all log content as untrusted: bound it, escape terminal content, and
   use standard JSON/CSV encoders.
4. Keep parser/aggregation/report logic independent of Click and Rich.
5. Never load the whole log or retain complete records; measure before adding
   concurrency or optimization complexity.
6. Add executable tests for every P0 acceptance criterion and every public exit
   code. Do not predict test results.
7. Use the repository Verification Loop: exact candidate, machine oracle, risk
   checker, and a current matching adjudication receipt.
8. Do not create `DEVILS_ADVOCATE_REVIEW.md` in implementation sessions unless
   the external review workflow explicitly owns that task.
9. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Implementation Status

| Step | Scope | Status | Required evidence before completion |
|---:|---|---|---|
| 1 | Package and CLI contract | Planned | Install/help and CLI contract tests |
| 2 | Models and parser | Planned | Parser fixture suite and compile check |
| 3 | Streaming aggregation | Planned | I/O, aggregation, and code-4 tests |
| 4 | Report model | Planned | Ranking and percentage tests |
| 5 | Rich text | Planned | Capture, escaping, and ANSI tests |
| 6 | JSON/CSV | Planned | Golden structured-output tests |
| 7 | End-to-end | Planned | Exit matrix and coverage gate |
| 8 | Performance/release | Planned | Wheel smoke test and documented benchmark |

Current phase: blueprint complete; product implementation has not started.
Next authorized implementation action, when requested: Step 1 only.

## Session Handoff

At the end of a work block, record commands actually run, evidence locations,
unresolved failures, active scope, and the single next action. A narrative
“passed” is not completion evidence. Do not claim an adversarial or independent
review unless its separate session and artifact actually exist.

