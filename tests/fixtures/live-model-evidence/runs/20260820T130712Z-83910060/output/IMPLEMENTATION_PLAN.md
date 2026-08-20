# Implementation Plan: Nginx Log Lens

This is a planning artifact only. Implementation follows the accepted design in
`PROJECT_ARCHITECTURE.md` and requirements in `PRD.md`. Estimated total focused
effort is 14–18 hours within one weekend.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package and pip console entry point | Every vertical slice needs an importable/installable boundary | 1 h |
| 2 | Immutable record/report dataclasses and typed errors | Parser, aggregator, renderers, and CLI need one shared contract | 1 h |
| 3 | Fixed fixtures and benchmark generator design | Correctness and performance must be measurable before feature work | 1 h |

No database schema, authentication system, API framework, Docker environment,
or deployment pipeline belongs in the runway. They are explicitly excluded by
the architecture.

## Exit-Code Contract for All Steps

Every implementation and test step must preserve the full contract:

| Code | Contract |
|---:|---|
| `0` | Successful complete report, including empty input |
| `1` | Runtime or input/output failure |
| `2` | Click usage error |
| `3` | Malformed non-empty log data; no report |
| `4` | Unique-cardinality exhaustion; no report |

Codes may not be omitted, remapped, or collapsed. In particular, code `4`
means exact unique User-Agent cardinality would exceed the configured ceiling.

## STEP 1: Package Skeleton and Domain Contracts

**Goal:** The project installs on Python 3.11, exposes `nginx-log-lens`, and has
typed domain models/errors without product behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Model”, “Data Model”,
“Packaging and Deployment”, and “Exit Codes”.

**Tasks:**

1. Create `pyproject.toml` with Python range, Click/Rich runtime dependencies,
   test extras, build backend, and console entry point.
2. Create `src/nginx_log_lens/__init__.py` with package version exposure.
3. Create `src/nginx_log_lens/models.py` with the five frozen dataclasses.
4. Create `src/nginx_log_lens/errors.py` with input, parse, and cardinality errors.
5. Create `src/nginx_log_lens/cli.py` with a minimal Click command and help/version.
6. Create `tests/test_models.py` and `tests/test_cli_contract.py` for construction,
   help, version, and the planned code mapping.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `nginx-log-lens --help`
- `python3.11 -m pytest tests/test_models.py tests/test_cli_contract.py -q`

**Commit:** `step-1: establish package and domain contracts`

## STEP 2: Streaming Input and Nginx Parser

**Goal:** File/stdin lines are decoded and parsed incrementally into exact
`AccessRecord` values for supported Common and Combined formats.

**Time:** ~3 hours

**Context:** Architecture sections “Input Contract”, “Parsing and Processing
Sequence”, and “Security and Privacy”; PRD FR-001 through FR-004.

**Tasks:**

1. Create `src/nginx_log_lens/input.py` for path/stdin ownership, strict UTF-8,
   streaming iteration, and the line-size guard.
2. Create `src/nginx_log_lens/parser.py` with precompiled Common/Combined grammar,
   request URL extraction, timestamp validation, and safe line-number errors.
3. Create `tests/fixtures/common.log`, `tests/fixtures/combined.log`, and
   `tests/fixtures/malformed.log` with non-sensitive synthetic data.
4. Create `tests/test_input.py` for stdin/file parity, strict decoding, and I/O errors.
5. Create `tests/test_parser.py` for valid, missing, quoted, boundary, and malformed cases.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_cli_contract.py -q`

**Commit:** `step-2: parse nginx streams safely`

## STEP 3: Error-URL and IP Rankings

**Goal:** One pass produces deterministic top-10 error URLs and top-10 client IPs.

**Time:** ~2 hours

**Context:** Architecture “Component Model” and “Performance and Resource
Budgets”; PRD FR-005 and FR-006. These are the highest-value metric slices after
their parser dependency.

**Tasks:**

1. Create `src/nginx_log_lens/aggregate.py` with total count, IP counter, and
   400–599 URL counter updates.
2. Implement final top-10 selection with descending count and ascending key ties.
3. Add `tests/test_aggregate_rankings.py` for status boundaries, missing URLs,
   fewer/more than ten values, and deterministic ties.
4. Extend `tests/test_cli_contract.py` to ensure aggregation errors never produce
   partial stdout and keep the `0/1/2/3/4` mapping.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate_rankings.py tests/test_cli_contract.py -q`

**Commit:** `step-3: aggregate deterministic top rankings`

## STEP 4: Hourly Distribution and User-Agent Diversity

**Goal:** The remaining metrics are exact, denominator-defined, and safely bounded.

**Time:** ~2 hours

**Context:** Architecture “Input Contract”, “Data Model”, and ADR-002; PRD
FR-007 through FR-009.

**Tasks:**

1. Extend `aggregate.py` with 24 local-hour buckets and calculate each percentage
   as `100 × hourly_request_count / total_valid_requests`.
2. Track non-missing User-Agent observations and exact unique strings.
3. Check the maximum before inserting a new unique value; raise the typed
   cardinality error mapped only to exit `4`.
4. Create `tests/test_aggregate_distribution.py` for empty input, hour offsets,
   denominator conservation, UA missing values, duplicates, exact limit, and exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate_distribution.py -q`
- `python3.11 -m pytest tests/test_aggregate_rankings.py -q`

**Commit:** `step-4: calculate distribution and bounded ua diversity`

## STEP 5: Terminal, JSON, and CSV Renderers

**Goal:** One immutable report produces accessible Rich output and stable
pipeline schemas without recomputation.

**Time:** ~3 hours

**Context:** Architecture “Output Contract”; PRD FR-010 through FR-013.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/__init__.py` defining renderer selection.
2. Create `renderers/terminal.py` with four ordered Rich sections, safe text,
   TTY detection, `NO_COLOR`, and explicit color override.
3. Create `renderers/json.py` with schema version 1 and 24 ordered hour objects.
4. Create `renderers/csv.py` with the long-form five-column RFC 4180 schema.
5. Create `tests/golden/report.json` and `tests/golden/report.csv` plus
   `tests/test_renderers.py` covering ordering, rounding, escaping, and no ANSI
   in machine output.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest tests/test_aggregate_distribution.py -q`

**Commit:** `step-5: render terminal and pipeline formats`

## STEP 6: Complete CLI Wiring and Failure Semantics

**Goal:** The installed command implements every option, input/output rule, and
exit code as an end-to-end unit.

**Time:** ~2 hours

**Context:** Exact architecture heading “CLI Interface”; PRD FR-014 through FR-016.

**Tasks:**

1. Complete `cli.py` option declarations, mutual exclusion, stream lifecycle,
   renderer selection, and safe stderr diagnostics.
2. Map success/runtime/usage/data/cardinality outcomes to `0/1/2/3/4` exactly.
3. Ensure aggregation completes before any report write so failures have empty stdout.
4. Create `tests/test_cli_integration.py` covering file/stdin, three output modes,
   empty input, every exit code, conflicting options, malformed data, and UA exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py -q`
- `nginx-log-lens --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-lens --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: enforce complete cli contract`

## STEP 7: Quality, Security, and Performance Acceptance

**Goal:** Correctness and the 1 GB/<30-second target have reproducible evidence.

**Time:** ~2 hours plus benchmark runtime

**Context:** Strategic “KPIs” and “Definition of Done”; architecture “Testing
Strategy” and “Performance and Resource Budgets”.

**Tasks:**

1. Create `tests/test_invariants.py` for count conservation, ranking determinism,
   and percentage properties.
2. Create `benchmarks/generate_access_log.py` to deterministically generate a
   representative bounded-cardinality fixture without checking it into Git.
3. Create `benchmarks/README.md` documenting fixture parameters, hardware fields,
   cache context, time/RSS commands, and the <30-second acceptance threshold.
4. Configure coverage and lint/type tools in `pyproject.toml` without adding runtime dependencies.
5. Run dependency and unsafe-output review focused on untrusted log strings.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_lens --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m ruff check src tests benchmarks`
- `python3.11 -m mypy src`
- `python3.11 benchmarks/generate_access_log.py --size-gib 1 --output /tmp/nginx-log-lens-1g.log`
- `/usr/bin/time -v nginx-log-lens --json /tmp/nginx-log-lens-1g.log >/dev/null`

The benchmark passes only when recorded wall time is under 30 seconds on the
declared reference laptop; another machine's result is informative, not a substitute.

**Commit:** `step-7: validate correctness and performance`

## STEP 8: Packaging and User Documentation

**Goal:** A clean Python 3.11 environment can build, install, understand, and run
the release candidate within the documented product boundary.

**Time:** ~2 hours

**Context:** Architecture “Packaging and Deployment”; `README.md`; all P0 PRD criteria.

**Tasks:**

1. Finalize `README.md` with install, examples, supported formats, exact metric
   definitions, schemas, limitations, and exit codes.
2. Add `LICENSE` using the chosen OSI-approved license and `CHANGELOG.md` for schema notes.
3. Validate wheel/sdist contents and console entry point in a clean environment.
4. Reconcile every P0 criterion and update the implementation status in `CLAUDE.md`.
5. Freeze the exact staged candidate and run the `.itd/` verification-loop oracle
   and risk-tier checker required by the repository contract.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest -q`
- `python3.11 -m venv /tmp/nginx-log-lens-verify && /tmp/nginx-log-lens-verify/bin/pip install dist/*.whl && /tmp/nginx-log-lens-verify/bin/nginx-log-lens --help`

**Commit:** `step-8: prepare installable documented release`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable foundation and correct streaming parser | 5 h |
| Saturday PM | 3–4 | Complete one-pass metric engine | 4 h |
| Sunday AM | 5–6 | Output formats and full CLI behavior | 5 h |
| Sunday PM | 7–8 | Evidence, packaging, and handoff | 4 h |

## Dependency and Scope Rules

- WIP remains one step at a time; a later step starts only after the prior
  verification commands pass or a recovery note is recorded.
- Product behavior changes begin in `PRD.md`, then architecture/plan, then code.
- Gzip input and malformed-line sampling are P1 follow-ons; top-N customization
  is P2. They do not delay the P0 release.
- No product code is considered complete from narration or a standalone test
  message; acceptance requires the repository's current exact-candidate receipt.
