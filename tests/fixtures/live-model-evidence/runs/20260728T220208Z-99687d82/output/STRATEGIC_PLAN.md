# Strategic Plan: Nginx Log Lens

## 1. Product Summary

Nginx Log Lens is a local, installable Python 3.11 command-line tool for
DevOps and SRE engineers. It reads nginx access logs as a stream and reports
the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly
request distribution, and the share of unique User-Agents. Rich terminal
output is the default; stable JSON and CSV formats support pipelines.

The MVP is open source, costs $0 to operate, and is scoped for one weekend.
It processes local files or standard input without uploading or persisting
log data.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses production incidents | Needs a useful traffic/error summary in seconds without starting a service | One local command, streaming analysis, readable terminal report |
| DevOps engineer | Builds shell and CI workflows | Ad hoc grep/awk scripts are brittle and hard to consume | Stable `--json` and `--csv` contracts with meaningful exit codes |
| Platform engineer | Reviews large archived logs | GUI stacks are too expensive and heavyweight for one-off analysis | Bounded-memory processing with a 1 GB / 30-second target |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive dashboards | More features and presentation modes than a small pipeline command needs | Narrow metrics, predictable machine output, Python install |
| Logstash + Elastic + Kibana | Powerful ingestion, search, and visualization | Requires services, storage, configuration, and operational cost | Zero-service, zero-database, single-process analysis |
| AWStats | Established historical reporting | Report-generation workflow and dated UX; not pipeline-first | Immediate streaming terminal, JSON, and CSV output |
| grep/awk/sort | Ubiquitous and composable | Format-sensitive scripts, repeated scans, inconsistent metrics and errors | Tested parser, one pass, one documented output contract |

## 4. Unique Value Proposition

Obtain the four nginx incident metrics an SRE most often needs from a large
log in one local, pipeline-friendly command—without deploying or operating
anything.

## 5. Business and Distribution Model

- Open-source package distributed through PyPI and source releases.
- No paid tier, telemetry, hosted service, or infrastructure spend.
- Success is adoption and reliability, not revenue; CAC and LTV are therefore
  not applicable to the MVP.
- Maintenance is community/owner time, constrained to a small dependency and
  feature surface.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required, broadly available, fast enough with streaming I/O |
| CLI | Click | Mature option parsing, help, validation, and test utilities |
| Terminal UI | Rich | Color, tables, and automatic no-color handling |
| Domain models | `dataclasses` | Lightweight typed records with no persistence layer |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |
| Tests | pytest + Click `CliRunner` | Fast parser, aggregation, and end-to-end CLI coverage |

## 7. Timeline

| Block | Outcome | Budget |
|---|---|---|
| Saturday morning | Package skeleton, CLI contract, parser fixtures | 3 hours |
| Saturday afternoon | Streaming aggregations and output-neutral report model | 4 hours |
| Sunday morning | Rich, JSON, and CSV renderers; errors and exit codes | 4 hours |
| Sunday afternoon | Performance validation, docs, packaging, release check | 4 hours |

Total target effort: approximately 15 hours in one weekend.

## 8. KPIs

| Metric | Launch target | 1-month target | 3-month target |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s |
| Peak resident memory on 1 GB reference log | <256 MB | <256 MB | <192 MB |
| Valid combined-log lines parsed | ≥99.9% | ≥99.9% | ≥99.95% |
| Unhandled exceptions on malformed input | 0 | 0 | 0 |
| Output contract golden tests | 100% pass | 100% pass | 100% pass |

Performance claims must always name the hardware, storage, fixture hash, and
command used; no universal laptop guarantee is implied.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the default combined format | High | High | Document the accepted grammar, count malformed lines, add a later configurable format option |
| Exact top-10 counts require memory proportional to distinct IPs/URLs | Medium | High | Document the bound, measure high-cardinality fixtures, fail cleanly on resource exhaustion |
| Python misses the 1 GB / 30-second target | Medium | High | Avoid regex backtracking and per-line Rich work; benchmark early; profile before optimizing |
| CSV cannot naturally represent four differently shaped reports | Medium | Medium | Define a normalized long-form schema with `section`, `key`, `count`, and metric fields |
| Color or diagnostics corrupt pipeline output | Low | High | Auto-disable color for non-TTY; write diagnostics only to stderr; golden-test stdout |
| User-Agent “share” is misunderstood | Medium | Medium | Define it precisely as distinct non-empty UA strings divided by valid requests |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and dependencies are open source |
| Hosting/database/cloud | $0 | None used |
| Distribution | $0 | PyPI and source hosting |
| Development | $0 cash | One weekend of owner time |
| Ongoing operations | $0 | Local CLI; no managed runtime |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file and stdin without loading all bytes | **Must** | Core local and pipeline workflow |
| Parse nginx combined access-log records and report malformed count | **Must** | All metrics depend on safe parsing |
| Top 10 IPs | **Must** | Required product outcome |
| Top 10 error URLs for 4xx/5xx | **Must** | Required incident outcome |
| Hourly request distribution | **Must** | Required traffic outcome |
| Unique User-Agent share | **Must** | Required client-diversity outcome |
| Rich colored terminal renderer | **Must** | Required default experience |
| JSON renderer | **Must** | Required pipeline contract |
| CSV renderer | **Must** | Required pipeline contract |
| gzip input auto-detection | **Should** | Common archive workflow, but not needed for launch |
| Custom nginx `log_format` grammar | **Should** | Broadens compatibility after the default is stable |
| Configurable top-N | **Could** | Useful flexibility but the product contract says top 10 |
| Live periodically refreshed display | **Could** | Helpful for `tail -f`, but complicates output and signals |
| Database, HTTP API, server, auth, cloud, Kubernetes | **Won't** | Contradicts local, stateless, $0 scope |

### RICE Scoring for Must and Should Features

Confidence is expressed as a fraction in the formula
`Reach × Impact × Confidence / Effort`.

| Feature group | Reach | Impact | Confidence | Effort (days) | RICE |
|---|---:|---:|---:|---:|---:|
| Streaming input + safe combined-log parsing | 10 | 5 | 90% | 1.0 | 45.0 |
| Required four metric aggregations | 10 | 5 | 90% | 1.5 | 30.0 |
| Stable JSON and CSV renderers | 8 | 4 | 90% | 0.75 | 38.4 |
| Rich terminal renderer | 9 | 3 | 90% | 0.5 | 48.6 |
| gzip input | 6 | 3 | 80% | 0.5 | 28.8 |
| Custom log-format grammar | 5 | 4 | 60% | 2.0 | 6.0 |

Implementation order also respects dependencies: parsing precedes metrics and
renderers despite the terminal renderer’s higher standalone score.

## 12. Definition of Done

A feature is done only when:

- [ ] Its behavior and output contract are reflected in `PRD.md`.
- [ ] Implementation targets Python 3.11 and installs through pip.
- [ ] Unit and CLI tests pass with at least 90% line coverage for product code.
- [ ] P0 acceptance and golden-output tests pass.
- [ ] The 1 GB performance fixture meets the documented <30-second target on
      the named reference laptop.
- [ ] Code review is accepted with no unresolved critical/high findings.
- [ ] User-facing documentation and `--help` are consistent.
- [ ] No network, persistence, authentication, server, cloud, or Kubernetes
      component has been introduced.

## 13. Kill Criteria

Stop or redesign the MVP if profiling shows the reference 1 GB log cannot be
processed under 30 seconds without changing the approved stack, if common
combined logs cannot be parsed reliably, or if exact high-cardinality
aggregation requires unacceptable laptop memory. Preserve benchmark evidence
before changing architecture.

## 14. Related Documents

The technical contract is in `PROJECT_ARCHITECTURE.md`; detailed behavior is
in `PRD.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`.
