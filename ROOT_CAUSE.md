# Root Cause

Recorded: 2026-07-30; updated: 2026-08-01

## Primary defect

The broker originally decoded every changed Git blob as raw UTF-8. Draft PR
#177 contains one required sanitized JSONL transcript stored as
`transcript.jsonl.gz`; decoding its compressed byte `0x8b` therefore returned
`UNVERIFIED` before provider dispatch.

The bounded fix recognizes only paths explicitly declared by the frozen schema
as `.jsonl.gz`. It verifies the complete raw Git blob, stream-decompresses one
gzip member under the existing size bounds, requires strict UTF-8 without NUL
and valid JSONL, secret-scans the complete logical diff, and binds raw and
logical hashes/byte counts in the candidate and durable evidence. Undeclared or
generic binary content still returns `UNVERIFIED`; no archive is extracted or
candidate code executed.

## Acceptance constraints

- No generic `allowBinary`, truncation, partial success, or larger review cap.
- Full canonical reconstruction must remain `<=1.2 MB`, `<=16` units, with a
  mandatory integration verdict and a clean scrub result.
- Success remains exact-candidate, App-owned, provenance-bound, and fail closed
  on missing, ambiguous, oversized, redacted, or stale evidence.
- Only a current machine receipt, independent checker receipt, and adjudication
  for the same staged tree can accept GPG-001.

## Checker follow-up ledger

Each rejected tree stayed uncommitted until its reproducible findings were
covered regression-first. Repeated claims about the 80 KB compact review-plan
field, mixed transparent/text schema, serialized plan hash, closed policy,
hierarchical prompt/verdict bundle, and LOCAL_ONLY preflight authority were
refuted against exact code and mutation tests; the 1.2 MB full diff is bound
separately.

1. Bound callback failures, reservation-derived output caps, absolute curl,
   argv path inputs, effective Compose keys, and split byte/segment identity.
2. Bounded Git pipes, kept the sole worker alive across transient storage
   failures, mapped authenticated delivery conflicts to HTTP 409, and aligned
   public wording with the seventeenth-unit rejection.
3. Required Python isolation before the script operand, serialized manifest
   callbacks, rejected unsafe interpreter operands, and compared stored/fresh
   machine evidence.
4. Isolated the protected workflow, bound converted App owner to organization,
   aligned mounted-secret naming, and compared verifier bytes with HEAD.
5. Removed ambiguous interpreter option parsing, documented hash-locked systemd
   bootstrap, rejected relative DB paths, handled PyPy, rejected untracked
   verifier operands, and bounded quick-regression child output.
6. Classified admitted PyPy consistently in both protected validators and
   normalized hook-installer filesystem errors through JSON `BLOCKED`.

## Current checker follow-up

The review of staged tree `95921ddc2f74f266d4714a2925549646b67af8ac`
completed all eight fresh units but stopped fail closed because one critical
finding named line 2922 in a 2420-line file. A constrained refutation still
confirmed the underlying publication-order defect, and three other unit
findings reproduced:

- a required artifact could traverse a tracked symlinked parent and hash a host
  file outside the isolated candidate;
- a scalar `commands` row raised `AttributeError` instead of typed
  `PushBlocked`;
- `HTTPServer.timeout` bounded `accept()` but not reads from an accepted partial
  loopback request;
- a terminal successful Check was published before `reviews_v3` finalization;
  if that write failed, GitHub's immutable success could not be downgraded.

The fixes reject every symlink component of required artifact paths, validate
each command row as an object, apply a two-second timeout to accepted callback
sockets, and finalize the exact durable review receipt before authorizing any
terminal review Check. Ambiguous GitHub completion leaves the job explicitly
recovery-bound; recovery never repeats the provider call and processes only a
still-running exact job.

Tree `d6cc2713a0296737f28bcd1d9879ad64ef551e83` then passed both
machine contracts and returned Terra `PASSED_WITH_WARNINGS` with six findings.
Four were refuted: GitHub officially supports API version `2026-03-10`; an
empty ambient key did not satisfy `os.environ.get`; the 80 KB field binds the
serialized compact plan; and that plan's hash is exactly the value named
`reviewPlanSha256`, while it separately binds the full diff hash and bytes.
Two edge cases reproduced: readiness did not normalize every typed storage
failure, and an injected enforced policy could be paired with a digest read
from unvalidated on-disk bytes. Readiness now maps Broker/SQLite/OS storage
failures to 503, policy bytes are validated before their exact hash is stored,
and the unnecessary ambient-key declarations were removed from both deployment
paths.

Tree `ac3de562408be511d08e3cc7a6a0e18c8d626882` passed both machine
contracts but Terra returned `BLOCKED` with seven findings. The compact-plan
and mixed-transparent claims repeated covered false positives. The in-repo
receipt claim ignored the dedicated ignored gate-preflight path. The two
critical trust claims also crossed authority layers: adoption is explicitly a
non-attesting bootstrap until a later protected-base anchor merge, and the
quick aggregator is local regression input and absent from the protected
contract. One defect reproduced: after two disable/rotate cycles, an immutable
historical enrollment receipt could be reactivated. Historical receipt reuse
is now rejected. The unused `fail_review_preparation()` surface was removed;
review failure can transition only through a durable terminal
`failure_preparations` record.

Tree `869c4a26bdc3b63d340787c965be5c1c67ed857d` passed both machine
contracts and Terra returned `PASSED_WITH_WARNINGS` with five findings. Three
reproduced: the protected PR workflow did not prove the checked merge commit's
parents, `safe_relative()` admitted Windows drive-absolute paths, and adoption
admitted an untracked path-bearing `--config` value. The workflow now binds PR
parents and merge-queue ancestry, the oracle rejects drive prefixes, and
adoption treats config/data option values as declared inputs. The repeated
80 KB claim again confused the compact bound plan with its separately bound
1.2 MB full diff. The failure-publication claim also omitted the live exact
Check observation (`id`, App, name, head and external ID), exact job/enrollment
lookup, immutable preparation, and terminal authorization already enforced.

## MEM-8 regression recovery

Commit `954a3b6` removed the executable prompt-supply-chain trust boundary
while adding the accepted broker/bootstrap slice: the closed tool-registry
schema and validator, unknown-provider `abstain` policy, read-only `/adopt`
inventory, security-audit MEM-8 check, and their targeted mutation sensor were
deleted together. The bounded quick suite did not execute that deleted sensor,
so its green result could not prove preservation of the control.

The regression reproduces on a clean `954a3b6` tree by overlaying only the
parent `tests/verify_tool_trust_inventory.py`: it exits non-zero because
`skills/_shared/itd_harness_controls.py` is absent. The repair hypothesis is to
restore those parent trust surfaces without rolling back or weakening the GPG
bootstrap, retain the targeted test in the suite, and require a new bound
exact-candidate review before any commit or push.

The first recovery review of tree `b52779bea1a8def593d6a4580733a6cd592a01ff`
then exposed why a byte-for-byte parent restoration was insufficient: the
Python validator did not close nested capability metadata, local prompt-bearing
tools could keep `allow` after `promptTextReviewed=false`, the adoption sensor
covered only one of five forbidden mutations, and the targeted test was absent
from both local aggregators and CI. The bounded repair aligns the nested
validator/schema, applies the unreviewed-allow rule to every declared prompt
surface, mutation-tests all adoption prohibitions, and wires a stdlib phase
into Linux/Windows CI plus the full local test in `run-all.sh`.
The next checker found one pre-existing stale semantic-navigation integrity
fixture: its hard-coded expected demand hash no longer matched either the
registry or the tracked `DEMAND.json`. Updating that test constant to the
independently recomputed tracked-file SHA restores the intended exact binding;
it does not change the demand artifact or trust disposition.

## Regression evidence

RED reproduced all four failures. GREEN results on the replacement staged WIP:

- machine oracle `45/45`;
- guarded hooks `30/30`;
- GitHub App manifest `19/19`;
- review broker `569/569`, primitives `160/160`, policy `130/130`, broker
  server `45/45`, and deployment `24/24`;
- adoption cold-start all pass and bounded quick aggregator `DONE fails:none`;
- external-review release oracle: 14 criteria, `PASSED`;
- host adapters: 28 shared registrations and all 11 hard gates;
- meta-review: zero Critical findings, `PASSED`;
- `bash tests/run-all.sh --quick`: `DONE fails:none`.

An oversized intermediate tree was correctly rejected before provider dispatch;
the next bounded tree received warnings, not acceptance. Narration was compacted,
never the review input or implementation. A new exact tree and current machine,
Terra, and adjudication receipts are still required; GPG-001 remains
`in_progress`.

## GPG-001 credential-boundary and admission-order regression

The free-review producer CLI lacked an enforced protected-release boundary,
and the broker acquired an installation token before validating the producer's
signed phase-one receipt. As a result, candidate-controlled producer code could
run in the same process that reads reviewer subscription auth and the producer
signing key, while unauthenticated inputs could spend GitHub App authentication
and outbound-request capacity before proving admission.

The first defect reproduces when
`skills/_shared/itd_free_reviewer_producer.py` is executed from the same Git
worktree passed as `--root`: no guard rejects that candidate-owned executable
before `transport_home()` and `read_provenance_private_key()`. The second
reproduces with a phase-one envelope carrying an invalid signature:
`bind_free_review()` calls `_token()` before `_authorized_free_reviewer_keys()`,
so the fake App authenticator observes an installation-token request even though
the envelope is rejected.

The bounded repair is to require the credential-bearing producer entry point to
come from outside the candidate repository's resolved Git top level and to run
that check before freezing candidate data or reading credentials. The broker
must resolve only the local enrolled App identity, authenticate and authorize
the phase-one receipt, and request the installation token only after that
verification succeeds. Regression tests must prove both fail-closed ordering
properties and preserve the successful two-phase publication path.

## GPG-001 deployment-profile overfitting

The nine-point plan mixed portable review invariants with one pilot deployment:
an organization-owned private GitHub App plus an organization workflow ruleset.
That made an implementation choice look like a methodology requirement and did
not model users who own and merge their own projects, external repository
owners, self-hosted installations, or a future managed public App.

The defect is reproduced by the manifest bootstrap accepting only
`--organization`, always emitting `public: false`, and the plan/documentation
describing the private organization path as the sole deployment. The trust
property does not require those choices. It requires only that the exact
candidate be reviewed independently, that the reviewer App cannot merge or
deploy, and that any server-side enforcement be installed by the repository
owner.

The repair keeps the nine ordered stages but separates three dimensions:
portable roles, deployment profiles (`local-submission`, `self-hosted-app`,
`managed-app`), and protection profiles. Maker, maintainer, and deployer roles
may overlap; the independent reviewer must differ from the maker. A self-hosted
App may be private or public and may be registered by a user or organization;
a managed App is public. Only the strongest organization-workflow profile may
claim `PROTECTED`; weaker profiles remain useful without overstating GitHub
enforcement.

## GPG-001 reviewer-identity canonicalization bypass

The general profile review reproduced a same-model bypass in the free-review
receipt. `_identity()` rejected whitespace-padded maker fields, but
`_reviewer_identity()` only checked that `strip()` was non-empty and returned
the original reviewer strings. The different-model comparison then case-folded
without trimming, so maker model `gpt-5.6-sol` and reviewer model
` gpt-5.6-sol ` were treated as different and could be signed.

The repair is to apply the same canonical whitespace invariant to every
reviewer identity field before phase-one creation or verification. Regression
tests must cover producer creation, independently re-signed receipt
verification, and broker admission with a matching padded key authorization;
all must fail before an App token or GitHub API call.

## Pre-PR gate version-identity regression (PRG-001)

Recorded: 2026-08-21

### Summary

`installed_version()` compared raw Codex and Claude manifest strings before
deriving their release identity, so the trusted Codex cachebuster required by
local plugin reinstall made `1.99.0+codex.*` incompatible with `1.99.0`.

### Reproduction

- Live WSL and Windows `itd gate doctor --all` returned `UNVERIFIED` with
  `Codex/Claude ITD versions differ` for the pair
  `1.99.0+codex.20260820171321` / `1.99.0`.

### Evidence

- Release oracles remained green (mandatory route 83, Verification Loop 87,
  push adjudication 17, Git hooks 30, doctor 44, CLI 112, producer 249), proving
  the failure was deployment integration rather than reviewer semantics.
- Live negative canaries blocked both an unguarded push and a guarded push with
  stale evidence; stale exact-candidate rejection is intentional and excluded
  from the fix.

### Fix Hypothesis

- Parse both manifests into a closed release identity and allow only the exact
  host metadata form `+codex.<token>` on the Codex manifest; preserve strict
  rejection of other metadata, prereleases, malformed versions and core drift.

### Regression Tests

- `tests/verify_gate_profile_doctor.py` — trusted cachebuster parity plus
  hostile version mutations.
