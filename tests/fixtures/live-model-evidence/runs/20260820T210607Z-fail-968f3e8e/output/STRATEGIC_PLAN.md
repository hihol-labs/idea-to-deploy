# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs as a stream and produces an immediately useful operational summary: the top 10 client IPs, the top 10 request targets producing 4xx/5xx responses, the percentage distribution of valid requests by hour, and the share of distinct User-Agent values.

The product deliberately has no service tier, persistent store, or remote dependency. It is intended for incident triage, post-incident analysis, and shell pipelines where sending logs to an external system is unnecessary or prohibited.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates elevated error rates | Needs a useful answer before a dashboard or ingestion pipeline is available | One local command summarizes the relevant dimensions |
| DevOps engineer | Operates small and medium nginx installations | Full observability stacks are expensive and slow to configure for ad-hoc questions | Stateless processing, no infrastructure, `$0` operating cost |
| Security/operations analyst | Reviews exported or rotated logs | Raw grep pipelines are brittle and hard to reproduce | Stable parsing, deterministic rankings, JSON/CSV contracts |

## 3. Problem and Value Proposition

Operational teams often have the log file but not a ready query or working analytics backend. The tool turns a large nginx access log into a deterministic top-line report without ingestion, indexing, configuration servers, or retained customer data.

**Unique value proposition:** get four high-value nginx traffic and error signals from a gigabyte-scale log in one local command, with both human-readable and pipeline-safe output.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive terminal/HTML analytics | Larger feature surface; interactive presentation is more than a small pipeline may need | Narrow, deterministic four-metric contract and native JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful search, retention, dashboards, correlations | Infrastructure, storage, setup, and operational expense are disproportionate for local triage | Zero-service, stateless, one-command execution |
| AWStats | Established historical reporting | Configuration and generated reports favor periodic analytics over ad-hoc pipelines | Direct streaming CLI with modern machine-readable formats |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Parsing quoting and malformed lines is fragile; several passes and unbounded sort files are common | One tested parser, one pass, consistent definitions and exits |

The project does not attempt to replace persistent observability systems. It owns the fast, local, reproducible summary niche.

## 5. Product and Distribution Model

- Open-source package, installable with `pip` and exposing the `nginx-stream-report` command.
- No paid tier, telemetry, hosted service, authentication, or account system.
- Budget: **$0**. Development uses local/open-source tools and package hosting with no mandatory fee.
- Delivery window: one weekend, with maintainable scope prioritized over breadth.

## 6. Technology Strategy

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, strong packaging and text-processing ecosystem |
| CLI | Click | Reliable option parsing, help text, and standard usage-error behavior |
| Terminal output | Rich | Accessible color and tables with automatic terminal capability handling |
| Domain models | `dataclasses` | Typed, lightweight records without a validation framework |
| Processing | Single process, line-by-line streaming | Minimal moving parts and bounded memory except explicitly guarded cardinality |
| Packaging | `pyproject.toml`, pip | Standard install path and console-script entry point |

## 7. Success Metrics and Performance Objective

| Metric | Launch target | First-month target | Measurement |
|---|---:|---:|---|
| Performance | 1 GB in under 30 seconds | Maintain target on documented laptop baseline | Timed benchmark with a representative local log fixture |
| Correctness | All golden fixtures pass | No known P0 parsing/report defects | Automated unit, integration, and CLI contract tests |
| Memory safety | Cardinality exhaustion fails explicitly | No process OOM on guarded workloads | Stress test for configured User-Agent cardinality limit |
| Pipeline reliability | Stable JSON/CSV and exit codes | No unannounced schema break | Snapshot/schema tests and semantic versioning |
| Time to first report | Under 30 seconds after installation, excluding log scan | Same | Quick Start exercise |

Hourly request distribution is a percentage, defined exactly as `100 × hourly_request_count / total_valid_requests` for each `00`–`23` hour bucket using the hour encoded in each valid nginx timestamp.

## 8. Delivery Timeline

| Period | Outcome |
|---|---|
| Saturday morning | Package skeleton, domain contracts, combined-log parser |
| Saturday afternoon | Streaming aggregation and deterministic rankings |
| Sunday morning | Rich, JSON, and CSV renderers plus CLI behavior |
| Sunday afternoon | Tests, 1 GB benchmark, packaging, documentation, release candidate |

## 9. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming nginx combined-log parser | **Must** | No report can exist without correct one-pass parsing |
| Top-10 client IPs | **Must** | Core incident-triage signal |
| Top-10 error request targets | **Must** | Directly identifies 4xx/5xx hotspots |
| Hourly percentage distribution | **Must** | Required temporal signal |
| Distinct User-Agent share with cardinality guard | **Must** | Required metric and explicit memory-safety boundary |
| Colored terminal report | **Must** | Default user experience |
| JSON output | **Must** | Required pipeline integration |
| CSV output | **Must** | Required tabular pipeline integration |
| Gzip input | **Should** | Common for rotated logs, but decompression can be composed externally |
| Strict malformed-line mode | **Should** | Useful in validation workflows; permissive reporting covers MVP triage |
| Configurable top-N | **Could** | Adds flexibility but the product contract is top 10 |
| Persistent history/dashboard | **Won't** | Conflicts with stateless, local scope |
| HTTP API, authentication, cloud, Kubernetes | **Won't** | Explicitly outside the approved product boundary |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. Values are planning estimates, not measured demand.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 IPs | 9 | 4 | 90% | 0.25 | 129.6 |
| Top-10 error targets | 10 | 5 | 90% | 0.35 | 128.6 |
| Hourly distribution | 8 | 4 | 90% | 0.25 | 115.2 |
| Colored terminal report | 9 | 3 | 90% | 0.30 | 81.0 |
| JSON output | 8 | 4 | 90% | 0.35 | 82.3 |
| CSV output | 7 | 3 | 85% | 0.35 | 51.0 |
| User-Agent share and guard | 7 | 4 | 80% | 0.50 | 44.8 |
| Strict malformed-line mode | 5 | 2 | 75% | 0.20 | 37.5 |
| Gzip input | 6 | 2 | 80% | 0.30 | 32.0 |

Dependency order takes precedence over raw RICE score: the parser must exist before every metric, and renderers must consume a stable result model.

## 10. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex or decoding overhead misses the 30-second target | Medium | High | Benchmark early; compile parser once; avoid per-line object churn where measurement justifies it |
| Real nginx formats differ from combined format | High | Medium | State the accepted grammar, count malformed lines, provide strict mode, defer custom formats |
| High User-Agent cardinality exhausts memory | Medium | High | Enforce a configurable maximum and terminate with exit code 4 before uncontrolled growth |
| Machine output becomes ambiguous | Medium | High | Define schemas, deterministic ordering, stdout/stderr separation, snapshot tests |
| Color corrupts redirected output | Low | Medium | Enable color only for terminal output and only when stdout is a TTY |
| Scope expands into a general observability platform | Medium | High | Maintain explicit Won't list and CLI-only architecture decision |

## 11. Kill Criteria

Re-scope or stop the MVP if the implementation cannot process a representative 1 GB combined log under 30 seconds on the documented laptop after profiling, cannot guard unique-cardinality memory without invalidating the required metric, or requires a database/service to meet the approved feature set.

## 12. Definition of Done

A feature is Done when:

- [ ] Its PRD acceptance criteria are satisfied.
- [ ] Code is formatted and passes static checks.
- [ ] Unit and integration tests pass with at least 90% branch coverage for parser and aggregator modules.
- [ ] CLI contract tests cover terminal, JSON, CSV, stderr, and exit behavior.
- [ ] The representative 1 GB benchmark is recorded and is under 30 seconds on the documented laptop baseline.
- [ ] Documentation and examples match the shipped CLI.
- [ ] No known Critical or High security issue remains.
- [ ] A release candidate installs into a clean Python 3.11 virtual environment and completes the golden flows.

## 13. Document Relationships

Behavioral requirements live in [PRD.md](PRD.md), technical decisions in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and sequenced delivery work in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
