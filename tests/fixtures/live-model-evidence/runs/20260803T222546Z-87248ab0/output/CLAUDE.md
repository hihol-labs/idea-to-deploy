# Nginx Log Stats Project Memory

## Context

Build a local open-source Python 3.11 CLI for DevOps/SRE engineers that streams finite nginx combined access logs and reports top client IPs, top 4xx/5xx URLs, 24 hourly buckets, and exact unique User-Agent share. Default output is colored terminal text with JSON and CSV for pipelines. Cash budget is $0 and MVP delivery is one weekend.

The durable behavioral sources are `PRD.md` and `PROJECT_ARCHITECTURE.md`; the sequence and gates are in `IMPLEMENTATION_PLAN.md`. Update the spec before changing behavior.

## Non-Negotiable Rules

- No database, HTTP API, authentication, server, cloud, Docker, Kubernetes, telemetry, or retained state.
- Use Python 3.11, Click, Rich, dataclasses, a `src/` package, and pip-installable packaging.
- Consume binary physical lines incrementally and decode them independently; never load the whole log.
- Preserve exact metrics, the default 250,000 combined distinct-key guard, the 1 MiB line guard, deterministic ties, and codes `0..4`.
- Keep terminal formatting out of the report model and machine renderers; stdout is data and stderr is diagnostics.
- Treat log fields as untrusted. Prevent terminal-control/markup injection and document lossless CSV spreadsheet risk.
- Do not claim the 1 GB/<30 s and <=512 MiB target without a current representative benchmark receipt.
- Work one implementation step at a time (WIP=1). Failed/unrun evidence is recovery, not Done.
- Do not publish, push, deploy, or add P2 features without explicit authorization.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_log_stats/
  __init__.py       package version
  __main__.py       module entry point
  cli.py            Click contract and exit mapping
  input.py          binary physical-line ingestion
  parser.py         correctness-first combined parser
  fastpath.py       optional measured parser hot path
  models.py         dataclasses and renderer-neutral Report
  aggregate.py      exact guarded metrics
  errors.py         domain failure categories
  sanitize.py       untrusted terminal text boundary
  renderers/
    terminal.py
    json.py
    csv.py
tests/              unit, CLI, schema, adversarial, acceptance tests
benchmarks/         deterministic fixture and performance evidence tooling
scripts/            clean-wheel smoke verification
docs/               recorded benchmark context
```

`fastpath.py` is created only if Step 3 profiling justifies it. This tree is a plan, not evidence that files already exist.

## Commands and Gates

Canonical step-specific commands live in `IMPLEMENTATION_PLAN.md`. The final minimum checks are:

```bash
python3.11 -m pytest --cov=nginx_log_stats --cov-fail-under=90
python3.11 -m ruff check src tests benchmarks
python3.11 -m mypy src
python3.11 -m pip_audit
python3.11 -m build
sh scripts/smoke_wheel.sh dist/*.whl
python3.11 benchmarks/run_benchmark.py --input /tmp/nginx-1gb.log --manifest /tmp/nginx-1gb.manifest.json --max-seconds 30 --max-rss-mib 512
```

Also require the current Idea to Deploy exact-candidate adjudication receipt named by `.itd/VERIFICATION_CONTRACT.json`.

## Step Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package/models/fixtures | Not started | Install, unit/static checks, help/version |
| 2 | Binary parser/metrics | Not started | Parser/input/aggregation tests and static checks |
| 3 | Performance spike | Not started | Differential correctness, <30 s, <=512 MiB |
| 4 | CLI/exit codes | Not started | CLI/subprocess tests and smoke commands |
| 5 | Terminal renderer | Not started | Renderer snapshots and ANSI/control tests |
| 6 | JSON/CSV | Not started | Schema/golden/parser tests |
| 7 | Hardening | Not started | Acceptance/adversarial suite, >=90%, audit |
| 8 | Release candidate | Not started | Clean wheel plus full exact-candidate receipt |

## Current Status

Blueprint documentation is complete when all required root documents pass validation. Product implementation has not started. The next authorized action after blueprint approval is Step 1 only.

