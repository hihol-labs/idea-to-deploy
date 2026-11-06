# PRD: Nginx Lens

## Product and Scope
Local Python 3.11 CLI for DevOps/SRE engineers investigating nginx access logs. Stream one combined-format file or stdin, then show top-10 IPs, top-10 error URLs, hourly request percentages and unique User-Agent share. [Architecture](PROJECT_ARCHITECTURE.md) specifies schemas and boundary behavior; [strategy](STRATEGIC_PLAN.md) records MoSCoW/RICE; [plan](IMPLEMENTATION_PLAN.md) and [guide](CLAUDE_CODE_GUIDE.md) describe delivery.

## User Stories
Stories follow RICE order after verification scaffolding; all listed stories are P0/Must.

- As a DevOps engineer, I want combined logs parsed incrementally so that I can analyze a large local file without loading it into memory.
  Acceptance: valid quoted combined records and IPv6 parse; invalid UTF-8 and malformed/oversized records are counted once each and skipped; file and stdin return identical results; no whole-file buffering.
- As a responding SRE, I want the ten busiest IPs and ten URLs with the most 4xx/5xx errors so that I can identify traffic sources and failing routes.
  Acceptance: IP counts use all valid requests; URL counts combine 400–599 only; query strings remain distinct; rankings sort count descending and key ascending with at most ten entries; exact counts stop with exit 4 on cap exhaustion.
- As a duty engineer, I want a UTC hourly distribution and unique User-Agent share so that I can spot traffic patterns.
  Acceptance: all 24 UTC bins appear; hourly percentage is `100 × hourly_request_count / total_valid_requests`; UA share is `100 × unique_user_agents / total_valid_requests`; missing/empty UA is excluded from numerator; zero denominator yields 0; distinct means exact case-sensitive strings.
- As a shell user, I want a predictable command and exit status so that I can automate incident analysis reliably.
  Acceptance: file path, omitted input and `-` work; 0 success, 1 I/O/internal failure, 2 usage, 3 nonempty input with no valid records, 4 unique-cardinality exhaustion; diagnostics go to stderr; no report for consumption failures.
- As a terminal user, I want readable colored tables so that I can inspect results quickly.
  Acceptance: default TTY output uses Rich color; --no-color, NO_COLOR and redirected text disable it; malicious control sequences/markup are rendered safely; all metric sections appear.
- As a pipeline author, I want JSON and CSV output so that downstream tools can consume the same report without terminal formatting.
  Acceptance: --json and --csv are exclusive; schema v1 matches architecture; CSV quotes embedded delimiters/newlines; no ANSI output; counts and percentages agree across formats.

## Functional Requirements
| Priority | Requirement | Delivery |
|---|---|---|
| P0 / Must | Bounded combined parser and exact four-summary report | Weekend |
| P0 / Must | File/stdin, colored text, JSON, CSV, complete exit contract | Weekend |
| P0 / Must | Key cap, deterministic ordering, correctness/performance evidence | Weekend |
| P1 / Should | gzip input | After MVP |
| P2 / Could | Custom nginx format definitions | Future consideration |

## Nonfunctional Requirements
Target 1 GB (1,000,000,000 bytes) under 30 seconds on the recorded laptop and representative bounded-cardinality fixture, peak RSS <=512 MiB, as specified in architecture. Keep one synchronous process and no persistent state. Support Python 3.11 and pip installation. No telemetry, credential handling or network calls. Treat log strings as untrusted data. Memory grows with distinct keys up to the explicit cap; never advertise constant memory for arbitrary cardinality.

## Acceptance Fixture
Build a six-valid-record fixture: three requests from 192.0.2.1, two from 192.0.2.2 and one from 192.0.2.3. Three error requests target `/bad` twice (404 and 500) and `/other` once (503); other requests succeed. Four timestamps normalize to UTC hour 10, two to hour 11, including a nonzero-offset timestamp. Use UA `A` twice, `B` twice, and `-` twice. Append one malformed line.

Expected: valid=6, malformed=1; IP counts 3/2/1; error URLs `/bad`:2 and `/other`:1; hour 10=66.67%, hour 11=33.33%, all other hours=0; unique UAs=2 and share=33.33%. All formats must match. Additional fixtures cover empty byte stream (0), nonempty all-invalid (3), option conflict (2), unreadable path (1), and a low key cap (4 with no report). Fixtures and assertions are planned, not executed here.

## Out of Scope
Authentication, database, HTTP API, server, cloud, Kubernetes, live follow/dashboard, persistent history, approximate sketches, user tracking, automatic remediation and arbitrary nginx formats. No product code in this blueprint session.

## Kill Criteria
Do not label the MVP ready if exact fixture results disagree, memory exhaustion silently truncates metrics, or any required exit code is wrong. If representative performance remains above target after bounded optimization within the weekend, record the miss and defer release; obtain a later scope decision rather than claiming success. Cash costs above $0 or new infrastructure invalidate the current plan.
