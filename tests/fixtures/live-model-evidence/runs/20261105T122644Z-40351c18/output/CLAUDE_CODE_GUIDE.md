# Claude Code Implementation Guide: Nginx Lens

Read [CLAUDE.md](CLAUDE.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [PRD.md](PRD.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) before implementation. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) records approved priorities. These prompts describe future work; this blueprint session implements no product code.

## Shared Contract for Every Prompt

Use Python 3.11, Click, Rich and dataclasses in one process. No authentication, database, HTTP API, server, cloud or Kubernetes. Read bounded lines and aggregate exact keys; finalize at EOF. Preserve the complete exit-code contract 0/1/2/3/4: 0 successful/empty/help/version; 1 report with malformed lines skipped; 2 usage error; 3 I/O/resource/interruption failure; 4 unique-cardinality exhaustion. Fatal 3/4 override pending 1. Do not remap or omit code 4.

unique-cardinality exhaustion

Code 4 covers either shared distinct-entry or stored-key-byte limit and emits no report. Defaults: 250000 entries and 67108864 bytes. Never switch to approximate counting, truncate keys or evict entries. The hourly formula is `100 × hourly_request_count / total_valid_requests`; UTC hour-of-day buckets combine dates. UA share is 100 times exact nonmissing UA cardinality divided by total valid requests; missing UAs still count in the denominator. Zero denominators yield zero. All schema, grammar, tie-breaking and rounding details come from architecture.

Work on one numbered step at a time. For each step: read its referenced contracts, add meaningful tests, implement, run the specified checks, and record actual results. Stop completion claims when a check fails. Commit messages below are suggestions only; do not push, publish, deploy or send artifacts externally without explicit human confirmation. All product step statuses start as not started.

## Prompt 1: Package and Contracts

"Execute Step 1 only. Create pyproject.toml, src/nginx_lens/__init__.py, cli.py and models.py, MIT LICENSE and tests/conftest.py, tests/test_contracts.py, tests/test_install.py plus synthetic combined.log and expected.json fixtures. Define the console entry point, development dependencies and typed report/failure models. Hand-calculate fixture metrics from PRD, independently of implementation. Run python -m pip install -e '.[dev]' and python -m pytest tests/test_contracts.py tests/test_install.py. Apply the shared 0/1/2/3/4 contract. Report executed checks and save continuity. Proposed local commit: step-1: establish package and CLI contracts."

## Prompt 2: Reader and Parser

"Execute Step 2 after Step 1 is verified. Implement reader.py and parser.py plus tests/test_reader.py and tests/test_parser.py. Use bounded 64 KiB physical lines, drain oversized records, support EOF without newline and CRLF, strict UTF-8, nginx hex escapes, canonical IPs and locale-independent timestamp parsing. Follow the combined-log grammar exactly. Test malformed fields, invalid encoding and IP/date/status boundaries. Run python -m pytest tests/test_reader.py tests/test_parser.py. Preserve the shared exit contract; save evidence and continuity. Proposed local commit: step-2: parse bounded nginx combined streams."

## Prompt 3: Rankings and Exactness Guards

"Execute Step 3 only. Implement aggregate.py and extend models.py. Count all valid IP requests and error URLs only for 400–599; preserve query strings. Maintain exact UA set and shared entry/key-byte budgets with atomic per-record quota checks. Add tests/test_rankings.py and tests/test_limits.py for ties, ten-row limits, same keys in separate namespaces, duplicates at capacity, exact limits and one-over exhaustion. Run python -m pytest tests/test_rankings.py tests/test_limits.py. Exhaustion must retain code 4 and no output report. Save continuity. Proposed local commit: step-3: add exact rankings and cardinality guards."

## Prompt 4: Percentages and Probe

"Execute Step 4 only. Extend aggregate.py with 24 UTC hours, percentage formula and exact nonmissing UA share. Add tests/test_metrics.py for offset rollover, multiple days, missing/duplicate agents and empty input. Create benchmarks/generate.py and benchmarks/probe.py with deterministic synthetic logs. Run python -m pytest tests/test_metrics.py and python benchmarks/probe.py --bytes 100000000. Label the probe as component evidence, never as the final 1 GB end-to-end claim. Save results and continuity. Proposed local commit: step-4: define exact percentages and probe throughput."

## Prompt 5: CLI and Rich

"Execute Step 5 only. Complete cli.py and add render.py text output. Support single file/stdin, help/version, quotas, --no-color and stderr diagnostics. Emit only after EOF; map all of 0/1/2/3/4 including interruption, pending partial status and fatal errors. Test input ownership, missing files, escaped terminal controls, TTY colors and redirected output in tests/test_cli.py and tests/test_terminal.py. Run python -m pytest tests/test_cli.py tests/test_terminal.py and nginx-lens --no-color tests/fixtures/combined.log. Save evidence and continuity. Proposed local commit: step-5: wire safe terminal CLI and exit contract."

## Prompt 6: Machine Formats

"Execute Step 6 only. Implement JSON schema version 1 and normalized CSV in render.py; reject --json with --csv before input reads in cli.py. Test parsing, quoting, percent precision, deterministic order, cross-renderer equivalence and uncontaminated stdout using tests/test_exports.py. Preserve the exact raw key semantics and complete exit contract. Run python -m pytest tests/test_exports.py and nginx-lens --json tests/fixtures/combined.log. Save evidence and continuity. Proposed local commit: step-6: support stable JSON and CSV pipelines."

## Prompt 7: Full Validation and Performance

"Execute Step 7 only. Add tests/test_end_to_end.py and tests/test_failures.py exercising every exit code, stdin equivalence, quota failure, interruption and broken pipe. Add benchmarks/run.py and record actual platform, cache, elapsed and peak-RSS results in benchmarks/results.md. Run python -m pytest --cov=nginx_lens --cov-branch; generate the 1000000000-byte fixture and run three end-to-end JSON measurements using the commands in IMPLEMENTATION_PLAN.md. Profile only demonstrated bottlenecks; rerun correctness after modifications. A missed target remains a failed release gate. Never fabricate measurements or weaken quotas. Save continuity. Proposed local commit: step-7: verify failure paths and performance budget."

## Prompt 8: Local Package Handoff

"Execute Step 8 only after preceding checks pass. Update README.md, CLAUDE.md, pyproject.toml and tests/test_install.py to match implemented behavior. Run python -m pytest and python -m build. Prepare an offline dependency wheelhouse, install the wheel in the fresh virtual environment and run help/version and golden JSON analysis with the plan's commands. Confirm MIT and dependency licenses. Record actual results and unresolved risks in .itd-memory/continuity/nginx-lens-implementation.md. Seek independent product-code review before release; no external publication is authorized. Proposed local commit: step-8: package and document local release candidate."

## Recovery and Handoff

If a step fails, keep it in progress, preserve the command/output and identify one next action. Change specifications before intentionally changing behavior. Do not treat blueprint checks as product tests. At every significant block, use the repository-local session-save skill; preserve canonical .itd-memory continuity and append durable decisions to .itd/DECISIONS.md. This session's adversarial architecture review is owned by the external harness and is not an implementation prompt.
