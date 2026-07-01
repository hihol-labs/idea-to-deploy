<!-- ITD:BEGIN methodology — managed by scripts/sync-to-active.sh. Edit THIS repo file, not the deployed ~/.claude/CLAUDE.md; sync propagates the block between the ITD:BEGIN/ITD:END markers to every machine and preserves everything outside them (personal sections). -->
# Global development methodology — idea-to-deploy (MANDATORY)

This machine uses the **idea-to-deploy** methodology for ALL software development,
in **every project — new or existing** — unless the user explicitly says
"skip the methodology" (or gives a `SKILL_BYPASS: <reason>`) for that specific task.

This file is a standing user instruction. It overrides ad-hoc / improvised coding.

## Core routing rule

Before writing or changing code, route the work through the methodology instead of
coding from scratch:

- **New project, or a new feature from an idea** → start with `/project` (the router)
  or the `discover → blueprint → kickstart` pipeline. Ask clarifying questions first,
  produce a plan, and **wait for the user's approval before building.**
- **Existing / legacy project not yet onboarded** → run `/adopt` first to map it,
  then proceed with the methodology.
- **Day-to-day task on an existing project** → start with `/task` to route to the
  right skill (bugfix, refactor, perf, test, review, deps-audit, security-audit,
  infra, harden, migrate, deploy, …).

## Always

1. **Plan before code.** Show the plan and wait for approval on any non-trivial work.
2. **Test every change.** Write/extend tests and run them after each step.
3. **Review before commit.** Run `/review`; never commit unreviewed multi-file changes.
4. **Document & persist.** Record decisions; run `/session-save` when wrapping up a session.
5. **Prefer the methodology's skills/agents** over improvising your own ad-hoc process.

## Skill decision (visible line + trigger map)

On every substantive request, the FIRST line of the response declares the skill
decision: `Скилл: /<name>` (then call it via the Skill tool before any
Read/Edit/Bash/Write) or `Скилл: не нужен — <reason>`. Silently skipping is not
allowed; an explicit refusal with a reason IS a valid decision (the enforcement
hook treats it so — see `SKILL_BYPASS`).

Trigger → skill (apply as a rule, not a hint):

- New product/feature from an idea → `/project` (or `/discover` → `/blueprint`).
- Advisory / consulting / "analyze, don't code" → `/advisor`.
- Stress-test a plan/design/architecture before committing → `/grill-me`.
- Product discovery (market, personas, competitors) → `/discover`.
- Meeting / interview prep, drafting questions → `/advisor` (or `/grill-me`).
- Existing-project task → `/task` (routes to bugfix/refactor/test/perf/…).
- End of a working session → `/session-save` (always, before wrapping up).

When several fit, pick the most specific; when none fit, say so in the decision line.
Pure mechanics (file generation, browser ops) and tight back-and-forth wording
iterations are legitimate `Скилл: не нужен` cases — name the reason, don't pretend.

## Bypass

The only way to skip the methodology for a task is an explicit user instruction
("skip the methodology" / "just do it directly") or an explicit `SKILL_BYPASS: <reason>`.
Absent that, apply the methodology — when in doubt, apply it.

> Methodology source (canonical): WSL repo `idea-to-deploy`
> (`/home/hihol/projects/idea-to-deploy`), published as plugin
> `hihol-labs/idea-to-deploy`. 38 skills + 10 agents + 20 hooks.

## Project profiles & markers (v1.35.0)

A project can declare an **opt-in** profile in its own `CLAUDE.md`; unset = default
behaviour. See `docs/project-profiles.md` in the methodology repo.

- **`itd-profile: brownfield`** (or `<!-- itd:brownfield -->`) — feature/maintenance
  on a mature existing codebase. The skill-hint hook suppresses greenfield-pipeline
  skills (`/project`, `/blueprint`, `/discover`, `/kickstart`, `/guide`, `/strategy`,
  `/market-scan`, `/autopilot`); `/task`, `/bugfix`, `/refactor`, `/review`, `/test`,
  `/migrate`, … stay active. On such a project the project's own `CLAUDE.md` is the
  real source of truth — do not force the greenfield pipeline.
- **`itd-domain: data-sensitive`** (or `<!-- itd:data-sensitive -->`) — the project
  mutates production / financial / irreplaceable data. **Gate:** model the change
  read-only first, show before/after, get explicit confirmation, then mutate. Never
  run a data-mutating op (prod write, mass re-post, destructive migration, money
  movement) straight from an ad-hoc command.

**Memory is the continuity backbone.** Checkpoint via `/session-save` on every
meaningful state change (subphase / roadmap item done, migration applied, before a
risky or irreversible op, after an external artifact is sent) — cheap incremental
checkpoints, not one big end-of-session save.

**Read-only Bash does not need a skill line.** Pure inspection (ls/cat/grep/find/
git status|log|diff) is exempt from the skill-decision gate; declare the skill only
before a mutation or a genuine new task.
<!-- ITD:END methodology -->
