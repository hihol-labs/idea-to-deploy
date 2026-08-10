# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs one line at a time and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It is designed for incident triage and routine log inspection without uploading operational data or running a service.

The MVP is open source, costs $0 to operate, and is scoped for delivery in one weekend. The performance acceptance target is processing a 1 GB representative log in under 30 seconds on a documented laptop baseline.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary in seconds without building a query stack | One local command, streaming aggregation, terminal-first output |
| Platform engineer | Maintains nginx fleets and automation | Needs machine-readable results in shell pipelines | Stable `--json` and `--csv` contracts and explicit exit codes |
| Developer/operator | Debugs a service locally or on a small host | Existing observability stacks are unavailable or excessive | Pip installation, stdin/file input, no daemon or database |

## 3. Problem and Value Proposition

Operational access logs are easy to obtain but slow to summarize correctly under incident pressure. Ad hoc `grep`/`awk` pipelines are fragile, while observability platforms have setup and operating costs. The product provides a focused, reproducible summary locally with bounded streaming behavior and pipeline-safe output.

**Unique value proposition:** actionable nginx traffic and error distributions from a local log in one command, with no service, database, account, or data upload.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than the requested four metrics | Smaller, automation-first CLI contract and Python packaging |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, querying, dashboards, retention | Significant installation, resources, and ongoing operations | Stateless, local, zero-infrastructure execution |
| AWStats | Established historical web analytics | Batch/reporting orientation and dated operational workflow | Immediate stream summary and JSON/CSV output |
| `grep`/`awk` pipelines | Ubiquitous and zero-install on many hosts | Quoting, parsing, portability, and metric consistency are fragile | Tested nginx parsing, one stable schema, explicit failure semantics |

The product does not try to replace persistent observability or exploratory analytics. It wins when a fast, repeatable local summary is enough.

## 5. Business Model and Budget

The MVP is an open-source utility with no monetization requirement. Potential future sustainability is community sponsorship or paid support, but neither affects MVP design.

| Item | One-time | Recurring | Notes |
|---|---:|---:|---|
| Development | $0 | $0 | One-weekend contributor time; no paid labor budget |
| Hosting/infrastructure | $0 | $0 | Local CLI; package may use free public package hosting |
| Runtime services | $0 | $0 | No server, database, telemetry, or third-party API |
| Tooling | $0 | $0 | Python and open-source dependencies/tooling |
| **Total cash budget** | **$0** | **$0** | Contributor time is the binding constraint |

## 6. Technology Strategy

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved stack and broad operator availability |
| CLI | Click | Predictable option validation, help, and exit handling |
| Terminal output | Rich | Readable tables and color with terminal detection |
| Domain models | `dataclasses` | Lightweight typed records and aggregates |
| Packaging | `pyproject.toml`, pip | Standard install and console-script workflow |
| Processing | Single process, single pass | Minimal operational complexity and bounded input memory |

## Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from a file or stdin | **Must** | Foundation for all value and for large-file memory behavior |
| Top-10 client IPs | **Must** | Direct traffic-source triage |
| Top-10 4xx/5xx URLs | **Must** | Direct error hotspot triage |
| Hourly request percentages | **Must** | Required time-distribution view |
| Exact unique User-Agent share with a cardinality guard | **Must** | Required metric without unbounded silent memory growth |
| Colored terminal report | **Must** | Required default operator experience |
| JSON output | **Must** | Required pipeline integration |
| CSV output | **Must** | Required pipeline/spreadsheet integration |
| Invalid-line diagnostics and stable exit codes | **Must** | Required for trustworthy unattended use |
| gzip input | **Should** | Common operational format, but decompression can be piped for MVP |
| Configurable top-N | **Could** | Useful flexibility beyond the fixed top-10 requirement |
| IPv6/request-format extensions | **Could** | Broadens compatibility after the common combined format is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with local stateless CLI scope |
| Persistent dashboards and historical correlation | **Won't** | Belongs to GoAccess or an observability platform |

### RICE Scoring (Must and Should)

Confidence is represented as a decimal in the formula `Reach × Impact × Confidence / Effort`. Scores guide dependency-aware ordering; foundational parsing precedes dependent reports even where scores are close.

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin ingestion | 10 | 5 | 100% | 0.6 | 83.3 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly request percentages | 8 | 4 | 95% | 0.3 | 101.3 |
| Colored terminal report | 8 | 3 | 95% | 0.3 | 76.0 |
| JSON output | 8 | 4 | 95% | 0.4 | 76.0 |
| CSV output | 6 | 3 | 90% | 0.35 | 46.3 |
| Unique User-Agent share and guard | 7 | 3 | 85% | 0.55 | 32.5 |
| Diagnostics and exit codes | 8 | 4 | 95% | 0.55 | 55.3 |
| gzip input | 5 | 3 | 80% | 0.4 | 30.0 |

## 8. Delivery Timeline

| Window | Work | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI can stream and classify valid/invalid lines |
| Saturday afternoon | Aggregation and terminal output | Four required metrics render deterministically |
| Sunday morning | JSON/CSV, error semantics, tests | Pipeline interfaces and complete exit contract are covered |
| Sunday afternoon | 1 GB benchmark, profiling, docs, packaging | Performance evidence and release-ready documentation |

## 9. Success Metrics

| KPI | Release target | Measurement |
|---|---|---|
| Performance | 1 GB in under 30 seconds | Hyperfine or timed benchmark on the documented laptop, warm-up excluded |
| Streaming memory | Memory does not grow with line count except bounded distinct keys | Peak RSS recorded on benchmark; cardinality guard tested |
| Correctness | Golden fixture outputs match for all four metrics and all formats | Automated unit and CLI integration tests |
| Pipeline reliability | Every defined failure maps to `0/1/2/3/4` | CLI tests assert status and stderr/stdout separation |
| Usability | Fresh user reaches first report in under 30 seconds after install | README quick-start walkthrough |

## 10. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the combined format | Medium | High | State MVP grammar, provide actionable invalid-line counts, add formats only from fixtures |
| Unique User-Agent set grows beyond laptop memory | Medium | High | Exact configurable cap; fail with exit code 4 rather than approximate silently |
| Python misses the 1 GB/30 s target | Medium | High | Single compiled parser pattern, no per-line object retention, benchmark early, profile before optimizing |
| Output schemas drift across renderers | Medium | Medium | One report dataclass and golden tests for text/JSON/CSV |
| Piped output contains ANSI codes or diagnostics | Low | Medium | Auto-disable color off-TTY; stdout for results, stderr for diagnostics |
| Corrupt lines bias percentages unnoticed | Medium | Medium | Count and report skipped lines; denominator is explicitly `total_valid_requests` |

## 11. Kill Criteria

Re-scope or stop the MVP if representative 1 GB logs cannot meet the target after profiling, exact User-Agent tracking cannot be bounded with an explicit failure, or the supported nginx grammar cannot achieve reliable fixture-based parsing in the weekend. Do not add a database, server, or distributed processing to rescue the MVP; those would invalidate its value proposition.

## Definition of Done

A release is done when:

- [ ] The package installs on Python 3.11 and exposes the documented console command.
- [ ] All P0 acceptance criteria in `PRD.md` pass.
- [ ] Unit and CLI integration tests pass with at least 90% statement coverage for parser, aggregation, rendering, and exit mapping.
- [ ] The representative 1 GB benchmark completes in under 30 seconds on the recorded laptop baseline.
- [ ] Text, JSON, and CSV golden outputs are stable and documented.
- [ ] Invalid input and unique-cardinality exhaustion are covered by tests.
- [ ] Documentation (`README.md`, `PROJECT_ARCHITECTURE.md`, and CLI help) is current.
- [ ] No known critical or high-severity security issue remains.
- [ ] A maintainer review is complete; this blueprint's architecture review was only a self-critique.

The technical source of truth is `PROJECT_ARCHITECTURE.md`; product acceptance is defined by `PRD.md`, and delivery sequencing by `IMPLEMENTATION_PLAN.md`.
