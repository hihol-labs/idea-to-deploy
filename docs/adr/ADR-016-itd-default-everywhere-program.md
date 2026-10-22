# ADR-016: The ITD change program - a bounded lift of ADR-012 item 5 to make ITD the light default everywhere

- **Status:** accepted (owner decision 2026-10-20: the final change plan approved as a whole and the pause of ADR-012
  item 5 lifted for this program only; recorded in plan session 2, 2026-10-21)
- **Amends:** [ADR-012](ADR-012-minimal-path-default.md) item 5 ("methodology development stops") for exactly the
  program in item 2 below, and replaces ADR-012's rejection of "Editing the managed methodology block" for plan
  session 4. Does not touch ADR-012 items 1-4 and 6-8 (the owner's minimal path, the human gates, the neuroexpert
  class check and leak journal), [ADR-006](ADR-006-single-opposite-gpt-review.md),
  [ADR-007](ADR-007-human-adjudication-of-independent-review.md), [ADR-011](ADR-011-default-risk-tier-low.md),
  [ADR-013](ADR-013-graph-lite-measured-exception.md) / [ADR-014](ADR-014-conditional-graph.md) (Graph Lite stays
  default-off) or [ADR-015](ADR-015-installation-owned-methodology.md), and keeps GATE-OPTIN-1
  (`.itd/DECISIONS.md` 2026-10-16) unchanged.

## Context

ADR-012 (2026-10-06) stopped methodology development after the value measurement showed no catch-rate gain for the
route at a 3-17x time cost. On 2026-10-20 the owner asked for a final plan, in line with the 2026 market, under which
ITD is the default methodology for every project on this machine. The assessment of the "ITD simplification plan"
(15 parts, three independent judges, verdict `implement_restructured`; working materials in the git-excluded
`scratchpad/plan-simplification-analysis/`) found the cost where the owner meets it every day, not in the
methodology's own gates:

- 18 hook processes on one Bash call on the owner's install (16 of ITD, 2 of context-mode) and a two-layer
  instruction set (a 167-line MANDATORY
  managed block plus a personal section after `ITD:END` that overrides it);
- skill texts of 455 (session-save), 473 (task) and 674 (adopt) lines, above the 500-line body limit of the Agent
  Skills standard;
- the accounting close of a release: 94 minutes and 6 model sessions for the 3-file ledger diff of REL-1.109.1, and
  19 precommit checker reports and 13 opposite-GPT attempts for REL-1.109.2;
- false denies of the external-write gate on ordinary local work (fixed in 1.109.2, plan session 1, which ADR-012
  item 5 already allowed because it blocked product work).

The numbers, each with the command that produced it, are in
[`docs/measurements/ITD-SIMPLIFY-BASELINE.md`](../measurements/ITD-SIMPLIFY-BASELINE.md).

## Decision

1. **Goal: "ITD by default everywhere".** Every project on this machine - existing and new, on WSL and on Windows,
   in Claude Code and in Codex - gets the ITD rules, hooks and skills without onboarding. By default ITD is light and
   fast; strictness switches on where it is needed: ITD's own critical mechanisms, strict projects such as invoices,
   money, access, deploy and external actions. In existing projects there are no old rule blocks, duplicate hooks,
   copied tools or stale goals; strict projects keep their contracts and gates without a downgrade; all of it is
   checked by one machine command, not by word.
2. **Scope of the lift: exactly these sessions.** One session is one plan item and, except sessions 3 and 12 (local
   configuration only), one PR:

   | # | Session | Result |
   |---|---|---|
   | 1 | Patch 1.109.2 (done, v1.109.2) | false denies removed, Gate 1 docs freshness kept green |
   | 2 | ADR-016 and baseline (this record) | lawful entry into the program, the "before" measurement |
   | 3 | Owner configuration on both hosts (no PR) | quick win without code, the "after" measurement |
   | 4 | Short global instructions | one rule layer for Claude and Codex, managed block of at most 60 lines |
   | 5 | Hooks by default | core on, diagnostics off, Codex reads the same lists |
   | 6 | Hook latency | one process per event, median latency -50% |
   | 7 | session-save and handoff | one continuity document, the skill at most 200 lines |
   | 8 | bugfix, test, refactor | strict steps by profile, texts at most 500 lines |
   | 9 | task and adopt | thin router, adopt is a pointer |
   | 10 | One review per candidate | the receipt is reused, native review for ordinary work |
   | 11 | Release 1.110.0 | release and rollout on the four host x OS combinations |
   | 12 | ITD by default on the whole machine (no PR) | audit and cleanup of all projects, smoke of a new project |
   | 13 | Final measurement and decision | "after" metrics, a 30-day journal, decision on sessions 14-15 |
   | 14 | Conditional: narrow machine closure in code | only if the journal shows a residual closure cost |
   | 15 | Conditional: removal of the unused | only after 30 days of operation |

   Anything outside this table stays under ADR-012 item 5. The second sentence of item 5 stays in force: a new check
   becomes mandatory only after it wins a measurement of the same kind.
3. **The managed block may be rewritten.** ADR-012 rejected editing `docs/templates/global-claude-md.md` because six
   tests read it and the personal section reached the same result. That rejection is replaced for session 4: the
   managed block (Claude and Codex templates) is rewritten to at most 60 lines together with the tests and
   `docs/instruction-registry.json` that read it, after which the personal section holds only personal data.
4. **Rules of every session** (plan section 4):
   1. WIP=1: the next session starts only after the current one passes its acceptance.
   2. One session - one PR (sessions 3 and 12 change only local configuration).
   3. Tests for the change and a suite run before the commit; changes to the installation and hooks are checked on
      WSL and on Windows.
   4. One independent review of the final candidate before publication; fixing a finding makes a new candidate.
   5. No separate ledger-close PR: the completion record rides in the same PR or the next one.
   6. Push, PR, release and global configuration changes happen only on the owner's confirmation.
   7. Changes to critical mechanisms (hooks, trust policy, pre-push, CI, the installation runtime) are accepted by
      the policy in force. A new lighter rule does not approve itself: it applies from the first candidate after the
      PR that merged it.
5. **GATE-OPTIN-1 is kept.** `hihol-labs/idea-to-deploy` stays registered in the pre-push gate and its critical paths
   keep the strict route; product repositories keep pushing through the opt-in gate as decided on 2026-10-16. The
   program does not migrate the ITD repository itself to the minimal path.
6. **Stop rule.** The program stops at a session that misses its own acceptance in the plan: for a session whose
   acceptance sets an improvement target (3-10, 12, and 14-15 when they run), no measurable gain against the
   baseline on that target; for the record, measurement and release sessions (2, 11, 13), an unmet acceptance item
   (session 2: ADR and convention accepted by one review, every baseline number with its command). It also stops at
   any session that breaks a gate - a hard-gate test goes red, a false "done", an egress or secret leak, invoices
   behaves differently than before. Then the candidate is not merged (or a merged one is reverted), the next
   session does not start, and the owner decides in `.itd/DECISIONS.md` whether and how to continue.
7. **Closure convention.** A release or ledger close whose candidate tree did not change after its accepted review is
   closed by a machine delta check plus the owner's signature under ADR-007, without a new model round
   (`docs/RELEASE_RUNBOOK.md`, "Конвенция закрытия"). By rule 4.7 it applies from the first close after this record
   is merged. A close here is a separate accounting close of an already published candidate; the completion
   records of sessions 2-10 ride inside the next program PR (rule 4.5) and are reviewed with it, so the convention
   does not govern them. Its first planned use is the release close of session 11.
8. **Measurement.** The baseline is taken in session 2, repeated "after" in sessions 3 and 6 for their acceptance
   and in full in session 13 against plan section 2. Time is measured from transcript and hook timestamps, not from
   the agent's own estimate. Quality conditions hold throughout: hard-gate tests green, egress and secrets protected,
   invoices unchanged, no false "done", user hooks and settings preserved on update.

## Consequences

- The program has a lawful entry and a fixed end: 13 sessions plus two conditional ones, each with its own
  acceptance and the stop rule; it cannot grow into a new open-ended methodology repair.
- The owner's minimal path (ADR-012 items 1-4) stays the working route for product work during the whole program.
- The plan itself lives in the git-excluded scratchpad; this record and the baseline document are its durable part
  in git. A session whose plan text changes needs the owner's decision recorded in `.itd/DECISIONS.md`.
- Sessions 5 and 6 change the live-benchmark pin; one live run per such session is budgeted in advance.

## Rejected

- **Migrating the ITD repository to the minimal path**: GATE-OPTIN-1 stays; ITD's own critical changes stay strict.
- **A 12-pair pilot on four host x OS combinations**: the before/after measurement on real work and the 30-day
  journal answer the question cheaper.
- **A new profile engine, a JSON classifier of critical paths, an own CI routing of closures or a release runner.**
- **New mandatory checks without a measured win**: ADR-012 item 5, second sentence, stays in force.
