# PRD: nginx-logstats

## Product and Problem
DevOps/SRE engineers need four consistent metrics from local nginx logs without deploying analytics infrastructure. MVP is a finite, stateless Python 3.11 command installed through pip. Product and MoSCoW decisions are pre-approved. See [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for positioning and priorities.

## User Stories
- As a SRE, I want combined nginx records parsed correctly so that malformed lines do not distort incident metrics.
  Priority: P0 / Must. Acceptance: quoted/escaped fields and IPv4/IPv6 fixtures parse as specified; malformed lines are counted once, excluded from all metric denominators, and cause code 3 after EOF with a complete valid-record report.
- As a on-call engineer, I want top-10 IPs, error URLs, hourly percentages, and distinct User-Agent share so that I can identify traffic concentration and failures.
  Priority: P0 / Must. Acceptance: golden counts match independently calculated expectations; 400–599 statuses contribute to error URLs; ties use key ascending; all 24 logged-hour buckets are emitted; empty input produces zeros and empty top lists.
- As a DevOps engineer, I want to read a file or stdin with predictable exit codes so that scripts can detect incomplete analysis.
  Priority: P0 / Must. Acceptance: omitted input and `-` read stdin; file input needs no seeking; codes 0/1/2/3/4 follow the architecture contract, including immediate code 4 without a report on cardinality exhaustion.
- As a terminal user, I want readable colored tables so that an incident summary is easy to scan.
  Priority: P0 / Must. Acceptance: default TTY output uses Rich; redirected output and `--no-color` have no ANSI; log strings cannot inject markup or control sequences; all metrics and malformed totals appear.
- As a pipeline author, I want JSON and CSV so that I can process results without scraping tables.
  Priority: P0 / Must. Acceptance: schema version 1 and exact documented CSV columns/row order; counts agree with terminal output; JSON preserves numeric percentages and CSV rounds to two decimals; both flags together return 2 before input reads; diagnostics appear only on stderr.
- As a local operator, I want bounded reads and explicit distinct-key exhaustion so that unusual input cannot silently consume unbounded memory or yield approximate metrics.
  Priority: P0 / Must. Acceptance: oversized lines drain without whole-line allocation; combined K defaults to 250000; a record crossing K is rejected atomically with code 4; a fresh process starts with empty counters.
- As a maintainer, I want pip installation and measured throughput so that I can use this tool during incidents.
  Priority: P0 / Must. Acceptance: a clean Python 3.11 environment installs the wheel; installed CLI integration tests pass; the reference 1 GB benchmark meets the under-30-second and memory protocol in the implementation plan.
- As a operator of custom nginx formats, I want explicitly selected extra formats so that I can reuse the same output contract.
  Priority: P1 / Should, deferred beyond MVP. Acceptance when scheduled: explicit format selection and format-specific fixtures; no silent auto-detection.
- As a frequent terminal user, I want shell completion so that options are easier to discover.
  Priority: P2 / Could, deferred. Acceptance when scheduled: completion lists the documented options and does not read logs.

## Functional Requirements
P0 = every Must feature; P1 = additional log formats; P2 = shell completion. Stories above follow the strategic RICE order, splitting aggregation from its resource guard for explicit acceptance.

Only valid requests count toward top IPs or denominators. URL is the literal request target including queries; error ranking combines 4xx and 5xx. Exact, case-sensitive User-Agent distinctness includes literal `-`. Hour buckets use logged local hour across dates and offsets. Hourly percentage is `100 × hourly_request_count / total_valid_requests`. Unique-agent share is `100 × unique_user_agents / total_valid_requests`. For example, four valid requests at hour 13 yield 100% at hour 13, and two distinct User-Agents yield a 50% share. Zero valid requests yield zero percentages. No fractions mislabeled as percentages.

The complete command/options/schema/exit contract is [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md#cli-interface). It is normative for implementation, including parsing limitations and combined-cardinality limits.

## Nonfunctional Requirements
- Python 3.11, Click, Rich, dataclasses, pip distribution; no runtime network calls or telemetry.
- Process input incrementally with bounded line buffers and capped exact-key state; never load the whole file.
- Process 1,000,000,000 bytes in under 30 seconds with peak RSS at most 512 MiB under the documented reference-laptop protocol. This target is not yet measured.
- Deterministic rank ties and serialization; JSON/CSV stdout remains machine parseable even with malformed input and code 3.
- No raw record contents in errors; log content is data, never executable code or Rich markup.

## Out of Scope
Authentication, databases, HTTP endpoints, servers, Docker, cloud, Kubernetes, persistent state, live tailing, compressed files, custom log formats in MVP, multi-file merging, geolocation, bot classification, dashboards, and approximate cardinality. No guarantee that unique User-Agents identify unique humans.

## Kill Criteria and Release Gate
Do not release if golden counts disagree, any exit code is missing/remapped, terminal injection is possible, default caps are ineffective, or the repeatable benchmark misses its threshold after the allocated optimization window. Report the miss and seek a future scope/target decision; never claim performance from an estimate. No production or external release occurs as part of documentation generation.

## Traceability
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) steps 2–3 cover parsing/metrics; step 4 input and exits; step 5 terminal; step 6 machine formats; steps 7–8 performance and packaging. [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) supplies prompts; [CLAUDE.md](CLAUDE.md) records project status; [README.md](README.md) describes future use.
