# Product Requirements Document: nginx-log-top

## Product Summary

`nginx-log-top` gives DevOps and SRE engineers a fast local summary of nginx access logs without requiring a service or persistent store. The product is an open-source Python 3.11 CLI installed through pip, delivered within one weekend at a $0 cash budget.

## Goals

- Analyze a representative 1 GB nginx access log in under 30 seconds on a documented laptop.
- Provide top-10 client IPs, top-10 4xx/5xx request URLs, hourly request percentages, and exact unique User-Agent share.
- Work from either a local path or stdin with bounded streaming behavior.
- Produce human-friendly terminal output and stable JSON/CSV pipeline output.
- Make malformed input and resource-policy failures observable through stderr and the `0/1/2/3/4` exit contract.

## Non-Goals

- Authentication, authorization, users, or accounts.
- A database, retained history, indexing, or search.
- An HTTP API, daemon, server, web interface, cloud service, Docker runtime, or Kubernetes.
- Live tail-follow mode, multiple custom nginx formats, approximate cardinality, or distributed processing in the MVP.
- Replacing long-term observability or analytics platforms.

## User Stories

- As a SRE on call, I want to see the top 10 client IPs so that I can identify traffic concentration or abusive clients quickly.
- As a service owner, I want to see the top 10 URLs returning 4xx or 5xx statuses so that I can focus incident investigation on failing routes.
- As a capacity engineer, I want to see each hour's request percentage so that I can understand the traffic shape without doing spreadsheet calculations.
- As a reliability engineer, I want to see the share of unique User-Agents so that I can distinguish diverse clients from repetitive automated traffic.
- As a pipeline author, I want JSON output so that I can consume typed metrics without parsing terminal decorations.
- As a shell user, I want normalized CSV output so that I can load results into standard command-line and spreadsheet tools.
- As an operator handling imperfect logs, I want malformed records counted by default and rejected in strict mode so that I can choose resilience or validation.
- As a laptop user, I want a hard exact-cardinality ceiling so that pathological User-Agent diversity fails explicitly instead of exhausting memory.

## Functional Requirements

### P0 — Must Ship

#### FR-1: Streaming input

The command accepts one optional `INPUT` path; omission or `-` reads stdin. It processes one physical line at a time and does not retain raw records.

Acceptance criteria:

- [ ] The same fixture produces equivalent results from a path and stdin.
- [ ] Empty input exits 0 and returns a structurally complete zero-valued report.
- [ ] A missing or unreadable path emits a concise stderr diagnostic, no report, and exits 1.

#### FR-2: Parse supported nginx format

The MVP parses nginx Combined Log Format into IP, offset-aware timestamp, request target, status, and User-Agent fields.

Acceptance criteria:

- [ ] Supported IPv4, IPv6, query-string, timezone-offset, missing-user, and non-ASCII fixtures parse as specified.
- [ ] Malformed lines are counted and skipped by default.
- [ ] `--strict` stops at the first malformed line and exits 3 without a completed report.

#### FR-3: Top client IPs

Count valid requests per client IP and emit at most 10 results ordered by count descending, then IP lexicographically ascending.

Acceptance criteria:

- [ ] Duplicate IPs aggregate exactly.
- [ ] Eleven or more distinct IPs yield exactly 10 ranked rows.
- [ ] Ties have deterministic lexical order in every format.

#### FR-4: Top error URLs

Count request targets only for HTTP statuses 400 through 599 inclusive and emit at most 10 using the stable ranking rule.

Acceptance criteria:

- [ ] Status 399 is excluded; 400 and 599 are included.
- [ ] Statuses outside 400–599 never affect error-URL rankings.
- [ ] Query strings remain part of the raw request-target key for the MVP.

#### FR-5: Hourly request distribution

Emit 24 ordered buckets (`00`–`23`). Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`; this is a scaled percentage, not a fraction. Round only for output.

Acceptance criteria:

- [ ] A nonempty fixture's unrounded hourly percentages total approximately 100%, within floating-point tolerance.
- [ ] Empty input emits 24 buckets with zero counts and `0.0` percentages.
- [ ] The hour is derived from the local hour recorded in each offset-bearing nginx timestamp.

#### FR-6: Unique User-Agent share and guard

Count exact distinct nonempty User-Agent strings and report `100 × unique_nonempty_user_agent_count / total_valid_requests`. Before adding a distinct value beyond `--max-unique-user-agents`, stop safely.

Acceptance criteria:

- [ ] Repeated identical User-Agents contribute one unique value but every valid line remains in the denominator.
- [ ] Missing or `-` User-Agents are excluded from the unique set.
- [ ] Exceeding the ceiling emits no partial report, explains the policy on stderr, and exits 4.

#### FR-7: Three output modes

The default is Rich terminal output. `--json` emits schema version 1, and `--csv` emits `section,rank,key,count,percentage`.

Acceptance criteria:

- [ ] `--json` and `--csv` are mutually exclusive and their combination exits 2.
- [ ] JSON parses with the standard library and CSV parses with `csv.reader`.
- [ ] Machine formats never include ANSI escapes or progress text.
- [ ] Non-TTY terminal output and `--no-color` contain no ANSI escapes.

#### FR-8: Stable process contract

Diagnostics go to stderr and result data goes to stdout. The complete exit-code contract is `0/1/2/3/4`: success, input I/O failure, usage error, strict parsing/internal format failure, and unique-cardinality exhaustion, respectively.

Acceptance criteria:

- [ ] An automated CLI test independently triggers and asserts each code.
- [ ] Fatal errors emit no completed report to stdout.
- [ ] A downstream closed pipe does not show a traceback.

### P1 — Should Ship Next

- Transparently read `.gz` paths while preserving the same streaming and exit behavior.
- Publish a reproducible benchmark recipe and environment table.
- Provide shell-completion metadata through Click.

### P2 — Could Ship Later

- Accept a configurable top-N with an enforced positive upper bound.
- Support explicitly named nginx `log_format` profiles.
- Add optional URL query stripping while preserving the raw mode as default.

## Output Data Contract

JSON contains `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. CSV normalizes all data into `section,rank,key,count,percentage`. Numeric data remains numeric in JSON; CSV uses plain decimal text. Rankings and hour ordering are identical across all modes.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | 1 GB completes in under 30 seconds on the documented laptop | Timed deterministic benchmark |
| NFR-2 | Raw lines and parsed request objects are not accumulated | Code review plus memory stress test |
| NFR-3 | Package supports CPython 3.11 | Clean-environment install and test |
| NFR-4 | Core package has at least 90% statement coverage | Coverage gate |
| NFR-5 | No network access or persisted log data | Static inspection and isolated smoke test |
| NFR-6 | Output is deterministic for identical input/options | Golden and repeated-run tests |

## Dependencies and Constraints

- Runtime: Python 3.11, Click, Rich, and standard-library dataclasses.
- Installation: pip-compatible wheel/source distribution; `pipx` recommended.
- Cost: $0 cash budget; open-source dependencies only.
- Schedule: one weekend.
- Architecture: single local process with no database, API, auth, server, cloud, or Kubernetes.

## Success Metrics

The release succeeds when all P0 acceptance criteria pass, a fresh install produces a report in under 30 seconds excluding download time, and the recorded 1 GB benchmark meets the under-30-second target. Early usage quality is tracked by correctness defects, malformed-line reports, and reproducibility of pipeline schemas rather than telemetry.

## Kill Criteria

Pause or re-scope the release if, after profiling and two optimization passes, the selected Python design cannot process the representative 1 GB fixture within 30 seconds; if exact cardinality cannot operate safely at the documented default ceiling; or if Combined Log Format validity on the agreed fixture corpus falls below 99.9%. Do not silently replace exact metrics with approximations or introduce a server/database to conceal a failed local design.

## Traceability

- Product priorities and competitive context: `STRATEGIC_PLAN.md`.
- CLI, data, algorithm, and packaging contracts: `PROJECT_ARCHITECTURE.md`.
- File-level delivery sequence and checks: `IMPLEMENTATION_PLAN.md`.
- Execution prompts for a coding session: `CLAUDE_CODE_GUIDE.md`.

