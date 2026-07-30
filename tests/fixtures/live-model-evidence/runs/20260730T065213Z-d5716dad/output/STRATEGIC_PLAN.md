# Strategic Plan: nginx Log Top

## 1. Product Idea

nginx Log Top is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads an nginx access log as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Human-readable colored terminal output is the default; JSON and CSV make the same results usable in shell pipelines.

The product deliberately does not run a service or retain logs. It provides useful incident and traffic summaries without sending operational data elsewhere or requiring a monitoring platform.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents under time pressure | Needs a fast summary of a large local log without provisioning tools | One command produces the four core views |
| DevOps engineer | Automates diagnostics and reports | Terminal-only tools often lack stable machine output | Stable JSON and CSV contracts support pipelines |
| Platform engineer | Works on restricted or air-gapped systems | Uploading access logs is prohibited or impractical | All processing is local, streaming, and stateless |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | nginx Log Top differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a small pipeline tool needs | Narrow metrics, predictable CLI, JSON/CSV, Python installation |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, dashboards | Infrastructure, storage, operations, and resource cost are disproportionate | Zero service dependencies and no retained data |
| AWStats | Established historical reporting | Persistent reports and legacy configuration-oriented workflow | Immediate local streaming analysis |
| `grep` / `awk` / `sort` | Ubiquitous and composable | Fragile parsing, repeated passes, locale differences, hard-to-version output contracts | One parser, one pass, tested metrics, stable schemas |

## 4. Unique Value Proposition

Get the nginx incident summary an SRE needs from a gigabyte-scale log in one local command, with no service, database, or data upload.

## 5. Business Model

The project is open source and free to install and use. There is no monetization in the MVP; its value is reduced incident-response time and a reusable community tool. Commercial hosting, telemetry, paid support, and enterprise features are outside the one-weekend scope.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved baseline; widely available to operators |
| CLI | Click | Mature argument parsing, help, and exit handling |
| Terminal rendering | Rich | Accessible colored tables with graceful non-color behavior |
| Domain records | `dataclasses` | Explicit, low-overhead internal contracts |
| Packaging | pip-compatible Python package | Familiar local and virtual-environment installation |
| Tests/benchmarks | pytest plus standard-library generators | Repeatable correctness and 1 GB performance evidence |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Package, CLI, parser contracts | Installable command and representative fixture parsing |
| Saturday afternoon | Streaming aggregations | All four P0 metrics computed in one pass |
| Sunday morning | Rich, JSON, and CSV renderers | Stable human and pipeline output |
| Sunday afternoon | Edge cases, benchmark, docs | Acceptance suite and 1 GB performance evidence |

## 8. KPIs

| Metric | Launch target | 1-month target | Measurement |
|---|---:|---:|---|
| Processing time for a 1 GB valid log | <30 seconds | <30 seconds at p95 on reference laptop | Repeatable benchmark |
| Peak resident memory | <512 MiB on the defined representative fixture | No regression >10% | Benchmark measurement |
| Correctness | 100% acceptance fixtures pass | Zero known P0 correctness defects | Automated test suite |
| Pipeline compatibility | JSON and CSV contract tests pass | No breaking schema changes in 0.x without release note | Golden-output tests |
| Adoption | Publish installable package | 25 installs/stars combined | Package/repository counters |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx log formats vary | High | High | Support a documented combined/common-compatible grammar, clear malformed-line policy, and an explicit future custom-format boundary |
| High-cardinality IPs, URLs, or User-Agents grow memory | Medium | High | Document exact aggregation behavior, benchmark adversarial fixtures, and fail clearly on resource exhaustion |
| Python misses the 1 GB / 30 s target | Medium | High | Benchmark early, parse once, avoid regex backtracking and per-line object churn, profile before optimization |
| CSV cannot naturally represent multiple report tables | Medium | Medium | Define a normalized row schema with a `report` discriminator |
| Colored output behaves poorly in pipes | Low | Medium | Disable color when output is not a TTY and for JSON/CSV |
| Malformed or partially written lines skew results | Medium | Medium | Count and report skipped lines; strict mode is a post-MVP option |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Software and dependencies | $0 | Open-source stack |
| Infrastructure | $0 | Local CLI; no hosted runtime |
| Development | One weekend | Approved delivery constraint |
| Ongoing operations | $0 | No service or stored data |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin in one pass | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Core traffic/abuse signal |
| Top 10 URLs by 4xx/5xx errors | **Must** | Core failure signal |
| Hourly request distribution | **Must** | Core temporal signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal report | **Must** | Required default experience |
| JSON output | **Must** | Required machine-readable pipeline format |
| CSV output | **Must** | Required tabular pipeline format |
| Malformed-line accounting and useful exit codes | **Should** | Operational trust and diagnosability |
| Gzip input | **Could** | Convenient but not required for the first release |
| Custom nginx `log_format` definitions | **Could** | Broadens compatibility at significant parser cost |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly excluded and contrary to a local stateless CLI |

### RICE Scoring for Must and Should

Confidence is expressed as a fraction in the calculation.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input | 10 | 5 | 90% | 0.75 | 60.0 |
| Top client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL ranking | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 3 | 95% | 0.20 | 114.0 |
| Unique User-Agent share | 7 | 3 | 85% | 0.25 | 71.4 |
| Colored terminal output | 9 | 3 | 90% | 0.35 | 69.4 |
| JSON output | 8 | 4 | 95% | 0.25 | 121.6 |
| CSV output | 7 | 3 | 90% | 0.30 | 63.0 |
| Malformed-line and exit contracts | 8 | 4 | 90% | 0.40 | 72.0 |

Dependency order overrides raw score where a report depends on the parser. After the streaming foundation, implementation follows value and shared-risk order: error URLs, top IPs, JSON contract, hourly distribution, malformed-line handling, User-Agent share, terminal rendering, and CSV.

## 12. Definition of Done

A feature is done when:

- [ ] Behavior and acceptance criteria are implemented without breaking the frozen CLI/output contract.
- [ ] Unit and integration tests pass with at least 90% line coverage for parser, aggregation, and serialization modules.
- [ ] Representative common/combined logs and malformed lines are covered.
- [ ] JSON and CSV golden-contract tests pass.
- [ ] The reference 1 GB benchmark completes in under 30 seconds on the documented laptop with peak memory recorded.
- [ ] Static checks and code review pass with no known critical or high security issues.
- [ ] User-facing documentation and `--help` are current.
- [ ] The exact staged candidate passes the repository Verification Loop and has a current adjudication receipt.

## 13. Kill Criteria

Re-scope or stop the MVP if, after profiling and one focused optimization cycle, the reference 1 GB log cannot be processed in under 30 seconds; if exact metrics require unbounded memory beyond the documented laptop envelope; or if supporting real nginx logs requires a custom-format language incompatible with a one-weekend release.

## 14. Blueprint Completion Criteria

The planning unit is complete when the architecture, PRD, implementation plan, operator README, implementation guide, and project memory agree on scope, CLI behavior, performance, and verification. See `PROJECT_ARCHITECTURE.md`, `PRD.md`, and `IMPLEMENTATION_PLAN.md`.
