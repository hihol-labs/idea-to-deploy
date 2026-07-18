# Project Architecture: Nginx Stream Analyzer

## 1. Context and Constraints

This is a single-process Python 3.11 command-line program for local nginx combined-format logs. The architecture decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, cleanup, disk amplification, and privacy exposure while the required result exists only for one invocation. An HTTP API would add a server, authentication and authorization concerns, ports, deployment, concurrency, and an operational lifecycle without improving local incident triage or Unix pipeline use. Input bytes enter through a file handle or stdin; formatted results leave through stdout; diagnostics leave through stderr.

Approved constraints:

- Python 3.11, Click, Rich, and dataclasses; installable through pip.
- One OS process and one streaming pass over input.
- Target: a representative 1 GB log in under 30 seconds on a laptop.
- $0 budget and one-weekend delivery.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.

## 2. Architecture Variants

### Variant A: Exact single-process stream aggregator (Recommended)

- **Approach:** parse each line, update exact counters/sets in memory, and render once at EOF.
- **Pros:** simplest behavior; exact output; one pass; straightforward tests; no intermediate files.
- **Cons:** memory grows with unique IPs, error URLs, and User-Agents.
- **Best for:** typical laptop-sized operational logs where exact answers are preferred.
- **Estimated complexity:** Low.

### Variant B: Exact external-sort pipeline

- **Approach:** emit normalized records to temporary files and use chunked sorting/merging.
- **Pros:** bounded memory for extreme cardinality; exact counts.
- **Cons:** substantial disk I/O, temporary-data privacy concerns, multi-stage processing, and likely difficulty meeting 30 seconds.
- **Best for:** much larger-than-memory logs where exactness is mandatory.
- **Estimated complexity:** High.

### Variant C: Approximate bounded-memory stream

- **Approach:** use heavy-hitter sketches for top lists and a cardinality estimator for User-Agents.
- **Pros:** predictable memory even with adversarial cardinality.
- **Cons:** approximate answers, extra dependencies or complex implementations, and a changed user contract.
- **Best for:** unbounded streams where estimates are explicitly acceptable.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the product decisions pre-approve the obvious single-process design, the MVP promises simple exact summaries, and one-weekend delivery rewards minimal moving parts. The implementation must measure peak memory on high-cardinality fixtures. Variant C is the documented escape hatch if measured laptop memory becomes unacceptable; adopting it requires a PRD decision about approximation.

## 3. System Context and Data Flow

```text
nginx log file ─┐
                ├─> Click command -> text stream -> parser -> aggregator -> report model
standard input ─┘                                              │              │
 malformed-line diagnostics ----------------------------------┘              ├─> Rich text -> stdout
                                                                               ├─> JSON -> stdout
                                                                               └─> CSV -> stdout
```

The hot path performs no network calls and no persistent writes. Input is consumed line by line; the renderer runs only after EOF. Broken-pipe handling permits downstream consumers such as `head` to close cleanly.

## 4. Module Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
├── __init__.py       # package metadata only
├── cli.py            # Click options, streams, exit codes
├── models.py         # frozen LogRecord and Report dataclasses
├── parser.py         # combined-log parsing and validation
├── aggregate.py      # one-pass mutable aggregation state
├── service.py        # orchestration from iterable[str] to Report
└── renderers/
    ├── __init__.py
    ├── terminal.py   # Rich output
    ├── json.py       # stable JSON document
    └── csv.py        # normalized CSV rows
tests/
├── fixtures/
├── test_parser.py
├── test_aggregate.py
├── test_renderers.py
├── test_cli.py
└── test_performance.py
```

Dependencies point inward: `cli` depends on `service` and renderers; `service` depends on parser, aggregator, and models; domain modules never import Click or Rich.

## 5. Domain Models

`LogRecord` is a dataclass with:

| Field | Python type | Meaning |
|---|---|---|
| `ip` | `str` | Client address exactly as parsed |
| `hour` | `int` | Validated hour (`0..23`) from the logged offset-local timestamp |
| `method` | `str` | Request method |
| `url` | `str` | Request target, including query string as logged |
| `protocol` | `str` | HTTP protocol token |
| `status` | `int` | HTTP response status |
| `user_agent` | `str` | User-Agent field; `-` remains a valid distinct token |

`Report` is an immutable boundary dataclass:

| Field | Python type | Contract |
|---|---|---|
| `total_requests` | `int` | Successfully parsed lines |
| `malformed_lines` | `int` | Skipped lines |
| `top_ips` | `tuple[RankedCount, ...]` | At most 10, descending count then lexicographic key |
| `top_error_urls` | `tuple[RankedCount, ...]` | At most 10 URLs whose status is 400–599 |
| `hourly_requests` | `tuple[HourCount, ...]` | All 24 local log hours, including zeros |
| `unique_user_agents` | `int` | Number of distinct User-Agent strings |
| `unique_user_agent_share` | `float` | `unique_user_agents / total_requests`, or `0.0` for empty input |

The “share of unique User-Agents” is therefore a ratio in `[0,1]`, rendered as a percentage only in terminal output. JSON retains the ratio as a number.

## 6. Parsing Contract

- Supported input is nginx combined log format with IPv4 or IPv6 client addresses.
- Input is opened as a buffered binary stream. A logical line is limited to 64 KiB including its terminator; use bounded `readline(65_537)`, classify an oversized line as malformed, and drain only to the next newline with bounded reads before continuing. The implementation must not call unbounded `read()` or materialize all lines.
- After removing the line terminator, each bounded line must decode as strict UTF-8; invalid byte sequences make that line malformed. This keeps terminal, JSON, CSV, and exact distinctness semantics deterministic.
- Quoted combined-format fields recognize nginx-style `\\` and `\"` escapes. Use a small linear scanner, or an anchored expression whose linear behavior is demonstrated by pathological-line tests; unknown/truncated escapes are malformed.
- Timestamp validation covers `[day/month/year:hour:minute:second ±offset]`, but the hot-path record stores only the validated logged hour because no report consumes a full `datetime`. Hourly grouping uses the hour written in each log entry.
- The request field is split into method, target, and protocol; malformed request triples are rejected.
- Status must be a three-digit integer. Error URL counting includes 400 through 599 inclusive.
- Malformed lines are skipped, counted, and summarized on stderr; individual bad lines are not echoed because logs may contain sensitive values.
- Empty input succeeds with an empty report. A missing/unreadable file is a usage/runtime error.

## 7. Aggregation and Complexity

For `n` valid records, `u_ip` distinct IPs, `u_err` distinct error URLs, and `u_ua` distinct User-Agents:

- Time is `O(n + u_ip log 10 + u_err log 10)`; final top-10 selection should use `heapq.nlargest` or equivalent rather than sorting every counter when it is measurably beneficial.
- Memory is `O(u_ip + u_err + u_ua + 24)` and independent of total line count for repeated keys.
- Tie-breaking is deterministic: count descending, key ascending. The bounded selection contract is `heapq.nsmallest(10, counts.items(), key=lambda item: (-item[1], item[0]))`; tests must include equal-count candidates spanning the tenth-place boundary.
- Counters use Python integers. Hour buckets are a fixed 24-element list.

The target is throughput, not streaming partial output: reports are emitted at EOF so rankings are final and JSON/CSV remain valid documents.

## 8. CLI Contract

Proposed executable: `nginx-stream-analyzer`.

```text
nginx-stream-analyzer [OPTIONS] [INPUT]

INPUT                 nginx access-log path; omit or use '-' for stdin
--json                emit one JSON document
--csv                 emit normalized CSV rows
--no-color            disable ANSI color in terminal mode
--version             show package version
--help                show usage
```

`--json` and `--csv` are mutually exclusive. Color is enabled only for the default renderer when stdout is a TTY and `NO_COLOR` is absent. Machine formats never contain ANSI escapes. Data goes to stdout; warnings and diagnostics go to stderr.

Exit codes:

| Code | Meaning |
|---:|---|
| 0 | Report produced, including empty input or input with some malformed lines |
| 1 | Input could not be read or an unexpected processing error occurred |
| 2 | Click usage error, including mutually exclusive format flags |

## 9. Output Schemas

### JSON

Top-level keys are stable and ordered for readability, though consumers must not rely on order:

```json
{
  "total_requests": 120,
  "malformed_lines": 2,
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 42}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 9}],
  "hourly_requests": [{"hour": 0, "count": 3}],
  "unique_user_agents": 18,
  "unique_user_agent_share": 0.15
}
```

All 24 hour objects appear. JSON serialization uses UTF-8 without ANSI decoration and rejects NaN/infinity.

### CSV

CSV uses one normalized table so a single stdout stream remains pipeline-friendly:

```text
report,rank,key,value
summary,,total_requests,120
summary,,malformed_lines,2
summary,,unique_user_agents,18
summary,,unique_user_agent_share,0.15
top_ips,1,192.0.2.1,42
top_error_urls,1,/missing,9
hourly_requests,,00,3
```

The standard library `csv` module performs quoting and newline handling. All 24 hourly rows appear.

## 10. Database, API, Authentication, and Deployment Decisions

### Database schema

There are **zero database tables**. Aggregation state consists only of process-local counters, a set, and 24 hour buckets, discarded on exit. Inventing the generic template’s requested tables would violate the approved stateless requirement.

### HTTP API

There are **zero HTTP endpoints**. The CLI arguments and stdout schemas in Sections 8–9 are the complete external interface. Inventing the generic template’s requested endpoints would violate the approved CLI-only requirement.

### Authentication

There is no authentication flow because there is no remote or multi-user boundary. Access control is the operating system’s permission check when opening the input file and writing pipeline destinations. The tool must not elevate privileges, read credentials, or transmit log data.

### Deployment and installation

The deployment target is a local CPython 3.11 environment on Linux/macOS (WSL supported) installed with pip or `pipx`. Packaging exposes a console-script entry point. Docker, Compose, cloud resources, and Kubernetes are intentionally absent: container startup and volume plumbing add no value to an installable local CLI.

### Environment variables

No project-specific environment variables are required. Standard `NO_COLOR` disables terminal color. Locale must not change JSON/CSV numeric formatting.

## 11. Performance Validation

The release benchmark must:

1. Generate a deterministic fixture outside version control from a versioned generator specification. Record seed, exact byte count, valid/malformed ratio, error ratio, timestamp distribution, IP/URL/User-Agent cardinalities and average/max key lengths, plus an expected report oracle.
2. Run the installed console command with stdout redirected to a file or null device.
3. Record wall-clock time, Python version, CPU, OS, storage type, and peak resident memory.
4. Repeat three times after one warm-up; use the median wall-clock time.
5. Pass only when the median is below 30 seconds, peak RSS is at most 512 MiB, and all output counts match the precomputed oracle.
6. Run a second high-cardinality 1 GB memory profile in which IPs, error URLs, and User-Agents approach worst-reasonable uniqueness. It must meet the same 512 MiB RSS gate; runtime is recorded but the 30-second gate applies to the representative profile.

The representative profile uses a fixed pseudorandom seed, exactly 1,073,741,824 bytes, 0.1% malformed lines, 8% error responses split across 4xx/5xx, all 24 hours uniformly represented, 10,000 IPs, 50,000 URLs, and 2,000 User-Agents. Exact distributions and key-length bounds live beside `scripts/generate_benchmark_log.py` and are versioned with the oracle.

If either RSS profile exceeds 512 MiB, the exact MVP does not pass its release gate. The command does not poll RSS continuously; an actual `MemoryError` is converted to a concise stderr diagnostic and exit code 1. The next design decision is an explicit exact spill-to-disk mode with permission-restricted temporary files and guaranteed cleanup, or a PRD-approved approximate mode—never a silent semantic change.

Profiling order: parser/regex cost, datetime creation, allocation volume, counter updates, and only then micro-optimizations. Correctness may not be weakened silently to meet the target.

## 12. Security and Privacy

- Log content is untrusted data, never code or format strings.
- No shell invocation is required for parsing or rendering.
- Diagnostics do not reproduce malformed lines or full User-Agent values.
- JSON and CSV use library encoders; terminal rendering treats values as text and disables Rich markup for log-derived fields.
- Terminal rendering applies a presentation-only sanitizer that visibly escapes C0/C1 controls, DEL, ESC, carriage return/newline, and Unicode bidi-formatting controls. JSON preserves the decoded logical string; CSV applies only its separately documented spreadsheet-safety transformation.
- CSV cells beginning with `=`, `+`, `-`, or `@` should be prefixed with a single quote to reduce spreadsheet formula injection risk; document this transformation.
- No input content leaves the machine and no persistent cache is created.

## 13. Architecture Decision Record (ADR)

### ADR-001: Exact one-pass in-memory aggregation

- **Status:** Accepted with measured release conditions.
- **Decision:** Use Variant A with exact counters and a distinct User-Agent set.
- **Drivers:** one-process constraint, exact reports, 1 GB target, one-weekend schedule, $0 budget.
- **Consequences:** minimal I/O and implementation surface; memory scales with distinct keys.
- **Guardrail:** representative and high-cardinality profiles must stay at or below 512 MiB peak RSS; change to spill/approximation only through an explicit architecture/PRD revision.

### ADR-002: CLI and schemas are the only public interfaces

- **Status:** Accepted.
- **Decision:** Keep Click options and versioned JSON/CSV shapes stable; do not create a network interface.
- **Consequences:** easy local use and pipeline integration, with no remote access or persistent history.

### Debate Summary

The architecture was reviewed by the Blueprint Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS

**Challenges raised:**

1. Exact aggregation lacked a measurable memory boundary → **Resolution:** set a 512 MiB peak-RSS release gate for representative and high-cardinality 1 GB profiles; specified failure and redesign behavior.
2. Line-by-line text input did not bound hostile single lines or define encoding/escaping → **Resolution:** specified buffered binary reads, a 64 KiB line limit, strict UTF-8, bounded draining, and quoted-field escape rules.
3. The performance workload was under-specified → **Resolution:** fixed generator metadata and representative characteristics, added an oracle and a separate high-cardinality profile, and removed unnecessary per-record `datetime` construction.
4. Rich-markup disabling did not prevent terminal control injection → **Resolution:** required presentation-only escaping of terminal and bidi control characters.
5. Heap tie behavior could violate lexicographic ordering → **Resolution:** specified the exact `nsmallest` composite order and a tenth-place boundary test.

**Alternatives considered and rejected:**

- Always spill to temporary files — rejected for MVP because disk I/O, sensitive temporary artifacts, and cleanup complexity conflict with the performance and weekend constraints; reconsider only if the RSS gate fails.
- Approximate heavy-hitter/cardinality structures — rejected because the approved MVP promises exact metrics; approximation requires an explicit PRD revision.
- Full `datetime` creation per line — rejected because only the logged hour reaches the report and timestamp validation can avoid unnecessary hot-path allocation.

## 14. Traceability

- Product scope and risks: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md)
- User-visible requirements: [PRD.md](PRD.md)
- Delivery sequence and verification: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Implementation-session prompts: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md)
