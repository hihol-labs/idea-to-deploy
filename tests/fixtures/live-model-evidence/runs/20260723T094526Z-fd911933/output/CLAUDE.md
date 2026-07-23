# Project Memory: Nginx Stream Analytics CLI

## Context

This repository is in blueprint/planning state. The intended product is a pip-installable local Python 3.11 CLI for DevOps/SRE engineers that incrementally analyzes nginx combined access logs. Product code does not exist yet and must be created only through an authorized implementation unit.

## Source of Truth

1. [PRD.md](PRD.md) defines user-visible behavior and acceptance.
2. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) defines technical and interface decisions.
3. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) defines work order, file scope, and verification.
4. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) defines priorities, risks, budget, KPIs, and kill criteria.
5. `.itd/` contracts and `.itd-memory/` state govern execution and verification.

When documents disagree, stop and reconcile them before implementation. Behavior changes begin in the PRD and architecture; generated code follows the specification.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
- One local process and one sequential input pass.
- Exact required metrics and deterministic output ordering.
- Default Rich terminal text plus mutually exclusive `--json` and `--csv`.
- No authentication, database, HTTP API, server, telemetry, cloud, Docker requirement, or Kubernetes.
- No retained or transmitted log data.
- Target: a documented representative 1 GiB input under 30.0 seconds on a laptop.
- Budget $0 and one-weekend MVP.

## Engineering Rules

- Preserve WIP=1: activate and complete or recover one implementation-plan step at a time.
- Never mark work complete from narration; run the current `.itd/` verification contract and retain exact-candidate adjudication evidence.
- Read input in binary mode line by line and decode each line under the strict/lenient policy. Do not use `read()`, `readlines()`, or retain complete logs.
- Treat every log field as untrusted data. Escape terminal controls and Rich markup and neutralize spreadsheet formula prefixes.
- Keep stdout exclusively for selected report data and stderr for diagnostics.
- Output-schema changes require a PRD/architecture revision and new golden fixtures.
- Exact User-Agent semantics may not be replaced by approximation without an approved spec change.
- Do not publish packages, create cloud resources, start servers, or add persistent storage without explicit user scope.
- At the end of every session or meaningful block of work, preserve context through `/session-save`.
- «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned Structure

```text
src/nginx_stream_analytics/
  cli.py parser.py models.py aggregate.py
  render_text.py render_json.py render_csv.py
tests/
  fixtures/ test_parser.py test_aggregate.py test_cli.py
  test_renderers.py test_performance.py test_package.py
tools/generate_benchmark_log.py
docs/BENCHMARK.md
```

## Implementation Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI contract | Not started | Install, help, CLI tests |
| 2 | Models and parser | Not started | Parser tests, compileall |
| 3 | One-pass aggregation | Not started | Unit tests, branch coverage |
| 4 | JSON renderer | Not started | JSON validation, focused tests |
| 5 | CSV renderer | Not started | CSV round trip, focused tests |
| 6 | Rich terminal renderer | Not started | Color/markup/control focused tests |
| 7 | Streaming I/O and errors | Not started | CLI commands and tests |
| 8 | Performance evidence | Not started | Typical/high-cardinality time/RSS evidence and CI-size test |
| 9 | Release quality | Not started | Lint, types, tests, build, clean-wheel smoke |

## Current State and Next Action

Blueprint documents are the only planned deliverable in the current unit. No product code has been implemented or tested. The next authorized lifecycle action is to activate STEP 1, establish its task/acceptance contract, and use Prompt 1 from [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).
