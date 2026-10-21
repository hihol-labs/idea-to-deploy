# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an immediately useful operational summary: top-10 client IPs, top-10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of unique User-Agents. It is deliberately local, stateless, and pipeline-friendly, with colored terminal output by default plus JSON and CSV modes.

The MVP is a $0 open-source utility delivered in one weekend. It does not provide authentication, a database, an HTTP API, a server process, cloud services, or Kubernetes support. The product and behavior contracts are detailed in [PRD.md](PRD.md); the technical design is in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Diagnoses incidents under time pressure | Needs a quick traffic/error picture without shipping logs elsewhere | One local command yields bounded top lists and distributions |
| DevOps engineer | Investigates hosts and deployment regressions | Existing observability stacks may be unavailable, slow to query, or excessive for ad hoc work | Streams files or stdin with no service setup |
| Platform engineer | Builds shell-based operational workflows | Human-only output is difficult to compose | Stable `--json` and `--csv` outputs plus documented exit codes |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Rich terminal/HTML nginx analytics | More features and presentation than a small pipeline primitive needs | Narrow report contract, JSON/CSV designed for composition, Python/pip delivery |
| Logstash + Elasticsearch + Kibana | Centralized ingestion, storage, search, dashboards | Operational cost, persistent infrastructure, and setup are disproportionate for local triage | Zero-service, stateless local analysis with a $0 runtime budget |
| AWStats | Persistent web-log reports | Batch-oriented, configuration-heavy, dated workflow for incident-time CLI use | Streaming input and immediate terminal output |
| `grep`/`awk`/`sort` | Universal ad hoc text processing | Commands are brittle, format assumptions are implicit, multiple metrics require repeated passes | One tested parser and one-pass aggregation with stable semantics |

## 4. Unique Value Proposition

Get a reliable, pipeline-ready nginx traffic and error summary from a large local log in one command, without deploying or operating anything.

## 5. Business Model

The project is free and open source. There is no monetization, paid tier, hosted dependency, CAC, or infrastructure bill in the MVP. Success is measured through usefulness, correctness, speed, and adoption rather than revenue. Contributions and issue reports provide the feedback loop.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required stack; broadly available and productive for a weekend CLI |
| CLI | Click | Mature argument parsing, validation, help, and exit handling |
| Terminal UI | Rich | Accessible colored tables and automatic terminal capability handling |
| Domain models | `dataclasses` | Typed records without a validation-framework dependency |
| Parsing/aggregation | Python standard library | Streaming iteration, regex/date parsing, counters, JSON, CSV |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Testing | pytest | Concise unit, integration, golden-output, and performance tests |

## 7. Timeline

| Window | Stage | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI and validated combined-log records |
| Saturday afternoon | Streaming aggregates | All four metrics calculated in one pass |
| Sunday morning | Text, JSON, CSV renderers | Stable human and machine output contracts |
| Sunday afternoon | Edge cases, benchmark, docs | Test suite, 1 GB performance evidence, release-ready documentation |

## 8. KPIs

| Metric | MVP target | First month | Third month |
|---|---:|---:|---:|
| Performance on a 1 GB representative log | Under 30 seconds on the reference laptop | Maintain under 30 seconds | No regression over 10% |
| Peak resident memory | Bounded independently of line count, excluding exact unique-UA state | Measured and documented | No regression over 10% |
| Parser correctness on supported combined-log fixtures | 100% expected records/fields | No open correctness defect | No open correctness defect |
| Automated test pass rate | 100% | 100% on supported Python 3.11 | 100% on supported Python 3.11 |
| Invalid-line visibility | Counted and reported; never silently treated as valid | Same | Same |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats deviate from the supported combined format | Medium | High | Declare the supported grammar; count malformed lines; return code `3` when no valid records remain |
| Exact unique User-Agent cardinality exhausts memory on adversarial input | Medium | High | Enforce a configurable safety ceiling and exit with code `4`; never silently approximate |
| Python misses the 1 GB/30 s target | Medium | High | Single pass, precompiled parser, bounded top-k inputs, benchmark early, profile before optimizing |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | Use a stable long-form schema with a `metric` discriminator |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for a terminal; JSON/CSV never contain ANSI escapes |
| Top-10 ties create nondeterministic output | Medium | Medium | Specify count descending, key ascending as the deterministic tie-break |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and dependencies | $0 | Python and dependencies are open source |
| Hosting/cloud/database | $0 | No deployed service or persistence |
| Development | One weekend | Owner-contributed time |
| Distribution | $0 | Source repository and optional public package index |
| Total cash budget | $0 | Hard product constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin in nginx combined-log format | Must | Core input path and prerequisite for every report |
| Top-10 client IPs | Must | Core traffic diagnostic |
| Top-10 URLs by combined 4xx/5xx count | Must | Core error diagnostic |
| Hourly request distribution | Must | Required traffic-shape metric |
| Unique User-Agent share | Must | Required client-diversity metric |
| Colored terminal report | Must | Required default experience |
| Stable JSON and CSV output | Must | Required pipeline integration |
| Malformed-line accounting and complete exit-code contract | Must | Required for trustworthy automation |
| Gzip-compressed file input | Should | Common log-rotation workflow, but plain files/stdin ship the MVP |
| User-configurable top-N | Could | Useful generalization after stable top-10 behavior |
| Additional nginx log-format configuration | Could | Broadens use but risks the weekend scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly excluded; conflicts with the local stateless purpose |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal in the calculation.

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin + parsing | 10 | 5 | 90% | 0.75 | 60.0 |
| Malformed-line handling + exit codes | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 9 | 5 | 95% | 0.40 | 106.9 |
| Hourly request distribution | 8 | 4 | 95% | 0.30 | 101.3 |
| Unique User-Agent share + safety ceiling | 8 | 4 | 85% | 0.50 | 54.4 |
| JSON output | 8 | 4 | 95% | 0.35 | 86.9 |
| CSV output | 6 | 3 | 90% | 0.30 | 54.0 |
| Colored terminal report | 8 | 3 | 95% | 0.40 | 57.0 |
| Gzip input | 5 | 2 | 90% | 0.30 | 30.0 |

Implementation order in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) respects dependencies first, then uses RICE to order independently deliverable behavior.

## 12. Definition of Done

A feature is Done when:

- [ ] Its PRD acceptance criteria are traceable to automated tests.
- [ ] Python 3.11 code passes formatting, linting, and type checks selected by the project.
- [ ] Unit and integration tests pass; core parser and aggregation logic reach at least 90% branch coverage.
- [ ] Machine-readable outputs pass schema/golden-output tests and contain no ANSI control sequences.
- [ ] The representative 1 GB benchmark completes under 30 seconds on the documented reference laptop.
- [ ] Documentation, CLI help, and the exit-code contract agree.
- [ ] No known critical or high-severity security issues remain.
- [ ] The package installs into a clean virtual environment and the console command runs.

## 13. Kill Criteria

Re-scope or stop the MVP if a single-pass Python implementation cannot meet the 1 GB/30 s target after profiling, if correct unique-cardinality behavior cannot be bounded with an explicit failure mode, or if supporting real logs requires an open-ended configurable parser. Do not add persistent infrastructure to conceal a failure of the local CLI premise.
