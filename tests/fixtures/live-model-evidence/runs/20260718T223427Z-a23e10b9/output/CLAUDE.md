# Project Memory: nginx-log-report

## Product context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers. It streams nginx common/combined access logs and reports top 10 IPs, top 10 request targets producing 4xx/5xx responses, 24 hourly request buckets, and distinct User-Agent share. Default output is Rich terminal text; `--json` and `--csv` are stable pipeline formats.

The repository is currently in blueprint-only state. No product code exists or is authorized by the blueprint task.

## Durable sources of truth

1. `PRD.md` — behavior, priorities, acceptance, and kill criteria.
2. `PROJECT_ARCHITECTURE.md` — runtime boundaries, exact parsing/resource/output contracts, and ADR.
3. `IMPLEMENTATION_PLAN.md` — dependency order, file scope, commands, and evidence gates.
4. `STRATEGIC_PLAN.md` — product rationale, competitors, KPIs, risks, budget, MoSCoW, and RICE.
5. `CLAUDE_CODE_GUIDE.md` — bounded implementation prompts.

Update specifications before changing behavior. Architecture is authoritative when a lower-level document is ambiguous; reconcile contradictions rather than guessing.

## Non-negotiable architecture

- One synchronous local process: buffered byte input → parser → exact aggregator → canonical report → one renderer.
- **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- No authentication, server, daemon, cloud service, Docker runtime, Kubernetes, or network dependency.
- Python 3.11, Click, Rich, dataclasses, pip wheel/sdist.
- Exact results inside the documented record/field and 500,000 summed-distinct-value envelope; never silently approximate.
- Diagnostics go to stderr; report data goes to stdout. JSON/CSV never contain ANSI bytes.
- Treat all log fields as untrusted. Apply the architecture's terminal sanitizer and never echo malformed raw records.
- The official performance gate is the exact deterministic 1 GiB end-to-end benchmark protocol, not extrapolation.

## Planned structure

```text
src/nginx_log_report/   package and console command
src/nginx_log_report/renderers/   text, JSON, CSV
tests/                  parser, aggregate, renderer, CLI, performance evidence
scripts/                deterministic benchmark generator
BENCHMARK.md             reference-machine performance record
```

Do not create database schemas, endpoints, containers, deployment manifests, or product features outside the PRD.

## Engineering rules

- Preserve WIP=1: only one implementation-plan step may be active.
- Use test fixtures that are deterministic, minimal, and free of real log data/secrets.
- Tie ordering is descending count then lexical key.
- Source timestamp hour is used without host-timezone conversion.
- User-Agent share denominator includes only valid records with non-empty User-Agent.
- A dash request remains valid but contributes no error URL.
- Structured schema changes require PRD/architecture review and an explicit version decision.
- Do not optimize before profiling; do not weaken correctness or evidence for speed.
- Never claim completion without actual command output and required benchmark/artifact evidence.
- At the end of every session or meaningful work block, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Implementation status

| Step | Unit | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI surface | Not started | Install, help, CLI tests |
| 2 | Dataclasses and errors | Not started | Model tests, compileall |
| 3 | Byte-level parser | Not started | Parser tests and ≥90% parser coverage |
| 4 | Exact aggregations | Not started | Aggregation tests and ≥90% aggregation coverage |
| 5 | JSON/CSV renderers | Not started | Golden contract tests |
| 6 | Rich text and sanitizer | Not started | TTY/no-color/hostile-value tests |
| 7 | CLI integration | Not started | Integration and pipeline smoke tests |
| 8 | 1 GiB performance gate | Not started | Five-run timing/RSS benchmark record |
| 9 | Release candidate | Not started | Full suite, ≥90% coverage, built-wheel clean install |

Allowed statuses are `Not started`, `In progress`, `Blocked`, and `Verified`. `Verified` requires the evidence listed in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); narration alone never advances status.

## Current next action

When product implementation is separately authorized, start Step 1 only and follow the matching prompt in `CLAUDE_CODE_GUIDE.md`. Until then, keep this repository documentation-only.
