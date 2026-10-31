# Project Architecture: nginx-log-report

## Architecture Decision

The selected architecture is a single Python process with a line iterator, parser, in-memory aggregators, and one selected renderer. The governing decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, and operational state to a task that only needs one-pass aggregation and a final report. An HTTP API would add a daemon, networking, authentication questions, deployment, and exposure of potentially sensitive logs while providing no value for local shell use. The CLI already composes with files, stdin, exit codes, JSON, and CSV.

The brief makes the single-process choice obvious, so no architecture-choice pause is needed. Multiprocessing is rejected for the MVP because splitting lines, merging exact counters, preserving deterministic errors, and measuring process overhead would consume the one-weekend budget before profiling proves it necessary. The main risk is Python throughput; the response is an early benchmark and profiler evidence, not speculative distribution.

## System Context

```text
nginx access log file ----\
                           > [Click CLI] -> [line stream] -> [parser]
stdin --------------------/                              -> [aggregators]
                                                               |
                                      +------------------------+------------------+
                                      |                        |                  |
                               [Rich renderer]          [JSON renderer]    [CSV renderer]
                                      |                        |                  |
                                   terminal                 stdout             stdout
```

Only the current line, counters, 24 hourly buckets, top-k candidates, and the exact set of observed User-Agent strings are held in memory. The User-Agent set has a configurable hard ceiling; crossing it stops processing with code `4` rather than risking host exhaustion or returning a silently approximate result.

## Components and Source Layout

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python requirement, dependencies, build system, `nginx-log-report` entry point |
| `src/nginx_log_report/cli.py` | Click command, option validation, stream lifecycle, exit mapping |
| `src/nginx_log_report/model.py` | `LogRecord`, `Report`, `RankedItem`, and error dataclasses |
| `src/nginx_log_report/parser.py` | Compiled combined-log parser and timestamp/status validation |
| `src/nginx_log_report/aggregate.py` | Single-pass counters, cardinality limit, deterministic top-10 selection |
| `src/nginx_log_report/render/terminal.py` | Rich tables and summary diagnostics |
| `src/nginx_log_report/render/json.py` | Versioned JSON document serialization |
| `src/nginx_log_report/render/csv.py` | Normalized CSV row serialization |
| `tests/fixtures/` | Small valid, malformed, mixed, and high-cardinality log fixtures |
| `tests/` | Unit, CLI, contract, and benchmark-oriented tests |

## Data Model and Processing Semantics

`LogRecord` contains `ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str`. Fields not required by the report may be parsed over but are not retained. A line is valid only when it matches the documented nginx combined-log structure and all required fields validate.

`StreamingAggregator` maintains:

- `total_valid_requests: int`;
- `malformed_lines: int`;
- `ip_counts: Counter[str]`;
- `error_url_counts: Counter[str]`, incremented only when `400 <= status <= 599`;
- `hour_counts: list[int]` with exactly 24 buckets based on the log entry's own numeric timezone timestamp;
- `unique_user_agents: set[str]`, including the literal `-` if nginx recorded no User-Agent.

Ranking is count descending, then key ascending for deterministic ties. At end of input, at most 10 rows are emitted for each ranking. Hourly request distribution is a percentage computed as `100 × hourly_request_count / total_valid_requests`; all 24 hours are present and sum to approximately 100% subject only to display rounding. The unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. Empty or all-invalid input does not divide by zero; it exits with code `3` and no report payload.

There are no database tables, migrations, indexes, cache services, or persisted application state. This deliberately overrides the generic web-project template because persistence would violate the approved product scope.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [PATH]
```

`PATH` is a single nginx access-log file. Omit it or pass `-` to read stdin. Input is UTF-8 text with replacement disabled: invalid byte sequences are input errors. `--follow` requires a regular file and waits for appended complete lines until interrupted; without it, input is finite.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | off | Emit normalized CSV; mutually exclusive with `--json` |
| `--follow` / `-f` | off | Follow appended lines from a regular file |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive hard limit for exact unique User-Agent values |
| `--color` / `--no-color` | auto | Override TTY-based color behavior for terminal output only |
| `--version` | — | Print package version and exit `0` |
| `--help` | — | Print usage and exit `0` |

### Outputs

Default terminal output contains four labeled Rich tables/sections plus counts of valid and malformed lines. Color is enabled only for a TTY unless explicitly overridden. Diagnostics go to stderr; the report goes to stdout.

JSON is a single UTF-8 object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents`. Ranked items contain `rank`, `value`, and `count`; hourly items contain `hour`, `request_count`, and `percentage`; the User-Agent object contains `unique_count` and `share_percentage`.

CSV uses the header `metric,rank,key,count,percentage`. It emits rows for `top_ip`, `top_error_url`, `hour`, and `unique_user_agents`; non-applicable cells are empty. Newlines and delimiters are handled by Python's `csv` module.

### Exit Codes

The complete exit-code contract is `0/1/2/3/4`; no code may be omitted or remapped.

| Code | Meaning |
|---:|---|
| `0` | Report completed successfully, or help/version was printed |
| `1` | Operational I/O failure while opening or reading input, or writing output |
| `2` | CLI usage or option-validation error |
| `3` | Input completed but contained no valid log records |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent limit would be exceeded |

On codes `1`, `2`, `3`, or `4`, a concise diagnostic is written to stderr. No partial JSON or CSV document is written. In terminal mode, no success report is presented after a fatal error.

## Error and Resource Policy

Malformed individual lines are skipped and counted so one damaged record does not prevent analysis. File errors and invalid encoding are fatal code `1`. Cardinality is checked before inserting a new User-Agent; exceeding the ceiling raises a typed domain error mapped to code `4`. `BrokenPipeError` is handled quietly as an operational output failure without a traceback. Click owns usage errors and code `2`.

Counters for IPs and URLs can also scale with unique input. The 1 GB benchmark therefore records peak RSS, and release documentation states the workload assumption. The dedicated User-Agent ceiling exists because that metric explicitly requires exact cardinality and is most vulnerable to arbitrary strings; broader approximate or spill-to-disk modes are out of MVP scope.

## Performance Design

- Iterate over the binary stream and decode each line once.
- Compile the parser expression once at module import.
- Avoid retaining `LogRecord` instances after aggregation.
- Update only necessary counters and 24 fixed buckets.
- Render only after finite input completes; `--follow` renders a final report on clean interrupt.
- Benchmark a deterministic generated 1 GB fixture outside Git and measure wall time plus peak RSS on a documented laptop.

The acceptance target is under 30 seconds for 1 GB on the reference laptop. It is a measured release gate, not a guaranteed time on every machine.

## Security and Privacy

Processing is local and makes no network requests. Logs are treated as untrusted input: parsing is non-evaluating, terminal values are rendered as text rather than Rich markup, CSV/JSON escaping uses standard-library serializers, and errors do not echo whole lines. The tool never persists records. Packaging pins supported dependency ranges and dependency audits are part of release preparation.

## Packaging and Deployment

Deployment means building an sdist and wheel and installing them with pip into Python 3.11; there is no runtime service deployment. `pyproject.toml` declares Click and Rich runtime dependencies, a `src` layout, and the console script. A clean-environment check runs `python -m build`, installs the wheel, and invokes `nginx-log-report --version` plus a fixture report.

Docker, cloud resources, Kubernetes manifests, authentication, secrets, and environment variables are intentionally absent. The CLI has no authenticated boundary and no configuration that needs secrets.

## Architecture Decision Record

### ADR-001: Single-process stateless CLI

- **Status:** Accepted by the product brief.
- **Context:** A local operator needs four exact aggregate views over one nginx log stream within a one-weekend, $0 scope.
- **Decision:** Use Python 3.11, Click, Rich, dataclasses, and in-memory streaming aggregation in one process.
- **Consequences:** Minimal installation and operations; exact counters consume memory proportional to distinct keys; performance must be demonstrated on the reference laptop.
- **Rejected:** Persistent database, HTTP service, Elastic stack, and Kubernetes because they introduce state and operations outside the value proposition. Multiprocessing is deferred until profiling demonstrates a bottleneck.

No adversarial or independent review is recorded in this document; that review is explicitly delegated to the external harness after this session.
