---
project: idea-to-deploy
stage: GPG-004 / юнит политики независимого ревьюера, фаза A
roles: "сессия 2026-08-09 (план согласован) → следующая сессия-реализатор"
---

# HANDOFF — GPG-004: юнит политики ревьюера, фаза A «канал адъюдикации» (в работе)

**Дата:** 2026-08-09 · **Ветка:** `codex/gpg-003-unified-keyless-review` · **HEAD:** `4971a55`, коммитов нет.
Risk `high`, WIP=1.

## 1. From → To

Сессия 2026-08-09 (слайс принят машинно; согласован сжатый план юнита политики
ревьюера, фаза A начата) → следующая сессия/агент, реализующий фазу A.

## 2. Причина передачи

Передача до компакции: план юнита политики зафиксирован, реализация фазы A
не завершена в этой сессии.

## 3. Текущее состояние

- **Слайс bounded-process + возобновляемость: принят машинно, ЗАМОРОЖЕН.**
  Staged tree `1a9eaa240f8bd7d3` (25 файлов) = executedTree зелёной квитанции
  26/26 (`.itd-memory/verification-loop/receipts/b5abe0bcd9dbbb25/GPG-003-machine-4d17d17719048977.json`).
  Мутации 19/19, обе живые ноги host-parity (метрики 1.0), H4 PASS, полный
  `run-all` green. Коммит слайса заблокирован review-гейтом (нет канала
  адъюдикации) — детали в архиве ниже и в `.itd-memory/session_2026-08-09_3.md`.
- **Согласован сжатый план юнита политики независимого ревьюера.** Порядок
  переупорядочен: **фаза A — канал человеческой адъюдикации находок — первой**
  (доказанное требование: обязательный no-bypass ревьюер без канала адъюдикации
  навсегда клинит корректный код). Последующие фазы: класс независимости
  {Claude, Codex} cross-vendor + помеченный same-vendor-different-model фолбэк +
  `HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW`, затем коммит слайса через новый канал.
- **Фаза A в работе:** кодовых правок фазы A в рабочем дереве ещё НЕТ
  (единственное незастейдженное изменение — этот `HANDOFF.md`). Начинать с
  контрактов, не с кода.

## 4. Финальные решения (durable: `.itd/DECISIONS.md`, записи 2026-08-09)

- Review-гейт НЕ обходится (`--no-verify` запрещён); юнит политики строится
  ВПЕРЁД коммита слайса — подтверждено пользователем (вариант 1).
- Канал адъюдикации: машинно записываемое решение человека «находка принята как
  trade-off / false positive» для точного кандидата; сегодня чеканка требует
  checker-вердикт строго `PASSED` (`validate_checker`,
  `skills/_shared/itd_verification_loop.py` ~строка 1260), BLOCKED не
  принимается — это и есть предмет фазы A.
- Слайс не расширять: reviewer-cardinality кейсы, `minimumIndependentReviewers`,
  лестница — scope ЭТОГО юнита (частичный перенос `itd_review_evidence.py` уже
  записан в DECISIONS).
- Все находки шести прогонов маршрута adjudicated/refuted исполнением; новых
  реальных дефектов кода нет.

## 5. Требуемые входы

1. `.itd-memory/session_2026-08-09_3.md` (блокер + решение) и
   `.itd/DECISIONS.md` — все записи 2026-08-09.
2. Механика гейта: `hooks/check-review-before-commit.sh`,
   `skills/review/scripts/itd_review_cache.py`,
   `skills/_shared/itd_verification_loop.py` (`validate_checker`).
3. Кандидатская политика ревьюера (лестница, cardinality) — только как референс:
   `git show refs/itd-backup/gpg004-candidate:<путь>`.
4. План юнита (широкий, до сжатия): `.itd-memory/GPG-004_UNIT_PLAN.md`;
   политика согласована в `session_2026-08-08_8.md`.
5. Архивный пакет слайса — ниже в этом файле.

## 6. Зоны записи и запреты

Можно менять (фаза A): `.itd/SCOPE_LOCK.md` (переписать под юнит),
`.itd/ACCEPTANCE_CONTRACT.json`, `docs/adr/ADR-007-*`,
`skills/_shared/itd_verification_loop.py`,
`skills/review/scripts/itd_review_cache.py`,
`hooks/check-review-before-commit.sh`, `tests/verify_verification_loop.py` и
смежные тесты, CHANGELOG/BACKLOG.

> [!warning] Запреты
> - НЕ трогать staged-индекс слайса: никаких `git add`/`git restore --staged`
>   по 25 staged-путям — staged tree `1a9eaa240f8bd7d3` привязан к квитанции.
> - НЕ push, НЕ PR, НЕ `--no-verify`, НЕ отключать/ослаблять гейты ради прохода.
> - НЕ пересэмплировать ноги бенчмарка; НЕ править архивные evidence/fixtures.
> - НЕ запускать `scripts/sync-to-active.sh`; не поднимать
>   `--max-transport-attempts`, не смягчать `UNAVAILABLE`.
> - Правка любого tracked-файла инвалидирует H4-пин слайса — свежий H4 +
>   чеканка + маршрут при коммите слайса уже заложены в план, но лишних правок
>   staged-файлов избегать.

## 7. Команды проверки

```bash
bash tests/run-all.sh --quick                                  # DONE fails:none
sh skills/_shared/itd_py.sh tests/verify_verification_loop.py   # при правках loop
sh skills/_shared/itd_py.sh tests/verify_free_reviewer_producer.py  # 128 checks PASSED (регрессия слайса)
git write-tree                                                  # должен остаться 1a9eaa240f8bd7d3, пока слайс не коммитится
```

RED-first обязателен: новый тест канала адъюдикации обязан падать на текущем
`validate_checker` до правок.

## 8. Блокеры и риски

> [!warning]
> - Слайс — verified-но-незакоммиченный WIP-долг; живёт только в index +
>   backup-ref `refs/itd-backup/gpg004-candidate` + receipts. Не потерять index.
> - Канал адъюдикации ослабляет «findings=[] или ничего» — проектировать
>   fail-closed: только явное человеческое решение на точный кандидат, никакого
>   авто-даунгрейда BLOCKED→PASSED.
> - 7 отложенных долгов в BACKLOG (раздел GPG-004).
> - Предсуществующий шум validate_state: warnings о рассинхроне `events.jsonl` с
>   GOAL-axis1..3/`PE5-015` — не scope этого юнита.

## 9. Первое действие

> [!todo] Прочитай входы (п.5, минимум session_2026-08-09_3.md + DECISIONS
> 2026-08-09), затем перепиши `.itd/SCOPE_LOCK.md` под юнит политики ревьюера
> (фаза A: канал адъюдикации) и предъяви пользователю план фазы A ДО правок кода.

---

# АРХИВ — пакет слайса bounded-process (2026-08-09, сохранён как вход)

**Ветка:** `codex/gpg-003-unified-keyless-review` · **HEAD:** `4971a55`
**Юнит:** `GPG-004` (`.itd-memory/STATE.json` → `currentUnit`), risk `high`, WIP=1.
**Предыдущий контекст:** `.itd-memory/session_2026-08-08_8.md`, `.itd/DECISIONS.md` (запись 2026-08-08).

## Что сделано в этой сессии

1. **Кандидат сохранён вне ветки** (ничего не потеряно):
   - ref `refs/itd-backup/gpg004-candidate` = commit `a2014e9`, дерево `f480521011126161719fcd472e649f9a34245c23`;
   - патч `scratchpad/full-candidate.patch` (834 827 байт, `git diff --binary HEAD refs/itd-backup/gpg004-candidate`);
   - ledger-копии `scratchpad/cand-memory/{GOAL.json,STATE.json}`.
2. **Рабочее дерево откатано к HEAD** (`git reset --hard HEAD`) — это и есть разрез.
   Восстановлен единственный slice-артефакт: `.itd/GPG-004_A16_TRANSPORT.md` (staged `A`).
3. **Собран slice-продюсер** `skills/_shared/itd_free_reviewer_producer.py` = HEAD + два
   scope-нейтральных блока (см. ниже). Скрипт сборки: `scratchpad/build_slice_producer.py`
   (детерминированный, работает из `prod_head.py` + `prod_cand.py` в том же каталоге).

## КЛЮЧЕВОЕ ОГРАНИЧЕНИЕ, найденное в этой сессии

`tests/verify_independent_review_efficacy.py:320` привязывает подписанные ноги бенчмарка к
`sha256` **файла продюсера**:

- нога HEAD `producerSha256` = `ce2a2544…` = sha HEAD-продюсера;
- нога кандидата = `f935970b…` = sha продюсера кандидата.

Следствие: **любое** изменение байт продюсера обнуляет обе ноги. Ноги кандидата в слайс
перенести НЕЛЬЗЯ — их придётся **перепрогнать живьём на обоих хостах** (WSL + Windows)
против slice-продюсера. Это не меняет состав слайса, но добавляет два живых прогона в приёмку.

## Состав слайса (первый чистый коммит)

Входит:
- продюсер: блок bounded-process (`run_bounded_process`, windows job wrapper, `_close_process_tree`,
  `_windows_*`) + блок возобновляемости (`ROUTE_CHECKPOINT_KIND`, `MAX_ROUTE_CHECKPOINT_AGE`,
  `_route_checkpoint_context`, `_load_route_checkpoint`, `_write_route_checkpoint`,
  параметры/цикл `run_packet_review`, флаг `--unit-checkpoint`, обвязка в `main`: чтение ключа +
  `route_checkpoint_kwargs` + три call-site'а openai/anthropic/copilot);
- `tests/verify_free_reviewer_producer.py` — блок checkpoint-тестов + адаптация моков (ЕЩЁ НЕ СДЕЛАНО);
- матчер: `tests/run-independent-review-efficacy.py` + `tests/verify_independent_review_efficacy.py` (ЕЩЁ НЕ СДЕЛАНО);
- `benchmarks/independent-review-efficacy/cases.json` + СВЕЖИЕ `results/{wsl,windows}.json` (ЕЩЁ НЕ СДЕЛАНО);
- `.itd/GPG-004_A16_TRANSPORT.md` (готов), записи CHANGELOG/BACKLOG (ЕЩЁ НЕ СДЕЛАНО).

Не входит (следующий GPG-юнит, начинается с переписывания `.itd/SCOPE_LOCK.md`):
лестница и всё vendor-neutral (`reviewer_ladder`, `maker_family`, `independence_class`,
`require_independent_reviewer`, `ladder_*`), `itd_risk_tier.py`, `itd_gate_control.py`,
`itd_review_broker.py`, `services/review_broker/server.py`, ADR-007, SCOPE_LOCK,
ACCEPTANCE_CONTRACT, README/README.ru, docs/*, hooks/*, `/cross-review`, все
`tests/fixtures/live-model-evidence/**`, `verify_reviewer_independence_contract.py`,
`verify_gate_inventory.py`, а также 4 scope-независимые находки ревьюера.

Сознательно НЕ взято в слайс (отдельный дефект → отдельный юнит):
- codex error-item fix в `run_codex_review` (A19) — тянет `CODE_MODE_DISABLED_ADVISORY_PREFIX`
  и изменение `codex_command` (reasoning-effort). Взят HEAD-вариант функции + только swap
  `subprocess.run` → `run_bounded_process`. **Риск:** обязательный маршрут перед коммитом может
  снова упереться в «reviewer attempted to use a tool» на свежих сборках Codex; если упрётся —
  это отдельный юнит, а не повод расширять слайс молча.

## Блокер моков — СНЯТ

HEAD-тест подменял `producer.subprocess.run`, а slice-продюсер вызывает `run_bounded_process`,
поэтому мок не перехватывал и запускался реальный бинарь
(`FreeReviewError: OpenAI reviewer failed without proven transport unavailability`).
Исправлено шестью заменами `producer.subprocess.run` → `producer.run_bounded_process`
в `tests/verify_free_reviewer_producer.py`. Результат прогона:

```
{"checks": 109, "liveExternalCalls": 0, "paidApiCalls": 0, "status": "PASSED"}
```

Это регрессия HEAD-тестов против slice-продюсера, НЕ покрытие возобновляемости —
блок checkpoint-тестов (+205) ещё не портирован (см. п.1 порядка работ).

Кандидатские версии файлов доступны так:

```bash
git show refs/itd-backup/gpg004-candidate:tests/verify_free_reviewer_producer.py
```

## Сессия 2026-08-09 (продолжение): шаги 1-2 закрыты

**Шаг 1 — мутации возобновляемости, ЗАКРЫТ.** Харнесс (вне репо, переживает сессию):
`~/.cache/itd-gpg004/mutate_checkpoint.py`, sha256
`c0ad5a99bd3f1ff971ae605c20c7887c4add8dadfe5aec1af59045f2268b9298`. Он снимает по одной
проверке чекпоинта в продюсере, гоняет `tests/verify_free_reviewer_producer.py` и
восстанавливает файл байт-в-байт (проверяется sha).

- Базовый прогон: **19 мутантов, 7 убито, 12 выжило** (envelope-closed, signed-field-set,
  key-id, signature-format, prefix-length, row-exact-keys, foreign-unit, row-report-contract,
  row-provenance, session-reuse, model-change, binding-validity).
- В `tests/verify_free_reviewer_producer.py` добавлен блок из 12 проверок: каждый аномальный
  чекпоинт пересобирается и **переподписывается** валидным ключом, поэтому проверяется именно
  целевой guard, а не подпись. Ожидание — полный рестарт (`unit_count + 1` вызовов).
- Итог: **19/19 killed, survivors: []**, продюсер восстановлен
  (`sha256 0e982dc08cc3ad5aacaa07857ea16244cc5899b4f78ddbe4ca306d18784afaf5`).
- Оракул продюсера: **116 → 128 checks, `status: PASSED`, liveExternalCalls 0, paidApiCalls 0**.

**Шаг 2 — матчер, ПЕРЕНЕСЁН (с одним осознанным вычетом).**
`git checkout refs/itd-backup/gpg004-candidate --` для
`tests/run-independent-review-efficacy.py`, `tests/verify_independent_review_efficacy.py`,
`benchmarks/independent-review-efficacy/cases.json`.

- Совместимость со slice-продюсером проверена: `required_isolation()` совпадает с
  `EXPECTED_ISOLATION`, `select_openai_reviewer_model` на месте, host-pin
  `.itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256` существует.
- **Вычтен блок reviewer-cardinality** в `structural_metrics` (кейсы `low-reviewer` /
  `high-quorum`): он падает с `AssertionError: low-reviewer reviewer cardinality was accepted`,
  потому что опирается на изменения `skills/_shared/itd_review_evidence.py` из юнита политики
  ревьюера. Вернуть эти кейсы — задача ТОГО юнита; на месте вычета оставлен комментарий.
- Текущее состояние верификатора (RED, ожидаемо):
  `AssertionError: wsl semantic result binding is foreign` — ноги привязаны к старым sha
  продюсера/раннера/манифеста. Это исполненное подтверждение, что **обе ноги обязаны быть
  перепрогнаны живьём**; запуск: `--expected-keyring-sha256-file .itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256`.
- Раннер кандидата теперь требует `--maker-model` (проверяет, что ревьюер — точно
  противоположная модель) и сам аттестует транспорт до version-probe.

**Шаг 3 — обе живые ноги ЗАКРЫТЫ, верификатор ЗЕЛЁНЫЙ.**

Версии транспорта выровнены по решению пользователя: WSL codex обновлён 0.144.3 → **0.146.0**
(активный бинарь — вложенный `…/@openai/codex/node_modules/@openai/codex-linux-x64/…/bin/codex`,
sha `2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04`; старый 0.144.3 остался
leftover'ом в `…/@openai/codex-linux-x64/…`, поэтому путь передавать ЯВНО, не через PATH).
Windows: `codex.exe` 0.146.0, sha `bc343ba420dc2e2e9f59e6fc5e5bf0aae1cd8c771fc319665241fc9c0271fddb`.

- **WSL-нога:** `{"host": "wsl", "status": "PASSED"}`, 9 кейсов, 9 попыток, `paidApiCalls: 0`.
  Два обрыва транспорта (`Reconnecting... 2/5 (request timed out)`, exit 3 = `UNAVAILABLE`),
  оба возобновлены с чекпоинта — по A21 это единственный разрешённый ретрай. Каждый обрыв
  стоил один вызов вместо девяти: возобновляемость окупилась вживую.
- **Windows-нога:** `{"host": "windows", "status": "PASSED"}`, 9 кейсов, без обрывов;
  чекпоинт в `C:\Windows\Temp`, в репо не пишется.
- **Верификатор:** `{"status": "PASSED", "hostParityVerified": true, "closedEvidenceDetection": 1.0,
  "missingEvidenceDetection": 1.0, "unitFindingRetention": 1.0}`, семантика на обоих хостах
  `criticalHighDetection 1.0 / mediumDetection 1.0 / cleanFalseBlockRate 0.0`.

**Три дефекта, найденные приёмкой (все закрыты исполнением):**

1. `structural/high-duplicate-criterion` не детектился → `closedEvidenceDetection` 0.923 < 1.0.
   Причина: перенесённый корпус требует guard, которого в слайсе не было. Диф кандидата к
   `skills/_shared/itd_review_evidence.py` — 8 строк из ДВУХ независимых частей; взята только
   вторая (отказ на дубликат `criterion ID` в `coverage_matrix`, 4 строки, гигиена
   acceptance-контракта). Первая часть (кардинальность `minimumIndependentReviewers`) осталась
   юниту политики. Пороги и `cases.json` НЕ трогались.
2. `verify_copilot_reviewer` падал `GitHub Copilot reviewer failed before a classified outcome`.
   Бисект исполнением: на HEAD-продюсере `rc=0, 49 checks, PASSED`, на slice-продюсере FAIL →
   регрессия слайса. Причина того же класса, что вчера: тест подменял `producer.subprocess.run`,
   а copilot-путь слайса вызывает `run_bounded_process`, поэтому запускался реальный бинарь.
   Исправлено подменой `producer.run_bounded_process` (2 места).
3. `tests/run-all.sh` не передавал обязательный `--expected-keyring-sha256-file` новому
   верификатору → `rc=2`. Добавлена ветка ТОЛЬКО для `verify_independent_review_efficacy`
   (вариант кандидата включал ещё `verify_reviewer_provider_freshness`, у которого в слайсе
   такого аргумента нет — его добавление сломало бы этот тест).

Состояние проверок: `verify_free_reviewer_producer` 128 checks PASSED,
`verify_copilot_reviewer` 49 checks PASSED, `run-all.sh --quick` → `DONE fails:none`.

**Шаги 4-6 (CHANGELOG/BACKLOG, стейдж, H4, machine receipt) — ЗАКРЫТЫ.**

- CHANGELOG (Unreleased): bounded-process, возобновляемый маршрут, guard дубликата
  criterion ID. BACKLOG: раздел P0 GPG-004 — 5 долгов (юнит политики, кейсы
  кардинальности, A19, необъяснённый UNVERIFIED, фильтрация харнесс-мусора в пине
  дерева). DECISIONS: +2 записи (частичный перенос itd_review_evidence, F-06).
- Полный `run-all` был красным ЕЩЁ НА HEAD (`verify_feature_ledger_fallbacks`,
  ячейка F-06 сломана коммитом `7fcfc0f`) — восстановлена, теперь `DONE fails:none`.
- H4 гонялся ТРИ раза: №1 сгорел из-за постороннего trace-файла
  `skills/_shared/.claude/traces/…` (git-ignored, но входит в METHODOLOGY_TREE_ROOTS —
  вынесен в scratchpad/evicted), №2 сгорел из-за правки BACKLOG во время прогона
  (dirty-state digest), №3 PASS: `20260809T080256Z-d100f5a2` (застейджен; superseded
  архивы №1-2 выведены из кандидата и лежат в scratchpad/evicted).
- **Machine receipt ЗЕЛЁНЫЙ: 25/25, exit 0** —
  `.itd-memory/verification-loop/receipts/a8f732cd33b087e5/GPG-003-machine-46c2668035639ba1.json`,
  executedTree `9b45e51aa97fdb9b…`. Состав = прошлая квитанция минус два
  candidate-scope entry: `controlled-project-inventory-regression`
  (tests/verify_gate_inventory.py существует только в кандидате) и флаг
  `--expected-keyring-sha256-file` у `reviewer-provider-freshness` (то же). Оба —
  долг юнита политики (BACKLOG). Host-pin keyring передан как `--input`
  (declaredInputs), как в прошлой зелёной квитанции.
- Урок порядка: H4 и квитанция требуют НЕПОДВИЖНОГО дерева — никаких правок
  файлов между стейджем, H4 и квитанцией; dirty-state digest ловит одну строку.

**ФИНАЛЬНОЕ СОСТОЯНИЕ 2026-08-09 (session_2026-08-09_3.md): слайс принят машинно,
заблокирован на commit review-гейте — это принципиальный вывод, не транспорт.**

Всё зелёное: мутации 19/19, обе живые ноги host-parity (метрики 1.0), receipt 26/26
zero-bad (`b5abe0bcd9dbbb25/GPG-003-machine-4d17d17719048977.json`, executedTree =
staged `1a9eaa240f8bd7d3`), H4 PASS, полный `run-all` green. Независимый маршрут
(`gpt-5.6-sol` → `gpt-5.6-terra`) прогнан ~6 раз; все находки adjudicated или refuted
исполнением, НОВЫХ реальных дефектов нет.

**Но коммит невозможен через гейт:** `check-review-before-commit.sh` требует записанный
PASSED adjudication-receipt; чеканка требует checker-вердикт = только PASSED
(`validate_checker`); BLOCKED-с-adjudicated-находками не принимается, а канала
человеческой адъюдикации в машинерии НЕТ. Блокирующие находки (gzip false-positive,
checkpoint-freshness accept-by-design, host-pin, fixture) чистыми не станут никогда.

**Решение пользователя (вариант 1):** НЕ обходить гейт. Юнит политики независимого
ревьюера строится ПЕРВЫМ и обязан добавить **канал человеческой адъюдикации находок**
(это новое доказанное требование), после чего слайс коммитится через него без обхода.

**Слайс сохранён целиком:** staged tree `1a9eaa240f8bd7d3` (25 файлов), backup-ref,
все receipts, снапшот продюсера `~/.cache/itd-gpg004-producer/a4/`. Пуш и PR не трогать.

**Следующий шаг — НЕ коммит слайса, а старт юнита политики ревьюера** (см.
session_2026-08-09_3.md → «Следующие шаги»).

## Порядок работ дальше

1. ✅ СДЕЛАНО. Mock-адаптации + блок checkpoint-тестов (+205 строк, одна чистая вставка после
   строки 536) портированы в `tests/verify_free_reviewer_producer.py`. RED-first проведён
   исполнением:
   - RED на HEAD-продюсере: `TypeError: run_packet_review() got an unexpected keyword argument
     'checkpoint_path'` (`tests/verify_free_reviewer_producer.py:581`);
   - GREEN на slice-продюсере: `{"checks": 116, "liveExternalCalls": 0, "paidApiCalls": 0,
     "status": "PASSED"}` (было 109 без блока).
2. ✅ СДЕЛАНО. Мутации возобновляемости в обе стороны — 19/19 killed (см. раздел выше).
3. ✅ СДЕЛАНО. Матчер перенесён из кандидата минус блок reviewer-cardinality (см. раздел выше).
4. Живьём: WSL-нога, затем Windows-нога (из WSL через
   `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`, пути через `$env:LOCALAPPDATA`,
   чекпоинт в `C:\Windows\Temp`, НЕ в репо).
5. Финальный стейдж ВСЕГО содержимого (`.itd-memory/STATE.json` — только `git add -f`), потом
   H4 живой прогон (продюсер лежит под `skills/` → входит в content-pin `METHODOLOGY_TREE_ROOTS`),
   потом machine receipt (26 оракулов, внутрь `.itd-memory/verification-loop`).
6. `run-all --quick && run-all` → независимый маршрут (старый scope: openai Sol/Terra, теперь
   возобновляемый через `--unit-checkpoint`) → коммит. **Пуш и PR — только по явной команде.**

## Запреты (действуют)

- Не поднимать `--max-transport-attempts`, не добавлять ретраи в обязательный маршрут,
  не смягчать `UNAVAILABLE`.
- Не пересэмпливать ноги ради удобного исхода.
- Не переписывать `.itd/SCOPE_LOCK.md` в рамках ЭТОГО слайса — это следующий юнит.
- Не запускать `scripts/sync-to-active.sh`.
