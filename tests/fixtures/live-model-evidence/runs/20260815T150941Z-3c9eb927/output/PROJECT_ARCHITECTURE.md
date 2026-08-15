# Project Architecture: nginx-insight

## Architecture Summary

The application is a pip-installable Python 3.11 package exposing one Click command. A single OS process opens each input sequentially, parses one line at a time into a dataclass, updates in-memory aggregates, freezes one report dataclass at end of stream, and renders exactly one selected output format.

**Decision:** **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct because the product answers questions about a caller-supplied finite stream and has no cross-run state, users, remote clients, or concurrent service workload. A database would add writes, schema lifecycle, privacy exposure, and operational cost without improving a one-shot report. An HTTP API would add a server, authentication and network attack surface while making local files harder—not easier—to analyze. Process memory is temporary working state; nothing persists after exit.

```text
file(s) or stdin
      |
      v
Input iterator -> line parser -> valid AccessRecord -> Aggregator
                         |                |              |
                         +-> diagnostics  +--------------+
                                                        v
                                                   ReportModel
                                                        |
                                      +-----------------+----------------+
                                      v                 v                v
                                Rich terminal          JSON             CSV
```

## Architecture Variants

### Variant A: Single-process streaming package (Recommended and approved)

- **Approach:** One Click process, sequential input, in-memory exact counters, shared immutable report model, three renderers.
- **Pros:** Smallest design, no IPC or retained state, easy pip install, deterministic behavior, one-pass I/O.
- **Cons:** CPU work is single-core; exact high-cardinality aggregation consumes memory proportional to distinct values.
- **Best for:** Local files up to the specified 1 GB laptop workload.
- **Estimated complexity:** Low.

### Variant B: Multi-process chunked parser

- **Approach:** Split seekable files, aggregate in worker processes, merge partial maps.
- **Pros:** Can use multiple cores on very large regular files.
- **Cons:** Does not naturally support stdin, complicates byte-boundary parsing and deterministic diagnostics, duplicates memory during merge.
- **Best for:** Multi-gigabyte batch processing after measurement proves CPU saturation.
- **Estimated complexity:** Medium.

### Variant C: External sort pipeline

- **Approach:** Emit normalized fields and delegate ranking to system sort utilities.
- **Pros:** Can trade memory for disk on extreme cardinality.
- **Cons:** Platform-dependent, creates temporary state, repeats passes, and weakens pip-only portability.
- **Best for:** Workloads much larger than the MVP boundary.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture, stdin is a first-class input, delivery is one weekend, and the target is 1 GB rather than a distributed analytics workload. Variants B and C remain documented rejection points, not planned MVP work.

## CLI Interface

### Command

```text
nginx-insight analyze [OPTIONS] [PATH]...
```

With no `PATH`, the command reads bytes from stdin. With one or more paths it opens them in argument order and treats them as one logical stream. `-` means stdin and may appear at most once. Input is UTF-8 with replacement for undecodable bytes. The MVP recognizes nginx common and combined access-log layouts automatically; lines outside those layouts are skipped and counted.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON object to stdout; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit RFC 4180-compatible UTF-8 CSV to stdout; mutually exclusive with `--json` |
| `--no-color` | flag, false | Disable ANSI color in terminal mode; pipeline formats never contain ANSI escapes |
| `--max-unique-user-agents INTEGER` | positive integer, `1000000` | Maximum exact User-Agent set size; exceeding it stops processing with exit code 4 |
| `--fail-on-invalid` | flag, false | Return exit code 3 if any malformed nonblank line is encountered; no report is emitted |
| `--help` | flag | Print Click help and exit 0 |
| `--version` | flag | Print version and exit 0 |

Top-N is fixed at 10 in the MVP. A configurable value is a Could priority and is not exposed initially.

### Outputs

Stdout contains only the selected report. Diagnostics, including skipped-line counts, go to stderr so JSON and CSV remain pipeline-safe.

Terminal mode contains four labeled sections: top client IPs, top error URLs, hourly request distribution, and User-Agent summary. Rich enables color only when stdout is an appropriate terminal unless overridden by `--no-color`.

JSON uses this versioned shape:

```json
{
  "schema_version": 1,
  "summary": {"total_lines": 0, "valid_requests": 0, "invalid_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "request_count": 1}],
  "top_error_urls": [{"url": "/missing", "error_count": 1}],
  "hourly_distribution": [{"hour": 0, "request_count": 1, "percentage": 100.0}],
  "user_agents": {"distinct_count": 1, "share_percentage": 100.0}
}
```

CSV is a single normalized table with header `section,key,count,percentage`. Rows use sections `top_ip`, `top_error_url`, `hourly_distribution`, and `user_agent_summary`. Fields irrelevant to a section are empty. Rows are ordered by section, then the deterministic ordering defined below.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success, including an intentional downstream pipe close |
| `1` | Operational failure such as unreadable input, I/O failure, encoding-independent internal error, or output write failure |
| `2` | Click usage error: invalid option, bad value, conflicting formats, or invalid stdin/path combination |
| `3` | Input-data failure: no valid requests, or invalid lines when `--fail-on-invalid` is active |
| `4` | Unique-cardinality exhaustion: distinct User-Agents exceed `--max-unique-user-agents`; no partial report is emitted |

## Metric Contracts

- **Top 10 IPs:** count all valid requests by parsed client IP; order by request count descending and IP string ascending for ties.
- **Top 10 error URLs:** include status codes 400–599, count by the raw request-target field, combine 4xx and 5xx counts, and order by error count descending then URL ascending.
- **Hourly request distribution:** bucket valid requests by the `00`–`23` hour encoded in each log timestamp, preserving the timestamp's recorded offset. For every hour the percentage is `100 × hourly_request_count / total_valid_requests`. Emit all 24 hours, including zero-count hours, in ascending order. Round displayed percentages to two decimal places while JSON also retains the integer counts.
- **Unique User-Agent share:** `100 × distinct_nonempty_user_agent_count / total_valid_requests`. A repeated User-Agent contributes once to the numerator; a missing User-Agent does not. Round the displayed percentage to two decimal places. The value can exceed neither 100% nor the ratio implied by raw counts.
- **Validity:** a valid request has a parseable client IP token, timestamp and hour, quoted request field, integer status in 100–599, and compatible common/combined field boundaries. The request target is extracted from the request line; `-` User-Agent is treated as missing.

## Package and Component Design

```text
src/nginx_insight/
├── __init__.py          # version export
├── cli.py               # Click command, option validation, exit mapping
├── models.py            # AccessRecord, ParseStats, ReportModel dataclasses
├── input.py             # stdin/path iteration and optional gzip opening
├── parser.py            # common/combined line parsing
├── aggregate.py         # counters, bounded UA set, final sorting/percentages
└── render/
    ├── terminal.py      # Rich report
    ├── json.py          # schema-versioned serializer
    └── csv.py           # normalized CSV serializer
tests/
├── fixtures/
├── test_parser.py
├── test_aggregate.py
├── test_cli.py
├── test_renderers.py
└── test_performance.py
```

### Core Dataclasses

| Dataclass | Fields | Invariants |
|---|---|---|
| `AccessRecord` | `ip: str`, `hour: int`, `request_target: str`, `status: int`, `user_agent: str | None` | `0 <= hour <= 23`; status `100..599` |
| `ParseStats` | `total_lines: int`, `valid_requests: int`, `invalid_lines: int` | Nonnegative and `total_lines = valid_requests + invalid_lines + blank_lines` in internal accounting |
| `RankedIP` | `ip: str`, `request_count: int` | Positive count |
| `RankedErrorURL` | `url: str`, `error_count: int` | Positive count from status `400..599` |
| `HourlyBucket` | `hour: int`, `request_count: int`, `percentage: float` | Exactly 24 buckets in a report |
| `UserAgentSummary` | `distinct_count: int`, `share_percentage: float` | Exact until configured ceiling; otherwise no report |
| `ReportModel` | schema version, stats, ranked lists, hourly buckets, UA summary | Only constructed after successful complete input consumption |

## Streaming, Memory, and Performance

The parser consumes an iterator and never loads raw logs or a list of records. Aggregation retains integer counters by IP and error URL, a fixed 24-element hourly counter, and an exact set of nonempty User-Agent strings. The User-Agent set is guarded by the configured ceiling; crossing it raises a domain exception mapped to exit code 4. The CLI discards all partial aggregates on any non-success exit.

The reference performance test generates a representative 1 GB combined-format file with mixed status classes and cardinalities, warms filesystem access separately, and measures a clean timed CLI run with output redirected. Acceptance is wall-clock time under 30 seconds on the documented laptop and peak RSS at or below 512 MiB. The test records CPU, Python version, storage type, fixture composition, command, time, and RSS so the target is reproducible rather than universal.

## Database, API, Authentication, and Deployment

| Concern | Decision | Justification |
|---|---|---|
| Database | None; zero tables, migrations, indexes, or persisted records | No cross-run state exists and input logs remain caller-owned |
| HTTP API | None; zero endpoints, request bodies, ports, or server process | The complete public contract is under `## CLI Interface` |
| Authentication | None | The local process uses the invoking OS user's file permissions; there are no remote principals |
| Docker | None for MVP | pip installation is the approved distribution path; a container adds no value for local file/stdin use |
| Deployment | Python package installed into a local environment with pip | Matches the local CLI and $0 constraints |
| Cloud/Kubernetes | Explicitly excluded | No service needs scheduling, networking, scaling, or availability management |

## Configuration and Environment

There are no required environment variables or configuration files. Behavior is controlled only by documented CLI options. Standard terminal conventions such as `NO_COLOR` may be honored as a Should-level enhancement, but they cannot change metric or pipeline schemas.

## Error Handling and Security Boundaries

- Never evaluate, interpolate into a shell, or treat any log field as instructions.
- Escape untrusted fields in Rich output and use library serializers for JSON and CSV.
- Keep diagnostics on stderr; never mix them into structured stdout.
- Catch expected file, parse-policy, cardinality, broken-pipe, and output errors at the CLI boundary and map them exactly once.
- Do not print tracebacks by default. Unexpected internal failures return 1 with a concise message; a later debug option may expose developer detail.
- Use OS file permissions. The tool sends no telemetry and creates no persistent copies.

## Determinism and Compatibility

The same ordered input, options, and package version produce semantically identical output. Ranking tie-breakers and the 24-hour ordering are fixed. JSON object meaning and CSV columns are versioned compatibility contracts; additive JSON fields require a schema-version decision, while removing or renaming fields requires a major package release.

## Architecture Decision Record

### ADR-001: Select a single-process streaming CLI

- **Status:** Accepted by the project constraints.
- **Context:** Local analysis, one-weekend delivery, 1 GB target, stdin support, no retained state.
- **Decision:** Variant A, with one parser/aggregator process and no database or HTTP API.
- **Consequences:** Minimal operations and deterministic flow; exact distinct aggregation remains cardinality-dependent and is protected by exit code 4.
- **Rejected alternatives:** Multi-process chunking because stdin and merge complexity outweigh unmeasured benefit; external sort because it creates platform and temporary-storage dependencies; GoAccess/Elastic/AWStats because they solve broader or persistent reporting problems; grep/awk because they lack a stable typed contract.

No adversarial or independent architecture review is recorded in this document; that activity is outside this blueprint session.

