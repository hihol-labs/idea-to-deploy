# Project Architecture: Nginx Log Lens

## 1. Context and constraints

The product is an installable Python 3.11 command-line program used locally by
DevOps/SRE engineers. It consumes a path or stdin, processes input once, and
writes exactly one selected output format to stdout. Diagnostics go to stderr.
The target is 1 GB in under 30 seconds on a laptop, with no paid or operated
infrastructure.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema and
lifecycle management without helping a one-shot report; all required metrics
can be accumulated while each line is visited once. An HTTP API would turn a
local executable into a long-running service with network, security,
deployment, and operational obligations. File/stdin input and stdout/stderr
output already provide the composition boundary engineers need.

## 2. Architecture variants

### Variant A: single-process streaming CLI (recommended and approved)

- **Approach:** Click invokes an iterator-based parser and one aggregation
  engine, then selects a Rich, JSON, or CSV renderer.
- **Pros:** smallest operational surface, one pass, natural stdin support,
  easiest path to a weekend release and $0 budget.
- **Cons:** one CPU process; exact high-cardinality sets can consume memory.
- **Best for:** local analysis of individual nginx log streams.
- **Estimated complexity:** Low.

### Variant B: two-pass local batch analyzer (rejected)

- **Approach:** parse into temporary normalized records, then run reports.
- **Pros:** simple report isolation and repeat analysis.
- **Cons:** extra disk I/O, temporary storage lifecycle, poor stdin semantics,
  and a direct conflict with stateless single-pass processing.
- **Best for:** repeated exploratory queries, which are outside MVP scope.
- **Estimated complexity:** Medium.

### Variant C: external ingestion/search stack (rejected)

- **Approach:** ship logs to Logstash/Elastic or a similar service and query it.
- **Pros:** long-term search, dashboards, distributed scale.
- **Cons:** database/server/cloud operations, nonzero resource cost, setup
  latency, and major scope expansion.
- **Best for:** fleet-wide retained analytics, not local incident triage.
- **Estimated complexity:** High.

### Recommendation

Variant A is approved because the product decisions make the architecture
unambiguous: a single process directly supports the latency, budget, delivery,
and pipeline constraints. Variants B and C are recorded to make their rejected
trade-offs explicit, not to reopen the decision.

## 3. Components and data flow

```text
file path or stdin
       |
       v
Click command -> text line iterator -> nginx parser -> ParsedRequest stream
                                                       |
                                                       v
                                           StreamingAggregator
                                  +------------+---------+----------+
                                  |            |         |          |
                                IP counts  error URLs  hours   UA set/counts
                                  +------------+---------+----------+
                                                       |
                                                       v
                                              ReportSnapshot
                                          /       |          \
                                  Rich text      JSON         CSV
                                      stdout; diagnostics -> stderr
```

| Component | Planned path | Responsibility |
|---|---|---|
| CLI adapter | `src/nginx_log_lens/cli.py` | Arguments, input/output selection, exit codes |
| Input adapter | `src/nginx_log_lens/input.py` | Lazy UTF-8 text iteration from file or stdin |
| Parser | `src/nginx_log_lens/parser.py` | Convert supported nginx lines to typed records |
| Models | `src/nginx_log_lens/models.py` | Frozen dataclasses for requests, counters, report metadata |
| Aggregator | `src/nginx_log_lens/aggregate.py` | Update all metrics in one pass and finalize top 10 |
| Renderers | `src/nginx_log_lens/renderers/` | Text, JSON, and normalized CSV serialization |
| Errors | `src/nginx_log_lens/errors.py` | Stable domain errors and exit-code mapping |

Dependencies point inward: adapters and renderers depend on models/domain
logic; parsing and aggregation do not import Click or Rich. Renderers receive a
final immutable snapshot and never reread the source.

## 4. Domain and parsing contracts

`ParsedRequest` contains `client_ip: str`, `timestamp: datetime`,
`request_target: str`, `status: int`, and `user_agent: str | None`.
`ReportSnapshot` contains totals, malformed-line count, ranked IP/error-URL
entries, 24 hourly buckets (00 through 23), unique User-Agent count, and
unique-User-Agent share.

Supported MVP input is nginx common and combined format. Each input byte stream
is decoded as UTF-8 with strict error handling; any decoding failure is fatal
for the input and maps to exit 3. After decoding, a line must match this
restricted grammar:

```text
IP SP "-" SP REMOTE_USER SP "[" TIMESTAMP "]" SP
"METHOD SP REQUEST_TARGET SP PROTOCOL" SP STATUS SP BYTES
[SP "REFERER" SP "USER_AGENT"] LF?
```

`IP`, `REMOTE_USER`, `METHOD`, `PROTOCOL`, `STATUS`, and `BYTES` are non-space
tokens; this accepts IPv4 and IPv6 strings without validating address
ownership. `TIMESTAMP` must parse as `%d/%b/%Y:%H:%M:%S %z`. Status is exactly
three decimal digits. `REQUEST_TARGET` is the content between the first and
last single-space separators in the quoted request and may itself contain
spaces; its decoded value is retained exactly. Quoted fields accept `\\` and
`\"` escapes; an unclosed quote, unsupported escape, missing field, invalid
timestamp/status, or trailing field makes only that line malformed. Common
format has no Referer/User-Agent, so User-Agent is missing. Blank lines are
malformed.

The URL key is the request target exactly as logged after quoted-field
unescaping, including query text; this avoids lossy normalization in the MVP.
Status codes 400–599 contribute to error URLs. The hourly bucket uses the hour
encoded in the log timestamp; timezone offsets are parsed but not converted.
Missing User-Agent (`"-"` or common format) does not enter the unique set. The share is:

`unique non-missing User-Agent values / successfully parsed requests × 100`.

If no request is successfully parsed, the share is `0.0`. Malformed lines are
skipped and counted. Fatal file/encoding/write failures return nonzero; skipped
lines alone do not make the run fail.

## 5. Streaming and performance design

- Never call `read()`, `readlines()`, or retain raw lines.
- Update IP and error-URL dictionaries, a fixed 24-element hour array, and the
  User-Agent set per parsed record.
- Derive top 10 at finalization with
  `sorted(items, key=lambda item: (-item.count, item.key))[:10]`; this is
  intentionally tie-safe. Replace it with a bounded heap only if profiling
  proves the sort material, and only with equivalence tests at the rank-10 tie
  boundary.
- Emit output once after the stream completes so JSON and CSV remain valid.
- Keep hot-loop logging disabled; summarize malformed input at completion.
- Benchmark wall time and peak resident memory on a reproducible generated
  1 GiB fixture in a clean Python 3.11 environment. The representative fixture
  uses combined format, a fixed seed, 4,096 distinct IPs, 50,000 distinct
  request targets, 25,000 distinct non-missing User-Agents, a uniform 24-hour
  distribution, 15% 4xx, 2% 5xx, 1% malformed lines, and enough repeated rows
  to reach exactly 1,073,741,824 bytes. The generator records its seed and
  SHA-256. These cardinalities are part of the performance claim; arbitrary
  adversarial cardinality is not covered by the 250 MiB gate.

The exact User-Agent set and count dictionaries are proportional to distinct
values/keys rather than file size. This is a conscious correctness trade-off.
If adversarial cardinality violates the memory target, an approximate
cardinality algorithm is a later opt-in feature and must never silently replace
the exact MVP metric.

## 6. CLI and output interface

Planned invocation:

```text
nginx-log-lens [OPTIONS] [LOG_FILE]
```

With no `LOG_FILE`, stdin is read. `--json` and `--csv` are mutually exclusive;
neither means Rich text. `--no-color` makes text deterministic when explicitly
requested. `--version` and `--help` follow Click conventions.

| Exit | Meaning |
|---:|---|
| 0 | Report produced, including runs with skipped malformed lines |
| 2 | Invalid CLI usage or conflicting format flags |
| 3 | Input open/read/decode failure |
| 4 | Output write/serialization failure other than a broken pipe |

`BrokenPipeError` is a normal downstream early-close condition (for example,
`... | head -n 1`): close stdout without a traceback or diagnostic and exit 0.

JSON is one object with `schema_version`, `summary`, `top_ips`,
`top_error_urls`, `hourly_requests`, and `unique_user_agents`. CSV uses one
header and normalized rows: `schema_version,report_type,rank,key,value,unit`.
Text may contain ANSI color only when color is enabled; JSON and CSV never do.

### Machine-readable schema version 1

| JSON path | Type | Rule |
|---|---|---|
| `schema_version` | integer | Exactly `1` |
| `summary.total_lines` | integer | All lines observed |
| `summary.parsed_lines` | integer | Successfully parsed lines |
| `summary.malformed_lines` | integer | Skipped malformed lines |
| `top_ips[]` | array of `{rank: integer, ip: string, requests: integer}` | Rank starts at 1; maximum 10 |
| `top_error_urls[]` | array of `{rank: integer, url: string, errors: integer}` | Status 400–599 only; maximum 10 |
| `hourly_requests` | object from two-digit `"00"`…`"23"` to integer | All 24 keys in ascending order |
| `unique_user_agents.count` | integer | Exact distinct non-missing values |
| `unique_user_agents.share_percent` | number | Six decimal places in serialized output |

CSV `report_type` is one of `summary`, `top_ip`, `top_error_url`, `hour`, or
`unique_user_agent`. `rank` is populated only for ranked rows. Summary keys are
`total_lines`, `parsed_lines`, and `malformed_lines`; hour keys are `00`–`23`;
User-Agent keys are `count` and `share_percent`. Units are respectively
`lines`, `requests`, `errors`, `requests`, `agents`, and `percent`. Rows appear
in that report-type order; keys/ranks are ordered as specified above. Empty
cells are empty CSV fields. Integers use base-10 digits; percent uses exactly
six fractional digits.

For an input containing one valid combined line at hour 13 with status 200 and
User-Agent `curl/8.0`, plus one malformed line, canonical JSON is:

```json
{"schema_version":1,"summary":{"total_lines":2,"parsed_lines":1,"malformed_lines":1},"top_ips":[{"rank":1,"ip":"192.0.2.1","requests":1}],"top_error_urls":[],"hourly_requests":{"00":0,"01":0,"02":0,"03":0,"04":0,"05":0,"06":0,"07":0,"08":0,"09":0,"10":0,"11":0,"12":0,"13":1,"14":0,"15":0,"16":0,"17":0,"18":0,"19":0,"20":0,"21":0,"22":0,"23":0},"unique_user_agents":{"count":1,"share_percent":100.000000}}
```

Canonical CSV is:

```csv
schema_version,report_type,rank,key,value,unit
1,summary,,total_lines,2,lines
1,summary,,parsed_lines,1,lines
1,summary,,malformed_lines,1,lines
1,top_ip,1,192.0.2.1,1,requests
1,hour,,00,0,requests
1,hour,,01,0,requests
1,hour,,02,0,requests
1,hour,,03,0,requests
1,hour,,04,0,requests
1,hour,,05,0,requests
1,hour,,06,0,requests
1,hour,,07,0,requests
1,hour,,08,0,requests
1,hour,,09,0,requests
1,hour,,10,0,requests
1,hour,,11,0,requests
1,hour,,12,0,requests
1,hour,,13,1,requests
1,hour,,14,0,requests
1,hour,,15,0,requests
1,hour,,16,0,requests
1,hour,,17,0,requests
1,hour,,18,0,requests
1,hour,,19,0,requests
1,hour,,20,0,requests
1,hour,,21,0,requests
1,hour,,22,0,requests
1,hour,,23,0,requests
1,unique_user_agent,,count,1,agents
1,unique_user_agent,,share_percent,100.000000,percent
```

There is no `top_error_url` row when its ranking is empty. All string fields
are escaped according to RFC 4180 by the standard `csv` module.

## 7. Database, HTTP API, and authentication

### Database schema

There are no database tables, fields, constraints, migrations, indexes,
connections, or persisted records. Runtime data lives only in process memory
and is discarded at exit. Adding even a local SQLite table would violate the
approved stateless contract without improving the required one-shot reports.

### HTTP API

There are no endpoints, request/response bodies, ports, listeners, or API
versioning. The public automation contract is the CLI plus JSON/CSV schemas.

### Authentication flow

Authentication is not applicable because the tool has no accounts, network
boundary, or service. Access is governed by the invoking OS user's permission
to read the log and execute the binary:

```text
OS user -> shell -> CLI -> OS opens selected file
                         | permission denied
                         +-> stderr + exit 3
```

The process does not elevate privileges, request secrets, or store credentials.

## 8. Configuration and environment

No environment variable is required. Locale-independent parsing and UTF-8
handling are explicit in code. CLI flags are the only user configuration in
the MVP, which keeps pipeline behavior visible and reproducible.

## 9. Packaging, deployment, and operations

The deployment target is the engineer's local laptop or compatible CI runner.
The project uses a `src/` layout, `pyproject.toml`, a console-script entry point,
and a wheel/sdist built with standard Python packaging. Installation is via
`pip` or `pipx`. Docker, `docker-compose`, servers, cloud resources, and
Kubernetes manifests are intentionally absent: none is needed to execute a
local Python package and each would expand the support surface.

Runtime observability consists of actionable stderr diagnostics and a final
malformed-line count. No telemetry leaves the machine.

## 10. Security and privacy

- Treat log content as untrusted data; never execute or interpolate it into a
  shell command.
- Escape terminal cells through Rich and keep log-derived content out of
  diagnostic control sequences.
- Open only the path explicitly supplied by the user and do not follow derived
  paths or write temporary copies.
- Never transmit, persist, or automatically redact log data; local processing
  minimizes exposure, and users control downstream output.
- Handle broken pipes quietly and avoid tracebacks for normal pipeline closure.
- Pin minimum supported dependency versions and audit the release dependency
  graph before publication.

## 11. Architecture Decision Record

### ADR-001: single-process stateless streaming CLI

- **Status:** Accepted (pre-approved).
- **Decision:** Use Variant A with Python 3.11, Click, Rich, dataclasses, and a
  single aggregation pass.
- **Consequences:** Minimal operations and fast delivery; throughput is bounded
  by one Python process, and exact cardinality consumes memory proportional to
  distinct values.
- **Rejected:** temporary batch materialization, databases, HTTP services, and
  external analytics stacks.

### Debate summary

The architecture was reviewed by the repository-local Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS

**Challenges and resolutions:**

1. Exact dictionaries/sets do not guarantee bounded memory for arbitrary
   cardinality. **Resolution:** the performance claim now defines fixture
   cardinalities, seed/hash recording, and its non-adversarial boundary;
   runtime time/RSS remains unverified until Implementation Plan Step 8.
2. JSON/CSV schemas were too loose for compatibility tests. **Resolution:**
   mandatory types, keys, ordering, precision, row types, and canonical output
   are specified in section 6.
3. Parser and decoding behavior were ambiguous. **Resolution:** a restricted
   common/combined grammar, strict UTF-8 policy, escape rules, and line-local
   versus fatal failures are explicit in section 4.
4. `heapq.nlargest` did not prove lexicographic tie ordering. **Resolution:**
   the MVP uses a full deterministic sort; optimization requires measurement
   and rank-boundary equivalence tests.
5. Broken-pipe handling conflicted with generic write failures. **Resolution:**
   quiet broken-pipe exit 0 is now distinct from exit 4.

**Alternatives considered and rejected:** two-pass temporary materialization
and an external analytics stack do not resolve these contract issues without
violating the stateless, local, $0 scope. No alternative architecture is
warranted.

## 12. Cross-document contract

[PRD.md](PRD.md) owns behavior and acceptance criteria;
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) sequences delivery;
[STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) owns priorities and success measures.
Behavior changes begin in those specifications before product code changes.
