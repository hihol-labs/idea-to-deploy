# Product Requirements Document: `nginx-top`

## 1. Product Summary

`nginx-top` gives DevOps and SRE engineers a fast, trustworthy summary of nginx access logs from a local file or stdin. It is a Python 3.11 CLI distributed through pip. It processes records in one pass, defaults to colored terminal output, and supports JSON and CSV pipelines.

## 2. Goals and Success Measures

- Deliver the four required reports from the supported nginx combined-log format.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Keep operation stateless, local, and free of external services.
- Make results deterministic and machine-consumable.
- Surface invalid data and cardinality exhaustion explicitly.

Success is measured by all P0 acceptance criteria passing, zero machine-schema regressions, correct parsing of the maintained fixture corpus, and a recorded benchmark meeting the target.

## 3. Non-Goals

- Authentication, user accounts, authorization, or multi-tenancy.
- Database storage, historical querying, dashboards, or a long-running server.
- HTTP API, cloud service, containers, or Kubernetes.
- Tail/follow mode, remote files, compressed input, or custom nginx formats in the MVP.
- GeoIP, bot classification, session reconstruction, or query-parameter normalization.

## User Stories

- As a DevOps engineer, I want to stream a large nginx log from a file or stdin so that I can analyze it without loading it into memory or deploying services. **Priority: P0.**
- As an on-call SRE, I want the top 10 client IPs so that I can quickly spot concentrated traffic sources. **Priority: P0.**
- As an on-call SRE, I want the top 10 request URLs among 4xx/5xx responses so that I can find failing endpoints. **Priority: P0.**
- As a reliability engineer, I want request volume expressed as a percentage for every hour so that I can see the daily traffic shape. **Priority: P0.**
- As a security-minded operator, I want the share and count of unique User-Agents so that I can gauge client diversity. **Priority: P0.**
- As an automation author, I want stable JSON and CSV output so that I can feed results into pipelines. **Priority: P0.**
- As a terminal user, I want readable colored tables that automatically disable color when redirected so that output remains pleasant and safe. **Priority: P0.**
- As an operator, I want malformed lines and distinct-value exhaustion reported explicitly so that partial or unsafe results are never mistaken for complete analysis. **Priority: P0.**
- As an operator with archived logs, I want native gzip input so that I can avoid a decompression pipe. **Priority: P1.**
- As an analyst, I want a configurable ranking size so that I can inspect more than ten entries. **Priority: P1.**
- As an nginx administrator, I want selectable custom log-format templates so that non-default formats can be analyzed. **Priority: P2.**

### P0 acceptance criteria

#### Streaming input

- [ ] A regular UTF-8 file and stdin (`-`) produce identical reports for identical bytes.
- [ ] Processing iterates line by line and does not retain full request records.
- [ ] A documented 1 GB fixture completes in under 30 seconds on the named benchmark laptop.
- [ ] File/read failures return exit code 1; invalid CLI use returns exit code 2.

#### Parsing and diagnostics

- [ ] Supported combined-format IPv4 and IPv6 lines parse into the defined dataclass fields.
- [ ] Malformed and undecodable lines increment `invalid_lines` and never enter a metric denominator.
- [ ] Mixed valid/invalid input still returns code 0 and exposes exact counts.
- [ ] Non-empty input with zero valid records returns code 3; empty input returns a successful empty report.

#### Top rankings

- [ ] Top IPs include at most 10 values ordered by count descending, then IP text ascending.
- [ ] Top error URLs include only statuses 400–599 and use the same deterministic tie-break.
- [ ] Query strings remain part of the URL key.

#### Hourly distribution

- [ ] The output contains all hour buckets `00` through `23`.
- [ ] Each bucket uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages sum to 100 within documented rounding tolerance when valid requests exist, and all equal `0.0` otherwise.

#### Unique User-Agent share

- [ ] The numerator is the exact count of distinct non-missing User-Agent strings.
- [ ] The displayed percentage is `100 × unique_user_agent_count / total_valid_requests`, or `0.0` when no valid requests exist.
- [ ] Inserting a new distinct IP, error URL, or User-Agent beyond `--max-unique` stops processing and returns exit code 4.

#### Output formats

- [ ] Default output uses Rich sections/tables and color only for a TTY unless explicitly overridden.
- [ ] `--json` emits the versioned object described in `PROJECT_ARCHITECTURE.md` and parses with a standard JSON parser.
- [ ] `--csv` emits the normalized six-column schema and parses with a standard CSV parser.
- [ ] JSON and CSV never contain ANSI escape sequences.
- [ ] `--json` and `--csv` together return exit code 2.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Accept exactly one local path or `-` and stream it once |
| FR-02 | P0 | Parse the documented nginx combined access-log grammar |
| FR-03 | P0 | Count total, valid, and invalid lines |
| FR-04 | P0 | Report deterministic top-10 client IPs |
| FR-05 | P0 | Report deterministic top-10 targets for 400–599 statuses |
| FR-06 | P0 | Report counts and percentages for all 24 local log hours |
| FR-07 | P0 | Report exact unique User-Agent count and its percentage share |
| FR-08 | P0 | Render Rich text, stable JSON, and normalized CSV |
| FR-09 | P0 | Enforce cardinality ceilings and the `0/1/2/3/4` exit-code contract |
| FR-10 | P1 | Read gzip input directly |
| FR-11 | P1 | Allow ranking size configuration |
| FR-12 | P2 | Support additional explicit log-format templates |

## 6. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | 1 GB in under 30 seconds | Performance harness with elapsed time and fixture checksum |
| NFR-02 | Peak RSS at or below 512 MiB for representative input | OS-level RSS measurement |
| NFR-03 | Python 3.11 and pip-installable wheel | Clean-environment wheel smoke test |
| NFR-04 | Deterministic byte output for identical input/options | Repeat-run golden comparison |
| NFR-05 | No network, persistent data, telemetry, or temp files | Integration sandbox and source review |
| NFR-06 | At least 90% line coverage for product package | Coverage gate |
| NFR-07 | Untrusted fields cannot inject Rich markup or terminal control output | Adversarial fixture tests |

## 7. Output and Error Contract

The normative CLI details and schemas live under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. Exit codes are complete and stable: `0` success, `1` operational/internal failure, `2` usage error, `3` non-empty input with zero valid records, and `4` unique-cardinality exhaustion. Error text goes to stderr; reports go to stdout.

## 8. Dependencies and Assumptions

- Users have Python 3.11 and permission to read the log.
- MVP input follows the documented combined-log format.
- The benchmark machine, fixture-generation procedure, fixture checksum, elapsed time, and peak RSS will be recorded together.
- Architecture and serializer schemas in `PROJECT_ARCHITECTURE.md` are authoritative if an implementation prompt is ambiguous.

## 9. Release Criteria

- Every P0 acceptance item passes against the exact release candidate.
- Wheel and sdist build and the wheel works in a clean Python 3.11 environment.
- Performance and peak-memory evidence meet NFR-01 and NFR-02.
- No open Critical/High security defect or machine-output compatibility regression.
- User documentation states supported format, formulas, limits, schemas, and all five exit codes.

## 10. Kill Criteria

Pause and re-scope if the representative workload remains slower than 30 seconds after two measured optimization passes, exact required aggregation cannot remain within the 512 MiB envelope under the agreed cardinality limit, or supporting the stated combined-log grammar would require a persistent service. Do not silently relax accuracy, percentages, or exit semantics.

