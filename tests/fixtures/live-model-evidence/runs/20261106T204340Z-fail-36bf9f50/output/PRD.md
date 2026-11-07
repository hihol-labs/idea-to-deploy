# PRD: Nginx Lens

## Problem and Goals
DevOps/SRE engineers need a fast local access-log summary during incidents and in pipelines. Deliver the four specified metrics with terminal, JSON and CSV output using the [architecture contract](PROJECT_ARCHITECTURE.md). Target one weekend and $0 cash; performance is a target awaiting implementation evidence.

## User Stories
Stories follow value ranking from [strategy](STRATEGIC_PLAN.md); shared input and safety dependencies apply first.

- As a SRE, I want top-10 client IPs and error URLs so that I can identify traffic sources and failing resources. Priority: P0 (Must).
  Acceptance: count all valid IPs and only 400–599 URL errors; sort descending count then ascending key; ties do not exceed ten; IPv4/IPv6 canonicalization follows architecture fixtures.
- As a DevOps engineer, I want exact results with explicit cardinality limits so that large or hostile logs fail predictably. Priority: P0 (Must).
  Acceptance: a record exceeding the aggregate distinct-entry cap produces exit 4 and no report; exactly at the cap succeeds; no eviction or approximation occurs.
- As a SRE, I want hourly request percentages so that I can spot traffic peaks. Priority: P0 (Must).
  Acceptance: UTC hours 00–23 always appear; use `100 × hourly_request_count / total_valid_requests`; two requests in an hour out of four total produce 50%; timestamps crossing a UTC date boundary are bucketed correctly.
- As a service maintainer, I want the unique User-Agent share so that I can assess client diversity. Priority: P0 (Must).
  Acceptance: two distinct UAs among four valid requests yield 50%; sentinel `-` counts once; empty input yields zero, not division failure.
- As a platform operator, I want file/stdin streaming and pip installation so that I can analyze exports without infrastructure. Priority: P0 (Must).
  Acceptance: equivalent file and stdin input produces identical reports; invalid lines are counted/skipped; all-invalid nonempty input exits 3; empty input succeeds; memory never retains the whole file.
- As a pipeline author, I want JSON and CSV alongside colored terminal output so that automation can consume stable results. Priority: P0 (Must).
  Acceptance: machine output matches schema version 1 and CSV contract; stdout contains no diagnostics/ANSI; conflicting flags exit 2; redirected terminal text has no color; CLI integration tests cover exits 0/1/2/3/4.
- As a new operator, I want troubleshooting examples so that I can resolve malformed-log and memory-limit failures. Priority: P1 (Should).
  Acceptance: examples explain the combined-only format and cap increase without claiming a memory guarantee.
- As a frequent shell user, I want completion so that invoking the command is quicker. Priority: P2 (Could); defer if the weekend budget is exhausted.

## Functional Requirements
P0: single-pass combined-log parsing; top rankings; UTC hourly percentages; exact unique-UA percentage; bounded-line and bounded-cardinality processing; file/stdin; terminal/JSON/CSV; full exit/status and packaging contract. P1: extended examples. P2: completion. All output definitions, option defaults and error precedence are normative in PROJECT_ARCHITECTURE.md.

## Nonfunctional Requirements
Python 3.11, Click, Rich, dataclasses; no external services; pip-installable. Target <30 seconds on a documented laptop for a decimal 1 GB fixture below the cap. Correctness takes precedence over optimization. Core branch coverage >=85%; all golden and integration fixtures pass. Treat terminal content as data and never execute log strings.

## Out of Scope
Authentication, database, HTTP API, server, cloud, Kubernetes, cross-run persistence, live follow mode, gzip, custom nginx formats, dashboards and approximate metrics. No product implementation or package publication in this blueprint session.

## Release and Kill Criteria
Release only after the [Definition of Done](STRATEGIC_PLAN.md) is evidenced. If profiling cannot meet the throughput target within the weekend, record the failing measurement and delay release rather than claiming success. Stop expansion if exactness requires approximation or new services; revisit scope explicitly. A cardinality failure is an expected explicit error, not a successful partial report.

## Delivery References
[Implementation plan](IMPLEMENTATION_PLAN.md), [guide](CLAUDE_CODE_GUIDE.md), [project memory](CLAUDE.md), and [quick start](README.md).
