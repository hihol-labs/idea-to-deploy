# Project Architecture: nginx-stream-insights

## Context and Constraints

The product is a local Python 3.11 command-line program. The controlling decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because reports are derived in one pass, persistence adds setup and privacy risk, and the approved use case does not require history. An HTTP API is incorrect because the consumer is a local engineer or shell pipeline; a server would add lifecycle, networking, authentication, and deployment concerns without product value.

The program must process a representative 1 GB log in under 30 seconds on a documented laptop. It reads incrementally, never loads the whole input, and retains only aggregate counters. Exact aggregation is bounded by a configurable unique-cardinality ceiling; reaching it exits safely rather than returning an incomplete result as exact.

## Architectural Decision

A single-process, layered CLI is pre-approved and recommended:

`Click command → text stream → parser → streaming aggregator → report model → Rich/JSON/CSV renderer`

The single process minimizes serialization and operational overhead. Layers remain separately testable, but they are Python modules, not services. Threads/process pools are deferred until measurement proves they are needed; ordered streaming and Python IPC can otherwise cost more than parsing.

### Alternatives considered

| Alternative | Why rejected for MVP |
|---|---|
| Multiple processes | Adds chunk-boundary handling, merge logic, and IPC before profiling shows a need |
| Persistent SQLite cache | Violates statelessness and adds lifecycle/staleness semantics |
| HTTP service | Violates the local CLI contract and creates auth/deployment obligations |
| Go rewrite | Could improve throughput but violates the approved stack and weekend scope |

This is an owner-approved architecture decision, not an adversarial-review verdict. No independent or Devil's Advocate review is recorded in this document.

## Module Structure

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  cli.py          # Click command, validation, exit mapping
  models.py       # ParsedRequest, Report, ranked item dataclasses
  parser.py       # Supported nginx line parsing
  aggregator.py   # single-pass counters and cardinality guard
  renderers/
    text.py       # Rich output
    json.py       # JSON schema
    csv.py        # long-form CSV schema
tests/
  fixtures/
  unit/
  integration/
  performance/
```

Dependencies point inward: renderers and the CLI consume report dataclasses; parsing and aggregation do not import Click or Rich.

## Data Model and Streaming Algorithm

`ParsedRequest` contains `client_ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `status: int`, and `user_agent: str | None`. `Report` contains `total_lines`, `total_valid_requests`, `invalid_lines`, ranked IP/error-URL entries, 24 hourly buckets, `unique_user_agents`, and `unique_user_agent_share_percent`.

For every line:

1. Parse a supported common/combined-style record; increment `invalid_lines` if invalid.
2. For a valid record, increment total requests, its UTC-offset-preserving log-hour bucket, and the IP counter.
3. If status is 400–599, increment the normalized request-path counter.
4. Add a non-empty User-Agent to the exact set, enforcing the cardinality ceiling before growth.
5. At EOF, rank by count descending and key ascending for deterministic ties, keeping ten.

Hourly request distribution is a percentage for each of 24 hour buckets using `100 × hourly_request_count / total_valid_requests`. When there are no valid requests, every hourly percentage and the unique User-Agent share are `0.0`. Unique User-Agent share is `100 × unique_user_agents / total_valid_requests`; it can exceed neither 100% nor the number of valid requests because each request contributes at most one User-Agent.

Exact IP, error-URL, and User-Agent structures grow with unique cardinality, not file size. The default ceiling is documented and exposed by `--max-unique`; crossing it terminates with exit code 4 before a misleading report is emitted.

## CLI Interface

### Command

```text
nginx-stream-insights [OPTIONS] [INPUT]
```

`INPUT` is a path to an uncompressed nginx access log. Omit it or use `-` to read UTF-8 text from stdin. The command never mutates the input. One invocation produces one complete report.

### Options

| Option | Meaning | Default |
|---|---|---|
| `--json` | Emit one JSON document | off |
| `--csv` | Emit long-form CSV rows | off |
| `--format [combined|common]` | Select supported nginx format | `combined` |
| `--encoding TEXT` | Input text encoding | `utf-8` |
| `--errors [strict|skip]` | Fail on first malformed line or count and skip it | `skip` |
| `--max-unique INTEGER` | Maximum distinct key count per exact-cardinality structure | `1000000` |
| `--color/--no-color` | Force or suppress color for text | auto by TTY |
| `--version` | Print version and exit | — |
| `--help` | Print help and exit | — |

`--json` and `--csv` are mutually exclusive. Machine formats never contain ANSI color.

### Outputs

Default text writes a Rich report to stdout with four sections and an input-quality footer. Diagnostics go to stderr.

JSON uses stable top-level keys: `schema_version`, `total_lines`, `total_valid_requests`, `invalid_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Ranked entries use `value`, `count`, and `share_percent`; hourly entries use `hour`, `request_count`, and `share_percent`.

CSV is UTF-8 with header `schema_version,metric,rank,key,count,share_percent`. `metric` is one of `top_ip`, `top_error_url`, `hour`, `unique_user_agents`, `total_valid_requests`, or `invalid_lines`. Non-applicable cells are empty.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Report completed; skipped invalid lines may be reported when `--errors skip` |
| 1 | Input I/O failure, including missing/unreadable file or decoding error |
| 2 | CLI usage or option validation error |
| 3 | Parse failure in `--errors strict` mode |
| 4 | Unique-cardinality exhaustion; no exact report is emitted |

## Error and Safety Model

The parser never evaluates input and treats log contents as untrusted data. URLs and User-Agents are escaped by Rich and serialized by standard JSON/CSV writers. Broken pipes terminate quietly with the conventional successful pipeline behavior where supported. File, decode, usage, strict-parse, and cardinality failures map only to the documented exit codes. Tracebacks are suppressed for expected user errors and retained only behind a future debug option.

## Performance Budget

| Area | Budget/decision |
|---|---|
| Input | Buffered iteration; no `read()` of the whole file |
| Parse | Precompiled parser and minimal timestamp work |
| Aggregation | O(n) expected time; memory O(unique IPs + unique error URLs + unique UAs + 24) |
| Ranking | `heapq.nsmallest`/equivalent O(u log 10), deterministic tie ordering |
| Rendering | Only after EOF; at most 10 ranked rows plus 24 hourly rows |
| Benchmark | Generated representative 1 GB fixture outside Git; wall time and peak RSS recorded |

The 30-second target is accepted only from a repeatable benchmark on a named CPU, Python 3.11 patch version, storage type, input format, and command.

## Packaging and Runtime

`pyproject.toml` declares Python `>=3.11,<3.12` for the MVP, Click and Rich runtime dependencies, and the `nginx-stream-insights` console script. Installation is `python3.11 -m pip install .` or `pipx install .`. There are no environment variables, containers, daemons, ports, migrations, external services, authentication flows, secrets, or deployment target. Distribution is a source/wheel artifact installed locally through pip.

## Observability and Testing Boundaries

The report includes total, valid, and invalid line counts. Tests cover parser boundaries, timezone/hour behavior, tie sorting, 4xx/5xx filtering, missing User-Agents, output schemas, all exit codes, pipes, and cardinality exhaustion. Performance tests are opt-in because the 1 GB fixture is large; a smaller scaling test runs in the normal suite.

## Architecture Decision Record

### ADR-001: Local single-process streaming CLI

- **Status:** Accepted by the supplied product brief.
- **Decision:** Use the layered single-process design above with no persistence or network interface.
- **Consequences:** Fast setup and private local processing; exact high-cardinality data can consume memory, so a hard guard and exit code 4 are part of the public contract.
- **Revisit when:** Measurement shows the target cannot be met, or a separately approved product scope requires persistent historical analysis.

