# Project Memory: nginx-log-report

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams a finite nginx access-log file or stdin and reports top client IPs, top error URLs, hourly request percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV are pipeline contracts. Delivery is one weekend with a $0 budget.

This repository currently contains a blueprint, not product implementation. Read `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and `IMPLEMENTATION_PLAN.md` before writing code. `CLAUDE_CODE_GUIDE.md` supplies step-scoped prompts.

## Product Invariants

- **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- No authentication, server, cloud, Docker, or Kubernetes.
- Python 3.11 with Click, Rich, dataclasses, pip packaging, and a single process.
- Never load the complete input or retain raw access records.
- The exact hourly formula is `100 × hourly_request_count / total_valid_requests`.
- Exact UA cardinality is guarded before insertion; exhaustion exits `4` with no partial report.
- Structured output is deterministic, ANSI-free stdout; diagnostics are stderr.
- Specification and acceptance criteria are the source of truth. Change documents before intentionally changing behavior.

## Complete Exit-Code Contract

| Code | Meaning |
|---:|---|
| `0` | successful report/help/version; lenient parsing may skip invalid lines |
| `1` | I/O or unexpected runtime failure |
| `2` | Click usage/argument error |
| `3` | input-data failure: strict malformed input, invalid UTF-8, unsupported content, or zero valid requests |
| `4` | unique-cardinality exhaustion before exceeding `--max-unique-user-agents` |

Never omit, remap, or merge code `4` with codes `1` or `3`.

## Planned Structure

```text
pyproject.toml
src/nginx_log_report/
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
  test_*.py
scripts/
  generate_benchmark_log.py
docs/
  BENCHMARK.md
```

Create only the paths assigned by the active implementation step. Do not pre-create later-step code.

## Engineering Rules

1. Preserve WIP=1: finish and verify the active step before starting another.
2. Keep parsing, aggregation, and rendering independent; only `cli.py` owns orchestration and exit mapping.
3. Treat every log field as untrusted data. Do not execute, fetch, interpolate as Rich markup, or emit full raw lines in default diagnostics.
4. Ranking order is count descending, then key ascending. JSON/CSV bytes must be repeatable for the same input/config/version.
5. Common format has no UA metric: terminal `N/A`, JSON `null`, CSV empty percentage.
6. Test through both file and stdin boundaries and independently prove exit codes `0/1/2/3/4`.
7. Profile before performance optimization. Bind benchmark claims to fixture, hardware, OS, command, cache state, and exact wheel candidate.
8. Do not claim a reviewer ran unless one actually did; label solo challenge work as self-review/self-critique.
9. Update documentation and status only after the relevant command actually passes.
10. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Verification Baseline

```bash
python3.11 -m pytest -q --cov=nginx_log_report --cov-fail-under=90
python3.11 -m build
python3.11 -m twine check dist/*
/usr/bin/time -v nginx-log-report --json /tmp/nginx-log-report-benchmark-1gb.log >/dev/null
```

The final benchmark must be under 30 seconds on the documented reference laptop. During planning these commands are future acceptance commands, not evidence that code already exists or passes.

## Implementation Status

| Step | Scope | Status | Evidence |
|---:|---|---|---|
| 1 | Package and CLI boundary | Not started | None; blueprint only |
| 2 | Models, errors, fixtures | Not started | None; blueprint only |
| 3 | Streaming parser | Not started | None; blueprint only |
| 4 | Rankings and hourly distribution | Not started | None; blueprint only |
| 5 | Exact UA share and exhaustion guard | Not started | None; blueprint only |
| 6 | Rich terminal renderer | Not started | None; blueprint only |
| 7 | JSON and CSV renderers | Not started | None; blueprint only |
| 8 | End-to-end contract suite | Not started | None; blueprint only |
| 9 | Performance and release evidence | Not started | None; blueprint only |

## Current State and Next Action

The full blueprint is complete and no product code has been implemented. The next authorized implementation action, when requested, is Step 1 from `IMPLEMENTATION_PLAN.md`; do not start it during documentation-only work.

