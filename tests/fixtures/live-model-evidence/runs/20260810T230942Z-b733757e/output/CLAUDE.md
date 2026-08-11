# Project Memory: nginx-stream-stats

## Context

Build an open-source local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top-10 IPs, top-10 URLs by combined 4xx/5xx count, 24 hourly request percentages, and unique User-Agent share. Default output is colored terminal text, with JSON and CSV for pipelines. Target: exactly 1 GB in under 30 seconds on documented laptop hardware. Delivery: one weekend, $0 cash budget.

This file is agent guidance, not a substitute for specifications:

1. [PRD.md](PRD.md) — user-visible requirements and acceptance.
2. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) — technical and CLI source of truth.
3. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — eight-step delivery sequence.
4. [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) — bounded implementation prompts.

## Hard Rules

- Use Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
- Keep one synchronous local process. Add no authentication, database, HTTP API, server, cloud runtime, or Kubernetes.
- Process input incrementally; never retain raw log lines or echo them in diagnostics.
- Support nginx combined format only in MVP. Reject/count unsupported lines; never guess a custom format.
- Use `100 × hourly_request_count / total_valid_requests` for every hourly bucket.
- Define unique User-Agent share as `100 × distinct_non_missing_user_agents / total_valid_requests`; `-` is missing.
- Sort ranked output by count descending and key ascending on ties; return at most 10.
- Keep stdout exclusively for the chosen report and stderr for diagnostics/errors.
- Preserve the complete exit contract everywhere: `0` success, `1` input/runtime failure, `2` usage error, `3` zero valid records, `4` unique-cardinality exhaustion. Never omit or remap code `4`.
- Treat PRD and architecture as spec-as-source. Change the specification before intentionally changing behavior.
- Do not publish packages, push branches, deploy, or tag releases without explicit authorization.
- Work in one implementation step at a time and run its stated verification before advancing.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Structure

```text
pyproject.toml
src/nginx_stream_stats/
  __init__.py
  cli.py
  models.py
  parser.py
  analyzer.py
  errors.py
  renderers/{__init__,text,json,csv}.py
tests/
  fixtures/
  test_models.py
  test_errors.py
  test_parser.py
  test_analyzer.py
  test_renderers.py
  test_cli.py
  test_performance.py
docs/PERFORMANCE.md
```

## Status

Blueprint status is complete; product implementation has not started.

| Step | Name | Status | Required evidence |
|---:|---|---|---|
| 1 | Package skeleton and contracts | Not started | Install, model/error tests, help smoke |
| 2 | Combined-format parser | Not started | Parser tests and lazy/malformed cases |
| 3 | Metrics and cardinality | Not started | Analyzer golden and exhaustion tests |
| 4 | JSON/CSV renderers | Not started | Parse/round-trip/no-ANSI tests |
| 5 | Rich terminal renderer | Not started | Text/color/sanitization tests |
| 6 | Click integration | Not started | CLI tests exercising `0/1/2/3/4` |
| 7 | Performance gate | Not started | Documented exact 1 GB time and peak RSS |
| 8 | Release readiness | Not started | Full suite, build/check, clean wheel smoke |

## Session Handoff

Before ending a work block, record the active step, changed files, commands actually run, pass/fail evidence, unverified checks, blockers, and the exact next action. A prose “done” is not evidence. Never mark a failed or unrun gate as passed.
