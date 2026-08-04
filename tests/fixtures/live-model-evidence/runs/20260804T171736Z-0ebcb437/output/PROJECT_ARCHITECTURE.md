# Project Architecture: Nginx Stream Analyzer

## Context and Goals

The product is an installable Python 3.11 command-line application for local nginx access-log analysis. Its architecture optimizes for a one-weekend build, deterministic pipeline behavior, bounded streaming memory, and a measured target of processing 1 GB in under 30 seconds on a documented reference laptop.

The controlling decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the report needs only one-pass counters and would add writes, schema lifecycle, disk amplification, and retained sensitive logs. An HTTP API is incorrect because there is no remote client or shared service: it would introduce a server, authentication, ports, deployment, and an attack surface while making local pipe usage worse.

## Architecture Decision

The approved design is a single operating-system process with four internal layers:

```text
file/stdin bytes -> line decoder/parser -> streaming aggregator -> selected renderer -> stdout
                              |                    |
                         malformed count      cardinality guard
errors and diagnostics ------------------------------------------------------> stderr
```

The CLI opens one binary input stream, frames one physical line at a time with a byte limit, decodes and parses it, updates counters, and renders only after EOF. It never stores raw log lines. Every exact high-cardinality structure—IP keys, error-URL keys, and User-Agent keys—has a configured maximum; crossing any limit stops safely with exit code 4 rather than swapping or silently estimating.

### Alternatives Considered

| Variant | Advantages | Rejection reason |
|---|---|---|
| Single-process streaming (selected) | Lowest coordination cost, deterministic output, simplest profiling | Meets the approved scope and laptop target |
| Multiprocess file sharding | Potential CPU parallelism | Harder byte-boundary handling, counter merges, nondeterminism, and overhead before profiling proves a need |
| Batch/DataFrame loading | Concise aggregation code | Violates bounded-memory streaming and performs unnecessary materialization |
| Persistent SQLite cache | Repeat queries can be faster | Adds state and I/O for a single-report tool; conflicts with the explicit no-database decision |

## Components and File Boundaries

| Planned path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, Python 3.11 constraint, `nginx-stream-analyzer` entry point |
| `src/nginx_stream_analyzer/cli.py` | Click command, option validation, stream ownership, exit mapping |
| `src/nginx_stream_analyzer/models.py` | `AccessRecord`, `Report`, ranked-entry dataclasses |
| `src/nginx_stream_analyzer/parser.py` | Supported nginx combined-log parsing and timestamp/status validation |
| `src/nginx_stream_analyzer/aggregate.py` | Counters, 24 hourly buckets, exact User-Agent set and guard |
| `src/nginx_stream_analyzer/render/text.py` | Rich tables and percentage formatting |
| `src/nginx_stream_analyzer/render/json.py` | Stable JSON document serialization |
| `src/nginx_stream_analyzer/render/csv.py` | Stable long-form CSV serialization |
| `src/nginx_stream_analyzer/errors.py` | Typed domain failures and exit-code mapping |
| `tests/` | Parser fixtures, aggregation assertions, CLI/golden output, performance harness |

Dependency direction is `cli -> parser + aggregate + renderers`; renderers depend only on report models. Parser and aggregator never import Click or Rich.

## Data Model and Algorithms

`AccessRecord` is a frozen, slotted dataclass containing client IP, UTC-offset-aware timestamp, request target, integer status, and User-Agent. A tuple-like representation may replace it only if profiling demonstrates a material allocation bottleneck without weakening the public model. `Report` contains total lines, valid requests, malformed lines, ranked IP counts, ranked error-URL counts, 24 hourly percentages, unique User-Agent count, and unique User-Agent share percentage.

- IP and error-URL counts use `collections.Counter`; ties sort by descending count then ascending key for repeatability.
- A request contributes to error URLs when `400 <= status <= 599`.
- Hour is taken from the parsed nginx timestamp as written, preserving its explicit offset. Each hour percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`. With zero valid requests, all 24 percentages are `0.0`.
- Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`, or `0.0` when there are no valid requests.
- IP, error-URL, and User-Agent keys are stored exactly until their respective `--max-distinct-ips`, `--max-distinct-error-urls`, and `--max-unique-user-agents` limits; inserting a new key beyond any limit raises unique-cardinality exhaustion.
- Top lists are truncated to 10 after deterministic sorting.

Memory is `O(max_distinct_ips + max_distinct_error_urls + max_unique_user_agents + max_line_bytes)`, independent of file size. All four limits are mandatory and have conservative defaults. The 1 GB benchmark reports peak RSS and must remain below the documented ceiling.

## CLI Interface

### Command

```text
nginx-stream-analyzer [OPTIONS] INPUT
```

`INPUT` is a path to a UTF-8-compatible nginx access log. The planned Should-level extension accepts `-` for standard input. The supported MVP grammar is nginx combined log format; malformed or undecodable lines are skipped, counted, and reported.

### Options

| Option | Meaning | Default/constraint |
|---|---|---|
| `--json` | Emit one JSON report to stdout | Mutually exclusive with `--csv` |
| `--csv` | Emit long-form CSV rows to stdout | Mutually exclusive with `--json` |
| `--max-unique-user-agents INTEGER` | Exact-cardinality safety limit | `1_000_000`, integer >= 1 |
| `--max-distinct-ips INTEGER` | Exact IP-counter safety limit | `1_000_000`, integer >= 1 |
| `--max-distinct-error-urls INTEGER` | Exact error-URL-counter safety limit | `1_000_000`, integer >= 1 |
| `--max-line-bytes INTEGER` | Maximum physical log-line size | `65_536`, integer >= 256 |
| `--no-color` | Disable color in terminal mode | Color otherwise only when stdout is a TTY |
| `--version` | Print version and exit | No input required |
| `--help` | Print usage and exit | No input required |

### Inputs

- One regular file path in the MVP; `-`/stdin and gzip are Should priorities.
- A binary iterator frames on LF in fixed-size chunks, strips an optional CR, and handles a final non-LF-terminated line. Each frame is strictly decoded as UTF-8. An undecodable line counts once as malformed and processing resumes at the next byte-level line boundary.
- A line exceeding `--max-line-bytes` is drained in bounded chunks through the next LF and counts once as malformed, preventing one physical line from allocating unbounded memory.
- The normative grammar is nginx's conventional combined format: `remote_addr - remote_user [time_local] "METHOD request_target PROTOCOL" status body_bytes_sent "http_referer" "http_user_agent"`. IPv4/IPv6 are accepted as text; `-` is accepted for absent remote user/referer; quoted fields support nginx backslash escaping. A malformed request line invalidates the line. The full logged request target, including its query string, is the error-URL key.
- No network URL, directory traversal, glob expansion, or recursive input is performed by the tool.

### Outputs

- Default: four Rich sections plus totals; ANSI appears only on an interactive TTY unless disabled.
- JSON: one UTF-8 object with schema version, totals, ranked lists, 24 hourly entries expressed as percentages, and User-Agent count/share.
- CSV: UTF-8 long form with header `metric,rank,key,value,unit`; percentages use unit `percent`.
- Normal report data goes to stdout. Diagnostics go to stderr. JSON/CSV stdout is never mixed with progress text or ANSI codes.

### Exit Codes

| Code | Contract |
|---:|---|
| `0` | Successful report, including an empty file or a file containing only malformed lines |
| `1` | Unexpected internal/runtime or output-delivery failure, including broken pipe |
| `2` | CLI usage or option validation error |
| `3` | Input open/read/decode failure that prevents continued analysis |
| `4` | Unique-cardinality exhaustion: an exact IP, error-URL, or User-Agent key limit was exceeded |

The complete public exit-code contract is `0/1/2/3/4`; code `4` is never remapped to a generic failure.

## Output Schemas

JSON fields are `schema_version`, `input`, `total_lines`, `total_valid_requests`, `malformed_lines`, `top_ips[]`, `top_error_urls[]`, `hourly_request_distribution[]`, and `user_agents`. Ranked items contain `rank`, `key`, and `count`; hourly items contain `hour` (`00`–`23`) and `percentage`; `user_agents` contains `unique_count` and `share_percentage`.

CSV uses one row type so pipelines need one parser. Count rows use metrics `top_ip` and `top_error_url`; hour rows use `hourly_request_distribution`; the final User-Agent row uses `unique_user_agent_share`. Totals are emitted as separate `total_*` metrics.

## Database, API, Authentication, and Server

There are no database tables: all state lives in process-local counters and is discarded after output. There are no API endpoints or request/response bodies: the complete external surface is under `## CLI Interface`. There is no authentication flow because the application opens only a user-supplied local stream with the invoking user's permissions and does not establish a trust-bearing remote session. There is no HTTP server, background daemon, telemetry, or listener.

These are intentional architecture decisions, not missing implementation detail. Adding any of them requires a new PRD and architecture decision.

## Configuration and Environment

There are no required environment variables and no `.env` file. Behavior is controlled by explicit CLI options to keep runs replayable. Standard process environment affects only conventional terminal capabilities and locale; machine output is always UTF-8.

## Packaging and Deployment

Deployment is a pip-installed local console script, preferably inside a virtual environment or via `pipx`. The package supports CPython 3.11 and declares Click and Rich dependencies. No Docker image, Compose file, cloud target, Kubernetes manifest, or system service is part of the product: containerization would add no value to a local file-processing command and complicate host-file access.

## Performance and Reliability

- The versioned benchmark generator uses seed `20260804`, writes exactly `1_073_741_824` bytes, and records line count with 90% 2xx, 5% 4xx, 4% 5xx, 1% malformed lines plus declared IP/URL/User-Agent cardinalities. Its source hash is recorded with results.
- Run JSON mode to `/dev/null` three times on the documented laptop after one unmeasured warm-up; use the median wall time as the oracle and require it to be below 30.0 seconds. Record CPU, RAM, OS, filesystem, Python/dependency versions, command, cache policy, and `/usr/bin/time -v` peak RSS; set and enforce the accepted RSS ceiling before release.
- Keep the hot loop free of Rich, Click callbacks, per-line dataclass retention, and repeated timestamp formatter construction.
- Count every physical line exactly once as valid or malformed.
- Catch expected input and cardinality exceptions at the CLI boundary; preserve unexpected tracebacks in developer tests but return code 1 in normal execution.
- Serialize the small final JSON/CSV report completely before a single stdout write. Rich text is not atomic. A broken pipe is caught at the CLI boundary, emits no traceback, and returns code 1 so the closed `0/1/2/3/4` contract remains exhaustive.

## Security and Privacy

Logs can contain IP addresses, URLs, and User-Agents. The tool sends nothing over the network and retains nothing after process exit. It treats log contents as data, never shell syntax; renderers must neutralize terminal control characters in human output and serialize machine output through standard libraries. File permissions remain the operating system's responsibility.

## Architecture Decision Record (ADR)

### ADR-001: Stateless single-process CLI

- **Status:** Accepted and pre-approved.
- **Decision:** Use one Python process, a streaming parser, in-memory aggregate structures, and renderer adapters.
- **Consequences:** Low operational complexity and bounded-by-cardinality memory; exact high-cardinality dimensions need explicit guards and performance evidence.

### Debate Summary

The architecture was reviewed by the blueprint workflow's Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS — all conditions were incorporated into this document and the implementation guides.

**Challenges raised and resolutions:**

1. IP and error-URL counters were not bounded. **Resolution:** add hard limits for all exact aggregate dimensions and map any exhaustion to code 4.
2. Text decoding could not reliably recover from invalid UTF-8 or an oversized line. **Resolution:** specify binary LF framing, strict per-line decoding, bounded draining, and `--max-line-bytes`.
3. The 1 GB/30 s target was not reproducible. **Resolution:** specify seed, exact byte count, traffic mix, warm-up, three measured runs, median oracle, environment record, and peak RSS evidence.
4. Combined-log grammar and URL identity were underspecified. **Resolution:** define the normative fields/escaping and retain the full request target including query string.
5. Broken-pipe conventions conflicted with the closed exit set. **Resolution:** suppress traceback and return code 1; buffer each machine report for one write while acknowledging text is non-atomic.

No alternative architecture was warranted: the reviewer found the selected single-process streaming CLI appropriate to the scope. The review was document-only; implementation behavior and benchmark results remain unverified until the corresponding plan steps run.
