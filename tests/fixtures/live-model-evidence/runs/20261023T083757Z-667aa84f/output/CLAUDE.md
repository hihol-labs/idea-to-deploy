# Nginx Stream Analyzer — Project Memory

## Context

This repository is planned as a local Python 3.11 CLI for DevOps and SRE engineers. It incrementally reads nginx combined access logs and reports top client IPs, top error URLs, hourly request percentages, and the share of unique User-Agents. Human output uses Rich; pipelines use JSON or CSV. The delivery budget is $0 and the implementation window is one weekend.

The durable product specification is `PRD.md`. Architecture and interface decisions are in `PROJECT_ARCHITECTURE.md`. Work order and executable checks are in `IMPLEMENTATION_PLAN.md`; session prompts are in `CLAUDE_CODE_GUIDE.md`.

## Non-Negotiable Product Rules

- Local, stateless, single-process streaming only.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Do not load the complete input into memory and do not persist log contents.
- No telemetry or network calls.
- Default output is colored terminal text when attached to a capable TTY; `--json` and `--csv` are stable pipeline formats without ANSI escapes.
- Hourly distribution uses `100 × hourly_request_count / total_valid_requests`.
- Ranking is count descending and key ascending, limited to 10 results.
- Exit codes are permanently `0/1/2/3/4`; code 4 is exact-cardinality exhaustion and must not emit a normal report.
- Log content is untrusted data: escape terminal markup, use standard serializers, and avoid raw-line diagnostics.
- The 1 GB under 30 seconds target is unverified until a reproducible benchmark runs on a named laptop.

## Stack

| Concern | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal UI | Rich |
| Models | Standard-library dataclasses |
| Packaging | `pyproject.toml`, pip, src layout |
| Testing | pytest with coverage and subprocess acceptance tests |

## Planned Structure

```text
src/nginx_stream_analyzer/
  __init__.py
  __main__.py
  cli.py
  config.py
  errors.py
  models.py
  reader.py
  parser.py
  aggregate.py
  renderers/
    base.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  test_cli.py
  test_models.py
  test_config.py
  test_reader.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_end_to_end.py
  test_exit_codes.py
  test_security.py
benchmarks/
  generate_log.py
  run_benchmark.sh
  README.md
```

This is a planned structure, not evidence that product code exists.

## Working Rules

1. Preserve WIP=1 and implement one numbered step from `IMPLEMENTATION_PLAN.md` at a time.
2. Read the relevant PRD and architecture sections before editing.
3. Add or update tests for new behavior, run focused tests, then run the full suite before any commit.
4. Record actual tool evidence; never report an unrun test or benchmark as passing.
5. Change the specification before intentionally changing user-facing behavior.
6. Do not commit, push, publish, deploy, delete, or send data externally without the required human confirmation.
7. Keep unrelated findings out of the current diff and record them for later work.
8. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Implementation Status

| Step | Deliverable | Status |
|---:|---|---|
| 1 | Installable CLI skeleton | Not started |
| 2 | Models, configuration, errors | Not started |
| 3 | Combined-log parser | Not started |
| 4 | Streaming reader | Not started |
| 5 | Exact bounded aggregation | Not started |
| 6 | Terminal, JSON, CSV renderers | Not started |
| 7 | Complete CLI and exit mapping | Not started |
| 8 | End-to-end contracts | Not started |
| 9 | Performance and memory proof | Not started |
| 10 | Verified release candidate | Not started |

## Current State

Blueprint documentation is the only completed work. No product code, tests, benchmark evidence, package artifact, external review verdict, or release exists yet. The next implementation action is Step 1 from `IMPLEMENTATION_PLAN.md` after explicit direction to begin implementation.

