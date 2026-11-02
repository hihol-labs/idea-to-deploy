# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined access logs as a stream and produces a compact operational report: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, request distribution by hour, and the share of unique User-Agents. Rich colored terminal output is the default; JSON and CSV support automation and pipelines.

The product is intentionally local and stateless. It has no authentication, database, HTTP API, server, cloud service, or Kubernetes dependency. MVP delivery is constrained to one weekend and a $0 software/infrastructure budget.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs immediate traffic/error clues without uploading sensitive logs | One local command produces bounded-memory summaries |
| Platform engineer | DevOps engineer maintaining hosts and pipelines | Needs machine-readable output that composes with shell tooling | Stable `--json` and `--csv` schemas and meaningful exit codes |
| Service owner | Backend engineer investigating regressions | Needs to identify noisy clients and failing routes quickly | Top-10 rankings plus hourly percentages |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive dashboards | Broader UI/configuration footprint than a focused pipeline report | Small, purpose-built CLI with stable JSON/CSV contracts |
| Logstash + Elastic + Kibana | Powerful ingestion, search, and visualization | Operationally heavy; requires services, storage, and setup | Zero-service local processing with no retained data |
| AWStats | Established historical reports | Batch-oriented and dated operational workflow | Immediate streaming analysis and pipeline output |
| `grep`/`awk` | Ubiquitous and flexible | Fragile parsing, repeated one-off commands, inconsistent output | Tested nginx parsing and one reproducible report contract |

## 4. Unique Value Proposition

Turn a large nginx access log into the four incident metrics SREs need most, locally and reproducibly, with one command and no service to operate.

## 5. Business Model

The MVP is open source and free. There is no monetization requirement for the one-weekend release. Value is measured through adoption, reliability, and reduced incident-analysis time rather than revenue; optional future sponsorship must not gate core functionality.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, broadly available, rapid weekend delivery |
| CLI | Click | Stable option parsing, help, validation, and exit handling |
| Terminal UI | Rich | Accessible colored tables with automatic non-TTY handling |
| Domain models | `dataclasses` | Typed, dependency-free records and report structures |
| Packaging | `pyproject.toml` + pip | Standard install and console-script distribution |
| Tests | pytest | Fast unit/integration/performance test workflow |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, parser, domain model | Installable CLI skeleton and validated streaming records |
| Saturday afternoon | Aggregation | All four metrics computed in one pass |
| Sunday morning | Text, JSON, CSV renderers | Stable human and pipeline contracts |
| Sunday afternoon | Tests, benchmark, documentation | Release candidate meeting correctness and performance gates |

## 8. KPIs

| Metric | Release target | First month | Three months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Valid fixture correctness | 100% | 100% | 100% |
| P0 automated test pass rate | 100% | 100% | 100% |
| Peak resident memory on 1 GB benchmark | ≤256 MiB | ≤256 MiB | ≤192 MiB target |
| Installs by users other than maintainers | 0 required | 10 | 50 |

The reference laptop, input fixture, cache state, timing command, and peak-memory measurement must be recorded with benchmark results so the 30-second claim is reproducible.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx format variations break parsing | High | High | Define supported combined format, count malformed lines, document custom formats as out of scope |
| Exact unique User-Agent tracking exhausts memory | Medium | High | Configurable cardinality cap and exit code `4`; bounded failure instead of swapping |
| Python misses the 1 GB/30 s target | Medium | High | Byte-oriented profiling, one pass, no per-line regex recompilation, benchmark early |
| CSV cannot naturally express heterogeneous report sections | Medium | Medium | Define a normalized row schema with `section`, `key`, `count`, `percentage`, and `rank` |
| Color corrupts redirected output | Low | Medium | Enable color only for TTY by default; JSON/CSV never contain ANSI escapes |
| Incorrect timezone assumptions skew hourly results | Medium | Medium | Use each nginx timestamp's numeric offset and define buckets by logged local hour |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, pytest are open source |
| Infrastructure | $0 | Local-only CLI; no hosted services |
| Distribution | $0 | Source repository and pip-compatible artifact tooling |
| Delivery labor | One weekend | Scope is fixed to the MVP contract |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming combined-log parsing | Must | Foundation for every metric and bounded memory |
| Top 10 client IPs | Must | Core incident triage question |
| Top 10 error URLs for 4xx/5xx | Must | Core regression and failure signal |
| Hourly request distribution percentages | Must | Reveals traffic concentration over time |
| Unique User-Agent share with cardinality guard | Must | Required metric with explicit bounded-resource behavior |
| Rich terminal output | Must | Required default UX |
| JSON output | Must | Required pipeline integration |
| CSV output | Must | Required pipeline integration |
| Gzip input autodetection | Should | Common log rotation format, but decompression can be piped externally |
| Top-N customization | Could | Useful extension after the fixed top-10 contract is stable |
| Custom nginx log formats | Could | Broadens adoption but increases parser complexity |
| Database, HTTP API, auth, cloud, Kubernetes | Won't | Explicitly outside a local stateless CLI |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. Ties are ordered by dependency.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL aggregation | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly percentages | 8 | 4 | 95% | 0.25 | 121.6 |
| Rich output | 9 | 4 | 90% | 0.35 | 92.6 |
| JSON output | 8 | 4 | 95% | 0.25 | 121.6 |
| CSV output | 7 | 3 | 90% | 0.30 | 63.0 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.50 | 51.2 |
| Gzip input | 6 | 2 | 80% | 0.25 | 38.4 |

Dependency overrides raw RICE where necessary: parsing precedes aggregators, and the canonical report model precedes renderers.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code is typed and lint-clean under the project's configured checks.
- [ ] Unit tests and relevant CLI integration tests pass.
- [ ] P0 paths have at least 90% line coverage; parser and aggregation branches include malformed-input cases.
- [ ] No known Critical or High security issue remains.
- [ ] User-facing contracts and examples are updated.
- [ ] Performance-affecting changes pass the recorded 1 GB benchmark.
- [ ] Another maintainer reviews the change before release.

## 13. Release and Kill Criteria

Release the MVP only if all P0 acceptance criteria pass, all output formats are deterministic, and the reproducible 1 GB benchmark completes under 30 seconds. Stop or rescope the weekend release if the benchmark exceeds 45 seconds after profiling, exact User-Agent cardinality cannot be bounded safely, or valid-line parsing correctness is below 99.9% on the agreed fixture corpus.

