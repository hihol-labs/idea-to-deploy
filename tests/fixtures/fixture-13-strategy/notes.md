# Fixture 13 notes

## Why this fixture exists

Фиксирует, что /strategy работает на EXISTING проекте и обновляет LAUNCH_PLAN.md + ADR, а не генерирует документацию с нуля (это домен /blueprint).

## Known limitations

- Fixture is `status: pending` — verify_snapshot.py авто-пассит без content-валидации.
- Качество стратегических альтернатив (A/B) не проверяется — только наличие секций.
- Нет реальных метрик/CSV для подпитки Situation Analysis — только prompt-контекст.

## Run manually

1. `cd tests/fixtures/fixture-13-strategy/`
2. `mkdir -p output && cd output`
3. Start Claude Code session, paste idea.md content, invoke /strategy.
4. After it finishes: `cd .. && python3 ../../verify_snapshot.py .`
