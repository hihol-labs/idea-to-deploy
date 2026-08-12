# Project Memory: nginx-report

## Context

`nginx-report` is a planned local Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs and reports top 10 client IPs, top 10 4xx/5xx URLs, hourly request distribution, and exact unique User-Agent share. Default output is colored terminal text; `--json` and `--csv` are stable pipeline formats. The cash budget is $0 and the MVP delivery window is one weekend.

This repository currently contains the blueprint only. Product code must not be inferred as implemented from these documents.

## Source of Truth

Read in this order before implementation:

1. `PRD.md` — product behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — normative CLI, schemas, calculations, boundaries, and ADR.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered work and verification.
4. `CLAUDE_CODE_GUIDE.md` — ready-to-run prompts for each step.
5. `STRATEGIC_PLAN.md` — priorities, risk, budget, and success measures.

If documents conflict, stop and reconcile them. Architecture governs technical interfaces; PRD governs user-visible intent. Change the specification before changing behavior.

## Non-Negotiable Decisions

- Use Python 3.11, Click, Rich, and standard-library dataclasses; install through pip/pipx.
- Use one local process and stateless one-pass streaming. Never retain raw requests.
- No authentication, database, HTTP API, server, cloud, Kubernetes, telemetry, or network call.
- Default to safe Rich terminal text; JSON/CSV are ANSI-free and stable.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests` and are never unscaled fractions.
- User-Agent cardinality is exact within a configured ceiling. Never silently approximate.
- Preserve public exit codes: `0` success, `1` I/O failure, `2` usage/configuration error, `3` malformed log data, `4` unique-cardinality exhaustion.
- Treat paths and log fields as untrusted. Do not echo full malformed records or permit terminal/CSV injection.
- Target a representative 1 GB log in under 30 seconds on a documented laptop; performance claims require recorded reproducible evidence.

## Planned Structure

```text
pyproject.toml
src/nginx_report/
  __init__.py
  __main__.py
  cli.py
  parser.py
  models.py
  aggregate.py
  render_text.py
  render_json.py
  render_csv.py
  errors.py
tests/
  fixtures/
  golden/
bench/
```

Do not create alternative application roots or duplicate agent-instruction files.

## Engineering Rules

- Keep WIP=1: only the current plan step may be in progress.
- Preserve unrelated user changes and obey `.itd/` contracts.
- Make small, dependency-ordered changes with tests.
- Use byte-oriented line streaming on the hot path; profile before optimizing.
- Keep parser/aggregation independent of Click and Rich; renderers consume the canonical report only.
- Run the exact step verification plus the current repository oracle against the frozen staged candidate.
- Do not mark work complete from prose, a standalone PASSED string, or stale evidence; require a current revalidated adjudication receipt.
- At the end of every session or significant work block, save context through `/session-save`.

## Step Status

| Step | Scope | Status | Required evidence before Done |
|---:|---|---|---|
| 1 | Package, models, error contracts | Not started | Install/import and focused tests |
| 2 | Combined-log parser and early benchmark | Not started | Parser suite and recorded 100 MB measurement |
| 3 | IP and hourly aggregation | Not started | Aggregate tests and coverage gate |
| 4 | Error URLs and exact User-Agent tracking | Not started | Boundary, exhaustion-code-4, and coverage tests |
| 5 | Rich terminal renderer | Not started | Plain/color golden tests and safety cases |
| 6 | JSON and CSV renderers | Not started | Schema and golden serialization tests |
| 7 | CLI and exit integration | Not started | Integration suite proving codes 0/1/2/3/4 |
| 8 | Robustness and 1 GB performance | Not started | Full suite, security cases, benchmark <30 seconds |
| 9 | Docs, package, release candidate | Not started | Clean wheel install and exact-candidate verification receipt |

Allowed statuses are `Not started`, `In progress`, `Blocked`, and `Done`. Only one row may be `In progress`; `Done` requires the stated current evidence.

## Current State and Next Action

Blueprint documents are complete; no implementation step has begun. The next authorized implementation action is Step 1 only, using the matching prompt in `CLAUDE_CODE_GUIDE.md`. P1/P2 roadmap features are not authorized by the MVP plan.
