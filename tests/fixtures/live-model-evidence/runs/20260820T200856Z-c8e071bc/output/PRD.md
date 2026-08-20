# Product Requirements Document: nginx-report

## 1. Purpose

`nginx-report` gives DevOps and SRE engineers fast, local, deterministic summaries of nginx combined access logs without infrastructure. It processes a file or stdin as a stream and reports top client IPs, top error-producing request targets, UTC hourly request percentages, and unique User-Agent share.

The MVP runs on Python 3.11, installs through pip, defaults to colored terminal output, and supports JSON and CSV pipelines.

## 2. Goals and Success Criteria

- Produce all four required metrics correctly from valid combined-format records.
- Process a representative 1 GB file in under 30 seconds on the documented laptop baseline.
- Keep peak RSS under 512 MiB for the representative cardinality profile.
- Provide deterministic terminal, JSON, and CSV results with clean stdout/stderr separation.
- Install and run in a fresh Python 3.11 virtual environment.

## 3. Non-goals

Authentication, authorization, accounts, a database, retained history, HTTP or other network API, server/daemon mode, cloud hosting, Docker as a requirement, Kubernetes, dashboards, alerting, and arbitrary nginx formats are outside the MVP. The tool does not replace a centralized log platform.

## 4. Personas

- **On-call SRE:** needs a trustworthy summary during an incident.
- **DevOps automation author:** needs stable structured output and process exit semantics.
- **Platform engineer:** needs offline analysis in local or restricted environments.

## User Stories

### US-1 — Analyze a local file

As an on-call SRE, I want to analyze an nginx log file with one command so that I can identify dominant clients and failing request targets quickly.

**Priority:** P0

**Acceptance criteria:**

- [ ] `nginx-report access.log` streams the file and emits all four report sections.
- [ ] Top lists default to 10 items, order by count descending, and break ties by key ascending.
- [ ] A missing or unreadable file produces no report, writes a diagnostic to stderr, and exits `1`.

### US-2 — Analyze a pipeline stream

As a DevOps engineer, I want to pipe logs through stdin so that the tool composes with decompression, SSH, and shell workflows.

**Priority:** P0

**Acceptance criteria:**

- [ ] Omitting `INPUT` or passing `-` reads a non-seekable stdin stream once.
- [ ] The same records produce identical report data from stdin and a file.
- [ ] The process does not load the full stream into memory.

### US-3 — Consume JSON in automation

As an automation author, I want stable JSON output so that another process can consume metrics without scraping terminal text.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits exactly one valid JSON document with `schema_version: 1`.
- [ ] It contains summary counts, ranked IPs, ranked error URLs, 24 ordered hourly entries, and User-Agent metrics.
- [ ] stdout contains no ANSI escapes or warnings.

### US-4 — Consume CSV in a pipeline

As a platform engineer, I want normalized CSV output so that I can load results into standard command-line and spreadsheet tools.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--csv` emits the fixed header `section,rank,key,count,percentage` and properly escaped rows.
- [ ] It represents every report section, including all 24 UTC hours.
- [ ] `--csv --json` is rejected as usage error with exit `2` and no report.

### US-5 — Understand data quality

As an SRE, I want malformed records accounted for so that I do not mistake a partial parse for complete evidence.

**Priority:** P0

**Acceptance criteria:**

- [ ] Invalid lines increment `invalid_lines` and do not affect metrics.
- [ ] If a non-empty input contains at least one valid request, a report is emitted with a concise invalid-line warning.
- [ ] If a non-empty input has zero valid requests, the command emits no report and exits `3`.
- [ ] Empty input is a successful zero-valued report with exit `0`.

### US-6 — Bound exact-cardinality memory

As an operator, I want a deterministic cardinality ceiling so that pathological logs fail explicitly instead of exhausting my laptop or silently approximating results.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--max-unique` applies independently to distinct IP, error-target, and non-empty User-Agent keys.
- [ ] Before exceeding the limit, processing stops, no report is written, and the command exits `4`.
- [ ] The diagnostic identifies the exhausted dimension without printing raw sensitive values.

### US-7 — Adjust ranking depth

As a DevOps engineer, I want to set `--top` so that I can inspect more or fewer ranked values without changing metric definitions.

**Priority:** P1

**Acceptance criteria:**

- [ ] Values from 1 through 1000 are accepted and affect both ranked sections.
- [ ] Invalid values are usage errors with exit `2`.

### US-8 — Disable terminal color

As an operator, I want color to follow terminal conventions so that redirected reports remain clean.

**Priority:** P1

**Acceptance criteria:**

- [ ] Default text uses color only on a TTY.
- [ ] `--no-color` and `NO_COLOR` disable ANSI styling.
- [ ] JSON and CSV never include ANSI styling.

### US-9 — Read compressed files directly

As an operator, I want optional gzip input so that I can avoid a separate decompression command.

**Priority:** P2

This is deferred; `gzip -dc access.log.gz | nginx-report --json` is the MVP workaround.

## 6. Functional Requirements

### P0 — Must Ship

| ID | Requirement |
|---|---|
| FR-1 | Accept one combined-format file path, omitted input, or `-` for stdin |
| FR-2 | Parse required address, timestamp, request target, status, and optional User-Agent fields one line at a time |
| FR-3 | Report top 10 IPs by valid request count |
| FR-4 | Report top 10 verbatim request targets by count for statuses `400..599` |
| FR-5 | Report 24 UTC hourly buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-6 | Report User-Agent share as `100 × distinct_nonempty_user_agent_count / total_valid_requests` |
| FR-7 | Emit TTY-aware Rich text by default, schema-versioned JSON with `--json`, or normalized CSV with `--csv` |
| FR-8 | Apply deterministic ranking, stream separation, malformed-line accounting, and the exit contract in `PROJECT_ARCHITECTURE.md` |
| FR-9 | Enforce a configurable exact-cardinality guard and exit `4` on exhaustion |
| FR-10 | Package as a pip-installable Python 3.11 project with `nginx-report` console entry point |

### P1 — Should Ship

| ID | Requirement |
|---|---|
| FR-11 | Allow `--top 1..1000` and `--max-unique` positive integer overrides |
| FR-12 | Support `--no-color`, `NO_COLOR`, `--version`, and complete help text |

### P2 — Could Ship Later

| ID | Requirement |
|---|---|
| FR-13 | Detect/read gzip files directly |
| FR-14 | Support explicitly configured custom nginx log formats |

## 7. Metric and Ordering Contract

- The denominator for hourly percentages and User-Agent share is `total_valid_requests`.
- Hourly distribution uses the literal formula `100 × hourly_request_count / total_valid_requests`; it is a percentage, not an unscaled fraction.
- Timestamps are normalized to UTC before selecting hour buckets.
- `-` User-Agent values are not distinct agents but their valid requests remain in the denominator.
- Request targets include query strings exactly as logged.
- Ranked ties use key ascending after count descending.
- Zero valid requests yields zero percentages; only an empty input may emit that zero report successfully.

## 8. Output and Exit Contract

The complete interface, JSON schema, CSV schema, and stdout/stderr rules are normative in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`.

| Exit | Product meaning |
|---:|---|
| `0` | Success, including empty input |
| `1` | I/O or unexpected runtime failure |
| `2` | CLI usage failure |
| `3` | Non-empty input with zero valid requests |
| `4` | Unique-cardinality exhaustion |

Failure exits write no report to stdout.

## 9. Non-functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Representative 1 GB log completes in under 30 seconds on the documented laptop baseline |
| NFR-2 | Representative benchmark peak RSS remains below 512 MiB |
| NFR-3 | Input is consumed in one pass; raw records are not retained |
| NFR-4 | Identical input/options produce byte-stable JSON and CSV output |
| NFR-5 | Log-derived terminal values are escaped; serializers handle JSON/CSV escaping |
| NFR-6 | No network calls, telemetry, persistence, credentials, or services |
| NFR-7 | Parser, aggregator, and renderers reach at least 90% line coverage |

## 10. Release Acceptance

- All P0 stories and acceptance criteria pass on Python 3.11.
- Unit, CLI, golden-schema, package-install, and representative benchmark checks pass.
- The complete exit-code contract is tested end-to-end.
- Built wheel installs in a clean venv and reads both file and stdin fixtures.
- Documentation matches implemented schemas and metric definitions.

## 11. Kill Criteria

Do not ship if the 1 GB target remains over 30 seconds after profiling, the exact-cardinality strategy exceeds its declared memory envelope on representative data, any machine format is nondeterministic, or malformed input can yield trustworthy-looking success with zero valid records. Revisit runtime or scope; do not introduce a database/API to conceal a failed local CLI design.

## 12. Dependencies

`PROJECT_ARCHITECTURE.md` is authoritative for technical interfaces. `IMPLEMENTATION_PLAN.md` maps these requirements to an ordered build sequence. `STRATEGIC_PLAN.md` contains prioritization and release rationale.
