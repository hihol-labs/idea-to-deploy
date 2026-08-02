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
line boundaries into at most 16 exact units. The complete diff is scrubbed
before partitioning; a single over-limit line, a seventeenth unit, any missing
unit, or any redaction blocks every success path. Unit hashes and byte counts
form one candidate-bound review plan. A successful hierarchical result requires
all unit verdicts plus a final integration verdict over their structured
behavior/interface summaries.

In direct mode, candidate-manifest `reviewDiffSha256`/`reviewDiffBytes` bind the
canonical diff. In hierarchical mode those same fields bind the compact review
plan (still capped at 80,000 bytes); the plan independently binds the complete
diff through `fullDiffSha256`/`fullDiffBytes` up to 1,200,000 bytes and every
unit hash. Therefore `reviewPlanSha256` intentionally equals the manifest's
`reviewDiffSha256`; it is not presented as the full-diff hash. Provider packing
also bounds both JSON-escaping layers before the final absolute 100,000-byte
request check.

`totalReviewBytes` is present whenever at least one declared `.jsonl.gz`
transparent representation exists, including mixed text/transparent
candidates. It counts raw text bytes plus logical decompressed JSONL bytes.
Candidates with no transparent representation must omit it. Generic binary
paths remain `UNVERIFIED`.

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

## Portable roles and deployment profiles

The methodology separates people/roles from service identities. `maker`,
`maintainer`, and `deployer` may be the same person. Only the independent
reviewer must differ from the maker of the exact candidate. The reviewer App
may read candidate metadata and publish its Check, but cannot merge, change
repository contents, or deploy. A project owner may still merge and deploy
with their own account or a separately scoped CI identity after the gate.

`skills/_shared/GATE_DEPLOYMENT_PROFILES.json` defines three deployments:

- `local-submission`: signed independent review before PR; no App or repository
  administration is required, and GitHub enforcement is not claimed;
- `self-hosted-app`: the operator registers an App under a user or organization
  account; it may be private for that owner or public for wider installation;
- `managed-app`: the service operator owns one public App that repository
  owners explicitly install on selected repositories.

Protection is a separate choice. `local-review` reports `LOCAL_REVIEWED`;
`app-check` may report `APP_CHECK_ENFORCED` after the repository owner requires
the App-owned Check; only the fully observed `organization-workflow` profile
may report `PROTECTED`. The canonical `itd gate doctor` reads profile-aware
`gates.json` v2 and reports the weakest verified claim across the selected
repositories; weaker profiles never borrow the strongest profile's claim.
Legacy v1 organization-workflow registries remain readable but are never
silently rewritten as v2.

For `local-submission`, independently adjudicate the exact staged candidate,
then wrap that unchanged index in exactly one normal single-parent commit.
Register the adjudication after the commit but before guarded push:

```bash
itd gate register-profile \
  --repository <owner/repository> \
  --checkout <absolute-git-root> \
  --repository-owner-type <user-or-organization> \
  --deployment-profile local-submission \
  --protection-profile local-review \
  --local-review-receipt-file <absolute-current-adjudication.json> \
  --local-review-unit-id <unit-id>:general-review \
  --local-review-risk-tier high
itd gate doctor --repository <owner/repository>
```

The doctor must return `LOCAL_REVIEWED`. Its local validator uses Verification
Loop `--candidate-mode committed-head`, which reconstructs the original review
context from `HEAD^`, `HEAD^{tree}`, and the exact binary diff. Thus the commit
does not self-invalidate the review, while an amended tree, merge commit,
second commit, or foreign parent fails closed. The default staged validator is
unchanged. `itd pr create` then revalidates this bridge and the exact machine
preflight before its guarded push, creates or updates the Draft PR, and
performs no App, broker, ruleset, or status-check call. To refresh evidence
after commit, run the Verification Loop machine, checker, and adjudicate
commands with `--candidate-mode committed-head`.

## GitHub gate

The repository-resident `external-review-gate.yml` remains the active legacy
guard during bootstrap. Do not disable or remove it until the App/broker and
pinned organization ruleset are live, `itd gate doctor` reports `PROTECTED`,
and cutover canaries pass. Its removal is a separate exact-candidate change
after that evidence exists, so migration never opens an unreviewed merge
window.

In server-enforced profiles, the required external-review publisher authority
is the selected GitHub App and review broker, not a repository workflow. The
App receives signed `pull_request` and
`merge_group` webhooks, reacquires the complete candidate through GitHub APIs,
verifies exact head/base/test-merge coordinates and Ed25519 maker provenance,
routes to a different eligible API model, and publishes the
`ITD external review gate` Check Run on the exact GitHub test-merge SHA.
`Codex CLI` and `Gemini CLI` remain advisory transports only.
GitHub's Compare API exposes its changed-file list on the first response and
caps that list at 300 files; the frozen broker policy keeps `maxFiles` strictly
below that cap (100), rejects a response at the API cap, and independently
paginates/binds every compared commit before accepting file coverage.

The broker stores its OpenAI service-account key only in its mounted
secret/KMS boundary. Candidate code is never executed by a process that can
read that credential. Reservations and settlements use the broker SQLite
transaction boundary; exhausted budget, API outage, malformed evidence,
redaction, unknown maker, over-limit/unsplittable candidate, or incomplete pagination
publishes `failure`/`action_required`, never `neutral`, `skipped`, or success.
Candidate blobs remain text-only by default. The sole transparent container
declared by the frozen policy is `.jsonl.gz`: the broker verifies the complete
raw Git blob, stream-decompresses exactly one gzip member under the per-blob
and aggregate limits, requires strict UTF-8 JSONL without NUL, duplicate keys,
non-standard constants, trailing data, or a second member, and binds both raw
and logical hashes/byte counts in the candidate manifest. Secret scanning runs
over the complete logical canonical diff before hierarchical partitioning.
Every undeclared binary representation remains `UNVERIFIED` without provider
dispatch.
The canonical contract is
`skills/_shared/REVIEW_BROKER_POLICY.json`.

Provision a self-hosted private/public App or the operator-owned managed public
App through `scripts/itd_github_app_manifest.py`. Its official manifest is
closed to the exact broker webhook, review-only least-privilege permissions,
and the
`pull_request`/`merge_group` events. Registration credentials are written
outside the repository, and `itd gate enrollment` derives the broker receipt
from live GitHub App and ruleset metadata rather than operator assertions.

`docs/templates/github/itd-machine-oracle.yml` is the staged
no-reviewer-secret ruleset workflow. The bootstrap merge lands its trust
anchors under the retained legacy gate; only a follow-up copies the template
to `.github/workflows/itd-machine-oracle.yml` and enables the ruleset. The
organization ruleset uses GitHub's server-side
`workflows` rule and pins its workflow-file reference by central
`repository_id`, path, and immutable release `sha`. The rule requires that
specific workflow run, not a same-named status context: a candidate copy with
the same workflow/job/check name cannot satisfy it. For this directly defined
workflow, `github.workflow_ref` and `github.workflow_sha` expose the source
coordinates GitHub already selected; the workflow validates the exact central
repository/path and checks out that SHA. These checks are defense in depth,
not the source of authority. Enrollment and every live doctor call
independently reacquire the organization ruleset and require its repository
ID, path, and SHA to match the registered pinned release. That trusted workflow loads the oracle runner from the pinned
ITD release, the verification contract from the target repository's protected
base, and only then materializes and tests the current GitHub candidate. A PR
therefore cannot replace its own required workflow, oracle runner, active
contract, or declared verifier with a passing no-op. GitHub documents the
immutable `WorkflowFileReference` fields in both its GraphQL Actions schema and
organization rules REST schema.
Contract v2 uses shell-free `argv`; every command declares
`trustedVerifierPaths`, whose regular Git objects must be identical in the
protected base and candidate before any command runs. Each command binds its
exact executable verifier plus every verifier-side file it reads or executes,
without freezing unrelated regression tests. Python verifiers additionally run
with `-I` through the protected launcher, excluding their script directory,
the candidate working directory, user site packages, and candidate-only
startup modules such as `sitecustomize.py` from import resolution. Verifier
authority is distinct from the subject under test: broker/server/policy/CLI
modules and static artifacts explicitly loaded or read by a protected verifier
may change in the candidate, remain bound by the exact candidate tree and
required-artifact hashes, and must satisfy the protected assertions. A
test-side helper that participates in deciding pass/fail is verifier authority
and must instead be declared in `trustedVerifierPaths`; `-I` prevents such a
helper from entering implicitly through the script directory or working tree.
Verifier
rotation is a three-merge operation: add the verifier under a new path, trust
that already-protected path in the contract, then use it for implementation
changes. A verifier therefore never attests the PR that replaces it. The
oracle runs commands in a disposable exact-tree checkout, so
ignored/untracked overlays do not become inputs. It emits a SHA-,
protected-contract-, and verifier-manifest-bound receipt under the job context
`ITD machine oracle`.

The first repository trust anchor is necessarily installed before this
workflow becomes a required ruleset check. Merge the initial workflow, oracle,
contract, launcher, and declared verifier files under the repository's
pre-existing controls (with an explicit audited temporary ruleset exclusion
only if an organization rule would otherwise require the not-yet-anchored
workflow), verify that those exact objects are now in the protected base, and
only then activate the pinned required workflow. Missing protected-base
contract or verifier objects always remains `UNVERIFIED`; the workflow never
falls back to candidate-owned trust material.

For the `organization-workflow` protection profile, the organization ruleset
must require the pinned workflow and the external
App-bound status check, require the PR to be current with its base, and block
deletion, force-push, unexpected rules, and bypass actors. A repository-level
ruleset cannot establish this protected workflow authority and remains
`UNVERIFIED`. For a v2 `organization-workflow` row, `itd gate doctor --all`
validates this strongest profile's
installed ITD version,
workflow repository/SHA, tracked contract, live ruleset, App enrollment
receipt, broker policy/routes/budget, provenance key, and drift. `itd pr
create` performs the local preflight, pushes only the exact receipt HEAD,
creates or reuses a Draft PR, submits signed maker provenance, and waits for
both server checks.

`/adopt` must select one deployment/protection profile explicitly. A local
submission is registered with `itd gate register-profile` only after its exact
adoption commit receives a current adjudication; `LOCAL_REVIEWED` establishes
local review, not GitHub enforcement. App profiles require owner-authorized
App/ruleset provisioning and profile-valid v2 coordinates. The legacy
`itd gate adopt` command remains a fail-closed v1 organization-workflow
bootstrap: it writes only after the protected default branch, live ruleset,
pinned workflow, App source, broker enrollment, budget, and provenance key
match. Only a doctor result of `PROTECTED` establishes the strongest claim.

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
