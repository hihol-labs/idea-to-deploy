# Strategic Plan: Nginx Log Lens

## 1. Idea

Nginx Log Lens is a local, pip-installable Python 3.11 CLI for DevOps and SRE
engineers. It reads an nginx access log as a stream and reports the top 10
client IPs, top 10 URLs producing 4xx/5xx responses, hourly request
distribution, and the proportion of distinct User-Agent values. Its default
output is colored terminal text, with JSON and CSV modes for pipelines.

The MVP is deliberately local and stateless: no authentication, persistence,
network service, cloud dependency, or cluster is needed. The delivery target
is one weekend, the software budget is $0, and the performance target is a
1 GB log processed in under 30 seconds on a representative laptop.

## 2. Target users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a useful traffic/error summary before opening a large observability stack | One command yields the four essential views |
| DevOps engineer | Service operator | Needs repeatable data in shell pipelines and reports | Stable JSON and CSV schemas plus meaningful exit codes |
| Platform engineer | Tooling maintainer | Avoids operating another server or datastore | Local pip package with streaming, bounded-memory processing |

## 3. Competitive analysis

| Alternative | Strength | Weakness for this use case | Nginx Log Lens difference |
|---|---|---|---|
| GoAccess | Fast, mature, rich interactive reports | Broader UI/configuration surface than a four-metric pipeline tool | Narrow contract, Python install, deterministic JSON/CSV |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, search, dashboards | Operational cost and setup are disproportionate for local triage | Zero-service, zero-database, one-command analysis |
| AWStats | Established historical web analytics | Oriented to persisted, generated reports rather than ad-hoc streams | Immediate terminal and machine-readable output |
| `grep`/`awk` pipelines | Ubiquitous and flexible | Fragile parsing, inconsistent outputs, hard to maintain | Tested nginx parsing and a versioned output contract |

## 4. Unique value proposition

Get the four nginx traffic signals most useful during local incident triage
from a gigabyte-scale log in one command, without deploying or operating
anything.

## 5. Business and distribution model

The project is open source and free to use. Distribution is through a public
pip-compatible package. There is no paid tier, CAC, or subscription unit
economics in the MVP; success is measured by utility, reliability, and
adoption. Maintenance is community/owner time and must remain compatible with
the $0 software and infrastructure budget.

## 6. Technology stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, productive for a weekend build |
| CLI | Click | Mature argument validation, help, exit handling |
| Terminal UI | Rich | Colored tables and terminal-aware output |
| Domain models | `dataclasses` | Explicit, dependency-free records and aggregates |
| Packaging | pip-compatible `pyproject.toml` | Standard install and console entry point |
| Processing | Single-pass iterators and bounded top-k structures | Low memory and no persistence |

## 7. Timeline

| Window | Stage | Deliverable |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable CLI skeleton and validated parsing fixtures |
| Saturday afternoon | Streaming aggregation | All four metrics computed in one pass |
| Sunday morning | Renderers | Rich text, JSON, and CSV output contracts |
| Sunday afternoon | Quality and release | Tests, 1 GB benchmark evidence, docs, package build |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <25 s | <20 s |
| Peak memory on 1 GB reference fixture | <250 MB | <200 MB | <150 MB |
| Valid common/combined log lines parsed | >=99.0% | >=99.5% | >=99.5% |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Documented user-reported successful uses | 5 | 20 | 50 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the assumed common/combined grammar | High | High | Make format explicit, test escaped/missing fields, count malformed lines |
| Exact unique User-Agent tracking grows with high-cardinality input | Medium | High | Document memory behavior, benchmark adversarial cardinality, add an opt-in approximate mode only after MVP if needed |
| Python misses the 30-second target | Medium | High | Profile a generated 1 GB fixture early; optimize parsing/hot loops before adding features |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | Define a normalized row schema with `report_type`, `key`, `value`, and `rank` |
| Terminal color contaminates pipelines | Low | Medium | Emit color only in text mode on a TTY; JSON/CSV never contain ANSI escapes |
| A malformed line aborts an incident-time analysis | Medium | Medium | Skip with a final malformed-line count; reserve nonzero exit for fatal input/output errors |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Development tools and libraries | $0 | $0 | Python and dependencies are open source |
| Hosting/database/cloud | $0 | $0 | None used |
| Package publication | $0 | $0 | Public package indexes and source hosting have free paths |
| Maintainer labor | One weekend | Best effort | Time contribution, not a cash expense |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream common/combined nginx logs from a file or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Core traffic/concentration signal |
| Top 10 URLs with 4xx/5xx responses | **Must** | Core failure-triage signal |
| Hourly request distribution | **Must** | Core time-distribution signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal report | **Must** | Required default experience |
| Stable `--json` and `--csv` output | **Must** | Required automation interface |
| Malformed-line count and clear diagnostics | **Should** | Preserves usefulness on imperfect logs |
| Configurable top-N | **Could** | Useful polish but top 10 is the approved requirement |
| Additional nginx/custom log formats | **Could** | Valuable after the base grammar is proven |
| Auth, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly out of scope and contrary to local stateless operation |

### RICE scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a
decimal. Ordering guides dependency-aware implementation, not independent
delivery of features that share the same aggregation pass.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE |
|---|---:|---:|---:|---:|---:|
| Streaming input and parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top 10 client IPs | 9 | 4 | 90% | 0.25 | 129.6 |
| Hourly distribution | 8 | 3 | 90% | 0.20 | 108.0 |
| Error URL top 10 | 10 | 5 | 90% | 0.50 | 90.0 |
| Colored terminal report | 8 | 3 | 90% | 0.30 | 72.0 |
| JSON output | 8 | 4 | 95% | 0.45 | 67.6 |
| Unique User-Agent share | 7 | 3 | 75% | 0.35 | 45.0 |
| CSV output | 6 | 3 | 90% | 0.45 | 36.0 |
| Malformed-line diagnostics | 7 | 3 | 85% | 0.50 | 35.7 |

## 12. Definition of Done

A feature is done when:

- [ ] Its PRD acceptance criteria have executable tests.
- [ ] Code runs on Python 3.11 and package build/install checks pass.
- [ ] Unit and integration tests pass with at least 90% line coverage for core parsing and aggregation modules.
- [ ] Static checks and code review pass with no unresolved high-severity findings.
- [ ] User-facing and output-schema documentation is current.
- [ ] No known Critical or High security issue remains.
- [ ] The full CLI is manually verified against file and stdin input.
- [ ] Performance claims have recorded runtime and peak-memory evidence on the reference 1 GB fixture.

## 13. Product completion and kill criteria

The MVP may be released only when all P0 stories in [PRD.md](PRD.md) pass,
the package installs in a clean Python 3.11 environment, JSON/CSV parse without
ANSI bytes, and the 1 GB benchmark is under 30 seconds. Re-scope or stop the
MVP if, after profiling and one optimization pass, the reference benchmark is
over 45 seconds, or exact User-Agent counting makes the agreed memory ceiling
unachievable without violating the stateless design.

