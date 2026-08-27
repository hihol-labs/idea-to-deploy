# Project Architecture: Nginx Stream Analyzer

## Architecture Drivers

- Local Python 3.11 CLI, installed through pip.
- One sequential pass over a file or standard input; no retained raw records.
- Exact required metrics, with an explicit safety failure if unique cardinality exceeds the configured ceiling.
- Target: analyze 1 GB in under 30 seconds on a documented laptop.
- Human-first Rich output plus stable JSON and CSV contracts.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** Click invokes an input/parser/aggregator pipeline and one renderer in the same process.
- **Pros:** minimal startup and serialization overhead, deterministic exits, easy pip install, straightforward testing.
- **Cons:** one CPU-bound parsing path; exact high-cardinality sets require a guard.
- **Best for:** local one-shot analysis under the one-weekend constraint.
- **Estimated complexity:** Low.

### Variant B: Multiprocessing chunk parser

- **Approach:** split seekable files into byte ranges, parse in workers, merge partial aggregates.
- **Pros:** may use multiple cores on very large regular files.
- **Cons:** cannot naturally split stdin, complicates line boundaries and errors, increases memory and weekend risk.
- **Best for:** a later version after profiling demonstrates CPU saturation.
- **Estimated complexity:** Medium.

### Variant C: Shell pipeline of specialized passes

- **Approach:** compose multiple commands or repeated file passes per metric.
- **Pros:** individually simple transformations.
- **Cons:** repeated I/O, fragile quoting/parsing, inconsistent errors, poor Windows portability.
- **Best for:** ad hoc manual analysis, not this product.
- **Estimated complexity:** Low initially, high to make reliable.

### Recommendation

Variant A is selected. The single-process architecture is the obvious fit for pip installation, stdin support, $0 infrastructure, and one-weekend delivery. Variant B is a measured performance contingency, not MVP scope.

## Architecture Decision

**"no database — stateless streaming processing; no HTTP API — CLI-only tool"**

Both constraints are correct because the requested output is derived entirely from the current input stream and has no cross-run state. A database would add writes, schema lifecycle, disk usage, and privacy exposure without improving any required metric. An HTTP API would turn a local utility into a long-running service requiring networking, authentication, deployment, and operations; stdin/stdout and exit codes already provide the proper automation boundary.

Authentication is therefore not applicable: the process reads only paths and streams available to the invoking OS user. Deployment means publishing a Python wheel/source distribution, not deploying a service. Docker, cloud resources, and Kubernetes are deliberately absent.

## Component Model

```text
Click CLI
  -> InputSource (file or stdin)
  -> AccessLogParser (line -> ParsedRecord | malformed)
  -> StreamAggregator (constant-pass counters + guarded unique set)
  -> AnalysisResult (frozen dataclasses)
  -> TextRenderer | JsonRenderer | CsvRenderer
  -> stdout

Diagnostics -----------------------------------------------> stderr
Exit policy ------------------------------------------------> process status
```

| Component | Planned path | Responsibility |
|---|---|---|
| CLI | `src/nginx_stream_analyzer/cli.py` | Options, stream selection, renderer selection, exit mapping |
| Parser | `src/nginx_stream_analyzer/parser.py` | Parse supported nginx combined/common lines and timestamps |
| Models | `src/nginx_stream_analyzer/models.py` | `ParsedRecord`, `AnalysisResult`, ranked-item dataclasses |
| Aggregator | `src/nginx_stream_analyzer/aggregate.py` | Count requests, errors, hours, IPs, and guarded unique agents |
| Errors | `src/nginx_stream_analyzer/errors.py` | Typed domain failures mapped to exits |
| Renderers | `src/nginx_stream_analyzer/renderers/{text,json,csv}.py` | Stable format-specific serialization |
| Entry point | `src/nginx_stream_analyzer/__main__.py` | `python -m` delegation |

Dependency direction is CLI -> domain pipeline -> immutable result -> renderer. Renderers never parse input; the parser never formats output.

## Data Model and Streaming Algorithm

`ParsedRecord` fields:

| Field | Type | Meaning |
|---|---|---|
| `ip` | `str` | Client address token |
| `timestamp` | aware `datetime` | Nginx timestamp including numeric offset |
| `target` | `str` | Request target exactly as logged |
| `status` | `int` | HTTP response status |
| `user_agent` | `str | None` | Combined-format agent; missing for common format |

The aggregator retains only counters and the exact unique User-Agent set:

- `total_lines`, `total_valid_requests`, and `malformed_lines` integers.
- IP `Counter[str]`.
- error-target `Counter[str]` for records whose status is 400–599.
- 24-element hourly count array, using the hour encoded in each record's timestamp.
- exact `set[str]` of present User-Agent values, capped by `--max-unique-user-agents`.

No raw record survives its loop iteration. Rankings use deterministic ordering: count descending, then key lexicographically ascending, and return at most `--top` entries (default 10). The error ranking combines 4xx and 5xx responses and includes per-target `error_count`; the machine formats also include separate `client_error_count` and `server_error_count` fields.

Hourly request distribution is a percentage for every hour `00` through `23`, including zero-value hours, calculated exactly as `100 × hourly_request_count / total_valid_requests`. User-Agent share is `100 × unique_user_agent_count / total_valid_requests`; missing-agent common-format records remain valid requests but do not create an agent value.

If adding a previously unseen User-Agent would exceed the configured ceiling, processing stops and exits `4`. The tool does not silently switch to approximate cardinality.

## Supported Input Contract

- UTF-8-compatible nginx common or combined access-log lines; decoding uses replacement only for display tokens and never crashes on a bad byte.
- Input is one positional path, `-`, or omitted; omitted and `-` both mean stdin.
- Regular files are opened read-only in binary mode and iterated line by line.
- Request parsing extracts the request target from `"METHOD target HTTP/version"`; an unparseable request field makes the line malformed.
- Status must be a three-digit integer. Timestamp must match nginx's bracketed `%d/%b/%Y:%H:%M:%S %z` form.
- Blank and malformed lines increment `malformed_lines` and processing continues. If the stream contains no valid request, exit `3` and emit no report.
- Files are never modified. FIFOs/stdin are supported; seeking and total-size discovery are not required.

## CLI Interface

### Commands

Installed console command: `nginx-stream-analyzer [OPTIONS] [INPUT]`. The equivalent module form is `python -m nginx_stream_analyzer [OPTIONS] [INPUT]`.

### Options

| Option | Default | Contract |
|---|---|---|
| `[INPUT]` | `-` | Log path or `-` for stdin |
| `--json` | false | Emit one JSON object; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized CSV rows; mutually exclusive with `--json` |
| `--top INTEGER` | `10` | Ranking length; integer from 1 to 1000 |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive exact-cardinality safety ceiling |
| `--color / --no-color` | auto | Force or suppress Rich color for terminal format only |
| `--version` | n/a | Print version and exit `0` |
| `--help` | n/a | Print usage and exit `0` |

### Inputs

Exactly one file stream is analyzed per invocation. A path is resolved relative to the current directory. The command never discovers, tails, rotates, or recursively reads files. "Streams" means incremental consumption of an input stream, not a perpetual `tail -f` service.

### Outputs

- Default text: Rich sections for summary counts, top IPs, error URLs, 24 hourly percentages, and unique User-Agent count/share. Color is auto-enabled only for a TTY.
- JSON: one UTF-8 object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_request_distribution`, and `user_agents`. Percentages are JSON numbers rounded to six decimal places for serialization.
- CSV: header `metric,rank,key,count,percentage,client_error_count,server_error_count`, followed by normalized rows in fixed section order. Non-applicable cells are empty.
- Report data goes only to stdout. Warnings and failure messages go only to stderr. Machine formats never include ANSI escape sequences.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful analysis and output |
| `1` | Input or I/O failure, including missing/unreadable file or broken read |
| `2` | CLI usage/configuration error, including conflicting formats or invalid ranges |
| `3` | Data error: processing completed but no valid requests were available |
| `4` | Unique-cardinality exhaustion: exact User-Agent ceiling exceeded |

Partial reports are not written for exits `1`, `2`, `3`, or `4`.

## Output Schema

The JSON `schema_version` begins at `1`. Required summary fields are `total_lines`, `total_valid_requests`, and `malformed_lines`. Each ranked item includes its key, exact count, and one-based rank. Hour objects include two-digit `hour`, `request_count`, and `percentage`. `user_agents` includes `unique_count`, `share_percentage`, `missing_count`, and `cardinality_limit`.

Schema field removal, renaming, changed meaning, or ordering changes in CSV require a documented breaking version. Additional JSON fields may be added only in a new schema version or with an explicit compatibility decision.

## Error Handling and Observability

Domain exceptions are caught once at the CLI boundary. Diagnostics contain the input label and actionable reason, but no traceback unless a future debug option is explicitly specified. A successful report includes malformed-line count; if nonzero, terminal mode prints a warning to stderr while JSON/CSV retain clean stdout and expose the count in data rows/object fields.

The implementation benchmark records elapsed wall time, Python version, CPU model, storage type, file size, valid-line count, and peak RSS outside normal output. No telemetry or network call is permitted.

## Performance and Resource Strategy

- Compile parsing expressions once; avoid `split()` work on fields that are not used.
- Read and parse sequentially; do not call `read()`, `readlines()`, or sort all raw rows.
- Maintain counters in-process; select top-N only after EOF.
- Benchmark first with a reproducible 1 GB fixture outside the repository and verify output against a smaller deterministic oracle.
- Profile before considering Variant B. The 30-second target is an acceptance target, not an unsupported guarantee for every laptop or storage device.
- The exact IP and URL counters also scale with unique values. The MVP documents this operational characteristic; the mandatory User-Agent ceiling addresses the explicitly defined exhaustion exit. A post-MVP bounded heavy-hitter algorithm would change exactness and requires a spec decision.

## Security and Privacy

Logs are untrusted input. The parser treats contents as data, performs no shell evaluation, does not follow values as paths, caps line length at a documented implementation limit, and uses bounded diagnostic excerpts. Output escaping is delegated to JSON/CSV libraries and Rich text is rendered with markup disabled for log-derived strings. Local data never leaves the process. File permissions are controlled by the OS user.

## Packaging and Deployment

Build a PEP 517 package from `pyproject.toml` using a `src/` layout and a console-script entry point. The release artifacts are a wheel and source distribution installable with `python -m pip install ...`. Supported runtime is CPython 3.11. No Docker image, daemon, systemd unit, database migration, environment variable, HTTP endpoint, auth flow, cloud target, or Kubernetes manifest exists.

## Architecture Decision Records

### ADR-001: One process and one pass

- **Status:** Accepted (pre-approved product architecture).
- **Decision:** Use Variant A.
- **Consequences:** simple stdin behavior and low overhead; parallel parsing is deferred until benchmark evidence demands it.

### ADR-002: Exact cardinality with fail-closed ceiling

- **Status:** Accepted.
- **Decision:** Keep exact User-Agent values up to a configured ceiling; exit `4` beyond it.
- **Consequences:** result meaning stays exact and memory failure becomes deterministic; approximation is out of scope.

### ADR-003: No persistence and no service boundary

- **Status:** Accepted.
- **Decision:** Use local streams and process output only.
- **Consequences:** $0 infrastructure and minimal privacy surface; no history, dashboards, remote querying, or multi-user access.

The in-session Devil's Advocate review is intentionally not performed or represented here; the benchmark harness owns that separate review artifact.
