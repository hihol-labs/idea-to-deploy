# Strategic Plan: nginx-insights

## 1. Product Idea

`nginx-insights` is a local, pip-installable Python 3.11 CLI that streams nginx access logs and reports the top 10 client IPs, top 10 URL paths producing 4xx/5xx responses, request distribution by hour, and the share of unique User-Agents. It serves DevOps and SRE engineers who need an immediate, reproducible diagnostic summary without deploying a service or uploading logs. Default output is colored terminal text; JSON and CSV are stable pipeline formats.

The MVP is a $0 open-source project delivered in one weekend. It is intentionally stateless and local: no authentication, database, HTTP API, server, cloud service, or Kubernetes resources.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs rapid traffic and error hotspots on a laptop or bastion | One command, streaming input, terminal summary, meaningful exit codes |
| Platform engineer | DevOps owner of nginx fleets | Needs composable evidence in scripts and CI jobs | Stable `--json` and `--csv` contracts, stdin support |
| Service owner | Developer debugging a release | Cannot justify operating a full observability stack for one log | Local pip install, no daemon, no retained data |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | nginx-insights distinction |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI/configuration surface than a four-metric pipeline tool | Minimal fixed reports and machine-readable output |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, and retention | Operational cost, services, storage, and setup contradict the local weekend scope | No infrastructure and no persistence |
| AWStats | Established historical web analytics | Batch-oriented, dated workflow, persistent reports/configuration | Streams stdin/files and produces immediate diagnostics |
| `grep`/`awk`/`sort` | Available everywhere and flexible | Fragile parsing, repeated passes, inconsistent schemas, poor portability | Tested nginx parser, one-pass aggregation, explicit contracts |

## 4. Unique Value Proposition

Actionable nginx traffic and error evidence from a gigabyte-scale log in one local command, with human-friendly output and pipeline-safe schemas but no observability stack to operate.

## 5. Business Model and License

The project is open source and free to use. There are no paid tiers, hosted services, tracking, or data collection. Adoption, contributor activity, and usefulness are the success measures; financial unit economics are intentionally not applicable to a $0 local utility.

## 6. Technology Stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required target with mature text and packaging support |
| CLI | Click | Stable option parsing, help, validation, and exit behavior |
| Terminal rendering | Rich | Tables, color, and automatic terminal capability handling |
| Domain models | `dataclasses` | Small typed records without a validation framework |
| Parsing/aggregation | Python standard library | Streaming I/O and counters with no unnecessary dependencies |
| Packaging | pip-compatible `pyproject.toml` | Familiar local installation and console entry point |
| Testing | pytest | Unit, golden-output, integration, and performance tests |

## 7. Timeline

| Weekend block | Outcome |
|---|---|
| Saturday morning | Package skeleton, contracts, nginx parser, fixtures |
| Saturday afternoon | Streaming aggregation and deterministic rankings |
| Sunday morning | Rich, JSON, and CSV renderers; CLI wiring |
| Sunday afternoon | Integration/performance verification, documentation, release candidate |

## 8. KPIs

| Metric | Launch target | First month target | Third month target |
|---|---:|---:|---:|
| Performance | 1 GB under 30 seconds on the reference laptop | Maintain target | Maintain target across supported releases |
| Valid-record correctness | 100% of golden fixtures | No known correctness defects | No regression in golden corpus |
| Install-to-first-report | Under 5 minutes | Under 5 minutes | Under 5 minutes |
| Pipeline compatibility | JSON and CSV golden tests pass | No unannounced schema break | Versioned migration for any schema change |
| Open-source adoption | Public release | 10 users or stars | 3 external issues, discussions, or contributions |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx format variants produce misleading parses | Medium | High | Support and document Combined/Common formats; count skipped lines; golden fixtures |
| Exact unique User-Agent tracking exhausts memory | Medium | High | Configurable cardinality ceiling; fail deterministically with exit code 4 |
| Python misses the 1 GB/30 s target | Medium | High | One pass, compiled regex, allocation-conscious records, benchmark before release |
| Pipeline output changes silently | Low | High | Explicit schemas and golden-output tests |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for a TTY; `--no-color`; JSON/CSV never contain ANSI escapes |
| A weekend scope expands into an observability platform | Medium | Medium | Enforce MoSCoW and explicit Won't list |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Development tools | $0 | $0 | Python and dependencies are open source |
| Hosting/infrastructure | $0 | $0 | Local CLI; no service |
| Database/storage | $0 | $0 | Reads user-supplied logs and retains nothing |
| Distribution | $0 | $0 | Source release and pip-compatible package metadata |
| Total | $0 | $0 | Meets the approved budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream Common/Combined nginx logs from a file or stdin | **Must** | Foundation for local and pipeline use |
| Top-10 client IPs | **Must** | Core traffic hotspot report |
| Top-10 URL paths with 4xx/5xx responses | **Must** | Core failure hotspot report |
| Hourly request percentages | **Must** | Core temporal distribution report |
| Unique User-Agent share with exhaustion guard | **Must** | Core diversity metric with safe failure behavior |
| Colored terminal report | **Must** | Required default experience |
| JSON output | **Must** | Required pipeline format |
| CSV output | **Must** | Required pipeline format |
| Skipped-line diagnostics and deterministic exit codes | **Should** | Essential operability, but does not create the primary metrics |
| Configurable exact-cardinality ceiling | **Should** | Makes the memory safety boundary useful across laptops |
| gzip input | **Could** | Convenient but shell decompression can cover MVP |
| Custom nginx `log_format` configuration | **Could** | Broadens compatibility after the fixed formats are stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless product boundary |
| Live dashboard, retention, alerting | **Won't** | Belongs to full observability products |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. Ordering is a planning aid, not measured production data.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top-10 client IPs | 10 | 4 | 90% | 0.25 | 144.0 |
| Hourly request percentages | 9 | 4 | 90% | 0.25 | 129.6 |
| Top-10 error URL paths | 10 | 5 | 90% | 0.35 | 128.6 |
| Streaming file/stdin ingestion | 10 | 5 | 90% | 0.5 | 90.0 |
| JSON output | 8 | 4 | 90% | 0.35 | 82.3 |
| Skipped-line diagnostics and exit codes | 8 | 4 | 90% | 0.4 | 72.0 |
| Configurable cardinality ceiling | 6 | 3 | 80% | 0.2 | 72.0 |
| CSV output | 7 | 3 | 90% | 0.35 | 54.0 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.5 | 51.2 |
| Colored terminal report | 9 | 3 | 90% | 0.5 | 48.6 |

Dependencies override raw score where needed: ingestion and shared aggregation precede every report; renderers follow the report model.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria agree with `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is formatted, linted, type-checked, and imports successfully.
- [ ] Unit and integration tests pass with at least 90% line coverage for core parser/aggregation modules.
- [ ] JSON/CSV and terminal golden tests pass without ANSI escapes in machine formats.
- [ ] The 1 GB reference benchmark completes under 30 seconds on the documented laptop profile.
- [ ] Error paths cover the complete `0/1/2/3/4` exit-code contract.
- [ ] Documentation and `--help` are current.
- [ ] No known Critical or High security issue remains.
- [ ] A release candidate installs into a clean Python 3.11 virtual environment and is manually smoke-tested.

## 13. Release and Kill Criteria

Release only if correctness fixtures, clean installation, output contracts, and the performance target pass. Re-scope or stop the MVP if a single-pass Python implementation cannot meet 1 GB under 30 seconds after profiling, if exact User-Agent cardinality cannot be bounded transparently, or if reliable parsing requires a general custom-format language beyond the weekend budget.

Architecture details are authoritative in `PROJECT_ARCHITECTURE.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`; user-facing acceptance is in `PRD.md`.
