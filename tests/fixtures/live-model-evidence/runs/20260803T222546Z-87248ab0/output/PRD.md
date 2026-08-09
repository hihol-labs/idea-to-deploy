# Product Requirements Document: Nginx Log Stats

## Product Summary

Nginx Log Stats is a local Python 3.11 CLI for rapid nginx combined access-log analysis. It consumes a finite file or stdin stream and reports top client IPs, top URLs producing 4xx/5xx responses, a 24-bucket hourly distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV are stable pipeline formats.

## Goals

- Give DevOps/SRE users all four requested metrics in one command.
- Process a representative 1 GB log in under 30 seconds on the declared reference laptop.
- Remain stateless, local, pip-installable, and $0 to run.
- Make automation reliable through deterministic output, stdout/stderr separation, and explicit exit codes.

## Non-Goals

- Authentication, accounts, authorization, multi-tenancy, or secrets.
- Database storage, cross-run history, dashboards, HTTP APIs, servers, cloud, Docker, or Kubernetes.
- Arbitrary nginx `log_format` parsing, gzip-native input, multiple input files, geolocation, bot identification, or periodic live refresh in MVP.
- Claims that User-Agent values identify unique humans.

## User Stories

### US-1: Analyze a local file or stdin stream

As an on-call SRE, I want to stream a combined-format nginx log from a path or stdin so that I can analyze an export or compose the tool with `tail`, `ssh`, or decompression commands.

Priority: P0

Acceptance criteria:

- [ ] With one valid record in a file, `nginx-log-stats file.log` exits `0` and counts one valid request.
- [ ] Piping the same bytes to `nginx-log-stats -` produces the same report model.
- [ ] A file larger than available memory is consumed line-by-line rather than read wholesale.
- [ ] A missing/unreadable path emits a concise stderr diagnostic and follows the documented exit-code contract.
- [ ] Exceeding the default 250,000 combined distinct-key guard fails before an inexact report is emitted and exits `4`.

### US-2: Find the busiest client IPs

As a DevOps engineer, I want the top 10 client IPs by request count so that I can spot concentrated traffic or abusive clients.

Priority: P0

Acceptance criteria:

- [ ] At EOF the report contains at most 10 IPs by default, ordered by descending request count.
- [ ] Ties are ordered by ascending IP text for deterministic output.
- [ ] `--top N` accepts `1..100` and applies the same limit to IP and error-URL lists.

### US-3: Find URLs causing client/server errors

As an on-call SRE, I want the top 10 request URLs producing 4xx or 5xx responses so that I can prioritize broken or failing endpoints.

Priority: P0

Acceptance criteria:

- [ ] Status codes `400..599` contribute to the URL error counter; `399` and `600` do not.
- [ ] Counts combine 4xx and 5xx responses per exact logged request-target.
- [ ] Results use descending count and ascending URL tie-breaking and respect `--top`.

### US-4: See hourly request distribution

As an SRE reviewing an incident window, I want requests grouped by hour so that I can see traffic concentration through the day.

Priority: P0

Acceptance criteria:

- [ ] Output contains all integer hours `0..23`, including zero-count buckets.
- [ ] Each valid record increments the hour expressed by its parsed nginx timestamp and offset.
- [ ] The sum of 24 buckets equals the valid request total.

### US-5: Estimate User-Agent diversity

As a DevOps engineer, I want the share of unique User-Agent strings so that I can gauge client diversity without interpreting it as user identity.

Priority: P0

Acceptance criteria:

- [ ] The report includes distinct User-Agent count and `distinct / valid requests × 100` rounded only for presentation.
- [ ] Repeated identical strings count once as distinct values and once per record in the denominator.
- [ ] Empty valid input yields `0.0`, not division by zero.

### US-6: Use safe human and machine outputs

As a platform engineer, I want colored terminal output plus JSON and CSV modes so that the same tool works interactively and in pipelines.

Priority: P0

Acceptance criteria:

- [ ] Default terminal output presents all four metrics with color only when enabled/capable.
- [ ] `--json` emits one valid schema-version-1 JSON document and no ANSI escapes.
- [ ] `--csv` emits the documented normalized header/rows and no ANSI escapes.
- [ ] `--json` and `--csv` together produce a usage error; data stays on stdout and diagnostics on stderr.
- [ ] Control characters/markup from log fields cannot alter terminal structure.

### US-7: Choose malformed-line policy

As an automation author, I want tolerant and strict parsing modes so that exploratory analysis can continue while validation jobs can fail fast.

Priority: P1

Acceptance criteria:

- [ ] Default mode skips malformed records, counts them, avoids echoing sensitive full lines, and can still exit `0`.
- [ ] `--strict` stops on the first malformed/undecodable record, reports its one-based line number and category, and exits `3`.

### US-8: Read compressed logs directly

As an SRE with rotated logs, I want native gzip input so that I do not need an external decompression pipeline.

Priority: P2

Acceptance criteria:

- [ ] If implemented after MVP, `.gz` handling preserves the same parser, report, error, and streaming contracts.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one file path, `-`, or omitted input for stdin using combined-log grammar |
| FR-2 | P0 | Parse IP, timestamp with offset, request method/target/protocol, status, bytes, referrer, and User-Agent |
| FR-3 | P0 | Compute exact top IP counts, exact 4xx/5xx URL counts, 24 hourly buckets, and exact distinct User-Agent count/share |
| FR-4 | P0 | Default top-list size to 10 with deterministic tie ordering |
| FR-5 | P0 | Render Rich terminal, schema-version-1 JSON, and normalized CSV according to architecture schemas |
| FR-6 | P0 | Enforce output-flag exclusivity and exit codes `0`, `1`, `2`, `3`, and `4` as documented |
| FR-7 | P0 | Sanitize untrusted terminal text and never emit ANSI escapes in JSON/CSV |
| FR-8 | P1 | Support `--strict`, `--top`, `--encoding`, `--max-cardinality`, and `--no-color` behavior |
| FR-9 | P2 | Consider gzip and configurable log formats only after MVP evidence |

P0 maps to MoSCoW Must, P1 to Should, and P2 to Could. Won't items are listed under Non-Goals.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Representative 1 GB input completes in under 30 seconds on the reference laptop | Timed benchmark with fixture manifest and environment record |
| NFR-2 | Input is processed incrementally; no whole-file read | Code review plus large-stream integration test/peak RSS measurement |
| NFR-2a | Representative peak RSS is <=512 MiB and unsupported cardinality fails closed rather than emitting approximations | Benchmark plus resource-guard integration tests |
| NFR-3 | Same report model yields deterministic ordering and stable machine schemas | Golden JSON/CSV tests and repeated-run comparison |
| NFR-4 | Package installs on Python 3.11 through pip and exposes `nginx-log-stats` | Clean-wheel install smoke test |
| NFR-5 | No network, persistence, telemetry, authentication, or service dependency | Dependency/config review and offline smoke test |
| NFR-6 | Overall test coverage is at least 90%, with all P0 branches explicitly exercised | Coverage report and acceptance trace matrix |

## Input and Parsing Rules

The MVP grammar is nginx combined format as specified in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). Binary physical lines are decoded independently so default mode can recover after a decoding failure. Request-targets remain exact logged values and timestamps group by the hour encoded in each record. Lines outside the grammar, lines over 1 MiB, invalid status/timestamp values, and decode failures are malformed. Blank lines are malformed rather than silently treated as requests.

## Output and Error Contract

The exact command, options, JSON/CSV shapes, stdout/stderr rules, and exit codes are normative under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. Terminal wording may improve without a breaking change; machine field names, meanings, or CSV layout require a deliberate schema compatibility decision.

## Analytics Semantics

- “Top IPs” means valid requests grouped by exact parsed IP text.
- “Top error URLs” means valid records with status `400..599`, grouped by exact request-target.
- “Hourly” means 24 buckets keyed to the hour in each record's timestamp; it is not host-local conversion.
- “Unique User-Agent share” means distinct exact User-Agent strings divided by valid records. It is not unique-user share.

## Success Metrics

MVP success requires every P0 acceptance criterion, the 1 GB/<30 s performance gate, a clean pip install, zero known false-success machine-output cases, and no Critical/High security finding. Adoption metrics in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) are observed after release and do not weaken launch quality gates.

## Kill Criteria

Pause release and reassess if either condition remains after one bounded remediation cycle:

1. Correct single-process Python cannot meet the 1 GB/<30 s gate on the declared reference fixture/hardware without unacceptable laptop memory use.
2. The stable terminal/JSON/CSV contract cannot provide materially less effort or fewer parsing errors than documented GoAccess or `awk` workflows for the four target questions.

Do not respond by adding a server/database or by changing exact metrics to approximate ones without revising this PRD and its approved scope.

## Dependencies and Traceability

This PRD derives priorities from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), technical contracts from [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and executable sequencing from [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). The spec is the durable source of truth: behavioral changes start here and in architecture before code changes.
