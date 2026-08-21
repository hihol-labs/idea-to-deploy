# Project Architecture: Nginx Stream Analyzer

## Context and Decision

The chosen architecture is a pip-installed Python 3.11 command that runs as one operating-system process and performs a single streaming pass over one nginx access-log source. The binding decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, migrations, retained sensitive traffic data, cleanup, and operational cost even though the four reports are calculated completely during one invocation. An HTTP API would introduce a long-running server, authentication and network threat surfaces, deployment work, and request lifecycle semantics that provide no benefit to a local or piped log analysis task. Process memory is temporary working state, not persistence; it is discarded on exit.

The obvious single-process architecture is pre-approved. Alternatives are recorded for context, not offered as open choices:

| Approach | Decision | Reason |
|---|---|---|
| Single-process Python streaming CLI | Selected | Smallest deployable unit, direct stdin support, sufficient for 1 GB/30 s target |
| Multiprocessing pipeline | Rejected for MVP | Serialization, ordering, startup, and complexity costs precede measured need |
| Go implementation | Rejected | Conflicts with required stack; optimize measured Python hot paths first |
| GoAccess | Buy/use alternative | Excellent general analyzer, but not this focused machine-output contract |
| Elastic/Logstash/Kibana or AWStats | Rejected | Persistence/service/reporting footprint conflicts with local stateless scope |
| `grep`/`awk` chain | Rejected | Harder to make portable, validated, and schema-stable |

## Quality Attributes

- Performance: process a 1 GB uncompressed local file in under 30 seconds on the documented reference laptop.
- Memory safety: never buffer the input; bound exact unique-key tracking with a configurable limit.
- Determinism: equivalent records yield stable JSON/CSV ordering and numerically consistent reports.
- Operability: use stdin/stdout/stderr conventions and complete exit codes.
- Portability: support Python 3.11 on common Linux/macOS developer systems; Windows is best-effort for MVP.
- Privacy: perform no network calls and retain no input after process exit.

## System Context

```text
nginx log file ─┐
                ├─> Click CLI -> streaming parser -> accumulator -> report model
stdin pipe ─────┘                                      │              │
                                                       │              ├─> Rich terminal
                                                       │              ├─> JSON stdout
                                                       │              └─> CSV stdout
                                                       └─> diagnostics stderr
```

There is one process, one reader, one parser, one accumulator, and one renderer selected at startup. Rendering starts only after end-of-input so no partial success document is emitted.

## Component Design

| Module | Responsibility | Key types/functions |
|---|---|---|
| `src/nginx_stream_analyzer/cli.py` | Click command, option validation, stream ownership, exception-to-exit mapping | `main()`, `OutputFormat` |
| `src/nginx_stream_analyzer/models.py` | Typed immutable parsed record and final report structures | `AccessRecord`, `AnalysisReport`, `RankedCount` dataclasses |
| `src/nginx_stream_analyzer/parser.py` | Precompiled combined-log parser and timestamp/status validation | `parse_line()` returning record or structured parse error |
| `src/nginx_stream_analyzer/aggregator.py` | One-pass counters, cardinality guards, percentage calculation | `StreamingAggregator.consume()`, `.finish()` |
| `src/nginx_stream_analyzer/renderers/terminal.py` | Rich tables and concise diagnostics | `render_terminal()` |
| `src/nginx_stream_analyzer/renderers/json.py` | Versioned deterministic JSON document | `render_json()` |
| `src/nginx_stream_analyzer/renderers/csv.py` | Normalized deterministic CSV rows | `render_csv()` |
| `src/nginx_stream_analyzer/errors.py` | Domain exceptions carrying public exit semantics | `InputError`, `MalformedLogError`, `OutputError`, `CardinalityError` |

Dependency direction is `cli -> parser/aggregator/renderers -> models`; renderers never parse input, and the aggregator never writes output.

## Streaming Data Flow

1. Click validates mutually exclusive output flags and opens `PATH` in text mode, or uses stdin for `-`/omitted path.
2. The reader iterates line by line with no whole-file read.
3. The parser extracts remote IP, timestamp hour, request target, status, and User-Agent from nginx combined format.
4. A malformed line increments `invalid_lines`; parsing continues unless strict handling makes malformed input fatal.
5. For each valid record, the accumulator increments total requests, the hour bucket, IP count, error-URL count only for status 400–599, and the User-Agent set.
6. Before inserting any new IP, error URL, or User-Agent key, the relevant exact-cardinality cap is checked. Exhaustion stops safely with code 4.
7. At EOF, the aggregator constructs a report, sorting rankings by descending count then ascending key for deterministic ties.
8. The selected renderer writes one complete representation to stdout; diagnostics go to stderr.

Top-10 calculations are exact within accepted cardinality limits. The design does not pretend that streaming alone makes exact distinct-key aggregation constant-memory.

## Data Model and Metric Definitions

There are no database tables. The complete ephemeral model is:

| Field | Type | Rule |
|---|---|---|
| `total_lines` | `int` | All nonempty input lines observed |
| `total_valid_requests` | `int` | Lines successfully parsed into an `AccessRecord` |
| `invalid_lines` | `int` | Nonempty lines rejected by parser |
| `ip_counts` | `dict[str, int]` | Exact count per normalized textual client address |
| `error_url_counts` | `dict[str, int]` | Exact count per request target for status 400–599 |
| `hour_counts` | `list[int]` length 24 | Bucket by hour encoded in each nginx timestamp, preserving its logged local hour |
| `user_agents` | `set[str]` | Exact distinct User-Agent strings, including `-` as the literal missing value |

Top lists contain at most 10 entries. Hourly request distribution is a percentage for each hour `00`–`23`, using the literal formula `100 × hourly_request_count / total_valid_requests`; when there are no valid requests, every hourly percentage is `0.0`. Percentages are rounded to two decimal places only at serialization/render time.

Unique User-Agent share means the percentage of valid requests represented by distinct User-Agent values: `100 × unique_user_agent_count / total_valid_requests`; it is `0.0` when there are no valid requests. The report also exposes the numerator and denominator to prevent misinterpretation. This can exceed intuitive “traffic share” interpretations only up to 100% because each valid request contributes one User-Agent value.

## Cardinality and Resource Policy

`--max-unique INTEGER` defaults to `1_000_000` and independently caps distinct IPs, distinct error URLs, and distinct User-Agents. Existing-key increments remain allowed at the cap. Attempting to add a new key beyond any cap raises `CardinalityError`, writes the exhausted dimension and configured limit to stderr, emits no success report, and exits 4. The limit must be positive. This explicit failure preserves exactness; the MVP does not silently approximate or drop keys.

Input is processed with the platform’s buffered file object. Rich is never invoked per line. Performance tests separately record elapsed time and peak resident memory.

## CLI Interface

### Command

```text
nginx-analyzer [OPTIONS] [PATH]
```

`PATH` is an nginx combined access-log file. `PATH=-` or omitted `PATH` reads stdin. Exactly one input stream is processed per invocation. UTF-8 decoding uses replacement for invalid byte sequences and records such lines as malformed if they cannot match the grammar.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON document to stdout; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized CSV to stdout; mutually exclusive with `--json` |
| `--color / --no-color` | auto | Control color in terminal mode; ignored by machine formats; auto requires a TTY and honors `NO_COLOR` |
| `--strict` | false | Stop on the first malformed nonempty line with exit 1 instead of counting and continuing |
| `--max-unique INTEGER` | `1000000` | Positive per-dimension exact-cardinality cap; exhaustion exits 4 |
| `--version` | n/a | Print package version and exit 0 |
| `--help` | n/a | Print Click help and exit 0 |

### Inputs

The MVP accepts nginx combined format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

IPv4 and IPv6 textual addresses are accepted. Request target is taken from the request field; a request of `-` has URL `-`. Status must be a three-digit integer. Blank lines are ignored and do not increment `total_lines`. Compressed files and custom `log_format` definitions are post-MVP.

### Outputs

- Default terminal: Rich summary header and four tables/values. Rankings show rank, value, count, and percentage of valid requests. Hours always show all 24 buckets. Color is never written to redirected output unless forced.
- JSON: one UTF-8 object with `schema_version`, input statistics, `top_ips`, `top_error_urls`, `hourly_request_distribution`, and `unique_user_agents` (`count`, `share_percentage`). Rankings are arrays of `{rank, value, count, percentage}`; hours use `{hour, count, percentage}`.
- CSV: UTF-8 with header `schema_version,section,rank,key,count,percentage`. Sections are `top_ip`, `top_error_url`, `hour`, and `unique_user_agents`; non-applicable rank is empty. Quoting follows Python `csv` rules.
- stderr: warnings and failures only. Machine-readable stdout remains uncontaminated.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Successful analysis and complete output, including empty input |
| 1 | Log-data failure: strict-mode malformed line or analysis invariant failure |
| 2 | CLI usage error: invalid/mutually exclusive option or invalid argument |
| 3 | Input/output system error: cannot open/read input or write output |
| 4 | Unique-cardinality exhaustion for IPs, error URLs, or User-Agents |

Broken-pipe handling follows pipeline convention: close cleanly without a traceback; if output cannot otherwise be completed, map it to code 3.

## Error and Diagnostics Policy

Errors use concise messages prefixed with `error:` and never include log content by default. Non-strict malformed lines produce an end summary on stderr containing counts but not raw potentially sensitive lines. Every domain exception maps in `cli.py` to exactly one documented exit code; unexpected internal exceptions map to code 1 with a concise message unless debug behavior is explicitly added later.

## Security and Privacy

- No network, subprocess, plugin, eval, or dynamic-code behavior exists.
- Logs are untrusted data; parser fields never become format strings or terminal markup.
- Terminal values are rendered with Rich markup disabled/escaped.
- CSV uses the standard writer; JSON uses the standard encoder.
- No input lines or aggregates are persisted, and diagnostics avoid echoing sensitive URLs or User-Agents.
- Symlink and file permissions follow the invoking user; the CLI does not elevate privileges.

## Packaging and Deployment

Distribution is a standard Python package with a `src/` layout, `pyproject.toml`, and console entry point `nginx-analyzer = nginx_stream_analyzer.cli:main`. Runtime dependencies are Click and Rich. Deployment means `python -m pip install nginx-stream-analyzer` into a Python 3.11 environment. There is no Docker image, Compose file, daemon, service manager, cloud target, or Kubernetes manifest because those would contradict the approved local CLI delivery model.

No environment variables are required. `NO_COLOR`, when present, is honored as a conventional presentation override; it is not application configuration.

## Observability

The tool’s observability surface is its stderr diagnostic summary, exit code, elapsed time exposed only in terminal mode, and deterministic structured report. It emits no telemetry. Benchmark scripts record command, environment, input size/hash, wall time, throughput, and peak RSS outside the product process.

## Test Strategy

- Parser unit fixtures: IPv4/IPv6, quoted fields, timezone offsets, `-`, malformed status/request/timestamp, Unicode replacement.
- Aggregator unit tests: 4xx/5xx boundaries, top-10 tie order, all hours, zero denominator, exact UA percentage, each cardinality dimension.
- CLI integration tests: file/stdin parity, option conflicts, TTY color behavior, stderr separation, and codes 0/1/2/3/4.
- Golden serialization tests: JSON keys/types and CSV header/sections/quoting.
- Property tests where useful: counts never negative; valid + invalid equals nonblank total; hourly counts sum to valid count.
- Performance test: generated 1 GB representative combined log on a documented laptop, under 30 seconds, with peak RSS recorded.

## Architectural Runway

Before feature work: establish the `src/` package and console entry point, freeze parsed/report dataclasses and machine-output schemas, create representative fixtures, and add a benchmark generator/runner. No database, auth system, API scaffold, Docker, or CI deployment platform belongs in the runway.

## Decision Consequences

The architecture is easy to install, audit, and remove and has no service operations. It trades arbitrary-cardinality exact analysis for explicit bounded exactness; code 4 tells callers when the configured resource envelope is insufficient. It also intentionally supports only combined format in the MVP. Scaling beyond one host or retaining historical results requires a separate product decision, not hidden evolution of this CLI.
