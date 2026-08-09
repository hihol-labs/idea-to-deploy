# Strategic Plan: StreamSift

## 1. Product Idea

StreamSift is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access-log records as a stream and produces four immediately useful views: the top 10 client IPs, the top 10 URLs returning 4xx/5xx responses, hourly request distribution, and the percentage share of distinct User-Agent values. Rich, colored terminal output is the default; JSON and CSV provide stable pipeline interfaces.

The product solves a narrow incident-response problem: obtain a useful traffic and error summary from a large log without deploying a service, uploading potentially sensitive logs, maintaining a database, or composing fragile one-off shell pipelines.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE/operations responder | Needs a first-pass view of a large log during an incident | One command yields traffic, error, time, and client-diversity signals |
| Platform engineer | DevOps/tooling owner | Needs deterministic output inside shell pipelines | `--json` and `--csv` provide machine-readable results and explicit exit codes |
| Application operator | Developer responsible for nginx-backed systems | Has no analytics stack on a laptop or restricted host | Local, stateless processing requires only Python and a readable file/stdin |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | StreamSift differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Larger feature surface and report model than a four-metric pipeline tool needs | Small, predictable CLI/output contract and Python installation |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, storage, search, dashboards | Operationally heavy, persistent, and incompatible with a $0 local weekend tool | No services, database, cluster, or ongoing operations |
| AWStats | Established historical web-log reporting | Configuration and batch-report orientation; less natural for stdin pipelines | Immediate streaming summary with JSON/CSV modes |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Parsing and quoting are fragile; repeated sorting can consume memory/disk; output contracts vary | Tested nginx parsing, bounded aggregations, consistent metrics and exit codes |

## 4. Unique Value Proposition

Turn a large nginx access log into the four highest-value operational summaries, locally and pipeline-safely, with one command and no infrastructure.

## 5. Business Model and Economics

The project is open source and free. There is no monetization, telemetry, hosted tier, or paid dependency in MVP. Value is measured as saved diagnosis time and reusable automation rather than revenue. Development is constrained to one weekend; ongoing infrastructure cost is $0 because execution is local and stateless.

## 6. Technology Strategy

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, productive for a weekend build |
| CLI | Click | Clear command/options contract and reliable usage errors |
| Terminal presentation | Rich | Colored tables, progress-safe console output, color policy |
| Data model | `dataclasses` | Lightweight typed records and result objects |
| Packaging | `pyproject.toml`, pip | Standard install and console-script entry point |
| Processing | Single process, line-by-line aggregation | Minimal operational complexity and bounded working memory |

## 7. Delivery Timeline

| Window | Work | Exit result |
|---|---|---|
| Saturday morning | Packaging, CLI contract, parser fixtures | Installable command parses representative combined logs |
| Saturday afternoon | Streaming aggregators and metric semantics | All four metrics computed in one pass |
| Sunday morning | Rich, JSON, and CSV renderers | Human and pipeline outputs satisfy stable schemas |
| Sunday afternoon | Error handling, performance, documentation | Verification suite passes; 1 GB target is measured |

## 8. Success Metrics

| Metric | Release target | Measurement |
|---|---|---|
| Performance | Process a representative 1 GB log in under 30 seconds on the reference laptop | Timed benchmark with machine and fixture-generation details recorded |
| Correctness | 100% of golden fixtures match expected counts, rankings, percentages, and exit codes | Automated unit/integration tests |
| Memory behavior | Memory scales with distinct aggregation keys, not total lines | Peak-memory benchmark comparing equal-cardinality inputs of different lengths |
| Pipeline stability | JSON parses; CSV has a documented schema; stdout contains no diagnostics | CLI integration tests |
| Adoption proxy | A new user can install and analyze a log in under 5 minutes | Clean-environment walkthrough |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Unbounded unique IP/URL/User-Agent cardinality exhausts memory | Medium | High | Configurable hard cardinality limit, deterministic exit code `4`, documented recovery |
| nginx formats differ from the supported grammar | High | Medium | Declare supported combined/common-derived format, count malformed lines, fail if no valid records |
| Python misses the 1 GB/30 s target | Medium | High | Avoid per-line regex recompilation and retained records; benchmark early; profile before optimization |
| Ties or rounding make pipeline results unstable | Medium | Medium | Specify secondary lexicographic ordering and numeric percentage precision |
| Colored diagnostics corrupt redirected output | Low | High | Separate stdout results from stderr diagnostics; disable color automatically when non-TTY |
| CSV representation of four heterogeneous result sets is ambiguous | Medium | Medium | Use a normalized row schema with a `metric` discriminator |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Development | $0 cash | One-weekend contributor time |
| Runtime infrastructure | $0 | Runs on the user's machine |
| Dependencies | $0 | Open-source Python packages |
| Distribution | $0 | Source repository and standard Python package tooling |
| Total MVP cash budget | **$0** | No paid services or licenses |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file or stdin without retaining records | **Must** | Core value and large-file constraint |
| Top 10 client IPs | **Must** | Immediate source concentration signal |
| Top 10 URLs by 4xx/5xx count | **Must** | Primary failure hotspot signal |
| Hourly request distribution percentage | **Must** | Shows temporal traffic concentration |
| Unique User-Agent share | **Must** | Shows client diversity/automation signal |
| Colored terminal report | **Must** | Approved default interface |
| JSON and CSV output | **Must** | Required pipeline interfaces |
| Stable `0/1/2/3/4` exit codes | **Must** | Required automation contract |
| Gzip input | **Should** | Common log-storage form, but decompression can be piped initially |
| Custom top-N value | **Could** | Useful polish; fixed top 10 meets MVP |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless product boundary |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence represented as a decimal. They order work within dependency constraints.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input | 10 | 5 | 90% | 1.0 | 45.0 |
| Stable exit-code/error contract | 10 | 4 | 90% | 0.5 | 72.0 |
| Top IP aggregation | 9 | 4 | 90% | 0.4 | 81.0 |
| Error URL aggregation | 10 | 5 | 90% | 0.5 | 90.0 |
| Hourly distribution | 8 | 4 | 90% | 0.4 | 72.0 |
| Unique User-Agent share | 8 | 3 | 80% | 0.4 | 48.0 |
| Rich terminal renderer | 9 | 3 | 90% | 0.6 | 40.5 |
| JSON and CSV renderers | 8 | 5 | 90% | 0.8 | 45.0 |
| Gzip input | 5 | 2 | 70% | 0.5 | 14.0 |

The implementation plan respects prerequisite order: CLI and parsing establish the contract before the independently scored aggregations and renderers.

## 12. Definition of Done

A release is done when:

- [ ] The package installs under Python 3.11 and exposes the documented console command.
- [ ] Unit and CLI integration tests pass with at least 90% branch coverage in parser, aggregation, and renderer modules.
- [ ] Golden fixtures prove all four metrics, malformed-line behavior, stable tie ordering, and `0/1/2/3/4` exits.
- [ ] JSON and CSV outputs validate against their documented schemas and diagnostics remain on stderr.
- [ ] A recorded reference-laptop benchmark processes a representative 1 GB log in under 30 seconds.
- [ ] Peak-memory evidence demonstrates no retention proportional to input line count and validates cardinality exhaustion behavior.
- [ ] Documentation matches `PROJECT_ARCHITECTURE.md`, `PRD.md`, and `IMPLEMENTATION_PLAN.md`.
- [ ] No known critical or high-severity dependency/security issue remains.
- [ ] A clean-environment manual smoke test succeeds.

## 13. Release and Kill Criteria

Release the MVP only if correctness, pipeline schema, and exit-code tests pass and the performance target is demonstrated. Re-scope or stop the MVP if a representative 1 GB supported-format file cannot meet 30 seconds after profiling and focused optimization, if bounded-cardinality handling cannot fail safely, or if pipeline formats cannot remain backward-compatible without adding persistent state.

