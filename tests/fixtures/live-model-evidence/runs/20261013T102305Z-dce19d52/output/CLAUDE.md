# Nginx Lens Project Memory

## Context

Local Python 3.11 CLI for DevOps/SRE engineers, with Click, Rich, and dataclasses. Analyze nginx combined access logs from a file or stdin and report top-10 IPs, top-10 error URLs, 24 UTC hourly percentages, and exact unique User-Agent share. Provide terminal, JSON, and CSV outputs; distribute through pip under MIT. Budget $0, implementation window one weekend.

This session produced planning documents only. No product source, test suite, wheel, or runtime performance evidence exists yet. Product priorities and the single-process architecture were pre-approved. Independent adversarial review is reserved for the external harness; no internal reviewer verdict is claimed.

## Source of Truth

- [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md): exact parsing, metrics, CLI, schemas, and resource contracts.
- [PRD.md](PRD.md): user stories and acceptance criteria; update the spec before changing behavior.
- [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md): scope, priorities, RICE, budget, risks, Definition of Done.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): eight dependency-ordered steps and checks.
- [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md): per-step implementation prompts.
- [README.md](README.md): intended user workflow, clearly labeled as not implemented.
- `.itd/`: project and verification contracts; `.itd-memory/`: canonical execution state and evidence.

## Rules

1. Keep WIP=1. Do not mark a step complete without real static/runtime evidence appropriate to that step and the verification contract.
2. No authentication, database, HTTP API, server, cloud, Kubernetes, persistent analytics state, telemetry, or network requirement.
3. Preserve exact metrics. Hourly percentage is `100 × hourly_request_count / total_valid_requests`; UA share is `100 × unique_user_agent_count / total_valid_requests`. Empty denominators yield 0. Unknown UAs remain in the denominator only.
4. Preserve exit codes **0/1/2/3/4**: 0 success/empty/help/version; 1 I/O/internal failure; 2 usage error; 3 malformed input; 4 unique-cardinality exhaustion from either configured key budget, with no report. Default malformed processing emits a report then returns 3; strict processing returns 3 without a report.
5. Never retain all input lines. Enforce bounded lines and aggregate key-count/key-byte limits. No silent approximation or truncated rankings.
6. Treat log strings as data: no Rich markup execution, terminal controls, shell execution, or raw-line diagnostics. Follow CSV protection and JSON raw-key semantics.
7. Keep project agent instructions centralized here, preserve existing AGENTS.md harness instructions, and use links to the specification instead of inventing inconsistent contracts elsewhere.
8. Before changing scope, update `.itd/SCOPE_LOCK.md` and reconcile the active unit in `.itd-memory/STATE.json`.
9. At the end of each session or significant block of work, save context through `/session-save`. If unavailable, write equivalent evidence and next-action state manually and disclose that fallback.
10. Do not create DEVILS_ADVOCATE_REVIEW.md or claim independent review in this blueprint session. External acceptance remains UNVERIFIED until the actual harness receipt exists.

## Planned Structure

`src/nginx_lens/`: cli.py, reader.py, parser.py, models.py, aggregate.py, render.py. `tests/`: correctness and CLI/installation checks with synthetic fixtures. `benchmarks/`: deterministic generator, timing runner, measured results. `pyproject.toml`: packaging and dependencies. These implementation paths do not yet exist.

## Step Status

| Step | Work | Status | Required evidence |
|---|---|---|---|
| 1 | Package and data contracts | Not started | Install/import/help tests |
| 2 | Reader and parser | Not started | Reader/parser boundary tests |
| 3 | Four metrics | Not started | Hand-audited metric fixture tests |
| 4 | Capacity guards | Not started | Boundary and atomicity tests |
| 5 | Output formats | Not started | Schema, quoting, and color tests |
| 6 | CLI integration | Not started | Complete 0/1/2/3/4 failure-path tests |
| 7 | Performance/security boundaries | Not started | Real benchmark and hostile-input evidence |
| 8 | Local wheel/handoff | Not started | Clean install, coverage, reviews, build |

## Verification and Next Action

For the blueprint, consult `.itd-memory/blueprint-validation.md` and `ITD_REPORT.md` for static checks actually performed. Planned commands are not test evidence. The unconfigured project verification contract and missing independent receipt cannot be represented as a passed acceptance gate.

Next action: external harness runs its fresh adversarial reviewer and final-file validation. Then reconcile any findings before starting Step 1 in a separately authorized implementation session. Do not implement product code as part of this blueprint request.
