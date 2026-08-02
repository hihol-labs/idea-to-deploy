# Project Memory: nginx-log-report

## Context

This repository is planning a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It incrementally reads nginx combined access logs and reports top client IPs, top 4xx/5xx URLs, request counts by logged hour, and exact unique User-Agent diversity. Default output is Rich terminal text; JSON and CSV are stable pipeline formats.

The current repository state is blueprint-only. Do not imply that planned commands work until implementation and exact-candidate verification exist.

## Durable Sources of Truth

1. `AGENTS.md` and `.itd/` methodology contracts govern execution and verification.
2. `PRD.md` governs user-visible behavior and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` governs technical and CLI contracts.
4. `IMPLEMENTATION_PLAN.md` governs dependency order and step boundaries.
5. `STRATEGIC_PLAN.md` governs product scope and priorities.

If they conflict, stop implementation, reconcile the documents, scope lock, and active unit before changing code.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, pip installation.
- One local process and one streaming read pass.
- Exact P0 calculations with deterministic tie ordering.
- Default colored text plus `--json` and `--csv`.
- **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- No authentication, server, cloud, Kubernetes, telemetry, or recurring cost.
- Target exactly 1,000,000,000 bytes in under 30 seconds and <=2.0 GiB RSS on a documented reference laptop, plus the high-cardinality <=3.0 GiB RSS gate.
- Budget $0 and one-weekend MVP delivery.

## Engineering Rules

- Keep WIP=1 and execute one Implementation Plan step at a time.
- Treat all log content as untrusted data: no shell/eval, network calls, or Rich-markup interpretation.
- Keep diagnostics on stderr and machine-readable payloads on stdout.
- Never load the whole input file; do not add persistence or hidden caching.
- Preserve exact UA semantics and explicitly measure cardinality-related memory.
- Add or update acceptance tests before changing a documented behavior contract.
- Preserve unrelated worktree changes and do not weaken tests or gates.
- For completion, freeze the exact staged candidate, run its machine oracle, apply the risk-tier checker, and require a current revalidated adjudication receipt under `.itd/VERIFICATION_CONTRACT.json`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_log_report/
  __init__.py
  __main__.py
  cli.py
  models.py
  errors.py
  parser.py
  aggregate.py
  renderers/
tests/
  fixtures/
  golden/
  performance/
scripts/generate_benchmark_log.py
pyproject.toml
```

## Status

| Step | Scope | Status | Required evidence before completion |
|---:|---|---|---|
| Blueprint | Six required project documents plus workflow README/.gitignore | Complete (2026-08-02) | Root existence/content checks passed; no product code added |
| 1 | Package and CLI skeleton | Not started | Install/help/tests + adjudication receipt |
| 2 | Domain models and errors | Not started | pytest/mypy + receipt |
| 3 | Combined parser | Not started | parser tests/durations + receipt |
| 4 | Aggregation | Not started | focused coverage/tests + receipt |
| 5 | Terminal renderer | Not started | golden/TTY safety tests + receipt |
| 6 | JSON and CSV | Not started | schema/golden tests + receipt |
| 7 | End-to-end behavior | Not started | CLI/exit tests + receipt |
| 8 | Performance and robustness | Not started | recorded decimal 1 GB median/RSS + receipt |
| 9 | Release candidate | Not started | full quality/package gates + receipt |

## Current Next Action

After blueprint acceptance, update `.itd/SCOPE_LOCK.md` and the active Idea to Deploy unit for Implementation Plan Step 1, then execute only that step using [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md). Do not start product implementation as part of the blueprint task.
