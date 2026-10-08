# Project Memory: nginx-log-insights

## Mission

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top-10 IPs, top-10 4xx/5xx URLs, hourly request percentages, and unique User-Agent share. Default output is colored terminal text; `--json` and `--csv` serve pipelines.

The current repository state is **blueprint only**. No product code has been implemented or verified.

## Source of Truth

Read these before product work, in order:

1. `PRD.md` — user-visible behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — system boundaries, algorithms, CLI/output/exit contracts.
3. `IMPLEMENTATION_PLAN.md` — dependency order, files, and verification commands.
4. `STRATEGIC_PLAN.md` — product boundary, priorities, performance goal, risks.
5. `CLAUDE_CODE_GUIDE.md` — session prompts; it may not override the documents above.

When documents conflict, stop implementation and reconcile the specification first. Architecture is authoritative for technical contracts; PRD is authoritative for product behavior.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, and standard-library dataclasses.
- A single local process, installed through pip.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Stream input line-by-line; do not retain raw records.
- Exact aggregates with a visible unique-value ceiling.
- Representative 1 GB input must complete in under 30 seconds on documented laptop hardware.
- Cash budget is $0 and P0 delivery is one weekend.
- The stable exit map is `0` success, `1` runtime/I/O, `2` usage, `3` parse quality, `4` unique-cardinality exhaustion.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.

## Engineering Rules

- Keep WIP at one `IMPLEMENTATION_PLAN.md` step.
- Write or expose a failing acceptance check before implementation, then make the smallest passing change.
- Keep domain models, parsing, aggregation, and rendering separated as documented.
- stdout is result data only; stderr is diagnostics only.
- Treat all log-derived strings as untrusted data, never Rich markup or executable content.
- Never weaken a test, performance fixture, ceiling, or acceptance criterion to claim success.
- Do not implement P1/P2 until all P0 release criteria have current evidence.
- Update specifications before changing contracted behavior.
- Do not create `DEVILS_ADVOCATE_REVIEW.md`; independent adversarial review belongs to the external harness.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Repository Structure

```text
src/nginx_log_insights/
  __init__.py
  __main__.py
  cli.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  conftest.py
  test_cli_contract.py
  test_models.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_end_to_end.py
  test_untrusted_output.py
benchmarks/
  generate_log.py
  run.sh
  README.md
pyproject.toml
```

This is a planned structure, not evidence that these paths exist.

## Verification Standard

A step is complete only when every verification command in that step has actually run against the current candidate and passed. The final candidate additionally requires the clean-wheel smoke test, full coverage/lint/type suite, all exit-code integration checks, and a reproducible three-run 1 GB benchmark whose median is below 30 seconds and peak RSS is at most 512 MiB.

Narration such as “should pass” is not evidence. Record failures as recovery work, not completion.

## Status

| Step | Description | State | Evidence |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete | Document presence and structural checks only |
| 1 | Package skeleton and contract tests | Not started | None |
| 2 | Domain models, errors, and fixtures | Not started | None |
| 3 | Combined-log parser | Not started | None |
| 4 | Exact aggregation and guards | Not started | None |
| 5 | Terminal/JSON/CSV renderers | Not started | None |
| 6 | Integrated CLI and exit codes | Not started | None |
| 7 | Quality and output safety | Not started | None |
| 8 | Performance benchmark | Not started | None |
| 9 | Packaging and release gate | Not started | None |

## Next Action

After the external architecture review is reconciled, begin only Step 1 using the corresponding prompt in `CLAUDE_CODE_GUIDE.md`.
