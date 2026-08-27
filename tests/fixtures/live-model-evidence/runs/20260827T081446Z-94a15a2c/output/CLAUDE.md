# Project Memory: nginx Stream Analytics CLI

## Project Context

This repository is planned as a local Python 3.11 CLI for DevOps and SRE
engineers. It reads nginx common/combined access logs from a file or stdin and
reports top-10 IPs, top-10 request targets with 4xx/5xx responses, 24 hourly
request percentages, and exact unique User-Agent share. Default output is Rich
terminal text; JSON and CSV are stable pipeline interfaces.

This blueprint contains specifications only. Product implementation has not
started. Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and
`IMPLEMENTATION_PLAN.md` before changing product behavior.

## Non-negotiable Decisions

- Use Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- Use one local process and one streaming pass; do not retain raw input.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- No telemetry or network calls; input remains local and source files are
  read-only.
- Hourly percentage is
  `100 × hourly_request_count / total_valid_requests`, not an unscaled ratio.
- JSON, CSV, and terminal output must derive from the same report dataclass.
- Preserve exit codes: `0` success; `1` unexpected/runtime failure; `2` usage
  error; `3` input/decoding/strict malformed-line failure; `4`
  unique-cardinality exhaustion.
- Never silently approximate exact User-Agent cardinality.
- Do not claim the performance target without a real, documented benchmark.

## Source-of-Truth Order

1. `PRD.md` — product behavior, priorities, and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — component, metric, schema, CLI, and failure
   contracts.
3. `IMPLEMENTATION_PLAN.md` — nine dependency-ordered delivery steps.
4. `STRATEGIC_PLAN.md` — audience, alternatives, roadmap, budget, and risks.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for executing one step at a time.

If documents conflict, stop and reconcile the PRD and architecture before
editing code. A behavior change starts in the specification.

## Planned Repository Structure

```text
src/nginx_stream_analytics/
  __init__.py
  cli.py
  models.py
  errors.py
  input.py
  parser.py
  aggregate.py
  render/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
benchmarks/
pyproject.toml
```

These paths are planned, not evidence that implementation files currently
exist.

## Engineering Rules

- Preserve WIP=1: implement and verify only one numbered plan step at a time.
- Before editing, read the relevant PRD acceptance criteria and architecture
  sections and inspect the working tree.
- Keep parsing, aggregation, rendering, and Click orchestration separated.
- Treat all log fields as untrusted data; never pass them to a shell or render
  terminal control sequences unsafely.
- Keep diagnostics on stderr and report content on stdout.
- Add tests with each behavior; do not weaken or delete a gate to get green.
- Run the exact per-step verification commands and report observed results.
- A benchmark or test not run is unverified, never assumed passing.
- Do not commit generated 1 GB fixtures or user access logs.
- Keep dependencies minimal and explain any addition against the weekend and
  $0 constraints.
- Do not create `DEVILS_ADVOCATE_REVIEW.md`; the external harness owns the
  separate fresh-session adversarial review.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Step Status

| Step | Scope | Status | Evidence required |
|---:|---|---|---|
| 1 | Installable CLI skeleton | Not started | Install, CLI contract tests, help output |
| 2 | Models, errors, fixtures | Not started | Model/error tests and compile check |
| 3 | Streaming input and parser | Not started | Input/parser tests including lazy read |
| 4 | Rankings and hourly percentages | Not started | Hand-checked aggregate tests |
| 5 | User-Agent cardinality | Not started | Cap and share boundary tests |
| 6 | Text, JSON, CSV renderers | Not started | Renderer and golden-output tests |
| 7 | CLI integration and exits | Not started | Integration evidence for `0/1/2/3/4` |
| 8 | Correctness, safety, performance | Not started | Full suite plus real benchmark record |
| 9 | Packaging and release docs | Not started | Build, clean install, and smoke test |

Update a row only when its named evidence has actually been produced. Planning
completion does not change implementation rows to complete.

## Current Handoff

- Lifecycle: Full blueprint documentation.
- Product code: not implemented.
- Next authorized action: begin Step 1 only, after the user requests
  implementation.
- External adversarial review: not run in this session and not represented by
  any local artifact.

