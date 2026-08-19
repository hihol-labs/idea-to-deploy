# Strategic Plan: nginx-logtop

## 1. Product Idea

`nginx-logtop` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an immediately useful incident or traffic summary: the ten busiest client IPs, the ten request URLs producing the most 4xx/5xx responses, hourly request distribution, and the percentage of unique User-Agent values. Colored terminal output is the default; stable JSON and CSV formats make the same analysis usable in pipelines.

The product is deliberately narrow: one process, no retained state, no network service, and no infrastructure to operate. The first release is an open-source utility delivered in one weekend at a cash budget of $0.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE responding to an alert | Needs a fast traffic and error overview without uploading sensitive logs | Streams a local file or stdin and prints the four core summaries |
| Platform engineer | DevOps engineer maintaining nginx fleets | Repeats brittle `awk`, `sort`, and `uniq` pipelines | Provides a stable parser, metric definitions, and machine-readable output |
| Incident analyst | Engineer preparing a post-incident report | Needs reproducible results that can enter another tool | Exports deterministic JSON or tidy CSV with documented schemas |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | nginx-logtop differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports, broad log support | More functionality and presentation surface than a four-metric pipeline tool needs | Smaller CLI contract and purpose-built JSON/CSV output |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, and retention | Requires services, storage, configuration, and operating cost | Zero-service local analysis with no retained log data |
| AWStats | Established historical web analytics | Batch/report orientation and generated reports are less convenient during an incident | Streams directly to a concise terminal summary |
| `grep`/`awk`/`sort`/`uniq` | Ubiquitous and composable | Easy to misparse quoted fields; pipelines differ between engineers and often need large sorts | One tested parsing and metric contract across text, JSON, and CSV |

## 4. Unique Value Proposition

Get a reproducible nginx traffic and error snapshot from a local stream in one command, without deploying or operating an analytics stack.

## 5. Business Model and Distribution

- License: permissive open-source license.
- Distribution: Python package installable with `pip`/`pipx`.
- Price and infrastructure spend: $0.
- Monetization: none for MVP; adoption, trust, and maintainer sustainability matter more than revenue.
- Cost model: volunteer development over one weekend; CI should use free open-source-project allowances where available.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, productive for a weekend CLI |
| CLI | Click | Reliable option parsing, help, validation, and usage exit behavior |
| Terminal rendering | Rich | Readable colored tables with automatic no-color behavior when needed |
| Domain models | `dataclasses` | Explicit, lightweight records without a framework |
| Parsing and aggregation | Python standard library | Keeps dependencies and startup overhead low |
| Packaging | `pyproject.toml` with a console-script entry point | Standard `pip` installation and reproducible metadata |
| Verification | pytest plus benchmark fixtures | Unit, integration, format-contract, and performance checks |

## 7. Delivery Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, parser, domain records | Valid combined-log lines stream into typed records |
| Saturday afternoon | Aggregation and error/cardinality policy | All four metrics computed in one pass |
| Saturday evening | Text, JSON, and CSV renderers | Stable human and pipeline contracts |
| Sunday morning | CLI integration and failure semantics | stdin/files/options and exit codes `0/1/2/3/4` work end to end |
| Sunday afternoon | Tests, 1 GB benchmark, packaging docs | Installable release candidate with recorded evidence |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for the approved 1 GB fixture on the reference laptop | <30 s | <30 s | <25 s if profiling supports safe optimization |
| Peak resident memory for bounded-cardinality benchmark | <512 MiB | <512 MiB | <384 MiB target |
| Correct results on golden fixtures | 100% | 100% | 100% |
| Unhandled tracebacks for documented user errors | 0 | 0 | 0 |
| Install-to-first-report time | <2 min | <2 min | <1 min |

Performance claims are accepted only against a documented fixture, machine profile, command, wall-clock result, and peak-memory result.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex or token parsing accepts malformed quoting and silently corrupts metrics | Medium | High | Parse with a compiled, anchored grammar; keep golden malformed-line fixtures; count invalid lines |
| Exact unique User-Agent tracking consumes excessive memory on adversarial input | Medium | High | Enforce a configurable cardinality ceiling and exit with code `4`; never silently approximate |
| Python misses the 1 GB / 30 s target | Medium | High | Stream bytes/text once, avoid per-line allocations where practical, benchmark early, profile before optimization |
| Output schemas drift and break pipelines | Medium | High | Version and test JSON/CSV contracts; deterministic ordering and tie-break rules |
| Locale, timezone, or color behavior makes results non-reproducible | Low | Medium | Use timestamps from log records, locale-independent numeric formats, and explicit `--color/--no-color` behavior |
| Scope expands toward dashboards, storage, or multiple formats | Medium | Medium | Enforce the MoSCoW exclusions and CLI-only architecture decision |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and dependencies | $0 | Python and selected libraries are open source |
| Hosting / database / cloud | $0 | None exists in the architecture |
| Development tools | $0 | Local and open-source tooling |
| Distribution | $0 | Source repository and package index publishing |
| Labor | One weekend | Owner-contributed time; no cash expenditure |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx access logs from files and stdin | **Must** | The product has no value without local streaming input |
| Top-10 client IPs | **Must** | Core incident summary requested by users |
| Top-10 4xx/5xx URLs | **Must** | Core error-triage summary requested by users |
| Hourly request distribution | **Must** | Core traffic-shape summary requested by users |
| Unique User-Agent share | **Must** | Core client-diversity summary requested by users |
| Colored terminal report | **Must** | Required default interaction |
| JSON and CSV pipeline output | **Must** | Required automation interface |
| Explicit malformed-line and cardinality failure policy | **Must** | Prevents plausible but misleading reports |
| Gzip input | **Should** | Common operational convenience, but shell decompression is an MVP fallback |
| Additional nginx `log_format` definitions | **Could** | Useful later but increases parser and CLI complexity |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly excluded and contrary to local stateless operation |
| Interactive dashboards or retained history | **Won't** | Existing products already serve this broader use case |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. Equal scores are ordered by dependency and risk reduction.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin plus parser | 10 | 5 | 90% | 0.6 | 75.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share and exhaustion guard | 8 | 4 | 80% | 0.4 | 64.0 |
| Colored terminal report | 9 | 3 | 90% | 0.35 | 69.4 |
| JSON and CSV output | 8 | 4 | 90% | 0.5 | 57.6 |
| Malformed-input and exit-code contract | 10 | 5 | 90% | 0.45 | 100.0 |
| Gzip input | 5 | 2 | 75% | 0.3 | 25.0 |

Implementation order adjusts raw RICE rank for dependencies: parsing precedes every metric, and the failure contract is built alongside parsing and aggregation rather than deferred.

## Definition of Done

A release feature is done only when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is formatted, linted, type-checked at the agreed boundary, and contains no unhandled documented errors.
- [ ] Unit and integration tests pass with at least 90% line coverage for parser, aggregation, and renderer modules.
- [ ] Golden output tests pass for terminal-without-ANSI, JSON, and CSV.
- [ ] The complete exit-code contract `0/1/2/3/4` is tested, including code `4` for unique-cardinality exhaustion.
- [ ] The approved 1 GB benchmark completes in under 30 seconds on the documented reference laptop.
- [ ] Installation in a clean Python 3.11 virtual environment and a manual sample-log run succeed.
- [ ] README and CLI help match actual behavior.
- [ ] No known Critical or High security issue remains.
- [ ] Review and exact-candidate verification evidence required by the Idea to Deploy project contract is current.

## Strategic Kill Criteria

Re-scope or stop the MVP if a representative 1 GB stream cannot meet 30 seconds after profiling, if exact User-Agent cardinality cannot be bounded with an explicit failure contract, or if the interface requires storage/service infrastructure to provide the promised four summaries. Do not hide a failed premise with approximation or undeclared scope expansion.
