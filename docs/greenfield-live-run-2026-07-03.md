# Акт: live-прогон greenfield-пайплайна (kickstart) — 2026-07-03

> Цель: закрыть остаток аудита 2026-07-02 «greenfield 8/10 — структурно полный,
> но без боевых подтверждений». Метод: штатный headless-раннер фикстур +
> отдельная headless-проба новой init-фазы v1.40.0. Исполнено на WSL
> (claude CLI 2.1.186, model sonnet).

## Ступень 1 — kickstart Phase 1–2 (документация), штатная фикстура

- **Прогон:** `bash tests/run-fixture-headless.sh fixture-01-saas-clinic --keep-output`
  (SaaS-клиника, Full-набор из 7 документов, pre-seeded clarifications).
- **Результат:** все 7 документов сгенерированы; snapshot-валидация после фикса
  валидатора — **PASSED, 33/33 проверок**. Cost: **$1.02** (equiv pay-as-you-go).
- **Находка №1 (исправлена в этом же патче):** `tests/verify_snapshot.py`
  `_API_ENDPOINT_RE` не считал эндпоинты в формате «метод в отдельной ячейке
  таблицы» (`| GET | /api/v1/... |`) — легитимный и частый выход модели дал
  0/15 и ложный FAIL. Регекс расширен четвёртой формой; тот же вывод после
  фикса — 33/33. Дефект валидатора, не генерации.

## Ступень 2 — kickstart Phase 3 (init-фаза v1.40.0), headless-проба

Поверх доков ступени 1, промпт = «выполни Phase 3 шаги 1–8 из SKILL.md»
(backend-only, SQLite вместо PG, Docker — файлы без сборки; cap $8).

- **Результат агента:** `PHASE3-PROBE-DONE 6/6` — все пункты Initialization
  Acceptance Checklist закрыты.
- **Независимая ручная верификация (не со слов агента):**
  - `.venv/bin/python -m pytest -q` → **1 passed** (example-тест health-роута);
  - `.itd/` → **13 файлов** (полный контрактный слой);
  - `scripts/validate_state.py .itd-memory/STATE.json` → **OK**
    (`sessionState=ACTIVE`, `currentStage=SCAFFOLDING`);
  - `git log` → **2 чекпоинт-коммита** (scaffold + .itd), `.itd*` в HEAD;
  - `events.jsonl` создан; `pyproject/Dockerfile/compose/.env.example` на месте.
- Т.е. вся init-фаза Anthropic-порта (ось I карты, §4.4) подтверждена боем:
  запускаемое окружение, проверяемый тест-фреймворк, bootstrap-контракт,
  декомпозиция (10 шагов в IMPLEMENTATION_PLAN), git-чекпоинт.

## Операционные заметки (для будущих прогонов)

- **№2:** headless-запуск из Windows через `wsl.exe bash script.sh` БЕЗ
  login-shell даёт `Not logged in` у claude CLI — креды/env подтягиваются
  только в `bash -lc`. Всегда: `wsl.exe -d <distro> --exec bash -lc '...'`.
- **№3:** проба выполнила bootstrap с «proxy workaround» при pip install
  (сетевая специфика машины) — checklist-пункт «bootstrap from scratch»
  прошёл, но на чистых машинах шаг может требовать индекс-настройку pip.
- Фикстурный вывод сохранён в `tests/fixtures/fixture-01-saas-clinic/output/`
  (артефакт прогона; в git не входит — каталог output в .gitignore фикстур).

## Вердикт

Greenfield-пайплайн **live-подтверждён** на фазах 1–3 (докогенерация с
контент-контрактами + инициализация с fail-closed чеклистом). Непокрытыми
боем остаются Phase 4–5 (пошаговая реализация с Gate 2 и деплой) — их
честная стоимость $10–25/прогон; гонять по сигналу (первый реальный
greenfield-проект), не ради галочки. Оценка greenfield по линейке аудита:
**8 → 9** (структура 10, live-покрытие 3/5 фаз).
