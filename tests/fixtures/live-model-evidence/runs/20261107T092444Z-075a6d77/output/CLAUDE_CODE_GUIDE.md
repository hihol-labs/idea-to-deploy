# Claude Code Guide: Nginx Lens

This guide is for future implementation, not evidence of implemented functionality. Read [CLAUDE.md](CLAUDE.md), [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) first. [README.md](README.md) describes the intended operator flow.

## Contract for Every Prompt

Use Python 3.11, Click, Rich, and dataclasses. Implement one step at a time, with tests; run the named tests and report actual output. Do not introduce a server, auth, DB, HTTP API, cloud, Kubernetes, or persistence. Do not publish, push, or deploy without later explicit approval.

Preserve complete exit codes **0/1/2/3/4**: 0 success (including empty input and help/version); 1 I/O/internal/broken-pipe/interruption failure; 2 usage; 3 strict parsing failure or nonempty stream with no valid records; 4 unique-cardinality exhaustion.

The exact lowercase contract term is unique-cardinality exhaustion and must remain code 4.

Diagnostics use stderr; input processing must finish before any successful report is emitted. Output write failure may leave partial bytes. Never silently approximate exact keys. Hourly percentages use `100 × hourly_request_count / total_valid_requests`; distinct-UA share uses `100 × distinct_nonmissing_user_agents / total_valid_requests`. Hours are the logged local hour-of-day across dates/offsets. No valid requests means zero percentages.

## Prompt 1: Package and Fixtures

> Execute only implementation step 1. Create pyproject.toml, the src/nginx_lens package entry points, dataclasses, and synthetic fixture/oracle files at the paths specified in IMPLEMENTATION_PLAN.md. Configure dev tests and the console command. Preserve the shared 0/1/2/3/4 exit contract. Run `python -m pip install -e '.[dev]'`, `python -m pytest tests/test_packaging.py`, and `python -m nginx_lens --help`. Report actual results and files changed; do not implement later steps.

## Prompt 2: Streaming Parser

> Execute only step 2. Implement reader.py and parser.py with bounded 64 KiB physical lines and incremental oversized-line draining. Test quoted escapes, IPv6, numeric timezone offsets, final lines, blank lines, malformed UTF-8, and missing request/UA policy. Never buffer the whole input. Run `python -m pytest tests/test_reader.py tests/test_parser.py`; preserve the complete shared exit contract when integrating later.

## Prompt 3: Exact Aggregation

> Execute only step 3. Implement aggregate.py and the Report model. Count IPs, 400–599 URL errors, 24 logged hour buckets, and nonmissing distinct UAs. Apply the shared-key budget before mutating a record's counters, with default 100000 and code 4 on exhaustion. Use bounded top-10 selection and deterministic key tie-breaking. Test independent oracle values, raw query strings, repeated/missing UAs, hours across dates/offsets, all-zero input, and at/over-limit behavior. Run `python -m pytest tests/test_aggregate.py`.

## Prompt 4: CLI and Error Mapping

> Execute only step 4. Wire file/stdin input, --strict, --json, --csv, --max-unique, --color, --help, and --version according to the exact CLI Interface section. Test every exit 0/1/2/3/4 including explicit color/export conflicts, interruptions, malformed-only input, and reader errors. Keep raw lines out of diagnostics. Override library defaults where needed to match the specified exits. Run `python -m pytest tests/test_cli.py` and `python -m nginx_lens --version`.

## Prompt 5: Machine Exports

> Execute only step 5. Add JSON schema version 1 and the single long-form CSV table in renderers.py. Preserve numeric types, deterministic row order, missing values, two-decimal round-half-even percentages, and Unicode/CSV quoting. Add round-trip tests and broken-pipe failure coverage. No warnings or ANSI on machine stdout. Run `python -m pytest tests/test_exports.py` and the fixture JSON/CSV commands from the plan.

## Prompt 6: Human Output

> Execute only step 6. Add Rich tables showing all four metrics and input-quality totals. Honor TTY/NO_COLOR and explicit color settings. Treat input as untrusted plain text, escape terminal controls, and avoid Rich markup interpretation. Test both forced and disabled color, empty reports, and malicious-looking keys. Run `python -m pytest tests/test_terminal.py` and inspect the fixture text output in a TTY.

## Prompt 7: Measure Capacity

> Execute only step 7. Build synthetic benchmark generation and timing/RSS tooling at the specified paths. Keep fixtures under 100000 shared distinct keys for the performance target, and test separate over-limit failures as code 4. Generate exactly 1000000000 input bytes outside timing. Run the full coverage suite and three warm-cache end-to-end JSON benchmark runs. Record hardware, Python/OS, fixture profile, each duration, median, and peak RSS in bench/RESULTS.md. Report failure honestly if <30 seconds or <512 MiB is not met; profile before proposing architecture changes.

## Prompt 8: Install and Handoff

> Execute only step 8. Build a wheel, test its installation into a clean Python 3.11 venv outside the source directory, and verify command/module parity, all output modes, and exits 0/1/2/3/4. Finalize LICENSE and README. Run `python -m build`, `python -m pytest tests/test_wheel.py`, and `python -m pytest`. Update CLAUDE.md with actual evidence and save continuity through /session-save. Keep release blocked for unmet P0 criteria; package publishing requires separate approval.

## Session and Recovery Protocol

At the end of each meaningful block, use `/session-save` and record files, observed checks, unresolved failures, and one next action. If a check fails, fix within the active step and rerun it before advancing. Change the PRD/architecture first if a behavior change is needed. Do not record a suggested verification as executed. This blueprint session runs no product tests and no independent or adversarial review; the latter belongs to the external harness.
