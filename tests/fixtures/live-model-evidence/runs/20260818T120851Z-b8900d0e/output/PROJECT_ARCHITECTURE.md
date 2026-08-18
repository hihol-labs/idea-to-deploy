# Project Architecture: Nginx Insights CLI

## 1. Context and Constraints

The product is a local Python 3.11 CLI for DevOps/SRE engineers. It analyzes
nginx Combined Log Format from a regular file or standard input, emits four
summary families, and exits. It has a $0 budget, a one-weekend delivery window,
and a performance target of 1 GB in under 30 seconds on a documented laptop.

The binding architectural decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema
management, disk amplification, cleanup, and retained sensitive data without
helping a one-shot summary. An HTTP API would turn a local command into a
long-running network service with authentication, exposure, deployment, and
operations concerns. Files/stdin and stdout already form the appropriate
interfaces for local investigation and automation.

## 2. Architecture Decision and Alternatives

### Variant A: single-process streaming CLI (selected)

- **Approach:** one Python process iterates over input once, parses one record
  at a time, updates bounded counters plus an explicitly guarded exact
  User-Agent set, then renders one result object.
- **Pros:** lowest complexity, no intermediate storage, pipeline-native,
  compatible with the weekend and $0 constraints.
- **Cons:** exact User-Agent cardinality can grow with input diversity; a hard
  limit and exit code 4 are required.
- **Best for:** local one-shot analysis of logs up to the benchmarked size.
- **Estimated complexity:** Low.

### Variant B: multi-process chunked CLI (rejected for MVP)

- **Approach:** split seekable files into byte ranges, parse in workers, merge
  partial counters and sets.
- **Pros:** can use multiple CPU cores.
- **Cons:** complicates newline boundaries, stdin support, deterministic error
  handling, progress, memory peaks, and set merging.
- **Best for:** a later version only if measurement proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: indexed local analytics engine (rejected)

- **Approach:** import records into SQLite or an embedded analytics engine and query them.
- **Pros:** flexible ad hoc queries and repeat analysis.
- **Cons:** violates stateless processing, duplicates the input, adds storage
  lifecycle and dependency cost, and is slower to first result.
- **Best for:** retained exploratory analytics, which is outside scope.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process
architecture and it is the only option aligned with all explicit constraints.
No architectural choice remains open for this blueprint.

## 3. Component Model

```text
regular file or stdin
        |
        v
Input opener -> line iterator -> Combined Log parser -> Aggregator
                                                      |-- IP Counter
                                                      |-- error-URL Counter
                                                      |-- 24 hourly buckets
                                                      `-- guarded exact UA set
                                                               |
                                                               v
                                                        AnalysisResult
                                                   /          |          \
                                           Rich terminal     JSON        CSV
```

| Component | Proposed path | Responsibility |
|---|---|---|
| Click entry point | `src/nginx_insights/cli.py` | Validate options, select streams/renderer, map domain failures to exit codes |
| Input adapter | `src/nginx_insights/input.py` | Open a file or use stdin without loading all content |
| Domain records | `src/nginx_insights/models.py` | Frozen dataclasses for parsed records, counters snapshot, and result metadata |
| Parser | `src/nginx_insights/parser.py` | Compile the Combined Log parser once and yield normalized `AccessRecord` values |
| Aggregator | `src/nginx_insights/aggregate.py` | Maintain counters, hourly buckets, exact UA set, malformed count, and limit guard |
| Output contract | `src/nginx_insights/render/base.py` | Build a canonical serializable result and stable ordering |
| Renderers | `src/nginx_insights/render/{terminal,json_output,csv_output}.py` | Format the same result without recomputation |
| Errors | `src/nginx_insights/errors.py` | Typed domain exceptions carrying public exit semantics |

Dependency direction is `cli -> input/parser/aggregate -> models`, with renderers
depending only on the canonical result model. Core modules never import Click or Rich.

## 4. Streaming Data Model and Algorithms

`AccessRecord` contains client IP text, timestamp with its encoded numeric
offset, request target, status integer, and User-Agent text. A line is valid
only if all required Combined Log Format fields parse, status is 100–599, and
the timestamp is valid. The request target is the request-line target token;
query strings remain part of the target in MVP results.

For every valid record:

1. increment `total_valid_requests` and the client-IP counter;
2. if status is 400–599, increment the request-target error counter;
3. increment the bucket matching the hour in the timestamp as written in the log;
4. add the exact User-Agent string to the guarded set, failing before the set
   exceeds `max_unique_user_agents`.

Top lists sort by count descending and then key ascending for deterministic
ties, taking the first 10. All 24 hourly buckets are emitted, including zeros.
Hourly request distribution is a percentage computed with the literal formula
`100 × hourly_request_count / total_valid_requests`. The unique User-Agent share
is `100 × unique_user_agent_count / total_valid_requests`; it is `0.0` only when
no result is emitted because empty/no-valid input is an exit-code 3 condition.
Percentages are numeric values rounded to two decimal places at serialization.

Time complexity is O(n + k log k), where n is valid records and k is distinct
IPs plus distinct error URLs during final ranking. Memory is O(i + u + e), for
distinct IPs, exact User-Agents, and error URLs; it is not falsely described as
constant. `--max-unique-user-agents` gives the unbounded term an explicit guard.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT]
```

`INPUT` is a path to an uncompressed nginx access log. Omitted input or `-`
means standard input. The command performs one finite pass; live follow/tail
behavior is outside MVP scope.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit exactly one JSON document; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized CSV rows; mutually exclusive with `--json` |
| `--no-color` | false | Disable Rich color in terminal mode; structured formats never contain color |
| `--strict` | false | Exit 3 at the first malformed non-empty line; otherwise count and skip malformed lines |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive hard limit for exact distinct User-Agent values; exhaustion exits 4 |
| `--version` | n/a | Print package version and exit 0 |
| `--help` | n/a | Print usage and exit 0 |

### Inputs

- UTF-8-compatible nginx Combined Log Format, one record per line.
- Binary NULs, undecodable sequences, truncated records, and unsupported custom
  formats are malformed input.
- File input must be a readable regular file. Shell decompression may feed stdin.
- Non-strict mode skips malformed lines but returns a result only if at least
  one valid request exists.

### Outputs

- **Terminal (default):** four labeled Rich tables plus processed/invalid-line
  metadata. Color is enabled only for a capable TTY and can be disabled.
- **JSON:** keys `schema_version`, `source`, `total_valid_requests`,
  `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`,
  `unique_user_agents`, and `unique_user_agent_share_percent`. Top entries are
  objects with `value` and `count`; hours are `00` through `23`.
- **CSV:** header `section,key,count,percent`, followed by deterministic rows for
  `top_ip`, `top_error_url`, `hour`, and `unique_user_agents`. Empty cells are
  present where a measure does not apply.
- Diagnostics go to stderr. Successful data goes to stdout. JSON/CSV stdout is
  never mixed with progress or diagnostics.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success, including `--help`, `--version`, and a downstream broken pipe |
| `1` | Runtime or I/O failure: missing/unreadable file after validation, read failure, or output failure |
| `2` | Click usage/configuration error: invalid option, conflicting formats, invalid positive limit, or extra arguments |
| `3` | Input-format failure: strict-mode malformed line, empty input, or no valid requests |
| `4` | Unique-cardinality exhaustion: another distinct User-Agent would exceed the configured limit |

The complete contract is always `0/1/2/3/4`; renderers and guides must not
omit, remap, or overload code 4.

## 6. Persistence, Database, API, Authentication, and Deployment

### Database

No database exists, so there are no tables, fields, migrations, indexes, or
retention jobs. Aggregates live only in process memory and are discarded on exit.

### HTTP API

No HTTP API exists, so there are no endpoints, request bodies, response bodies,
ports, CORS rules, or OpenAPI description. The complete public interface is
the CLI contract above.

### Authentication

No authentication exists because there is no remote service or multi-user
boundary. Access control is the local operating system's file and process
permissions. The program makes no network requests and sends no telemetry.

### Environment variables and configuration

There are no product-specific environment variables or configuration files in
MVP. Locale must not affect parsing, sorting, JSON, or CSV. Standard terminal
capability variables may influence Rich color only; `--no-color` is authoritative.

### Packaging and deployment

Distribution is an sdist/wheel installed with pip, exposing the
`nginx-insights` console script. Deployment means installation into a Python
3.11 virtual environment on Linux or macOS. Docker, docker-compose, cloud,
server, and Kubernetes artifacts are intentionally absent because they add no
value to a local pip-installed CLI.

## 7. Reliability, Security, and Performance

- Stream lines and never call `read()` without a bounded size.
- Compile parsing machinery once, keep hot-loop logging disabled, and avoid
  retaining raw lines or full records.
- Check cardinality before insertion; report the configured limit on stderr
  without printing a log line or User-Agent value.
- Escape terminal content through Rich, serialize JSON with the standard
  encoder, and use `csv.writer` to prevent formula/quoting mistakes.
- Open only the user-selected input; do not traverse directories or follow an
  application-managed file list.
- Benchmark after installation with color disabled and stdout redirected, and
  measure both elapsed time and peak RSS.
- A SIGINT produces the conventional shell interruption behavior and no
  partial JSON/CSV document; temporary output files are not managed by MVP.

## 8. Test Architecture

| Layer | Evidence |
|---|---|
| Parser unit tests | valid combined records, escaping, IPv4/IPv6, malformed timestamps/status/request lines |
| Aggregation unit tests | all four formulas, 24 buckets, deterministic ties, 399/400/599/600 boundaries, exhaustion before insertion |
| Renderer golden tests | semantically identical terminal/no-color, JSON, and CSV result fixtures |
| CLI integration tests | stdin/file equivalence, stdout/stderr separation, mutually exclusive formats, complete exit codes `0/1/2/3/4` |
| Packaging smoke test | clean Python 3.11 environment installs and invokes console script |
| Performance test | generated representative 1 GB fixture completes under 30 seconds with recorded environment and peak RSS |

## 9. Architectural Decisions

| ID | Decision | Rationale | Revisit trigger |
|---|---|---|---|
| ADR-001 | Select single-process, one-pass processing | Smallest design meeting local CLI constraints | Reproducible benchmark misses target after two optimization passes |
| ADR-002 | Exact User-Agent set with a hard cap | Metric remains exact and exhaustion is explicit | Approved approximate-cardinality requirement in a later PRD |
| ADR-003 | Combined Log Format only | Keeps parsing contract testable within one weekend | Validated demand for named custom formats |
| ADR-004 | One canonical result feeds all renderers | Prevents output semantic drift | Never, unless schema versioning requires an adapter |
| ADR-005 | No database/API/auth/container | These solve problems the product explicitly does not have | Product changes from local one-shot CLI to retained or remote analysis |

No Devil's Advocate or independent adversarial review was performed or recorded
in this blueprint session, by explicit session constraint.

