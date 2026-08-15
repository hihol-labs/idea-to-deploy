# Project Architecture: Nginx Stream Analyzer

## 1. Context and Drivers

The product is a local Python 3.11 CLI for DevOps/SRE engineers. It reads one nginx access-log stream and produces four summaries in colored terminal text, JSON, or CSV. Its main drivers are deterministic correctness, bounded processing behavior, pipe safety, pip installation, $0 operating cost, one-weekend delivery, and a measured 1 GB-under-30-seconds target.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the required result is computed in one pass, no history or cross-run queries are required, storage would add setup and privacy burden, and it would violate the zero-operations goal. An HTTP API is incorrect because the intended users operate locally and compose shell pipelines; a server would add lifecycle, port, authentication, and exposure concerns without improving the required analysis.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended and approved)

- **Approach:** one Python process connects an input iterator, parser, aggregator, immutable result snapshot, and one selected renderer.
- **Pros:** minimal operational surface, natural backpressure, simple tests, pip installability, no serialization between components.
- **Cons:** exact IP and User-Agent cardinalities can consume memory; CPU work is single-process.
- **Best for:** one-shot analysis of a 1 GB local log within a one-weekend MVP.
- **Estimated complexity:** Low.

### Variant B: External Unix pipeline

- **Approach:** document a composition of `awk`, `sort`, `uniq`, and related tools.
- **Pros:** no Python package and familiar primitives.
- **Cons:** brittle quoted-field parsing, locale/platform variation, repeated passes, unbounded sorts, and no unified exit/output contract.
- **Best for:** disposable investigation of a known fixed format.
- **Estimated complexity:** Low initially, medium to maintain.

### Variant C: Multiprocess chunk analyzer

- **Approach:** partition regular files, parse chunks in worker processes, and merge partial aggregates.
- **Pros:** possible CPU parallelism on large regular files.
- **Cons:** cannot naturally partition stdin; quoted lines and byte boundaries complicate correctness; merge/cardinality overhead threatens weekend scope.
- **Best for:** a later release only if profiling proves parsing is CPU-bound and Variant A misses the target.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process design, inputs must include stdin, and correctness plus delivery speed outweigh speculative parallelism. Variant C remains a measured-performance contingency, not MVP scope.

## 3. Component Model

```text
file path / stdin
       |
       v
 InputSource (text lines, strict decoding policy)
       |
       v
 NginxLineParser ---- malformed diagnostics/count
       |
       v ValidRequest(ip, timestamp, target, status, user_agent)
       |
       v
 StreamingAggregator
   |-- Counter[ip]
   |-- Counter[error_url] only for 400..599
   |-- 24 fixed hourly buckets
   `-- Set[user_agent] with cardinality ceiling
       |
       v
 AnalysisResult + RunDiagnostics
       |
       +--> Rich terminal renderer
       +--> JSON renderer
       `--> CSV long-form renderer
```

The command selects exactly one renderer. Results go to stdout. Warnings and failure diagnostics go to stderr. No component opens a network socket or persists application state.

## 4. Package and File Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py                 # Click command, option validation, exit mapping
  models.py              # dataclasses: ValidRequest, AnalysisResult, diagnostics
  parser.py              # compiled nginx grammar and timestamp parsing
  aggregate.py           # counters, hourly buckets, UA cardinality ceiling
  service.py             # one-pass orchestration and result finalization
  errors.py              # typed domain errors mapped to exit codes
  renderers/
    __init__.py
    terminal.py           # Rich tables and percentages
    json_output.py        # stable JSON object
    csv_output.py         # stable long-form CSV rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_output_contracts.py
  test_performance.py
```

Dependencies point inward: renderers and the CLI consume domain results; parser and aggregator never import Click or Rich. Dataclasses are used at boundaries, while hot-loop implementation choices must be justified by benchmark evidence.

## CLI Interface

### Command

```text
nginx-stream-analyzer [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. If omitted or exactly `-`, input is read from stdin. The process reads sequentially and never seeks, so pipes and regular files have the same semantics.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, off | Emit one UTF-8 JSON object; mutually exclusive with `--csv`; never colorize |
| `--csv` | flag, off | Emit UTF-8 RFC 4180 long-form CSV with header; mutually exclusive with `--json`; never colorize |
| `--log-format` | `combined` (default) or `common` | Select the supported nginx grammar; unsupported values are usage errors |
| `--max-unique-user-agents` | positive integer, default `1_000_000` | Stop before inserting a value beyond this exact-cardinality ceiling |
| `--color/--no-color` | auto on TTY | Controls only terminal output; invalid with JSON/CSV when explicitly forced on |
| `--version` | flag | Print version and exit 0 without reading input |
| `--help` | flag | Print usage and exit 0 without reading input |

The MVP top-N value is fixed at 10. A later `--top` option is P1 and must not silently change the v1 schema.

### Inputs

- UTF-8 text, one nginx access record per physical line, using the selected common or combined format.
- The parser extracts remote address, timestamp with numeric UTC offset, request target, status, and (combined format) User-Agent.
- The URL key is the request-target exactly as logged (path plus query, if present); method and protocol are excluded. A request field of `-` yields URL `-` and is otherwise valid if the remaining fields parse.
- Status must be a three-digit integer from 100 through 599. Error URL aggregation includes 400 through 599.
- For common-format input, User-Agent is unavailable; its unique count and share are `0`, with `user_agent_observations: 0` in structured output.
- Blank or malformed lines are skipped and counted. If zero valid requests remain, processing fails with exit code 3 and no result payload.
- File decoding or read failures are input failures, not malformed-line skips.

### Outputs

All modes represent the same finalized result:

- `top_ips`: at most 10 entries ordered by count descending, then IP string ascending.
- `top_error_urls`: at most 10 entries for 4xx/5xx requests, ordered by count descending, then URL ascending.
- `hourly_distribution`: all 24 local hours `00` through `23` from each record's logged numeric offset, with request counts and percentages.
- `unique_user_agents`: exact distinct non-missing User-Agent count, observation count, and percentage share.
- `diagnostics`: total lines, valid requests, malformed lines, and selected format.

Hourly request distribution is a percentage using `100 × hourly_request_count / total_valid_requests`. If total valid requests is zero, no distribution is emitted and exit code 3 applies. Percentages are serialized as numbers rounded to two decimal places using round-half-even; consumers should tolerate the displayed 24 buckets summing to 99.99 or 100.01 due to independent rounding.

Unique User-Agent share uses `100 × unique_user_agent_count / total_valid_requests`. Only non-missing combined-format User-Agent strings enter the exact set; the denominator remains all valid requests. Empty quoted User-Agent values are values, while `-` means missing. This metric describes distinct-agent strings per valid request, not a claim about unique people or browsers.

Terminal output uses four labeled Rich tables plus a diagnostic footer. JSON uses a versioned top-level object with keys `schema_version`, `top_ips`, `top_error_urls`, `hourly_distribution`, `unique_user_agents`, and `diagnostics`. CSV uses columns `schema_version,metric,rank,bucket,key,count,percentage`; absent fields are empty, and the diagnostics metrics appear as additional rows. Structured output contains no ANSI escapes.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Analysis completed successfully, including runs with some skipped malformed lines |
| `1` | Unexpected internal error |
| `2` | CLI usage/configuration error or input open/read/decode failure |
| `3` | No valid request records were found |
| `4` | Unique-cardinality exhaustion: adding another distinct User-Agent would exceed `--max-unique-user-agents` |

On exit codes 1–4, stderr contains a concise diagnostic and stdout contains no partial terminal, JSON, or CSV result.

## 6. Parsing and Aggregation Rules

The parser compiles the selected grammar once. It recognizes nginx quoting and escaped characters without splitting naively on spaces. Timestamp parsing uses the logged numeric offset; the hourly bucket is the hour as represented in that timestamp, with no machine-timezone conversion. Each valid record updates:

1. total valid requests;
2. the exact IP counter;
3. one of 24 hour counters;
4. the error-URL counter only for status 400–599; and
5. the exact User-Agent set when present.

Top 10 extraction occurs once at finalization using a bounded selection from counters. The pipeline is one pass over input. Hour storage is constant. IP, error-URL, and exact User-Agent storage is O(distinct values); only User-Agent has an explicit ceiling because exit code 4 is part of the approved product contract. The benchmark must record peak memory and may motivate future ceilings for other keys, but the MVP must not silently evict or approximate counts.

## 7. Data, API, Authentication, and State Decisions

### Database

There are no database tables, schemas, indexes, migrations, or retained records. Runtime counters and sets are process memory and are discarded at exit. Introducing a database would change the product and requires a new architecture decision.

### HTTP API

There are no endpoints, request bodies, response bodies, ports, or server process. JSON and CSV stdout are the automation interfaces. Introducing an API would change the product and requires a new architecture decision.

### Authentication

There is no authentication or authorization flow because the tool has no remote boundary or multi-user service. Access control is inherited from the local OS permissions of the invoking process and input file.

### Environment variables

No application environment variables are required. Locale must not affect JSON/CSV ordering or numeric formatting. Standard terminal capability variables may be interpreted by Rich but are not product configuration; explicit CLI options win.

## 8. Error Handling and Safety

- Treat log contents as untrusted data: never evaluate fields, interpolate them into shell commands, or allow terminal escape sequences through Rich markup.
- Open explicit paths read-only and stream them. Never rewrite, delete, or rotate input.
- Catch expected open/read/decode and parse conditions at their narrow boundary.
- Enforce the User-Agent ceiling before mutating the set, then raise the typed exhaustion error mapped to code 4.
- Convert only known domain/Click exceptions to codes 2–4; an outermost handler maps unexpected errors to 1 without a traceback by default.
- Sanitize terminal rendering and rely on JSON/CSV library escaping.
- Keep stdout transactional by aggregating before rendering; failures cannot leave a plausible partial report.

## 9. Packaging and Deployment

Deployment means building a wheel/sdist and installing it locally through pip into a Python 3.11 environment. `pyproject.toml` declares a console script named `nginx-stream-analyzer`, runtime dependencies with compatible version ranges, and optional development dependencies. Release verification installs the built wheel into a clean virtual environment and runs `--help`, `--version`, and a fixture analysis.

There is no Dockerfile, Docker Compose file, hosted environment, staging service, cloud resource, or Kubernetes manifest. Those artifacts would add no value to a local pip CLI and are excluded.

## 10. Test and Performance Strategy

- Parser unit tests cover common/combined formats, quoted requests, IPv4/IPv6, offsets, missing fields, escaped quotes, blank lines, invalid statuses, and decoding failures.
- Aggregation tests cover filtering, deterministic ties, all 24 buckets, percentage rounding, missing/empty User-Agents, and ceiling boundary behavior.
- CLI tests cover file/stdin equivalence, three renderers, stdout/stderr separation, mutual exclusions, and every exit code 0/1/2/3/4.
- Golden contract tests decode JSON and CSV semantically rather than snapshotting cosmetic terminal layout.
- The performance harness generates a deterministic 1 GB fixture outside version control, warms neither result cache nor database, captures elapsed monotonic time and peak RSS, and records OS, CPU, storage, and Python version.

The release performance command and its hardware profile are specified in `IMPLEMENTATION_PLAN.md`; the target is accepted only by actual measurement.

## 11. Architecture Decision Record (ADR)

### ADR-001: Select a single-process streaming CLI

- **Status:** Accepted (pre-approved product decision).
- **Decision:** Variant A, with in-memory exact aggregation and explicit User-Agent cardinality exhaustion.
- **Consequences:** minimal operations and deterministic results; memory scales with distinct keys; performance must be measured early.
- **Rejected:** Unix-only pipeline due to parsing/portability risk; multiprocessing until profiling justifies its complexity; persistence and HTTP service because they contradict scope.

### Adversarial Review Status

No Devil's Advocate or independent reviewer ran in this session, and no adversarial-review artifact is produced here. Per the benchmark protocol, the external harness performs that review in a separate fresh session. This section records process status only and is not a review verdict.

