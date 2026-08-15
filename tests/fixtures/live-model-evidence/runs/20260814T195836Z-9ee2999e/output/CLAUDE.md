# Project Instructions: nginx-stream-report

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top 10 IPs, top 10 URLs by 4xx/5xx count, hourly request percentages, and unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` support pipelines. The target is a representative 1 GB log in under 30 seconds on a documented laptop.

Current state: blueprint complete; no product code has been implemented.

## Source of Truth

Read in this order before implementation:

1. `PRD.md` for behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` for interfaces, schemas, and technical boundaries.
3. `IMPLEMENTATION_PLAN.md` for ordered work units and verification.
4. `CLAUDE_CODE_GUIDE.md` for bounded execution prompts.
5. `STRATEGIC_PLAN.md` for priorities, risks, and Definition of Done.

Specifications are durable assets. Update them first when behavior changes; do not let code silently redefine the contract.

## Non-Negotiable Rules

- Preserve a single-process, stateless, streaming architecture.
- Add no authentication, database, HTTP API, server, cloud service, Docker, or Kubernetes.
- Use Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- Never retain all raw log lines or silently approximate exact results.
- Calculate hourly distribution as `100 × hourly_request_count / total_valid_requests`; it is a percentage, not an unscaled fraction.
- Preserve the full exit contract: `0` success, `1` input/I/O, `2` CLI usage, `3` strict malformed data, `4` unique-cardinality exhaustion.
- Code `4` must not be omitted or remapped in implementation, tests, docs, or prompts.
- Keep JSON/CSV deterministic, uncolored, and empty on failed executions.
- Treat paths and log fields as untrusted data; never shell-interpolate them.
- Keep WIP=1 and attach the evidence required by `.itd/VERIFICATION_CONTRACT.json` before accepting implementation work.
- Do not create `DEVILS_ADVOCATE_REVIEW.md` or claim an adversarial review occurred unless a future dedicated review session actually runs it.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_stream_report/
  __init__.py
  __main__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  scripts/
benchmarks/
```

Do not create these paths ahead of the active plan step.

## Work Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Pending | Clean install, help, CLI tests |
| 2 | Models and errors | Pending | Unit tests and type check |
| 3 | Combined-log parser | Pending | Parser tests and lint |
| 4 | Aggregation/cardinality | Pending | Unit tests and branch coverage |
| 5 | Rich text renderer | Pending | Snapshot/security cases |
| 6 | JSON/CSV renderers | Pending | Golden and parse-back tests |
| 7 | End-to-end CLI | Pending | Integration suite and exits `0/1/2/3/4` |
| 8 | Performance/release | Pending | Full checks, clean wheel, measured 1 GB benchmark |

Only mark a row complete after current evidence is recorded and applicable Idea to Deploy verification state is reconciled.

## Working Commands

These are planned commands; they become executable after the corresponding files and environment exist:

```bash
.venv/bin/pytest -q --cov=nginx_stream_report --cov-branch --cov-fail-under=90
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/python -m build
/usr/bin/time -v .venv/bin/python benchmarks/run.py --size-gib 1 --max-seconds 30
```

## Session Handoff

At the end of each session, state the active step, files changed, exact commands and outcomes, known failures, scope decisions, and the next safe action. A prose “passed” is not a substitute for the repository’s current verification receipt when that contract applies.

