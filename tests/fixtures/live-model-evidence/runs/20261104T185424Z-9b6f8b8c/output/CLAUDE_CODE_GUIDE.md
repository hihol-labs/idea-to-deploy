# Claude Code Implementation Guide: Nginx Lens

This is a future execution guide, not an implementation or review report. Begin with [CLAUDE.md](CLAUDE.md), [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), and [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). [README.md](README.md) describes the intended installed experience. Keep agent rules centralized in CLAUDE.md.

## Shared Prompt Contract

For every prompt below: implement only its named step, write meaningful tests, run them, and report observed outcomes. Preserve Python 3.11, Click, Rich, dataclasses, local-only processing and no persistent state. Preserve exact top ten, UTC hours, query-stripped error URL keys and exact nonmissing-UA identity. No auth, DB, HTTP API, server, cloud, Kubernetes, or product telemetry. Read the spec before editing; update it first if behavior must change.

Every step must preserve the complete exit contract **0/1/2/3/4**:

| Code | Meaning |
|---|---|
| 0 | Clean complete report, empty input, help/version |
| 1 | Operational/I/O/output failure, broken pipe, internal failure or interruption |
| 2 | Invalid CLI usage/options |
| 3 | Report complete with malformed lines skipped, including all-malformed input |
| 4 | unique-cardinality exhaustion; no report |

The lowercase diagnostic category is `unique-cardinality exhaustion`.

Input-time fatal failures emit no report; output failures may leave unusable partial stdout and must exit 1. Usage validation happens first; first fatal runtime failure overrides malformed status. Do not omit code 4 or inherit a framework's conflicting default. Hourly percentage is `100 × hourly_request_count / total_valid_requests`; unique-UA share is `100 × distinct_nonmissing_user_agents / total_valid_requests`; zero denominators produce zero. Round percentages only at rendering.

## Prompt 1: Package and Contracts

“Execute implementation step 1. Create pyproject.toml, the src/nginx_lens package, cli.py, models.py, and tests/test_cli_contract.py with the small fixture. Implement console installation, help/version, mutually exclusive output flags and positive key-cap validation. Follow the architecture's exact field and exit definitions. Run the step's install/help/tests and show evidence. Do not begin step 2 or publish anything.”

## Prompt 2: Streaming Parser

“Execute step 2 after step 1 is green. Create input.py and parser.py plus test_input.py and test_parser.py. Support only the specified combined grammar. Bound physical reads, drain oversized lines once, decode strict UTF-8, validate addresses/status/timestamps, handle nginx escapes, and normalize URL query removal. Verify stdin/file parity and timezone-boundary cases with the documented pytest command.”

## Prompt 3: Aggregation

“Execute step 3. Implement aggregate.py and test_aggregate.py. Use exact dictionaries/set, UTC hour counts, heap-based deterministic top ten, and the combined IP/error-URL/UA entry budget. Preflight new keys atomically and fail with code 4 before rendering on exhaustion. Demonstrate repeated keys at the cap succeed. Match the PRD's hand-calculated fixture and shuffled-order equivalence; run tests.”

## Prompt 4: Terminal Output

“Execute step 4. Implement the Report-based Rich renderer in render.py, connect CLI default output and add test_terminal.py. Include totals and all four metrics; respect TTY, NO_COLOR and --no-color. Render user fields literally and escape controls. Check that warnings use stderr. Run terminal tests without changing report semantics.”

## Prompt 5: JSON

“Execute step 5. Add the schema_version=1 JSON serializer and tests/test_json.py. Emit exactly one object with the architecture's keys, types, ordered arrays and 24 hour entries. Check no ANSI/prose pollution, zero-input behavior, percentage rounding and numerical parity. Run JSON tests.”

## Prompt 6: CSV

“Execute step 6. Add standard-library CSV serialization and tests/test_csv.py. Use the exact section,key,count,errors_4xx,errors_5xx,percentage header, fixed row order and empty irrelevant cells. Test round trips with difficult field values and parity against JSON. Run CSV tests.”

## Prompt 7: Failures and Integration

“Execute step 7. Complete CLI exception mapping and add subprocess test_integration.py. Exercise all codes 0/1/2/3/4 across all formats, including invalid options, empty/all-malformed input, missing file, cap overflow, broken pipe, interrupted input and write failure. Assert stdout suppression before render and nonzero status for partial write failure. Run the integration tests and full coverage command; report real parser/aggregate coverage.”

## Prompt 8: Performance and Local Package

“Execute step 8. Implement the deterministic benchmark generator and runner with the documented flags and write measured RESULTS.md. Time three complete 1,000,000,000-byte runs, record peak RSS and machine/cache conditions, and test high-uniqueness exit 4. Profile if needed; keep exact semantics. Run the full suite, build a wheel, and test a fresh local installation. Update README examples and MIT license metadata. Do not upload, push, deploy, or claim review occurred without real review evidence. Record any unmet release gate explicitly.”

## Verification and Recovery

Use the commands in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). On failure, reproduce with the smallest fixture, fix only that step, rerun the failed tests and affected suite, and record actual output. Performance claims require the benchmark record; document checks are not product tests. Do not change fixture expectations to hide a defect. Default project state is unimplemented; none of these prompts has been executed.

Save continuity through `/session-save` at the end of each significant block. No commit with a red test layer; no irreversible or external action without human authorization. The separate external harness handles architecture adversarial review; this guide does not supply or assert such a verdict.
