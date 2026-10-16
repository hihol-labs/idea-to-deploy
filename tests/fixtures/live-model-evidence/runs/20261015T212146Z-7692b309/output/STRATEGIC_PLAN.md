# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an operational snapshot: top client IPs, the URLs producing the most 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It is designed for a one-off incident check or a repeatable shell pipeline without a database, service, account, or infrastructure bill.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | Diagnoses incidents under time pressure | Large logs are slow to inspect manually and SaaS upload may be prohibited | One local command, streaming memory use, concise top-10 views |
| SRE/platform engineer | Automates recurring investigations | Human-oriented tools are awkward in pipelines | Stable `--json` and `--csv` schemas with explicit exit codes |
| Systems administrator | Maintains small or isolated estates | Full observability stacks are too expensive or complex | Pip-installable, zero-service, $0 open-source utility |

## 3. Problem and Value Proposition

The product turns a large nginx access log into the four answers most often needed in initial triage. Its value proposition is: **fast, private, pipeline-friendly nginx log triage with no service to operate**.

The tool is intentionally not a general observability platform. It is optimized for bounded summaries of a finite stream, including piped live input that ends when its producer closes.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, rich interactive reports | Wider UI/reporting scope and different output contract than the requested four metrics | Smaller, explicit four-metric CLI and simple machine formats |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, and dashboards | Operational cost, services, storage, and setup are disproportionate to local triage | No daemon, database, cloud, or recurring cost |
| AWStats | Mature historical web analytics | Batch/report orientation and dated operational workflow | Streaming stdin/file processing and modern JSON/CSV output |
| `grep`/`awk`/`sort` | Ubiquitous, composable, no installation in many environments | Fragile parsing, repeated scans, locale differences, and no stable cross-format schema | Tested nginx parser, single pass, deterministic contracts |

## 5. Business and Distribution Model

- License: permissive open-source license, selected before publication.
- Distribution: source repository and Python package installable with `pip`.
- Monetization: none for MVP; the goal is community and internal operational value.
- Unit economics: $0 infrastructure and vendor spend; contributor time is the only cost.

## 6. Product Principles

1. Local by default: log content never leaves the invoking machine.
2. One pass: do not retain raw records or require a second scan.
3. Stable automation: machine-readable output and exit codes are versioned contracts.
4. Honest limits: malformed input, I/O failures, and cardinality exhaustion are reported, not hidden.
5. Narrow scope: avoid becoming a dashboard, collector, or storage system.

## 7. Technology Strategy

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, productive for a one-weekend build |
| CLI | Click | Reliable options, help text, validation, and exit handling |
| Terminal UI | Rich | Required colored tables and accessible no-color fallback |
| Domain model | `dataclasses` | Typed, lightweight records and aggregate snapshots |
| Packaging | `pyproject.toml` + pip | Standard install and console entry point |
| Tests | pytest | Fast unit, CLI, integration, and performance checks |

## 8. Delivery Timeline

| Window | Outcome |
|---|---|
| Saturday morning | Package skeleton, contracts, parser fixtures, and CLI shell |
| Saturday afternoon | Streaming aggregates and resource bounds |
| Sunday morning | Rich, JSON, and CSV renderers plus error mapping |
| Sunday afternoon | End-to-end, performance, packaging, and documentation validation |

## 9. Success Metrics

| Metric | MVP target | Measurement |
|---|---:|---|
| Performance | 1 GB in under 30 seconds on the documented laptop/reference dataset | Repeatable benchmark command with machine specs recorded |
| Correctness | 100% of golden fixtures and output-schema tests pass | CI/test report |
| Streaming behavior | Peak memory is independent of input byte size except bounded IP/URL maps and configured User-Agent cardinality | Resource test at two input sizes |
| Automation stability | JSON and CSV schemas plus exit codes are covered by tests | CLI contract test suite |
| Adoption signal | At least 3 engineers complete a real triage without assistance in month one | Short feedback record |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Runtime and libraries | $0 | Python and selected dependencies are open source |
| Infrastructure | $0/month | No server, database, cloud, or telemetry backend |
| Distribution | $0 | Source and package tooling use free/open-source paths |
| Delivery labor | One weekend | Fixed scope; no paid contractor or vendor assumed |

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the assumed combined format | Medium | High | Document accepted format; fail malformed lines consistently; isolate parser for later format adapters |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, avoid regex backtracking and per-line object retention, profile before adding features |
| High-cardinality IP/URL/UA data exhausts memory | Medium | High | Document bounded strategy; enforce a configurable unique-UA ceiling and exit `4` rather than corrupting results |
| CSV representation of several report sections surprises pipeline users | Medium | Medium | Define one long-form schema with `section`, `key`, `count`, and `percentage`; test ordering |
| Color or diagnostics contaminate pipelines | Low | High | Disable color for non-TTY/machine formats; send diagnostics to stderr only |
| Malformed records bias percentages | Medium | Medium | Base percentages on `total_valid_requests`; report valid and malformed counts |

## 12. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from files or stdin | **Must** | Foundation for local and pipeline use |
| Top-10 client IP counts | **Must** | Core incident-triage question |
| Top-10 URLs restricted to 4xx/5xx responses | **Must** | Core error hotspot view |
| Hourly request distribution | **Must** | Required traffic-shape view |
| Unique User-Agent share with bounded cardinality | **Must** | Required client-diversity signal and safety bound |
| Colored terminal, JSON, and CSV outputs | **Must** | Required interactive and pipeline interfaces |
| Deterministic exit-code and malformed-line contract | **Must** | Required reliable automation behavior |
| Gzip input | **Should** | Common operational convenience; defer if weekend capacity is tight |
| User-supplied top-N | **Could** | Useful generalization but the MVP contract is top 10 |
| Persistent history, dashboard, server, auth, cloud, Kubernetes | **Won't** | Conflicts with a stateless local CLI |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Exit and malformed-line contract | 9 | 4 | 90% | 0.3 | 108.0 |
| Hourly distribution | 8 | 4 | 90% | 0.3 | 96.0 |
| IP and error-URL top tens | 10 | 5 | 90% | 0.5 | 90.0 |
| Streaming input + parser | 10 | 5 | 90% | 0.6 | 75.0 |
| Terminal/JSON/CSV output | 10 | 4 | 90% | 0.6 | 60.0 |
| Unique User-Agent share and cap | 7 | 4 | 80% | 0.4 | 56.0 |
| Gzip input | 5 | 2 | 70% | 0.3 | 23.3 |

Dependency order overrides raw RICE where necessary: input parsing precedes every aggregate, while the contract is frozen before implementation.

## 13. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Code is type-checkable/importable on Python 3.11 and package installation succeeds.
- [ ] Unit and integration tests pass; critical parser, aggregation, renderer, and exit paths are covered.
- [ ] The 1 GB benchmark completes under 30 seconds on the documented reference laptop.
- [ ] Output schemas, help text, README, and implementation guidance agree.
- [ ] No known critical/high security issue remains and untrusted log text cannot inject terminal controls.
- [ ] No database, API, server, cloud, authentication, or Kubernetes dependency has been introduced.

## 14. Kill Criteria

Stop or rescope the MVP if profiling shows the required 1 GB/30 s target cannot be reached in Python 3.11 without native extensions, or if exact required metrics cannot be produced within a documented safe memory envelope. Do not silently weaken correctness, resource safety, or output contracts.
