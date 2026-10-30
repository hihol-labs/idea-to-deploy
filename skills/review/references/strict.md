# /review - strict route

Read this file whenever any strict selector applies, whatever the Step 0
command of `skills/review/SKILL.md` printed: the command printed `strict` (the
marker `itd-route: strict` or `itd-domain: data-sensitive` in the first 8 KB of
`CLAUDE.md`, `.claude/CLAUDE.md` or `AGENTS.md`), the arguments contain
`--strict`, or the task falls in a strict class of the global rules (ITD's own
critical mechanisms, money, access and secrets, security, deploy, migrations
and production data, external actions). Only a candidate with none of these
selectors takes the minimal route - the host's native review - and never
reaches this file.

## S1. One independent review of the final candidate

For every medium/high/unknown-risk candidate that is going to be published as a
PR, `/review`, `/cross-review` and the Verification Loop use the same producer:
`skills/_shared/itd_free_reviewer_producer.py`. The fixed keyless route is
`Sol -> Terra` and `Terra -> Sol`: exactly one fresh opposite OpenAI
model/session reviews the evidence-bound candidate. `BLOCKED`, `UNVERIFIED`
and `UNAVAILABLE` stop the gate. Anthropic, GitHub Copilot, Antigravity and
paid API adapters are optional separately invoked facilities, not automatic
fallbacks or quorum members.

Approved maker compatibility also routes `gpt-6.1-sol` and `gpt-6-astra`
to `gpt-5.6-terra`. Preserve the observed maker identity in provenance.
These additions do not make either maker a reviewer or standby.

The signed phase-one v2 receipt contains the exact attempt prefix and one fresh
opposite-GPT identity plus its prompt/report. Missing or malformed route
evidence is `UNVERIFIED`, and the broker must reject it before authorization.

For PR publication, pass the producer-emitted prompt/report plus
`--phase-one-receipt` and its trusted `--producer-keyring` to Verification Loop
`checker`. The local gate revalidates the final adjudication with
`--require-mandatory-route`; a generic checker receipt is diagnostic only and
cannot satisfy guarded publication. Never default a missing verdict field.

This route has no caller bypass. A user acknowledgement, a local self-review,
or a request to publish anyway cannot replace its exact-candidate receipt.
The default route uses installed user/subscription authentication and must not
request a provider API key. The Verification Loop adjudication receipt remains
the sole acceptance authority; the shared producer supplies its independent
checker evidence rather than creating a parallel gate.

Convergence (plan sessions 6-10): a high finding from the session's own diff is
fixed and the fixed candidate is reviewed again; a round with only medium
findings may be `ADJUDICATED` by the owner (ADR-007) with a disposition per
finding. Every fixed finding is a new candidate and therefore a new review.

## S2. Evidence-first coverage before semantic review

When `activeFollowup.reviewPolicy.mode=evidence-first`, validate the closed
criterion -> impact class -> exact-tree oracle matrix before semantic review.
Missing coverage is `UNVERIFIED`, even when ordinary tests are green. For
medium/high/unknown risk require one clean fresh opposite-GPT report; combine
every unit, integration and reviewer finding by host adjudication. A clean
later response can never erase earlier negative evidence.

Every active criterion must have closed `reviewEvidence` with non-empty
`impactClasses` and exact-tree passing `oracleIds`; their union must cover the
policy's `requiredImpactClasses`. Treat any gap as `UNVERIFIED` and stop before
the quality rubric.

## S3. One receipt per candidate (plan session 10)

- The final candidate's adjudication receipt is minted under the **bare active
  unit id** (`<unit>`) through the shared workflow in `docs/VERIFICATION_LOOP.md`:
  the machine receipt carries one leg per `reviewEvidence.oracleIds` entry of
  the unit's criteria (for this repository the deterministic review oracle is
  `tests/meta_review.py --verbose`), the checker receipt binds the producer's
  exact prompt, durable report and host-observed maker/checker provenance
  (`targeted` for medium risk, `full` for high/unknown; low risk stays
  machine-only), and the adjudication closes the chain.
- That one receipt is accepted by every consumer while the reviewed tree and
  the diff hash still match: the commit review cache
  (`skills/review/scripts/itd_review_cache.py`), the DoD security gate
  (`hooks/check-dod-before-commit.sh` - the same receipt, when the unit's
  `reviewPolicy.requiredImpactClasses` names `security` and a checker ran), the
  pre-push gate and `itd pr create` (`--candidate-mode committed-head`, valid
  again after exactly one commit of the staged candidate) and the unit closure
  (`itd_goal_verify.py` on the goal ledger, `itd_unit_log.py verified` on the
  STATE ledger). No second model call is made for a candidate that did not
  change.
- There is no `<unit>:general-review` round. A receipt minted under a suffixed
  claim (`:general-review`, `:security-review`) is refused by the cache as
  another unit. A changed candidate - a new tree or a new diff - needs a new
  review; nothing relabels or reissues an old receipt.
- A strict candidate whose receipt lacks security coverage keeps the security
  gate closed; a machine-only (low) receipt never unlocks it.

## S4. Record the receipt

Persist the real status against the exact repository/base/tree/diff, scope and
acceptance contracts, rubric/version and risk tier. Only an accepted verdict
for that complete key is reusable: it pays down the **general** risk bucket and,
when the receipt covers security, the **security** bucket as well. `BLOCKED`
and `UNVERIFIED` are deliberately recorded as rejected and overwrite any stale
pass for the same checkout.

`PASSED*` is proof-carrying: record it only with the adjudication receipt of
S3. For `PASSED_WITH_WARNINGS`, add one durable `--warning` argument per
warning in the form `path: summary`; an empty warning list is rejected.

```bash
RC="skills/review/scripts/itd_review_cache.py"
[ -f "$RC" ] || RC="$HOME/.claude/idea-to-deploy/skills/review/scripts/itd_review_cache.py"
SHD="skills/_shared"
[ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/idea-to-deploy/skills/_shared"
sh "$SHD/itd_py.sh" "$RC" record --root . --kind general --verdict PASSED \
  --verification-receipt "$ADJUDICATION_RECEIPT"
```

`BLOCKED`/`UNVERIFIED` are recorded without a receipt and remain non-gating.
Plain verdict text or a generic SubagentStop payload can never mint a cache hit.
The workflow caller runs this explicit producer only after accepting the
independent verdict; `hooks/verdict-contract.sh` validates the JSON shape and
records non-gating findings but never writes cache evidence. Rationale and
recovery rules: `references/runner-and-recovery.md` §5.

## S5. Ledger-close candidates: provenance is verified by the machine

A pure ledger close (only `.itd-memory/STATE.json`, the closing fields of the
acceptance contract's active followup and declared ledger files) inherits the
delivered unit's coverage. Before the model review of such a candidate the
producer (`itd_free_reviewer_producer.py freeze_packet`) resolves every commit
named in the scope's "Start from" line and in the added ledger lines, relates
them with `git merge-base --is-ancestor` and `git rev-parse <sha>^`, and hands
the result to the reviewer as `MACHINE-VERIFIED PROVENANCE`. The scope must
name its start commit ("Start from merged main `<sha>`"); a scope that names
no start commit, a start token that does not resolve to a unique commit, or a
start commit outside the candidate's history is `UNVERIFIED` before any model
call - the ancestry proof is required, never inferred. The
reviewer must not infer parent/child relations from ledger text: the
REL-1.109.1 close review blocked on "582a093 vs 4993649" when the first is the
parent of the second.
