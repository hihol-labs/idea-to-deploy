# Project Memory: nginx-stream-report

## Context

This repository plans a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams conventional nginx combined access logs and reports top-10 IPs, top-10 request targets producing 4xx/5xx responses, hourly request percentages, and distinct User-Agent share. Default output is Rich terminal text; JSON and CSV are pipeline formats.

The delivery constraint is one weekend at `$0`, with a representative 1 GB log processed in under 30 seconds on a documented laptop. Planning documents are the specification source; current blueprint work does not implement product code.

## Non-Negotiable Decisions

- One local single-process, synchronous streaming pipeline.
- Python 3.11, Click, Rich, dataclasses, pip packaging.
- No authentication, database, HTTP API/server, cloud, Docker, or Kubernetes.
- No persistence, telemetry, or network dependency.
- Exact metrics with deterministic ranking ties.
- Hourly percentage uses `100 × hourly_request_count / total_valid_requests`.
- The exit contract is complete and fixed: `0` success, `1` operational failure, `2` usage error, `3` data-quality failure or zero valid requests, `4` unique-cardinality exhaustion.
- Code 4 must not be omitted, remapped, or collapsed into another failure.
- Machine-readable output is written only after successful complete analysis; diagnostics go to stderr.

## Sources of Truth

1. `PRD.md` — user-visible behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — technical, CLI, schema, metric, and error decisions.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered delivery and verification commands.
4. `CLAUDE_CODE_GUIDE.md` — bounded prompts for future implementation sessions.
5. `STRATEGIC_PLAN.md` — scope, priorities, market position, risks, and Definition of Done.

If documents conflict, stop and reconcile them before product work. Change the spec before changing contracted behavior.

## Intended Repository Structure

```text
src/nginx_stream_report/
  __init__.py
  cli.py
  parser.py
  models.py
  aggregate.py
  renderers.py
  errors.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
scripts/generate_benchmark_log.py
docs/PERFORMANCE.md
pyproject.toml
```

Do not create this product structure during blueprint-only work.

## Engineering Rules

- Preserve WIP=1 and honor `.itd/` contracts plus `.itd-memory/` state when present.
- Do not mark work complete from narration; run the exact current verification and retain its evidence.
- Treat every log line and path as untrusted data. Never evaluate content or interpolate it into shell commands.
- Process input line by line and never retain all parsed entries.
- Check User-Agent cardinality before inserting beyond the configured limit; fail with exit 4 and no partial report.
- Rank by descending count, then ascending value.
- Keep Rich out of JSON/CSV serialization and keep diagnostics out of stdout.
- Keep fixtures small; generate the 1 GB synthetic benchmark locally and ignore it in Git.
- Do not publish packages or create remote releases without explicit authorization.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Step Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete | Root-document structural checks; no product code |
| 1 | Package and CLI contract | Not started | Step 1 commands in `IMPLEMENTATION_PLAN.md` |
| 2 | Models, errors, fixtures | Not started | Step 2 commands |
| 3 | Parser | Not started | Parser tests and branch coverage |
| 4 | Streaming accumulator | Not started | Aggregator tests and branch coverage |
| 5 | Renderers | Not started | Renderer semantic/snapshot tests |
| 6 | End-to-end CLI | Not started | Full CLI suite including exits 0/1/2/3/4 |
| 7 | Performance/resource gate | Not started | Recorded 1 GB wall time and peak RSS |
| 8 | Release candidate | Not started | Full suite, build checks, clean-wheel golden flows |

## Next Action

In a separately authorized implementation session, activate Step 1 only, reconcile the Idea to Deploy state/scope contract, and use Prompt 1 from `CLAUDE_CODE_GUIDE.md`. No implementation is authorized by this blueprint itself.
