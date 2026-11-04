# Nginx Lens: Project Instructions

## Context and Source of Truth

Local nginx combined-log CLI for DevOps/SRE engineers. Python 3.11, Click, Rich, dataclasses; pip-installable. $0 and one weekend. This session produces documentation only; product code is not implemented.

Read [PRD.md](PRD.md) for acceptance criteria, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for interface contracts, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities, [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for step checks, [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for prompts, and [README.md](README.md) for intended usage. Update the spec before changing behavior. Keep agent rules in this file, without duplicating them across new instruction files. Existing AGENTS.md and project contracts remain applicable.

## Rules

- WIP=1. Implement one approved step at a time; unrelated work belongs in backlog.
- No authentication, database, HTTP API, server, cloud, Kubernetes, persistence, or telemetry.
- Read input incrementally; exact aggregates are bounded by the combined unique-key budget. Do not silently approximate or evict keys.
- Preserve all exits 0/1/2/3/4: clean completion / operational failure / usage error / malformed input with completed report / unique-cardinality exhaustion with no report. Match architecture precedence and output-write caveats.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`, using UTC. Unique-UA percentage uses distinct nonmissing agents divided by valid requests, multiplied by 100. Zero denominators produce zero.
- Add meaningful tests to new product code and run the suite before committing. No claimed performance without measured benchmark evidence.
- Obtain human confirmation before irreversible or external actions, including publishing, deploy, push/PR, deletion, money or production changes. Keep secrets out of outputs and egress.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.
- Save decisions to `.itd/DECISIONS.md`; record actual checks and next action in local continuity. Do not treat narration as a verified transition.

## Planned Structure

`pyproject.toml`; `src/nginx_lens/cli.py`, `input.py`, `parser.py`, `models.py`, `aggregate.py`, `render.py`; `tests/`; `benchmarks/`. These paths are future implementation artifacts.

## Step Status

| Step | Deliverable | Status |
|---|---|---|
| 1 | Packaging and interface | Not started |
| 2 | Streaming parser | Not started |
| 3 | Exact capped aggregation | Not started |
| 4 | Terminal output | Not started |
| 5 | JSON | Not started |
| 6 | CSV | Not started |
| 7 | Failure matrix and integration | Not started |
| 8 | Benchmark and local wheel | Not started |

## Current Handoff

Blueprint candidate is prepared for document checks and the separate external harness architecture review. No adversarial or independent reviewer ran in this session. Next: external harness reviews the final documents in a fresh session; subsequent implementation follows step 1 after any required specification corrections. Tests and benchmark commands in the plan are future checks and have not run against product code.
