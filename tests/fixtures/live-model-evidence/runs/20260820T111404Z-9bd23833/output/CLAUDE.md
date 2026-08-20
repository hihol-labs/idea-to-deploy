# Project Memory: Nginx Stream Analytics CLI

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams nginx common/combined access logs from a file or stdin and reports Top 10 IPs, Top 10 URLs by 4xx/5xx count, 24 hourly request percentages, and the share of unique User-Agents. Default output is colored Rich text; `--json` and `--csv` are stable pipeline formats.

The cash budget is $0 and delivery scope is one weekend. The performance acceptance target is a reproducibly generated 1 GB log in under 30 seconds on a documented reference laptop.

## Sources of Truth

Read these before implementation and keep them consistent:

1. `.itd/` contracts and `.itd-memory/` state — scope, WIP=1, verification, and current execution truth.
2. `PROJECT_ARCHITECTURE.md` — architecture, metric semantics, CLI, schemas, errors, and security boundaries.
3. `PRD.md` — user stories, P0/P1/P2 requirements, and release criteria.
4. `IMPLEMENTATION_PLAN.md` — the eight ordered units and their checks.
5. `STRATEGIC_PLAN.md` — product scope, priorities, KPIs, risks, and kill criteria.
6. `CLAUDE_CODE_GUIDE.md` — prompts for future step-by-step implementation.

When behavior changes, update the durable specification before or with code; do not let generated implementation become the only source of truth.

## Mandatory Engineering Rules

- Preserve WIP=1. Bind one active implementation unit in `.itd/SCOPE_LOCK.md`; do not start the next until current evidence and state are reconciled.
- Use the repository-local Idea to Deploy lifecycle skill appropriate to the task.
- For change work, freeze the exact candidate, run its declared oracle, apply the risk-tier checker, and accept only a current revalidated adjudication receipt.
- Do not claim completion from prose, a standalone pass message, or stale evidence.
- Use Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
- Keep the architecture a single local process with one streaming pass. Never retain all raw lines or parsed records.
- Do not introduce authentication, a database, HTTP API, server, network dependency, telemetry, cloud service, Docker runtime requirement, or Kubernetes.
- Keep the public outcome mapping exact: `0` successful complete report; `1` operational or internal failure; `2` CLI usage error; `3` input data or parse failure; `4` unique-cardinality exhaustion. Code 4 covers guarded IP, error-URL, and User-Agent distinct-key state and must not be collapsed or remapped.
- Calculate hourly percentages with the literal formula `100 × hourly_request_count / total_valid_requests`.
- Keep top-list ties deterministic: count descending, key ascending.
- Treat log fields as untrusted data. Do not shell-evaluate, fetch, dynamically import, or render them as Rich markup; do not echo full raw records in diagnostics.
- Keep report data on stdout and diagnostics on stderr. JSON and CSV must never contain ANSI escapes.
- Do not commit generated 1 GB benchmark data, virtual environments, build output, caches, secrets, or local logs.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Metric Snapshot

- Top IP: count every valid request; first 10.
- Top error URL: exact request target, only status 400–599; first 10.
- Hourly distribution: 24 entries; record's encoded timezone hour; `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share: `100 × unique_non_missing_user_agent_count / total_valid_requests`; common/missing User-Agent records remain in the denominator.
- Default malformed behavior: skip/count non-empty malformed lines and exit 0 if any valid record exists.
- Strict malformed behavior or zero-valid input: exit 3.
- Cardinality guard checked before insertion: exit 4 with no partial report.

## Planned Structure

```text
src/nginx_stream_analytics/
  __init__.py              package version
  __main__.py              module entrypoint
  cli.py                   Click and failure boundary
  models.py                dataclasses and typed failures
  parser.py                common/combined line parser
  aggregate.py             streaming counts and finalization
  reporters/
    __init__.py            reporter selection
    text.py                Rich terminal report
    json.py                JSON schema v1
    csv.py                 normalized CSV schema
tests/
  fixtures/                small deterministic logs
  unit/                    parser and aggregation tests
  integration/             CLI/report/exit-code tests
  acceptance/              PRD user-story tests
  performance/             memory-guard checks
  golden/                  deterministic expected outputs
benchmarks/
  generate_log.py          deterministic ignored data generator
  run.sh                   environment/time/RSS recorder
  RESULTS.md               measured reference evidence
pyproject.toml             Python package and console script
```

## Implementation Status

Blueprint completion does not mean product implementation has started.

| Step | Unit | Status | Required acceptance |
|---:|---|---|---|
| 1 | Package, contracts, harness | Not started | Import, console skeleton, test collection |
| 2 | Streaming parser | Not started | Parser unit suite and branch coverage |
| 3 | Exact streaming aggregation | Not started | Metric, tie, formula, and guard suite |
| 4 | CLI and failure boundary | Not started | Integration evidence for `0/1/2/3/4` |
| 5 | Text/JSON/CSV reporters | Not started | Golden and cross-format equivalence tests |
| 6 | Functional and safety acceptance | Not started | All P0 stories and coverage gate |
| 7 | Performance proof | Not started | Recorded 1 GB time/RSS and exit-4 evidence |
| 8 | Distribution readiness | Not started | Build, clean install, full suite, smoke tests |

## Current State and Next Action

Planning documents are present; no product code is implemented. The next authorized implementation action, when requested, is STEP 1 only. Before editing, establish the active unit in Idea to Deploy state, update `.itd/SCOPE_LOCK.md` to STEP 1 paths, and use the applicable implementation lifecycle skill.

## Definition of Ready for a Step

- Previous step is verified with current evidence, or this is STEP 1.
- Scope lock and state name exactly one active unit.
- Relevant PRD acceptance criteria and architecture sections are cited.
- Verification commands and expected evidence are executable and candidate-bound.
- No ignored/untracked overlay is treated as oracle input unless declared and content-bound.

## Definition of Complete Implementation

All eight units have current accepted evidence; P0 stories pass; coverage meets the plan; exact exit codes `0/1/2/3/4` are proven; text/JSON/CSV values agree; the standard 1 GB default-text run is under 30 seconds on the recorded laptop; high cardinality exits 4 safely; wheel/sdist clean-install smoke tests pass; durable state is reconciled; and the next action is explicit.
