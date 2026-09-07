# Project Memory: nginx-stream-report

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx access logs and reports top client IPs, top 4xx/5xx URLs, hourly request percentages, and exact unique User-Agent share. Default output is colored Rich text; JSON and CSV support pipelines. Cash budget is $0 and delivery is one weekend.

Current phase: **blueprint complete; product implementation not started**.

## Source of Truth

Read in this order before implementation:

1. `AGENTS.md` and `.itd/` contracts.
2. `PRD.md` for behavior and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` for component, CLI, data, and output contracts.
4. `IMPLEMENTATION_PLAN.md` for the active step.
5. `.itd-memory/` for the current exact-candidate state and evidence.
6. `CLAUDE_CODE_GUIDE.md` for bounded step prompts.

If documents conflict, explicit user requirements and project contracts win; otherwise architecture is authoritative. Change the specification before changing behavior.

## Non-Negotiable Decisions

- Python 3.11; Click; Rich; dataclasses and standard library; pip-installable `src/` package.
- One local process, one-pass streaming, no retained raw records.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Hourly percentage formula: `100 × hourly_request_count / total_valid_requests`.
- Exact UA cardinality protected by a configurable hard limit.
- Exit codes: `0` success, `1` runtime I/O/output failure, `2` usage error, `3` strict parse/validation failure, `4` unique-cardinality exhaustion.
- On failure, emit no partial report to stdout; diagnostics go to stderr.
- Tie-break top lists by count descending, then key ascending.
- JSON and CSV are versioned/stable process-output contracts.

## Engineering Rules

- Preserve WIP=1 and implement only the active plan step.
- Use the smallest applicable repository-local Idea to Deploy lifecycle skill before changing code.
- Follow test-first red/green work for observable behavior and record actual command evidence.
- Treat log content as untrusted data; escape terminal controls and use standard JSON/CSV serializers.
- Do not add a runtime dependency, approximate metric, concurrency, custom log grammar, or persistent state without an explicit architecture/PRD update.
- Do not claim the performance target without the exact recorded benchmark.
- Accept completion only through the project’s current Verification Loop adjudication receipt, not narration or a standalone pass message.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Structure

```text
src/nginx_stream_report/
  __init__.py
  __main__.py
  cli.py
  errors.py
  input.py
  models.py
  parser.py
  aggregate.py
  renderers/
    __init__.py
    terminal.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  golden/
benchmarks/
```

This tree is planned, not evidence that implementation files exist.

## Implementation Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package and CLI contract | Not started |
| 2 | Models and parser | Not started |
| 3 | Streaming input and parse policy | Not started |
| 4 | Core aggregations | Not started |
| 5 | Cardinality guard | Not started |
| 6 | Rich terminal renderer | Not started |
| 7 | JSON and CSV renderers | Not started |
| 8 | End-to-end QA and packaging | Not started |
| 9 | Performance gate and release handoff | Not started |

Next action: begin Step 1 through the appropriate Idea to Deploy implementation workflow; do not create product code as part of blueprint work.

