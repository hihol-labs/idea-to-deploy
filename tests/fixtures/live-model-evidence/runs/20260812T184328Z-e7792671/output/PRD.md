# Product Requirements Document: nginx-insights

## 1. Product Summary

`nginx-insights` gives DevOps/SRE users a quick, exact snapshot of a finite nginx combined access-log stream. It is a local pip-installable Python 3.11 CLI, not a service. It reads a file or stdin once and reports top IPs, error URLs, hourly distribution, and unique User-Agent share as colored terminal text, JSON, or CSV.

## 2. Problem and Outcome

Operators frequently have access to a raw log before they have a useful dashboard query. Existing choices are either ad hoc shell pipelines that are easy to get wrong or systems that require persistence and operations. The desired outcome is a reproducible report suitable both for a human incident check and for a pipeline, with no database, server, authentication, cloud, or Kubernetes dependency.

## 3. Goals and Non-Goals

### Goals

- Parse nginx combined access-log input incrementally from a file or stdin.
- Compute the four approved views exactly and deterministically.
- Complete a representative 1 GB input in under 30 seconds on a documented laptop.
- Provide Rich terminal, JSON, and CSV modes with stable semantics.
- Fail predictably using the complete `0/1/2/3/4` exit-code contract.
- Install through pip on Python 3.11 at zero infrastructure cost.

### Non-Goals

- Authentication, authorization, users, or tenancy.
- Database storage, retained history, HTTP API, server, daemon, cloud, or Kubernetes.
- A browser dashboard or interactive TUI.
- Arbitrary nginx `log_format` configuration in the MVP.
- Geo-IP, bots, latency percentiles, bandwidth analysis, or alerting.
- Indefinite `tail -f` behavior; a producer may pipe a finite stream through stdin.

## 4. Personas

- **On-call SRE:** needs a fast summary with visible invalid-input warnings.
- **DevOps engineer:** embeds deterministic JSON/CSV in shell and CI pipelines.
- **Backend engineer:** correlates a traffic or error spike to clients, URLs, and hours.

## User Stories

### US-1 — Analyze a local log in one command

As an on-call SRE, I want to pass a combined access-log path so that I can see the agreed incident summary without composing multiple shell pipelines.

Priority: P0

Acceptance criteria:

- [ ] `nginx-insights access.log` processes the file sequentially and prints one terminal report.
- [ ] The report contains total valid and invalid lines, top-10 IPs, top-10 4xx/5xx URLs, 24 hourly buckets, and unique User-Agent count/share.
- [ ] Equal counts use the same deterministic tie order in every output format.
- [ ] A successful valid or empty stream exits 0.

### US-2 — Consume a pipeline stream

As a DevOps engineer, I want to read from stdin so that decompression, SSH, or filtering tools can feed the analyzer without a temporary file.

Priority: P0

Acceptance criteria:

- [ ] Omitting `PATH` or using `-` reads stdin lazily until EOF.
- [ ] The application never closes stdin and never seeks it.
- [ ] A 1 GB stream is not loaded into memory as raw lines or records.

### US-3 — Find traffic sources and failing routes

As a backend engineer, I want ranked IP and error-URL views so that I can identify dominant clients and routes returning 4xx/5xx.

Priority: P0

Acceptance criteria:

- [ ] IP counts include every valid record and return at most 10 entries.
- [ ] Error URL counts include only statuses 400–599 inclusive and return at most 10 entries.
- [ ] Ranking is count descending, then value ascending.

### US-4 — Understand time and client diversity

As an SRE, I want hourly percentages and unique User-Agent share so that I can understand load shape and client diversity at a glance.

Priority: P0

Acceptance criteria:

- [ ] The report contains all hours 00–23 based on the hour written in each valid log timestamp.
- [ ] Each hourly percentage is computed as `100 × hourly_request_count / total_valid_requests` and is `0.0` when the denominator is zero.
- [ ] Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests` and is `0.0` when the denominator is zero.
- [ ] A literal missing User-Agent value `-` counts as one distinct observed value.

### US-5 — Automate with structured output

As a DevOps engineer, I want JSON or CSV output so that downstream tools can consume results without parsing terminal decoration.

Priority: P0

Acceptance criteria:

- [ ] `--json` emits one documented JSON object plus a trailing newline.
- [ ] `--csv` emits the documented normalized header and section rows with RFC 4180 quoting.
- [ ] `--json` and `--csv` are mutually exclusive and misuse exits 2.
- [ ] Structured output never contains ANSI control sequences; diagnostics use stderr.

### US-6 — Detect damaged input

As an operator, I want malformed lines counted or rejected explicitly so that a plausible-looking report cannot hide input quality problems.

Priority: P1

Acceptance criteria:

- [ ] Default mode counts and skips malformed lines and reports the count.
- [ ] `--fail-on-invalid` stops on the first malformed line, emits a path/stdin and line-number diagnostic without the raw content, and exits 3.
- [ ] An unreadable file or UTF-8 decoding failure exits 3 and emits no report.

### US-7 — Bound exact cardinality

As an operator, I want a deterministic memory guard so that adversarial or unusual cardinality does not crash the laptop unpredictably.

Priority: P1

Acceptance criteria:

- [ ] `--max-unique` is a positive integer with default `5000000`.
- [ ] It applies separately to IP, error-URL, and User-Agent distinct-key trackers.
- [ ] Adding a distinct value past the ceiling emits no report and exits 4.
- [ ] The tool never substitutes approximate values.

### US-8 — Follow a growing file

As an on-call SRE, I want an optional live follow mode so that I can watch a continuing incident without restarting the command.

Priority: P2

Acceptance criteria:

- [ ] Deferred beyond MVP; design must not imply that EOF-waiting or periodic reports already exist.

## 6. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept zero or one path argument; absent or `-` means stdin |
| FR-02 | Parse UTF-8 nginx combined-format lines into the fields defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) |
| FR-03 | Count top 10 IPs across all valid requests |
| FR-04 | Count top 10 request targets for status 400–599 |
| FR-05 | Emit 24 local-log-hour counts and percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Emit distinct User-Agent count and its percentage of valid requests |
| FR-07 | Render the same report model as Rich text, JSON, or normalized CSV |
| FR-08 | Use deterministic ranking, numeric rounding, CSV line endings, and JSON key structure |
| FR-09 | Keep stdout data-only and stderr diagnostic-only |

### P1 — Should ship for release readiness

| ID | Requirement |
|---|---|
| FR-10 | Count malformed lines by default and implement fail-fast invalid-line mode |
| FR-11 | Enforce the exact-cardinality ceiling and unique exit code 4 |
| FR-12 | Provide `--help`, `--version`, and TTY-aware `--color/--no-color` behavior |
| FR-13 | Publish a pip-installable wheel/source distribution and console script |
| FR-14 | Record reproducible correctness, coverage, and performance verification |

### P2 — Could follow

| ID | Requirement |
|---|---|
| FR-15 | Add explicitly requested indefinite follow mode with periodic snapshot semantics in a future PRD revision |

## 7. Input Contract

Each non-empty record must follow standard nginx combined format:

```text
remote_addr ident remote_user [day/month/year:hour:minute:second zone] "request" status bytes "referer" "user-agent"
```

The parser needs remote address, timestamp, request target, status, and User-Agent; it validates the surrounding grammar so quoted spaces are handled. Status must be a three-digit integer. Timestamp must include a numeric offset. Bytes may be digits or `-`. Request `-` yields target `-`; otherwise the middle token of `METHOD TARGET PROTOCOL` is used. Empty, truncated, undecodable, or structurally mismatched lines are invalid.

## 8. Output and Exit Contract

The precise JSON/CSV schemas and CLI options are normative in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) under `## CLI Interface`.

| Code | Contract |
|---:|---|
| `0` | Successful command, including zero valid records under skip policy |
| `1` | Operational/internal error or stdout write failure |
| `2` | Usage/options error |
| `3` | Input/read/decode/strict-parse failure |
| `4` | Unique-cardinality exhaustion |

Failures 1, 3, and 4 do not produce a normal report. JSON/CSV stdout remains free of warnings and terminal control codes.

## 9. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Process a representative 1 GB log in <30 seconds on the documented reference laptop | Timed release-candidate benchmark |
| NFR-02 | Operate in one pass without retaining raw lines/records | Code review plus memory benchmark |
| NFR-03 | Support CPython 3.11 and pip installation | Clean-environment wheel smoke test |
| NFR-04 | Maintain at least 90% test coverage | Coverage gate |
| NFR-05 | Never send logs or telemetry over a network | Dependency review and offline integration test |
| NFR-06 | Produce deterministic JSON/CSV independent of TTY, locale, timezone, and platform line endings | Golden tests under varied environment settings |
| NFR-07 | Escape terminal markup and serialize structured data with standard encoders | Adversarial fixture tests |

## 10. Release Acceptance

- All P0 stories and P1 fault paths pass on Python 3.11.
- The exact `0/1/2/3/4` exit mapping has integration coverage.
- A fixture with ties, quoted spaces, all status classes, offsets, missing values, malformed lines, Unicode, and formula-like CSV values passes golden tests.
- The built wheel installs into a clean environment and its console command passes help, stdin, JSON, and CSV smoke tests.
- The documented reference benchmark meets the 1 GB / 30 s target without disabling exactness or cardinality protection.

## 11. Kill Criteria

Pause release and revisit scope if any of the following occurs:

- The profiled single-process Python implementation cannot process the agreed representative 1 GB fixture in under 30 seconds on the reference laptop.
- Exact P0 results cannot be maintained within the declared cardinality limit and reasonable laptop memory.
- Supporting observed nginx inputs requires arbitrary `log_format` parsing rather than the fixed combined grammar.
- Delivery requires a database, HTTP service, authentication, paid infrastructure, or work beyond one weekend.
- JSON/CSV semantics cannot be made stable across platforms without breaking the CLI contract.

Any behavior change begins by updating this PRD, then reconciling architecture and implementation guidance.
