# Project Memory: nginx-log-top

## Context

This repository is planned as a local Python 3.11 CLI for DevOps/SRE nginx access-log triage. It streams one supported combined-format input and reports top-10 IPs, top-10 4xx/5xx URLs, 24 hourly buckets, and exact unique User-Agent share. Terminal output is default; JSON and CSV are stable pipeline interfaces.

## Non-Negotiable Decisions

- Single-process, stateless streaming architecture.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Python 3.11, Click, Rich, dataclasses, pip installation.
- $0 budget, open source, one-weekend delivery.
- Performance claim: a content-hashed 1 GB fixture in under 30 seconds on a recorded reference laptop.
- Product behavior changes start in `PRD.md`; architecture changes require an ADR in `PROJECT_ARCHITECTURE.md`.

## Planned Structure

```text
src/nginx_log_top/
  __init__.py
  __main__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  render/{__init__,terminal,json,csv}.py
tests/
  fixtures/
  golden/
tools/generate_benchmark_fixture.py
```

No product-code paths exist at blueprint completion; this tree is a plan.

## Engineering Rules

- Follow `AGENTS.md`, `.itd/` contracts, and `.itd-memory/` state; preserve WIP=1.
- Work one [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) step at a time.
- Treat log input as untrusted data; never evaluate it, shell it, fetch from it, or pass it as Rich markup.
- Preserve streaming iteration and deterministic sort semantics.
- Keep stdout machine-readable and send diagnostics/errors to stderr.
- Require real tests and exact-candidate verification evidence before marking a step complete.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Status

| Step | State | Evidence/next action |
|---:|---|---|
| Blueprint | Complete | Required files verified; Devil's Advocate conditions incorporated |
| 1. Package skeleton | Not started | Use Step 1 prompt in `CLAUDE_CODE_GUIDE.md` |
| 2. Models/fixtures | Not started | Blocked by Step 1 |
| 3. Parser | Not started | Blocked by Step 2 |
| 4. Aggregation | Not started | Blocked by Step 3 |
| 5. Input/errors | Not started | Blocked by Step 4 |
| 6. Terminal output | Not started | Blocked by Step 5 |
| 7. JSON/CSV | Not started | Blocked by Step 6 |
| 8. Release evidence | Not started | Blocked by Step 7 |

## Document Map

- Strategy and priorities: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md)
- Architecture and CLI contract: [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)
- Behavioral requirements: [PRD.md](PRD.md)
- Ordered work: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Step prompts: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md)
