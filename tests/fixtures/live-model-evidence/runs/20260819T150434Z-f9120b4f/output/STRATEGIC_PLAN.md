# Strategic Plan: nginx-log-insights

## 1. Product Idea

`nginx-log-insights` is a local, pip-installable Python 3.11 command-line tool
for DevOps and SRE engineers. It reads nginx combined access logs as a stream
from a file or standard input and reports the top 10 client IPs, the top 10
URLs producing 4xx/5xx responses, hourly request distribution, and the share
of unique User-Agents. It is designed for fast incident triage without a
server, account, database, or ingestion pipeline.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE/operations | Needs a quick traffic and error picture during an incident | One command produces actionable terminal summaries |
| Platform engineer | DevOps | Needs repeatable analysis in shell automation | Stable JSON and CSV contracts work in pipelines |
| Service owner | Backend engineer | Needs to identify noisy clients and failing routes locally | Exact counts and deterministic top-10 ordering |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a focused pipeline tool | Small, explicit four-metric CLI contract with JSON/CSV |
| Logstash + Elastic + Kibana | Powerful retained search and dashboards | Requires services, storage, setup, and operational budget | Zero-service, local, stateless execution |
| AWStats | Established historical web analytics | Report-generation workflow and dated operational UX | Immediate streaming analysis with modern pipeline formats |
| `grep`/`awk` | Available almost everywhere and composable | Fragile parsing, difficult quoting, inconsistent metrics | Tested nginx combined-log parser and stable schema |

## 4. Unique Value Proposition

Get a deterministic nginx incident snapshot from a file or pipe in one local
command, with no infrastructure and with both human- and machine-readable
output.

## 5. Business Model

The project is open source and free. There is no monetization in the one-weekend
MVP; value is measured through adoption, reliability, and saved triage time.
There are no hosting or per-run costs, so conventional CAC/LTV assumptions do
not apply.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, strong text-processing ecosystem |
| CLI | Click | Mature option validation and predictable exit behavior |
| Terminal UI | Rich | Accessible colored tables and automatic non-TTY handling |
| Domain models | `dataclasses` | Lightweight typed records without an ORM |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Tests | pytest | Fast unit, CLI, fixture, and performance checks |

## 7. Timeline

| Block | Work | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, parser, record model | Valid combined-log records stream from file/stdin |
| Saturday afternoon | Aggregation and bounded-cardinality guard | All four metrics and deterministic ranking |
| Sunday morning | terminal/JSON/CSV renderers and CLI errors | Complete public CLI contract |
| Sunday afternoon | tests, benchmark, docs, packaging | Pip-installable release candidate |

## 8. KPIs

| Metric | Launch target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log on the reference laptop | <30 s | <30 s | <25 s |
| Peak resident memory on the bounded benchmark fixture | <512 MB | <512 MB | <384 MB |
| Correctness fixtures passing | 100% | 100% | 100% |
| Install-to-first-report time | <5 min | <3 min | <2 min |
| Critical/high known security issues | 0 | 0 | 0 |

The reference laptop, fixture generator, command, wall-clock measurement, and
peak-RSS measurement must be recorded with the benchmark result; the target is
not accepted from an estimate.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex parsing is too slow for 1 GB/30 s | Medium | High | Benchmark early; precompile parser; avoid per-line object churn in hot paths |
| High-cardinality inputs exhaust memory | Medium | High | Configurable hard limit; fail explicitly with exit code 4 |
| Custom nginx formats are mistaken for combined format | High | Medium | State MVP format clearly; count malformed lines; provide actionable diagnostics |
| CSV representation is ambiguous across metric types | Medium | Medium | One documented normalized schema with a `section` discriminator |
| Color corrupts redirected output | Low | Medium | Enable color only for terminal output; JSON/CSV never contain ANSI escapes |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 cash | One weekend of contributor time |
| Runtime/hosting | $0/month | Local CLI; no deployed service |
| Dependencies | $0 | Open-source Python packages |
| CI | $0 initially | Use a free open-source allowance or local checks |
| Total MVP cash budget | **$0** | No paid services or infrastructure |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from a file or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Core traffic-abuse signal |
| Top 10 URLs by 4xx/5xx count | **Must** | Core failure-triage signal |
| Hourly request percentage distribution | **Must** | Core temporal traffic signal |
| Unique User-Agent share | **Must** | Core client-diversity signal |
| Colored terminal output | **Must** | Approved default human interface |
| JSON output | **Must** | Required pipeline interface |
| CSV output | **Must** | Required pipeline interface |
| Malformed-line diagnostics and cardinality guard | **Should** | Operational safety; MVP can compute happy-path results without polish |
| Configurable top-N | **Could** | Useful extension after the fixed top-10 contract is stable |
| Common/custom nginx format support | **Could** | Broadens compatibility but increases parser scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly out of scope and contrary to local stateless operation |

### RICE Scoring (Must + Should)

Confidence is represented as a decimal in the formula
`Reach × Impact × Confidence / Effort`.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE |
|---|---:|---:|---:|---:|---:|
| Top 10 IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 3 | 95% | 0.25 | 91.2 |
| JSON output | 8 | 4 | 90% | 0.35 | 82.3 |
| Diagnostics and cardinality guard | 8 | 5 | 85% | 0.50 | 68.0 |
| Colored terminal output | 8 | 3 | 95% | 0.35 | 65.1 |
| Stream file/stdin and parse combined logs | 10 | 5 | 90% | 0.75 | 60.0 |
| Unique User-Agent share | 7 | 3 | 85% | 0.30 | 59.5 |
| CSV output | 6 | 3 | 90% | 0.30 | 54.0 |

Dependency order overrides raw RICE where necessary: parsing precedes every
metric, and metric models precede renderers.

## 12. Definition of Done

A feature is done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are implemented.
- [ ] Code runs on Python 3.11 and formatting/static checks pass.
- [ ] Unit and CLI tests pass with at least 90% line coverage for project code.
- [ ] The 1 GB benchmark is recorded and meets the <30-second target on the named reference laptop.
- [ ] JSON and CSV output contain no ANSI escape sequences and match their documented schemas.
- [ ] Documentation and `CLAUDE.md` status are updated.
- [ ] No known critical/high security issue remains.
- [ ] A review and the repository Verification Loop accept the exact candidate required by the active verification contract.

## 13. Success and Stop Conditions

Ship the MVP when all Must features and the performance target pass. Re-scope
before release if Python cannot meet the measured target after parser profiling,
or if exact aggregation cannot stay within the documented cardinality budget on
the representative fixture. Do not introduce a database or service to rescue
the one-weekend MVP; that would be a different product.
