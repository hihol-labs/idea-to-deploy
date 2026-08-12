# nginx-log-report Project Memory

## Context

This repository plans a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs from a file or stdin and reports top 10 IPs, top 10 URLs by combined 4xx/5xx errors, 24-hour request distribution, and unique User-Agent share. Default output is colored Rich terminal text; `--json` and `--csv` are stable pipeline formats.

The current repository state is **blueprint complete; product code not started**. Product decisions are in [PRD.md](PRD.md), technical contracts in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and work sequence in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Binding Rules

1. Preserve the decision: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
2. Use Python 3.11, Click, Rich, dataclasses, pip packaging, and one process.
3. Never add authentication, a server, cloud/Kubernetes resources, telemetry, or persistent application state without first changing the approved specs.
4. Read input incrementally and do not retain raw records after aggregation.
5. Hourly distribution is a percentage calculated as `100 × hourly_request_count / total_valid_requests`; zero valid requests means 24 `0.0` percentages.
6. Preserve exact exit codes: `0` success, `1` unexpected internal failure, `2` CLI usage error, `3` input/data error, `4` unique-cardinality exhaustion.
7. On exit `3` or `4`, emit no partial report. Reports use stdout and diagnostics use stderr.
8. Treat log content as untrusted data; do not evaluate it, invoke a shell with it, or allow Rich markup interpretation.
9. Specifications are the durable source of truth. Change PRD/architecture and acceptance criteria before intentionally changing behavior.
10. Preserve WIP=1: implement and verify one numbered plan step at a time.
11. Do not publish packages, create releases, or contact external services without explicit user authorization.
12. **В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save** (At the end of every session or significant work block, save context via `/session-save`).

## Stack

| Area | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal | Rich |
| Models | dataclasses |
| Aggregates | standard-library counters, set, fixed 24-slot list |
| Packaging | `pyproject.toml`, PEP 517 wheel/sdist, pip console script |
| Tests | pytest, golden CLI outputs, clean-install smoke test |

## Planned Repository Structure

```text
src/nginx_log_report/
  __init__.py
  __main__.py
  cli.py
  models.py
  parser.py
  aggregator.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_parser.py
  test_aggregator.py
  test_cli_*.py
  test_*_renderer.py
  test_end_to_end.py
benchmarks/
  README.md
  run_1gb.sh
pyproject.toml
```

This tree is planned, not yet implemented. Do not create several modules ahead of their numbered step merely to make the tree look complete.

## Working Protocol

1. Read `AGENTS.md`, this file, the active implementation-plan step, relevant PRD stories, and referenced architecture sections.
2. Inspect current changes and preserve unrelated work.
3. Freeze the step scope and acceptance checks; keep WIP at one.
4. Implement the smallest complete vertical slice.
5. Run the exact step checks plus proportionate regression checks.
6. Record evidence and update the status table only when current checks pass.
7. Use [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for bounded step prompts.

## Status

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| Blueprint | Six required planning documents plus workflow README | Complete | Documentation presence/consistency validation only |
| 1 | Contract and package skeleton | Not started | None |
| 2 | Combined-log parser | Not started | None |
| 3 | Single-pass aggregator | Not started | None |
| 4 | Streaming CLI input | Not started | None |
| 5 | Rich terminal renderer | Not started | None |
| 6 | JSON/CSV renderers | Not started | None |
| 7 | Cardinality/exit matrix | Not started | None |
| 8 | Correctness/security/performance evidence | Not started | None |
| 9 | Installable release candidate | Not started | None |

## Definition of Handoff-Ready

The active step has no placeholders, its named verification commands have current outcomes, contracts remain consistent, state/status reflects reality, and the next action is explicit. A narrated “passed” without command evidence is not completion.

## Next Action

Begin Step 1 from [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) only when implementation is authorized. This blueprint task itself does not authorize product code.
