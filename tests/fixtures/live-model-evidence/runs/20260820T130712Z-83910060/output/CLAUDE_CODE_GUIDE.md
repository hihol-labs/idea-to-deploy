# Implementation Guide: Nginx Log Lens

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts for future coding
sessions. It does not authorize scope expansion. Run one prompt at a time,
preserve WIP=1, and update specifications before changing behavior.

## Non-Negotiable Contract

Every prompt below inherits these rules:

- Python 3.11, Click, Rich, dataclasses, `src/` layout, pip-installable package.
- Single-process, one-pass streaming; no raw-log materialization.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Default output is Rich terminal; `--json` and `--csv` are mutually exclusive.
- Diagnostics use stderr; failed runs emit no partial report on stdout.
- Do not expose full malformed log lines in diagnostics.

The complete exit-code contract is mandatory in every implementation session:

| Code | Meaning |
|---:|---|
| `0` | Successful complete report, including empty input |
| `1` | Runtime or input/output failure |
| `2` | Click usage error |
| `3` | Malformed non-empty log data; no report |
| `4` | Unique-cardinality exhaustion; no report |

Code `4` specifically means inserting a new exact User-Agent would exceed
`--max-unique-user-agents`. Never omit, remap, or merge it with another code.

## Session Protocol

Before each step, read `AGENTS.md`, `.itd/SCOPE_LOCK.md`, the named plan step,
the related `PROJECT_ARCHITECTURE.md` sections, and relevant PRD requirements.
Confirm the previous step's evidence. Change only the current step's declared
files unless scope is reconciled first. Use tests as executable acceptance
evidence and finish with the repository's current verification-loop procedure.

## Prompt 1: Package Skeleton and Domain Contracts

```text
Implement only STEP 1 from IMPLEMENTATION_PLAN.md. Read the architecture's
Component Model, Data Model, Packaging and Deployment, CLI Interface exit codes,
and PRD FR-014 first. Create the package skeleton, frozen dataclasses, typed
domain errors, Click help/version boundary, and tests listed in the step. Do not
implement parsing, aggregation, or rendering yet. Preserve all exit meanings
0/1/2/3/4 in types/tests even where later behavior is still pending. Run every
STEP 1 verification command, record evidence, and stop after reconciling status.
```

## Prompt 2: Streaming Input and Parser

```text
Implement only STEP 2 from IMPLEMENTATION_PLAN.md on top of verified STEP 1.
Parse supported nginx Common/Combined lines incrementally from strict UTF-8 file
or stdin. Apply a bounded line guard, safe errors with line number/reason, and no
raw-line diagnostic. Add all declared fixtures/tests. A malformed non-empty line
maps to 3; I/O/decode failures map to 1; Click usage remains 2; success remains
0; reserve and retain 4 for unique-cardinality exhaustion. Do not aggregate or
render. Run STEP 2 and regression verification, record evidence, and stop.
```

## Prompt 3: IP and Error-URL Rankings

```text
Implement only STEP 3 from IMPLEMENTATION_PLAN.md. Add one-pass counts for all
valid client IPs and for present URLs whose status is 400..599 inclusive. Return
at most ten entries sorted by descending count and ascending key for ties. Keep
the parser/output boundaries clean and do not add hourly or UA logic. Test status
edges, missing URLs, cardinalities, ties, atomic failure, and the unchanged
0/1/2/3/4 contract. Run all STEP 3 commands and relevant regressions, record
evidence, reconcile status, and stop.
```

## Prompt 4: Hourly and User-Agent Metrics

```text
Implement only STEP 4 from IMPLEMENTATION_PLAN.md. Add 24 hour buckets using the
timestamp's written local hour and calculate each percentage exactly as
100 × hourly_request_count / total_valid_requests. Track non-missing UA
observations and exact uniques. Before inserting a new unique, enforce the
positive configured ceiling; exhaustion must emit no report and exit 4. Retain
0 success, 1 runtime/I/O, 2 usage, and 3 malformed data. Test all denominators,
empty input, duplicate/missing UAs, exact limit, and first-over-limit behavior.
Run the step verification and regressions, record evidence, and stop.
```

## Prompt 5: Three Renderers

```text
Implement only STEP 5 from IMPLEMENTATION_PLAN.md. Render the same immutable
Report through Rich terminal, JSON schema_version 1, and long-form RFC 4180 CSV.
Follow the architecture's exact ordering, field names, rounding, TTY/NO_COLOR,
escaping, and 24-hour rules. Never recompute metrics in renderers; never put ANSI
or diagnostics in machine stdout. Preserve atomic output and all codes 0/1/2/3/4.
Add the declared goldens and tests, run STEP 5 plus aggregation regressions,
record evidence, reconcile status, and stop.
```

## Prompt 6: CLI Integration and Failure Semantics

```text
Implement only STEP 6 from IMPLEMENTATION_PLAN.md. Wire the architecture's exact
CLI Interface: INPUT/stdin, input-format, UA limit, color, JSON/CSV exclusivity,
help, and version. Complete aggregation before output. Prove end-to-end that 0 is
success including empty input, 1 is runtime/I/O, 2 is Click usage, 3 is malformed
non-empty data, and 4 is unique-cardinality exhaustion. Every failure must have
empty report stdout and a safe stderr diagnostic. Run all listed integration and
schema commands plus regressions, record evidence, reconcile status, and stop.
```

## Prompt 7: Quality and Performance Acceptance

```text
Implement only STEP 7 from IMPLEMENTATION_PLAN.md. Add invariant tests and a
deterministic synthetic benchmark generator; do not commit the generated 1 GB
file. Configure dev-only quality tools and execute coverage, lint, type, and the
installed-command timing/RSS benchmark. Record Python/hardware/storage/cache and
fixture cardinality so <30 seconds is meaningful. Exercise security boundaries
for untrusted Rich/JSON/CSV values and all exit paths 0/1/2/3/4. Do not claim the
performance target without a measured reference-laptop result. Record evidence,
reconcile status, and stop.
```

## Prompt 8: Packaging and Release Handoff

```text
Implement only STEP 8 from IMPLEMENTATION_PLAN.md after Steps 1-7 are verified.
Finalize user docs, license/changelog, wheel/sdist metadata, and a clean Python
3.11 wheel install. Reconcile every P0 PRD criterion and ensure README/help agree
on 0 success, 1 runtime/I/O, 2 usage, 3 malformed data, and 4 unique-cardinality
exhaustion. Do not add a database, API, server, cloud, Docker, or Kubernetes.
Run build, package checks, full tests, and clean-install help. Then freeze the
exact staged candidate and run the repository's risk-routed verification loop;
accept only a current revalidated receipt. Record evidence and stop.
```

## Recovery Prompt

```text
The current implementation step failed verification. Do not start another step.
Reproduce the smallest failing command, classify whether the defect is spec,
implementation, fixture, or environment, and preserve the complete 0/1/2/3/4
contract. If behavior must change, update PRD and architecture before code. Make
the smallest in-scope repair, rerun the failed command and all affected
regressions, then rerun the repository verification loop. Record recovery rather
than success until exact-candidate adjudication is current.
```
