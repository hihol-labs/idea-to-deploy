# PRD: logpulse

> Product requirements. Source of truth for behavior. Cross-references:
> [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md),
> [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).

## Problem

DevOps/SRE engineers need fast answers to four questions from a raw nginx access log —
who is hitting us most, what is failing, when does traffic peak, and how varied are the
clients — without standing up GoAccess/ELK or hand-crafting fragile `awk`. `logpulse`
answers exactly those four questions from a stream, in one command, with structured output
for pipelines.

## Goals

- One-pass, stateless analysis of an nginx access log (file or stdin).
- Four metrics: Top-10 IPs, Top-10 URLs by 4xx/5xx errors, hourly request distribution,
  unique-User-Agent share.
- Colored terminal output by default; `--json` and `--csv` for automation.
- 1 GB processed in under 30 seconds on a laptop.

## Non-goals (out of scope)

Real-time follow/dashboard, GeoIP/DNS enrichment, database/history persistence, HTTP API,
authentication, and any cloud/Kubernetes deployment. See the `Won't` rows in
[STRATEGIC_PLAN.md](STRATEGIC_PLAN.md#11-feature-roadmap-prioritization).

## User Stories

- As a on-call SRE, I want to run `logpulse analyze access.log` and immediately see the top-10 client IPs by request volume, so that I can spot an abusive or misbehaving source during an incident. (Priority: P0)
- As a DevOps engineer, I want the top-10 URLs ranked by 4xx/5xx responses, so that I can find which endpoints are actually failing without scanning the whole log by hand. (Priority: P0)
- As a capacity planner, I want an hourly request distribution shown as a percentage using the formula `100 × hourly_request_count / total_valid_requests`, so that I can see peak traffic hours as a share of total valid requests rather than as an unscaled fraction. (Priority: P0)
- As a security-minded SRE, I want the count and share of unique User-Agents, so that I can gauge client diversity and notice a single-agent flood, with a clear signal if unique-cardinality tracking is exhausted. (Priority: P0)
- As a pipeline author, I want `--json` and `--csv` output, so that I can feed logpulse results into `jq`, spreadsheets, or downstream automation. (Priority: P1)
- As a DevOps engineer, I want to pipe a compressed log via `zcat access.log.gz | logpulse analyze -`, so that I can analyze rotated logs without decompressing to disk first. (Priority: P1)
- As a team lead, I want stable, documented exit codes, so that my triage scripts can branch on success, input errors, and cardinality exhaustion deterministically. (Priority: P1)

## Functional requirements

### P0 (Must)

- **FR-1 — Streaming parse.** Read an nginx access log (combined format default) line by
  line from a file argument or stdin; parse each line into a typed record; skip and count
  malformed lines without aborting.
  - **Acceptance criteria:**
    - [ ] A valid combined-format line yields ip, timestamp, method, url, status, bytes, user_agent.
    - [ ] A malformed line is skipped and reflected in `skipped_lines`, not crashing the run.
    - [ ] Input can come from a path or from stdin via `-` / omitted argument.
- **FR-2 — Top-10 IPs.** Report the `--top` (default 10) most frequent client IPs by request count.
  - **Acceptance criteria:**
    - [ ] Output lists IPs in descending request count.
    - [ ] Ties are ordered deterministically (count desc, then IP asc).
    - [ ] Honors `--top N`.
- **FR-3 — Top-10 error URLs.** Report the `--top` URLs with the most 4xx/5xx responses
  (`400 <= status <= 599`).
  - **Acceptance criteria:**
    - [ ] Only 4xx/5xx responses contribute to the ranking.
    - [ ] Output lists URLs in descending error count.
    - [ ] 2xx/3xx-only URLs never appear.
- **FR-4 — Hourly distribution (%).** For each hour `0..23`, report the percentage
  `100 × hourly_request_count / total_valid_requests`.
  - **Acceptance criteria:**
    - [ ] Each hour shows a percentage (scaled by 100), not an unscaled fraction.
    - [ ] Percentages across 24 hours sum to ~100 (rounding tolerance).
    - [ ] `total_valid_requests` excludes skipped/malformed lines.
- **FR-5 — Unique User-Agent share.** Report the count of unique User-Agents and their
  share of valid requests; bound the tracking set by `--max-unique`.
  - **Acceptance criteria:**
    - [ ] `unique_ua_share = unique_user_agents / valid_requests` is reported as ratio and percent.
    - [ ] When the set hits `--max-unique`, the result is flagged truncated and the process exits `4`.
- **FR-6 — Colored terminal output.** Default output is colored Rich tables/bars; `--no-color`
  and `NO_COLOR` disable color.
  - **Acceptance criteria:**
    - [ ] Default run prints colored tables for all four metrics.
    - [ ] `--no-color`/`NO_COLOR` produce plain text.
- **FR-7 — JSON output.** `--json` emits one JSON object mirroring the report.
  - **Acceptance criteria:**
    - [ ] Output is a single valid JSON object on stdout.
    - [ ] Diagnostics go to stderr, keeping stdout pure JSON.

### P1 (Should)

- **FR-8 — CSV output.** `--csv` emits section-delimited CSV to stdout.
- **FR-9 — Stdin input.** `-` or omitted LOGFILE reads from stdin.
- **FR-10 — Exit-code contract.** Implement the full `0/1/2/3/4` contract (see below).

### P2 (Could)

- **FR-11 — `--top N` override** beyond default 10.
- **FR-12 — Configurable format** (`--format common`).

## Exit-code contract (`0/1/2/3/4`)

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Unexpected internal error |
| `2` | Usage error (invalid arguments/options) |
| `3` | Input error (missing/unreadable file, or zero valid requests) |
| `4` | unique-cardinality exhaustion (unique-User-Agent cap reached) |

## Kill criteria

- If a single-process streaming design cannot hit 1 GB in under 30 seconds on the target
  laptop after the perf pass, revisit scope before adding features (do not add a DB or
  server to compensate — that would violate the core constraints).
- If real-world nginx logs skip > 5% of lines with the default parser on common deployments,
  the parser is wrong and must be fixed before shipping.
