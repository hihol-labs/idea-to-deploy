# Nginx Log Lens Project Memory

## Context

Nginx Log Lens is a planned open-source Python 3.11 CLI for local streaming
analysis of nginx Common/Combined access logs. Its four outputs are top-10 IPs,
top-10 4xx/5xx URLs, hourly request percentages, and exact unique User-Agent
share. Default output is Rich; JSON and CSV serve pipelines. The delivery budget
is $0 and one weekend.

The specifications are source-of-truth assets:

1. `PRD.md` — behavior and acceptance.
2. `PROJECT_ARCHITECTURE.md` — technical and CLI contracts.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered work units.
4. `STRATEGIC_PLAN.md` — priorities, outcomes, risks, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for future implementation sessions.

## Non-Negotiable Rules

- Planning is complete; do not implement outside the active approved step.
- Preserve WIP=1 and reconcile `.itd/SCOPE_LOCK.md` before scope changes.
- Use Python 3.11, Click, Rich, dataclasses, a `src/` layout, and pip packaging.
- Keep a single-process streaming pipeline; never materialize the complete log.
- Do not add authentication, a database, HTTP API, server, cloud, Docker, or Kubernetes.
- Calculate hour percentage as `100 × hourly_request_count / total_valid_requests`.
- Treat log values as untrusted; escape/quote output and avoid raw-line diagnostics.
- Update PRD first for behavior changes, then architecture/plan, then code.
- Never claim completion from narration or a standalone passing test; require the
  current exact-candidate ITD adjudication receipt and its risk-tier checks.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Exit-Code Contract

Every future guide, implementation, test, help page, and README must retain:

| Code | Meaning |
|---:|---|
| `0` | Success, including empty input |
| `1` | Runtime or input/output failure |
| `2` | Click usage error |
| `3` | Malformed non-empty log data; no report |
| `4` | Unique-cardinality exhaustion; no report |

Code `4` is exclusively the exact User-Agent cardinality ceiling failure. No
failure may emit a partial terminal, JSON, or CSV report.

## Planned Repository Structure

```text
src/nginx_log_lens/
  __init__.py
  cli.py
  input.py
  parser.py
  aggregate.py
  models.py
  errors.py
  renderers/{__init__,terminal,json,csv}.py
tests/
  fixtures/
  golden/
benchmarks/
pyproject.toml
```

This tree is prospective. The blueprint session intentionally creates no
product code.

## Implementation Status

| Step | Scope | Status | Required evidence before advancing |
|---:|---|---|---|
| Blueprint | Six core documents plus project memory/handoff | Complete | Root-file and content validation |
| 1 | Package/domain contracts | Pending | Install, help, focused tests |
| 2 | Input/parser | Pending | Parser/input tests and regressions |
| 3 | Rankings | Pending | Ranking tests and CLI-contract regressions |
| 4 | Hour/UA metrics | Pending | Distribution/cardinality tests |
| 5 | Renderers | Pending | Golden renderer tests |
| 6 | CLI integration | Pending | End-to-end modes and codes `0/1/2/3/4` |
| 7 | Quality/performance | Pending | Coverage/lint/type plus measured 1 GB benchmark |
| 8 | Packaging/release | Pending | Build, clean install, full suite, current ITD receipt |

## Current Decisions

- Architecture: recommended single-process layered CLI (ADR-001).
- Persistence/API: none; local stream in, complete report out.
- Unique cardinality: exact set with default ceiling 1,000,000; exit `4` before overflow.
- Ranking: count descending, key ascending ties; fixed top 10 in MVP.
- Machine formats: JSON schema version 1 and long-form CSV.
- Adversarial review: intentionally deferred to the external harness; none ran
  during blueprint creation and no local review artifact should be invented.

## Next Action

Begin only `IMPLEMENTATION_PLAN.md` STEP 1 using Prompt 1 in
`CLAUDE_CODE_GUIDE.md`, after updating the active scope lock from documentation
to that bounded implementation unit.
