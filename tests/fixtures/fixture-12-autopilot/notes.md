# Fixture 12 notes

## Why this fixture exists

Фиксирует, что /autopilot последовательно проходит все 5 фаз и создаёт ожидаемый набор артефактов.

## Known limitations

- Fixture is `status: pending` — verify_snapshot.py авто-пассит без глубокой валидации.
- Качество каждой отдельной фазы не проверяется — есть отдельные фикстуры на /discover, /blueprint, /kickstart.
- Прогон долгий (все 5 фаз) — запускать вручную редко.

## Run manually

1. `cd tests/fixtures/fixture-12-autopilot/`
2. `mkdir -p output && cd output`
3. Start Claude Code session, paste idea.md content, invoke /autopilot.
4. After it finishes: `cd .. && python3 ../../verify_snapshot.py .`
