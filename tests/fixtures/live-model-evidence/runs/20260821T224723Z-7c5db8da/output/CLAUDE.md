# CLAUDE.md — logpulse project memory

<!-- itd:brownfield is NOT set: this is a greenfield project planned via /blueprint --full. -->

## Context

`logpulse` is a local Python 3.11 CLI for DevOps/SRE engineers. It streams an nginx access
log (file or stdin) and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly request
distribution (as a percentage), and the share of unique User-Agents. Default output is
colored terminal (Rich); `--json` and `--csv` support pipelines. Stateless single-pass
streaming; target 1 GB in under 30 seconds. $0 budget, open source, one-weekend delivery.

## Core rules

- **No database, no HTTP API, no server, no auth, no cloud, no Kubernetes.** The binding
  decision is: **"no database — stateless streaming processing; no HTTP API — CLI-only
  tool"** (see [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md#core-architectural-decision)).
- **Stack is fixed:** Python 3.11, Click, Rich, dataclasses, pip. Do not add other runtime deps.
- **Single-pass streaming.** Memory stays bounded (O(unique keys)), never O(lines).
- **Hourly distribution** is a percentage using the formula
  `100 × hourly_request_count / total_valid_requests` — not an unscaled fraction.
- **Exit-code contract is `0/1/2/3/4`** and must never be omitted or remapped:
  `0` success, `1` unexpected error, `2` usage error, `3` input error,
  `4` unique-cardinality exhaustion.
- **Spec is the source of truth.** Change the blueprint docs first, then the code.

## Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.11 |
| CLI | Click |
| Rendering | Rich |
| Data model | dataclasses |
| Packaging | pip / pyproject.toml |
| Tests | pytest |

## Structure

```
logpulse/  cli.py input.py parser.py models.py aggregate.py report.py render/{rich,json,csv}_out.py errors.py
tests/     test_parser.py test_aggregate.py test_cli.py fixtures/sample_access.log
```

## Step status

| Step | Description | Status |
|------|-------------|--------|
| 1 | Package skeleton, dataclasses, exit codes | ☐ Not started |
| 2 | Streaming file/stdin reader | ☐ Not started |
| 3 | Combined/common format parser | ☐ Not started |
| 4 | Single-pass aggregators | ☐ Not started |
| 5 | Report builder + hourly percentage | ☐ Not started |
| 6 | Rich/JSON/CSV renderers | ☐ Not started |
| 7 | CLI wiring + `0/1/2/3/4` exit codes | ☐ Not started |
| 8 | Tests, perf pass, packaging | ☐ Not started |

## Blueprint documents

- [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md)
- [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)
- [PRD.md](PRD.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md)

## Working agreement

- Plan before code; test every change; review before commit (WIP=1).
- At the end of each session or meaningful block of work, save context via `/session-save`.
