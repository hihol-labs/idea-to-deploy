---
name: cross-review
description: 'Cross-vendor second-opinion code review — runs an INDEPENDENT external model (OpenAI Codex CLI or Gemini CLI) over the current diff to catch blind spots that a Claude-only review (/review) systematically shares with the code it produced. Use when the user wants a second opinion from a different vendor/model, a cross-review, a cross-vendor review, or to have codex/gemini review the diff. Fail-open and additive: it NEVER replaces or gates /review — the native /review remains the mandatory quality floor; cross-review is a bonus ceiling that gracefully degrades (codex -> gemini -> native Claude red-team self-review) when an external CLI is missing or out of quota. Scrubs secrets/PII out of the diff before sending anything to a third-party CLI.'
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

Ported from the omnigent concept "one vendor reviews another vendor's code" — as
an **outcome** (get an independent second opinion), not as omnigent's
orchestration server. When Claude both writes and reviews the code (`/review`),
the reviewer shares the author's blind spots. `/cross-review` sends the diff to a
**different** model (OpenAI Codex CLI or Google Gemini CLI) and folds its findings
back into the review notes.

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
(the mandatory Claude review). `/cross-review` is specifically the *cross-vendor /
second-opinion* request and is always additive to `/review`, never a substitute.

## Recommended model

**sonnet** — Orchestration only: scrub the diff, shell out to an external CLI,
parse and summarize its findings. No heavy generation. Set via `/model sonnet`.

## Core principle — fail-open, never a gate

1. **`/review` is the floor.** The mandatory Claude review is unaffected by this
   skill. `/cross-review` adds an independent opinion on top; it MUST NOT be a
   commit gate and MUST NOT write the `/tmp/claude-review-done-*` marker (that
   would let someone skip the real `/review`).
2. **Graceful degradation chain:** try `codex` → if missing/erroring/out of quota,
   try `gemini` → if also unavailable, fall back to a **native Claude red-team
   self-review** of the diff and clearly say the external second opinion was
   unavailable. The methodology's effectiveness never depends on a third-party
   CLI being installed or in-quota.
3. **Quota exhaustion == not installed.** A non-zero exit, auth error, or
   rate-limit/quota message from the external CLI is treated the same as "CLI not
   present": note it, degrade, continue. Never block the workflow.

## Steps

1. **Resolve the diff.** Use the argument as the range/path; default to the working
   tree plus staged changes:
   ```bash
   # $ARGUMENTS may be "HEAD~3", "main...HEAD", a path, or empty
   git diff ${ARGUMENTS:-HEAD} 2>/dev/null || git diff
   ```
   If the diff is empty, tell the user there is nothing to cross-review and stop.

2. **Scrub secrets/PII before egress.** Sending the diff to a third-party CLI is
   egress. Before sending, redact anything that looks like a secret or PII
   (API keys, private keys, Bearer tokens, emails, `password=`/`token=` values).
   The `pii-egress-guard.sh` hook is a backstop, not a substitute — scrub in the
   skill too. If the diff cannot be safely scrubbed and still contains a live
   credential, do NOT send it externally; degrade to the native review and say so.

3. **Detect and run an external reviewer.** See `references/cli-adapters.md` for
   the exact, verified invocations. In short:
   ```bash
   if command -v codex >/dev/null 2>&1; then ENGINE=codex
   elif command -v gemini >/dev/null 2>&1; then ENGINE=gemini
   else ENGINE=none; fi
   ```
   Pipe the scrubbed diff with a focused review prompt (correctness bugs, security,
   missed edge cases) and capture stdout. Treat any non-zero exit as "unavailable".

4. **Fold findings into review notes.** Summarize the external model's findings,
   de-duplicate against what Claude already knows, and present a short ranked list
   (file:line + concrete fix). Always state which engine actually ran (codex /
   gemini / native fallback) so the second opinion's provenance is explicit.

5. **Hand back to the gate.** Remind the user that `/cross-review` does not satisfy
   the `/review` gate — run `/review` if it has not run yet.

## Relationship to `/review` and `/security-guidance-setup`

| Skill | Reviewer | Role | Gates? |
|---|---|---|---|
| `/review` | Claude (this vendor) | Mandatory quality floor | Yes — required before multi-file commit |
| `/cross-review` | External model (codex/gemini), else Claude red-team | Bonus independent second opinion | No — additive, fail-open |
| `/security-guidance-setup` | security-guidance plugin | Continuous shift-left security | No — complements /security-audit |

## Self-validation

Before finishing, verify:
- [ ] The diff was scrubbed of secrets/PII before any external send (or external send was skipped).
- [ ] The degradation chain was honored (codex → gemini → native) and the engine that ran is named.
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

### Example 2: Codex out of quota — graceful degrade

User says: «ревью другой моделью этот PR».

Actions:
1. Resolve diff for the PR range, scrub it.
2. `codex exec ...` → exits non-zero with a quota/rate-limit message.
3. Per the chain, try `gemini` → not installed.
4. Fall back to a native Claude red-team self-review of the diff; clearly state
   "Внешнее второе мнение недоступно (codex: лимит; gemini: не установлен) —
   сделал adversarial self-review Claude. Базовый `/review` это не заменяет."

### Example 3: Nothing to review

User says: «cross review».

Actions:
1. `git diff HEAD` and `git diff` both empty → "Нет изменений для cross-review."
   Stop without calling any external CLI.

## Troubleshooting

### No external CLI installed
Expected and supported. The skill degrades to a native red-team self-review and
says so. Suggest installing `codex` or `gemini` if the user wants a true
cross-vendor opinion, but never require it.

### External CLI hangs
Wrap the external call with a timeout (see `references/cli-adapters.md`). On
timeout, treat as unavailable and degrade.

### The diff contains a real secret that cannot be scrubbed
Do NOT send it externally. Degrade to the native review and tell the user to
rotate/remove the credential.

## Rules (hard)

- **Never gate on `/cross-review`.** It is additive; `/review` is the floor.
- **Never write the `/tmp/claude-review-done-*` marker** — that belongs to `/review`.
- **Always scrub before egress.** A third-party CLI is an external service.
- **Always name the engine that ran.** Provenance of the second opinion matters.
- **Fail open.** Any external error/quota/timeout → degrade, never block.
