# Strategic Plan: Nginx Log Lens

## 1. Product Idea

Nginx Log Lens is a local, pip-installable Python 3.11 command-line tool for
DevOps and SRE engineers. It reads nginx access logs as a stream and emits four
operational views in one pass: top-10 client IPs, top-10 URLs producing 4xx or
5xx responses, hourly request distribution, and the share of unique
User-Agents. Rich terminal output is the default; stable JSON and CSV formats
support shell pipelines and automation.

The MVP is deliberately local and stateless. It has no service lifecycle,
authentication, database, HTTP API, cloud dependency, or Kubernetes footprint.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| Incident responder | On-call SRE | Needs an immediate traffic/error overview without shipping sensitive logs | Runs one local command and gets actionable rankings |
| Platform engineer | DevOps engineer | Needs repeatable metrics in scripts and CI jobs | Uses versioned JSON or CSV output and deterministic exit codes |
| Small-site operator | Developer/operator | Cannot justify operating a full observability stack | Installs a zero-service, zero-budget CLI with pip |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Nginx Log Lens distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a four-metric pipeline tool | Narrow contract, predictable machine output, Python packaging |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards | Operationally heavy; database/services, cost, and setup | No service or persistence; immediate local analysis |
| AWStats | Established historical reporting | Batch-oriented, dated workflow, persistent report artifacts | Streaming one-shot CLI designed for terminal and pipelines |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Fragile parsing, repeated passes, locale-dependent scripts | One-pass parsing, explicit semantics, tested output schemas |

## 4. Unique Value Proposition

Get the four nginx incident-triage metrics that matter from a local log stream
in one command, without deploying or operating anything.

## 5. Business Model

The project is open source and free. There is no monetization in the MVP;
success is measured by usefulness, correctness, and adoption. This matches the
$0 budget and avoids commercial infrastructure, telemetry, and account systems.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, widely available, strong text-streaming support |
| CLI | Click | Mature option parsing, help, validation, and exit behavior |
| Terminal UI | Rich | Accessible tables and automatic color/TTY handling |
| Domain models | `dataclasses` | Typed, lightweight records without framework coupling |
| Packaging | `pyproject.toml` + pip | Standard install path and console-script entry point |
| Tests | pytest | Fast unit/integration/performance-contract coverage |

See `PROJECT_ARCHITECTURE.md` for module boundaries and contracts.

## 7. Timeline

| Weekend block | Stage | Result |
|---|---|---|
| Saturday morning | Skeleton and parser | Installable CLI and validated nginx line parsing |
| Saturday afternoon | Aggregation | Four metrics computed in one streaming pass |
| Sunday morning | Renderers | Rich, JSON, and CSV output contracts |
| Sunday afternoon | Quality and packaging | Tests, benchmark evidence, docs, and release-ready wheel |

## 8. KPIs

| Metric | MVP target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing performance | 1 GB in <30 s on reference laptop | Maintain | Maintain |
| Valid-line result correctness | 100% on golden fixtures | No confirmed P0 defects | No confirmed P0 defects |
| Peak memory on 1 GB bounded-cardinality fixture | <512 MiB | Maintain | Maintain |
| Installation-to-first-report | <2 minutes | <2 minutes | <90 seconds |
| Machine-output schema stability | Version 1 documented | No breaking changes | No breaking changes |

The performance target must be measured with a documented reference laptop,
fixture characteristics, warm/cold-cache context, and wall-clock command.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from Common/Combined | High | High | Explicit supported grammar, `--input-format`, malformed-line diagnostics, fixtures |
| Exact high-cardinality tracking exhausts memory | Medium | High | Configurable hard ceiling and exit code `4`; benchmark representative cardinality |
| Python misses the 1 GB/30 s target | Medium | High | One pass, compiled regex, minimal allocations, early benchmark, profile before optimizing |
| Terminal/JSON/CSV metrics drift | Low | High | One immutable result model shared by all renderers; golden tests |
| CSV multi-section output surprises consumers | Medium | Medium | Stable long-form schema and documented `section` discriminator |
| Sensitive log values leak through diagnostics | Low | Medium | Report line numbers/reasons, not raw lines, by default |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Python and dependencies are open source |
| Runtime infrastructure | $0 | Local CLI; no hosted services |
| Distribution | $0 | Source and package build can use free tooling |
| Delivery effort | One weekend | Fixed scope; deferred features do not enter MVP |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming Common/Combined log parsing from file or stdin | **Must** | Foundation for every metric and pipeline use |
| Top-10 client IPs | **Must** | Core traffic triage view |
| Top-10 4xx/5xx URLs | **Must** | Core failure triage view |
| Hourly request percentages | **Must** | Core temporal view; percentage is `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share with cardinality guard | **Must** | Required diversity signal with bounded failure behavior |
| Rich terminal, JSON, and CSV renderers | **Must** | Human and pipeline output are both product requirements |
| Gzip-compressed input | **Should** | Common archive workflow, but decompression can be piped for MVP |
| Malformed-line sample report | **Should** | Improves format diagnosis without blocking valid input |
| Top-N customization | **Could** | Useful flexibility but conflicts with the intentionally fixed top-10 MVP |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless product boundary |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`; confidence is represented
as a decimal in the calculation. Ties are resolved by dependency order.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top-10 error URLs | 10 | 5 | 95% | 0.5 | 95.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.4 | 85.5 |
| Hourly request percentages | 8 | 3 | 95% | 0.3 | 76.0 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.5 | 51.2 |
| Streaming parser and input | 10 | 5 | 90% | 1.0 | 45.0 |
| Rich/JSON/CSV renderers | 10 | 5 | 90% | 1.0 | 45.0 |
| Malformed-line sample report | 6 | 2 | 80% | 0.4 | 24.0 |
| Gzip input | 5 | 2 | 80% | 0.4 | 20.0 |

Implementation remains dependency-aware: the parser precedes its higher-scored
consumers, after which feature order follows value and shared interfaces.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are represented in `PRD.md`.
- [ ] Python 3.11 code passes lint/type checks selected during implementation.
- [ ] Unit and integration tests pass with at least 90% line coverage overall.
- [ ] All output-format golden tests pass against the same result model.
- [ ] No known Critical or High security issues remain.
- [ ] User-facing documentation and `--help` are current.
- [ ] The exact staged candidate passes the repository verification loop and its risk-tier checker.
- [ ] The 1 GB benchmark meets <30 seconds on the documented reference laptop before release.

## 13. Kill Criteria

Stop or redesign the MVP if a representative 1 GB fixture cannot reach 30
seconds after profiling, exact unique-cardinality behavior cannot be bounded
with a clear failure contract, or supported-format parsing cannot achieve the
golden-fixture correctness target within the one-weekend budget.
