# Implementation Guide: Nginx Lens

This guide is a set of prompts for a future implementation session, not permission to implement during this blueprint. Read [CLAUDE.md](CLAUDE.md), [architecture](PROJECT_ARCHITECTURE.md), [PRD](PRD.md), [implementation plan](IMPLEMENTATION_PLAN.md), [strategy](STRATEGIC_PLAN.md), and [README](README.md) before starting. The external harness owns the independent architecture review; it has not run inside the blueprint session.

## Shared Contract for Every Prompt

Use one Python 3.11 process, Click, Rich, and dataclasses; distribute through pip. Keep all log processing local and stateless across invocations. No authentication, database, HTTP API, server, cloud, Kubernetes, product telemetry, custom formats, or approximate counting. Do not infer completed code from these documents.

Preserve the complete exit-code contract **0/1/2/3/4**:

- **0:** successful valid/empty input, help, or version.
- **1:** input/output or unexpected internal runtime failure; a failed write may leave partial stdout.
- **2:** CLI usage error, conflicting export flags, or invalid capacity options.
- **3:** malformed input; default emits a report over valid records and returns 3, while strict mode aborts without a report.
- **4:** unique-cardinality exhaustion from either retained-key-count or retained-key-byte budget; abort without a report.

The exact term `unique-cardinality exhaustion` is part of the code-4 contract. Never remap this case or quietly return approximate results. Use atomic per-record preflight and the architecture's error precedence. No report is published before EOF and successful serialization, except that OS write failures cannot retract already-written bytes.

Hourly request percentage is `100 × hourly_request_count / total_valid_requests`, using 24 UTC hour-of-day buckets across dates. Unique UA percentage is `100 × unique_user_agent_count / total_valid_requests`, excluding `-`/empty UA from the numerator only. Both return 0 for zero valid requests; round percentages to six decimal places. Preserve exact URL targets including queries and deterministic ties. Treat log fields as untrusted data; follow the terminal/CSV display and JSON interchange rules.

Work with WIP=1. Read `.itd/` contracts and `.itd-memory/STATE.json`, update scope before expanding it, and attach evidence before marking any implementation step complete. Change specifications first if behavior needs to change. The commands below are future verification commands and have not run in this planning session.

## Prompt 1: Package and Models

> Implement only Step 1 of IMPLEMENTATION_PLAN.md. Create pyproject.toml, the src/nginx_lens package, Click entry point, slotted dataclasses, package tests, and MIT LICENSE. Use the precise fields from PROJECT_ARCHITECTURE.md. Runtime dependencies are Click and Rich; dev extras include pytest, pytest-cov, and build. Help/version must not read stdin or files. Preserve the full shared 0/1/2/3/4 contract while later analysis paths remain unimplemented. Verify with `python -m pip install -e '.[dev]'`, `python -m pytest tests/test_package.py`, and `nginx-lens --help`. Record actual outcomes, changed paths, and the next step in project memory.

Expected outcome: an installable scaffold, not placeholder reports. Suggested commit: `step-1: establish package and data contracts`.

## Prompt 2: Reader and Parser

> Implement only Step 2 after checking Step 1 evidence. Create reader.py and parser.py with bounded binary reading and combined-log parsing. Enforce the 65,536-byte physical-line limit, LF/CRLF and final-line rules, strict UTF-8, nginx hex escaping, calendar/offset validation, canonical IPv4/IPv6, valid request and 100–599 status. Do not use locale-dependent month parsing. Test overlong-line draining without allocating the remainder and UTC day crossings. Add the planned fixtures plus tests/test_reader.py and tests/test_parser.py. Run `python -m pytest tests/test_reader.py tests/test_parser.py`; record failures honestly and keep raw log lines out of diagnostics.

Expected outcome: validated LogRecord values and explicit malformed-record results. Suggested commit: `step-2: parse combined logs with bounded reads`.

## Prompt 3: Exact Metrics

> Implement only Step 3. Build aggregate.py and tests/test_aggregate.py from PRD AC1–AC8. Maintain complete exact counters until EOF; calculate top ten deterministically, not from a truncated running candidate list. Use raw decoded request targets including queries and separate 4xx/5xx counts. Verify `A,A,B,-` gives two known agents and 50% for four valid requests. Verify 3/4 requests in an hour gives 75%, all 24 buckets exist, and zero denominators yield zero. Run `python -m pytest tests/test_aggregate.py` and record evidence.

Expected outcome: a report model whose values are independent of renderer choice. Suggested commit: `step-3: calculate exact traffic and error summaries`.

## Prompt 4: Capacity Guards

> Implement only Step 4. Enforce combined key-count and UTF-8 key-byte budgets in aggregate.py with a dedicated capacity exception. Preflight every new key in a record before changing any totals. Repeated keys at capacity remain valid; the same text in different collections consumes separate entries/bytes. Unknown UA values consume no UA entry. Add tests/test_limits.py for exact cap, next-key rejection, UTF-8 widths, and multi-key atomicity. Run `python -m pytest tests/test_limits.py tests/test_aggregate.py`. Preserve code 4 for unique-cardinality exhaustion when CLI integration occurs; do not substitute MemoryError as the normal capacity control.

Expected outcome: bounded exact aggregation or an explicit failure, never approximation. Suggested commit: `step-4: bound exact aggregation state`.

## Prompt 5: Output Formats

> Implement only Step 5. Create render.py plus tests/test_render.py and tests/test_export_schema.py. Implement the exact version-1 JSON keys and CSV header/sections from PROJECT_ARCHITECTURE.md. Produce all terminal sections with literal Rich text. Respect TTY, NO_COLOR, and --no-color; keep exports free of ANSI. Test JSON types, rounded numeric percentages, CSV quoting, escaped control characters, and formula-prefix protection while preserving raw keys in JSON. Run `python -m pytest tests/test_render.py tests/test_export_schema.py` and record schema comparison evidence.

Expected outcome: consistent metrics across human and machine formats. Suggested commit: `step-5: render terminal and pipeline reports`.

## Prompt 6: Integrated CLI

> Implement only Step 6. Connect cli.py to reader, parser, guarded aggregation, and rendering. Validate options before opening files; omitted input or '-' is stdin. Implement default skip-and-report and --strict, stdout/stderr separation, deferred report emission, broken pipes, interruptions, and first-fatal-error precedence. Test every exit 0/1/2/3/4 in tests/test_cli.py, including both configured capacity limits returning 4 with empty stdout. Inject mid-read and output failures. Run `python -m pytest tests/test_cli.py`, `nginx-lens --json tests/fixtures/combined.log`, and `cat tests/fixtures/combined.log | nginx-lens --csv -`. Record actual results and unresolved issues.

Expected outcome: a functioning finite-stream CLI with the documented failure contract. Suggested commit: `step-6: integrate streaming CLI and failure contract`.

## Prompt 7: Real Performance Evidence

> Implement only Step 7. Create benchmarks/generate.py, benchmarks/run.py, benchmarks/README.md, and tests/test_hostile_input.py. Follow the exact architecture benchmark profile, one warmup and three measured warm-cache repetitions, with independent expected-count validation outside timing. Record laptop/OS/runtime metadata, input bytes, elapsed time, peak RSS, and exit status. Run `python -m pytest tests/test_hostile_input.py`, `python benchmarks/generate.py --bytes 1000000000 --seed 42 --output .benchmark/reference.log`, and `python benchmarks/run.py --input .benchmark/reference.log --runs 3 --max-seconds 30 --max-rss-mib 512 --output benchmarks/results.json`. Each measured run must be under 30 seconds, not merely the average. Profile before optimizing. A failed goal blocks release; record it without weakening the fixture or silently changing architecture.

Expected outcome: real performance and hostile-input evidence. Suggested commit: `step-7: measure throughput and adversarial input boundaries`.

## Prompt 8: Local Release Candidate

> Implement only Step 8 after checking all prior evidence. Create tests/test_wheel_install.py and a Python 3.11 correctness/build workflow, update user docs with actual behavior, and build a local wheel. Smoke-test installation in a temporary fresh venv, help/version, file/stdin, and all report formats. Run `python -m pytest --cov=nginx_lens.parser --cov=nginx_lens.aggregate --cov-branch --cov-fail-under=90`, `python -m build`, and `python -m pytest tests/test_wheel_install.py`. Record code/security reviews and benchmark outcome; do not publish to a package registry or fabricate review approval. Update CLAUDE.md and .itd-memory/STATE.json only from evidence, preserve all five exit codes, and identify the next action.

Expected outcome: locally tested wheel ready for a release decision. Suggested commit: `step-8: prepare verified local wheel and handoff`.

## Session Handoff

At the end of each session or significant block of work, save context through `/session-save`. Record changed files, exact checks and outcomes, outstanding failures, active step, and next action. If the command is unavailable, persist the same information in `.itd-memory/STATE.json` and an evidence note; do not claim the skill ran. Keep `.itd/VERIFICATION_CONTRACT.json` authoritative and never infer independent approval from self-checks. Review the external harness artifact when it becomes available; do not create it yourself in the blueprint session.
