# `nginx-top` Project Instructions

## Product Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top-10 IPs, top-10 URLs among 4xx/5xx responses, hourly request percentages, and the share of unique User-Agent values. Default output is colored Rich terminal text; JSON and CSV are stable pipeline formats.

This file guides implementation sessions. The current blueprint session creates documentation only.

## Source of Truth

Read in this order:

1. `PROJECT_ARCHITECTURE.md` for architecture, schemas, CLI, and exit behavior.
2. `PRD.md` for product priorities and acceptance criteria.
3. `IMPLEMENTATION_PLAN.md` for dependency-ordered work.
4. `CLAUDE_CODE_GUIDE.md` for bounded per-step prompts.
5. `STRATEGIC_PLAN.md` for goals, constraints, risks, and Definition of Done.

When behavior changes, update the specification before changing code. Do not let generated code silently redefine the contract.

## Non-Negotiable Decisions

- Use Python 3.11, Click, Rich, and standard-library dataclasses; distribute through pip.
- Use one local process and stream each input once.
- No authentication, database, HTTP API, resident server, cloud dependency, Docker requirement, or Kubernetes.
- Do not persist or transmit logs, derived identifiers, or telemetry.
- Target a representative 1 GB input in under 30 seconds on a documented laptop.
- Use `100 × hourly_request_count / total_valid_requests` for hourly percentages.
- Keep JSON/CSV free of ANSI sequences and apply deterministic ranking ties.
- Preserve all exits: `0` success, `1` operational/internal failure, `2` usage error, `3` non-empty all-invalid input, `4` unique-cardinality exhaustion.

## Planned Structure

```text
src/nginx_top/       # CLI, parser, aggregation, report model, renderers
tests/unit/          # Isolated parser/aggregation/renderer behavior
tests/integration/   # CLI, stdin/file, exit, and installed-wheel contracts
tests/performance/   # Reproducible 1 GB elapsed-time and RSS evidence
tests/fixtures/      # Small reviewed input/golden fixtures only
```

Do not create product files outside the paths specified by the active step without first reconciling scope.

## Engineering Rules

- Keep WIP=1: finish and verify one implementation-plan step at a time.
- Treat input as untrusted data; never evaluate it or build shell commands from it.
- Escape log-derived Rich content and use standard JSON/CSV encoders.
- Keep metric calculation out of renderers.
- Never load the whole input or retain full request records.
- Add a regression test before fixing any discovered behavior defect.
- Do not weaken tests, coverage, schemas, cardinality guards, or performance criteria to obtain a pass.
- Record exact commands and observed evidence; expected success is not evidence.
- Do not publish packages, push changes, deploy, or write to external systems without explicit authorization.
- At the end of every session or meaningful block of work, save context through `/session-save` («В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save»).

## Verification Baseline

For implementation, the minimum local gate is:

```text
python3.11 -m pytest -q --cov=nginx_top --cov-fail-under=90
python3.11 -m ruff check src tests
python3.11 -m mypy src/nginx_top
python3.11 -m pytest tests/performance/test_one_gb.py -m performance -q
python3.11 -m build
```

The performance command is mandatory before release completion and must record the environment and observed values. Apply the repository Idea to Deploy verification contract to the exact candidate when implementation begins.

## Status

| Step | Scope | Status |
|---:|---|---|
| 0 | Full blueprint documents | Complete when all six root documents pass structural validation |
| 1 | Package and CLI shell | Not started |
| 2 | Models, errors, fixtures | Not started |
| 3 | Streaming input and parser | Not started |
| 4 | Aggregation and cardinality guard | Not started |
| 5 | JSON renderer | Not started |
| 6 | CSV renderer | Not started |
| 7 | Rich terminal renderer | Not started |
| 8 | End-to-end CLI and exits | Not started |
| 9 | Quality/security/performance evidence | Not started |
| 10 | Packaging and user documentation | Not started |

## Session Handoff

Before ending an implementation session, record changed files, verification output, unresolved risks, active step, and the exact next action. A failing or unrun gate leaves the step open; do not convert it into a narrative completion claim.

