# Implementation Plan: Nginx Log Stats

## Plan Contract

This is a planning artifact; it does not authorize product-code implementation in the current blueprint unit. Implementation follows one active step at a time (WIP=1). Each step begins by reconciling the spec and ends only with the listed verification evidence. If behavior changes, update [PRD.md](PRD.md) and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) before code.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python 3.11 `src/` package, test tooling, console entry point | Every vertical slice needs an installable/importable skeleton | 1 h |
| 2 | Golden combined-log corpus and expected report manifest | Parser and optimization require an independent correctness oracle | 1 h |
| 3 | Deterministic 1 GB fixture generator/manifest | The hard performance claim cannot wait until release | 1 h |
| 4 | Output schema fixtures | Prevents terminal concerns from leaking into JSON/CSV contracts | 0.5 h |

No database schema, authentication, API, container, or CI/CD infrastructure is part of the runway because the product is a local stateless CLI.

## Weekend Boundaries

| Session | Steps | Goal | Budget |
|---|---|---|---:|
| Saturday morning | 1–2 | Installable skeleton, trusted parser, exact metrics | 5 h |
| Saturday afternoon | 3–4 | Performance feasibility and complete CLI contract | 4 h |
| Sunday morning | 5–6 | Human and pipeline renderers | 3.5 h |
| Sunday afternoon | 7–8 | Adversarial hardening, wheel/release evidence | 3.5 h |

## Step 1: Establish Package, Models, and Reference Fixtures

**Goal:** A Python 3.11 package installs locally, the CLI help/version entry point runs, and golden fixtures define accepted/rejected combined-format behavior without implementing analytics yet.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Architecture Summary, Component Design, Processing and Data Model, Packaging and Deployment; `PRD.md` FR-1, FR-2, NFR-4.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11`, Click/Rich runtime constraints, development groups, `src` package discovery, and the `nginx-log-stats` entry point.
2. Create `src/nginx_log_stats/__init__.py`, `src/nginx_log_stats/__main__.py`, and `src/nginx_log_stats/cli.py` with help/version-only skeleton behavior.
3. Create `src/nginx_log_stats/models.py` with immutable `AccessRecord`, aggregate summary, ranked row, and `Report` dataclasses matching the architecture.
4. Create `tests/fixtures/combined_valid.log`, `tests/fixtures/combined_malformed.log`, and `tests/fixtures/expected_report_v1.json` covering IPv4, IPv6, escaped quotes/backslashes, `"-"` requests, offsets, and boundary statuses.
5. Create `tests/test_packaging.py` and `tests/test_models.py`; configure formatter, linter, type checker, pytest, and coverage thresholds in `pyproject.toml`.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_packaging.py tests/test_models.py`
- `python3.11 -m ruff check src tests && python3.11 -m mypy src`
- `nginx-log-stats --help && nginx-log-stats --version`

**Commit:** `step-1: establish package models and golden fixtures`

## Step 2: Implement Binary Input, Parsing, and Exact Aggregation

**Goal:** File/stdin bytes are decoded per physical line, the declared grammar produces records, malformed policies are observable, and all four exact report metrics are correct and deterministic.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Processing and Data Model, CLI Interface, Error Handling and Observability; `PRD.md` US-1 through US-5 and US-7.

**Tasks:**

1. Create `src/nginx_log_stats/input.py` with binary file/`sys.stdin.buffer` iteration, one-based physical line numbers, independent decoding, and the 1 MiB line guard.
2. Create `src/nginx_log_stats/parser.py` with the precise default-escape combined grammar and categorized failures; keep a clear correctness-first reference path.
3. Create `src/nginx_log_stats/aggregate.py` with total/malformed counts, exact counters, 24 buckets, unique-Agent share, deterministic ties, and the combined-key cardinality guard.
4. Create `src/nginx_log_stats/errors.py` with typed usage-independent input, resource-limit, and runtime failures for exit mapping.
5. Create `tests/test_input.py`, `tests/test_parser.py`, and `tests/test_aggregate.py` for grammar edges, decode recovery, status boundaries, time offsets, empty input, ties, and guard behavior.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_parser.py tests/test_aggregate.py --cov=nginx_log_stats --cov-report=term-missing`
- `python3.11 -m ruff check src tests && python3.11 -m mypy src`
- `python3.11 -m pytest tests/test_parser.py -k 'escape or missing_request or malformed'`

**Commit:** `step-2: add streaming parser and exact metrics`

## Step 3: Prove the Performance Architecture

**Goal:** A fixed representative 1 GB fixture proves exact output under 30 seconds and <=512 MiB RSS, or the step remains open while a profiled hot path is developed.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Performance Strategy and ADR-001; `PRD.md` NFR-1 and NFR-2.

**Tasks:**

1. Create `benchmarks/generate_fixture.py` to deterministically generate a 1 GB log outside the repository and write a manifest with bytes, records, line-length distribution, malformed rate, and distinct-key counts.
2. Create `benchmarks/reference_report.py` to derive expected aggregates with the correctness-first parser.
3. Create `benchmarks/run_benchmark.py` to capture elapsed time, peak RSS, environment, manifest hash, and report equality as machine-readable evidence.
4. Profile parsing/allocation. If required, create `src/nginx_log_stats/fastpath.py` that extracts only aggregation fields/hour while differential tests prove equivalence to `parser.py`.
5. Create `tests/test_parser_differential.py` to compare reference and selected hot path over golden and generated cases.

**Verification:**

- `python3.11 benchmarks/generate_fixture.py --size-bytes 1073741824 --output /tmp/nginx-1gb.log --manifest /tmp/nginx-1gb.manifest.json`
- `python3.11 benchmarks/run_benchmark.py --input /tmp/nginx-1gb.log --manifest /tmp/nginx-1gb.manifest.json --max-seconds 30 --max-rss-mib 512`
- `python3.11 -m pytest tests/test_parser_differential.py`

**Commit:** `step-3: prove streaming performance envelope`

## Step 4: Complete the Click Interface and Exit Contract

**Goal:** Every approved command option, file/stdin path, malformed mode, stdout/stderr rule, and exit code behaves exactly as documented.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` US-1, US-7, FR-6, FR-8.

**Tasks:**

1. Complete `src/nginx_log_stats/cli.py` with `INPUT`, mutually exclusive `--json`/`--csv`, `--top`, `--strict`, `--encoding`, `--max-cardinality`, and `--no-color`.
2. Map Click usage failures to `2`, strict input failures to `3`, cardinality failure to `4`, and runtime I/O failures to `1`; keep diagnostics on stderr.
3. Handle missing paths, decode recovery, empty input, text-only embedded stdin, broken stdout, and `SIGINT` according to the architecture.
4. Create `tests/test_cli.py` and `tests/test_exit_codes.py` using Click's isolated runner plus subprocess cases where signal/pipe behavior matters.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py tests/test_exit_codes.py`
- `printf '%s\n' '192.0.2.1 - - [01/Aug/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 1 "-" "curl/8"' | nginx-log-stats --json -`
- `nginx-log-stats --json --csv tests/fixtures/combined_valid.log; test $? -eq 2`

**Commit:** `step-4: enforce cli and exit contracts`

## Step 5: Build the Safe Rich Terminal Report

**Goal:** The default command presents all four reports clearly, with capability-aware color and no terminal-control injection from logs.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs and Security and Privacy Boundaries; `PRD.md` US-6 and FR-7.

**Tasks:**

1. Create `src/nginx_log_stats/renderers/__init__.py` and `src/nginx_log_stats/renderers/terminal.py` with four Rich sections, ranks, counts, all 24 hours, share, and valid/malformed summary.
2. Create `src/nginx_log_stats/sanitize.py` to remove or visibly escape C0/C1 controls and prevent Rich markup interpretation.
3. Respect `--no-color`, terminal detection, and `NO_COLOR`; never apply style to untrusted values as markup.
4. Create `tests/test_terminal_renderer.py` and golden snapshots for color-enabled, plain, empty, wide-value, and malicious-control inputs.

**Verification:**

- `python3.11 -m pytest tests/test_terminal_renderer.py`
- `nginx-log-stats --no-color tests/fixtures/combined_valid.log > /tmp/nginx-terminal.txt && test -s /tmp/nginx-terminal.txt`
- `test -z "$(LC_ALL=C sed -n $'/\033/p' /tmp/nginx-terminal.txt)"`

**Commit:** `step-5: add safe terminal report`

## Step 6: Add Versioned JSON and Stable CSV Renderers

**Goal:** JSON and CSV outputs are deterministic, ANSI-free, parseable, and match their published schemas without losing logged values.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs; `PRD.md` US-6, FR-5, NFR-3.

**Tasks:**

1. Create `src/nginx_log_stats/renderers/json.py` with schema version `1`, stable keys/types, 24 hourly rows, UTF-8, and a trailing newline.
2. Create `src/nginx_log_stats/renderers/csv.py` with `section,key,value,rank`, deterministic section order, RFC 4180 quoting, and lossless formula-leading values.
3. Create `tests/schemas/report-v1.schema.json`, `tests/fixtures/expected_report_v1.csv`, `tests/test_json_renderer.py`, and `tests/test_csv_renderer.py`.
4. Add end-to-end assertions that diagnostics remain on stderr and machine stdout contains no Rich/ANSI output.

**Verification:**

- `python3.11 -m pytest tests/test_json_renderer.py tests/test_csv_renderer.py`
- `nginx-log-stats --json tests/fixtures/combined_valid.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-stats --csv tests/fixtures/combined_valid.log | python3.11 -c 'import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert rows'`

**Commit:** `step-6: add json and csv contracts`

## Step 7: Harden Correctness, Security, and Compatibility

**Goal:** Adversarial input, parser variants, resource boundaries, and acceptance stories cannot cause false success, unsafe terminal output, or schema drift.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Security and Privacy Boundaries, Debate Summary, Verification Strategy; all P0 PRD acceptance criteria.

**Tasks:**

1. Create `tests/test_acceptance.py` as a trace matrix from US-1 through US-7 and every documented exit code.
2. Create `tests/test_adversarial.py` for long lines, high cardinality, escape/control sequences, formula-leading CSV keys, invalid encodings, truncated records, and broken pipes.
3. Create `tests/test_streaming_memory.py` to show peak memory is independent of byte size at fixed cardinality and the default distinct-key guard fails closed.
4. Run dependency/license/security checks and document justified findings in `SECURITY.md`; keep no secrets or network calls.
5. Update `README.md` with exact formats, limitations, safe CSV guidance, and benchmark reproducibility.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_stats --cov-fail-under=90`
- `python3.11 -m ruff check src tests benchmarks && python3.11 -m mypy src`
- `python3.11 -m pip_audit`
- `python3.11 -m pytest tests/test_adversarial.py tests/test_streaming_memory.py tests/test_acceptance.py`

**Commit:** `step-7: harden acceptance and resource boundaries`

## Step 8: Build and Verify the Release Candidate

**Goal:** The exact source candidate produces a clean wheel, passes all checks and the representative benchmark, and leaves reproducible evidence for handoff or publication.

**Time:** ~1.5 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PROJECT_ARCHITECTURE.md` Packaging and Deployment; `PRD.md` Success Metrics.

**Tasks:**

1. Finalize `README.md`, `CHANGELOG.md`, `LICENSE`, and package metadata without claiming unsupported platforms or features.
2. Create `scripts/smoke_wheel.sh` to build, install into a temporary clean environment, run help/version, and verify all three output modes.
3. Run the full suite, audit, golden-schema checks, and the 1 GB benchmark against the exact candidate.
4. Record hardware/fixture/tool versions and results in `docs/benchmark.md`; reconcile the Idea to Deploy state and exact-candidate verification receipt.
5. Tag/publish only after a current passing receipt; publication itself requires separate explicit authorization.

**Verification:**

- `python3.11 -m build && sh scripts/smoke_wheel.sh dist/*.whl`
- `python3.11 -m pytest --cov=nginx_log_stats --cov-fail-under=90 && python3.11 -m ruff check src tests benchmarks && python3.11 -m mypy src`
- `python3.11 benchmarks/run_benchmark.py --input /tmp/nginx-1gb.log --manifest /tmp/nginx-1gb.manifest.json --max-seconds 30 --max-rss-mib 512`
- `python3.11 -m pip_audit`

**Commit:** `step-8: verify release candidate`

## Dependency and Priority Rationale

The plan implements the highest-value analytics immediately after their shared input dependency, matching the RICE ordering where feasible. Performance proof precedes UI investment because it is a kill criterion. Terminal output precedes JSON/CSV because it is the default user path, while the common renderer-neutral report model prevents that order from coupling formats. P1 strict/top options are low-cost extensions completed with the core CLI; P2 features remain outside this weekend.

## Completion Rule

Do not mark a step complete from a commit message or narrative. Its exact candidate must pass every listed command applicable to that step, retain an acceptance trace, and satisfy the active `.itd/VERIFICATION_CONTRACT.json` adjudication route. A failed or unavailable command leaves the step in recovery, not Done.
