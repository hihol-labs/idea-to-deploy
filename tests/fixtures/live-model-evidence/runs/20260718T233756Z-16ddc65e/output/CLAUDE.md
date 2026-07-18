# Nginx Log Lens Project Memory

## Context

Build a local open-source Python 3.11 CLI for DevOps/SRE engineers that streams
nginx access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly
request distribution, and unique User-Agent share. Default output is colored
terminal text; JSON and CSV support pipelines. Target: 1 GB in under 30 seconds
on a documented laptop, $0 budget, one-weekend delivery.

## Governing sources

1. `AGENTS.md`, `.itd/`, and `.itd-memory/` govern execution and evidence.
2. `PRD.md` owns behavior and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` owns technical and interface decisions.
4. `STRATEGIC_PLAN.md` owns scope, priorities, KPIs, and risks.
5. `IMPLEMENTATION_PLAN.md` owns step order and verification commands.

When behavior changes, update specifications before product code. Preserve one
active unit (WIP=1), and never mark a step complete from narration alone.

## Fixed decisions

- Python 3.11, Click, Rich, dataclasses, pip installation.
- Single local process, one-pass streaming aggregation.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- File or stdin input; stdout report; stderr diagnostics.
- Rich text default; versioned, ANSI-free JSON and CSV.
- Do not silently change exact User-Agent semantics or performance criteria.

## Planned structure

```text
src/nginx_log_lens/
  cli.py input.py parser.py models.py aggregate.py errors.py
  renderers/text.py renderers/json.py renderers/csv.py
tests/
  contracts/ integration/ fixtures/
benchmarks/
```

## Engineering rules

- Never retain all input lines or materialize normalized logs.
- Keep Click/Rich at adapter boundaries; parser and aggregator remain testable
  domain modules.
- Deterministic ranking: count descending, key ascending.
- Treat log bytes and fields as untrusted data; never execute or transmit them.
- JSON/CSV stdout must contain only the selected format; diagnostics use stderr.
- Run the verification commands named by the active step and retain evidence.
- Do not publish packages, create cloud resources, or make external changes
  without explicit authorization.
- At the end of every session or meaningful block of work, save context through
  `/session-save`.

## Status

| Step | State | Evidence required |
|---:|---|---|
| Blueprint documents | Complete | Required root files exist and blueprint checks pass |
| 1. Package skeleton | Not started | Install, CLI tests, help command |
| 2. Domain contracts | Not started | Contract tests and type check |
| 3. Streaming parser | Not started | Parser/input tests and lint |
| 4. Aggregation | Not started | Aggregation/streaming tests and type check |
| 5. Rich text | Not started | Renderer/CLI tests and manual fixture run |
| 6. JSON/CSV | Not started | Renderer tests and JSON parse check |
| 7. Failure flows | Not started | Integration suite and malformed stdin run |
| 8. Performance | Not started | Recorded 1 GB wall time and peak RSS |
| 9. Release handoff | Not started | Full tests, static checks, build, package validation |

## Current handoff

The blueprint is the only completed unit. No product code exists. The next
authorized implementation action, when requested, is Step 1 in
`IMPLEMENTATION_PLAN.md`.

