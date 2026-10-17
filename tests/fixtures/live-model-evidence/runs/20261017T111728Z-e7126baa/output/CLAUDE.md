# Project Instructions: nginx-insights

## Context

This repository is for `nginx-insights`, a local Python 3.11 CLI for DevOps/SRE log triage. The durable product specification is `PRD.md`; `PROJECT_ARCHITECTURE.md` is the technical source of truth; `IMPLEMENTATION_PLAN.md` defines the approved delivery sequence; `STRATEGIC_PLAN.md` records scope and priorities; `CLAUDE_CODE_GUIDE.md` contains step prompts.

## Product Invariants

- Remain a local, single-process, stateless streaming CLI.
- Use Python 3.11, Click, Rich, and dataclasses; remain pip-installable.
- Do not add authentication, a database, HTTP API, server, cloud, Kubernetes, telemetry, or persistent application state.
- Never retain all parsed records; guard exact distinct-key maps and never silently sample or approximate.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Default output is colored terminal text when supported; `--json` and `--csv` are clean pipeline formats.
- Preserve exit codes: `0` success, `1` runtime/output failure, `2` usage error, `3` input/data error, `4` unique-cardinality exhaustion.
- Do not publish, deploy, push, open a PR, or perform another external/irreversible action without explicit human approval.

## Engineering Rules

1. Change the specification first when public behavior changes; generated/implemented code follows the spec.
2. Work on one numbered `IMPLEMENTATION_PLAN.md` step at a time and keep changes inside its scope.
3. Add or update tests with every behavioral change. Do not remove or weaken tests/quality gates to obtain green output.
4. Treat log data as untrusted. Never execute it, interpret it as Rich markup, or expose full sensitive lines in ordinary errors.
5. Keep JSON/CSV schemas deterministic and stdout data-only; send diagnostics to stderr.
6. Profile before performance optimization and record actual commands/results. Do not claim the 1 GB target without measured evidence from the exact candidate.
7. Before a commit, run the verification commands for the active step; before release, run the complete gate in `IMPLEMENTATION_PLAN.md`.
8. At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Structure

```text
src/nginx_insights/     # package: CLI, parser, models, aggregation, output, errors
tests/                  # unit, integration, fixtures, and marked performance tests
docs/PERFORMANCE.md     # reproducible performance evidence once implemented
pyproject.toml          # package, tools, and console entry point
```

Do not create product modules ahead of their numbered implementation step.

## Commands Once Implemented

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy src/nginx_insights
pytest -q --cov=nginx_insights --cov-report=term-missing --cov-fail-under=90
python -m build
```

The separately marked 1 GB performance acceptance is required for release but should not run in the ordinary fast test suite.

## Implementation Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Help/version/options tests |
| 2 | Models and parser | Not started | Parser tests, Ruff, mypy |
| 3 | Streaming metrics | Not started | Aggregation and cardinality tests |
| 4 | Rich terminal output | Not started | Safe/color terminal tests |
| 5 | JSON and CSV | Not started | Parsed schema and quoting tests |
| 6 | End-to-end exit behavior | Not started | Integration coverage for `0/1/2/3/4` |
| 7 | Quality and documentation | Not started | Full suite, coverage, build checks |
| 8 | Performance and release candidate | Not started | Recorded 1 GB time/RSS and clean install |

No row may be marked complete from narration alone; attach the named command output or artifact and keep failed checks visible.

