# Project Memory: Nginx Stream Analyzer

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx access logs and reports top 10 IPs, top 10 URLs producing 4xx/5xx errors, hourly request distribution, and unique User-Agent share. Default output is colored Rich terminal text; `--json` and `--csv` serve pipelines. The product is pip-installable, costs $0 to operate, and targets a one-weekend MVP with a documented 1 GB-under-30-seconds laptop benchmark.

Specifications are the durable source of truth:

1. `PRD.md` — behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — architecture, CLI, schemas, and boundaries.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 implementation sequence and checks.
4. `STRATEGIC_PLAN.md` — priorities, risks, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` — step-specific implementation prompts.

## Non-negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
- Preserve **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- Do not introduce authentication, a server, cloud services, Docker/Kubernetes, or persistent state.
- Keep one single-process streaming pass and do not buffer the entire input.
- Use only valid requests in metric denominators.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`, never an unscaled fraction.
- Keep terminal, JSON, and CSV semantics equivalent; diagnostics go to stderr and structured stdout contains no ANSI escapes.
- Preserve deterministic top-10 ordering: count descending, key ascending.
- Escape/encode all untrusted log values for the destination renderer.
- Preserve the complete exit-code contract: `0` success, `1` input/runtime failure, `2` usage error, `3` non-empty input with no valid records, `4` unique-cardinality exhaustion.
- Code `4` specifically means the exact distinct User-Agent set would exceed its configured safety limit; do not remap or omit it and do not emit a partial report.
- Work on one implementation-plan step at a time. Change the spec before changing approved behavior.
- Never claim tests, review, benchmark, or completion without current evidence.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Repository Structure

```text
src/nginx_stream_analyzer/
  __init__.py
  cli.py
  errors.py
  models.py
  input.py
  parser.py
  aggregate.py
  service.py
  renderers/{terminal,json,csv}.py
tests/
  fixtures/
  perf/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
pyproject.toml
```

This is a planned structure only; the blueprint session must not create product code.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package skeleton and contracts | Not started | Editable install, help/version, CLI tests |
| 2 | Streaming input and parser | Not started | Parser edge-case tests and coverage |
| 3 | One-pass aggregation | Not started | Metric/cardinality boundary tests |
| 4 | Rich terminal renderer | Not started | Terminal golden tests |
| 5 | JSON renderer | Not started | JSON golden/schema validation |
| 6 | CSV renderer | Not started | CSV golden/round-trip validation |
| 7 | Exit contracts and integration | Not started | Tests for exits 0/1/2/3/4 |
| 8 | Performance and release | Not started | Full suite, package install, 1 GB benchmark |

## Current State

Planning documents are complete; implementation has not started. The next authorized action is Step 1 of `IMPLEMENTATION_PLAN.md` in a separate implementation session.
