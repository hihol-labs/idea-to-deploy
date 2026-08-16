# Strategic Plan: nginx-stream-stats

## 1. Product Summary

`nginx-stream-stats` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined access logs from a file or standard input in one pass and reports the top client IPs, the URLs producing the most 4xx/5xx responses, hourly traffic distribution, and the percentage of unique User-Agent values. It is deliberately local, stateless, and pipeline-friendly.

The MVP is a one-weekend, $0 open-source delivery. It does not include a database, authentication, a network service, cloud resources, or Kubernetes.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary before a dashboard can be opened | Streams a local or piped log and returns the four core metrics immediately |
| Platform engineer | Maintains nginx fleets and shell automation | Ad hoc `awk` pipelines are fragile and inconsistent | Provides stable JSON/CSV schemas, exit codes, and deterministic ranking |
| Developer/operator | Debugs a service on a laptop or bastion | Full observability stacks are too heavy for a one-off log | Installs with pip, keeps no state, and requires no service or account |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a four-metric pipeline tool | Narrow contract, native JSON/CSV, Python/pip workflow |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, setup, and ongoing operations | Zero-service, one-shot local analysis |
| AWStats | Established historical web statistics | Report-generation model and persistent history do not fit stdin streaming | Immediate terminal output with no retained state |
| `grep`/`awk`/`sort` | Universally available and composable | Parsing quoted fields, errors, portability, and cardinality safely is cumbersome | Tested nginx parser and a stable machine-readable contract |

## 4. Unique Value Proposition

Get a deterministic, automation-safe nginx health snapshot from a large local log with one pip-installed command and no infrastructure.

## 5. Business and Distribution Model

The product is free and open source. There is no paid tier, hosted component, or telemetry. Value is measured through reliable adoption and reduced incident-analysis time rather than revenue, CAC, or LTV. Distribution is via a standard Python package and source repository; maintenance stays bounded by the intentionally small contract.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved platform with broad operator availability |
| CLI | Click | Stable option parsing, help, validation, and exit behavior |
| Terminal rendering | Rich | Readable color and tables with terminal detection |
| Domain models | `dataclasses` | Typed records without a heavier model dependency |
| Parsing/aggregation | Python standard library | Streaming I/O, counters, JSON, and CSV |
| Packaging | pip-compatible `pyproject.toml` | Standard install and console-script distribution |
| Verification | pytest plus CLI integration tests | Fast unit and end-to-end evidence |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for boundaries and [PRD.md](PRD.md) for behavior.

## 7. Delivery Timeline

| Block | Effort | Outcome |
|---|---:|---|
| Saturday morning | 3 hours | Package skeleton, typed records, streaming parser |
| Saturday afternoon | 4 hours | Aggregators, cardinality guard, deterministic results |
| Sunday morning | 4 hours | Click CLI and terminal/JSON/CSV renderers |
| Sunday afternoon | 3 hours | Tests, 1 GB benchmark, packaging and documentation |

Total planned engineering effort is approximately 14 hours in one weekend. The dependency order is in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 8. Success Metrics

| Metric | MVP gate | Month 1 | Month 3 |
|---|---:|---:|---:|
| 1 GB combined-log processing time on the reference laptop | < 30 seconds | < 30 seconds | < 25 seconds |
| Peak resident memory on representative 1 GB input | < 256 MiB, subject to configured UA guard | < 256 MiB | < 192 MiB |
| Correctness fixtures passing | 100% | 100% | 100% |
| CLI contract scenarios passing | 100% | 100% | 100% |
| Median install-to-first-report time in usability checks | < 5 minutes | < 3 minutes | < 2 minutes |

Performance claims require a documented laptop, generated fixture, command, and timing/RSS measurement.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx format variants break parsing | Medium | High | Scope MVP to combined format, expose strict mode, count skipped lines, test escaping and malformed records |
| Very high User-Agent cardinality exhausts memory | Medium | High | Configurable hard guard, fail explicitly with exit code 4, never silently approximate |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, compile the parser once, retain no lines, optimize only from profiles |
| JSON/CSV semantics drift from terminal output | Medium | Medium | One result model shared by all renderers and golden output tests |
| Pipe and encoding edge cases corrupt automation output | Low | Medium | Diagnostics on stderr, UTF-8 output, explicit I/O errors, integration tests |
| Scope creeps toward a dashboard or service | Medium | Medium | Enforce MoSCoW exclusions and the CLI-only decision |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Python, Click, Rich, pytest | $0 | Open-source dependencies |
| Development and benchmark environment | $0 | Existing laptop and local tooling |
| Hosting, database, cloud, Kubernetes | $0 | Explicitly absent |
| Distribution | $0 | Source repository and pip-compatible artifacts |
| Total cash budget | **$0** | Personal weekend effort is the only investment |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined logs from file or stdin | **Must** | Foundation for files and Unix pipelines |
| Top 10 client IPs | **Must** | Core incident triage signal |
| Top 10 URLs by 4xx/5xx count | **Must** | Core error hotspot signal |
| Hourly request percentages | **Must** | Required traffic-shape signal |
| Unique User-Agent percentage with exhaustion guard | **Must** | Required diversity signal without unbounded memory |
| Colored terminal report | **Must** | Approved default experience |
| JSON output | **Must** | Required structured pipeline output |
| CSV output | **Must** | Required tabular pipeline output |
| Strict malformed-line handling | **Should** | Useful enforcement, though lenient parsing can ship first |
| Configurable top-N limit | **Could** | Flexibility beyond the required top 10 |
| gzip input | **Could** | Shell decompression already composes with stdin |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Conflicts with local stateless CLI scope |
| Persistent history, dashboard, live follow mode | **Won't** | Not required for the one-shot MVP |

### RICE Scoring for Must and Should Features

Confidence is a decimal in the calculation; scores are planning estimates.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| File/stdin streaming and parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Top IP aggregation | 9 | 4 | 90% | 0.25 | 129.6 |
| Error URL aggregation | 9 | 5 | 90% | 0.35 | 115.7 |
| Hourly percentage distribution | 8 | 4 | 90% | 0.30 | 96.0 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.50 | 51.2 |
| JSON output | 8 | 4 | 90% | 0.30 | 96.0 |
| CSV output | 7 | 3 | 90% | 0.35 | 54.0 |
| Colored terminal output | 8 | 3 | 90% | 0.50 | 43.2 |
| Strict mode and diagnostics | 6 | 3 | 80% | 0.35 | 41.1 |

Implementation uses dependency constraints first, then descending RICE among unblocked features.

## 12. Definition of Done

A feature is done when:

- [ ] Behavior and acceptance criteria agree with [PRD.md](PRD.md).
- [ ] Python 3.11 code is formatted, linted, and type-checked.
- [ ] Unit tests pass with at least 90% statement coverage.
- [ ] Applicable CLI integration and golden-output tests pass.
- [ ] Performance-sensitive changes pass the documented 1 GB benchmark.
- [ ] User and developer documentation is updated.
- [ ] No known critical or high-severity security defect remains.
- [ ] A reviewer approves the eventual implementation; this planning session does not provide that review.
- [ ] The wheel is smoke-tested in a clean local virtual environment.

## 13. Release and Kill Criteria

Release only if fixtures pass, all output modes represent identical results, the complete `0/1/2/3/4` exit contract passes, and 1 GB completes under 30 seconds on the named reference laptop.

Stop or rescope if streaming cannot meet the target after profiling, exact User-Agent cardinality cannot be bounded with explicit failure, or scope begins to require persistent services.
