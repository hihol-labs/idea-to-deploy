# Nginx Log Lens Project Memory

## Mission

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx
combined access logs and reports top-10 IPs, top-10 4xx/5xx URLs, 24 hourly
request buckets, and the share of unique User-Agents. Default output is Rich
terminal text; JSON and CSV are stable pipeline interfaces.

Planning is complete when the blueprint documents are accepted. Product code
must follow `IMPLEMENTATION_PLAN.md` one verified step at a time.

## Source of Truth

Read in this order:

1. `AGENTS.md` and `.itd/` contracts for process.
2. `PRD.md` for behavior and acceptance.
3. `PROJECT_ARCHITECTURE.md` for public interfaces and technical decisions.
4. `IMPLEMENTATION_PLAN.md` for the active delivery step.
5. `STRATEGIC_PLAN.md` for priority and product trade-offs.
6. `CLAUDE_CODE_GUIDE.md` for bounded execution prompts.

If documents disagree, stop and reconcile the specification before code.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses; pip-installable.
- One local process; stream file/stdin once.
- Exact metrics with deterministic ordering.
- Default Rich text, plus versioned JSON and normalized CSV.
- stdout remains data-only in machine modes; diagnostics use stderr.
- Target 1 GB under 30 seconds is accepted only with documented benchmark
  evidence on the named reference laptop.
- No database, persistence, HTTP API, daemon, server, authentication,
  telemetry, cloud, or Kubernetes.
- Budget is $0 and MVP delivery is one weekend.

## Intended Structure

```text
src/nginx_log_lens/
  __init__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
benchmarks/
```

This tree is a plan, not evidence that files exist.

## Engineering Rules

- Preserve WIP=1 and keep `.itd/SCOPE_LOCK.md` aligned with the active unit.
- Treat log lines as untrusted data; never evaluate them or pass them to a
  shell, and escape terminal-derived values.
- Never load the complete input or render inside the hot parsing loop.
- Keep domain modules independent of Click and Rich.
- Add a focused failing test before correcting a defect.
- Do not weaken exactness, schemas, exit codes, or performance acceptance
  without changing the PRD/architecture first.
- Freeze the exact candidate and use the project’s Verification Loop and
  risk-tier checker before accepting implementation work.
- Do not commit generated 1 GB benchmark fixtures.
- В конце каждой сессии или значимого блока работы — сохранить контекст через
  /session-save.

## Current Status

| Step | State | Required evidence |
|---:|---|---|
| Blueprint documents | Complete (2026-07-29) | Six required root files, exact headings/decision phrase, 8 stories, 9 plan steps, no placeholders |
| 1. Package/CLI contracts | Not started | Install, help, focused tests |
| 2. Models/errors | Not started | Model tests, compile |
| 3. Input/parser | Not started | Parser/input tests and timings |
| 4. Aggregation | Not started | Metric tests and coverage |
| 5. Rich renderer | Not started | Golden text tests |
| 6. JSON/CSV | Not started | Golden machine-format tests |
| 7. CLI integration | Not started | End-to-end matrix |
| 8. Performance | Not started | 1 GB benchmark and peak RSS |
| 9. Release readiness | Not started | Full suite, package checks, wheel smoke |

## Next Action

After blueprint approval, activate only STEP 1 from
`IMPLEMENTATION_PLAN.md`. Do not implement later steps or product code during
the blueprint workflow.
