# Strategic Plan: nginx-streamtop

## 1. Product Idea

`nginx-streamtop` is a local, pip-installable Python 3.11 CLI for DevOps and
SRE engineers. It reads nginx access logs as a stream and produces an
operational snapshot: top 10 client IPs, top 10 URLs producing 4xx/5xx
responses, hourly request distribution, and the percentage of distinct
User-Agent values. Rich colored terminal output is the default; JSON and CSV
make the same report usable in shell pipelines.

The MVP is deliberately local, stateless, and narrow. It turns a large log into
an immediately useful report without provisioning a server, datastore, or
observability platform.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Investigates production incidents | Needs a useful traffic/error summary before a dashboard is available | One command returns the highest-volume clients, erroring URLs, and time distribution |
| DevOps engineer | Operates small and medium nginx deployments | Full log stacks are expensive to run and maintain for an ad hoc question | Runs locally with no service, account, or persistent state |
| Platform developer | Automates diagnostics in CI or shell scripts | Colored, human-oriented tools are difficult to parse reliably | Stable `--json` and `--csv` output contracts support pipelines |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this job | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than the four required metrics | Smaller command contract and pipeline-first JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, storage, search, and visualization | Significant setup, resources, and operational cost for a one-off local report | No service or storage; starts immediately and costs $0 |
| AWStats | Established historical web analytics | Persistent, report-oriented workflow and dated operational UX | Streaming local analysis with modern terminal and machine formats |
| `grep`/`awk` pipelines | Ubiquitous and composable | Fragile parsing, repeated custom scripts, inconsistent output | Tested nginx parsing and one consistent multi-metric report |

## 4. Unique Value Proposition

Get the four nginx incident metrics an SRE usually computes first, from a
gigabyte-scale log, in one local command and in a format suitable for either a
human terminal or a pipeline.

## 5. Business Model

The project is free and open source. There are no paid tiers, telemetry, hosted
service, CAC, or revenue target. Value is measured through adoption,
reliability, and saved investigation time; maintenance is constrained to the
available volunteer budget.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable runtime with sufficient streaming I/O performance |
| CLI | Click | Stable command/option parsing and clear help/errors |
| Terminal rendering | Rich | Colored, readable tables with terminal capability handling |
| Domain models | `dataclasses` | Typed, lightweight report and record models without framework overhead |
| Packaging | pip-compatible `pyproject.toml` | Standard installation and console entry point |
| Testing | pytest | Focused parser, aggregation, formatting, and CLI contract tests |

## 7. Timeline

| Delivery window | Stage | Result |
|---|---|---|
| Saturday morning | Skeleton and contract | Installable CLI, fixtures, parser contract |
| Saturday afternoon | Streaming metrics | Single-pass aggregation of all four report groups |
| Sunday morning | Output formats | Rich terminal, JSON, and CSV with stable schemas |
| Sunday afternoon | Quality and performance | Tests, malformed-line policy, 1 GB benchmark, documentation |

The one-weekend boundary is a scope constraint: unfinished Should/Could items
are deferred rather than extending delivery.

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB reference-log processing time on documented laptop | <30 s | <25 s | <20 s |
| Correctness on maintained parser/aggregation fixtures | 100% | 100% | 100% |
| Peak memory on 1 GB bounded-cardinality reference log | <256 MB | <192 MB | <192 MB |
| Successful pip installs in supported Python 3.11 environment | 95% | 98% | 99% |
| Users reporting a useful first result in one command | 10 | 30 | 75 |

Performance claims are accepted only against a documented fixture profile,
hardware, command, elapsed time, and peak RSS.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx custom formats do not match the supported parser | High | High | Document the supported combined format; fail clearly; isolate parser for later format support |
| Exact cardinality of IP/URL/User-Agent values grows memory without bound | Medium | High | State the limitation, benchmark adversarial cardinality, and fail gracefully on resource exhaustion; consider opt-in approximate mode after MVP |
| Python misses the 1 GB/30 s target | Medium | High | Stream bytes/text once, precompile parsing, avoid per-line Rich work, benchmark early |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | Use a normalized row schema with a `section` discriminator and fixed columns |
| Malformed lines silently bias results | Medium | High | Count skipped lines, expose the count in every format, and define strict/non-strict behavior |
| Terminal colors leak into redirected output | Low | Medium | Enable color only for an interactive terminal unless explicitly forced |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and dependencies | $0 | Open-source Python, Click, and Rich |
| Infrastructure | $0 | Local execution; no hosted components |
| Distribution | $0 | Source repository and public Python package infrastructure |
| Development | $0 cash | One weekend of contributor time |
| Ongoing operations | $0 target | No server, database, or cloud account |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file or stdin without loading the whole log | **Must** | Core value and prerequisite for gigabyte-scale input |
| Parse the documented nginx combined access-log format | **Must** | Every metric depends on trustworthy field extraction |
| Top 10 client IPs by request count | **Must** | Required incident metric |
| Top 10 URLs by 4xx/5xx response count | **Must** | Required incident metric |
| Hourly request distribution | **Must** | Required traffic-shape metric |
| Share of unique User-Agent values | **Must** | Required client-diversity metric |
| Rich colored terminal report | **Must** | Required default experience |
| Stable JSON and CSV reports | **Must** | Required pipeline integration |
| Malformed-line count and strict mode | **Should** | Makes data quality visible; default tolerant processing can ship first |
| Distinct-key safety guard and stable resource-limit exit | **Should** | Prevents uncontrolled host degradation on pathological exact-cardinality input |
| Read `.gz` logs directly | **Could** | Useful convenience but not required for the approved MVP |
| Approximate high-cardinality aggregation | **Could** | Could cap memory on hostile data at the cost of exactness |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless CLI boundary |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin input | 10 | 5 | 100% | 0.5 | 100.0 |
| Combined-log parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Single-pass core metric aggregation | 10 | 5 | 90% | 1.0 | 45.0 |
| Rich terminal report | 9 | 3 | 90% | 0.5 | 48.6 |
| JSON output | 8 | 4 | 95% | 0.4 | 76.0 |
| CSV output | 7 | 4 | 90% | 0.4 | 63.0 |
| Malformed-line count and strict mode | 8 | 3 | 85% | 0.4 | 51.0 |
| Distinct-key safety guard | 7 | 4 | 80% | 0.4 | 56.0 |

Implementation ordering may place a lower-scoring prerequisite before a
higher-scoring dependent feature; within the same dependency layer, descending
RICE score determines order.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are documented in `PRD.md`.
- [ ] Code is written for Python 3.11 and the package builds without errors.
- [ ] Unit and CLI tests pass with at least 90% coverage of product modules.
- [ ] Relevant integration tests pass using representative nginx fixtures.
- [ ] Code review is accepted with no unresolved Critical or High findings.
- [ ] User-facing documentation and output schemas are updated.
- [ ] No known Critical or High security issue remains.
- [ ] Performance-sensitive changes are measured against the documented benchmark.
- [ ] The package is installed into a clean local environment and manually smoke-tested.

## 13. MVP Success and Kill Criteria

Proceed beyond the weekend MVP only if all P0 acceptance criteria pass and the
documented 1 GB benchmark completes in under 30 seconds. Re-scope or stop if
exact aggregation cannot meet the target on the reference laptop, common nginx
combined logs cannot be parsed reliably, or machine outputs cannot be kept
stable without compromising the terminal report.
