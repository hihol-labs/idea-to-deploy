# Implementation Plan: nginx-streamtop

## 1. Delivery Rules

This plan implements the specification in `PRD.md` and the selected Variant A
in `PROJECT_ARCHITECTURE.md`. It is intentionally bounded to one weekend and
contains no database, HTTP service, authentication, cloud, or Kubernetes work.
Steps are dependency-ordered; RICE order is used within each dependency layer.

For every step, freeze the exact candidate, run the stated checks, and attach
the repository's current verification/adjudication evidence before marking the
step complete. Commands below are the intended implementation checks and may be
refined when the actual verification contract is established.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package skeleton and Python 3.11 tooling | Every module/test depends on import and console-entry contracts | 1 h |
| 2 | Domain dataclasses and fixtures | Parser, aggregation, and renderers need stable typed boundaries | 1 h |
| 3 | Benchmark protocol and fixture profile | Performance must be measured before architecture gets expensive to change | 1 h |
| 4 | CI test/lint/type commands | Every later increment needs a repeatable oracle | 1 h |

No database schema, migration, auth system, Docker environment, or deployment
pipeline is runway for this local-only product.

## STEP 1: Establish the installable package and quality gates

**Goal:** A clean Python 3.11 environment can build and invoke an empty but
well-defined `nginx-streamtop` command.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 10; `PRD.md` FR-01.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata,
   console entry point, and development test/lint/type dependencies.
2. Create `src/nginx_streamtop/__init__.py` with the version source.
3. Create `src/nginx_streamtop/cli.py` with the Click command surface described
   under `## CLI Interface`, without metric behavior yet.
4. Create `tests/test_cli.py` for help, version, and conflicting-format flags.
5. Add CI configuration at `.github/workflows/ci.yml` for a clean install and
   the agreed checks.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-streamtop --help`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Define records, reports, and representative fixtures

**Goal:** Parser and renderer boundaries are executable as typed domain models,
with fixtures that make expected behavior replayable.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` section 6; `PRD.md` data definitions.

**Tasks:**

1. Create `src/nginx_streamtop/models.py` with `AccessRecord`, `RankedCount`,
   `HourCount`, `ProcessingStats`, and `Report` dataclasses.
2. Create `tests/fixtures/combined.log` covering status classes, repeated/tied
   keys, offsets, query strings, and a literal `-` User-Agent.
3. Create `tests/fixtures/malformed.log` covering empty and malformed lines.
4. Create `tests/test_models.py` for model invariants and zero-record behavior.

**Verification:**

- `python3.11 -m pytest tests/test_models.py -q`
- `python3.11 -m ruff check src tests`
- `python3.11 -m mypy src`

**Commit:** `step-2: define domain report models`

## STEP 3: Implement streaming input ownership

**Goal:** The command reads a path, `-`, or omitted stdin line-by-line and maps
I/O failures to the documented behavior.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` Inputs and Exit Codes;
`PRD.md` US-01.

**Tasks:**

1. Create `src/nginx_streamtop/inputs.py` for file/stdin selection, encoding
   validation, context ownership, and read errors.
2. Extend `src/nginx_streamtop/cli.py` to connect Click arguments to the input
   iterator without materializing all lines.
3. Create `tests/test_inputs.py` for path, stdin, invalid codec, missing file,
   and simulated mid-stream read failure.
4. Extend `tests/test_cli.py` with exit-code and stderr/stdout separation tests.

**Verification:**

- `python3.11 -m pytest tests/test_inputs.py tests/test_cli.py -q`
- `printf '' | nginx-streamtop --json -`

**Commit:** `step-3: add streaming file and stdin input`

## STEP 4: Parse the supported nginx combined format

**Goal:** Valid lines become timezone-aware typed records; malformed lines have
safe, line-numbered failures.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6–7; `PRD.md` FR-02 and US-06.

**Tasks:**

1. Create `src/nginx_streamtop/parser.py` with a precompiled/deterministic
   combined-format parser and typed parse error.
2. Preserve request targets including query strings and validate status and
   timezone-aware timestamps.
3. Create `tests/test_parser.py` for valid records, escapes, IPv4/IPv6, `-`
   fields, malformed quotes, timestamp errors, and safe error text.
4. Extend `tests/test_cli.py` for tolerant and `--strict` parse behavior.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_cli.py -q`
- `nginx-streamtop --strict tests/fixtures/malformed.log; test $? -eq 2`

**Commit:** `step-4: parse nginx combined access logs`

## STEP 5: Aggregate all four metrics in one pass

**Goal:** One traversal produces deterministic IP, error-URL, hourly, and
unique-User-Agent statistics plus processing counts.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 6; `PRD.md` US-02 through US-05.

**Tasks:**

1. Create `src/nginx_streamtop/aggregate.py` with one mutable streaming state
   and a renderer-independent `Report` finalizer.
2. Implement status 400–599 filtering, source-offset hour buckets, exact agent
   distinctness, zero-input semantics, and deterministic top-10 ties.
3. Implement `--max-distinct` across `src/nginx_streamtop/aggregate.py` and
   `src/nginx_streamtop/cli.py`, including default/disabled behavior, exit 5,
   and suppression of partial reports.
4. Create `tests/test_aggregate.py` covering every metric, 10-item limits,
   ties, zero input, multiple days/offsets, malformed counters, and the exact
   distinct-key boundary.
5. Connect parser and aggregator in `src/nginx_streamtop/cli.py`.
6. Add the deterministic 100 MB spike fixture profile and record throughput in
   `docs/PERFORMANCE.md`; if extrapolated margin is below 20%, profile and use
   the architecture's allocation-conscious fallback before Step 6.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py tests/test_parser.py -q`
- `python3.11 -m pytest --cov=nginx_streamtop --cov-report=term-missing`
- `/usr/bin/time -v nginx-streamtop --json /tmp/nginx-streamtop-100m.log >/dev/null`

**Commit:** `step-5: add single-pass metric aggregation`

## STEP 6: Render the default Rich terminal report

**Goal:** Interactive users receive readable colored sections with no unsafe
markup or accidental color in redirected output.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 8; `PRD.md` US-07.

**Tasks:**

1. Create `src/nginx_streamtop/renderers/__init__.py` with renderer selection.
2. Create `src/nginx_streamtop/renderers/terminal.py` for four labeled metric
   sections and processing statistics.
3. Escape/disable markup for log-derived values and implement TTY/`--no-color`
   behavior.
4. Create `tests/test_render_terminal.py` with captured-console and malicious
   markup/escape fixtures.

**Verification:**

- `python3.11 -m pytest tests/test_render_terminal.py tests/test_cli.py -q`
- `nginx-streamtop --no-color tests/fixtures/combined.log`

**Commit:** `step-6: render safe Rich terminal report`

## STEP 7: Add stable JSON output

**Goal:** Pipelines receive the documented JSON object with no diagnostics or
ANSI bytes on stdout.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` Outputs; `PRD.md` US-08.

**Tasks:**

1. Create `src/nginx_streamtop/renderers/json.py` with explicit schema mapping,
   timestamp formatting, numeric types, and trailing newline.
2. Extend `src/nginx_streamtop/cli.py` to select JSON without importing Rich
   presentation behavior.
3. Create `tests/test_render_json.py` with schema, zero-input, special-string,
   stderr isolation, and golden-contract checks.

**Verification:**

- `python3.11 -m pytest tests/test_render_json.py tests/test_cli.py -q`
- `nginx-streamtop --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-7: add stable JSON pipeline output`

## STEP 8: Add normalized CSV output

**Goal:** Pipelines receive RFC-compatible rows with a fixed header and section
discriminator for the complete report.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` Outputs; `PRD.md` US-08.

**Tasks:**

1. Create `src/nginx_streamtop/renderers/csv.py` using the standard `csv`
   module and the fixed `section,key,count,value` schema.
2. Extend renderer selection in `src/nginx_streamtop/cli.py`.
3. Create `tests/test_render_csv.py` for every section, delimiters/newlines in
   values, zero input, stable headers, and absence of ANSI bytes.

**Verification:**

- `python3.11 -m pytest tests/test_render_csv.py tests/test_cli.py -q`
- `nginx-streamtop --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-8: add normalized CSV pipeline output`

## STEP 9: Validate performance and resource behavior

**Goal:** The project either proves the 1 GB/30 s target on a documented laptop
or records a measured blocker without weakening correctness.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 11; `STRATEGIC_PLAN.md`
KPIs; `PRD.md` NFR-01 and kill criteria.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically build the
   declared representative and high-cardinality fixtures outside source control.
2. Create `tests/test_performance.py` with a marked smoke benchmark and report
   correctness assertions.
3. Create `docs/PERFORMANCE.md` recording fixture hash/profile, hardware,
   versions, command, elapsed time, and peak RSS.
4. Profile first; optimize `parser.py`/`aggregate.py` only when evidence points
   to a bottleneck and behavior tests remain unchanged.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --size 1GiB --output /tmp/nginx-streamtop-1g.log`
- `/usr/bin/time -v nginx-streamtop --json /tmp/nginx-streamtop-1g.log >/dev/null`
- `python3.11 -m pytest -m performance -q`

**Commit:** `step-9: verify gigabyte-scale performance`

## STEP 10: Complete release and clean-install evidence

**Goal:** A wheel installed into a fresh Python 3.11 environment satisfies the
documented CLI, quality, privacy, and compatibility contracts.

**Time:** ~1.5 hours

**Context:** All architecture and PRD sections; `README.md` Quick Start.

**Tasks:**

1. Finalize `README.md` with supported format, examples, schemas, limitations,
   privacy notes, and measured performance link.
2. Add `CHANGELOG.md` with the initial public contract.
3. Add golden CLI cases under `tests/golden/` and complete `tests/test_cli.py`.
4. Build distributions into `dist/`, inspect metadata, install the wheel into a
   new environment, and smoke-test file/stdin plus all three formats.
5. Reconcile `CLAUDE.md`, the active Idea to Deploy state, and verification
   evidence for handoff.

**Verification:**

- `python3.11 -m ruff check src tests scripts`
- `python3.11 -m mypy src`
- `python3.11 -m pytest --cov=nginx_streamtop --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-streamtop-release && /tmp/nginx-streamtop-release/bin/pip install dist/*.whl && /tmp/nginx-streamtop-release/bin/nginx-streamtop --version`

**Commit:** `step-10: complete release verification`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable contract, models, and streaming input | 4 h |
| Saturday PM | 4–5 | Correct parsing and all core metrics | 4 h |
| Sunday AM | 6–8 | Terminal, JSON, and CSV output contracts | 4 h |
| Sunday PM | 9–10 | Performance proof, full verification, and release handoff | 4 h |

## Dependency and Deferral Notes

- Steps 1–5 are the critical path; output work must not duplicate aggregation.
- JSON precedes CSV within the output layer because it has higher RICE score.
- `.gz` input and approximate cardinality remain P2 and are excluded from this
  weekend plan.
- Publishing to a package index is a separate externally authorized action;
  building and checking the wheel is included, uploading it is not.
