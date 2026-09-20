# Project Architecture: nginx-insights

## 1. Context and Goals

The system is an installable Python 3.11 command-line program for local nginx access-log analysis. It processes a text stream once, retains only aggregation state, and emits one report. The primary quality goal is correct, deterministic results for a 1 GB log in under 30 seconds on the baseline laptop described in `STRATEGIC_PLAN.md`.

## 2. Architectural Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct here. A database would add writes, schema lifecycle, cleanup, privacy exposure, and operational cost while the product needs no cross-run history. In-memory counters and sets are sufficient for a single report and disappear on exit. An HTTP API would add a server, authentication and network attack surface, deployment, concurrency semantics, and an availability obligation while users explicitly need a local command that composes with files and Unix pipes.

The approved design is a single-process layered CLI. Database, HTTP, authentication, Docker, cloud, and Kubernetes variants are not offered because they violate the product boundary rather than presenting useful trade-offs.

Alternatives considered:

- A shell pipeline is smaller but cannot provide a reliable cross-platform parser and stable three-format contract.
- A Go binary could offer more throughput, but violates the required Python stack and is unnecessary until measurement disproves the target.
- Multiprocessing adds ordering, merge, and I/O overhead. The parser is single-pass and single-process first; optimize only from profiling evidence.

## 3. Component Model

```text
Click command
  -> input opener (file or stdin; UTF-8 policy)
    -> line iterator
      -> nginx parser -> AccessRecord dataclass | ParseError
        -> streaming Aggregator
          -> Report dataclass
            -> terminal | JSON | CSV renderer
              -> stdout

errors/diagnostics ---------------------------------> stderr + exit code
```

| Component | Planned path | Responsibility |
|---|---|---|
| CLI adapter | `src/nginx_insights/cli.py` | Parse options, select streams/renderer, map typed failures to exit codes |
| Input adapter | `src/nginx_insights/input.py` | Open a file or stdin as a line iterator without reading it in full |
| Parser | `src/nginx_insights/parser.py` | Parse supported nginx common/combined lines into `AccessRecord` |
| Domain models | `src/nginx_insights/models.py` | Frozen/slot dataclasses for records and immutable report snapshots |
| Aggregator | `src/nginx_insights/aggregate.py` | Update exact counters/sets and enforce cardinality limits |
| Renderers | `src/nginx_insights/renderers/{terminal,json,csv}.py` | Serialize the same report model without metric drift |
| Errors | `src/nginx_insights/errors.py` | Typed input, parse-quality, and cardinality failures |

Dependencies point inward: CLI and renderers depend on models; parsing and aggregation do not depend on Click or Rich. Rich is imported only by the terminal renderer.

## 4. Data Contracts

### AccessRecord

| Field | Python type | Contract |
|---|---|---|
| `client_ip` | `str` | Non-empty first nginx field; IPv4/IPv6 text retained as logged |
| `timestamp` | aware `datetime` | Parsed from nginx `%d/%b/%Y:%H:%M:%S %z` |
| `method` | `str | None` | Request method, or `None` for `"-"` request field |
| `target` | `str | None` | Raw request target, or `None` when unavailable |
| `path` | `str | None` | URL-split path; query and fragment excluded; empty path normalized to `/` |
| `protocol` | `str | None` | Request protocol when present |
| `status` | `int` | HTTP status in 100–599 |
| `user_agent` | `str | None` | Combined-log UA; `None` for absent or `"-"` |

### Report

| Field | Type | Contract |
|---|---|---|
| `total_lines` | `int` | Every physical input line |
| `valid_requests` | `int` | Successfully parsed records |
| `invalid_lines` | `int` | Lines skipped as malformed |
| `top_ips` | list of `(label, count)` | At most 10, count descending then label ascending |
| `top_error_paths` | list of `(label, count)` | At most 10 paths for status 400–599, same tie-break |
| `hourly_counts` | 24 integers | Index 0–23 is the hour encoded in each record's timestamp offset |
| `hourly_percentages` | 24 decimals | Each value uses `100 × hourly_request_count / total_valid_requests` |
| `unique_user_agents` | `int` | Distinct non-null User-Agent values |
| `user_agent_observations` | `int` | Valid requests with a non-null User-Agent |
| `unique_user_agent_share_pct` | decimal | `100 × unique_user_agents / user_agent_observations`, or `0` when the denominator is zero |

Percentages are rounded only at rendering time: two decimal places in terminal/CSV and JSON numbers derived from the same two-decimal quantization. The 24 hourly percentages sum to approximately 100%, subject only to display rounding. Hours use the offset embedded in each log entry; no timezone conversion occurs.

### Streaming State and Complexity

The aggregator stores 24 hourly counters, exact dictionaries for IP and error-path counts, and an exact set of User-Agent values. Time is O(n) expected for n valid records. Memory is O(i + p + u), where i, p, and u are distinct IPs, error paths, and User-Agents. This is stateless across runs but not magically constant-memory.

`--max-unique` sets a per-dimension cardinality ceiling (default `1_000_000`) for IPs, error paths, and User-Agents. Crossing any ceiling aborts without a normal report and returns code 4. Exactness is preferred to silent eviction or approximation.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT]
```

`INPUT` is one nginx access-log path. When omitted or `-`, bytes are read from standard input. Input is decoded as UTF-8 with invalid byte sequences treated as malformed lines. The MVP accepts uncompressed text; gzip support is P1 and users can pipe `gzip -cd` meanwhile.

### Options

| Option | Meaning |
|---|---|
| `--json` | Emit one JSON object to stdout |
| `--csv` | Emit long-form CSV to stdout |
| `--max-unique INTEGER` | Positive per-dimension exact-cardinality ceiling; default `1000000` |
| `--fail-on-malformed` | Return code 3 and suppress the normal report if any malformed line occurs |
| `--no-color` | Disable Rich color in terminal mode |
| `--version` | Print version and exit 0 |
| `--help` | Print usage and exit 0 |

`--json` and `--csv` are mutually exclusive. Terminal format is the default. Color is enabled only when terminal output is interactive and not disabled; JSON and CSV never contain ANSI escapes. Data goes to stdout and diagnostics go to stderr.

### Output contracts

Terminal output contains a summary, ranked IP table, ranked error-path table, 24-hour distribution table, and User-Agent summary. Empty valid input is a parse-quality failure rather than a misleading all-zero success.

JSON uses this stable top-level shape:

```json
{
  "summary": {"total_lines": 0, "valid_requests": 0, "invalid_lines": 0},
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 10}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 4}],
  "hourly_distribution": [{"hour": 0, "count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "observed_requests": 0, "share_percentage": 0.0}
}
```

The example shows shape, not internally consistent sample values. Actual output always contains 24 hourly rows. Keys and ranks are deterministic.

CSV has the header `section,rank,label,count,percentage`. Rows use sections `summary`, `top_ip`, `top_error_url`, `hour`, and `user_agent`; unused cells are empty. Labels for hourly rows are zero-padded `00` through `23`. CSV is RFC 4180-compatible and written through Python's `csv` module.

### Exit-code contract

| Code | Meaning |
|---:|---|
| 0 | Report emitted successfully, including success with some skipped malformed lines unless strict mode is set |
| 1 | Unexpected internal failure |
| 2 | CLI usage or input I/O error (invalid options, missing/unreadable input) |
| 3 | Parse-quality failure (no valid requests, or any malformed line with `--fail-on-malformed`) |
| 4 | Unique-cardinality exhaustion: an exact cardinality ceiling was crossed |

No normal terminal/JSON/CSV report is emitted for codes 2, 3, or 4. Code 1 may have partial bytes only if an output stream itself fails; diagnostics never move to stdout.

## 6. Parsing Rules

The parser supports standard nginx common and combined access-log field order with quoted request, referrer, and User-Agent handling. It compiles parsing machinery once, consumes one line at a time, and never evaluates input. Escaped quotes/backslashes in quoted fields, IPv6, `-` byte counts, and request field `-` have fixtures. Malformed timestamps, status codes, quoting, or required fields increment `invalid_lines`.

Top error URLs include only parsed statuses 400–599 and records with a usable request path. Query strings and fragments are removed to avoid splitting the same route into unbounded parameter variants. Top IPs count every valid request.

## 7. Security and Privacy

- Local files and stdin are the only data sources; there is no network access or telemetry.
- Log text is untrusted data. It is never executed, used as a format string, or interpolated into shell commands.
- Rich/CSV/JSON output relies on library escaping; terminal labels are sanitized to prevent control-sequence injection.
- Symlink behavior follows the OS open call; the tool does not change input files.
- No raw logs or derived state are persisted. Users control redirection and resulting output files.
- Dependency versions and licenses are checked before release; no secrets or authentication exist.

## 8. Packaging and Runtime

`pyproject.toml` declares Python `>=3.11,<4`, Click and Rich runtime dependencies, a `src/` layout, and the `nginx-insights` console entry point. A wheel and source distribution are built with standard PEP 517 tooling. No environment variables are required. Locale does not alter machine formats or tie-breaking.

There is no Docker Compose design and no deployment service. The deployment target is a user-controlled Python 3.11 environment installed by pip on Linux/macOS; Windows support is best effort for file/stdin processing. Release means publishing/installing a wheel, not starting infrastructure.

## 9. Performance Design

- Iterate buffered text lines; never call `read()` for the whole file.
- Compile regex/parsing helpers once and update mutable counters in place.
- Avoid constructing Rich objects before aggregation completes.
- Benchmark parser/aggregator separately from output formatting.
- Generate a deterministic 1 GB fixture outside version control and record wall time plus peak RSS.
- Preserve exact results under the default cardinality cap; performance changes must pass golden-output comparisons.

## 10. Test Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | Common/combined, IPv4/IPv6, time offsets, escaped content, malformed cases |
| Aggregator unit tests | Rankings, deterministic ties, error filter, 24 buckets, exact formulas, cap boundary |
| Renderer contract tests | ANSI policy, JSON schema/values, RFC-compatible CSV rows |
| CLI integration tests | stdin/file parity, option conflicts, stderr separation, all exit codes `0/1/2/3/4` |
| Property tests (optional) | Counts and percentages preserve invariants over generated records |
| Performance oracle | 1 GB completes under 30 s on the documented baseline, with peak RSS recorded |
| Packaging smoke test | Build wheel, install in clean Python 3.11 venv, run `--help` and a fixture |

## 11. Architecture Decisions

1. Single process and one-pass aggregation are accepted because the required workload is sequential local input and avoids merge overhead.
2. Exact maps/sets plus an explicit cap are accepted because silent approximation would violate the reporting contract.
3. A shared report dataclass is accepted so terminal, JSON, and CSV cannot independently calculate metrics.
4. Paths exclude query strings because operational route ranking should not explode on request parameters.
5. Input timestamps retain their encoded offsets because a single log can contain explicit local offsets and the product has no configured reporting timezone.

The external benchmark owns any later adversarial-review artifact; none is embedded in this blueprint.
