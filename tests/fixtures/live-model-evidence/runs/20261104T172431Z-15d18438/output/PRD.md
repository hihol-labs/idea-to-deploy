# Product Requirements: Nginx Lens

## Problem and outcome
DevOps/SRE engineers need a reproducible summary of local nginx logs without provisioning an analytics service. Success means exact incident triage metrics and pipeline-safe output within the approved weekend and $0 cash budget. [Strategy](STRATEGIC_PLAN.md) defines positioning; [architecture](PROJECT_ARCHITECTURE.md) specifies the executable contract.

## Scope and priorities
P0 = Must: combined file/stdin input, all four metrics, terminal/JSON/CSV, bounded exact state, malformed-data diagnostics and exit codes. P1 = Should: gzip input after MVP. P2 = Could: completions. Won't: auth, DB, HTTP, server, cloud, Kubernetes, follow mode, custom format DSL. Product choices are pre-approved; no discovery confirmation is pending.

## User Stories
- As a DevOps engineer, I want explicit malformed-data diagnostics so I can trust automated analysis. Priority: P0.
  - Acceptance: mixed input skips bad lines with an stderr count and exit 0; strict abort returns 3 with empty stdout; nonempty input with no valid records returns 3; empty input returns a zero report and 0.
- As a responder, I want a colored terminal report so I can read the four metrics during an incident. Priority: P0.
  - Acceptance: terminal output labels UTC and percentages; non-TTY, NO_COLOR, and --no-color disable ANSI; untrusted fields cannot invoke Rich markup or terminal controls.
- As an SRE, I want to read a file or stdin incrementally so I can analyze large logs locally. Priority: P0.
  - Acceptance: omitted input and `-` read stdin; one plain file works; 64 KiB line limit is enforced without reading an unbounded line; file-open failure returns 1.
- As an on-call engineer, I want exact top-10 IPs and error URLs so I can identify traffic and failure hotspots. Priority: P0.
  - Acceptance: IP ranking includes all valid requests; URL ranking includes only 400–599 and displays 4xx/5xx counts; query strings are removed; ties sort key ascending; at most ten entries; late winners remain correct.
- As a capacity engineer, I want hourly percentages so I can identify concentrated traffic. Priority: P0.
  - Acceptance: timestamps normalize to UTC; all dates combine into 24 hour-of-day buckets; each percentage is `100 × hourly_request_count / total_valid_requests`; empty input produces zero percentages; rounded display may sum slightly away from 100.
- As an SRE, I want unique User-Agent share so I can see diversity of reported clients. Priority: P0.
  - Acceptance: share is `100 × unique_user_agents / total_valid_requests`; repeated exact strings count once; empty and `-` UAs do not enter the set; valid requests with missing UA remain in denominator. Three valid requests containing A, A, B yield two unique UAs and about 66.67%.
- As an automation engineer, I want stable JSON and CSV so I can compose shell pipelines. Priority: P0.
  - Acceptance: formats describe the same Report and invalid count; mutually exclusive switches return 2; machine stdout has no banners/ANSI; CSV quoting round-trips and JSON parses; broken output pipe returns 1.
- As a laptop operator, I want a distinct cardinality failure so I can avoid misleading approximate results. Priority: P0.
  - Acceptance: cap+1 distinct IPs, error paths, or UAs each returns 4 with no report; repeated keys at cap succeed; no hidden evictions; --max-unique must be positive.
- As an operator, I want compressed archive input so I can avoid manual decompression. Priority: P1, deferred; future acceptance requires gzip/plain metric parity and explicit format selection semantics before implementation.
- As a frequent CLI user, I want shell completions so I can discover options quickly. Priority: P2, deferred; future acceptance requires completion output matching actual options.

Stories are ordered by strategic RICE where possible; parser/model dependencies precede complete rendering in implementation.

## Functional contract
Command, schema and parser details are authoritative under architecture's `CLI Interface`. Exit codes are 0 success/help/version; 1 IO/output/runtime failure; 2 usage; 3 invalid log data; 4 unique-cardinality exhaustion. Default cap: 100000 distinct values independently for IP, error URL and UA collections. Valid records use nginx combined format; custom JSON/common formats are unsupported.

## Nonfunctional requirements
Python 3.11, Click, Rich and dataclasses; local pip installation. No network or telemetry. Process 1 GB (decimal) under 30 seconds on a documented laptop using the architecture benchmark profile; correctness and bounded failures hold on other profiles but speed is not promised universally. State survives only one invocation; memory grows with distinct keys until explicit caps. Benchmark and tests are required implementation evidence and have not run in this planning session.

## Kill and release criteria
Do not release if any P0 fixture is wrong, schema differs across formats, a fatal parse/cap failure emits a success report, exit 4 is lost, raw log diagnostics leak sensitive content, or benchmark target fails. If a weekend cannot resolve these, stop release and report evidence; do not weaken exactness silently. P1/P2 cannot delay P0 validation.

## Verification and handoff
Implement [eight steps](IMPLEMENTATION_PLAN.md) using [guide prompts](CLAUDE_CODE_GUIDE.md). Keep [CLAUDE.md](CLAUDE.md) step status grounded in actual test results. Independent adversarial review is external and pending; this document makes no reviewer claim.
