# Nginx Lens Project Instructions

## Context and authority
Documentation-only blueprint for a weekend, $0, local DevOps/SRE CLI. Product code is not implemented. [PRD](PRD.md) is the product acceptance source; [architecture](PROJECT_ARCHITECTURE.md) is the technical contract. Also read [strategy](STRATEGIC_PLAN.md), [plan](IMPLEMENTATION_PLAN.md), [guide](CLAUDE_CODE_GUIDE.md), and [README](README.md). Change the specification before changing behavior; keep agent rules centralized here while preserving applicable AGENTS.md rules.

## Stack and boundaries
Python 3.11, Click, Rich, dataclasses, pip; one process. No authentication, database, HTTP API, server, cloud, Kubernetes, telemetry, or persisted run state. No product implementation is authorized by the blueprint task. Never publish, push, migrate, delete or send data externally without applicable human authorization.

## Implementation invariants
Read bounded lines; aggregate exactly with independent default caps of 100000 IPs, error paths, and User-Agents. No top-ten-only counting, silent eviction or approximate unique counts. Return code 4 on cap exhaustion with no report. Full contract: 0 success/help/version; 1 IO/output/runtime failure; 2 usage; 3 invalid log data; 4 unique-cardinality exhaustion. Sanitize terminal controls and never print raw failed log lines. Machine output and diagnostics use separate streams.

Hourly distribution = `100 × hourly_request_count / total_valid_requests`; UTC hours 00–23, zero for empty input. Unique UA share = `100 × unique_user_agents / total_valid_requests`, missing UAs excluded only from numerator. Follow architecture for all parsing and sorting semantics.

## Planned structure
`src/nginx_lens/{cli,errors,reader,parser,models,aggregate,render}.py`; `tests/` golden/CLI/unit tests; `benchmarks/` generator, runner and measured results; `pyproject.toml` package metadata. These paths are plans, not existing product code.

## Step status
| Step | Work | Status |
|---|---|---|
| 1 | Package/errors | Not started |
| 2 | Models/fixtures | Not started |
| 3 | Reader/parser | Not started |
| 4 | Exact analytics | Not started |
| 5 | Terminal integration | Not started |
| 6 | JSON/CSV | Not started |
| 7 | Benchmark | Not started |
| 8 | Local readiness | Not started |

## Working rules
WIP=1. Add meaningful tests with implementation and execute them before reporting completion or committing. Future readiness requires full pytest suite, branch coverage target 90%, isolated wheel smoke tests, and measured benchmark results. Do not represent targets or written tests as evidence. No code tests or performance benchmarks have run during blueprint authoring. Independent Devil's Advocate review is pending external harness execution; no review artifact or verdict was produced here.

At the end of each session or significant block of work, save context through `/session-save` using the repository-local skill. Record actual evidence and one explicit next action. Do not mark implementation steps complete merely because their documents exist.
