# nginx-insight Project Instructions

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams
one nginx combined access-log file or stdin and reports top-10 client IPs,
top-10 URLs with 4xx/5xx responses, 24 hourly request percentages, and exact
unique User-Agent share. Default output uses Rich; `--json` and `--csv` are
stable pipeline formats. The cash budget is $0 and delivery is one weekend.

The specification is the durable source of truth:

1. `PRD.md` owns user-visible requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` owns component, CLI, schema, and failure contracts.
3. `IMPLEMENTATION_PLAN.md` owns dependency order and verification commands.
4. `STRATEGIC_PLAN.md` owns priorities, risks, budget, and success metrics.
5. `CLAUDE_CODE_GUIDE.md` provides bounded prompts for future implementation.

Change the specification before changing behavior. Do not scatter conflicting
agent instructions into additional files.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- Preserve a single synchronous process and stateless streaming. Never read an
  entire input or retain all raw lines/records.
- Do not add authentication, a database, HTTP API, server, cloud service,
  Docker deployment, or Kubernetes.
- Keep exact fixed top-10 rankings deterministic: count descending, key ascending.
- Compute hourly distribution with
  `100 × hourly_request_count / total_valid_requests`.
- Keep JSON/CSV primary output on stdout and all diagnostics on stderr.
- Preserve exit codes exactly: `0` success; `1` unexpected internal/runtime
  failure; `2` usage/option error; `3` input open/read/decode or no-valid-record
  failure; `4` unique-cardinality exhaustion. Code 4 cannot be omitted,
  remapped, or converted to partial success.
- Treat log content as untrusted data: never execute it, fetch its URLs, or
  render it as Rich markup.
- Keep WIP=1. Before changing scope, update `.itd/SCOPE_LOCK.md` and reconcile
  the active unit in `.itd-memory/STATE.json` or `.itd-memory/GOAL.json`.
- Freeze the exact candidate and use the current Idea to Deploy machine oracle
  and risk-tier checker before marking implementation work complete.
- Do not claim an adversarial/independent review unless its separate artifact
  and provenance actually exist.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_insight/
  __init__.py
  __main__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  render/
    __init__.py
    terminal.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  test_cli_smoke.py
  test_parser.py
  test_aggregate.py
  test_exit_codes.py
  test_terminal_output.py
  test_pipeline_output.py
  test_end_to_end.py
benchmarks/
  generate_log.py
  run_benchmark.sh
  README.md
```

This is a planned structure, not evidence that files have been implemented.

## Working Commands

Use the commands defined by the active step. The eventual baseline suite is:

```text
python3.11 -m pytest -q --cov=nginx_insight --cov-fail-under=90
python3.11 -m ruff check .
python3.11 -m mypy src/nginx_insight
python3.11 -m build
```

Do not state that these pass until they have run against the exact candidate.

## Status

| Step | Scope | Status |
|---:|---|---|
| 0 | Full blueprint documents | Complete |
| 1 | Package and quality skeleton | Not started |
| 2 | Models, fixtures, parser | Not started |
| 3 | Streaming aggregations | Not started |
| 4 | Error and cardinality contract | Not started |
| 5 | Rich terminal output | Not started |
| 6 | JSON and CSV output | Not started |
| 7 | End-to-end acceptance | Not started |
| 8 | 1 GB performance evidence | Not started |
| 9 | Distribution and release gate | Not started |

Update this table only from recorded evidence and keep it consistent with the
Idea to Deploy state ledger. The next action after blueprinting is Step 1; do
not start it without an explicit implementation request.
