# Project Instructions: nginx-stream-stats

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx common/combined access logs and reports:

1. top 10 client IPs;
2. top 10 request targets by combined 4xx/5xx count;
3. 24 hourly request percentages; and
4. exact unique User-Agent share.

The default is colored Rich terminal text. `--json` and `--csv` are stable pipeline formats. The product is pip-installable, has a $0 budget and one-weekend delivery limit, retains no data, and targets a representative 1 GB input in under 30 seconds on a documented laptop.

## Sources of Truth

Read these before implementation:

1. `PRD.md` — product behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — authoritative metric, CLI, schema, failure, and component contracts.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 sequence and verification commands.
4. `CLAUDE_CODE_GUIDE.md` — bounded prompt for each implementation step.
5. `STRATEGIC_PLAN.md` — scope, prioritization, risks, and release Definition of Done.

When behavior changes, update the PRD/architecture contract first, then update code and tests. Do not create a competing contract in comments or a new instruction file.

## Non-negotiable Product Rules

- Use Python 3.11, Click, Rich, and standard-library dataclasses. Click and Rich are the only direct runtime dependencies.
- Keep one local process and one input pass. Do not retain parsed records.
- Do not add authentication, a database, HTTP API, server/daemon, cloud resource, Docker, Kubernetes, telemetry, or persistent state.
- Read one uncompressed file or stdin to EOF; do not mutate input.
- Rank top lists by descending count, then ascending exact key; combine 4xx and 5xx per request target.
- Calculate hourly percentages with exactly `100 × hourly_request_count / total_valid_requests`.
- Calculate unique User-Agent share with the denominator and missing-value semantics defined in `PROJECT_ARCHITECTURE.md`.
- Exact User-Agent cardinality stops at the configured ceiling; never silently approximate.
- Render all formats from one immutable report model. stdout is report-only; stderr is diagnostics-only.
- Treat all log-derived strings as untrusted data and escape them through the selected serializer/renderer.
- Do not implement native compressed input, custom formats, dashboards, geolocation, tail-follow reports, or other P2 scope during the MVP.

## Exit-code Contract

Every implementation guide, test, and user-facing help must use the complete mapping:

| Code | Meaning |
|---:|---|
| `0` | Successful complete report, help, or version |
| `1` | Input reached EOF with zero valid requests |
| `2` | Invalid command usage or option/configuration value |
| `3` | Input open/read failure, unexpected internal/runtime failure, or memory/resource failure outside the unique-UA ceiling |
| `4` | Unique-cardinality exhaustion |

Never omit or remap code 4. Codes 1, 2, 3, and 4 produce no partial report. Malformed lines alone do not fail a run that has at least one valid request.

## Planned Stack and Structure

```text
pyproject.toml
src/nginx_stream_stats/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregator.py
  metrics.py
  renderers/{__init__,terminal,json,csv}.py
tests/
  fixtures/
  test_parser.py
  test_aggregator.py
  test_metrics.py
  test_renderers.py
  test_cli.py
  test_performance.py
  test_packaging.py
```

Do not create product paths during blueprinting. During implementation, add only paths required by the active step.

## Engineering Workflow

1. Read the current scope in `.itd/SCOPE_LOCK.md` and reconcile the active unit before edits.
2. Work on exactly one `IMPLEMENTATION_PLAN.md` step at a time (WIP=1).
3. State which PRD criteria and architecture sections the step implements.
4. Add or update focused tests with the behavior change.
5. Run the step's exact verification commands; record actual output/status, not expectations.
6. Keep failures in recovery for the same step. Do not weaken gates, delete tests, or advance on narration.
7. Before release, freeze the exact candidate and run the full correctness, wheel-install, exit-code, and performance gates.

Mandatory continuity rule: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Testing and Quality Rules

- Parser tests cover common/combined formats, time zones, IPv4/IPv6 tokens, request/status boundaries, missing User-Agent, malformed and hostile text.
- Aggregate tests use independently stated expected values and cover status 399/400/599, deterministic ties, every hour, empty error lists, cardinality at and over the ceiling.
- Renderer tests parse JSON/CSV back, reject ANSI in pipeline formats, verify CSV quoting/final newline, and prove metric equivalence.
- CLI subprocess tests prove file/stdin, stdout/stderr separation, atomic failure output, and exact exits `0/1/2/3/4`.
- Packaging verification installs the built wheel in a fresh Python 3.11 environment.
- The performance claim requires an exact 1 GB run on a named laptop plus correctness comparison and peak-RSS capture. Do not extrapolate from smaller files.
- Do not commit generated 1 GB data. Label any generated fixture as synthetic benchmark data, never real production data.

## Security and Privacy Rules

- Never execute or dereference input-derived URLs/User-Agents or interpolate them as markup/format strings.
- Never echo complete raw malformed lines in diagnostics.
- Never send network traffic or telemetry.
- Avoid temporary raw-log copies and cleanly close only streams owned by the CLI.
- Review direct/transitive dependencies and licenses before release.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package skeleton and CLI contract | Not started | Fresh editable install, packaging/CLI tests, help output |
| 2 | Domain models and parser | Not started | Parser suite passing |
| 3 | Streaming aggregation and metrics | Not started | Aggregate/metric suite including code-4 boundary |
| 4 | Rich terminal renderer | Not started | Terminal/color/markup tests |
| 5 | JSON and CSV renderers | Not started | Parse-back, golden, and equivalence tests |
| 6 | End-to-end I/O and failure semantics | Not started | Subprocess matrix for `0/1/2/3/4` and atomic output |
| 7 | Correctness, security, and packaging | Not started | Full suite and clean wheel smoke test |
| 8 | Performance and release evidence | Not started | Correct 1 GB run under 30 seconds on declared laptop |

Blueprint status: documentation only; no product code has been implemented.

## Definition of Ready for the Next Step

- Active-step scope is explicit.
- Prior-step verification is current and recorded.
- Relevant PRD acceptance criteria and architecture contracts are named.
- No unresolved failure is being bypassed.
- The next step does not expand Must/Should/Could/Won't scope without updating the specifications.
