# Implementation Plan: Nginx Stream Analyzer

This is a planning document only. Implementation must preserve the complete exit-code contract everywhere: `0` success, `1` unexpected runtime/output failure, `2` usage/validation error, `3` input failure, and `4` unique-cardinality exhaustion for exact IP, error-URL, or User-Agent limits. Code 4 must never be omitted or remapped.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package/module boundaries and console entry point | Every slice needs importable, installable structure | 1.0 h |
| 2 | Canonical fixtures and output/exit contracts | Prevent parser and renderer drift | 1.0 h |
| 3 | Streaming benchmark harness | Makes the 1 GB target measurable before optimization | 1.0 h |

No database, auth, server, container, or CI deployment runway is required.

## STEP 1: Freeze contracts and scaffold the package

**Goal:** An installable Python 3.11 package exposes a Click command and immutable report models.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Components, CLI Interface, Output Schemas.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, test/lint tooling, and the `nginx-stream-analyzer` script.
2. Create `src/nginx_stream_analyzer/{__init__,cli,models,errors}.py` with typed dataclasses and error taxonomy.
3. Create `tests/test_cli_contract.py` for help, version, mutual exclusion, and the `0/1/2/3/4` mapping.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_contract.py -q`

**Commit:** `step-1: scaffold package and public contracts`

## STEP 2: Build the streaming parser

**Goal:** Supported combined-log lines become validated `AccessRecord` values without retaining input.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Data Model and Algorithms, Inputs.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with a bounded binary line iterator, strict per-line UTF-8 decoding, the normative compiled grammar, and explicit request/timestamp/status parsing.
2. Create `tests/fixtures/{valid,mixed,malformed}.log` with escaping, IPv4/IPv6, CRLF, EOF without LF, time offsets, query strings, 4xx/5xx, oversized lines, and undecodable-byte cases.
3. Create `tests/test_parser.py` to prove each physical line is exactly valid or malformed and recovery crosses buffer boundaries safely.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m ruff check src/nginx_stream_analyzer/parser.py tests/test_parser.py`

**Commit:** `step-2: add bounded streaming nginx parser`

## STEP 3: Implement core aggregation and safety guard

**Goal:** One pass produces deterministic counts, 24 hourly percentages, and exact User-Agent share with bounded aggregate cardinality.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Data Model and Algorithms; `PRD.md` US-1 through US-4.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with counters, 24 buckets, stable top-10 sorting, and configured exact-key limits for IPs, error URLs, and User-Agents.
2. Create `tests/test_aggregate.py` for ties, empty input, malformed exclusion, status boundaries, the formula `100 × hourly_request_count / total_valid_requests`, and exact UA share.
3. Extend `tests/test_cli_contract.py` to prove exhaustion of each dimension returns code 4 and does not emit a partial success report.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py tests/test_cli_contract.py -q`
- `python3.11 -m mypy src/nginx_stream_analyzer`

**Commit:** `step-3: aggregate required metrics with cardinality guard`

## STEP 4: Add Rich terminal output

**Goal:** Default interactive output clearly presents totals and all four metrics without leaking control characters.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Outputs, Security and Privacy.

**Tasks:**

1. Create `src/nginx_stream_analyzer/render/{__init__,text}.py` with four Rich sections and consistent percentage precision.
2. Create `tests/golden/report.txt` and `tests/test_text_output.py` covering TTY color, redirected output, `--no-color`, escaping, and empty results.

**Verification:**

- `python3.11 -m pytest tests/test_text_output.py -q`
- `python3.11 -m nginx_stream_analyzer.cli --no-color tests/fixtures/valid.log`

**Commit:** `step-4: render safe Rich terminal report`

## STEP 5: Add JSON and CSV pipeline output

**Goal:** Machine modes emit stable, equivalent, ANSI-free schemas.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Output Schemas; `PRD.md` US-5.

**Tasks:**

1. Create `src/nginx_stream_analyzer/render/json.py` and `src/nginx_stream_analyzer/render/csv.py` using standard serializers.
2. Create `tests/golden/{report.json,report.csv}` and `tests/test_machine_output.py` for schema, row ordering, encoding, stderr separation, and cross-format parity.
3. Wire mutually exclusive Click flags in `src/nginx_stream_analyzer/cli.py` while preserving exit codes `0/1/2/3/4`.

**Verification:**

- `python3.11 -m pytest tests/test_machine_output.py tests/test_cli_contract.py -q`
- `python3.11 -m nginx_stream_analyzer.cli --json tests/fixtures/valid.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable json and csv renderers`

## STEP 6: Complete input ownership and failure handling

**Goal:** File failures and optional stdin/gzip streams have explicit ownership and exit semantics.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Inputs, Exit Codes; `PRD.md` US-6 and US-7.

**Tasks:**

1. Create `src/nginx_stream_analyzer/input.py` to open plain files first, then stdin and gzip as P1 slices.
2. Create `tests/test_input.py` for missing, unreadable, undecodable, corrupt gzip, and caller-owned stdin streams.
3. Confirm input failures map to 3, any unique-cardinality exhaustion to 4, usage to 2, and unexpected/output failures—including broken pipe—to 1 without traceback noise.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_cli_contract.py -q`
- `python3.11 -m nginx_stream_analyzer.cli does-not-exist.log; test $? -eq 3`

**Commit:** `step-6: harden streaming input and error mapping`

## STEP 7: Prove performance and bounded behavior

**Goal:** Representative 1 GB processing is measured below 30 seconds with peak memory recorded.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Performance and Reliability; `STRATEGIC_PLAN.md` KPIs.

**Tasks:**

1. Create `benchmarks/generate_log.py` using seed `20260804`, the exact `1_073_741_824`-byte target, declared cardinalities, and the specified status/malformed mix; expose and record its content hash.
2. Create `benchmarks/run.sh` with one warm-up and three JSON-to-`/dev/null` measurements, using median wall time as the machine oracle while recording environment, cache policy, throughput, and peak RSS.
3. Create `benchmarks/RESULTS.md` with commands, all raw runs, median, reference environment, source hash, and an explicit accepted RSS ceiling; profile and optimize only measured hot paths if the target fails.

**Verification:**

- `python3.11 benchmarks/generate_log.py --size-bytes 1073741824 --output /tmp/nginx-stream-analyzer-1gb.log`
- `/usr/bin/time -v python3.11 -m nginx_stream_analyzer.cli --json /tmp/nginx-stream-analyzer-1gb.log >/dev/null`

**Commit:** `step-7: verify one-gigabyte performance target`

## STEP 8: Run the complete quality gate

**Goal:** All functional, type, lint, security, schema, and exit-code contracts pass together.

**Time:** ~1.5 hours

**Context:** `PRD.md` — Release Acceptance; all architecture sections.

**Tasks:**

1. Finalize `tests/test_end_to_end.py` with all three renderers and exit codes `0/1/2/3/4`, explicitly including unique-cardinality exhaustion as 4.
2. Configure coverage thresholds in `pyproject.toml` and check dependencies with an open-source audit tool.
3. Record any platform limitations without weakening P0 acceptance.

**Verification:**

- `python3.11 -m ruff check .`
- `python3.11 -m mypy src/nginx_stream_analyzer`
- `python3.11 -m pytest --cov=nginx_stream_analyzer --cov-branch --cov-fail-under=90 -q`

**Commit:** `step-8: pass complete release quality gate`

## STEP 9: Finish package and operator documentation

**Goal:** A clean Python 3.11 environment can install, understand, and exercise the release in under 30 seconds after download.

**Time:** ~1 hour

**Context:** `README.md`, `CLAUDE_CODE_GUIDE.md`, and all release contracts.

**Tasks:**

1. Update `README.md` with real package coordinates, examples, schemas, supported format, privacy, performance results, and `0/1/2/3/4` exits.
2. Add `CHANGELOG.md` and the chosen open-source `LICENSE` after owner approval of license identity.
3. Build distributions and inspect wheel contents without publishing.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-analyzer-venv && /tmp/nginx-stream-analyzer-venv/bin/pip install dist/*.whl && /tmp/nginx-stream-analyzer-venv/bin/nginx-stream-analyzer --help`

**Commit:** `step-9: prepare installable documented release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Contracts, parser, aggregation | 4–6 h |
| Saturday PM | 4–6 | Human/machine rendering and input errors | 4–5 h |
| Sunday | 7–9 | Performance proof, quality gate, package polish | 4–6 h |

## Dependency and Scope Rules

Only one step is active at a time. P1 stdin/gzip work in Step 6 starts only after every P0 test through Step 5 passes. No implementation step may add authentication, a database, an HTTP API, a server, cloud infrastructure, Docker, or Kubernetes without revising the source specifications first.
