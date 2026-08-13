# Claude Code Implementation Guide: nginx-log-report

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. Execute exactly one prompt at a time (WIP=1), review the diff, run its verification commands, and update the status table in `CLAUDE.md` only from evidence. The specifications—not generated code—are the source of truth.

## Non-Negotiable Contract for Every Prompt

- Python 3.11, Click, Rich, dataclasses, `src/` packaging, pip-installable wheel.
- Single local process; one pass over a file/stdin stream; no raw-record retention.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Hourly percentages use exactly `100 × hourly_request_count / total_valid_requests`.
- Terminal text is default; `--json` and `--csv` are deterministic and ANSI-free.
- Do not weaken or remap the complete exit-code contract:

| Code | Required meaning |
|---:|---|
| `0` | successful report/help/version; lenient mode may skip malformed lines |
| `1` | I/O or unexpected runtime failure |
| `2` | Click usage/argument error |
| `3` | input-data failure, including strict malformed input, invalid UTF-8, or zero valid requests |
| `4` | unique-cardinality exhaustion before inserting a distinct User-Agent beyond the configured cap |

On code `4`, write a concise diagnostic to stderr and no partial report to stdout. Code `4` must appear in integration tests and must not be folded into another error.

## Prompt 1 — Package and CLI Boundary

> Read `PROJECT_ARCHITECTURE.md`, `PRD.md`, `IMPLEMENTATION_PLAN.md`, and `CLAUDE.md`. Implement only Step 1 of `IMPLEMENTATION_PLAN.md`: `pyproject.toml`, package/version entry points, Click help/version/options, and the initial CLI tests. Preserve the non-negotiable contract in this guide, especially reserved exit codes `0/1/2/3/4`; Step 1 must prove option conflicts exit `2`. Do not add parser, aggregator, renderer, database, API, server, container, or cloud code. Run the Step 1 verification commands, report their actual results, and update only Step 1 in `CLAUDE.md` after they pass.

## Prompt 2 — Domain Models and Error Taxonomy

> Implement only Step 2 of `IMPLEMENTATION_PLAN.md`. Create the exact dataclasses/enums in the architecture, typed domain exceptions, and small deterministic fixtures. Freeze the complete error mapping with tests: success `0`, I/O/runtime `1`, usage `2`, input data `3`, and unique-cardinality exhaustion `4`. Do not implement parsing or rendering. Run the listed tests and compile check; do not mark the step complete without evidence.

## Prompt 3 — Streaming Parser

> Implement only Step 3. Parse the selected Combined/Common grammar from a binary-safe UTF-8 file/stdin boundary, compile grammar once, validate timestamps/status/request target, and track line numbers without retaining records. Strict malformed/invalid UTF-8/no-valid input is code `3`; lenient mode skips/counts malformed lines; unreadable streams are code `1`; Click validation remains code `2`; reserve code `4` unchanged. Treat log values only as data and never echo full raw lines by default. Add all specified parser/CLI tests, run Step 3 verification, and update status from evidence.

## Prompt 4 — Rankings and Hourly Metrics

> Implement only Step 4 in `src/nginx_log_report/aggregate.py` and its tests. In one pass, count valid IPs, count targets only for statuses 400–599, and maintain exactly 24 hour buckets. Rank by count descending then key ascending. Define every hourly percentage as `100 × hourly_request_count / total_valid_requests`; never expose an unscaled fraction and never include invalid lines in the denominator. Keep formatting out of aggregation. Preserve exit codes `0/1/2/3/4` and run the specified tests before changing status.

## Prompt 5 — Exact User-Agent Safety

> Implement only Step 5. Track exact normalized User-Agent strings for Combined format, return unavailable for Common, and calculate `100 × unique_normalized_user_agent_count / total_valid_requests`. Enforce the configured cap before insertion. If the next distinct value exceeds it, emit no report and exit exactly `4`; do not remap it to `1` or `3`. Add boundary/normalization/Common/no-partial-output tests and preserve the other meanings: `0` success, `1` I/O/runtime, `2` usage, `3` input data. Run Step 5 verification and record evidence.

## Prompt 6 — Rich Terminal Output

> Implement only Step 6. Add the Rich renderer for the four metrics and valid/invalid totals. Disable markup for all log-derived values; honor `--no-color`, `NO_COLOR`, and non-TTY output. Common-format UA is `N/A`; terminal percentages show two decimals. Do not change aggregation, structured schemas, or the `0/1/2/3/4` meanings. Add semantic and no-ANSI golden tests, run the verification commands, and update status only if they pass.

## Prompt 7 — JSON and CSV Output

> Implement only Step 7. Add schema-versioned deterministic JSON and RFC 4180 long-form CSV with header `section,rank,key,count,percentage`. Ensure all 24 hours, tie ordering, numeric precision, correct Common-UA null/empty behavior, locale independence, and stdout/stderr separation. `--json` and `--csv` conflict with exit `2`. Preserve `0` success, `1` I/O/runtime, `3` input data, and `4` unique-cardinality exhaustion. Emit no ANSI/prose in structured stdout. Run all Step 7 verification commands.

## Prompt 8 — Black-Box Contract Suite

> Implement only Step 8. Through installed-command subprocess tests, independently force and assert every exit code: `0` success, `1` I/O/runtime failure, `2` Click usage error, `3` input-data failure, and `4` unique-cardinality exhaustion. Verify that code `4` emits no partial report. Test file/stdin equivalence, strict/lenient parsing, invalid UTF-8, zero valid records, output schemas, tie order, all 24 hours, and clean stdout/stderr. Run the integration, output-contract, and coverage commands; fix only in-scope defects and report actual results.

## Prompt 9 — Performance and Release Candidate

> Implement only Step 9. Add a deterministic streaming benchmark generator and small performance smoke test, document the full 1 GB benchmark environment, and build the exact wheel candidate. Profile before optimizing. Run the complete suite, coverage gate, wheel validation, clean-environment smoke test, and `/usr/bin/time -v` benchmark. Accept only under 30 seconds on the documented reference laptop. Recheck `0/1/2/3/4`, including code `4` cardinality exhaustion, against the installed wheel. Do not introduce multiprocessing, persistence, services, containers, cloud, or approximations without first revising the architecture and PRD.

## Review Prompt After Each Step

> Self-review the current step against its exact diff, the relevant PRD acceptance criteria, `PROJECT_ARCHITECTURE.md`, and the verification output. Look specifically for whole-file loading, raw-line leakage, nondeterministic ordering, ANSI in structured output, denominator errors, broad exception handling, or collapse of exit code `4`. Label this as self-review unless an independent reviewer actually ran. If evidence is missing, mark the step unverified rather than complete.

## Final Handoff Prompt

> Validate the exact release candidate against all P0 stories and NFRs. Confirm the wheel installs in a clean Python 3.11 environment, the full suite and coverage gate pass, the documented 1 GB benchmark is under 30 seconds, and exit codes `0/1/2/3/4` are independently exercised. Reconcile `CLAUDE.md` status and state the next action. Do not claim completion from prose or stale output.

