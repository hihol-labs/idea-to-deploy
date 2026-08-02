---
project: /home/hihol/projects/idea-to-deploy
stage: transition
from_role: release-operator
to_role: next-unit-maker
reason: GPG-002 completed; GPG-003 authorized
unit: GPG-002
status: completed
---

# Handoff — GPG-002 complete, GPG-003 next

> [!todo] First action
> Merge the GPG-002 reconciliation PR, then open one new WIP=1 unit GPG-003
> for the unified mandatory keyless independent-review workflow.

## 1. Completed outcome

- GPG-001 remains verified under the portable
  `local-submission` / `local-review` profile. The claim is
  `LOCAL_REVIEWED`, never `PROTECTED`.
- GPG-002 fixed the native-Windows UNC doctor cold-start boundary without
  weakening receipt, path, candidate, risk or child-probe validation.
- Standard and extended Windows UNC shares receive a bounded 180-second outer
  adjudication timeout; drive, device, extended-local and incomplete UNC paths
  retain 30 seconds.
- PR #180 merged as `ed33169e8cc48f6a5da314586548ee0c5e2389cd`.
- Release PR #181 merged as `1422c94d28f7a6821f0038a766437b7618cc22f1`.
- Version 1.95.1 is installed and enabled in WSL and Windows Codex; both Claude
  installs have zero drift when checked from the clean merge archive. Five
  load-bearing repo/source/cache files are byte-identical on both hosts.
- A Windows-native committed-head machine/checker/adjudication chain is bound
  to `\\wsl.localhost\Ubuntu-24.04\home\hihol\projects\idea-to-deploy`.
  The real installed doctor returned `LOCAL_REVIEWED`, `drift=[]`,
  `protected=0`, version 1.95.1, in 32.57 seconds.
- The legacy credential returned GitHub 401 before cleanup. Five local branch
  remote URLs were sanitized; the final credential-bearing GitHub URL count is
  zero. The credential value was not persisted.

## 2. Authoritative evidence

- Completion index: `.itd/GPG-002_COMPLETION_EVIDENCE.json`.
- Root cause: `.itd/GPG-002_ROOT_CAUSE.md`.
- Feature adjudication:
  `.itd-memory/verification-loop/GPG-002-fix-final-adjudication.json`.
- Windows final adjudication:
  `.itd-memory/verification-loop/receipts/811a95a4aa31177c/GPG-002-windows-unc-live-adjudication-a1.json`.
- Windows candidate digest:
  `sha256:811a95a4aa31177c182254d7a12852d2a9e1f4a5acf4223f93d577557c3e6599`.
- Windows adjudication receipt SHA-256:
  `0dabd737b3a711c96c53f598529611708234cb790db03e59b535d46984438d09`.
- Release live evidence: `20260802T215518Z-a3bff95a`, strict replay 95/95,
  meta-review PASSED.
- PR #180 and #181 both passed `Gate 1 — meta-review rubric` and
  `windows-verify`.

## 3. GPG-003 authorized requirement

The user rejected multiple substitutable review paths. The next unit must make
one mandatory pre-PR independent-review workflow authoritative for `/review`,
`/cross-review` and the Verification Loop:

1. fresh different OpenAI model and session, without development context;
2. if unavailable, Anthropic;
3. if unavailable, Gemini;
4. if all are unavailable, fail closed — no caller/user bypass;
5. the default route must not require `OPENAI_API_KEY` or silently substitute a
   paid Responses API call;
6. WSL and native Windows must have parity tests and installed-host proof.

The paid API reviewer may remain only as a separately named, separately
authorized operation, or be removed from the default surface. App-backed
`PROTECTED` enforcement remains a distinct optional profile and is not required
for independent local review.

## 4. Guardrails

- Preserve WIP=1: do not start GPG-003 until the GPG-002 reconciliation PR is
  merged.
- Preserve exact staged/committed-head Verification Loop receipts and fresh
  different-model checker requirements.
- Do not expose reviewer credentials to candidate code or model context.
- Do not treat same-session/inherited-context review, generic CLI availability,
  outage, missing auth, incomplete output, caller consent or prose as PASS.
- Do not grant the reviewer merge/deploy rights; repository owner/maintainer
  retains those actions.
- Do not edit installed Codex caches directly. Publish and install a new patch
  release for GPG-003.

## 5. Useful checks

```bash
git status --short --branch
python3 scripts/itd.py gate doctor --repository hihol-labs/idea-to-deploy
bash tests/run-all.sh --quick
codex plugin list | grep idea-to-deploy
```

Windows:

```powershell
codex plugin list | Select-String idea-to-deploy
```

## 6. Current external state

- Canonical origin uses credential-free HTTPS:
  `https://github.com/hihol-labs/idea-to-deploy.git`.
- WSL and Windows registries each contain one
  `hihol-labs/idea-to-deploy` local-review row and report
  `LOCAL_REVIEWED` on their host-native current receipt.
- No GitHub tag or GitHub Release was created; the release runbook does not
  require them.
