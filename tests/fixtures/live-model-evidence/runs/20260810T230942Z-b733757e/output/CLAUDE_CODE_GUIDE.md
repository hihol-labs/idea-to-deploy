# Claude Code Implementation Guide: nginx-stream-stats

## Purpose

This guide translates [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) into bounded prompts for an implementation agent. It does not replace the specifications: [PRD.md](PRD.md) defines acceptance, and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) resolves technical conflicts.

Run one prompt at a time, keep WIP at one step, inspect the diff, execute the named verification, and record evidence before continuing. Do not implement deferred P2 features opportunistically.

## Non-Negotiable Contract for Every Step

- Python 3.11, Click, Rich, dataclasses, pip package; one local synchronous process.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes product runtime.
- Never retain or echo raw log lines; never invoke a shell with input paths.
- Preserve stdout for the selected report and stderr for diagnostics/errors.
- Preserve all exit codes exactly: `0` success; `1` input/runtime failure; `2` CLI usage error; `3` zero valid supported records; `4` unique-cardinality exhaustion. Code `4` must not be omitted, remapped, or caught as generic code `1`.
- Hourly percentages must use `100 × hourly_request_count / total_valid_requests`.
- Stop if the active step requires changing the PRD or architecture; update the specification explicitly before implementation.

## Prompt 1 — Package Skeleton and Domain Contracts

> Implement only Step 1 in `IMPLEMENTATION_PLAN.md`. Read `PROJECT_ARCHITECTURE.md` sections 4–6 and PRD FR-1, FR-7, and NFR-4 first. Create only `pyproject.toml`, `src/nginx_stream_stats/__init__.py`, `src/nginx_stream_stats/models.py`, `src/nginx_stream_stats/errors.py`, `tests/test_models.py`, and `tests/test_errors.py`. Make the console-script metadata installable but do not implement parsing or metrics. Encode the complete exit contract `0/1/2/3/4`, with `4` meaning unique-cardinality exhaustion. Run exactly the Step 1 verification commands and report files changed, test output, and remaining risks. Do not start Step 2.

## Prompt 2 — Combined-Format Parser

> Implement only Step 2 in `IMPLEMENTATION_PLAN.md`. Read the parser, data, and privacy contracts in `PROJECT_ARCHITECTURE.md` plus PRD FR-1 and FR-6. Add the precompiled, lazy nginx combined-format parser and only synthetic, non-sensitive fixtures/tests. Preserve exact URL query strings and logged timezone offsets. Missing User-Agent `-` must remain distinguishable from a real string. Diagnostics may retain line number and bounded reason category, never the raw line. Run the Step 2 verification commands and report evidence. Do not add aggregators or renderers.

## Prompt 3 — Metrics and Cardinality

> Implement only Step 3 in `IMPLEMENTATION_PLAN.md`. Read PRD US-2 through US-5 and architecture sections 5 and 7. Add one-pass exact IP/error-URL counters, 24 hour bins, distinct non-missing User-Agent tracking, deterministic top-10 ties, and the shared unique-key ceiling. Use the literal hourly formula `100 × hourly_request_count / total_valid_requests`. Enforce the ceiling before insertion and propagate the typed condition as exit `4`—unique-cardinality exhaustion only. Zero valid records remains `3`. Test every status boundary, tie, formula, missing value, and ceiling edge. Run Step 3 verification and stop.

## Prompt 4 — JSON and CSV

> Implement only Step 4 in `IMPLEMENTATION_PLAN.md`. Read the exact JSON and long-form CSV contracts under `PROJECT_ARCHITECTURE.md` `## CLI Interface`. Render the existing immutable report without recalculating metrics. Emit numeric values, deterministic ordering, correct escaping, `schema_version: 1`, and no ANSI/control commentary. Keep the exit-code contract `0/1/2/3/4` unchanged, including `4` for unique-cardinality exhaustion. Run the renderer verification commands and stop before terminal UI work.

## Prompt 5 — Rich Text

> Implement only Step 5 in `IMPLEMENTATION_PLAN.md`. Build the Rich renderer from the same report used by JSON/CSV. It must show the validity summary and all four metrics, sanitize untrusted field values, color only when policy enables it, and remain readable at 80 columns. Do not change metric semantics, parser behavior, CLI options, or the `0/1/2/3/4` contract. Run Step 5 verification and report terminal-specific test evidence.

## Prompt 6 — Click Integration

> Implement only Step 6 in `IMPLEMENTATION_PLAN.md`. Read the complete `PROJECT_ARCHITECTURE.md` `## CLI Interface` before editing. Wire `nginx-stream-stats analyze [OPTIONS] INPUT`, file/`-` input, mutually exclusive formats, color policy, positive `--max-unique`, bounded malformed diagnostics, help, and version. Keep stdout/stderr clean and map outcomes exactly: `0` success, `1` input/runtime, `2` usage, `3` zero valid records, `4` unique-cardinality exhaustion. Assert each code independently in `tests/test_cli.py`; specifically prove exhaustion stays `4`. Handle broken pipe as specified. Run all Step 6 commands and stop.

## Prompt 7 — Performance and Robustness

> Implement only Step 7 in `IMPLEMENTATION_PLAN.md`. Create a deterministic generator clearly labeled as synthetic benchmark data, the opt-in performance test, and `docs/PERFORMANCE.md`. Freeze and record the exact candidate and reference laptop context, then measure exactly 1 GB with `/usr/bin/time -v`. If wall time is 30 seconds or more, profile first and optimize only observed hotspots; do not introduce services, persistence, approximation, or multiprocessing without a spec change. Exercise the ceiling and verify code `4` still means unique-cardinality exhaustion. Report wall time and peak RSS in the file, not as an unsupported claim, and stop.

## Prompt 8 — Release Readiness

> Implement only Step 8 in `IMPLEMENTATION_PLAN.md`. Re-read the PRD release matrix and Strategic Plan Definition of Done. Finalize README, license, changelog, optional test workflow, package build, metadata check, clean-wheel install, full tests, and smoke runs. README must document `0/1/2/3/4`, with `4` meaning unique-cardinality exhaustion. Do not publish, deploy, tag, or push without separate authorization. Reconcile documentation with actual behavior; if behavior conflicts, treat PRD and architecture as source and fix or explicitly revise the spec. Report commands actually run and unresolved blockers.

## Review Prompt

> Review the exact candidate against `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md`. Check metric formulas, supported-format honesty, top-10 tie ordering, JSON/CSV types, ANSI/stdout isolation, raw-line privacy, streaming behavior, and each exit code `0/1/2/3/4`—especially that unique-cardinality exhaustion is still `4`. Cite file/line evidence, distinguish observed defects from hypotheses, and do not modify code during review.

## Handoff Template

At the end of each completed step record:

- Active step and exact scope completed.
- Files changed.
- Verification commands actually run and their outcomes.
- Acceptance criteria now evidenced.
- Known risks or failures; label unrun checks as unverified.
- Exact next step; do not mark a later step active prematurely.

At the end of the session follow the project memory rule in [CLAUDE.md](CLAUDE.md).
