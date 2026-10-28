# Project Instructions: nginx-stream-report

## Context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs and reports top IPs, top 4xx/5xx URLs, hourly percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV are pipeline contracts. The target is 1 GB under 30 seconds on a documented laptop.

## Source of Truth

Read documents in this order before implementation:

1. `PRD.md` for behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` for component, metric, CLI, output, and failure contracts.
3. `IMPLEMENTATION_PLAN.md` for current step and verification commands.
4. `CLAUDE_CODE_GUIDE.md` for a replayable step prompt.
5. `STRATEGIC_PLAN.md` for priorities and Definition of Done.

When behavior changes, update the specification first and then adjust implementation and tests. Do not silently make implementation the specification.

## Non-Negotiable Rules

- Preserve the single-process, stateless streaming design.
- Do not add authentication, a database, an HTTP API, server, cloud service, Kubernetes, or product-code persistence.
- Use Python 3.11, Click, Rich, and dataclasses; keep the package installable with pip.
- Process sequentially and do not retain input records after aggregation.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Preserve exit codes: `0` success, `1` unexpected internal failure, `2` usage/option error, `3` input/read/parse processing failure, and `4` unique-cardinality exhaustion.
- Add tests with every behavior change and run the relevant suite before calling work complete.
- Ground every progress claim in output from the current session; say clearly when a check was skipped or failed.
- Never commit with a red required test layer unless an explicit methodology bypass is recorded.
- Require explicit human confirmation before publishing, pushing, opening a PR, deleting data, spending money, or any deployment/external action.
- Never print or transmit secrets or raw logs outside the local process.
- At the end of every session or significant block of work, save context through `/session-save`.

## Planned Structure

```text
src/nginx_stream_report/   Python package
tests/                     unit, CLI, integration, and performance tests
docs/PERFORMANCE.md        measured benchmark evidence
pyproject.toml             package, dependencies, and tool configuration
```

## Work Status

| Step | Scope | Status |
|---:|---|---|
| 0 | Blueprint documents | Complete |
| 1 | Installable package scaffold | Not started |
| 2 | Models and failure mapping | Not started |
| 3 | Combined-log parser | Not started |
| 4 | Streaming aggregation | Not started |
| 5 | JSON and CSV renderers | Not started |
| 6 | Rich output and complete CLI | Not started |
| 7 | Integration and quality checks | Not started |
| 8 | 1 GB performance evidence | Not started |
| 9 | Local release candidate | Not started |

WIP is one step. Update this table only after the step's verification commands pass; narration alone is not completion evidence.

