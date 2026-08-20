# Strategic Plan: nginx-log-insights

## 1. Product Idea

`nginx-log-insights` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage share of unique User-Agent values. Its default experience is readable colored terminal output; deterministic JSON and CSV formats support automation.

The MVP is deliberately narrow: local files or standard input in, aggregate reports out. It has no authentication, persistence layer, network service, or remote dependency.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error snapshot without provisioning a dashboard | Runs one local command against a file or stream and gets four operational metrics |
| Platform engineer | Maintains CI and operational scripts | Shell parsing is brittle and terminal-only tools are hard to automate | Uses stable `--json` or `--csv` output and documented exit codes |
| Service owner | Developer responsible for an nginx-fronted application | Needs to identify noisy clients and failing routes quickly | Receives ranked IP and error-URL lists plus a time-of-day distribution |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this project | Our distinction |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics; fast native implementation | More features and UI surface than a four-metric pipeline tool needs | Minimal install and stable text/JSON/CSV contracts for exactly the approved metrics |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, and dashboards | Operationally heavy; requires services, storage, configuration, and ongoing resources | One local, stateless process with no infrastructure |
| AWStats | Established historical web analytics | Report-generation workflow and broad analytics are less suitable for immediate stream inspection | Immediate CLI output from files or stdin |
| `grep`/`awk`/`sort` | Ubiquitous, composable, and dependency-light | Format parsing, quoting, URL extraction, error handling, and multi-metric aggregation become brittle | Tested parsing with a single explicit output and exit-code contract |

## 4. Unique Value Proposition

Get the four nginx signals an on-call engineer needs from a gigabyte-scale log in one local command, with human-friendly output and pipeline-safe structured formats—without deploying or operating anything.

## 5. Business Model

The product is open source and costs $0 to use. There is no monetization in the MVP; success is measured by utility, reliability, and adoption. The project avoids infrastructure costs and paid services. Maintainer time for the one-weekend build is contributed and is not charged to the project budget.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable runtime with strong streaming text support |
| CLI | Click | Explicit option validation, help generation, and predictable CLI errors |
| Terminal rendering | Rich | Accessible tables and color with terminal detection |
| Domain models | Standard-library dataclasses | Typed, dependency-light data transfer between parser, aggregator, and renderers |
| Parsing and aggregation | Python standard library | Avoids unnecessary runtime dependencies and permits line-by-line processing |
| Packaging | `pyproject.toml` with pip entry point | Standard installation and isolated build metadata |
| Testing | pytest | Fast unit, integration, and CLI contract tests |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable command and validated combined-log parsing |
| Saturday afternoon | Streaming aggregations | All four metrics computed in a single pass with bounded-cardinality guards |
| Sunday morning | Text, JSON, CSV renderers | Stable human and pipeline outputs with exit-code behavior |
| Sunday afternoon | Performance, docs, release checks | 1 GB benchmark evidence, package smoke test, and handoff-ready documentation |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 s | < 25 s | < 20 s |
| Correctness fixtures passing | 100% | 100% | 100% |
| Peak memory on the standard 1 GB fixture | < 512 MiB | < 384 MiB | < 256 MiB |
| Valid-log parse rate on documented nginx combined format | >= 99.9% | >= 99.9% | >= 99.9% |
| GitHub stars or equivalent adoption signal | 10 | 50 | 150 |

Performance goals are acceptance targets to be measured during implementation, not claims about an implementation that does not yet exist.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python throughput misses 1 GB/30 s | Medium | High | Single pass, compiled regex or specialized tokenizer selected by benchmark, batched output, and a committed 1 GB benchmark procedure |
| High-cardinality IP/URL/User-Agent values exhaust memory | Medium | High | Configurable unique-value ceiling, early capacity checks, documented exit code `4`, and peak-memory tests |
| Real nginx formats differ from the documented combined format | High | Medium | Support an explicit `--log-format`, fail clearly for unsupported formats, count malformed lines, and publish examples |
| CSV representation becomes ambiguous across heterogeneous metrics | Medium | Medium | Use a normalized row schema with metric/rank/key/count/percentage columns and golden-output tests |
| Terminal color corrupts redirected output | Low | Medium | Enable color only for a terminal by default; `--color/--no-color` remains explicit |
| Malformed input silently distorts percentages | Medium | High | Base denominators only on valid parsed requests and report skipped-line counts |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and dependencies are open source |
| Hosting and infrastructure | $0 | Local-only CLI; no hosted components |
| CI | $0 | Use a free open-source allowance or local verification |
| Distribution | $0 | Source distribution/wheel and public package hosting |
| Paid data/services | $0 | None required |
| **Total cash budget** | **$0** | One-weekend contributor effort is in-kind |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined logs from files and stdin | **Must** | The product cannot analyze logs without safe streaming input |
| Top 10 client IPs | **Must** | Core approved incident-response metric |
| Top 10 4xx/5xx URLs | **Must** | Core approved error-localization metric |
| Hourly request percentage distribution | **Must** | Core approved traffic-shape metric |
| Unique User-Agent percentage | **Must** | Core approved client-diversity metric |
| Colored terminal tables | **Must** | Approved default user experience |
| JSON and CSV output | **Must** | Required for pipeline integration |
| Explicit malformed-line and cardinality handling | **Must** | Required for trustworthy and bounded operation |
| Gzip-compressed input | **Should** | Common operational convenience; shell decompression is an MVP workaround |
| Custom nginx format templates | **Should** | Broadens compatibility beyond the documented combined format |
| Configurable top-N | **Could** | Useful flexibility but top 10 is the approved product contract |
| Approximate low-memory cardinality | **Could** | Can extend scale after exact MVP behavior is validated |
| Database, HTTP API, server, cloud, Kubernetes, authentication | **Won't** | Explicitly outside the local stateless CLI boundary |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. Estimates are planning assumptions for the first month.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin + parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top 10 client IPs | 10 | 4 | 95% | 0.25 | 152.0 |
| Top 10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly percentage distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent percentage | 8 | 3 | 85% | 0.35 | 58.3 |
| Colored terminal output | 10 | 3 | 95% | 0.35 | 81.4 |
| JSON and CSV output | 9 | 5 | 90% | 0.50 | 81.0 |
| Malformed/cardinality handling | 10 | 5 | 85% | 0.50 | 85.0 |
| Gzip input | 6 | 2 | 80% | 0.25 | 38.4 |
| Custom format templates | 6 | 4 | 60% | 1.00 | 14.4 |

Dependency order takes precedence where a high-scoring metric requires the parser. Within each dependency layer, implementation follows descending RICE score.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria are represented in `PRD.md`.
- [ ] Code is written for Python 3.11 and the package builds without errors.
- [ ] Unit and CLI integration tests pass with at least 90% line coverage.
- [ ] Performance-sensitive work includes measured evidence against the reference benchmark.
- [ ] Output schemas, exit codes, and user documentation are updated.
- [ ] Code review passes with no unresolved critical or high-severity findings.
- [ ] The installable wheel is smoke-tested in a clean virtual environment.
- [ ] No network service, persistence layer, authentication, cloud, or Kubernetes dependency has entered scope.

## 13. Product Definition of Done

The MVP is ready when all P0 acceptance criteria in `PRD.md` pass, the 1 GB reference input completes in under 30 seconds on the documented laptop profile, exact output fixtures pass for text/JSON/CSV, all exit codes `0/1/2/3/4` are exercised, pip installation succeeds in a clean Python 3.11 environment, and there are no unresolved release-blocking defects.
