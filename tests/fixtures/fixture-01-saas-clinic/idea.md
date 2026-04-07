# Fixture 01: SaaS — clinic management

## User says

> Хочу сделать SaaS для управления небольшими частными клиниками. Нужна запись пациентов на приём, расписание врачей, медкарта пациента (история визитов, диагнозы, назначения), уведомления о визитах за день. Целевые клиники — 5–20 врачей, до 2000 пациентов в базе. Бюджет на старт ~₽200K, монетизация — подписка ₽5000/мес с клиники.

## Why this fixture exists

Tests **Full mode** (`/blueprint` or `/kickstart` on Opus). Exercises:
- Multi-table schema (patients, doctors, appointments, visits, diagnoses, prescriptions)
- Multi-role auth (admin, doctor, receptionist, patient)
- Notification system (cron + email/SMS)
- Subscription billing
- Multi-tenant data isolation

## Expected complexity

- ~6+ database tables
- ~15+ API endpoints
- 4+ user roles
- 8–12 implementation steps in Full mode
