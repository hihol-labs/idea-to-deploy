# Fixture 15 notes

## Why this fixture exists

Фиксирует ключевое свойство /advisor: analysis-only, никакой записи файлов. Регрессия если скилл начнёт генерировать артефакты.

## Known limitations

- Fixture is `status: pending` — verify_snapshot.py авто-пассит без content-валидации.
- Качество аргументации pros/cons не проверяется — только наличие секций и отсутствие файлов на диске.
- Вовлечение субагентов (business-analyst, devils-advocate) проверяется косвенно по структуре вывода.

## Run manually

1. `cd tests/fixtures/fixture-15-advisor/`
2. `mkdir -p output && cd output`
3. Start Claude Code session, paste idea.md content, invoke /advisor.
4. After it finishes: `cd .. && python3 ../../verify_snapshot.py .` (убедись, что в output/ только лог, без code/docs).
