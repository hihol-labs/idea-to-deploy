# GPG-001 handoff — canonical profile registry, final exact acceptance next

## 1. Current objective

Continue the existing high-risk `GPG-001` unit with WIP=1. Do not create a new
goal. The nine ordered stages remain intact, but their architecture is now
portable: maker/maintainer/deployer may overlap, only the reviewer differs from
maker, and deployment/protection profiles are selected per project. Paid API,
external writes, merge, deploy, and release require their own authorization.

## 2. Exact repository state

- Repository: `/home/hihol/projects/idea-to-deploy`
- Branch: `codex/harness-lifecycle-trust`
- HEAD: `4a8097613ed2400159c03512fba137382f36ff3f`
- Local branch is five commits ahead of origin before the namespace repair.
- The staged candidate contains the broker/free-review implementation,
  security repairs, portable profile contract, generic App manifest flow,
  canonical gates.json v2 local-review routing, contracts, tests, and this
  checkpoint. Resolve its exact tree after this edit; no earlier receipt
  accepts the self-referential final checkpoint.
- Draft PR #177 is still open and not updated; remote head is `e0384d6`.
- The first guarded publication attempt created the real local v2 registry but
  doctor correctly exposed that all 21 verification commands omitted their
  tracked `tests/` namespace directory. The staged repair declares that
  directory and adds a project-contract canary; no push occurred.

## 3. Completed implementation

- Free producer, signed Ed25519 two-phase receipts, App-side exact live
  revalidation, durable publication recovery, and free-primary routing are
  implemented; automatic paid fallback remains forbidden.
- Candidate-hosted producer code is rejected before subscription auth/signing
  key access. Invalid/foreign receipts and padded identities are rejected
  before App installation-token or GitHub API work.
- `skills/_shared/GATE_DEPLOYMENT_PROFILES.json` defines portable roles,
  `local-submission`, `self-hosted-app`, `managed-app`, and separate protection
  claims. Only `organization-workflow` may claim `PROTECTED`.
- `scripts/itd_github_app_manifest.py` supports user/organization App owners,
  self-hosted private/public Apps, and managed public Apps. Reviewer App
  permissions remain Checks write plus Contents/Metadata/PR read; it cannot
  merge or deploy. A project owner may author, merge, and deploy their own work.
- Canonical `gates.json` v2 now stores deployment/protection profiles. The
  canonical doctor reports the weakest verified claim; local guarded push/PR
  requires the current exact adjudication and performs no App/broker call.
  Legacy v1 remains readable and is never silently migrated.
- Verification Loop `committed-head` mode closes the local-review commit gap:
  a clean single-parent `HEAD` is accepted only when its parent, full tree, and
  binary diff reproduce the staged review context. The default staged mode is
  unchanged; a changed tree, merge commit, or second commit fails closed.

## 4. Latest bound evidence before this checkpoint

- Manifest/profile 30, producer 57, broker full 730, server 50, deployment 25;
  release 14 criteria, meta-review, host adapters, and quick suite passed.
- A fresh general review found and blocked a whitespace same-model bypass; its
  creation, re-signed verification, and broker admission regressions are GREEN.
- Pre-checkpoint general adjudication:
  `.itd-memory/verification-loop/receipts/98b1d51cc1bb7d76/GPG-001-general-review-adjudication-a1.json`.
- Pre-checkpoint security adjudication:
  `.itd-memory/verification-loop/receipts/2a54c162a0da2992/GPG-001-security-review-adjudication-a1.json`.
- Both receipts become stale when this tracked HANDOFF changes. Produce new
  current receipts before commit, push, or PR update.
- The first final profile-registry review on tree `83c5c625...` found the
  self-invalidating staged-review/commit lifecycle and returned `BLOCKED`.
  The committed-head bridge and its negative canaries are the bounded repair;
  they still require fresh general/security adjudication on the new tree.

## 5. Live boundary

- `~/.config/itd/gates.json` now contains the explicit
  `local-submission`/`local-review` profile for this checkout. Its old receipt
  must be replaced after the namespace-repair candidate is reviewed and
  committed; guarded push remains blocked until doctor returns
  `LOCAL_REVIEWED`. Never use `--no-verify` or another bypass.
- No live App/ruleset/provenance mutation is implied by local acceptance.
- `local-submission` needs no repository administration. `self-hosted-app` and
  `managed-app` require the repository owner to install the App; protection
  rules require owner/admin action.
- A concrete maintainer or external repository is a pilot/configuration, not a
  methodology dependency.

## 6. Next exact step

Review the small verification-namespace repair, commit exactly its staged tree,
replace the registry receipt, and require doctor to return `LOCAL_REVIEWED`.
Only then guarded-push the existing branch to update Draft PR #177. The chosen
deployment profile is already explicit; do not silently strengthen it:

1. Establish a stable HTTPS broker target only for an App profile.
2. For self-hosted, register a private/public user/organization App. For
   managed, register the operator public App. The repository owner installs it.
3. Select `local-review`, `app-check`, or `organization-workflow`; run matching
   negative canaries and never call a weaker profile `PROTECTED`.
4. For local-review, review the staged candidate, commit exactly that index as
   one normal single-parent commit, register the receipt, and let doctor verify
   `--candidate-mode committed-head`; do not add a second commit before push.
5. Commit/publish only through the guarded flow after separate authorization;
   Draft PR #177 remains unmodified until then.

## 7. Hard boundaries

- A local receipt is not evidence of live GitHub protection.
- Do not continue with live mutations, commit, or publish until current
  exact-candidate general and security adjudications accept the complete index,
  including this checkpoint. Protection requirements follow the explicitly
  selected profile; no profile selection authorizes merge/deploy.
- Do not raw-push, bypass hooks, use paid API, merge, release, edit installed
  plugin cache, or store secrets in the repository.
- The full PR base-to-candidate diff exceeds the producer direct bound; do not
  truncate it. Use the bounded staged-delta/hierarchical Verification Loop.

## 8. Authoritative inputs

Read, in order: `AGENTS.md`, this file, `.itd-memory/STATE.json`,
`.itd/GPG-001_NINE_POINT_PLAN.md`, `.itd/ACCEPTANCE_CONTRACT.json`
AC11/AC15/AC16, `skills/_shared/GATE_DEPLOYMENT_PROFILES.json`, and
`.itd/VERIFICATION_CONTRACT.json`.

## 9. Session transfer

Open the same WSL path in Codex after stopping the old session. Preserve WIP=1
and revalidate the exact index rather than trusting this narrative.
