# Implementation Guide: nginx-logtop

Use this guide after the blueprint is approved. It contains bounded prompts for implementing the nine steps in `IMPLEMENTATION_PLAN.md`; it does not authorize scope beyond those documents.

## Governing Instructions for Every Step

Before editing, read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the current step in `IMPLEMENTATION_PLAN.md`. Preserve WIP=1 and implement only that step. Treat the specifications and acceptance criteria as the source of truth. Do not add authentication, a database, HTTP API, server, cloud integration, Docker, or Kubernetes.

The complete exit-code contract applies throughout implementation and must never be omitted or remapped:

| Code | Meaning |
|---:|---|
| `0` | Success, including help/version |
| `1` | Unexpected internal error |
| `2` | CLI usage error |
| `3` | Input or data error |
| `4` | Unique-cardinality exhaustion |

Before accepting any step, freeze the exact candidate, run the step's machine oracle, and follow the repository's Idea to Deploy Verification Loop and risk-tier checker. A passing narrative is not evidence; require a current revalidated adjudication receipt when the project contract calls for it. Record tests and reconcile persistent execution state. Do not perform or fabricate the separate Devil's Advocate review.

## Step 1 Prompt: Packaging and Quality Gates

```text
Implement only Step 1 from IMPLEMENTATION_PLAN.md. Create the Python 3.11 source-layout package, pyproject metadata, Click/Rich dependencies, console entry point, and test/static-tool configuration. Do not implement parsing or aggregation. Preserve the complete exit contract: 0 success, 1 internal error, 2 usage error, 3 input/data error, 4 unique-cardinality exhaustion. Run the three Step 1 verification commands and report actual evidence plus changed files. Update the status table in CLAUDE.md only after the required verification receipt is current.
```

## Step 2 Prompt: CLI, Errors, and Models

```text
Implement only Step 2 from IMPLEMENTATION_PLAN.md. Create slotted data contracts, typed failures, and the Click interface exactly as specified under PROJECT_ARCHITECTURE.md > CLI Interface. Validate --json/--csv exclusivity, the positive cardinality ceiling, and stdin rules. Centralize the exact mapping 0 success, 1 unexpected internal, 2 usage, 3 input/data, 4 unique-cardinality exhaustion. Add contract tests, run Step 2 verification, and attach real evidence before updating CLAUDE.md.
```

## Step 3 Prompt: Inputs and Parser

```text
Implement only Step 3 from IMPLEMENTATION_PLAN.md. Stream UTF-8 files or stdin line by line and parse only the documented nginx combined format. Never store all input and never echo raw bad lines. Cover timestamps, offsets, request fields, statuses, IPv4/IPv6, missing User-Agent, malformed lines, and decoding failures. Maintain exit codes 0/1/2/3/4, with parser/input failures mapped to 3 and code 4 reserved for unique-cardinality exhaustion. Run the targeted tests and lint command, then record evidence.
```

## Step 4 Prompt: Streaming Aggregates

```text
Implement only Step 4 from IMPLEMENTATION_PLAN.md. Compute deterministic top-10 IPs, top-10 exact request targets for statuses 400–599 with 4xx/5xx splits, all 24 hourly buckets, and exact unique User-Agent share. Use the literal formula 100 × hourly_request_count / total_valid_requests. Enforce the ceiling before adding a new distinct nonempty User-Agent; emit no partial result and map this only to exit 4. Keep the full 0/1/2/3/4 contract. Run aggregate tests and coverage and provide measured evidence.
```

## Step 5 Prompt: Terminal Output

```text
Implement only Step 5 from IMPLEMENTATION_PLAN.md. Render the finalized result with Rich without recalculating metrics. Show all four metrics and valid/invalid totals, preserve specified ordering and two-decimal percentages, implement auto/forced color, and treat log-derived strings as literal text. Do not change exit semantics: 0 success, 1 internal, 2 usage, 3 input/data, 4 unique-cardinality exhaustion. Run golden and injection-focused tests and report evidence.
```

## Step 6 Prompt: JSON and CSV

```text
Implement only Step 6 from IMPLEMENTATION_PLAN.md. Add JSON schema version 1 and the documented long-form CSV using standard serializers. Write only data to stdout and never emit ANSI in machine formats. Prove semantic equivalence with the terminal result model and escaping of adversarial field values. Preserve exit codes 0/1/2/3/4, where 4 exclusively means unique-cardinality exhaustion. Run targeted tests plus json.tool validation and record evidence.
```

## Step 7 Prompt: End-to-End Contract

```text
Implement only Step 7 from IMPLEMENTATION_PLAN.md. Exercise installed CLI behavior for stdin, one/multiple files, lenient/strict input, empty/unreadable data, each renderer, and injected internal/cardinality failures. Assert the complete contract: 0 success, 1 unexpected internal error, 2 CLI usage error, 3 input/data error, 4 unique-cardinality exhaustion. Assert stdout is empty on exits 3 and 4. Run end-to-end tests and full coverage; attach actual output and reconcile CLAUDE.md only after acceptance.
```

## Step 8 Prompt: Performance

```text
Implement only Step 8 from IMPLEMENTATION_PLAN.md. Add deterministic benchmark tooling and documentation, generate the untracked 1 GB fixture, record reference-machine details, wall time, peak RSS, CPU, Python, and package versions, then profile before changing hot paths. Keep exact results and all exit codes 0/1/2/3/4; never replace unique-UA exhaustion code 4 with approximation. Run the benchmark with the under-30-second gate and rerun correctness tests. Report measurement evidence, not estimates.
```

## Step 9 Prompt: Release Readiness

```text
Implement only Step 9 from IMPLEMENTATION_PLAN.md. Finalize README, license, changelog, and package metadata; build wheel and sdist; validate and install the wheel in a clean Python 3.11 environment. Document the exact exit contract 0 success, 1 internal, 2 usage, 3 input/data, 4 unique-cardinality exhaustion. Run lint, full coverage, build/twine checks, and smoke installation. Accept only the frozen candidate with current Verification Loop evidence, then update CLAUDE.md status and next action.
```

## Cross-Step Review Checklist

- [ ] No parsed-request collection grows with line count.
- [ ] No database, API, auth, server, network, cloud, container, or Kubernetes surface appeared.
- [ ] Every output format consumes the same finalized report.
- [ ] Rankings and ties match `PROJECT_ARCHITECTURE.md`.
- [ ] Hour percentages use `100 × hourly_request_count / total_valid_requests`.
- [ ] Exact unique-UA exhaustion emits no normal report and exits `4`.
- [ ] Exit codes remain the complete `0/1/2/3/4` contract.
- [ ] Tests and benchmark evidence come from the exact candidate being accepted.
- [ ] Specs and user-facing docs changed before or with any contract change.
