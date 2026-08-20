# Claude Code Implementation Guide

This guide converts [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) into bounded prompts for future coding sessions. Execute exactly one step at a time (WIP=1), read `AGENTS.md`, `.itd/` contracts, `.itd-memory/STATE.json`, the architecture, and the PRD first, and use the smallest applicable Idea to Deploy implementation skill. Do not implement deferred P1/P2 scope during P0 steps.

## Invariant Contract for Every Prompt

All steps must preserve the full process contract: `0` success; `1` input/I/O or unexpected runtime failure; `2` invalid CLI usage; `3` no valid records; `4` unique-cardinality exhaustion. Code `4` must not be omitted or remapped. A nonzero result must not emit a partial JSON/CSV report.

Hourly percentages must use `100 × hourly_request_count / total_valid_requests`. Distinct User-Agent share must use valid requests as the denominator. No authentication, database, HTTP API, server, cloud, Docker, Kubernetes, telemetry, or persistent state may be introduced.

At the end of each prompt, freeze the exact staged candidate, run the declared machine oracle, apply the risk-tier checker, retain a current adjudication receipt, record actual evidence, reconcile state, and stop. A prose `PASSED` is insufficient.

## Prompt 1 — Package Baseline

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only `pyproject.toml`, `src/nginx_stream_analytics/__init__.py`, `src/nginx_stream_analytics/cli.py`, and `tests/test_cli.py`. Target Python 3.11 with Click and Rich and expose `nginx-log-report`. Implement only help/version/skeleton behavior; do not build product metrics early. Run the exact Step 1 verification commands and record outputs. Preserve the invariant exit contract 0/1/2/3/4, including 4 for unique-cardinality exhaustion, for later integration.

## Prompt 2 — Domain Contracts

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Add frozen/slotted dataclasses and domain exceptions only at the listed paths. Encode report fields consistent with `PROJECT_ARCHITECTURE.md`; do not add persistence or framework models. Add schema/model tests, run mypy and the Step 2 test command, and record outputs. Preserve exit codes 0/1/2/3/4 exactly; code 4 means unique-cardinality exhaustion.

## Prompt 3 — Streaming Parser

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Read file/stdin once with bounded lines and parse the documented nginx combined-format subset into transient `LogRecord` values. Count malformed lines without including them in totals; never retain raw records. Add only the listed fixtures/tests, run Step 3 checks, and record evidence. Preserve exit codes 0/1/2/3/4 exactly; code 4 means unique-cardinality exhaustion.

## Prompt 4 — Aggregations

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Add exact deterministic top-10 IP/error-URL counts, fixed 24-hour buckets, and exact distinct non-empty User-Agent tracking. Compute each hourly percentage as `100 × hourly_request_count / total_valid_requests`. Check the unique ceiling before insertion and raise the cardinality domain error rather than approximating. Exercise boundary/tie/status tests and the declared coverage check. Preserve exit codes 0/1/2/3/4 exactly; code 4 means unique-cardinality exhaustion.

## Prompt 5 — Machine Renderers

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Produce only the versioned JSON object and RFC-compatible long-form CSV declared by the architecture. Keep ordering deterministic, encode through standard libraries, and guarantee no ANSI. Add golden tests and run the Step 5 commands. Preserve exit codes 0/1/2/3/4 exactly; code 4 means unique-cardinality exhaustion; do not render partial output for nonzero outcomes.

## Prompt 6 — Terminal Renderer

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Add four Rich tables and totals, consistent percentage formatting, automatic non-TTY color suppression, and safe treatment of markup/control text from logs. Add the listed golden/security-oriented cases and run Step 6 checks. Preserve exit codes 0/1/2/3/4 exactly; code 4 means unique-cardinality exhaustion.

## Prompt 7 — CLI Integration

> Implement Step 7 from `IMPLEMENTATION_PLAN.md`. Connect input, parser, aggregator, and one renderer behind the exact Click interface. Enforce mutually exclusive formats and positive cardinality limit. Map outcomes to exactly 0 success, 1 input/I/O or unexpected runtime failure, 2 usage error, 3 no valid records, and 4 unique-cardinality exhaustion. Render only after complete aggregation. Prove all five codes and stdout/stderr separation with the listed tests.

## Prompt 8 — Release Evidence

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Add deterministic benchmark generation/measurement, end-to-end golden tests, clean-wheel install smoke testing, and implementation-accurate README details. Do not commit the 1 GB fixture. Run the full suite, lint/type checks, 1 GB/30 s gate, and build checks. Prove the final exit contract 0/1/2/3/4, with 4 meaning unique-cardinality exhaustion. Then execute the Idea to Deploy Verification Loop on the exact staged candidate and accept only a current adjudication receipt.

## Recovery Guidance

If a verification fails, keep the same active step, record the failure as recovery evidence, make the smallest in-scope correction, and rerun the relevant oracle. If scope must change, update `.itd/SCOPE_LOCK.md` and state before editing. Never mark a step complete because code appears plausible.
