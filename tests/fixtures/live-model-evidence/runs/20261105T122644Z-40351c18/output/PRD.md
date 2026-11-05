# Product Requirements: Nginx Lens

## Problem and Goal

DevOps/SRE engineers need a fast summary of nginx combined logs on a laptop without operating analytics infrastructure. Deliver four exact summaries in a pip-installable Python 3.11 CLI during one weekend for $0 cash cost. Product behavior is specified in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md); scope and ranking originate in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).

## User Stories

Stories follow descending RICE value subject to dependencies. Must=P0, Should=P1, Could=P2.

- As a pipeline author, I want explicit failures when exact unique-key limits are exhausted so that automation cannot accept silently approximate results. Priority: P0 (Must).
  Acceptance criteria: hitting a configured entry or key-byte limit exactly succeeds; the next new key beyond either limit exits 4 with a diagnostic and no report. Existing keys at the limit remain countable. No partial record mutation, approximation or eviction is allowed.
- As a DevOps engineer, I want to stream a combined log from a file or stdin so that I can inspect large exports without loading every record into memory. Priority: P0 (Must).
  Acceptance criteria: file and stdin yield identical metrics; malformed physical lines are counted once, skipped and produce exit 1; bounded reads handle oversized lines; empty input returns a zero report with exit 0.
- As a site reliability engineer on call, I want the ten busiest IPs and the ten URLs with the most 4xx/5xx errors so that I can identify concentrated traffic and failing requests. Priority: P0 (Must).
  Acceptance criteria: IPs include all valid requests; error URLs combine 400–599 only; query strings remain distinct; descending counts and lexical tie-breaks yield deterministic lists with at most ten rows.
- As a capacity engineer, I want hourly percentages and unique User-Agent share so that I can understand traffic concentration and client diversity. Priority: P0 (Must).
  Acceptance criteria: UTC conversion precedes bucketing; all 24 hours appear; hourly percentage is `100 × hourly_request_count / total_valid_requests`; UA share is 100 times distinct nonmissing UA strings divided by all valid requests. Zero denominators produce 0.0. Two copies of one UA across four valid requests produce 25% share, even if the other two UAs are missing.
- As a responder to incidents, I want a colored terminal summary so that I can read results quickly. Priority: P0 (Must).
  Acceptance criteria: default TTY rendering uses Rich; --no-color and redirection have no ANSI codes; untrusted log text is escaped; total_valid_requests and skipped_lines appear beside all four summaries.
- As a pipeline automation author, I want JSON and CSV output so that I can reuse the same analysis in pipelines. Priority: P0 (Must).
  Acceptance criteria: --json emits one schema-version-1 object; --csv emits the exact normalized header and row sections from the architecture; independently parsed outputs agree with the golden metrics. Mutually selecting formats exits 2 before input reads. stderr diagnostics do not contaminate stdout.
- As a platform operator, I want direct gzip-file input so that I can skip decompression commands. Priority: P1 (Should), deferred until after MVP; for now explicitly decompress into stdin.
- As a site reliability engineer, I want separate 4xx/5xx drilldowns so that I can compare client and server failures. Priority: P2 (Could), deferred; MVP ranks their combined counts.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Parse the exact combined grammar, nginx hex escapes, IPv4/IPv6 and offset timestamps described in architecture |
| FR-02 | P0 | One file or stdin, no retained records, final report at EOF |
| FR-03 | P0 | Exact top-10 IP and combined-error URL counts with stable ties |
| FR-04 | P0 | UTC hour-of-day counts and percentages, complete 24 buckets |
| FR-05 | P0 | Exact case-sensitive nonmissing UA cardinality and share |
| FR-06 | P0 | Rich text default, JSON/CSV alternatives and clean stdout |
| FR-07 | P0 | Positive configurable shared cardinality/key-byte quotas and bounded lines |
| FR-08 | P0 | pip wheel/console entry point and complete help |
| FR-09 | P1 | Future gzip convenience after MVP |
| FR-10 | P2 | Future status-family drilldown |

## Error and Output Acceptance

The complete exit contract is 0/1/2/3/4: 0 complete success or empty input/help/version; 1 completed report with malformed lines skipped; 2 usage error; 3 I/O/resource/interruption failure; 4 unique-cardinality exhaustion. Fatal codes 3/4 override a pending 1. No report for 2/4 or fatal input failure; output failure can leave a prefix that must be discarded. Defaults are 250000 total namespace entries and 67108864 stored unique-key UTF-8 bytes. No silent approximation is permitted. Missing agents are empty or `-`, excluded from the set but not the valid-request denominator.

## Nonfunctional Requirements

Correctness: golden fixtures include status 399/400/499/500/599, lexical ties, timestamp offsets crossing days, escaped fields, missing agents, invalid encoding and all-invalid input. Six-decimal machine percentages and two-decimal text may differ only by rounding.

Performance: 1,000,000,000 bytes in <30 seconds and <=512 MiB peak RSS on a recorded laptop, under the benchmark cardinality envelope in architecture. Test three end-to-end runs, including CLI startup and final JSON write, with recorded cache conditions. This is a release target, currently unmeasured. High-cardinality data may deliberately exit 4; benchmark success cannot be claimed by dropping keys or lines.

Safety and privacy: no telemetry, raw-log diagnostics, credentials, network calls or retained input. Treat terminal text and CSV cells as untrusted data. Test local files only with synthetic fixtures or separately authorized sanitized samples. OS file permissions control local access; application auth is unnecessary.

Portability: Python 3.11, UTF-8 input/output, local pip installation; correctness suite should run on supported laptop operating systems. RSS collection must document platform-specific measurement methods.

## Out of Scope

Authentication, database, HTTP API, server, cloud, Kubernetes, deployment, multi-user state, follow mode, multiple files per invocation, format DSL, compression autodetection, approximate counting and disk-spill persistence. P1/P2 are backlog scope, not weekend deliverables.

## Kill Criteria and Release Gate

- If the parser cannot implement a documented combined grammar reliably, narrow supported syntax explicitly before coding further; do not silently accept ambiguous data.
- If the final benchmark misses time or RSS after the allotted profiling step, withhold the performance claim and release acceptance; record measurements and propose a revised plan for human review.
- If arbitrary input requires unbounded memory, the design fails acceptance; retain explicit quotas and code 4 rather than remove guards.
- If P0 does not fit the weekend, defer P1/P2 and cosmetic polish; unresolved correctness or pipeline contracts block release.

Execute [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) using [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md). Blueprint documents are the source for implementation; they are not evidence that these gates have passed.
