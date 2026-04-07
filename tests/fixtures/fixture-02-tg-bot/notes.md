# Manual verification — fixture 02

After running `/blueprint --lite` or `/kickstart` (Sonnet auto-Lite) on this fixture, verify:

## Mode detection
- [ ] If on Sonnet, the skill announces "Запускаю в режиме Lite"
- [ ] STRATEGIC_PLAN.md is **NOT** generated (Lite mode skips it)
- [ ] CLAUDE_CODE_GUIDE.md is **NOT** generated (Lite delegates this to /guide later)

## PROJECT_ARCHITECTURE.md
- [ ] Tables: at least `masters`, `appointments` (optionally `clients` if explicit)
- [ ] Each table has all columns with types
- [ ] Tech stack: aiogram OR grammY explicitly chosen with reasoning
- [ ] No HTTP API section, OR explicit "API: none — bot uses Telegram Bot API"
- [ ] Reminder mechanism described (cron / asyncio.create_task / APScheduler)
- [ ] Auth: simple admin command rather than full RBAC

## PRD.md
- [ ] At least 3 user stories (Lite mode threshold)
- [ ] P0: book appointment, view my appointments, admin sees all
- [ ] No need for full acceptance criteria (Lite relaxes this)

## IMPLEMENTATION_PLAN.md
- [ ] 4–6 steps (Lite mode)
- [ ] Step 1: bot setup + database schema
- [ ] Each step has specific files and verification

## README.md
- [ ] Quick start in 30 seconds
- [ ] Tech stack section
- [ ] BOT_TOKEN environment variable mentioned in setup

## /review status
- [ ] Run `/review`
- [ ] All Critical pass (C1–C12)
- [ ] C2 (database table OR no-database justification) passes — may be implicit
- [ ] C4 (API endpoint OR no-API justification) passes — must have explicit "API: none — bot uses Telegram Bot API"
- [ ] Status: PASSED or PASSED_WITH_WARNINGS

## Failures (fill in if any)
