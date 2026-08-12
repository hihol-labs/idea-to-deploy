# Project Architecture: nginx-report

## 1. Context and Goals

`nginx-report` is a pip-installable Python 3.11 CLI that processes nginx access logs locally in a single pass. It targets DevOps/SRE shell workflows and must report top client IPs, top error URLs, hourly traffic percentages, and exact unique User-Agent share. The performance acceptance target is a representative 1 GB log in under 30 seconds on a documented laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because no queryable history or cross-run state is required; it would add writes, schema management, privacy exposure, and performance overhead. An HTTP API is incorrect because the intended trust boundary and composition surface are local files, stdin/stdout, and process exit codes; a server would add lifecycle, authentication, port, and deployment concerns with no MVP benefit.

## 2. Architecture Decision

The approved architecture is one local process with a layered internal design:

```text
file(s) / stdin
      |
      v
byte-line reader -> combined-log parser -> aggregate state -> report model
                                                        |-> Rich text renderer -> stderr/stdout terminal
                                                        |-> JSON renderer      -> stdout
                                                        `-> CSV renderer       -> stdout
```

One record is parsed and folded into aggregates before the next is read. Raw requests are never retained. There are no background workers, sockets, remote calls, persisted caches, or plugin execution.

### Why no architecture variants

The workflow normally compares variants when a meaningful unresolved choice exists. Here the user has explicitly approved the obvious single-process architecture and forbidden databases, APIs, servers, cloud, and Kubernetes. The rejected alternatives are recorded in the ADR rather than presented as fake choices.

## CLI Interface

### Command

```text
nginx-report [OPTIONS] [INPUTS]...
```

With no `INPUTS`, the command reads stdin. Each input is a path to a regular log file; `-` means stdin and may appear at most once. Multiple finite inputs are processed as one logical stream in argument order. Version 1 accepts uncompressed nginx combined-log records encoded as UTF-8-compatible bytes; parsed quoted fields are decoded with replacement only for display/serialization, never for structural parsing.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit the versioned JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit the versioned long-form CSV table; mutually exclusive with `--json` |
| `--color/--no-color` | auto | Force or disable ANSI color for text output; auto enables color only on a TTY |
| `--max-unique-user-agents INTEGER` | `1_000_000` | Positive ceiling for exact unique User-Agent values; exceeding it stops with code 4 |
| `--strict` | flag, false | Stop at the first malformed record; without it, skip malformed records and finish with code 3 |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print Click help and exit 0 |

Top-N is fixed at 10 in v1. `--json` and `--csv` never emit ANSI sequences. Diagnostics go to stderr; the report goes to stdout, including when malformed records cause exit 3.

### Inputs

- nginx combined-log lines, one request per line.
- Finite regular files and/or stdin.
- Empty input is valid and produces zero counts, 24 zero-percent hours, and a 0% unique User-Agent share.
- A line is valid only when all required combined-format fields parse, the status is a three-digit integer, and the timestamp contains a valid nginx offset.
- `-` may not be combined with another `-`; invalid paths, directories, and read failures are I/O errors.

### Outputs

The canonical report model is:

- `schema_version`: `1`
- `total_lines`, `total_valid_requests`, `invalid_lines`
- `top_ips`: up to 10 `{ip, count, percentage}` rows, sorted by count descending then IP bytewise ascending
- `top_error_urls`: up to 10 `{url, count, percentage}` rows for statuses 400–599, sorted by count descending then URL bytewise ascending; percentage denominator is total valid requests
- `hourly_distribution`: exactly 24 `{hour, count, percentage}` rows for `00` through `23`
- `unique_user_agents`: `{count, percentage}`

Hourly request distribution is a percentage using `100 × hourly_request_count / total_valid_requests`. The timestamp's recorded UTC offset is preserved for bucketing; no timezone conversion is performed. If `total_valid_requests` is zero, every hourly percentage is `0.0`.

Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`, or `0.0` for zero valid requests. The raw User-Agent string, including `-`, is an exact identity. Percentages are serialized as numbers rounded to two decimal places using round-half-up; terminal output appends `%`.

JSON is one UTF-8 object followed by a newline using the canonical field names above. CSV is UTF-8 RFC 4180 long form with the fixed header:

```text
metric,rank,key,count,percentage
```

Rows appear in this order: `top_ip`, `top_error_url`, 24 `hourly_request` rows, then `unique_user_agents`. Summary counts are represented as `summary` rows before ranked metrics. Empty optional ranks are omitted.

### Exit codes

| Code | Meaning | Output behavior |
|---:|---|---|
| `0` | Successful analysis; no malformed records | Complete report on stdout |
| `1` | Input/output failure, including unreadable input or broken non-pipeline output | Diagnostic on stderr; report is not guaranteed |
| `2` | CLI usage or configuration error | Click diagnostic/help on stderr/stdout as appropriate |
| `3` | One or more malformed log records | Default mode skips them and emits the complete valid-record report; strict mode stops at the first malformed line |
| `4` | Unique-cardinality exhaustion | Exact unique User-Agent ceiling was exceeded; diagnostic on stderr and no misleading complete report |

Precedence after successful CLI parsing is `1` over `4` over `3` over `0`; code `2` occurs before processing. A downstream pipe closed normally may be treated as successful quiet termination only when no report contract is partially claimed; all other write failures are code 1.

## 4. Internal Components and Files

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python requirement, dependencies, console script, tooling |
| `src/nginx_report/cli.py` | Click command, option validation, stream lifecycle, exit mapping |
| `src/nginx_report/parser.py` | Allocation-conscious combined-log parser |
| `src/nginx_report/models.py` | Parsed request and canonical report dataclasses |
| `src/nginx_report/aggregate.py` | Single-pass counters, exact User-Agent set, final sorting |
| `src/nginx_report/render_text.py` | Rich terminal report |
| `src/nginx_report/render_json.py` | Versioned JSON serialization |
| `src/nginx_report/render_csv.py` | RFC 4180 long-form CSV serialization |
| `src/nginx_report/errors.py` | Typed domain failures and exit-code enum |
| `tests/` | Unit, integration, golden-output, CLI, and performance tests |

Dependencies point inward: `cli` coordinates parser, aggregator, and one renderer; renderers consume only the canonical report dataclasses. Parsing and aggregation do not import Click or Rich.

## 5. Data Model and Streaming State

There are no database tables. In-memory dataclasses and aggregates are the complete model:

| Type | Fields | Invariants |
|---|---|---|
| `ParsedRequest` | `ip: bytes`, `timestamp: datetime`, `url: bytes`, `status: int`, `user_agent: bytes` | Created only from a valid complete line |
| `Report` | schema version, line counts, ranked rows, 24 hourly rows, UA summary | Immutable after finalization |
| `RankedMetric` | `key: str`, `count: int`, `percentage: Decimal` | Non-negative; stable tie ordering |
| `HourlyMetric` | `hour: int`, `count: int`, `percentage: Decimal` | Hour 0–23; exactly 24 final rows |
| `UniqueAgentMetric` | `count: int`, `percentage: Decimal` | Exact or processing fails with code 4 |

Mutable processing state contains total counters, a 24-element integer array, `Counter[bytes]` for IPs, `Counter[bytes]` for error URLs, and `set[bytes]` for User-Agents. The set is checked before accepting a new distinct value; crossing the configured ceiling raises a typed exhaustion error. This makes memory usage data-dependent but bounded by an explicit operator contract rather than by approximation.

## 6. Parsing and Aggregation Rules

- Read binary streams line by line; never call `read()` without a bounded size and never collect all lines.
- Parse the nginx combined layout, including quoted request, referrer, and User-Agent fields. Extract the URL target from the request field; a syntactically missing request target makes the line invalid.
- Count IPs for every valid request.
- Count error URLs only for HTTP status 400–599.
- Bucket the request by the hour written in its nginx timestamp.
- Insert each exact User-Agent value into the bounded set.
- Increment `total_valid_requests` only after all fields needed by every metric have validated.
- Do not include malformed lines partially in any aggregate.
- Final top lists use bounded `heapq.nsmallest`/equivalent selection or a measured faster deterministic alternative; do not sort all keys without profiling the trade-off.

## 7. Error Handling and Observability

Diagnostics identify input and one-based line number but do not reproduce the full log line. In default mode, malformed-line diagnostics are summarized to avoid flooding stderr; the final invalid count remains exact. `--strict` emits the first location and stops. No telemetry, log upload, or network access is permitted.

Internal exceptions are translated once at the CLI boundary. Expected input, usage, parse, cardinality, and pipe conditions never produce a traceback. Unexpected exceptions may show a concise failure message by default and a traceback only under a developer-only test/debug mechanism that is not part of the stable CLI.

## 8. Security and Privacy Boundaries

- Treat paths and log content as untrusted data; never evaluate fields or expand shell syntax.
- Open only paths explicitly supplied by the user; reject directories and special-device surprises where practical.
- Do not persist raw values, create caches, or make network calls.
- Keep report data on stdout and diagnostics on stderr.
- Escape/control-sanitize Rich text so crafted URLs or User-Agents cannot inject terminal markup or control sequences.
- CSV serialization must quote formula-leading cells safely for spreadsheet consumers or document a raw-data mode; the chosen v1 contract prefixes dangerous `=`, `+`, `-`, and `@` text cells with a single quote.
- Dependency versions and release artifacts are checked by the verification workflow.

## 9. Performance Architecture

The hot path is binary line iteration, structural parsing, counter updates, and a bounded-set membership check. Performance work is evidence-driven:

1. Generate a deterministic representative corpus outside the installed package and record its content identity.
2. Benchmark cold and warm filesystem-cache scenarios separately on named hardware.
3. Measure elapsed wall time and peak RSS.
4. Profile before changing the parser or data structures.
5. Fail release acceptance if the exact candidate does not process 1 GB in under 30 seconds on the reference laptop.

The target is throughput, not concurrency. Threads, multiprocessing, memory mapping, and native extensions are deferred unless profiling proves the single-process Python design insufficient and the architecture document is revised first.

## 10. Packaging and Runtime

The package uses a `src/` layout and exposes `nginx-report = nginx_report.cli:main`. Runtime dependencies are Click and Rich; dataclasses are from Python 3.11. Installation is `python3.11 -m pip install .` or `pipx install .`. Locale does not affect ordering, numeric formatting, timestamps, or CSV delimiters.

There are no runtime environment variables, configuration files, Docker images, Compose files, services, deployment manifests, or open ports. The deployment target is the user's local Python 3.11 environment through pip/pipx. This absence is an architectural constraint, not missing documentation.

## 11. Testing Strategy

- Parser fixtures: valid combined records, escaping, IPv4/IPv6, offsets, malformed status/timestamp/request, very long lines, and non-ASCII bytes.
- Aggregation tests: all four metrics, 4xx/5xx bounds, ties, empty input, percentage rounding, atomic invalid-line handling, and exact cardinality limit boundaries.
- Renderer golden tests: ANSI/no-ANSI text, JSON schema/order-independent semantics, CSV row order and quoting.
- Click integration tests: files, stdin, multiple inputs, mutual exclusions, stderr separation, and the complete `0/1/2/3/4` exit-code contract.
- Property tests or fuzz cases: parser never crashes or partially mutates aggregates for arbitrary bytes.
- Performance test: representative 1 GB corpus, <30 seconds on reference hardware, peak RSS recorded.

## 12. Architecture Decision Record (ADR)

### ADR-001: Local single-process streaming CLI

**Status:** Accepted.

**Decision:** Use one Python process, one-pass parsing, in-memory aggregate state, exact bounded User-Agent cardinality, and stdout/stderr/exit codes as the only integration boundary.

**Alternatives considered and rejected:**

- Go implementation: likely faster, but violates the approved stack and increases delivery/toolchain scope before Python performance is measured.
- SQLite or another embedded database: adds persistence and write overhead without a historical-query requirement.
- Logstash/Elastic pipeline: contradicts the $0, local, stateless, one-weekend boundary.
- Multiprocessing map/reduce: complicates stdin, deterministic merging, and exact cardinality with no profiling evidence.
- Approximate cardinality: bounds memory more tightly but breaks the exact v1 metric contract.

### Self-Critique (not an independent/adversarial reviewer)

The benchmark provides no independent reviewer or subagent transport. The following is the architect's labeled self-critique using the required Devil's Advocate structure; it must not be represented as independent review.

**Strengths acknowledged:** The architecture matches the local privacy boundary, minimizes operational surface, and gives pipelines deterministic schemas and exit semantics.

**Verdict:** APPROVE WITH CONDITIONS — the conditions below are incorporated into this document and must be verified during implementation.

#### Challenge 1: Exact User-Agent state can dominate memory

**Weakness:** A set grows with distinct User-Agents even though raw request records are streamed.  
**Risk level:** High.  
**Alternative:** HyperLogLog would provide fixed memory.  
**Trade-off:** Fixed memory is gained, but the exact v1 metric is lost.  
**Question for architect:** What prevents an adversarial or highly diverse log from exhausting the laptop?  
**Resolution:** Retain exactness, impose `--max-unique-user-agents`, stop with code 4 before accepting an excess value, and test both sides of the boundary.

#### Challenge 2: The 30-second target may be optimistic in pure Python

**Weakness:** Quoted-field parsing and several hash structures can make a Python hot path CPU- and allocation-heavy.  
**Risk level:** High.  
**Alternative:** Go or a native parser could provide more throughput.  
**Trade-off:** Performance headroom is gained, but the approved stack, packaging simplicity, and one-weekend scope are lost.  
**Question for architect:** Is there an early gate that detects infeasibility before renderers consume the schedule?  
**Resolution:** Benchmark the parser foundation in Step 2, profile before optimization, run the complete 1 GB gate in Step 8, and invoke kill/reassessment criteria rather than quietly changing architecture.

#### Challenge 3: Combined-log parsing is easy to make subtly incorrect

**Weakness:** Escaping, malformed quoted fields, offsets, and unusual bytes can create partial or misclassified records.  
**Risk level:** Medium.  
**Alternative:** A general configurable grammar could represent more nginx formats.  
**Trade-off:** Format coverage improves, but ambiguity, implementation time, and test surface grow materially.  
**Question for architect:** How is partial aggregate mutation prevented when a late field fails?  
**Resolution:** Define a narrow v1 combined grammar, parse the complete record before aggregation, add adversarial fixtures, and signal malformed input with code 3.

#### Challenge 4: CSV can become an injection vector

**Weakness:** URLs or IP-like text beginning with spreadsheet formula characters can execute when CSV is opened interactively.  
**Risk level:** Medium.  
**Alternative:** Emit raw RFC 4180 values and make consumers responsible for safety.  
**Trade-off:** Raw fidelity is gained, but common spreadsheet users inherit a preventable risk.  
**Question for architect:** Is CSV intended only for machines, or must it be safe for routine spreadsheet inspection?  
**Resolution:** Treat spreadsheet inspection as expected, prefix dangerous text cells as documented, and golden-test quoting and safety behavior.

#### Challenge 5: A partially written report could confuse pipelines

**Weakness:** Streaming report bytes before aggregation is known complete could leave syntactically valid-looking partial output after an error.  
**Risk level:** Medium.  
**Alternative:** Buffer each entire serialized report before its first stdout write.  
**Trade-off:** Atomicity improves at a negligible memory cost because the report is small, while true output streaming is sacrificed.  
**Question for architect:** Does any renderer write before parsing and exact-cardinality checks finish?  
**Resolution:** Finalize the small canonical report before rendering, serialize JSON/CSV at report scale, and keep exhaustion from producing a complete-looking report.

## 13. Traceability

Product priorities and acceptance criteria are in `STRATEGIC_PLAN.md` and `PRD.md`. File-by-file delivery and verification commands are in `IMPLEMENTATION_PLAN.md`; implementation prompts must preserve this architecture through `CLAUDE_CODE_GUIDE.md`.
