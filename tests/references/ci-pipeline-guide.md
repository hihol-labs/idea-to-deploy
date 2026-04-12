# CI Pipeline Guide — Production-Ready (GSD-inspired)

## Текущее состояние (v1.16.0+)

Headless execution уже работает:
```bash
bash tests/run-fixture-headless.sh fixture-02-tg-bot
```

## Расширения для production CI (v1.18.0)

### 1. Headless query (JSON snapshot без LLM)

Быстрая проверка состояния методологии без вызова Claude:
```bash
# Structural checks only — $0 cost
python3 tests/meta_review.py
python3 tests/verify_snapshot.py tests/fixtures/fixture-01-saas-clinic
```

### 2. Tiered CI pipeline

| Tier | Trigger | Cost | What |
|---|---|---|---|
| **Structural** | Every PR | $0 | meta_review.py (23 checks) |
| **Snapshot** | Every PR | $0 | verify_snapshot.py (3 active fixtures) |
| **Smoke** | Release branches | ~$5 | 1 fixture headless run (Sonnet) |
| **Full** | Manual / weekly | ~$30 | All active fixtures headless (Sonnet) |

### 3. Budget control

GSD v2 имеет per-unit budget ceiling. Наш аналог:
```bash
# Бюджет на fixture run
bash tests/run-fixture-headless.sh fixture-01 --budget 10.00

# Бюджет на весь CI run
MAX_CI_BUDGET=50.00 bash tests/run-all-fixtures.sh
```

### 4. GitHub Actions workflow

`.github/workflows/fixture-smoke.yml` уже подготовлен (disabled by default).
Для активации:
1. Добавить `ANTHROPIC_API_KEY` в GitHub Secrets
2. Убрать `if: false` guard
3. Push в `release/*` ветку

### 5. Cost reporting

После каждого CI run генерировать cost report:
```json
{
  "run_date": "2026-04-12",
  "fixtures_run": 3,
  "total_cost_usd": 4.73,
  "by_fixture": {
    "fixture-01": {"cost": 1.50, "duration_sec": 480, "status": "PASSED"},
    "fixture-02": {"cost": 1.73, "duration_sec": 600, "status": "PASSED"},
    "fixture-03": {"cost": 1.50, "duration_sec": 420, "status": "PASSED"}
  }
}
```

### 6. Crash recovery в CI

Если headless run крашится:
1. Проверить `/tmp/claude-checkpoint-*.json` (crash-recovery hook)
2. Retry с exponential backoff (1x, 2x, 4x)
3. После 3 retry — mark as FAILED, сохранить output для анализа

```bash
# В run-fixture-headless.sh
MAX_RETRIES=3
for i in $(seq 1 $MAX_RETRIES); do
  if run_fixture "$FIXTURE"; then
    break
  fi
  echo "Retry $i/$MAX_RETRIES (backoff: $((2**i))s)"
  sleep $((2**i))
done
```
