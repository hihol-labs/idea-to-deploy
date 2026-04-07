# Manual verification — fixture 01

After running `/kickstart` (Full mode, Opus) on this fixture, verify:

## STRATEGIC_PLAN.md
- [ ] At least 3 competitors named (e.g., MEDODS, IDENT, Renovatio, Kray)
- [ ] Budget breakdown adds up to ~₽200K or explains why more
- [ ] Subscription model (₽5000/mo) reflected in unit economics
- [ ] At least 3 risks with mitigations

## PROJECT_ARCHITECTURE.md
- [ ] Tables present: `clinics`, `users`, `doctors`, `patients`, `appointments`, `visits` (or close equivalents)
- [ ] Multi-tenant isolation explicitly described (clinic_id FK on every patient/visit row)
- [ ] Auth flow describes 4 roles: admin / doctor / receptionist / patient
- [ ] At least 15 API endpoints
- [ ] Notification system mentioned (cron job for reminders)
- [ ] Database indexes on `clinic_id`, `appointments.starts_at`, `patients.phone`

## PRD.md
- [ ] At least 8 user stories
- [ ] P0 stories cover: registration, appointment booking, viewing schedule, viewing patient history
- [ ] Acceptance criteria for all P0 stories
- [ ] Kill criteria mentions: data loss, regulatory non-compliance (152-ФЗ)

## IMPLEMENTATION_PLAN.md
- [ ] 8–12 steps
- [ ] Step 1 is "scaffold + auth", not "build everything"
- [ ] Multi-tenancy added before any patient-related step
- [ ] Notification system as a separate late step (not entangled with bookings)

## CLAUDE_CODE_GUIDE.md
- [ ] One prompt per implementation step
- [ ] Each prompt mentions specific table names from architecture

## /review status
- [ ] Run `/review` on the output
- [ ] Status should be `PASSED` or `PASSED_WITH_WARNINGS`
- [ ] All Critical checks (C1–C12) pass
- [ ] If `BLOCKED`, log which checks failed in this notes file under "Failures"

## Failures (fill in if any)

(empty unless fixture fails — leave space for documenting regressions)
