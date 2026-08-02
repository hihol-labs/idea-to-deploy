# nginx-log-report Project Memory

## Context

Build a local open-source Python 3.11 CLI for DevOps/SRE engineers. It streams conventional nginx Combined Log Format input and reports top-10 client IPs, top-10 request targets producing 4xx/5xx, 24 hourly request buckets, and User-Agent diversity. Default output is colored terminal text; `--json` and `--csv` are pipeline contracts.

Current phase: blueprint complete; product implementation has not started.

## Source of Truth

1. `AGENTS.md` and `.itd/` define the engineering process and acceptance gates.
2. `PRD.md` defines observable behavior and priorities.
3. `PROJECT_ARCHITECTURE.md` defines parser, resources, CLI schemas, exit codes, and module boundaries.
4. `IMPLEMENTATION_PLAN.md` defines the WIP=1 sequence.
5. `STRATEGIC_PLAN.md` defines product boundaries, KPIs, and Definition of Done.

When behavior changes, update the specification first. Do not let generated code become the only source of product truth.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, pip-installable `src/` package.
- Single process and one pass over each input stream.
- No authentication, database, HTTP API, server, cloud, Docker, Kubernetes, telemetry, or retained state.
- `$0` infrastructure budget and one-weekend MVP.
- JSON/CSV stdout must contain machine data only; diagnostics use stderr.
- Exact metrics inside the documented 64 KiB/cardinality resource envelope; no silent approximation.
- Strict UTF-8 conventional Combined Log Format for MVP.
- Target representative 1 GB input in under 30 seconds with the benchmark protocol in the architecture.

## Planned Structure

```text
src/nginx_log_report/
  __init__.py
  __main__.py
  cli.py
  io.py
  parser.py
  aggregate.py
  errors.py
  render/
    __init__.py
    text.py
    json.py
    csv.py
tests/
benchmarks/
pyproject.toml
```

## Engineering Rules

- Preserve WIP=1 and update `.itd-memory/STATE.json` from evidence.
- Check `.itd/SCOPE_LOCK.md` before edits; reconcile scope before expanding it.
- Keep I/O, parsing, aggregation, rendering, and error mapping separate.
- Never use whole-file reads, a second input pass, per-line Rich rendering, shell execution, or network calls.
- Treat log fields as untrusted; bound input, escape Rich content, quote CSV, and avoid full-line diagnostics.
- Test JSON and CSV structurally, not only through snapshots.
- Benchmark before optimizing; architecture changes require an ADR/spec update.
- Freeze and verify the exact candidate with the `.itd/` Verification Loop; prose is not completion evidence.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Step Status

| Step | Deliverable | Status |
|---:|---|---|
| 1 | Installable CLI skeleton | Not started |
| 2 | Bounded input and combined-log parser | Not started |
| 3 | Exact streaming aggregator and early performance projection | Not started |
| 4 | JSON and CSV renderers | Not started |
| 5 | Rich terminal renderer | Not started |
| 6 | Failure and interruption semantics | Not started |
| 7 | Full 1 GB performance evidence | Not started |
| 8 | Release verification and documentation | Not started |

## Next Action

Start Step 1 only after opening a new active implementation unit and binding its acceptance/verification contract. Do not implement multiple steps in parallel.
