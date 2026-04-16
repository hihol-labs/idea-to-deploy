# Fixture 11 notes

## Why this fixture exists

Регрессионно фиксирует, что /discover вызывается и выдаёт DISCOVERY.md с обязательными секциями.

## Known limitations

- Fixture is `status: pending` — verify_snapshot.py авто-пассит без content-валидации.
- Качество рыночных оценок (TAM/SAM/SOM числа) не проверяется — только наличие секций.

## Run manually

1. `cd tests/fixtures/fixture-11-discover/`
2. `mkdir -p output && cd output`
3. Start Claude Code session, paste idea.md content, invoke /discover.
4. After it finishes: `cd .. && python3 ../../verify_snapshot.py .`
