# Claude Code Implementation Guide: Nginx Log Insights CLI

This guide translates `IMPLEMENTATION_PLAN.md` into bounded implementation prompts for a later coding session. It does not authorize architecture changes. Work on one prompt at a time, inspect existing changes before editing, and attach actual command evidence to each handoff.

## Global Guardrails

- Use Python 3.11, Click, Rich, dataclasses, pytest, a `src/` layout, and pip packaging.
- Keep one single-process streaming pass and never retain raw records.
- Do not add authentication, a database, an HTTP API, a server, cloud resources, Docker runtime requirements, or Kubernetes.
- Preserve terminal, JSON, and CSV numeric parity.
- Preserve this complete exit contract: `0` success; `1` runtime/input I/O failure; `2` usage/configuration error; `3` input data or strict parse failure; `4` unique-cardinality exhaustion.
- Treat `PRD.md` acceptance criteria and `PROJECT_ARCHITECTURE.md` contracts as source of truth.
- Stop and update the specifications before making a behavior-changing interpretation.

## Prompt 1: Package and contract scaffold

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Read `PROJECT_ARCHITECTURE.md` first. Create only the package scaffold, Click command boundary, typed error boundary, and package/CLI tests listed in that step. Do not implement parsing or reports yet. Run the exact Step 1 verification commands and report changed files plus observed outputs.

Expected evidence: editable install succeeds, tests pass, and `nginx-insights --help` returns 0.

## Prompt 2: Parser and dataclasses

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Add every dataclass named in the architecture and a compiled parser for the fixed nginx combined format. Extract the remote address, local hour, request target, status, and exact User-Agent. Return structured parse errors that expose line number and reason without reproducing raw lines. Add all named fixtures and boundary tests. Do not add configurable formats.

Expected evidence: parser tests and parser coverage command pass on Python 3.11.

## Prompt 3: Streaming aggregation

> Implement Step 3 from `IMPLEMENTATION_PLAN.md` as a one-pass aggregator. Compute deterministic top-10 IP and 400–599 URL rankings, 24 hourly buckets using `100 × hourly_request_count / total_valid_requests`, and exact unique User-Agent share. Guard the set before it exceeds the configured maximum and raise the typed code-4 failure. Do not approximate cardinality. Add the specified unit tests.

Expected evidence: aggregation tests cover ties, boundary statuses, percentages, and cardinality exhaustion.

## Prompt 4: Input and exit semantics

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Stream from exactly one path or stdin, implement strict/non-strict malformed-line behavior, validate options, and map every path to the documented `0/1/2/3/4` codes. Confirm code 4 means unique-cardinality exhaustion. No failure may emit a partial report. Test each exit code through the Click runner or a subprocess boundary.

Expected evidence: CLI tests exercise codes 0, 1, 2, 3, and 4 and the full current suite passes.

## Prompt 5: Rich terminal output

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Render the four sections and metadata in the architecture-defined order. Make auto color TTY-aware, keep redirected output escape-free, and neutralize Rich markup/control sequences from IP, URL, and User-Agent-derived data. Do not change metric computation.

Expected evidence: terminal snapshots cover TTY, redirection, hostile strings, and no-error input.

## Prompt 6: JSON and CSV output

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Add schema-versioned JSON and fixed long-form RFC 4180 CSV with standard-library serializers. Wire mutually exclusive `--json` and `--csv` flags into the CLI. Include every metric and metadata field documented in `PROJECT_ARCHITECTURE.md`; never emit ANSI escapes in machine formats.

Expected evidence: both outputs parse with standard-library tools and have numeric parity with terminal results.

## Prompt 7: Hardening

> Implement Step 7 from `IMPLEMENTATION_PLAN.md`. Add the named hostile, malformed, Unicode, empty, boundary-status, broken-pipe, stdin/file-parity, and renderer-parity cases. Configure Ruff, mypy, and coverage in `pyproject.toml`. Fix issues without expanding product scope or weakening diagnostics.

Expected evidence: pytest coverage is at least 90%, Ruff passes, and mypy passes.

## Prompt 8: Performance

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Build a deterministic benchmark generator, a small CI performance smoke test, and the documented 1 GB release protocol. Measure first, profile actual hot paths, and preserve golden correctness while optimizing. Keep the large generated log outside the repository.

Expected evidence: three warm-cache runs for the exact candidate, median below 30 seconds, peak RSS below 512 MB, and recorded hardware/runtime context.

## Prompt 9: Distribution readiness

> Implement Step 9 from `IMPLEMENTATION_PLAN.md`. Add user-facing README, license, changelog, final package metadata, and a clean-wheel installation test. Document all formats, combined-log assumptions, privacy behavior, and the complete exit contract. Build the sdist/wheel, validate metadata, install the wheel, run the full suite, and repeat the release benchmark against the frozen candidate.

Expected evidence: build and metadata checks pass, the wheel installs in isolation, the full suite passes, and the candidate meets the performance gate.

## Handoff Format for Every Prompt

Return:

1. The implemented step and scope boundaries.
2. Files added or changed.
3. Exact verification commands actually run and their observed results.
4. Any acceptance criterion not verified, explicitly labeled unverified.
5. The next single step, without beginning it.
