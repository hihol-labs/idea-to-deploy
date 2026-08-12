# Claude Code Implementation Guide: Nginx Stream Insights

## 1. How to Use This Guide

This file contains execution prompts for a future implementation session. Run one step at a time in the order shown, preserving WIP=1. Before each step, read `AGENTS.md`, `.itd/` contracts, `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, `IMPLEMENTATION_PLAN.md`, and `CLAUDE.md`. Reconcile the active Idea to Deploy unit and scope lock before edits. Do not implement P1/P2 work while a P0 unit is active.

After each step, freeze the exact candidate, run the machine oracle named by the project's verification contract, apply the risk-tier checker, and accept the step only from a current revalidated adjudication receipt. Record commands and results; narration alone is not completion.

## 2. Non-Negotiable Product Contract

- Local Python 3.11 CLI using Click, Rich, and dataclasses; pip-installable.
- Single-process, single-pass streaming with no retained raw records.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- Exact top 10 IPs, exact top 10 URLs for combined 4xx/5xx counts, all 24 hourly buckets, and exact unique User-Agent count/share.
- Hourly percentage must be computed as `100 × hourly_request_count / total_valid_requests`.
- JSON and CSV are data-only and contain no ANSI escape sequences; diagnostics go only to stderr.
- `--max-unique` applies independently to IP, error-URL, and User-Agent state. Never approximate, truncate, or evict silently.

### Complete exit-code contract

| Code | Meaning |
|---:|---|
| `0` | Success or informational command |
| `1` | Unexpected runtime or output failure |
| `2` | CLI usage/configuration error |
| `3` | Input/read/decode/data failure, including zero valid records |
| `4` | Unique-cardinality exhaustion |

Code 4 is reserved for unique-cardinality exhaustion. Every implementation step, wrapper, test, and document must preserve all five codes `0/1/2/3/4` without omission or remapping.

## 3. Step Prompts

### Prompt 1 — Package skeleton and quality gates

> Execute only Step 1 of `IMPLEMENTATION_PLAN.md`. Establish `pyproject.toml`, the `src/nginx_insight` package, Click entry point, and test/quality configuration. Keep runtime behavior to help/version and validation scaffolding; do not begin parsing or aggregation. Add tests for option mutual exclusion and positive `--max-unique`. Verify installation and the commands listed in Step 1. Preserve the complete `0/1/2/3/4` contract, with code 4 reserved for unique-cardinality exhaustion. Reconcile Idea to Deploy state and return the current exact-candidate verification receipt evidence, or label the unit not accepted.

### Prompt 2 — Models, errors, and fixtures

> Execute only Step 2 of `IMPLEMENTATION_PLAN.md`. Add slotted dataclasses and a typed error taxonomy that maps internal/output failure to 1, Click usage to 2, input/data failure to 3, and cardinality exhaustion to 4. Create compact, declared golden fixtures; never label synthetic fixtures as production data. Do not implement the parser or aggregator. Run the Step 2 checks and exact-candidate Verification Loop before accepting the unit.

### Prompt 3 — Streaming input and parser

> Execute only Step 3 of `IMPLEMENTATION_PLAN.md`. Implement ordered buffered file/stdin iteration and the combined-log parser exactly as specified in `PROJECT_ARCHITECTURE.md` section 5. Do not read a whole input, normalize URLs, normalize timestamp offsets, or leak raw lines in diagnostics. Cap malformed-line diagnostic samples. Cover quoting, offsets, status parsing, stdin, fatal decode/read errors, and zero-valid semantics. Preserve exit code 3 for input/data failure and the full `0/1/2/3/4` contract. Run the named checks and exact-candidate verification.

### Prompt 4 — Aggregation and cardinality

> Execute only Step 4 of `IMPLEMENTATION_PLAN.md`. Implement one-pass exact aggregation, deterministic top-10 ties, 24 hourly buckets, and User-Agent uniqueness. Use the literal hourly formula `100 × hourly_request_count / total_valid_requests`. Enforce `--max-unique` independently before insertion into each distinct-key collection; updates at the ceiling remain valid. On exhaustion, emit no partial report and preserve exit code 4. Do not add approximate algorithms or persistence. Run coverage and boundary tests, then the exact-candidate verification route.

### Prompt 5 — Rich text

> Execute only Step 5 of `IMPLEMENTATION_PLAN.md`. Render the canonical report with four labeled Rich sections and totals. Keep calculations out of the renderer. Implement TTY-aware color plus `NO_COLOR` and explicit option precedence. Escape markup and control sequences in untrusted values. Preserve stdout/stderr separation and all exit codes `0/1/2/3/4`, especially code 4 for cardinality exhaustion. Run the named renderer/security-oriented fixtures and exact-candidate verification.

### Prompt 6 — JSON and CSV

> Execute only Step 6 of `IMPLEMENTATION_PLAN.md`. Implement JSON `schema_version: 1` and normalized CSV `metric,key,count,percentage` exactly as specified under `PROJECT_ARCHITECTURE.md` `## CLI Interface`. Emit all 24 hours, authoritative counts, and derived percentages; use `100 × hourly_request_count / total_valid_requests`. Use standard encoders and never emit ANSI or diagnostics to stdout. Add golden/schema/parity tests. Do not change the report model or exit-code mapping without updating the source specifications first. Verify the exact candidate.

### Prompt 7 — CLI integration

> Execute only Step 7 of `IMPLEMENTATION_PLAN.md`. Compose input, parser, aggregator, and exactly one renderer in `cli.py`. Assert stdout/stderr isolation and map 0 success, 1 unexpected/output failure, 2 usage/configuration, 3 input/read/decode/data failure, and 4 unique-cardinality exhaustion. Handle normal closed pipes quietly and expected errors without tracebacks. Exercise file, stdin, malformed mixtures, format conflicts, all five exit codes, and no-partial-report exhaustion. Run the named integration checks and the required exact-candidate adjudication route.

### Prompt 8 — Acceptance and release evidence

> Execute only Step 8 of `IMPLEMENTATION_PLAN.md`. Add end-to-end tests, implementation README, deterministic benchmark generator/protocol, build checks, and clean-wheel installation evidence. Measure the declared representative 1 GB fixture with hardware, Python version, command, elapsed time, and peak RSS. Profile only if the baseline misses the target. Confirm the hourly formula `100 × hourly_request_count / total_valid_requests` and the entire `0/1/2/3/4` contract; code 4 must mean unique-cardinality exhaustion. Freeze the exact release candidate, run its machine oracle and risk-tier checker, and accept only a current revalidated adjudication receipt.

## 4. Review Prompt

> Review the exact candidate against `PROJECT_ARCHITECTURE.md`, every P0 criterion in `PRD.md`, and `IMPLEMENTATION_PLAN.md`. Prioritize correctness, unbounded memory, parsing ambiguity, stdout contamination, terminal/CSV injection, percentage semantics, deterministic ties, and exit-code drift. Explicitly verify that the hourly percentage is `100 × hourly_request_count / total_valid_requests` and that the complete exit contract is 0 success, 1 unexpected/output failure, 2 usage/configuration, 3 input/data failure, 4 unique-cardinality exhaustion. Report findings with file/line evidence. Do not call the candidate complete without the current exact-candidate adjudication receipt required by `.itd/VERIFICATION_CONTRACT.json`.

## 5. Performance Prompt

> Benchmark the frozen candidate against the declared 1 GB fixture on the documented laptop using Python 3.11. Record input shape/cardinality, command, interpreter, CPU/RAM profile, wall time, and peak RSS. Compare with the <30-second target and the declared memory target. If it fails, profile parser, allocation, and rendering boundaries before proposing a change. Do not introduce multiprocessing, approximation, a database, or a service without updating architecture and scope. Re-run correctness and the exact-candidate Verification Loop after any optimization.

## 6. Handoff Checklist

- [ ] Active step and scope match `.itd-memory` state and `.itd/SCOPE_LOCK.md`.
- [ ] Only the current step's files changed.
- [ ] Named unit checks actually ran and results were recorded.
- [ ] Complete exit codes `0/1/2/3/4` remain tested; code 4 is unique-cardinality exhaustion.
- [ ] No prohibited server, API, auth, database, cloud, or Kubernetes scope was added.
- [ ] Specs were updated before any intentional behavior change.
- [ ] Exact-candidate oracle and risk checker were run.
- [ ] A current revalidated adjudication receipt exists, or the handoff says `NOT ACCEPTED` and gives the next action.

