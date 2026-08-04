# Project Memory: Nginx Stream Analyzer

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE users that streams nginx combined access logs. Required metrics are top-10 IPs, top-10 4xx/5xx URLs, 24 hourly percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV support pipelines. The performance target is 1 GB in under 30 seconds on a documented laptop.

## Non-Negotiable Rules

- Treat `PRD.md` and `PROJECT_ARCHITECTURE.md` as the specification source of truth.
- Keep WIP at one and follow `IMPLEMENTATION_PLAN.md` in dependency order.
- Use Python 3.11, Click, Rich, dataclasses, and pip packaging.
- Use stateless single-process streaming; do not retain raw lines.
- Do not add auth, a database, HTTP API, server, cloud, Docker, or Kubernetes.
- Hourly distribution is a percentage: `100 × hourly_request_count / total_valid_requests`.
- Preserve the complete exits: `0` success, `1` unexpected runtime/output failure, `2` usage error, `3` input failure, `4` unique-cardinality exhaustion for exact IP, error-URL, or User-Agent limits. Never omit or remap 4.
- Change the specification before changing a public behavior contract.
- End each implementation step with its listed executable verification evidence.
- At the end of every session or meaningful block of work, save context via `/session-save`.

## Planned Structure

```text
src/nginx_stream_analyzer/
  cli.py models.py parser.py aggregate.py input.py errors.py
  render/text.py render/json.py render/csv.py
tests/
  fixtures/ golden/ and contract/unit/integration tests
benchmarks/
  deterministic generator, runner, and RESULTS.md
```

## Step Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package and contracts | Not started |
| 2 | Streaming parser | Not started |
| 3 | Aggregation and cardinality guard | Not started |
| 4 | Rich output | Not started |
| 5 | JSON and CSV | Not started |
| 6 | Input and failures | Not started |
| 7 | Performance proof | Not started |
| 8 | Quality gate | Not started |
| 9 | Packaging and handoff | Not started |

## Current Status

The Full blueprint documents are complete and contract-checked. No product code exists; the next authorized implementation action would be Step 1.
