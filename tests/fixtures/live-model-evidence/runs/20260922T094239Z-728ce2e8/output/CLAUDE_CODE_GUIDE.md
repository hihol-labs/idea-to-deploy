# Claude Code Implementation Guide: nginx-stream-report

This guide converts `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. Run one prompt at a time, preserve WIP=1, and do not begin the next step until the current step's named checks pass. Read `PRD.md` and `PROJECT_ARCHITECTURE.md` before editing.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, dataclasses, pip-installable package.
- Local single-process streaming; no authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Default colored terminal text, plus `--json` and `--csv`.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- The complete exit-code contract is `0/1/2/3/4`: `0` success, `1` input/output runtime failure, `2` usage error, `3` no valid records, `4` unique-cardinality exhaustion.
- Never remap or omit code 4, silently approximate exact counts, emit partial reports, or load the entire input.

## Prompt 1: Package Skeleton

> Implement Step 1 of `IMPLEMENTATION_PLAN.md` only. Create `pyproject.toml`, `src/nginx_stream_report/__init__.py`, `src/nginx_stream_report/cli.py`, and `tests/integration/test_cli_basics.py`. Do not implement parsing or aggregation yet. Run the three Step 1 verification commands, report exact results, and stop.

## Prompt 2: Models and Errors

> Implement Step 2 only. Use the dataclass fields and invariants from `PROJECT_ARCHITECTURE.md`. Centralize typed failures and preserve exit codes `0/1/2/3/4`, with code 4 reserved for unique-cardinality exhaustion. Run Step 2 verification and stop.

## Prompt 3: Parser

> Implement Step 3 only. Parse the documented common/combined byte grammar line by line. Add clearly labeled synthetic fixtures and all listed edge tests. Do not broaden the grammar or normalize URL targets. Run Step 3 verification and stop.

## Prompt 4: Aggregator

> Implement Step 4 only. Build exact counters, all 24 hour buckets, and User-Agent statistics. Enforce each distinct-key ceiling before atomic record mutation. Use the exact hourly formula from the PRD. Run all aggregate tests, especially cardinality boundaries, and stop.

## Prompt 5: JSON and CSV

> Implement Step 5 only. Match the exact JSON and CSV contracts in `PROJECT_ARCHITECTURE.md`, including deterministic ordering, newline behavior, escaping, and zero-denominator representations. Do not add fields without updating the specs first. Run Step 5 verification and stop.

## Prompt 6: Terminal Text

> Implement Step 6 only. Create the Rich report with semantics independent of color, safe rendering of untrusted log values, TTY-aware styling, and `--no-color`. Run snapshots in colored/plain modes and stop.

## Prompt 7: CLI Integration

> Implement Step 7 only. Wire file/stdin streaming, parsing, aggregation, and delayed rendering. Test the complete `0/1/2/3/4` contract end to end. On any nonzero result, structured stdout must be empty. Ensure code 4 reports the exhausted dimension and configured limit. Run Step 7 verification and stop.

## Prompt 8: Quality Gate

> Implement Step 8 only. Close coverage gaps with meaningful tests, configure Ruff/mypy/pytest coverage, and validate wheel/sdist metadata. Do not lower thresholds or remove tests. Run every Step 8 command and stop with failures unresolved and clearly recorded.

## Prompt 9: Performance Evidence

> Implement Step 9 only. Generate a deterministic, non-committed 1 GB benchmark fixture and measure wall time plus peak memory with environment metadata. If the 30-second gate fails, profile before changing code and record before/after evidence. Do not claim generated data is production data. Run Step 9 verification and stop.

## Prompt 10: Release Handoff

> Implement Step 10 only. Reconcile README/help/spec behavior, add the changelog, build the candidate, and rerun all named release gates against the exact candidate. Do not publish externally. Record commands and outcomes, then stop.

## Recovery Rules

If a verification command fails, keep the current step active, preserve the failure output, make the smallest in-scope correction, and rerun the relevant gate. Change `PRD.md` first if intended behavior changes; change `PROJECT_ARCHITECTURE.md` first if a load-bearing technical decision changes. Never move forward on an unverified assumption.

