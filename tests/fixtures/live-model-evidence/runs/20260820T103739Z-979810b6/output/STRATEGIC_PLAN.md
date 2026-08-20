# Strategic Plan: nginx-report

## 1. Product Idea

`nginx-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE
engineers. It reads standard nginx combined access logs as a stream and emits
four operational summaries: the ten most active client IPs, the ten URLs with
the most 4xx/5xx responses, request distribution across the 24 hours of a day,
and the share of unique User-Agent values. The normal experience is a colored
Rich terminal report; stable JSON and CSV modes support scripts and pipelines.

The MVP is deliberately local and stateless. It does not authenticate users,
retain logs, expose a network service, or require infrastructure. Its core
promise is useful incident triage from a large log with one command.

## 2. Target Audience

| Persona | Role | Pain | How nginx-report helps |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs an immediate traffic/error overview without uploading sensitive logs | Produces four bounded summaries locally in one pass |
| Platform engineer | Maintains nginx fleets and shell automation | Ad hoc `awk` pipelines are fragile and inconsistent | Provides versioned JSON/CSV contracts and deterministic exit codes |
| DevOps engineer | Troubleshoots a service on a laptop or bastion | Full observability stacks are unavailable or excessive | Installs with pip and works with files or stdin at zero service cost |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | nginx-report differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive and HTML reporting | Broader UI/configuration surface than a four-metric pipeline tool | Smaller fixed report contract and first-class JSON/CSV pipeline output |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, setup, and operational budget | No server, database, or data upload; immediate local analysis |
| AWStats | Established historical web analytics | Oriented to configured, persisted reports rather than one-off terminal triage | One-command local streaming analysis with modern machine formats |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Quoting, malformed lines, status groups, and cross-platform behavior are easy to get wrong | Tested parser, explicit metric definitions, stable schemas and errors |

## 4. Unique Value Proposition

Get a reproducible nginx traffic-and-error snapshot from a gigabyte-scale log
in one local command, with human-friendly terminal output and pipeline-safe
JSON or CSV, without operating another service.

## 5. Business Model

The project is open source and free to use. There are no paid tiers, hosted
services, telemetry, or monetization in the MVP. Value is measured through
adoption, reliability, and reduced incident-triage time rather than revenue;
CAC and LTV are therefore not applicable. Maintenance is community-led under
an OSI-approved permissive license.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, mature standard library |
| CLI | Click | Predictable argument validation and exit behavior |
| Terminal UI | Rich | TTY-aware color and readable tables |
| Domain models | `dataclasses` | Typed records without a framework |
| Parsing/aggregation | Python standard library | Streaming I/O, regex/datetime, counters, JSON and CSV with no service dependencies |
| Packaging | `pyproject.toml` + pip | Standard install and console-script delivery |
| Quality | pytest, Ruff, mypy | Fast tests, linting, formatting, and type checks |

## 7. Timeline

| Weekend block | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable command and validated combined-log records |
| Saturday afternoon | Aggregation and metrics | One-pass exact summaries and cardinality guard |
| Sunday morning | Terminal, JSON, and CSV presenters | All approved output modes and exit codes |
| Sunday afternoon | Tests, 1 GB benchmark, docs, release check | Evidence against correctness and performance targets |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log on the reference laptop | < 30 s | < 30 s | < 25 s or documented hardware baseline |
| Peak resident memory on the representative 1 GB fixture | ≤ 512 MiB under documented cardinality assumptions | ≤ 512 MiB | ≤ 384 MiB if profiling supports it |
| Correctness of golden metric/output cases | 100% | 100% | 100% |
| Crash-free completion on valid supported inputs | 100% | ≥ 99.5% of reported runs | ≥ 99.9% of reported runs |
| Median time from install to first report in usability check | < 2 min | < 2 min | < 90 s |

Performance claims are accepted only on a documented laptop, Python version,
fixture generator, input cardinalities, elapsed-time method, and RSS method.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parser misses the 1 GB/30 s target | Medium | High | Benchmark early; compile parsing regex once; avoid per-line Rich/Click work; profile before optimizing |
| Exact IP/URL/User-Agent cardinality causes memory growth | Medium | High | Document assumptions, cap unique User-Agents, exit 4 before unsafe growth, measure RSS |
| Real nginx formats differ from the supported combined format | High | Medium | State the grammar precisely, count malformed lines, provide parse diagnostics, defer custom formats |
| CSV representation is misunderstood as four separate files | Medium | Medium | Define one normalized row schema with a `section` discriminator and golden fixtures |
| Corrupt or mixed logs silently distort reports | Medium | High | Count valid/invalid lines; exit 3 when none are valid; expose counts in every output mode |
| Weekend scope expands into tailing, storage, or dashboards | Medium | High | Enforce MoSCoW scope and explicit Won't list |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Open-source Python, Click, Rich |
| Hosting/database/cloud | $0 | None exists in the product |
| Development infrastructure | $0 | Local tools and public package index |
| Labor | One weekend | Personal/open-source contribution; no cash allocation |
| Total cash budget | **$0** | Fixed MVP constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream standard nginx combined logs from files and stdin | **Must** | Foundation for all value and bounded input memory |
| Top-10 client IPs | **Must** | Core traffic triage question |
| Top-10 4xx/5xx URLs with status-class counts | **Must** | Core failure triage question |
| Hourly request distribution as percentages | **Must** | Core load-shape view |
| Unique User-Agent share with cardinality guard | **Must** | Required client-diversity signal and controlled failure mode |
| Colored terminal, JSON, and CSV presenters | **Must** | Required interactive and pipeline interfaces |
| Gzip-compressed input | **Should** | Common operational convenience; plain files/stdin remain sufficient for MVP |
| Configurable result limit | **Could** | Useful beyond the required top ten, but expands the public contract |
| Custom nginx `log_format` parser | **Could** | Broadens adoption but cannot fit a one-weekend robust MVP |
| Database, auth, HTTP API, server, cloud, Kubernetes, dashboards | **Won't** | Explicitly conflicts with the local stateless CLI scope |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the formula.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Hourly percentage distribution | 8 | 4 | 95% | 0.4 | 76.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.5 | 68.4 |
| Top-10 error URLs | 10 | 5 | 95% | 0.75 | 63.3 |
| Stream files/stdin and parse combined logs | 10 | 5 | 90% | 1.0 | 45.0 |
| Gzip input | 6 | 2 | 80% | 0.25 | 38.4 |
| Terminal, JSON, and CSV presenters | 10 | 4 | 90% | 1.0 | 36.0 |
| Unique User-Agent share and cap | 7 | 3 | 85% | 0.5 | 35.7 |

Dependency order takes precedence over raw RICE: parsing comes first, then the
highest-scoring metrics, output modes, and finally the Should item.

## 12. Definition of Done

A feature is done only when:

- [ ] Its behavior and public contract match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Implementation is typed and installs on Python 3.11 through pip.
- [ ] Unit and integration tests pass with at least 90% line coverage for `src/`.
- [ ] Ruff and mypy pass without ignored new findings.
- [ ] P0 acceptance criteria and golden terminal/JSON/CSV cases pass.
- [ ] The documented 1 GB benchmark completes in under 30 seconds on the reference laptop.
- [ ] No known critical or high-severity security issue remains.
- [ ] README and CLI help reflect the behavior.
- [ ] A clean virtual-environment install and manual smoke test succeed locally.

No hosted staging deployment is required because this is an installable,
local-only CLI.

## 13. Release and Kill Criteria

Release the MVP only if all Must features and Definition of Done checks pass.
Stop or rescope the MVP if a representative 1 GB log cannot be processed under
30 seconds after profiling, exact metrics cannot remain within the documented
memory envelope, or supported-log parsing cannot be made deterministic within
the weekend. In that event, reduce supported input formats or document a lower
validated size; do not silently weaken correctness.
