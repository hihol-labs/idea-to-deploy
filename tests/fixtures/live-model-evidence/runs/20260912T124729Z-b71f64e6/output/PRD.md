# Product Requirements Document: nginx-log-top

## Product Summary

`nginx-log-top` lets DevOps/SRE users turn one nginx combined access-log stream into four fast operational summaries. It runs locally, requires no service or credentials, and supports human-readable and machine-readable output.

## Problem and Outcome

During incidents and investigations, engineers often have a log file before they have a queryable observability system. Ad-hoc shell pipelines are easy to mistype and hard to reproduce. Success is a one-command, one-pass report whose metrics, schemas, and failures are predictable enough for both a terminal and automation.

## User Stories

- As a site reliability engineer, I want the top 10 client IPs so that I can identify dominant or suspicious traffic sources.
- As an on-call engineer, I want the top 10 URLs ranked by 4xx/5xx responses so that I can focus error triage on the worst request targets.
- As a DevOps engineer, I want hourly request distribution as percentages so that I can recognize traffic concentration across the day.
- As a service owner, I want the share of unique User-Agents so that I can estimate client diversity without equating agents to people.
- As an automation author, I want stable JSON and CSV output so that I can feed results into scripts without scraping terminal text.
- As an operator, I want stdin and file inputs so that I can analyze stored logs or compose the tool in a Unix pipeline.
- As a reliability engineer, I want explicit malformed-data and cardinality failures so that an incomplete result is never mistaken for a correct one.

## Personas and Primary Journey

1. The operator obtains an nginx combined access log or pipes it from another local command.
2. They run `nginx-log-top access.log`, optionally selecting `--json` or `--csv`.
3. The tool streams the input, reports malformed-line diagnostics on stderr, and emits one report on stdout.
4. The operator acts on ranked IPs/routes and time/client-diversity patterns or passes the structured result downstream.

## Functional Requirements

### P0 — Must ship

#### P0.1 Stream one input

- Accept a file path, `-`, or omitted input for stdin.
- Never read the full file or retain raw records.

Acceptance criteria:

- [ ] File and stdin runs over the same fixture produce equivalent metric results.
- [ ] A 1 GB run demonstrates memory growth based on aggregate cardinality, not bytes read.
- [ ] Missing/unreadable input returns exit code 1 and writes no report to stdout.

#### P0.2 Parse nginx combined records

- Extract IP, timestamp/hour, request target, status, and User-Agent.
- Lenient mode skips malformed lines and counts them; strict mode stops at the first malformed line.

Acceptance criteria:

- [ ] Valid IPv4, IPv6, offset timestamps, placeholders, and escaped quoted fields pass fixtures.
- [ ] Lenient mode completes and reports malformed count.
- [ ] `--strict` returns exit code 3 with a 1-based line diagnostic.

#### P0.3 Compute the four reports

- Return top 10 IPs by valid request count.
- Return top 10 request targets where status is 400–599.
- Return all 24 hourly buckets. Hourly request distribution is a percentage calculated as `100 × hourly_request_count / total_valid_requests`; it is not an unscaled fraction.
- Return exact unique User-Agent count and `100 × unique_user_agent_count / total_valid_requests`.

Acceptance criteria:

- [ ] Known fixtures match expected counts and percentages.
- [ ] Rank ties resolve by key ascending after count descending.
- [ ] Zero valid requests produce empty rankings, 24 zero-valued hours, and a zero User-Agent share.
- [ ] Crossing the configured exact User-Agent limit produces exit code 4 and no misleading completed report.

#### P0.4 Render text, JSON, and CSV

- Colored Rich text is the default for terminals.
- `--json` and `--csv` are mutually exclusive pipeline modes.
- All renderers consume one canonical analysis result.

Acceptance criteria:

- [ ] Golden tests cover each output mode.
- [ ] JSON/CSV parse with standard library readers and contain no ANSI sequences.
- [ ] Redirected default text is uncolored unless color is explicitly forced.
- [ ] stdout contains only report data; diagnostics use stderr.

#### P0.5 Honor the process contract

- Exit codes are `0/1/2/3/4`: 0 success; 1 input I/O failure; 2 CLI usage error; 3 strict parse or output/data failure; 4 unique-cardinality exhaustion.
- `--help` and `--version` return 0.

Acceptance criteria:

- [ ] Integration tests trigger and assert every code from 0 through 4.
- [ ] Mutually exclusive formats and nonpositive cardinality limits return 2.
- [ ] A closed/unwritable output is handled as an output failure without a traceback.

#### P0.6 Meet release performance and packaging gates

- Install from a wheel on Python 3.11.
- Process the deterministic 1 GB benchmark in under 30 seconds on the documented reference laptop.

Acceptance criteria:

- [ ] Clean-environment wheel smoke test succeeds.
- [ ] Benchmark records machine, Python version, elapsed time, peak RSS, and known-result correctness.

### P1 — Should ship next

- `--top N` changes both ranked lists while preserving output schema field names.
- Add shell-completion documentation.
- Publish a machine-readable JSON Schema for JSON output v1.

### P2 — Could ship later

- Read gzip-compressed files directly.
- Support explicitly configured nginx `log_format` variants.
- Provide IPv4/IPv6 network grouping with clearly named semantics.

## Non-Functional Requirements

| Attribute | Requirement |
|---|---|
| Performance | 1 GB in < 30 seconds on a documented laptop |
| Memory | Bounded by unique aggregate keys; exact User-Agent ceiling defaults to 1,000,000 |
| Determinism | Stable sorting, schemas, rounding, and exit behavior |
| Compatibility | Python 3.11; Linux/macOS primary; Windows when CI passes |
| Security | No execution of input, no network access, terminal control characters escaped |
| Privacy | No telemetry, persistence, or log upload |
| Accessibility | Text labels carry meaning independently of color |

## Out of Scope

- Authentication, accounts, database, HTTP API, server, daemon, cloud, Docker, or Kubernetes.
- Historical retention, dashboards, alerting, tail-follow mode, multi-file correlation, geolocation, bot detection, or identity inference.
- Approximate unique counting in MVP.
- Full compatibility with arbitrary custom nginx log formats.

## Analytics and Telemetry

The tool collects no telemetry. Project-level usage may be inferred only from public package/repository statistics. Local logs and results never leave the user's process unless the user pipes or saves them.

## Dependencies and Cross-References

- Architecture and schemas: `PROJECT_ARCHITECTURE.md`.
- Delivery steps and verification: `IMPLEMENTATION_PLAN.md`.
- Market, priorities, risks, and Definition of Done: `STRATEGIC_PLAN.md`.

## Release Criteria

All P0 acceptance criteria pass; all exit codes have integration evidence; the wheel smoke test passes; the deterministic performance gate passes on the documented reference laptop; and no P1/P2 feature delays the release.

## Kill Criteria

Pause release and reconsider scope if correctness on the agreed combined-format corpus is below 100%, if a profiled implementation still cannot process 1 GB under 30 seconds, or if exact User-Agent cardinality cannot fail safely at a documented limit. Do not introduce a database or service as an unapproved workaround.
