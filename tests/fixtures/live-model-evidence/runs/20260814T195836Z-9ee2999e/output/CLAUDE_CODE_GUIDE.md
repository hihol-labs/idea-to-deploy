# Claude Code Guide: nginx-stream-report

## Purpose

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. Start only one step at a time, inspect the current repository first, preserve existing work, and reconcile Idea to Deploy state/evidence at handoff. The specifications are the source of truth: change `PRD.md` and `PROJECT_ARCHITECTURE.md` before changing a public behavior.

Do not add authentication, a database, HTTP API, server, cloud infrastructure, Docker, or Kubernetes. Maintain a local, stateless, single-process Python 3.11 CLI using Click, Rich, and dataclasses.

## Global Acceptance Contract

Every implementation step must preserve and test the complete exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Successful report, including empty input |
| `1` | Input or I/O failure |
| `2` | Invalid CLI usage or option combination |
| `3` | Malformed log data when strict mode is enabled |
| `4` | Unique-cardinality exhaustion for IPs, error URLs, or User-Agents |

Code `4` is mandatory and must never be omitted, remapped, or collapsed into code `1` or `3`. JSON/CSV stdout must be empty on every nonzero exit. Hourly percentages must use `100 × hourly_request_count / total_valid_requests` and return `0.0` for every hour when no valid requests exist.

## Prompt 1: Package and Quality Skeleton

```text
Execute Step 1 of IMPLEMENTATION_PLAN.md only. Read PRD.md and the CLI Interface and Deployment sections of PROJECT_ARCHITECTURE.md first. Create the Python 3.11 src-layout packaging skeleton, Click console entry point, help/version behavior, and initial CLI tests. Do not implement parsing or reports yet. Verify installation, --help, and the named tests. Preserve exit meanings 0/1/2/3/4 in the design even where later steps implement their triggers. Record actual commands/results and stop after Step 1 is handoff-ready.
```

## Prompt 2: Models and Failures

```text
Execute Step 2 of IMPLEMENTATION_PLAN.md only. Define the exact dataclasses from PROJECT_ARCHITECTURE.md and one error taxonomy mapping success to 0, input/I/O to 1, usage to 2, strict malformed data to 3, and unique-cardinality exhaustion to 4. Add tests proving the mappings, especially code 4. Do not add parsing, rendering, persistence, or services. Run the stated type and unit checks, record evidence, and stop.
```

## Prompt 3: Parser

```text
Execute Step 3 of IMPLEMENTATION_PLAN.md only. Implement the documented nginx combined-format parser as a streaming-safe, precompiled parser. Treat log content as untrusted data, avoid retaining raw lines, and keep diagnostics free of full sensitive records. Add the specified synthetic fixtures and parser tests. Malformed records must be classifiable for later default-skip versus strict exit-3 behavior; decoding and I/O remain exit 1. Preserve the complete 0/1/2/3/4 contract. Run only the stated checks and reconcile handoff state.
```

## Prompt 4: Aggregation and Cardinality

```text
Execute Step 4 of IMPLEMENTATION_PLAN.md only. Implement exact one-pass aggregation for top 10 IPs, top 10 4xx/5xx URLs, 24 hourly percentage rows, and unique User-Agent count/share. Use deterministic tie ordering. Calculate hourly percentages with the literal formula 100 × hourly_request_count / total_valid_requests. Enforce --max-unique semantics independently for IP, error URL, and User-Agent state; exceeding a ceiling must map to exit 4 and never silently approximate. Preserve exits 0/1/2/3/4. Add and run the stated tests with branch coverage evidence, then stop.
```

## Prompt 5: Terminal Renderer

```text
Execute Step 5 of IMPLEMENTATION_PLAN.md only. Build the default Rich text renderer for all four report sections. Color only for a compatible terminal unless --no-color is set, escape untrusted control characters, and render percentages consistently. Do not change metric semantics or add pipeline formats. Preserve the 0/1/2/3/4 error contract and do not render a successful report for codes 1-4. Run snapshot and manual fixture checks, record results, and stop.
```

## Prompt 6: JSON and CSV

```text
Execute Step 6 of IMPLEMENTATION_PLAN.md only. Implement the exact JSON schema-version-1 and long-form CSV contracts in PROJECT_ARCHITECTURE.md using standard serializers. Output must be deterministic and contain no ANSI/prose. Buffer structured output until successful finalization so exits 1, 2, 3, and 4 cannot leave partial JSON or CSV. Preserve exit 0 for successful empty input and the full 0/1/2/3/4 mapping. Add golden and parse-back tests, run the listed verification commands, and stop.
```

## Prompt 7: CLI Integration

```text
Execute Step 7 of IMPLEMENTATION_PLAN.md only. Wire file/stdin input, parser, aggregator, and renderer through Click. Implement default malformed-line skipping and --fail-on-malformed. Test every public option and the exact exit contract: 0 success, 1 input/I/O, 2 usage, 3 strict malformed data, 4 unique-cardinality exhaustion. Assert stderr/stdout separation and no partial structured report on errors. Handle ordinary broken pipes without traceback. Run the integration suite and explicit exit-code script, record evidence, and stop.
```

## Prompt 8: Performance and Release

```text
Execute Step 8 of IMPLEMENTATION_PLAN.md only. Add a deterministic benchmark fixture generator and runner, package smoke tests, and release documentation. Do not commit the generated 1 GB fixture. Freeze and test the exact candidate according to the repository's Idea to Deploy verification contract. Run the full suite, static checks, wheel smoke test, and documented 1 GB benchmark on recorded hardware. Do not claim the under-30-second target unless measured. Verify exits 0/1/2/3/4 remain covered, with code 4 meaning unique-cardinality exhaustion. Record evidence and leave the state handoff-ready.
```

## Review Checklist for Every Step

- Scope matches exactly one implementation-plan step.
- No raw input is accumulated and no forbidden infrastructure is introduced.
- Public behavior remains consistent across architecture, PRD, help, tests, and README.
- New untrusted values are safely rendered in text, JSON, and CSV as applicable.
- Verification commands actually ran; failures remain failures rather than narrative success.
- The complete exit-code contract `0/1/2/3/4` remains explicit and tested.

