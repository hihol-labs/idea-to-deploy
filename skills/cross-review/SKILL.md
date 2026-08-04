---
name: cross-review
description: 'Run the mandatory independent pre-PR review over the exact candidate through the shared keyless OpenAI, Anthropic, and GitHub Copilot route.'
argument-hint: exact staged candidate or PR preparation target
license: MIT
allowed-tools: Read, Bash
metadata:
  effort: medium
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 2.0.0
  category: quality-assurance
  tags: [code-review, independent-review, exact-candidate, verification-loop]
---

# Cross-Review

`/cross-review` is the explicit independent-review entry point for the same
mandatory pre-PR gate used by `/review` and the Verification Loop. It is not a
second evidence authority and cannot be substituted with a local self-review.

## Trigger phrases

- cross-review, cross review, кросс-ревью, перекрёстное ревью
- review by another model, independent review by another LLM
- ревью другой моделью, независимое ревью другой моделью
- second opinion on the code, второе мнение по коду
- codex review, claude review, copilot review

A plain "review this" or «проверь PR» normally enters through `/review`, but
both skills converge on the same producer and evidence contract.

## Recommended model

The orchestrator uses the active host model. The reviewer model is selected by
the producer and must differ from the maker; callers do not choose a shortcut.

## Mandatory route

Use `skills/_shared/itd_free_reviewer_producer.py`. The fixed keyless order is:

`OpenAI -> Anthropic -> GitHub Copilot`

1. A fresh OpenAI subscription session using a model different from the maker.
2. An isolated Anthropic subscription session if OpenAI returns typed
   `UNAVAILABLE`, or after a clean OpenAI pass when the risk-required independent
   quorum is still unmet.
3. An isolated official GitHub Copilot user-auth session in free `auto` mode if
   Anthropic returns typed `UNAVAILABLE`, or after a clean Anthropic pass when
   the risk-required independent quorum is still unmet.

`BLOCKED` and `UNVERIFIED` are terminal. Invalid output, tool use, missing or
same maker/reviewer provenance, credential leakage, an untrusted executable,
or an inexact candidate is `UNVERIFIED`, not a reason to try another provider.
If all three providers are unavailable, the gate returns `UNAVAILABLE` and PR
publication remains blocked.

Before routing, enforce the active evidence-first coverage matrix. Every active
criterion must declare generic impact classes and exact-tree oracle IDs, and
the union must cover every impact required by `activeFollowup.reviewPolicy`.
Missing/failed/foreign evidence is `UNVERIFIED`; reviewer judgment cannot
substitute for a missing product-scale or business-invariant oracle.

There is no caller bypass. User permission to publish, a same-session review,
or an ordinary local review cannot mint the missing independent evidence. The
default producer uses installed user/subscription authentication; it does not
request provider API keys and does not call a paid API endpoint.

## Workflow

1. Resolve the requested repository. Never silently review the current working
   directory when the user named another target.
2. Freeze the exact staged candidate. Reject unstaged/untracked overlays,
   generic binary diffs, oversized inputs, secret-bearing text, and a mismatch
   with the machine receipt or contracts.
   For an initial local PR, bind the repository while leaving the not-yet-known
   PR number/head SHA null; existing-PR/App review binds both exact coordinates.
   Validate the closed evidence-coverage matrix before provider dispatch. The
   Verification Loop's isolated machine runs are the read-only explorer.
3. Obtain maker provider/model/session from host-observed orchestration
   metadata. Reviewer narration is not provenance.
4. Run the shared producer with content-pinned transports and the fixed route;
   persist its signed phase-one receipt, exact prompt, and canonical report.
   Each reviewer runs in a fresh private home with repository/shell/network
   tools disabled; only provider service transport is available.
   If the complete scrubbed diff exceeds the broker's direct bound, reuse its
   frozen complete-file/UTF-8-line plan: review every one of at most 16 bound
   units through the same selected provider/model, then require a separate
   integration review. Persist and sign the canonical bundle containing the
   plan, every exact unit prompt/report, and the integration prompt; missing or
   changed coverage is `UNVERIFIED`.
   For high/unknown risk, continue the ordered route after the first clean pass
   until two provider/model/session-independent reviewers pass. One blocker or
   unverified contour stops the route; do not seek a favorable vote.
5. **Validate the strict structured verdict.** Enforce the closed JSON schema
   with exactly `verdict/findings/unverified`. Empty, prose-only, or malformed
   output is `UNVERIFIED`; it is not a reason to reinterpret the result as
   green or to ask the same model to repair its untrusted response. A clean
   result has `verdict=PASSED` and both lists empty.
   The host unions every unit, integration and reviewer finding. A later clean
   response cannot delete earlier negative evidence.
6. **Bind the signed route into Verification Loop.** Pass the producer receipt
   and trusted producer keyring as `--phase-one-receipt` and
   `--producer-keyring` to `itd_verification_loop.py checker`, then adjudicate.
   The publication gate requires this route-bound receipt; a generic checker
   cannot satisfy it.

The ordered attempt ledger must name every actual provider status and be bound
inside the signed phase-one receipt. Phase-one v3 additionally binds the full
reviewer list and each reviewer's canonical prompt/report artifact. Never
relabel same-vendor evidence as cross-vendor evidence or claim a provider was
tried when its transport did not run.

## Windows and WSL

The policy and producer are host-neutral Python. On WSL they use the WSL-native
installed CLIs and private POSIX auth copies. On native Windows they use the
Windows-native installed CLIs and private temporary profiles. Do not execute a
Windows credential-bearing CLI through a WSL wrapper, or the inverse. Every
selected launcher/runtime is resolved on the active host and content-pinned
before credentials are exposed.

## Relationship to other workflows

| Entry point | Function | Authority |
|---|---|---|
| `/review` | Full rubric plus required independent checker | Verification Loop adjudication |
| `/cross-review` | Explicit independent checker invocation | Same Verification Loop adjudication |
| `itd_free_reviewer_producer.py` | Ordered keyless quorum transport and signed evidence | Evidence producer only |
| Optional protected GitHub App | Live PR/check countersignature | Extra protected-repository binding |
| Separately configured paid API adapter | Optional operator integration | Cannot replace the mandatory route |

Merge/deploy ownership is outside this skill. A project owner may remain the
only person who merges and deploys; the independent review gate verifies the
candidate before publication or merge without acquiring those permissions.

## Terminal outcomes

- `PASSED`: the risk-required independent reviewer quorum returned clean,
  closed reports and the exact evidence chain can proceed to adjudication.
- `BLOCKED`: real findings exist; fix them and freeze a new candidate.
- `UNVERIFIED`: evidence, isolation, provenance, or output integrity failed;
  repair the cause instead of falling through.
- `UNAVAILABLE`: the current provider transport/auth/service is absent; only
  this status advances as provider fallback. A clean `PASSED` may continue only
  to fill an unmet risk-required quorum; it is not fallback or vote shopping.
  All-provider exhaustion blocks publication until a route becomes available.

## Self-validation

- [ ] Exact staged candidate and machine evidence hashes match.
- [ ] Maker identity came from the host and reviewer model/session differ.
- [ ] High/unknown has at least two authorized independent reviewer identities.
- [ ] Every active criterion/impact has an exact-tree passing oracle ID.
- [ ] Route order and every typed provider outcome are recorded.
- [ ] No provider API key entered the reviewer process.
- [ ] Reviewer tools and inherited development context were disabled.
- [ ] The final claim relies on a current adjudication receipt, not prose.

## Examples

### Example 1: OpenAI route succeeds

A Sol-authored candidate is frozen. The producer starts a fresh Terra session,
gets a closed clean verdict, records OpenAI provenance, and sends the checker
evidence to adjudication. Anthropic and GitHub Copilot are not called.

### Example 2: OpenAI transport is unavailable

The OpenAI adapter returns typed `UNAVAILABLE`. The producer tries Anthropic.
If Anthropic returns `BLOCKED`, the route stops with findings; GitHub Copilot is not
used to seek a more favorable answer.

### Example 3: Every provider is unavailable

The result names OpenAI, Anthropic, and GitHub Copilot as unavailable. PR publication
does not proceed until at least one keyless transport is restored.

## Troubleshooting

- Missing login: authenticate the installed CLI with its normal user or
  subscription login; do not add a provider API key.
- Changed executable pin: inspect the installed update, record its new digest,
  and rerun the exact candidate.
- Same OpenAI model as maker: the producer selects the known alternate model;
  if none is configured, OpenAI is `UNAVAILABLE` and routing may advance.
- Invalid JSON or a tool event: treat it as `UNVERIFIED` and repair the adapter;
  never continue to another provider.
- Native Windows/WSL mismatch: install and authenticate the CLI on the active
  host instead of crossing the credential boundary.

## Rules

- Always use `itd_free_reviewer_producer.py`; do not implement another router.
- Preserve `OpenAI -> Anthropic -> GitHub Copilot`: fallback advances only on
  `UNAVAILABLE`; a clean pass advances only while an explicit quorum is unmet.
- Enforce no caller bypass and no same-context self-certification.
- Never turn missing evidence or provider exhaustion into success.
- Never grant the reviewer merge or deploy permissions.
- Never allow integration or a later reviewer to erase an earlier finding.
