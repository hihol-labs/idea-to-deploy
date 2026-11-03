# Claude Code Guide: nginx-logstats

## Working Contract
Read [CLAUDE.md](CLAUDE.md), [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) first. These prompts are for later implementation; this blueprint session creates documentation only. Keep contributor instructions centralized in CLAUDE.md. Amend the specification before changing product behavior. Use one step at a time and preserve the exact CLI schema.

Every implementation prompt below inherits the complete exit-code contract `0/1/2/3/4`: 0 clean success/help/version/empty input; 1 I/O/runtime failure, broken pipe or interrupt; 2 usage error; 3 complete valid-record report after malformed lines; 4 unique-cardinality exhaustion with no report.
The case-sensitive term for code 4 is unique-cardinality exhaustion.
Immediate terminal failures override accumulated malformed counts; write failures return 1. Never silently approximate metrics or omit code 4. No auth, database, API, server, cloud, Kubernetes, or publication work is authorized by these prompts.

## Step 1 Prompt: Package Runway
“Implement only step 1 of IMPLEMENTATION_PLAN.md. Create the setuptools src-layout package, Click help/version, module entry point, dev extras, and package tests at the exact planned paths. Run that step's verification commands. Report actual results, files changed, and remaining work; preserve the shared exit contract. Do not publish.”

## Step 2 Prompt: Parser
“Implement only step 2. Use typed dataclasses and an anchored nginx combined parser with the exact field/escape/date/address rules in PROJECT_ARCHITECTURE.md. Add hand-calculated valid and malformed fixtures, including quoted User-Agents and IPv6. Do not derive expected results by calling the implementation. Run parser tests and report evidence.”

## Step 3 Prompt: Metrics and Limits
“Implement only step 3. Count exact IPs, combined 400–599 URL errors, 24 logged-local-hour buckets and distinct User-Agent strings. Hourly percentage must be 100 × hourly_request_count / total_valid_requests. Unique-agent share must be 100 × unique_user_agents / total_valid_requests. Define zero denominators as zero, preserve deterministic ties and raw keys, and enforce combined K atomically. Test code-4 exhaustion boundaries without truncation or approximation. Run the planned aggregation and limits tests.”

## Step 4 Prompt: Streaming CLI
“Implement only step 4. Connect binary file/stdin reading, bounded oversized-line draining, malformed counts, Click validation and stderr diagnostics. Test every code in 0/1/2/3/4, with no report for unique-cardinality exhaustion and a complete valid-record report for code 3. Test I/O failures and broken pipe. Do not load an entire file or echo raw log records. Run reader and CLI-error tests.”

## Step 5 Prompt: Terminal
“Implement only step 5. Render all required sections with Rich and readable two-decimal percentages. Escape untrusted markup/control characters, disable ANSI for redirected stdout and --no-color, and test both TTY and redirected behavior. Run the planned terminal tests and fixture command.”

## Step 6 Prompt: Exports
“Implement only step 6. Add schema-version-1 JSON and the exact CSV column/row contract from Architecture CLI Interface. Preserve raw keys using standard serialization, keep stdout clean, and test flag conflict, quoting, malformed input and exhaustion through subprocesses. Verify codes 0/1/2/3/4 and machine-format agreement against independent expected data. Run export and CLI suites.”

## Step 7 Prompt: Performance
“Implement only step 7. Generate the exact 1,000,000,000-byte fixture and independent counter oracle, benchmark the installed CLI through completed output, and record hardware/software, cache policy, durations and peak RSS. Execute the cold and warm protocols plus near-cap and over-cap scenarios. Optimize only from profiles. Clearly state whether the under-30-second and memory targets were measured and met; do not infer success from file size alone.”

## Step 8 Prompt: Local Candidate
“Implement only step 8. Run the complete tests with branch coverage, build and install a wheel in a clean Python 3.11 environment, and run installed CLI checks. Update documentation to actual behavior and benchmark results. Inspect package contents and save context. Report remaining gates honestly. Keep the candidate local; commits follow project rules and push/publication require separate confirmation.”

## Troubleshooting and Handoff
On malformed-only input expect code 3 with an otherwise empty report, not code 0. On exhaustion lower input cardinality or explicitly raise the cap with a known memory budget; never replace exact keys with sketches. On a slow benchmark profile parser CPU and allocations before adding concurrency. Tests and benchmark commands are future instructions, not evidence of runs in this session.

At each milestone use `/session-save`, retaining actual check results, current step and one precise next action. The external harness performs this blueprint's adversarial review separately; this guide does not record a review verdict.
