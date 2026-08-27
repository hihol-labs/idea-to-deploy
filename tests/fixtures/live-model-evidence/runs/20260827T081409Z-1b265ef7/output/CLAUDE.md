# Project Memory: Nginx Stream Analyzer

## Project Context

Build a local open-source Python 3.11 CLI for DevOps/SRE engineers. It incrementally reads one nginx common/combined access-log stream and reports top client IPs, top 4xx/5xx request targets, 24-hour request percentages, and exact unique User-Agent share. Default output is colored terminal text; JSON and CSV serve pipelines.

The current repository state is blueprint-only. No product code has been implemented or verified.

## Source of Truth

Read these before implementation, in this order:

1. `PRD.md` — behavior, priorities, acceptance, and non-goals.
2. `PROJECT_ARCHITECTURE.md` — modules, metric semantics, CLI/schema/exit contracts.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 sequence, files, and checks.
4. `CLAUDE_CODE_GUIDE.md` — scoped prompts for executing each step.
5. `STRATEGIC_PLAN.md` — delivery constraints, KPIs, risks, and Definition of Done.
6. `.itd/` and `.itd-memory/` — active methodology contracts and persistent execution state.

When behavior changes, update the PRD and architecture first, then implementation and tests. Do not let generated code become the undocumented source of truth.

## Non-Negotiable Product Decisions

- Runtime and stack: CPython 3.11, Click, Rich, dataclasses, pip packaging.
- Architecture: one local process and one sequential streaming pass.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- No raw-record retention, telemetry, network calls, or persistence.
- Default ranking length is 10; ties are count descending then key ascending.
- Hourly distribution is `100 × hourly_request_count / total_valid_requests` for all 24 hours.
- User-Agent cardinality is exact and guarded; approximation is not an automatic fallback.
- Exit contract: `0` success, `1` input/I/O, `2` usage/configuration, `3` no valid requests, `4` unique-cardinality exhaustion.
- stdout contains reports only; stderr contains diagnostics only; nonzero exits produce no partial report.
- The target is 1 GB under 30 seconds on a documented reference laptop, with correctness checked independently.

## Engineering Rules

- Preserve WIP=1. Complete and verify the active implementation step before opening another.
- Before changing scope, reconcile `.itd/SCOPE_LOCK.md` and the active `.itd-memory` unit.
- Use tests as executable acceptance evidence; do not weaken tests or contracts to obtain green output.
- Treat every log line as untrusted data. Never execute it, interpolate it into a shell, or enable Rich markup for its values.
- Keep parser, aggregation, and renderer responsibilities separate.
- Avoid whole-file reads and per-request accumulation. Profile before optimizing or introducing concurrency.
- Use native patch/edit tools for scoped changes and preserve unrelated worktree changes.
- Exclude undeclared ignored/untracked files from the oracle; declare and content-bind any necessary non-Git input.
- Accept completion only from a current, revalidated exact-candidate adjudication receipt under the project Verification Loop.
- Never create `DEVILS_ADVOCATE_REVIEW.md` during normal implementation; the external benchmark harness owns that separate review.
- Mandatory continuity rule: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  __main__.py
  cli.py
  models.py
  errors.py
  parser.py
  aggregate.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_cli.py
  test_errors.py
  test_parser.py
  test_aggregate.py
  test_text_renderer.py
  test_json_renderer.py
  test_csv_renderer.py
  test_integration.py
  test_install.py
  test_resource_guards.py
benchmarks/
  generate_log.py
  run.py
```

This is a planned structure, not evidence that files exist.

## Implementation Status

| Step | Scope | Status | Required evidence before Done |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Install/help/version and CLI tests |
| 2 | Models and exit policy | Not started | `0/1/2/3/4` mapping tests |
| 3 | Access-log parser | Not started | Fixture matrix and parser coverage |
| 4 | Streaming aggregation | Not started | Exact metrics, one-pass, and ceiling tests |
| 5 | Rich terminal renderer | Not started | Safe golden/TTY/color tests |
| 6 | JSON and CSV renderers | Not started | Parseable deterministic golden tests |
| 7 | End-to-end and packaging | Not started | Subprocess, clean-install, build checks |
| 8 | Performance and release gate | Not started | Correct 1 GB benchmark and current verification receipt |

## Current Handoff

- **Active lifecycle:** Blueprint Full completed as planning documents only.
- **Implementation unit:** None; do not infer that Step 1 has started.
- **Next action:** When explicitly authorized to implement, initialize/reconcile the Step 1 Idea to Deploy unit and follow Prompt 1 in `CLAUDE_CODE_GUIDE.md`.
- **Known review state:** No in-session adversarial or independent architecture review was performed. The external harness runs that review separately.
