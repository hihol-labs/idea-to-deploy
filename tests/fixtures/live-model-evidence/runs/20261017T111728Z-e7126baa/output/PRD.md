# Product Requirements Document: nginx-insights

## Product Summary

`nginx-insights` lets DevOps/SRE engineers analyze a local nginx access-log stream without installing or operating an observability platform. It produces top client IPs, top error URLs, hourly traffic percentages, and unique User-Agent share as terminal, JSON, or CSV output.

## Problem and Outcome

During incident triage, an operator often has a log file or pipe but not a prepared dashboard. Hand-built shell pipelines are quick but inconsistent around quoting, malformed records, denominators, ties, and reusable machine output. The desired outcome is a trustworthy summary in one command, on a 1 GB file in under 30 seconds on a documented laptop.

## Scope

The MVP supports Python 3.11, pip installation, plain-text file/stdin input, nginx common and combined formats, a single-process one-pass calculation, colored terminal output, JSON, CSV, stable diagnostics, and explicit exit codes.

It does not include authentication, database, HTTP API, server, cloud, Kubernetes, dashboards, telemetry, persistence, arbitrary `log_format` definitions, compressed files, or approximate metrics.

## User Stories

- As a DevOps engineer, I want to see the top 10 client IPs so that I can identify concentrated traffic sources during triage.
- As an on-call SRE, I want to see the top 10 request URLs returning 4xx/5xx statuses so that I can focus error investigation.
- As a capacity engineer, I want a 24-hour percentage distribution so that I can spot peak traffic hours.
- As a security-minded operator, I want the share of unique User-Agent values so that I can recognize unusually diverse or automated clients.
- As an automation author, I want stable JSON and CSV on stdout with diagnostics on stderr so that I can compose reliable pipelines.
- As an operator handling imperfect logs, I want rejected-line counts and strict mode so that I can choose tolerant or fail-fast analysis.
- As a laptop user, I want explicit cardinality exhaustion rather than an out-of-memory crash or silent approximation so that failures are actionable.

## Functional Requirements

### P0 — Must

#### P0.1 Stream and parse input

The CLI shall read a named plain-text file, omitted input, or `-` (stdin) line by line and parse nginx common/combined formats.

Acceptance criteria:

- [ ] File and stdin versions of the same bytes produce the same summary.
- [ ] The implementation retains no list of all parsed requests.
- [ ] Blank lines are ignored; malformed non-empty lines are rejected and counted in tolerant mode.
- [ ] `--strict` stops on the first malformed non-empty line with exit code 3.

#### P0.2 Produce top client IPs

Count remote-address values over all valid requests and return ten by default.

Acceptance criteria:

- [ ] Results sort by count descending and then IP text ascending.
- [ ] `--top N` returns at most N entries and rejects values below 1 as usage error code 2.

#### P0.3 Produce top error URLs

Count request targets only for statuses from 400 through 599 inclusive.

Acceptance criteria:

- [ ] 3xx responses do not contribute and 400, 499, 500, and 599 do.
- [ ] Query strings remain part of the raw request target.
- [ ] Ordering and `--top` behavior match the IP report.

#### P0.4 Produce hourly request distribution

Emit all 24 local-hour buckets from the timestamp represented in each log line. Each bucket percentage is exactly `100 × hourly_request_count / total_valid_requests`, rounded to two decimal places only at output.

Acceptance criteria:

- [ ] Counts across the 24 buckets equal `total_valid_requests`.
- [ ] Zero-count hours are present with `0.00` percent.
- [ ] No percentage is produced for zero valid requests; the command exits 3.

#### P0.5 Produce unique User-Agent share

Compute `100 × unique_nonempty_user_agent_count / total_valid_requests`; requests without a User-Agent stay in the denominator.

Acceptance criteria:

- [ ] Repeated identical agents add one to `unique_count`.
- [ ] Common-format lines and `"-"` agents add no distinct agent but remain valid requests.
- [ ] The output includes unique count, requests carrying an agent, and percentage.

#### P0.6 Render terminal, JSON, and CSV formats

Default output shall be Rich terminal text; `--json` and `--csv` shall be pipeline-safe and mutually exclusive.

Acceptance criteria:

- [ ] Terminal output uses color only when supported and not disabled by `--no-color`.
- [ ] JSON parses as one complete document with the schema documented in `PROJECT_ARCHITECTURE.md`.
- [ ] CSV has the documented normalized header and correct quoting.
- [ ] Structured stdout has no ANSI escapes or diagnostic text.

#### P0.7 Enforce error and capacity contracts

Acceptance criteria:

- [ ] Exit codes have exactly these meanings: `0` success, `1` runtime/output failure, `2` usage error, `3` input/data error, `4` unique-cardinality exhaustion.
- [ ] Exceeding `--max-unique` in any guarded dimension exits 4 and does not emit a misleading completed report.
- [ ] Unexpected errors do not expose full input records or a traceback in normal operation.

#### P0.8 Meet the performance target

Acceptance criteria:

- [ ] The exact release candidate processes a deterministic representative 1 GB file in under 30 seconds on the recorded reference laptop.
- [ ] Peak RSS and command/environment metadata are recorded with the timing.
- [ ] Failure to meet the target blocks release and triggers profiling or scope reconsideration.

### P1 — Should

- Follow mode for a growing regular file, with signal-driven final report and documented rotation semantics.
- A concise rejected-reason summary to help diagnose format mismatch without echoing sensitive lines.

### P2 — Could

- Transparent gzip file input after separate performance acceptance.
- A constrained custom-format mapping for common nginx `log_format` variants.
- Shell completion metadata supplied through Click.

## Output and Compatibility Requirements

JSON carries a numeric `schema_version` starting at 1. Backward-incompatible structured-output changes require a new schema version and release note. Counts are integers; percentages are numbers rounded to two decimals. Terminal wording is not a machine interface. JSON/CSV determinism includes stable rank tie-breaking and fixed hour order.

## Quality Attributes

| Attribute | Requirement |
|---|---|
| Performance | Representative 1 GB input in <30 seconds on recorded laptop |
| Memory | No retained records; guarded exact maps; target peak RSS <512 MiB on benchmark corpus |
| Reliability | Malformed data is visible in counts or fails under strict mode |
| Security/privacy | Offline, no telemetry, untrusted text never interpreted as markup/commands, bounded error excerpts |
| Portability | Python 3.11 on supported pip platforms; no shell utility dependency |
| Testability | Deterministic sorting, schemas, fixtures, and injectable streams/console |

## Success Metrics

Release requires all P0 acceptance criteria, under-30-second benchmark evidence, successful clean-environment pip installation, and no known critical/high security defect. Post-release indicators are parser-format issue rate, structured-schema regressions, and real-world benchmark reports—not downloads alone.

## Kill Criteria

Pause release if the optimized single-process design cannot meet the 1 GB target on the agreed reference machine, if exact counters exceed the practical memory/cardinality envelope on representative logs, or if common/combined parsing yields ambiguous results. Approximation, hidden sampling, a database, or a service are not silent escape hatches; any such change requires a new product/architecture decision.

## Dependencies and References

The architecture and exact CLI/output contracts are in `PROJECT_ARCHITECTURE.md`. Delivery sequencing and verification commands are in `IMPLEMENTATION_PLAN.md`. Product rationale and prioritization are in `STRATEGIC_PLAN.md`.

