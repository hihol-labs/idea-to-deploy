# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs from a file or standard input in one pass and reports the top client IPs, the URLs producing the most 4xx/5xx responses, hourly traffic distribution, and the share of unique User-Agents. It is designed for quick incident triage and pipeline-friendly reporting without operating a service or shipping logs off the laptop.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary before a full observability query is ready | One local command provides the four core summaries |
| Platform engineer | Maintains nginx fleets and shell pipelines | Ad hoc `awk` pipelines are brittle and difficult to reuse | Stable parsing and JSON/CSV contracts make automation repeatable |
| DevOps generalist | Supports small systems without an analytics stack | GoAccess or Elastic may be unavailable or excessive | A zero-service, pip-installable tool works offline |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature real-time terminal and HTML analytics | Broader configuration and presentation surface than a four-metric pipeline tool needs | Narrow, predictable CLI with first-class JSON and CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, and dashboards | Operational overhead, persistent infrastructure, and non-zero resource cost | No service, database, indexing, or deployment |
| AWStats | Established historical web analytics | Batch/report orientation and aging workflow; not ideal for fast shell pipelines | Streaming local triage with machine-readable output |
| `grep` / `awk` / `sort` | Available almost everywhere and composable | Quoting-sensitive parsing, repeated passes, weak malformed-line handling, platform variance | Tested nginx parsing, a single pass, explicit errors and exit codes |

## 4. Unique Value Proposition

Get the four nginx signals most useful during local incident triage from a gigabyte-scale log in one command, with no service to run and stable terminal, JSON, and CSV output.

## 5. Product and Distribution Model

- Open-source package, installable with `pip`.
- No paid tier, hosted service, telemetry, or data collection.
- Adoption goal: become a dependable local utility and reference-quality small CLI.
- License choice should be a permissive OSI-approved license such as MIT; confirm before publishing, not during implementation.

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required platform; broad SRE availability |
| CLI | Click | Reliable option parsing, help, streams, and exit handling |
| Terminal presentation | Rich | Readable tables and controlled color output |
| Domain models | `dataclasses` | Typed lightweight records without another runtime dependency |
| Processing | Standard-library streaming iterators and bounded top-k structures | Avoids loading the log into memory |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Test tooling | pytest | Focused unit, CLI, fixture, and performance-contract tests |

## 7. One-Weekend Timeline

| Block | Work | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, parser, input handling | Valid records stream from file/stdin; malformed input is classified |
| Saturday afternoon | Aggregation and cardinality guard | All four metrics compute in bounded operational memory |
| Sunday morning | Terminal, JSON, CSV, CLI and exit semantics | Stable human and pipeline interfaces |
| Sunday afternoon | Tests, 1 GB benchmark, docs, packaging | Release candidate with recorded evidence |

## 8. Success Metrics

| Metric | Release target | First month | Three months |
|---|---:|---:|---:|
| 1 GB processing time on the documented reference laptop | < 30 seconds | Maintain | Maintain |
| Valid-line parsing correctness on fixture corpus | 100% | 100% | 100% |
| Peak memory on 1 GB benchmark | <= 256 MiB, subject to unique-cardinality limit | Maintain | Maintain |
| Output-contract regression tests | 100% passing | 100% | 100% |
| Critical/high known security issues | 0 | 0 | 0 |
| External adoption | Not a release gate | 10 installs/stars combined | 50 installs/stars combined |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real-world nginx formats differ from combined format | High | Medium | State supported format, fail visibly, and keep parser isolated for later format templates |
| Exact unique User-Agent cardinality consumes excessive memory | Medium | High | Configurable hard limit and dedicated exit code 4 instead of silently approximating |
| Python misses the 1 GB / 30 s target | Medium | High | Benchmark early, avoid per-line regex recompilation and object retention, profile before optimization |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | Define one normalized row schema with a `section` discriminator |
| Malformed lines produce misleading summaries | Medium | High | Count invalid lines, expose them in output, and return code 3 under the strict malformed-input policy |
| Terminal color contaminates pipelines | Low | Medium | Rich console capability detection; `--json` and `--csv` never emit ANSI sequences |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Python, Click, Rich, pytest | $0 | Open-source ecosystem |
| Hosting and infrastructure | $0 | Local CLI only |
| CI | $0 | Optional free open-source allowance; local verification remains supported |
| Domain, database, monitoring | $0 | Not required |
| Delivery labor | One weekend | Time constraint, not cash spend |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format input from file or stdin | **Must** | Foundation for local and pipeline use |
| Top-10 client IPs | **Must** | Core traffic-abuse signal |
| Top-10 URLs by 4xx/5xx count | **Must** | Core failure signal |
| Hourly request percentage distribution | **Must** | Core traffic-shape signal |
| Unique User-Agent share with cardinality guard | **Must** | Required client-diversity signal without unbounded failure |
| Colored terminal, JSON, and CSV outputs | **Must** | Required interactive and pipeline interfaces |
| Strict malformed-line policy and exit contract | **Should** | Makes automation dependable; basic reporting can exist first |
| Gzip input | **Could** | Useful convenience but shell decompression already works |
| Configurable nginx log formats | **Could** | Broadens compatibility after the combined-format MVP |
| Authentication, database, HTTP API, cloud, Kubernetes | **Won't** | Contradicts a local stateless CLI and the $0/weekend constraints |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. They guide implementation order but do not weaken dependency ordering.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin input | 10 | 5 | 100% | 0.5 | 100.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL top-10 | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly percentage distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share and guard | 8 | 4 | 85% | 0.5 | 54.4 |
| Terminal/JSON/CSV output | 10 | 5 | 90% | 0.75 | 60.0 |
| Strict malformed-line and exit policy | 8 | 4 | 90% | 0.35 | 82.3 |

Recommended delivery sequence is dependency-aware: streaming parser first; the high-scoring core aggregations next; error policy, output contracts, and the higher-risk User-Agent guard integrated before release.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria agree with `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is formatted, type-checkable under the chosen tooling, and installs with pip.
- [ ] Unit and CLI tests pass; core parser and aggregation modules meet an agreed coverage floor of 90%.
- [ ] Integration fixtures cover valid, malformed, empty, Unicode, IPv6, and high-cardinality inputs.
- [ ] Terminal, JSON, and CSV output contracts have regression tests and contain no unintended ANSI escapes.
- [ ] The documented 1 GB benchmark completes under 30 seconds on the named reference laptop and records peak memory.
- [ ] Documentation is updated and no critical/high security issue is known.
- [ ] A local wheel install and smoke test pass; no staging deployment is applicable to this local-only CLI.

## 13. Release and Kill Criteria

Ship the MVP only if parsing correctness, all output contracts, exit semantics, pip installation, and the reference benchmark pass. Stop or revise the approach if profiling shows the required exact metrics cannot meet the 1 GB / 30 s target in Python 3.11, or if exact User-Agent cardinality cannot be bounded with an explicit safe failure. Do not add a service or persistent store to rescue the schedule; reconsider the metric or implementation instead.

