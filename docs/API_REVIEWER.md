# Verifiable external API reviewer

`skills/_shared/itd_external_reviewer.py` is a provider-neutral checker
transport for the existing Verification Loop. It is not a new lifecycle skill
and cannot mark work complete by itself.

## Local advisory use

Stage the exact candidate, explicitly permit egress, and provide real
host-observed maker provenance:

```bash
export ITD_EXTERNAL_REVIEW_EGRESS_OK=1
export OPENAI_API_KEY=...

sh skills/_shared/itd_py.sh skills/_shared/itd_external_reviewer.py review \
  --root . \
  --maker-vendor openai \
  --maker-model gpt-5.6-sol \
  --maker-session '<host session id>' \
  --risk high \
  --mode local
```

Local mode returns a typed JSON status and remains fail-open for
`UNAVAILABLE`/`UNVERIFIED`. `FINDINGS` is non-zero so scripts cannot confuse it
with a clean review. The API key is read only from `OPENAI_API_KEY`.

Consent can instead use a local, normally untracked
`.itd-external-review-egress-ok` marker. The legacy
`CROSS_REVIEW_EGRESS_OK`/`.cross-review-egress-ok` forms remain compatible.

## Evidence bridge

A successful run writes:

- sanitized prompt under `.itd-memory/verification-loop/prompts/`;
- canonical verdict under `.itd-memory/verification-loop/reports/`;
- provider/model/session, independence, usage/cost, exact tree/diff manifest,
  prompt/report hashes, and prior failures under
  `.itd-memory/verification-loop/external-review/`.

Validate freshness before minting a checker receipt:

```bash
sh skills/_shared/itd_py.sh skills/_shared/itd_external_reviewer.py validate \
  --root . --risk high --metadata <metadata-path>
```

Then pass the recorded prompt/report and maker/checker fields to
`itd_verification_loop.py checker`. Complete through the ordinary `machine`,
`adjudicate`, and `check` commands. Only that adjudication is acceptance
evidence.

## Routing

The default policy is `skills/_shared/EXTERNAL_REVIEW_POLICY.json`.

- Claude/Gemini-authored candidate: managed OpenAI API is eligible
  cross-vendor evidence.
- GPT/Codex-authored candidate: the managed OpenAI API is same-vendor and
  potentially same-provider evidence; the exact same model remains ineligible
  for high/unknown risk.
- Codex CLI and Gemini CLI remain registered host-native alternatives, but are
  not eligible for automated diff egress or protected evidence until their
  adapter can prove a no-tools/no-secret sandbox and complete cost telemetry.

Actual eligibility is computed from maker provenance and risk. Claude/Anthropic
API or a hardened CLI broker can be added later without changing the evidence
contract. Test fixtures require
`ITD_EXTERNAL_REVIEW_TESTING=1`, are recorded with `liveObserved:false`, and
the normal `validate` path rejects them as acceptance evidence.

## Limits and privacy

The default policy caps files, bytes, estimated input tokens, output tokens,
timeout, retries, per-run cost, and monthly observed cost. Binary or oversized
changes return `UNVERIFIED`; content is never silently truncated. One canonical
sanitizer is shared with the legacy pre-commit hook. Redaction is not a legal or
governance guarantee, so egress stays default-off.

For `gpt-5.6-sol`, the default single-call bounds are 55,000 raw diff bytes,
66,500 serialized request bytes, and 5,550 output/reasoning tokens. Treating
each request byte as a possible token keeps the worst-case priced request below
the $0.50 per-run ceiling without relying on a heuristic tokenizer estimate.
Paid automatic retries are disabled by default because two worst-case attempts
would exceed that ceiling; callers may start a new separately reserved run.
Larger changes must be split into independently bound review units.

Raw API request/response bodies are not logged. Durable artifacts contain only
the sanitized checker prompt, validated verdict, hashes, bounded telemetry, and
provenance. The monthly ledger hashes the response/session identifier.
Fixture-backed tests never reserve or append to the production usage ledger.

Known credential families, JWTs, and credentials embedded in URLs are redacted.
Unlabelled long mixed-character tokens with high measured entropy fail closed
instead of being sent. This reduces, but cannot eliminate, the governance risk
of source egress; explicit consent remains mandatory.

## GitHub gate

`.github/workflows/external-review-gate.yml` runs candidate code only in the
separate `candidate-oracle` job, where reviewer tooling, durable review
evidence, and the API credential are absent. The protected review job then
loads tooling from the trusted default branch, checks out the PR candidate
separately, exposes the API key only to the no-execution review step, and binds
the GitHub-observed oracle-job result into the high-risk Verification Loop.
The protected job consumes the immutable head/base/repository outputs resolved
by `candidate-oracle`; it does not re-resolve mutable PR refs. The reviewed
change set is staged from the PR merge-base to the exact head, while the oracle
separately tests the prospective merge with the current base tip. Fork PRs are
rejected before candidate checkout or execution.

The gate is triggered by the trusted broker with the
`itd-external-review` `repository_dispatch` event. Unlike
`workflow_dispatch`, the caller cannot select a branch/tag version of the gate;
GitHub runs the workflow definition from the default branch. The payload
requires the PR number, maker vendor/model/session, current PR head and base
SHAs, and an
HMAC-SHA256 signature over the UTF-8 canonical JSON object with sorted keys
`base`, `head`, `model`, `pr`, `session`, `vendor` and compact separators.
Configure a protected GitHub
environment named `itd-external-review`, store `OPENAI_API_KEY` and a distinct
`ITD_PROVENANCE_HMAC_KEY` there, optionally set
`ITD_EXTERNAL_REVIEW_ORACLE`, and require the commit-status context
`ITD external review gate` in branch protection. The workflow publishes this
status on the verified PR head SHA; the default-branch dispatch run SHA is not
used as the merge gate. Mutable PR labels and unsigned dispatch strings are not
accepted. The broker must reject CR/LF in model/provider/session values. Branch
protection must also require the PR to be up to date with the protected default
branch so a head-scoped status cannot outlive its reviewed base. A workflow file
alone does not make the check blocking.
The workflow never performs branch-protection mutation, merge, or rule
weakening; those remain explicit administrator actions outside this transport.

CI also restores the newest serialized usage ledger before review and uploads
the updated ledger with 45-day retention. This ledger is reconciliation and
an observed monthly guardrail, not a hard guarantee under runner loss. A global
non-cancelling concurrency group prevents normal races. Restore accepts only
non-expired artifacts whose originating run used this workflow file on the
default branch; artifact names include both run ID and run attempt.
Paid responses with
complete usage telemetry are recorded before verdict parsing, including
incomplete or schema-invalid responses. Before each paid call, the remaining
monthly budget must cover the policy-bounded worst-case request cost.

The $0.50 per-request ceiling is strict. A hard distributed monthly ceiling
requires a provider-side project limit or an external broker with atomic
reservation/consumption; ITD does not claim that guarantee from Actions
artifacts.

Infrastructure outage is distinct from findings:

- `PASSED`: eligible clean verdict and valid adjudication;
- `FINDINGS`: checker found merge-relevant issues;
- `UNAVAILABLE`: all eligible transports failed;
- `UNVERIFIED`: consent, coverage, schema, provenance, budget, or evidence
  contract failed.

Emergency merge is a GitHub administrative bypass with an audit trail. It never
creates an ITD PASS receipt.

## Shadow metrics

`docs/api-reviewer/SHADOW_PILOT.json` validates the measurement contract without
claiming a paid/live result. Live opt-in runs should record availability, p95
latency, observed token/cost use, unique actionable findings, false positives,
and duplication against `/review`. Promotion remains a human decision.
