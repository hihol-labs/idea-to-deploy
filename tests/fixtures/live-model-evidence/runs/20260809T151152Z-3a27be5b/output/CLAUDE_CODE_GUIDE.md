# Claude Code Implementation Guide: StreamSift

## 1. How to Use This Guide

This file turns `IMPLEMENTATION_PLAN.md` into bounded prompts for a future implementation agent. Execute one prompt at a time and preserve WIP=1. Before each step, read `PRD.md`, the cited architecture sections, existing tests, and the current diff. Do not expand scope or mark a step complete from narration; run the listed verification against the exact candidate.

This guide does not authorize a database, authentication, HTTP API, server, cloud resource, Docker, or Kubernetes. Product behavior is spec-first: update the PRD/architecture before intentionally changing a contract.

## 2. Global Implementation Contract

Use Python 3.11, Click, Rich, and dataclasses. Keep one process and one pass over input. Results go to stdout and diagnostics to stderr. Raw log lines and parsed-record lists must not be retained.

Every step must preserve and test the complete exit-code contract:

| Code | Required meaning |
|---:|---|
| `0` | Successful analysis with complete output |
| `1` | Input/output runtime failure |
| `2` | CLI usage or validation error |
| `3` | Log-data failure: strict malformed record or no valid requests |
| `4` | Unique-cardinality exhaustion |

Do not omit, reuse, or remap code `4`. Hourly percentages always use `100 × hourly_request_count / total_valid_requests` and are rounded only at serialization.

For every prompt below:

1. State the files you intend to change and confirm they are within that step.
2. Add or update tests with the behavior; do not weaken existing gates.
3. Run the exact verification commands and report command/output evidence.
4. Inspect the diff for unrelated changes, placeholders, debug output, and secret/network behavior.
5. Stop on a failed gate; leave a concise recovery note and do not claim completion.

## 3. Step Prompts

### Prompt 1 — Package and CLI Shell

> Implement only Step 1 of `IMPLEMENTATION_PLAN.md`. Create `pyproject.toml`, package initializers, `errors.py`, and the Click shell in `cli.py`, plus focused CLI tests. Require Python 3.11 and expose the `streamsift` console script. Declare canonical constants for the full `0/1/2/3/4` exit contract, including `4` for unique-cardinality exhaustion. Implement help/version, input argument, mutually exclusive `--json`/`--csv`, color controls, `--strict`, and positive `--max-cardinality`; do not implement parsing or fake results. Run the Step 1 verification commands and show evidence.

**Acceptance focus:** installation, option surface, validation exit `2`, no fabricated analysis output.

### Prompt 2 — Parser and Input

> Implement only Step 2 of `IMPLEMENTATION_PLAN.md`, following the grammar and dataclasses in `PROJECT_ARCHITECTURE.md`. Add `model.py`, `parser.py`, fixtures, and parser tests; connect buffered read-only file/stdin iteration. Compile parsing machinery once and do not retain lines. Tolerant mode counts malformed lines; strict malformed data and zero-valid input map to `3`; I/O maps to `1`. Preserve `0/1/2/3/4` globally, with `4` reserved for unique-cardinality exhaustion. Run both verification commands and show evidence.

**Acceptance focus:** supported combined format, timestamp offsets, quoted fields, query targets, missing User-Agent, UTF-8 replacement, file/stdin equivalence.

### Prompt 3 — Streaming Metrics

> Implement only Step 3 of `IMPLEMENTATION_PLAN.md` in `aggregate.py` and focused tests. In one traversal update IP counts, 400–599 target counts, 24 integer hour buckets, and the exact set of nonempty User-Agents. Enforce one distinct-insertion budget before adding new aggregate keys; raise the typed exhaustion failure mapped to exit `4`, never partial success. Rank deterministically. Compute each hourly percentage with `100 × hourly_request_count / total_valid_requests`, and the User-Agent share from distinct nonempty agents over valid requests; round only in renderers. Preserve all `0/1/2/3/4` meanings. Run the Step 3 checks and show evidence.

**Acceptance focus:** four correct metrics, fixed top 10, tie ordering, exact cardinality guard, no raw-record retention.

### Prompt 4 — Rich Output

> Implement only Step 4 of `IMPLEMENTATION_PLAN.md`. Add the Rich terminal renderer and integrate it as the default. Render four clearly labeled sections and record totals; include all 24 hours. Escape untrusted fields and control sequences. Apply color automatically only for a TTY, with explicit overrides, and keep diagnostics on stderr. Preserve the full `0/1/2/3/4` behavior, including exit `4` for unique-cardinality exhaustion. Add golden and safety tests, then run the listed checks.

**Acceptance focus:** readable default output, safe rendering, deterministic content, no ANSI in non-TTY output.

### Prompt 5 — JSON and CSV

> Implement only Step 5 of `IMPLEMENTATION_PLAN.md`. Add JSON schema version 1 and normalized CSV with header `metric,dimension,count,percentage` exactly as specified in `PROJECT_ARCHITECTURE.md`. Use standard serializers, stable ordering, UTF-8, and numeric percentages. Never mix stderr diagnostics or ANSI with pipeline stdout. Map read/write/broken-pipe runtime failures to `1`, invalid mode use to `2`, bad/no data to `3`, and unique-cardinality exhaustion to `4`; success is `0`. Prevent any failed invocation from emitting a complete-looking partial payload. Run schema/golden checks and show evidence.

**Acceptance focus:** parseable schemas, escaped values, all 24 hourly rows, strict stdout/stderr separation.

### Prompt 6 — End-to-End Contract

> Implement only Step 6 of `IMPLEMENTATION_PLAN.md`. Build an end-to-end subprocess matrix proving every source, output mode, metric invariant, and the exact exits: `0` success, `1` I/O runtime failure, `2` CLI usage error, `3` strict malformed/no valid data, `4` unique-cardinality exhaustion. Assert failure stderr is actionable, contains no traceback, and does not leave a successful payload. Add property/invariant tests where useful without adding a new runtime dependency unless justified. Run the full coverage and compile checks.

**Acceptance focus:** no untested exit path, no remapping of `4`, stable ranking/formula behavior.

### Prompt 7 — Performance and Memory Gate

> Implement only Step 7 of `IMPLEMENTATION_PLAN.md`. Add opt-in performance tooling/tests that generate representative data outside the repository and record environment, bytes, line count, cardinality, wall time, and peak RSS. Prove a 1 GB supported-format log completes in under 30 seconds on the documented laptop. Compare equal-cardinality inputs of different lengths to demonstrate no retained-record growth, and prove over-limit input exits `4`. Preserve `0/1/2/3/4`. Profile before optimizing; do not add multiprocessing or change architecture without updating the specs. Run smoke and benchmark commands and report measured evidence.

**Acceptance focus:** reproducible evidence rather than an unmeasured claim; representative, not trivial, cardinality.

### Prompt 8 — Release Rehearsal

> Implement only Step 8 of `IMPLEMENTATION_PLAN.md`. Add user-facing README/license/package hygiene, build wheel and sdist, inspect contents, and install the wheel in a clean Python 3.11 environment. Document all metrics, the literal hourly formula `100 × hourly_request_count / total_valid_requests`, JSON/CSV schemas, limitations, and the complete exits `0/1/2/3/4`, with `4` defined as unique-cardinality exhaustion. Run the full suite and all golden smoke commands from both file and stdin. Reconcile any intentional contract change into every planning document before acceptance.

**Acceptance focus:** clean install, complete docs, exact-candidate evidence, no P1/P2 scope creep.

## 4. Review Checklist for Every Step

- [ ] Only the active step's files/behavior changed.
- [ ] No authentication, database, HTTP/API server, cloud, Docker, or Kubernetes was introduced.
- [ ] Streaming remains single-process and raw records are not accumulated.
- [ ] Metric definitions, stable ties, and serializer precision match the specs.
- [ ] stdout/stderr and color policies remain intact.
- [ ] `0/1/2/3/4` remain complete and code `4` means unique-cardinality exhaustion.
- [ ] Tests ran against the exact candidate; no ignored/untracked fixture silently influenced results.
- [ ] Failure evidence is reported as failure/recovery, never success.

## 5. Handoff Format

At the end of an implementation step, record: active step, files changed, acceptance criteria satisfied, verification commands and outcomes, remaining risks, exact next step, and whether documentation contracts changed. Never report “done” based only on code inspection.

