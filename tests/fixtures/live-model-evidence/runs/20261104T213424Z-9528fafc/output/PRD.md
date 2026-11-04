# Product Requirements: nginx-scan

## Problem and outcome

DevOps/SRE engineers need a repeatable local summary of nginx access logs without installing monitoring services. Success is a correct, pip-installable CLI producing the four requested metrics within the declared performance target. See [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for audience, roadmap and budget.

## User Stories

- As a DevOps engineer, I want to stream a file or stdin through a combined-log parser so that I can inspect large logs without loading the file into memory. Priority: P0 (Must), RICE 160.
  Acceptance criteria: file and stdin produce equal reports; missing trailing newline works; malformed/invalid UTF-8 lines are counted and skipped; no whole-file read occurs; unsupported formats are not silently guessed.
- As a SRE, I want the top-10 IPs and error URLs so that I can identify heavy clients and failing request targets. Priority: P0 (Must), RICE 133.33.
  Acceptance criteria: IP counts include all valid statuses; URL counts combine only 4xx/5xx; ties sort lexically; results contain at most ten entries; query strings remain distinct; fixtures with more than ten keys prove truncation.
- As a SRE, I want hourly percentages and unique User-Agent share so that I can compare traffic shape and client diversity. Priority: P0 (Must), shared metrics RICE 133.33.
  Acceptance criteria: hourly percentage is `100 × hourly_request_count / total_valid_requests`; 24 UTC buckets collapse across dates; offsets crossing midnight map correctly; User-Agent share is `100 × distinct_known_user_agents / total_valid_requests`; unknown `-` agents are excluded from the set; zero denominators produce 0.0.
- As an on-call engineer, I want bounded resource handling and explicit failures so that a high-cardinality input cannot silently corrupt the summary. Priority: P0 (Must), RICE 106.67.
  Acceptance criteria: total distinct-entry limit is configurable and checked before record mutation; exceeding it returns 4 without a report; oversized lines are drained with bounded buffers and counted once; no approximate fallback is used.
- As an on-call engineer, I want readable colored terminal tables so that I can interpret results quickly during an incident. Priority: P0 (Must), RICE 96.
  Acceptance criteria: default TTY output uses Rich color; redirects, NO_COLOR and --no-color remove ANSI; log-controlled markup/control bytes cannot inject terminal commands; all summary fields and four metrics are visible.
- As a platform engineer, I want pip installation so that I can run the command in an existing Python environment. Priority: P0 (Must), RICE 90.
  Acceptance criteria: a locally built wheel installs in a clean virtual environment; --help and --version exit 0; the installed console command runs a fixture without source-path imports.
- As a platform engineer, I want JSON and CSV so that I can integrate the report into shell pipelines. Priority: P0 (Must), RICE 85.33.
  Acceptance criteria: flags are mutually exclusive; JSON parses as schema version 1; CSV round-trips commas, quotes and newlines; each output exposes equivalent counts/percentages; stderr warnings never contaminate stdout.
- As a site operator, I want gzip input so that I can inspect rotated archives directly. Priority: P1 (Should), RICE 36; deferred after MVP. Acceptance: future decompression matches the uncompressed report and preserves resource limits.
- As a SRE, I want configurable top-N so that I can explore more clients. Priority: P2 (Could); deferred. Acceptance: a future explicit positive N changes ranking length without altering metric semantics.

## Functional requirements

P0 comprises combined-only UTF-8 file/stdin streaming, exact metrics, terminal/JSON/CSV renderers, pip packaging, diagnostics and complete exit handling. The [architecture](PROJECT_ARCHITECTURE.md#cli-interface) defines the authoritative commands, options, schemas and exit codes: 0 success, 1 internal failure/interruption, 2 usage, 3 I/O, 4 unique-cardinality exhaustion. All-malformed nonempty input succeeds with an empty report and stderr warning; total_lines equals valid plus malformed lines.

P1 is gzip support after the weekend. P2 is configurable top-N. No deferred feature is a dependency of P0 acceptance. Stories are ordered by RICE except dependency foundations in the implementation plan.

## Worked acceptance fixture

Four valid requests: 00 UTC has three, 01 UTC has one; all other hours have zero. Their UAs are `A`, `A`, `B`, `-`: unique known UAs=2; share=50%; hourly percentages=75% and 25%. If `/fail?q=1` receives statuses 404 and 500 it has error count 2; a 200 for that same target adds no error. A malformed fifth line leaves the denominator at four and sets malformed_lines=1. Fixture timestamps must include offset conversion and dates spanning midnight in additional cases.

## Nonfunctional requirements

- Python 3.11, Click, Rich and dataclasses; local, one process, no persisted processing state.
- Target 1,000,000,000 input bytes in <30 seconds on a declared laptop, measured as specified in architecture; not yet verified.
- Exact integer counts; deterministic ranking/schema; six-decimal machine percentages, two-decimal terminal percentages.
- Default 250,000 combined distinct entries and 65,536-byte line limit; finite guards are documented rather than a constant-memory claim.
- $0 cash budget and approximately 16 hours over one weekend. Local input never leaves the process through a network request.

## Out of scope

Auth, databases, HTTP APIs, servers, cloud, Kubernetes, custom log grammars, dashboards, live tailing, geolocation, UA interpretation, approximate metrics and production log changes. No public upload or product implementation is part of this blueprint session.

## Kill criteria and release gate

Stop release if a metric fixture disagrees, the installed command fails, an export cannot be parsed, resource exhaustion produces a successful partial report, or any declared benchmark trial exceeds 30 seconds. Profile or reduce deferred scope; never silently weaken exactness or reclassify a failed measurement as passing. If throughput remains infeasible within the weekend, record the failed target and seek a later scope decision. No implementation/test/performance/review completion is asserted now.

## Traceability

Stories 1–4 map to implementation steps 2, 3 and 6; terminal story to step 4; packaging to steps 1 and 8; pipeline story to step 5; performance to step 7. [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) supplies the execution prompts; [CLAUDE.md](CLAUDE.md) tracks their pending status.
