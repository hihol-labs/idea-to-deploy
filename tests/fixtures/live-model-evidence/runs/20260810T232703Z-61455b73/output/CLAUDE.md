# nginx-insights Project Memory

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams one nginx Common or Combined access log from a path or stdin. It reports top-10 IPs, top-10 normalized URL paths with 4xx/5xx responses, all 24 hourly request percentages, and exact unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` are pipeline contracts. Target: a documented 1 GB log in under 30 seconds on a laptop. Budget: $0. Delivery: one weekend.

## Source of Truth

1. `PRD.md` owns user-facing requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` owns technical, CLI, schema, algorithm, and exit-code decisions.
3. `IMPLEMENTATION_PLAN.md` owns dependency order and verification commands.
4. `STRATEGIC_PLAN.md` owns scope, priorities, risks, and release criteria.
5. `CLAUDE_CODE_GUIDE.md` supplies bounded prompts but never overrides the specifications.

Change the specification before changing behavior. Preserve WIP=1 and finish one implementation step with evidence before opening the next.

## Non-Negotiable Rules

- Single local process and one streaming pass; never read the complete log into memory.
- **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- No authentication, server, network calls, telemetry, cloud, Docker, Kubernetes, or retained user data.
- Use Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- Default Rich output is TTY-aware; JSON/CSV are deterministic and ANSI-free.
- Normalize request targets by removing query strings/fragments; count only 400–599 as error URLs.
- Rank by count descending, then key ascending.
- Hourly distribution uses `100 × hourly_request_count / total_valid_requests`, includes all 24 hours, and excludes malformed lines from the denominator.
- User-Agent share uses distinct non-empty values over total valid requests. Stop before exceeding the configured exact-cardinality ceiling.
- Preserve the complete exit contract everywhere: `0` success/help/version, `1` runtime or I/O failure, `2` usage/configuration error, `3` zero valid records, `4` unique-cardinality exhaustion with no partial report.
- Do not silently approximate, broaden nginx formats, or add architecture to rescue performance; profile and update specs first.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Structure

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  __main__.py
  aggregate.py
  cli.py
  errors.py
  models.py
  parser.py
  render/
    __init__.py
    csv.py
    json.py
    text.py
tests/
  fixtures/
  golden/
  perf/
  test_aggregate.py
  test_cli.py
  test_exit_codes.py
  test_parser.py
  test_render_machine.py
  test_render_text.py
```

## Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete | Required documents present and validated |
| 1 | Package and quality skeleton | Not started | Clean install, help, pytest |
| 2 | Domain and failure contracts | Not started | Exit matrix tests, mypy |
| 3 | Streaming parser | Not started | Parser fixtures/tests, Ruff |
| 4 | One-pass aggregation | Not started | Aggregation tests, coverage |
| 5 | Rich renderer | Not started | Golden, TTY, injection tests |
| 6 | JSON/CSV renderers | Not started | Machine golden/schema tests |
| 7 | CLI integration | Not started | End-to-end and `0/1/2/3/4` tests |
| 8 | Performance and release | Not started | Full gates, benchmark, clean wheel install |

## Working Protocol

Before editing, read the active plan step and its linked architecture/PRD sections. Keep changes inside the scope lock. Add or update tests with behavior. Run the exact verification commands and record actual outcomes; a narrated `PASSED` is not evidence. Do not mark a step complete until the repository's current verification/adjudication requirements are satisfied. Leave the worktree handoff-ready with current status and one explicit next action.

**Next action:** Implement Step 1 only when implementation is separately authorized.
