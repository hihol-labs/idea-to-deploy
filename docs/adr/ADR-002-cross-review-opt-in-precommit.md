# ADR-002: cross-vendor review is opt-in at pre-commit, never always-on

**Date:** 2026-06-29
**Status:** Accepted
**Review date:** 2026-09-29 (90 days) — or earlier if Claude Code ships a native
multi-vendor review surface, or if a repo owner's data-egress posture changes.

## Context

`/cross-review` (v1.30.0) gets an independent second opinion on a diff from a
*different* vendor's model (OpenAI Codex CLI / Google Gemini CLI), to catch the
blind spots a Claude-only `/review` shares with the Claude-written code. It is
**on-demand**: a human invokes it, fail-open, never a gate.

The question raised was whether to make it **continuous / automatic** — review
every change a Claude session writes, with a third-party model, by default. The
intuition (shift-left, catch regressions early) is sound; the naive
implementation (a per-edit or per-turn hook that egresses to OpenAI) is not. A
two-perspective advisory pass (business-analyst + devils-advocate) surfaced three
structural defects in "always-on by default":

1. **Privacy / governance.** On-demand, the human invoking the skill is the real
   egress barrier — they vouch that *this* diff may leave the machine. Automating
   it deletes that barrier and promotes regex scrubbing to sole defense. Regex
   catches secret-*by-format* (`AKIA…`, `sk-…`, private-key blocks) but
   structurally cannot catch secret-*by-meaning*: proprietary business logic, or
   real customer data (legal-entity names, INN/OGRN, amounts) sitting in fixtures.
   Auto-egress of employer/customer code to a third party is a data-governance
   decision, not a UX default.
2. **Quota theater.** Continuous use burns the external quota early in a session;
   thereafter every call silently degrades to Claude-reviews-Claude — exactly the
   same-vendor blind spot the feature exists to escape — with no honest signal.
3. **Self-contradiction with the environment.** Always-on collides with: a flaky
   VPN where an external CLI can hang to its full timeout on *every* turn; the
   methodology's own multi-agent / shared-worktree topology (where "the diff" is
   undefined and a Stop/per-edit hook could egress another agent's code); and the
   already-integrated, in-vendor `/security-guidance-setup`, which already owns
   the *continuous* shift-left layer with **no** third-party egress.

A specific owner approval is on record for the orbis project: the code owner
sanctioned running orbis through Claude Code and explicitly wanted "code written
by one model checked by another model." That clears the *governance* objection
**for that repo** — but only via an explicit, auditable opt-in, and it does not
remove the *engineering* objections (latency, worktree hazard, quota theater),
which are independent of consent.

## Decision

**Cross-vendor review stays on-demand by default. A continuous variant exists
only as an opt-in pre-commit hook (`hooks/cross-review-precommit.sh`), never as
an always-on per-edit (`PostToolUse`) or per-turn (`Stop`) layer.**

The hook:

- is **DEFAULT-OFF**; egress happens only on explicit opt-in, via env
  `CROSS_REVIEW_EGRESS_OK=1` (per-machine) or a `.cross-review-egress-ok` marker
  file at the repo root. The marker is detected by **presence in the working
  tree**, so it can be local/untracked (e.g. `.git/info/exclude`) and never enter
  a commit or PR — nothing lands in the reviewed repo; committing it is reserved
  for a deliberate team-wide opt-in. Never inherited from a global default; an
  employer repo is enabled only with the owner's sign-off (orbis: granted — via a
  per-machine env/local marker on the developer's box, not a committed file).
- triggers **only on sensitive paths** (migration / money / auth — the same
  signals as the DoD gate, `check-dod-before-commit.sh`), so ordinary commits are
  untaxed.
- is **async + non-blocking**: it scrubs the diff, dispatches a *detached
  background* codex→gemini review (or an honest "unavailable" note), and returns
  immediately. It MUST NOT block the commit and MUST NOT write the
  `/tmp/claude-review-done-*` sentinel — `/review` remains the mandatory floor.
- **auto-disables** unconditionally in a linked/secondary worktree; the bare
  Agent Teams flag also disables it but is overridable with
  `CROSS_REVIEW_ALLOW_AGENT_TEAMS=1` (v1.34.2 — so machines that run Agent Teams
  as their default can still use the hook). Refuses to egress if a high-confidence
  secret survives scrubbing.
- hard off-switch: `ITD_CROSS_REVIEW=0`.

This is consistent with ADR-001 (no own runtime): the hook is code that runs on
the existing Claude Code hook engine; it ships no service and operates nothing.

## Consequences

- **Continuous coverage with zero third-party egress** stays owned by
  `/security-guidance-setup` (in-vendor). Cross-vendor depth is a deliberate
  ceiling: on-demand `/cross-review` by default, plus an opt-in pre-commit pass on
  sensitive diffs where the decorrelated second opinion pays for its cost.
- The hook count rises 19 → 20 (it is the first **fail-open, non-blocking**
  PreToolUse-on-commit hook — the opposite posture to the DoD gate it sits beside).
- Latency lands at a natural checkpoint (commit), not inside the iteration loop,
  and never on the critical path (background dispatch).
- Residual risk: regex scrubbing still cannot redact secret-by-meaning. Mitigation
  is the per-repo opt-in (a human decided this repo's code may egress) plus the
  sensitive-path scoping — not a claim that scrubbing is complete.
- Revisit if Claude Code gains a native cross-vendor review surface, or if a
  repo's egress posture changes (re-evaluate the marker, not the code).
