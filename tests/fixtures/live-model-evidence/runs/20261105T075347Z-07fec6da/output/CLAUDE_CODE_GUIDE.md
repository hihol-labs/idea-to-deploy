# Implementation Guide: Nginx Lens

These prompts implement the eight planned steps in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Product code does not exist yet. Read [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) and [CLAUDE.md](CLAUDE.md) first. Execute one step at a time; show actual verification results before advancing. The spec is the durable source; reconcile it before changing behavior.

## Contract to Preserve in Every Step
Exit codes are **0/1/2/3/4**: 0 complete successful report/help/version; 1 I/O, interruption or runtime failure; 2 invalid CLI usage; 3 no valid requests; 4 unique-cardinality exhaustion (including MemoryError). Do not remap or omit any code.

Preserve literal semantics: `100 × hourly_request_count / total_valid_requests`; unique UA share is `100 × distinct_nonmissing_user_agents / total_valid_requests`. Exact dictionaries/sets have one global --max-unique budget; no approximations, persistence or partial aggregate on failure. Read finite stdin/files only. Use Python 3.11, Click, Rich, dataclasses, pip, and one synchronous process.

## Prompt 1: Package and Fixtures
> Execute step 1 only. Create pyproject.toml, src/nginx_lens/{__init__,cli,models}.py, tests/test_package.py, tests/test_models.py and hand-counted tests/fixtures/{combined.log,expected.json}. Configure the nginx-lens entry point and dev extras. Keep the 0/1/2/3/4 contract. Verify with `python -m pip install -e '.[dev]'`, `python -m pytest tests/test_package.py tests/test_models.py` and `nginx-lens --help`. Report actual output and update step status only after passing; do not publish.

## Prompt 2: Reader and Parser
> Execute step 2 using architecture Input and Parsing Semantics. Create reader.py, parser.py, tests/test_reader.py, tests/test_parser.py and malformed.log. Handle quoted escapes, IPv6, numeric timezone, status boundaries, missing UA, query stripping, CRLF and missing final newline. Drain oversized lines without unbounded allocation; invalid UTF-8 is an invalid line. Preserve stdin ownership. Run `python -m pytest tests/test_reader.py tests/test_parser.py`; retain the 0/1/2/3/4 contract.

## Prompt 3: Rankings
> Execute step 3. Build aggregate.py IP and combined 400–599 path counters, with deterministic count-descending/key-ascending top ten. Add tests/test_rankings.py with independent hand-counted ties, status boundaries and path normalization. Run `python -m pytest tests/test_rankings.py tests/test_parser.py`. Preserve 0/1/2/3/4 and count valid records only.

## Prompt 4: Metrics and Capacity
> Execute step 4. Extend models.py and aggregate.py with 24 local-offset-hour bins, valid/invalid totals, exact nonmissing UA set and global cardinality preflight. Add tests/test_metrics.py and tests/test_capacity.py. Verify the 75.00% hourly and 50.00% UA examples in PRD, and exactly-at/over-budget atomic behavior. Use default total cap 1000000; no eviction or disk spill. Run `python -m pytest tests/test_metrics.py tests/test_capacity.py tests/test_rankings.py`. Preserve 0/1/2/3/4, including resource failure 4.

## Prompt 5: Reports
> Execute step 5. Implement render.py from the architecture output schemas. Create tests/test_render.py and expected.csv; verify complete JSON types, normalized CSV rows/escaping, 24 ordered bins, TTY color policy and terminal control escaping. Do not mix diagnostics into stdout. Run `python -m pytest tests/test_render.py`. Preserve 0/1/2/3/4 and use identical summary semantics for every renderer.

## Prompt 6: Public CLI
> Execute step 6. Wire cli.py with all specified options and stdin/path selection. Validate options before opening input, consume through EOF before reporting, and implement the complete exit-code contract 0/1/2/3/4. Add tests/test_cli.py for each exit, conflicting formats, NO_COLOR, --no-color, invalid-line warnings, MemoryError, broken pipe and interruption. No raw log lines in errors. Run `python -m pytest tests/test_cli.py tests/test_capacity.py tests/test_render.py`.

## Prompt 7: Installation and End-to-End
> Execute step 7. Add tests/test_end_to_end.py and tests/test_install.py to compare subprocess file/stdin JSON/CSV reports to independent fixture oracles and to test a wheel in a clean environment. Cover 0/1/2/3/4, resource exhaustion and all-invalid input without partial reports. Run `python -m pytest --cov=nginx_lens --cov-branch --cov-report=term-missing`, `python -m build`, and `python -m pytest tests/test_install.py`. Verify parser/aggregation branch coverage at least 90%; do not claim code review or security review unless actually performed.

## Prompt 8: Benchmark and Handoff
> Execute step 8. Create benchmarks/generate_log.py, benchmarks/run.py and benchmarks/RESULTS.md. Generate explicitly synthetic 1000000000-byte combined input below default cardinality budget and measure three complete successful subprocess runs including startup and final output. Record laptop specs, versions, cache state, median wall time and peak RSS. Run `python benchmarks/generate_log.py --bytes 1000000000 --output /tmp/nginx-lens-bench.log`, `python benchmarks/run.py --input /tmp/nginx-lens-bench.log --runs 3 --max-seconds 30`, then `python -m pytest`. Preserve 0/1/2/3/4; a fast code-4 exit is not throughput success. Reconcile docs/status and save continuity. If the target fails, report it and continue profiling within scope; publishing requires separate human authorization.

## Checkpoint and Recovery
Record commands actually run, failures and remaining work. Tests described in this guide are future commands, not evidence from blueprint generation. Do not mark implementation complete from planning documents. Save continuity through session-save at significant milestones. See [README.md](README.md) for intended operator examples.
