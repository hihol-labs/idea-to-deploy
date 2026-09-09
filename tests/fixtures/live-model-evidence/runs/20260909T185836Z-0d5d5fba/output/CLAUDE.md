# Nginx Pulse Project Memory

## Context

Nginx Pulse is a planned open-source Python 3.11 CLI for DevOps/SRE engineers. It streams one nginx combined access-log input and reports top 10 IPs, top 10 URLs by 4xx/5xx count, a 24-hour request percentage distribution, and exact unique User-Agent share. It is a $0, one-weekend product with colored terminal text by default and JSON/CSV pipeline modes.

The durable product specification is `PRD.md`; architecture and public contracts are in `PROJECT_ARCHITECTURE.md`; step boundaries and checks are in `IMPLEMENTATION_PLAN.md`. If observed behavior and documentation disagree, stop, resolve the specification explicitly, and then update implementation and tests.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, and standard-library dataclasses.
- Keep a single local process with stateless streaming aggregation.
- Do not add authentication, a database, HTTP API, server, cloud service, Docker, or Kubernetes.
- Never buffer the full input or retain raw records after aggregation.
- Top lists contain at most ten entries and break equal-count ties by key ascending.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`; empty valid input produces 24 zeros.
- Keep text/JSON/CSV metric values consistent through one `AnalysisResult`.
- Keep normal output on stdout and diagnostics on stderr.
- Preserve the full exit mapping: 0 success, 1 runtime/input-output failure, 2 usage error, 3 partial malformed-line analysis, 4 unique-cardinality exhaustion.
- Treat logs as untrusted data, never evaluate content, invoke a shell, or transmit log data.
- Preserve WIP=1 and run the current step's verification before changing status.
- Do not claim the 1 GB / 30 s target without current benchmark evidence and machine metadata.
- Do not represent the external Devil's Advocate review as having run in this session.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Stack

| Area | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal output | Rich |
| Models | dataclasses |
| Serialization | standard-library `json` and `csv` |
| Tests | pytest |
| Static quality | Ruff and mypy |
| Packaging | `pyproject.toml`, wheel, source distribution, pip/pipx |

## Planned Structure

```text
src/nginx_pulse/
  cli.py
  models.py
  parser.py
  aggregate.py
  render/{text,json,csv}.py
tests/{fixtures,unit,integration,performance}/
```

## Interface Snapshot

One command accepts `[INPUT]`, where omission or `-` means stdin. It supports `--json`, `--csv`, `--color/--no-color`, `--max-unique-user-agents`, `--help`, and `--version`. `--json` and `--csv` are mutually exclusive. Refer to the exact `## CLI Interface` section in `PROJECT_ARCHITECTURE.md` before editing command behavior.

## Step Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Install, CLI contract tests, help smoke test |
| 2 | Models and parser | Not started | Parser tests and mypy |
| 3 | Streaming aggregation | Not started | Aggregate tests and branch coverage |
| 4 | JSON and CSV | Not started | Renderer tests and JSON parse smoke test |
| 5 | Rich text | Not started | Text tests and redirected output smoke test |
| 6 | Exit/stream semantics | Not started | Subprocess exit and stream tests |
| 7 | Performance guardrails | Not started | CI-safe test and measured 1 GB benchmark |
| 8 | Release readiness | Not started | Full quality suite, isolated wheel, package checks |

Active implementation step: none. Blueprint documentation is complete only when the required root files pass the documented structural checks. The next product-code action, in a future session, is STEP 1.

## Session Handoff Format

At the end of a work block, record: active step, files changed, commands actually run with outcomes, open blockers, relevant decisions, and one explicit next action. A prose claim without command evidence does not advance the step status.
