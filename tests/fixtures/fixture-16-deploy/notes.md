# Fixture 16 notes

## Why this fixture exists

Stub для /deploy — единственный скилл, требующий live SSH-таргет. Не запускается автоматически, но должен существовать ради `check-skill-completeness.sh` и как якорь для будущих регрессий.

## Known limitations

- Fixture is `status: pending` — verify_snapshot.py авто-пассит без content-валидации.
- Нет ephemeral test host / mocked SSH surface — реальный прогон невозможен в CI.
- Проверка идемпотентности deploy-pipeline отложена.

## Run manually

1. `cd tests/fixtures/fixture-16-deploy/`
2. `mkdir -p output && cd output`
3. Start Claude Code session против тестового SSH-хоста (НЕ основной prod), paste idea.md content, invoke /deploy.
4. After it finishes: `cd .. && python3 ../../verify_snapshot.py .`
