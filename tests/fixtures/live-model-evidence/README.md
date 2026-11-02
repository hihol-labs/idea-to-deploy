# Live workflow evidence

This directory retains observations from the representative `fixture-03-cli-tool`
blueprint workflow. Its frozen contract is
[`../fixture-03-cli-tool/expected-snapshot.json`](../fixture-03-cli-tool/expected-snapshot.json):
`fixture_type=blueprint-only`, six planning documents, CLI/no-database/no-HTTP-API
justifications, and the enumerated snapshot checks. No log-analyzer implementation
or executable generated application is shipped in these records.

`PASS` in `latest.json` binds the independent snapshot oracle's actual exit code
and its replayable archived inputs. It describes that bounded workflow test.
Candidate messages, command-level self-checks and their claimed success remain
untrusted transcript data. Failed commands are retained verbatim; a successful
model-session exit is not a claim that every command inside that session passed.
`verify_live_model_benchmark.py` independently replays the snapshot oracle and
validates the source, transcript, output and verdict hashes.

The generated plans are research observations. Their resource limits, follow-mode
semantics, terminal/CSV output handling and error-code details need a separate
design and implementation review before somebody builds the sample application.
H4 conformance measures the frozen rubric and does not certify the completeness
or production safety of every generated application design; see
[`../../../docs/HARNESS_CONFORMANCE_REPORT.md`](../../../docs/HARNESS_CONFORMANCE_REPORT.md).
These limitations are retained in the backlog. They do not change the frozen
oracle or the mandatory independent review of the ITD implementation.

For the current `20261102T170828Z-9c79faf3` observation, both `PRD.md` (FR-02)
and `PROJECT_ARCHITECTURE.md` (CLI `--format` and parser requirements) explicitly
support common and combined nginx logs. User-Agent is optional and valid request
counting does not depend on its presence. Its transcript contains failed author
inspection commands; those observations are preserved alongside the external
snapshot verdict. The bounded oracle's recorded exit code is zero and its replay
passes. No author self-report is used as the acceptance authority.
