---
name: cross-review
description: 'Independent second-opinion review over an exact staged candidate. Routes by maker provenance and risk across the managed OpenAI Responses API, Codex CLI, and Gemini CLI; labels same-vendor and cross-vendor evidence honestly. Local use is opt-in, advisory, and fail-open. Mandatory acceptance remains owned exclusively by the Verification Loop.'
argument-hint: diff range (e.g. HEAD~3, main...HEAD), a path, or empty for the working tree
license: MIT
allowed-tools: Read, Bash
metadata:
  effort: medium
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.0.0
  category: quality-assurance
  tags: [code-review, cross-vendor, second-opinion, codex, gemini, omnigent-port]
---

# Cross-Review (cross-vendor second opinion)

Ported from the omnigent concept "one reviewer challenges another agent's code"
as an **outcome**, not as an orchestration server. Correlated maker/checker
contexts share blind spots, so `/cross-review` routes an exact staged candidate
to an eligible managed checker and records the real independence class.
Codex/Gemini CLI remain named host-native alternatives, but generic CLI agents
are not automated evidence without a verifiable no-tools/no-secret sandbox.

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill.
They are kept here, not in the description, to avoid diluting the embedding-based
matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list —
keep them in sync.

- cross-review, cross review, кросс-ревью, перекрёстное ревью
- cross-vendor review, кросс-вендор ревью
- review by another model, independent review by another LLM
- ревью другой моделью, независимое ревью другой моделью
- second opinion on the code, второе мнение по коду
- codex review, ревью через codex
- gemini review, ревью через gemini

**Do NOT** route a plain "review this" / "проверь PR" here — that is `/review`
(the mandatory host-neutral review). `/cross-review` is specifically the *independent /
second-opinion* request and is always additive to `/review`, never a substitute.

## Recommended model

**sonnet** — Orchestration only: bind and scrub the diff, call an eligible
managed adapter, then validate its structured findings. No heavy generation.

## Core principle — advisory transport, never a gate

1. **Verification Loop is the only acceptance authority.** `/cross-review`
   adds an opinion and may produce checker artifacts, but it never mints
   completion, a review-cache hit, or the `/tmp/claude-review-done-*` marker.
2. **Maker/risk-aware routing:** the shared policy selects a cross-vendor
   checker first where possible, then an eligible different-model same-vendor
   checker. OpenAI Responses API is the automated adapter; Codex CLI and Gemini
   CLI remain host-native advisory alternatives but are automated-ineligible
   until their isolation and telemetry contracts are enforceable.
3. **Honest degradation:** provider errors, auth/quota exhaustion, invalid
   output, missing consent, incomplete provenance, or incomplete diff coverage
   produce typed `UNAVAILABLE`/`UNVERIFIED`. Local use reports that status and
   continues; it never fabricates a native "external" fallback or a clean pass.
4. **CI semantics differ only in enforcement:** a protected PR check fails
   closed when no policy-eligible exact-candidate evidence exists. It does not
   require one named provider when another eligible checker succeeds.

## Steps

1. **Resolve the exact staged candidate.** API evidence uses the staged index,
   not an arbitrary working-tree slice:
   ```bash
   # $ARGUMENTS may be "HEAD~3", "main...HEAD", a path, or empty
   git diff --cached --name-only
   ```
   If the diff is empty, tell the user there is nothing to cross-review and stop.

2. **Use the one shared egress boundary.** Do not duplicate regexes in this
   skill. `skills/_shared/itd_external_reviewer.py` requires explicit consent,
   rejects binary/incomplete/oversize candidates without truncation, applies
   the canonical sanitizer, and enforces file/byte/token/time/cost budgets.

3. **Route and run one eligible reviewer.** Supply host-observed maker
   provider/model/session and the real risk tier:
   ```bash
   sh skills/_shared/itd_py.sh skills/_shared/itd_external_reviewer.py review \
     --root . --maker-vendor "$MAKER_PROVIDER" --maker-model "$MAKER_MODEL" \
     --maker-session "$MAKER_SESSION" --risk "$RISK_TIER" --mode local
   ```
   Pipe the scrubbed diff with a focused review prompt (correctness bugs, security,
   missed edge cases) and capture stdout. Preserve typed outcomes: exit `2` is
   validated `FINDINGS`, `3` is `UNAVAILABLE`, and `4` is `UNVERIFIED`.

3a. **Structured verdict only.** Responses API uses strict JSON Schema.
   CLI alternatives must return the same closed verdict/findings/unverified
   object. Empty, prose-only, contradictory, unknown-file, or incomplete output
   is `UNVERIFIED`, not a reason to re-interpret text as green.

4. **Fold findings into review notes.** Present the validated ranked findings
   and name provider, model, response/session, independence class, exact tree,
   observed usage/cost, and any earlier provider failures. Never call
   same-vendor evidence cross-vendor.

5. **Hand back to the gate.** Remind the user that `/cross-review` does not satisfy
   the `/review` gate — run `/review` if it has not run yet.

## Relationship to `/review` and `/security-guidance-setup`

| Skill | Reviewer | Role | Gates? |
|---|---|---|---|
| `/review` | Host-selected fresh reviewer | Mandatory quality floor through Verification Loop | Yes |
| `/cross-review` | Managed API by maker/risk policy; Codex/Gemini host-native alternatives | Advisory second opinion; may supply checker artifacts | No, locally |
| CI external review | Same shared transport | Exact-candidate checker evidence | Only through Verification Loop adjudication |
| `/security-guidance-setup` | security-guidance plugin | Continuous shift-left security | No — complements /security-audit |

## Continuous mode — opt-in pre-commit hook (v1.34.0)

On-demand `/cross-review` is the default and covers ~80% of the value: run it by
hand before committing in correctness-critical work (`/bugfix`, `/migrate`,
`/harden`, `/refactor`). For repos that want a checkpoint reminder,
`hooks/cross-review-precommit.sh` fires on `git commit`. It never launches a
generic tool-capable CLI:

- **DEFAULT-OFF.** It does nothing unless you explicitly opt in to external
  egress, via env `CROSS_REVIEW_EGRESS_OK=1` (per-machine) or a
  `.cross-review-egress-ok` marker file at the repo root. The marker is detected
  by **presence in the working tree**, so it can be local/untracked (e.g. listed
  in `.git/info/exclude`) and **never enters a commit or PR** — nothing lands in
  the reviewed repo. Committing the marker is reserved for a deliberate
  team-wide opt-in, not the default. For the common single-developer flow,
  prefer the env var or a local marker, and reach for on-demand `/cross-review`
  when you want to see findings *before* committing.
- **Scoped to sensitive paths only** (migration / money / auth — the same signals
  as the DoD gate), so ordinary commits are never taxed.
- **Non-blocking and no egress.** It emits a reminder to run the canonical
  isolated `/cross-review` workflow. It NEVER blocks the commit and NEVER writes
  the `/review` sentinel — `/review` remains the mandatory floor.
- **Auto-disabled** in a linked/secondary worktree (unconditional — the index may
  hold another agent's staged work). Also disabled under the Agent Teams flag
  (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) **unless** you override with
  `CROSS_REVIEW_ALLOW_AGENT_TEAMS=1` (for machines that run Agent Teams as their
  default and still want the reminder).
- **Hard off-switch:** `ITD_CROSS_REVIEW=0`.

Why opt-in pre-commit and not always-on per-edit/per-turn: see
`docs/adr/ADR-002-cross-review-opt-in-precommit.md` (privacy/governance of
third-party egress, latency under a flaky VPN, multi-agent worktree hazard, and
non-duplication of the in-vendor `/security-guidance-setup` continuous layer).

## Self-validation

Before finishing, verify:
- [ ] The diff was scrubbed of secrets/PII before any external send (or external send was skipped).
- [ ] Maker/risk routing was honored and every attempted provider/status is named.
- [ ] No `/tmp/claude-review-done-*` marker was written (cross-review is not /review).
- [ ] Findings are concrete (file:line + fix), de-duplicated, and ranked.
- [ ] The user was reminded that `/review` is still required.

## Examples

### Example 1: External CLI available

User says: «сделай cross-review текущих изменений».

Actions:
1. `git diff HEAD` → non-empty.
2. Scrub secrets/PII from the diff.
3. `command -v codex` → found → pipe scrubbed diff + review prompt to `codex exec`.
4. Codex returns 3 findings; summarize ranked with file:line, note "engine: codex".
5. Remind: "Это второе мнение. Обязательный `/review` всё ещё нужен — запустить?"

### Example 2: Managed API unavailable — honest degradation

User says: «ревью другой моделью этот PR».

Actions:
1. Resolve diff for the PR range, scrub it.
2. The policy tries eligible providers in maker/risk order.
3. Every eligible provider is unavailable.
4. Return `UNAVAILABLE` with the attempted providers. Local development
   continues, but no independent evidence or clean verdict is claimed.

### Example 3: Nothing to review

User says: «cross review».

Actions:
1. `git diff HEAD` and `git diff` both empty → "Нет изменений для cross-review."
   Stop without calling any external CLI.

## Troubleshooting

### No external CLI installed
Expected and supported. Return typed `UNAVAILABLE` and name the missing
providers. A normal `/review` may still run, but it must not be presented as
the missing independent external opinion.

### External CLI hangs
Wrap the external call with a timeout (see `references/cli-adapters.md`). On
timeout, treat as unavailable and degrade.

### The diff contains a real secret that cannot be scrubbed
Do NOT send it externally. Return `UNVERIFIED`, tell the user to rotate/remove
the credential, and keep the candidate out of an evidence-gated merge.

## Rules (hard)

- **Never gate on the local `/cross-review`.** Only the CI Verification Loop
  adjudication may gate acceptance.
- **Never write the `/tmp/claude-review-done-*` marker** — that belongs to `/review`.
- **Always scrub before egress.** A third-party CLI is an external service.
- **Always name the engine that ran.** Provenance of the second opinion matters.
- **Fail open locally, fail closed at acceptance.** Preserve the typed failure;
  never reinterpret it as success.
