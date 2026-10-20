# Claude Code Implementation Guide: nginx-log-report

## How to Use This Guide

Execute one step at a time in the order below. Before editing, read `PROJECT_ARCHITECTURE.md`, the relevant `IMPLEMENTATION_PLAN.md` step, and the P0 requirements in `PRD.md`. Do not implement P1/P2 work until every P0 verification passes. After each step, run its checks, update the status table in `CLAUDE.md`, and stop on a failing check rather than describing it as complete.

The public exit contract is immutable across all steps and renderers:

- `0`: successful complete report.
- `1`: unexpected internal/runtime failure.
- `2`: usage/configuration error.
- `3`: input/read/decode/parse failure, strict rejection, or no valid requests.
- `4`: unique-cardinality exhaustion.

Always test the complete `0/1/2/3/4` mapping. Never emit a partial report for code 3 or 4.

## Prompt 1 — Package Skeleton and CLI

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Create an installable Python 3.11 src-layout package using Click and Rich, with the nginx-log-report console entry point and all CLI options documented under PROJECT_ARCHITECTURE.md > CLI Interface. Do not add parsing or aggregation logic yet. Add focused tests for help, version, invalid --max-unique, and mutually exclusive --json/--csv. Run every Step 1 verification command and report actual results. Do not publish the package.
```

Expected files: `pyproject.toml`, `src/nginx_log_report/__init__.py`, `src/nginx_log_report/__main__.py`, `src/nginx_log_report/cli.py`, `tests/test_cli_contract.py`.

## Prompt 2 — Models and Exit Codes

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Add frozen renderer-neutral dataclasses and a single typed error-to-exit mapping. Preserve exactly: 0 success, 1 internal/runtime, 2 usage/configuration, 3 input/read/decode/parse or no valid records, 4 unique-cardinality exhaustion. Add tests that force all five outcomes without hiding unexpected exceptions. Run the step verification commands and update CLAUDE.md only after they pass.
```

Expected files: `src/nginx_log_report/model.py`, `src/nginx_log_report/errors.py`, updates to `cli.py`, and `tests/test_exit_codes.py`.

## Prompt 3 — Streaming Parser

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Read files and stdin incrementally and parse the exact nginx combined-log contract from PROJECT_ARCHITECTURE.md. Compile parsing machinery once. Support IPv4, IPv6, quoted fields, '-' placeholders, status validation, and timezone offsets. Return structured rejections containing source and line number, but never echo full log lines. Add audited fixtures and tests. Run parser coverage with branch coverage >=90%.
```

Expected files: `src/nginx_log_report/stream.py`, `src/nginx_log_report/parser.py`, `tests/fixtures/*.log`, `tests/test_parser.py`, `tests/test_stream.py`.

## Prompt 4 — Aggregations

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Build one-pass exact aggregations for top-10 IPs, top-10 request targets with 400-599 statuses, all 24 hour buckets, and exact unique nonempty User-Agent strings. Never retain raw records. Use deterministic count-descending/key-ascending tie-breaking. Define each hourly percentage exactly as 100 × hourly_request_count / total_valid_requests. Round only in renderers. Add unit tests for ties, zero-error input, all hour buckets, mixed timezone offsets, and the UA numerator/denominator contract.
```

Expected files: `src/nginx_log_report/aggregate.py` and `tests/test_aggregate.py`.

## Prompt 5 — Safety Limits and Strict Parsing

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Enforce --max-unique independently before inserting a new client IP, error URL, or nonempty User-Agent. Repeated keys at the limit must continue. Any over-limit dimension must emit a concise stderr diagnostic, leave stdout empty, and exit 4 for unique-cardinality exhaustion. Wire --strict so the first malformed line exits 3. Test limit boundaries and the full 0/1/2/3/4 contract.
```

Expected files: updates to `aggregate.py`, `cli.py`, `tests/test_cardinality.py`, and `tests/test_exit_codes.py`.

## Prompt 6 — Renderers

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Render the same Report dataclass through Rich terminal, deterministic JSON, and RFC 4180-compatible long-form CSV. Match the exact schemas in PROJECT_ARCHITECTURE.md. Keep diagnostics on stderr and machine output on stdout. Prove JSON and CSV contain no ANSI escapes and add golden tests. Do not duplicate calculations in renderers.
```

Expected files: `src/nginx_log_report/render/*.py`, `tests/golden/report.json`, `tests/golden/report.csv`, `tests/test_renderers.py`.

## Prompt 7 — Integration and Packaging Quality

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Add end-to-end tests for stdin, multiple files, all formats, strict/non-strict malformed lines, stderr separation, and exit codes 0/1/2/3/4. Configure Ruff, mypy, pytest coverage, and Python 3.11 CI. Build wheel and sdist and install the wheel into a clean temporary venv. Do not publish, deploy, push, or open a PR. Record only commands that actually ran.
```

Expected files: `tests/test_integration.py`, `.github/workflows/test.yml`, and configuration updates in `pyproject.toml`.

## Prompt 8 — Performance and Handoff

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Create a deterministic benchmark-log generator and runner. Generate a representative 1 GB fixture outside the repository, verify its lines parse, then measure wall time and peak RSS on the current laptop. The acceptance target is under 30 seconds for uncompressed local input within cardinality limits. Update README.md with the actual machine and result; do not invent measurements. Run the full quality suite and package checks. Do not publish or deploy.
```

Expected files: `bench/generate_log.py`, `bench/run.sh`, `tests/test_benchmark_contract.py`, `README.md`, and the status update in `CLAUDE.md`.

## Cross-Step Guardrails

- Keep the architecture single-process and stateless; do not add a database, HTTP API, daemon, Docker requirement, cloud service, authentication, or Kubernetes.
- Keep specs authoritative: update the relevant approved document before intentionally changing public behavior.
- Never hide malformed input or substitute approximate cardinality/top-K results.
- Never expose full log lines in errors, tests, CI logs, or benchmark reports.
- Do not run a 1 GB benchmark in the fast unit suite.
- Use a temporary directory for build/install tests and benchmark data.
- Ask for human approval before package publication, deployment, push/PR, deletion, or any other external/irreversible action.

## Final Verification Checklist

- [ ] `python3.11 -m pytest --cov=nginx_log_report --cov-branch --cov-fail-under=90`
- [ ] `python3.11 -m ruff check src tests`
- [ ] `python3.11 -m mypy src`
- [ ] `python3.11 -m build && python3.11 -m twine check dist/*`
- [ ] Clean-wheel install exposes `nginx-log-report --version`.
- [ ] Golden JSON and CSV parse and contain no ANSI escapes.
- [ ] Tests demonstrate exit codes `0/1/2/3/4`, including code 4 for unique-cardinality exhaustion.
- [ ] Documented 1 GB benchmark completes under 30 seconds on the recorded laptop profile.
- [ ] No product code or generated data is committed outside the planned paths.

If any item fails, leave the corresponding `CLAUDE.md` step in `Not started` or `Blocked` and record the next concrete action.
