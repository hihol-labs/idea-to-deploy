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

The broker's direct path accepts at most 80,000 canonical diff bytes and
100,000 serialized request bytes. A clean diff between that limit and
1,200,000 bytes is partitioned deterministically at complete-file and UTF-8
line boundaries into at most 15 exact units. The complete diff is scrubbed
before partitioning; a single over-limit line, a sixteenth unit, any missing
unit, or any redaction blocks every success path. Unit hashes and byte counts
form one candidate-bound review plan. A successful hierarchical result requires
all unit verdicts plus a final integration verdict over their structured
behavior/interface summaries.

The monthly broker budget remains $10. Direct calls reserve $0.75. In a
hierarchical Sol-maker review, each Terra call reserves $0.50; Sol reviewer
calls reserve $0.75. The broker atomically reserves the complete planned
call-count before dispatch and settles aggregate primary usage. If one API
result is ambiguous, it charges observed prior usage plus only that call's cap
and releases the unused remainder. A large candidate whose worst-case
reservation does not fit the remaining budget returns `UNAVAILABLE`; splitting
the PR remains the lower-cost alternative.

Raw API request/response bodies are not logged. Durable artifacts contain only
the sanitized checker prompt, validated verdict, hashes, bounded telemetry, and
provenance. The monthly ledger hashes the response/session identifier.
Fixture-backed tests never reserve or append to the production usage ledger.

Known credential families, JWTs, and credentials embedded in URLs are redacted.
Unlabelled long mixed-character tokens with high measured entropy fail closed
instead of being sent. This reduces, but cannot eliminate, the governance risk
of source egress; explicit consent remains mandatory.

## GitHub gate

The required external-review authority is the central GitHub App and review
broker, not a repository workflow. The App receives signed `pull_request` and
`merge_group` webhooks, reacquires the complete candidate through GitHub APIs,
verifies exact head/base/test-merge coordinates and Ed25519 maker provenance,
routes to a different eligible API model, and publishes the
`ITD external review gate` Check Run on the exact GitHub test-merge SHA.
`Codex CLI` and `Gemini CLI` remain advisory transports only.

The broker stores its OpenAI service-account key only in its mounted
secret/KMS boundary. Candidate code is never executed by a process that can
read that credential. Reservations and settlements use the broker SQLite
transaction boundary; exhausted budget, API outage, malformed evidence,
redaction, unknown maker, over-limit/unsplittable candidate, or incomplete pagination
publishes `failure`/`action_required`, never `neutral`, `skipped`, or success.
The canonical contract is
`skills/_shared/REVIEW_BROKER_POLICY.json`.

Provision the private App through
`scripts/itd_github_app_manifest.py`; its official manifest is closed to the
exact broker webhook, least-privilege permissions, and the
`pull_request`/`merge_group` events. Registration credentials are written
outside the repository, and `itd gate enrollment` derives the broker receipt
from live GitHub App and ruleset metadata rather than operator assertions.

`.github/workflows/itd-machine-oracle.yml` is a separate no-reviewer-secret
ruleset workflow. The organization ruleset pins both its central source
repository and immutable release SHA. That trusted workflow loads the oracle
runner from the pinned ITD release, the verification contract from the target
repository's protected base, and only then materializes and tests the current
GitHub candidate. A PR therefore cannot replace its own required workflow,
oracle runner, active contract, or declared verifier with a passing no-op.
Contract v2 uses shell-free `argv`; every command declares
`trustedVerifierPaths`, whose regular Git objects must be identical in the
protected base and candidate before any command runs. At least one invoked
trusted path must be a directory namespace, so candidate additions beside a
verifier (including Python `sitecustomize.py`) also change the manifest and
block execution. Python verifiers additionally run with `-I` through the
protected launcher. Verifier rotation is a two-merge operation (add a new
namespace, then trust it), so a verifier never attests the PR that replaces
it. The oracle runs commands in a disposable exact-tree checkout, so
ignored/untracked overlays do not become inputs. It emits a SHA-,
protected-contract-, and verifier-manifest-bound receipt under the job context
`ITD machine oracle`.

The organization ruleset must require the pinned workflow and the external
App-bound status check, require the PR to be current with its base, and block
deletion, force-push, unexpected rules, and bypass actors. A repository-level
ruleset cannot establish this protected workflow authority and remains
`UNVERIFIED`. `itd gate doctor --all` validates the installed ITD version,
workflow repository/SHA, tracked contract, live ruleset, App enrollment
receipt, broker policy/routes/budget, provenance key, and drift. `itd pr
create` performs the local preflight, pushes only the exact receipt HEAD,
creates or reuses a Draft PR, submits signed maker provenance, and waits for
both server checks.

`/adopt` must finish its GitHub branch with `itd gate adopt`. That command
derives the repository from the exact origin and writes the host-global
registry only after the protected default branch already contains a valid
verification contract and the live ruleset, pinned workflow source, expected
App source, broker enrollment, budget admission, and provenance key match.
Only `itd gate doctor --repository <owner/repository>` returning `PROTECTED`
establishes gate-ready adoption. A first adoption contract must be merged
through the repository's pre-existing controls or an explicit audited
temporary organization-ruleset exclusion; local/staged content is never
treated as protected-base evidence.

Infrastructure outage is distinct from findings:

- `PASSED`: eligible clean verdict and valid adjudication;
- `FINDINGS`: checker found merge-relevant issues;
- `UNAVAILABLE`: all eligible transports failed;
- `UNVERIFIED`: consent, coverage, schema, provenance, budget, or evidence
  contract failed.

The canonical ruleset has no bypass actors. Emergency recovery therefore
requires an explicit, audited administrator mutation of the ruleset; it never
creates an ITD PASS receipt and `doctor` reports the drift until protection is
restored.

## Shadow metrics

`docs/api-reviewer/SHADOW_PILOT.json` validates the measurement contract without
claiming a paid/live result. Live opt-in runs should record availability, p95
latency, observed token/cost use, unique actionable findings, false positives,
and duplication against `/review`. Promotion remains a human decision.
