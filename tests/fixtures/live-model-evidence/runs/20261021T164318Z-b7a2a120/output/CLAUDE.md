# Project Instructions: nginx-stream-report

## Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx count, hourly request distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV are stable pipeline formats. The cash budget is $0 and the delivery target is one weekend.

The durable source of truth is:

1. `PRD.md` for behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` for interfaces and technical decisions.
3. `IMPLEMENTATION_PLAN.md` for dependency order and verification.
4. `CLAUDE_CODE_GUIDE.md` for bounded implementation prompts.
5. `STRATEGIC_PLAN.md` for scope, priority, and success measures.

If these conflict, stop implementation, reconcile the specification first, then update code and tests.

## Non-Negotiable Product Rules

- Use Python 3.11, Click, Rich, and dataclasses; distribute through pip.
- Remain a local, stateless, single-process streaming CLI.
- Do not add authentication, a database, an HTTP API, a server, cloud services, Docker, or Kubernetes.
- Do not retain complete input records, make network calls, or emit telemetry.
- Treat log fields as untrusted data.
- Rank top lists by count descending and key ascending; cap them at 10.
- Define every hourly percentage as `100 × hourly_request_count / total_valid_requests` across 24 logged-local-hour buckets.
- Calculate exact unique User-Agent cardinality until the configured safety ceiling; never silently approximate.
- Preserve exit codes: `0` success, `1` input/runtime I/O failure, `2` usage error, `3` no valid records, `4` unique-cardinality exhaustion.
- Keep JSON/CSV free of ANSI escapes and diagnostics; write diagnostics to stderr.
- Obtain human approval before publishing a package, pushing, opening a PR, deploying, deleting material data, or any other external/irreversible action.

## Engineering Rules

- Work on one implementation-plan step at a time.
- Add tests with new behavior and run the narrow tests before the full suite.
- Use a precompiled parser and one sequential pass; optimize only from measurements.
- Make output deterministic, including ties and all 24 hour buckets.
- Do not weaken semantics to pass the 1 GB/30 s benchmark.
- Keep generated 1 GB fixtures outside the repository and record reproducible generation metadata.
- Update specifications before deliberately changing a user-visible contract.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Structure

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregator.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_parser.py
  test_aggregator.py
  test_machine_renderers.py
  test_text_renderer.py
  test_cli_contract.py
  test_docs_examples.py
benchmarks/
  generate_log.py
  run.py
  README.md
```

## Standard Verification

Run step-specific commands from `IMPLEMENTATION_PLAN.md`, then:

```bash
python3.11 -m pytest -q
python3.11 -m build
python3.11 -m twine check dist/*
```

Before release, also install the built wheel in a clean Python 3.11 environment and run the representative 1 GB benchmark with a 30-second threshold.

## Status

| Step | Description | Status |
|---:|---|---|
| 0 | Full blueprint documents | Complete |
| 1 | Package skeleton and command boundary | Not started |
| 2 | Domain models and parser | Not started |
| 3 | Streaming aggregation | Not started |
| 4 | JSON and CSV outputs | Not started |
| 5 | Rich terminal report | Not started |
| 6 | End-to-end CLI and exit semantics | Not started |
| 7 | Performance proof | Not started |
| 8 | Release validation | Not started |

Do not mark a step complete from narration alone. Record the commands run, their results, and the relevant test/benchmark evidence.
