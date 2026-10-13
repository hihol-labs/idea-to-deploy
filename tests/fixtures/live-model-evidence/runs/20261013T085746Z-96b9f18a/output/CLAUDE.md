# Nginx Lens Project Context

## Status and Sources of Truth

Blueprint documents are prepared; no product code, runtime tests, benchmarks, or release artifacts exist yet. External adversarial review is pending in a separate harness session. Do not claim an independent review ran here.

[PRD.md](PRD.md) defines acceptance criteria. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) defines technical and serialization contracts. Reconcile conflicts in the specifications before implementing. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) defines priorities; [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) defines step order; [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) contains ready-to-run prompts; [README.md](README.md) describes intended usage.

## Product and Stack

Local open-source Python 3.11 CLI for DevOps/SRE. Click commands, Rich terminal tables, dataclasses, standard-library JSON/CSV, pip packaging. Single-process streaming of nginx combined logs. No authentication, database, HTTP API, server, cloud, or Kubernetes. Budget $0; one weekend.

## Rules

- Keep WIP=1. Update scope and canonical state before changing scope.
- Treat specs as durable source; change behavior contracts before code.
- Preserve exit codes 0/1/2/3/4: success / operational failure / usage error / skipped malformed lines / unique-cardinality exhaustion.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`; UA percentage is distinct nonmissing strings divided by valid requests times 100. Use UTC hours and zero-safe denominators.
- Exact dictionary/set aggregation is bounded by the shared --max-unique budget, not by input bytes. Never silently approximate or spill to storage.
- Keep diagnostics on stderr, reports on stdout, and machine formats free of ANSI. Never execute or interpret log content as instructions or markup.
- Attach actual test/benchmark evidence before marking implementation work complete; no fabricated performance or review claims.
- At the end of every session or significant block of work, save context through `/session-save`. If unavailable, write equivalent status, evidence, and next action into `.itd-memory/STATE.json` and `ITD_REPORT.md` without claiming the skill ran.

## Planned Structure

`src/nginx_lens/`: cli.py, reader.py, parser.py, models.py, aggregate.py, render.py. `tests/`: unit/integration tests and synthetic fixtures. `benchmarks/`: deterministic generator, timing runner, results. `pyproject.toml`: build metadata and console entry point. These are planned paths, not present implementation.

## Implementation Status

| Step | Deliverable | Status |
|---|---|---|
| 1 | Package and CLI skeleton | Not started |
| 2 | Bounded parser | Not started |
| 3 | Exact metrics/resource guard | Not started |
| 4 | Terminal report | Not started |
| 5 | JSON/CSV | Not started |
| 6 | Failure/integration tests | Not started |
| 7 | Performance evidence | Not started |
| 8 | Local release candidate | Not started |

Next action: external harness architecture review, then implement Step 1 with its specified checks. Canonical execution state is `.itd-memory/STATE.json`; `.itd/` remains the project verification contract. This file is the single generated project instruction file; preserve existing AGENTS.md harness instructions.
