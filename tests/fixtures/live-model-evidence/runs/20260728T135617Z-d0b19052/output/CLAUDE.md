# Project Memory: nginx-log-top

## Context

This repository is the planning baseline for a local Python 3.11 CLI that streams nginx combined access logs and reports top client IPs, top 4xx/5xx URLs, hourly request distribution, and exact unique User-Agent share. Default output is a colored Rich terminal report; JSON and CSV are stable pipeline interfaces.

The cash budget is $0 and delivery is one weekend. Product code has not been implemented. Specifications are durable source; when behavior changes, update `PRD.md` and architecture before code.

## Non-Negotiable Decisions

- Use Python 3.11, Click, Rich, dataclasses, standard-library aggregation, and pip packaging.
- Use one stateless single-process streaming pipeline.
- No database, HTTP API, authentication, server, cloud, Docker requirement, or Kubernetes.
- Do not retain raw events; exact counters may retain distinct keys within the documented supported envelope.
- Preserve `HourBucket(local_date, hour, offset_minutes)` identity.
- Enforce a 1 MiB physical-line limit and neutralize terminal control/markup injection.
- Keep terminal, JSON, and CSV stdout deterministic; send diagnostics only to stderr.
- Do not silently approximate exact metrics.
- Do not claim the 1 GiB/30-second and 1.5 GiB RSS acceptance gate without BR-1 evidence.

## Source-of-Truth Order

1. `AGENTS.md` and applicable `.itd/` contracts if adopted later.
2. `PRD.md` for behavior and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` for technical decisions and external interfaces.
4. `IMPLEMENTATION_PLAN.md` for step order and verification.
5. `STRATEGIC_PLAN.md` for scope, priority, risks, and Definition of Done.
6. `CLAUDE_CODE_GUIDE.md` for execution prompts.

Resolve contradictions by updating the higher-priority source and reconciling all dependent documents.

## Planned Structure

```text
pyproject.toml
src/nginx_log_top/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  renderers.py
  errors.py
tests/
  fixtures/
  benchmark-manifest.json
  test_cli.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_performance.py
docs/
  PERFORMANCE.md
```

## Engineering Rules

- Preserve WIP=1: complete and verify one implementation step before starting another.
- Inspect the working tree first and preserve unrelated user changes.
- Use synthetic, non-sensitive log fixtures; never commit production logs or benchmark blobs.
- Machine schemas and exit codes are public compatibility contracts.
- Avoid adding dependencies until profiling or a requirement proves the need.
- Record exact commands and results; narration alone does not complete a step.
- No external publishing, package upload, or release without explicit authorization.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Status

| Step | State | Required evidence | Recorded evidence |
|---:|---|---|---|
| Blueprint documents | Done | required files and contract checks | static validation recorded at blueprint handoff |
| 1. Package/CLI contracts | Not started | install, help, CLI tests | none |
| 2. Typed parser | Not started | parser tests, compileall | none |
| 3. Streaming aggregation | Not started | aggregation tests, coverage | none |
| 4. JSON/CSV | Not started | renderer/CLI tests, JSON validation | none |
| 5. Rich terminal | Not started | TTY/no-color/security tests | none |
| 6. Input/error lifecycle | Not started | integration and exit-code tests | none |
| 7. Quality/performance | Not started | ≥90% coverage, BR-1 benchmark/RSS | none |
| 8. Package/handoff | Not started | build, metadata, clean install, full suite | none |

## Current WIP and Next Action

- **Active implementation unit:** none; blueprint planning is complete.
- **Next action:** begin `IMPLEMENTATION_PLAN.md` Step 1 only when implementation is authorized.
- **Known risk gate:** BR-1 hardware must be available before final performance acceptance; other hardware produces secondary evidence only.

## Session Handoff Checklist

- [ ] Update the status table with only command-backed state.
- [ ] Record test, coverage, benchmark, and review results or mark them unverified.
- [ ] Reconcile changed behavior across PRD, architecture, plan, README, and CLI help.
- [ ] State the exact next action and any blocker.
- [ ] Run `/session-save`.
