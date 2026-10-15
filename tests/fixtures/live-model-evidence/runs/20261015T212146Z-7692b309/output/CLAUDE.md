# Project Instructions: nginx-stream-report

## Project Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly request distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV support pipelines. The MVP budget is $0 and delivery is one weekend.

## Sources of Truth

Read these before implementation, in this order:

1. `PRD.md` — behavior, priorities, and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — metric, schema, module, and CLI contracts.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered steps and verification.
4. `CLAUDE_CODE_GUIDE.md` — bounded prompt for the active step.
5. `STRATEGIC_PLAN.md` — product intent, risks, and success criteria.

When behavior changes, update the specification first and reconcile every affected document before changing code.

## Non-negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, a `src` layout, and pip packaging.
- Keep the product a single local process with stateless streaming processing.
- Do not introduce authentication, a database, an HTTP API, a server, cloud resources, Docker, or Kubernetes.
- Do not retain raw log records; treat every log-derived string as untrusted.
- Keep terminal, JSON, and CSV outputs deterministic and keep diagnostics on stderr.
- Preserve the complete exit-code contract `0/1/2/3/4`: `0` success; `1` input/I/O/decoding or unexpected runtime failure; `2` CLI usage error; `3` strict parse failure; `4` unique-cardinality exhaustion.
- Write tests with new behavior and run the relevant suite before committing.
- Never claim the 1 GB/30 s target from estimates; record a real benchmark and environment.
- Do not implement P1/P2 work until all P0 release acceptance criteria pass.
- At the end of every session or meaningful block of work, save context with `/session-save`.

## Intended Repository Structure

```text
src/nginx_stream_report/    # package, CLI, parser, aggregation, renderers
tests/                      # unit, CLI, renderer, integration, performance tests
docs/BENCHMARK.md           # reproducible performance evidence
pyproject.toml              # package, dependencies, entry point, tool config
README.md                   # user-facing install and usage
```

## Active Delivery Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package and CLI contracts | Not started |
| 2 | Models, fixtures, and errors | Not started |
| 3 | Combined-log parser | Not started |
| 4 | Streaming aggregation | Not started |
| 5 | Terminal/JSON/CSV renderers | Not started |
| 6 | I/O and exit behavior | Not started |
| 7 | Performance/resource proof | Not started |
| 8 | Release verification/docs | Not started |

Only one step may be active at a time. Update this table after verified work, not from narration.

## Standard Verification

Use the step-specific commands in `IMPLEMENTATION_PLAN.md`. The eventual baseline is:

```bash
python3.11 -m pytest -q
python3.11 -m build
nginx-stream-report --help
```

Record actual command outcomes. A skipped or unavailable check is not a pass.
