# Nginx Stream Report Project Memory

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports:

1. Top client IPs by request count (10 by default).
2. Top literal URLs by combined 4xx/5xx count (10 by default).
3. A 24-hour percentage distribution using `100 × hourly_request_count / total_valid_requests`.
4. Exact unique User-Agent count and its share of valid requests.

Default output is colored Rich text. `--json` and `--csv` provide stable pipeline interfaces. The target is a representative 1 GB file in under 30 seconds on a documented laptop profile. Cash budget is $0 and delivery scope is one weekend.

## Authoritative Documents

Read these before implementation, in this precedence order for their respective concerns:

1. `.itd/` contracts and `.itd-memory/` active state govern execution and verification.
2. `PROJECT_ARCHITECTURE.md` governs components, parsing/metric semantics, CLI, output schemas, and architectural constraints.
3. `PRD.md` governs user-visible behavior and acceptance criteria.
4. `IMPLEMENTATION_PLAN.md` governs dependency order and step checks.
5. `STRATEGIC_PLAN.md` governs product priorities, KPIs, risks, and release criteria.
6. `CLAUDE_CODE_GUIDE.md` supplies implementation prompts but does not override the specifications.

When behavior changes, update the specification first and then implementation/tests. Do not let generated code become the only record of a product decision.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, standard-library dataclasses, and a pip-installable `src` layout.
- Preserve the architecture statement: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- Do not add authentication, a database, HTTP API, server, cloud, Docker, or Kubernetes without an explicitly approved scope/specification change.
- Never load an entire input log or silently approximate required metrics.
- Treat log bytes and fields as untrusted data. Never evaluate them, pass them to a shell, interpret them as Rich markup, or make network requests from them.
- Keep stdout exclusively for the selected report and stderr for diagnostics.
- Preserve exit codes: 0 success (including skipped malformed records), 1 internal/output failure, 2 usage error, 3 input/read/parse failure, and 4 unique-cardinality exhaustion.
- Preserve WIP=1. Complete and verify the current step before starting another.
- Before changing scope, update `.itd/SCOPE_LOCK.md` and reconcile the active unit state.
- Exclude undeclared ignored/untracked overlays from verification; explicitly declare and content-bind any necessary non-Git input.
- Accept work only from a current revalidated adjudication receipt for the exact staged candidate under the active risk route.
- Do not weaken, delete, or bypass tests and quality gates to obtain a pass.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Stack and Structure

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  __main__.py
  cli.py
  input.py
  parser.py
  aggregate.py
  models.py
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

Runtime dependencies are Click and Rich. Development tooling is pytest, pytest-cov/coverage, Ruff, mypy, and build. No environment variables or `.env` file are part of the MVP.

## Development Commands

These commands become active as the corresponding implementation steps create their configuration:

```bash
python3.11 -m pip install -e '.[dev]'
python3.11 -m pytest -q --cov=nginx_stream_report --cov-branch --cov-fail-under=90
python3.11 -m ruff check .
python3.11 -m mypy src/nginx_stream_report benchmarks
python3.11 -m build
```

Also run the current Idea to Deploy Verification Loop commands for the active unit. A standalone green command or prose “passed” statement is not completion evidence.

## Implementation Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI contract | Not started | CLI tests, build, install, exact-candidate receipt |
| 2 | Models, errors, fixtures | Not started | Model/error tests, mypy, exact-candidate receipt |
| 3 | Streaming parser | Not started | Parser suite, Ruff, exact-candidate receipt |
| 4 | Exact bounded aggregation | Not started | Formula/cardinality tests and coverage, exact-candidate receipt |
| 5 | Rich terminal renderer | Not started | Golden/safety tests and smoke output, exact-candidate receipt |
| 6 | JSON and CSV renderers | Not started | Schema/golden/parse tests, exact-candidate receipt |
| 7 | CLI integration/failures | Not started | File/stdin and exit-code 0/1/2/3/4 tests, exact-candidate receipt |
| 8 | Performance/hardening | Not started | Full gates plus 1 GB benchmark and oracle, exact-candidate receipt |
| 9 | Package/release acceptance | Not started | Clean wheel smoke test and revalidated release receipt |

Update this table and `.itd-memory/` together after verified progress. Do not label a step complete while its receipt is stale or its required checks are missing.

## Current State and Next Action

Blueprint documents are complete; product code has not been implemented. The next authorized implementation action, when requested, is Step 1 in `IMPLEMENTATION_PLAN.md`. Do not skip ahead to parsing or aggregation before the package/CLI contract is accepted.
