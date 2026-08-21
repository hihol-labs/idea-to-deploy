# Product Requirements: Nginx Stream Insights

## Product Summary

Nginx Stream Insights gives DevOps/SRE users four exact summaries from nginx
combined access logs through a local Python 3.11 command. It is stateless,
pip-installable, and safe for interactive terminals and machine pipelines.
`PROJECT_ARCHITECTURE.md` is authoritative for parsing, metric, output, and
exit-code semantics.

## Goals

- Analyze a finite file or stdin stream without retaining raw records.
- Report top client IPs, top error URLs, hourly percentages, and exact unique
  User-Agent share.
- Provide readable colored terminal output and stable JSON/CSV output.
- Process a representative 1 GB log in under 30 seconds on a recorded laptop.
- Fail explicitly when exact User-Agent tracking exceeds its configured limit.

## Non-Goals

Authentication, a database, an HTTP API, a server, cloud resources,
Kubernetes, dashboards, log retention, alerting, arbitrary nginx log formats,
and distributed ingestion are not part of the MVP.

## User Stories

### US-1: Read operational log streams

As an on-call SRE, I want to pipe a combined-format nginx log or name a local
file so that I can analyze data using the shell workflow I already have.

Priority: P0

Acceptance criteria:

- [ ] Omitting `INPUT` or passing `-` reads stdin; passing a path reads that file.
- [ ] The reader handles a file incrementally and does not load it all at once.
- [ ] An unreadable input produces a concise stderr diagnostic and exit 1.
- [ ] An invalid option combination produces Click help context and exit 2.

### US-2: Find dominant clients

As an SRE investigating load, I want the top 10 client IPs so that I can spot
traffic concentration quickly.

Priority: P0

Acceptance criteria:

- [ ] Counts include every syntactically valid record regardless of status.
- [ ] At most 10 rows are emitted, sorted by count descending and IP ascending on ties.
- [ ] IPv4 and IPv6 strings are preserved as logged.
- [ ] Terminal, JSON, and CSV contain the same ranks and counts.

### US-3: Find failing URLs

As a DevOps engineer, I want the top 10 URL targets returning 4xx or 5xx so
that I can identify the endpoints causing user-visible errors.

Priority: P0

Acceptance criteria:

- [ ] Only statuses from 400 through 599 inclusive contribute.
- [ ] The request target is preserved as logged, including its query string.
- [ ] At most 10 rows are sorted by count descending and URL ascending on ties.
- [ ] Terminal, JSON, and CSV contain the same ranks and counts.

### US-4: See hourly traffic shape

As a capacity engineer, I want each hour's share of valid requests so that I
can identify peaks without doing another calculation.

Priority: P0

Acceptance criteria:

- [ ] Exactly 24 buckets labeled `00` through `23` are emitted.
- [ ] Bucketing uses the hour and numeric offset in each record's timestamp.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] For non-empty valid input, unrounded bucket percentages sum to 100% within floating-point tolerance.

### US-5: Quantify User-Agent diversity

As an SRE checking client diversity, I want the exact share of distinct
non-empty User-Agents among valid requests so that I can compare client variety
to request volume.

Priority: P0

Acceptance criteria:

- [ ] The share is `100 × distinct_nonempty_user_agents / total_valid_requests`.
- [ ] Identical User-Agent strings count once; empty values do not enter the distinct set.
- [ ] The configured distinct-value boundary succeeds at the limit.
- [ ] Attempting to exceed the boundary emits no complete report and exits 4 for unique-cardinality exhaustion.
- [ ] No approximate value is presented as exact.

### US-6: Use reports in pipelines

As a platform engineer, I want JSON and CSV output so that scheduled shell jobs
can consume results without parsing terminal decoration.

Priority: P0

Acceptance criteria:

- [ ] `--json` emits one schema-versioned JSON document and no ANSI sequences.
- [ ] `--csv` emits RFC 4180 rows with `metric,rank,key,count,percentage` and no ANSI sequences.
- [ ] `--json` and `--csv` are mutually exclusive and misuse exits 2.
- [ ] Data goes to stdout and diagnostics go to stderr.

### US-7: Watch a growing file

As an on-call SRE, I want to follow an active file so that I can summarize a
bounded incident window without restarting the command.

Priority: P1

Acceptance criteria:

- [ ] `--follow` works only with a regular file path and waits for complete appended lines.
- [ ] The command does not busy-spin while waiting.
- [ ] Invalid use with stdin exits 2.
- [ ] Clean termination renders the accumulated report; interruption behavior is documented.

### US-8: Read compressed logs directly

As a DevOps engineer, I want gzip input so that I can avoid an explicit
decompression pipeline.

Priority: P2

Acceptance criteria:

- [ ] Deferred until all P0 and P1 acceptance criteria and performance evidence pass.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional input path, with omitted input and `-` mapped to stdin |
| FR-02 | Parse the conventional nginx combined format defined in `PROJECT_ARCHITECTURE.md` |
| FR-03 | Skip malformed lines, count them, and never include them in metric denominators |
| FR-04 | Produce exact top-10 client-IP and 4xx/5xx URL rankings with deterministic ties |
| FR-05 | Produce all 24 hourly counts and percentage values using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Produce exact distinct non-empty User-Agent count and share with a configurable positive guard |
| FR-07 | Render colored Rich terminal output by default when stdout is a TTY |
| FR-08 | Render the versioned JSON and CSV schemas from `PROJECT_ARCHITECTURE.md` |
| FR-09 | Implement the complete exit-code contract `0/1/2/3/4`, where 4 is unique-cardinality exhaustion |
| FR-10 | Install on Python 3.11 through pip with the `nginx-insights` command |

### P1 — Should ship after the finite-stream MVP

| ID | Requirement |
|---|---|
| FR-11 | Follow complete lines appended to a named regular file without busy waiting |

### P2 — Could ship later

| ID | Requirement |
|---|---|
| FR-12 | Detect and stream gzip-compressed finite input |
| FR-13 | Support explicitly configured nginx log formats without weakening the combined-format default |

## Output and Error Requirements

The default report includes the four required summaries and a malformed-line
warning when applicable. JSON emits `schema_version`, totals, both rankings,
24 hourly objects, and the User-Agent summary. CSV emits the common five-column
schema specified in the architecture. Percentage values are presented to at
most six decimal places; counts, not rounded percentages, drive calculations.

The complete application exit-code contract is:

| Code | Requirement |
|---:|---|
| `0` | Success, help, or version |
| `1` | Input/output operating error |
| `2` | Usage or option error |
| `3` | No valid records in finite input |
| `4` | Unique-cardinality exhaustion |

Malformed lines do not alone make an otherwise valid run fail. If every line
is malformed or the finite input is empty, the result is exit 3. On exit 4,
the CLI must not silently approximate or emit a complete success payload.

## Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | A representative 1 GB finite log completes in under 30 seconds on a documented laptop |
| Memory | Raw input and parsed records are not retained; UA exactness stops at the configured bound |
| Compatibility | Runtime and tests support Python 3.11 |
| Determinism | Equal input and options yield equal JSON/CSV bytes, except explicitly documented version metadata |
| Privacy | No network calls, persistence, or full raw-line diagnostics |
| Accessibility | `--no-color` works; machine formats never contain ANSI escapes |
| Testability | Every P0 acceptance criterion has an automated unit or CLI integration test, except the machine-specific benchmark |

## Release Acceptance

- All P0 user-story acceptance criteria pass.
- Clean-environment pip installation and console entry point pass.
- Tests exercise exit codes `0/1/2/3/4` and output separation.
- The recorded 1 GB benchmark is under 30 seconds on its stated laptop.
- No placeholders, undocumented schema fields, or conflicting metric formulas remain across the blueprint documents.

## Kill Criteria

Stop or formally re-scope the weekend MVP if profiling cannot bring the 1 GB
run below 30 seconds, the exact User-Agent guard cannot fail before unbounded
allocation, combined-format parsing cannot be made reliable on the fixture
corpus, or JSON/CSV stability would require introducing a service/database.

## Dependencies and Traceability

`STRATEGIC_PLAN.md` owns priority and success framing.
`PROJECT_ARCHITECTURE.md` owns precise data, CLI, and output contracts.
`IMPLEMENTATION_PLAN.md` maps these requirements to planned files and checks.
Behavior changes start here and in the architecture before implementation.

