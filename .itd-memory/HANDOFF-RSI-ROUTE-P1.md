# HANDOFF — RSI-ROUTE-P1 (medium)

Сессия 2026-09-08 (после закрытия RSI-DEBT-1). База: `main` = `cc425b1`.

## 1. Что за юнит

`_transparent_review_representation` в `skills/_shared/itd_free_reviewer_producer.py`
возвращал **скраббленный** `diff_text`, а по-файловые `chunks` брал из
**до-скрабленных** канонических байт (`review_broker._canonical_diff`). При любой
редактируемой строке `"".join(chunks) != diff_text`, и `_review_units` в брокере
отказывал: **`hierarchical review unit coverage is invalid`** — до вызова модели.
Обычная ветка этой болезни не имеет: она режет чанки из `_safe_review_text` output.

DoD — поле `criterion` юнита `RSI-ROUTE-P1` в `.itd-memory/GOAL.json` (дословно,
не пересказывать). Скоуп — `.itd/SCOPE_LOCK.md`, контракт —
`.itd-memory/contracts/RSI-ROUTE-P1.md`.

## 2. Сделано (наблюдено живьём, не заявлено)

**RED-first на до-фиксовых байтах.** Проба
`scratchpad/red_probe.py` (temp-репо: `git_fixture` + `review.jsonl.gz` 5000 строк,
в строке 1234 — редактируемый e-mail `ops.person@example.com`):

```
REFUSED:  | hierarchical review unit coverage is invalid
```

После фикса та же проба: `ACCEPTED mode= hierarchical units= 5`.

**Правка** (`skills/_shared/itd_free_reviewer_producer.py`, сразу после
`logical_text = _safe_review_text(...)`): чанки перерезаются из `logical_text`
существующим билдером `_raw_review_file_chunks` — новых мест не заведено.

**Тест** (`tests/verify_free_reviewer_producer.py`, блок `redacted-transparent`
после `validate_review_prompt_artifact(large_packet, ...)`): запечатанная
фикстура + четыре проверки —
1) в скраббленном тексте нет исходного e-mail, есть `[REDACTED-EMAIL]`,
   `transparentFileCount == 1`;
2) `"".join(chunks) == diff_text` и порядок путей
   `["branch.py", "review.jsonl.gz", "service.py"]`;
3) **мутант** = чанки с восстановленным e-mail; его sha256 равен
   `reviewRepresentation["reviewDiffSha256"]` (= хеш ДО-скрабленных байт), то есть
   мутант машинно доказан как точный до-фиксовый источник чанков;
4) `_review_units(diff_text, mutant_chunks, policy)` падает ровно с
   `hierarchical review unit coverage is invalid`; `freeze_packet` на кандидате
   принимает и даёт `hierarchical`, unitCount 1<n<=16, без утечки e-mail.

**Оракулы.**
- `tests/verify_free_reviewer_producer.py` → `{"checks": 307, ... "PASSED"}` (было 302).
- `tests/verify_scrubber_precision.py` → `{"checks": 97, "status": "PASSED"}` (без правок).
- Мутация «чанки из сырых байтов» (снятие патча) → оракул красный:
  `AssertionError: transparent review units are not cut from the reviewed text`. Летальна.

## 3. Открытое: efficacy-ноги надо перечеканить

`bash tests/run-all.sh --quick` → `DONE fails: verify_reviewer_provider_freshness
verify_independent_review_efficacy`.

Контракт разрешает красным ТОЛЬКО `verify_reviewer_provider_freshness`.
Второй красный — **следствие правки продюсера**, а не дефект кандидата:

```
current semantic efficacy result is archived only as a historical or
foreign-producer observation, not a current-producer diagnostic: wsl.json
```

Проверено: на до-фиксовых байтах (`git stash` двух файлов)
`verify_independent_review_efficacy` **PASSED** — значит это ровно известный класс
«правка продюсера обесценивает efficacy-квитанции», не регрессия.

Рецепт перечеканки (HANDOFF-S10-LEDGER §18, HANDOFF-R1 §3):
рекордер `tests/run-independent-review-efficacy.py` (ВНИМАНИЕ: флаг
`--max-transport-attempts` из старых handoff'ов в текущем рекордере УДАЛЁН — см.
комментарий на `tests/run-independent-review-efficacy.py:270`; повторы транспорта
ограничены константой `TRANSPORT_ATTEMPT_BOUND`), ключи
`.itd-memory/verification-loop/keys/gpg003-local-producer-20260803{,.windows}.key`,
ноги `benchmarks/independent-review-efficacy/results/{wsl,windows,u12-cross-vendor-wsl}.json`.
Windows-нога — через `powershell.exe` по UNC, пути в §18 того же handoff.
Старый чекпоинт после смены продюсера невалиден (`checkpoint binding is stale or
foreign`) — прогон полный.

## 4. Остаток маршрута

1. Перечеканить три efficacy-ноги → `verify_independent_review_efficacy` зелёный.
2. Полный `bash tests/run-all.sh` → единственный допустимый красный
   `verify_reviewer_provider_freshness`.
3. `/review`-субагент — **сделано**: r2 (sonnet, свежая сессия) `Verdict: PASSED`,
   две minor-заметки без правок кода (хрупкость фикстуры мутанта при гипотетическом
   втором редактируемом токене; renamed-ветка недостижима из-за `--no-renames`).
   r1 упёрся в лимит ходов без отчёта и не засчитан.
4. Машинная квитанция (`itd_verification_loop.py machine`, unit `RSI-ROUTE-P1`,
   medium, oracle = `verificationCommand` юнита) → чекер → adjudicate → кэш.
5. Коммит кода.
6. **Отдельным вторым коммитом** — live re-pin
   (`tests/run-live-model-benchmark.py --fixture fixture-03-cli-tool --provider openai`)
   на ЧИСТОМ дереве.
7. Публикация: committed-head claim → register-profile → `itd pr create` → CI →
   merge ПО КОМАНДЕ → `itd_unit_log.py verified RSI-ROUTE-P1`.

## 5. Ловушка маршрута, известная заранее

Продюсер, который ревьюит этот кандидат, — **установленный 1.103.1 с тем самым
дефектом**. Поэтому в staged-дифф НЕЛЬЗЯ класть `.jsonl.gz` вместе с редактируемой
строкой: re-pin ложится отдельным коммитом после кода, а committed-head claim при
необходимости закрывается staged-квитанцией на том же дереве (прецедент PR #272).

Следующий юнит — `REL-1.104.0` (релиз с раскаткой и перепином review-authority);
внутри RSI-ROUTE-P1 релиз запрещён.

## 6. Точные входы перечеканки (собраны в этой сессии, проверены)

- WSL codex (пин `2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04`):
  `~/.npm-global/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex`
  — ВЛОЖЕННЫЙ путь. Верхнеуровневый `@openai/codex-linux-x64/...` — другой бинарь
  (`37e6f595…`, 0.144.3), НЕ тот пин.
- `--proxy-sha256 01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`
  = `sha256(b"\n")` = «прямой транспорт без прокси» (`trusted_proxy_environment`,
  itd_free_reviewer_producer.py:3783).
- Ноги и их параметры (из предыдущих подписанных результатов):
  - `wsl.json`: maker `gpt-5.6-terra` / `openai-subscription`, requested `gpt-5.6-sol`, runtime 0.146.0.
  - `u12-cross-vendor-wsl.json`: maker `claude-opus-5` / `anthropic-subscription`, requested `gpt-5.6-sol`.
  - `windows.json`: maker `gpt-5.6-terra` / `openai-subscription`, runtime 0.153.4,
    транспорт `e5aa76d19c7c…` (codex.exe), ключ `…20260803.windows.key`.
- Ключи: `.itd-memory/verification-loop/keys/gpg003-local-producer-20260803{,.windows}.key`,
  `--key-id gpg003-local-producer-20260803`.
- `--checkpoint` и `--output` обязаны различаться. Флага `--max-transport-attempts` больше нет.

**Порядок обязателен:** сначала закрыть все правки кода (ревью-находки), и только
потом чеканить ноги — правка продюсера обесценивает уже отчеканенные квитанции.

## 7. Находка маршрута: Windows-транспорт из прошлой ноги отсутствует

`windows.json` от 2026-09-06 записана транспортом
`e5aa76d19c7c94e2e9ef9b707d590206a73ac0e97c8ddc8382181242494bef75`, runtime 0.153.4.
На машине сейчас существует РОВНО ОДИН `codex.exe`:
`%APPDATA%\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe`,
sha `bc343ba420dc2e2e9f59e6fc5e5bf0aae1cd8c771fc319665241fc9c0271fddb`, дата 2026-07-31.
Именно `bc343ba4…` пинован в `.itd/PROVIDER_LIVE_WINDOWS.json` (наблюдение
2026-09-04, runtime 0.146.0). Бинарь `e5aa76d1…` не найден ни в `%APPDATA%\npm`,
ни в `Program Files\nodejs`, ни в `.local\bin`, ни в `scoop`.

Решение этой сессии: Windows-нога чеканится доказуемым `bc343ba4…` (тем же, что в
живом провайдер-пине), а не отсутствующим на диске sha. Расхождение записано как
факт маршрута; если верификатор потребует конкретный старый sha — это отдельная
находка, а не подгонка.

## 8. Efficacy-ноги перечеканены (2026-09-08, эта сессия)

Продюсер после фикса: `68b25d0863ee5f2f92874b86032cc927b87d3ee30d76b890978bccd4e2a64f81`.
Три ноги записаны живьём, все `status: PASSED`:

- `wsl.json` — maker `gpt-5.6-terra`, ревьюер `gpt-5.6-sol`, 2026-09-08T19:54:03Z.
- `u12-cross-vendor-wsl.json` — maker `claude-opus-5`/anthropic-subscription,
  2026-09-08T19:58:14Z.
- `windows.json` — транспорт `bc343ba4…`, 2026-09-08T20:02:04Z (см. §7).

Первый заход WSL-ноги упал на кейсе 2 с `OpenAI reviewer event stream transport is
unavailable` — транзиент; рекордер возобновляется с чекпоинта, второй заход прошёл
все 9 кейсов.

Архивирование (append-only, README истории): снимок
`history/route-debts/diagnostic-68b25d08/` + три записи в `manifest.json` + обновление
видов в `results/`. Две вещи, которых требует сам верификатор и о которых README молчит:

1. У записи `classification: "diagnostic"` поле `sourceGitBlobSha1` обязано быть `null`
   (`tests/verify_independent_review_efficacy.py:434`) — иначе
   «diagnostic archive provenance is invalid».
2. Каждый снимок обязан быть пинован в `HISTORY_PINNED_SNAPSHOTS` ВНУТРИ верификатора
   (`tests/verify_independent_review_efficacy.py:45`), иначе «immutable history manifest
   inventory differs from frozen pins». Пины намеренно живут в коде, а не в мутабельном
   манифесте.

Итог верификатора: `hostParityVerified: true`, обе ноги `cleanFalseBlockRate 0.0`,
`criticalHighDetection 1.0`, `mediumDetection 1.0`; ladder cross-vendor и same-vendor 1.0.

ВНИМАНИЕ: правка `tests/verify_independent_review_efficacy.py` расширила кандидата уже
ПОСЛЕ ревью r2 — нужен новый раунд ревью по полному кандидату.

## 9. Статус на момент перезапуска сессии (2026-09-08, ~20:10 UTC)

Сессия перезапустилась; три фоновые задачи (полный `run-all` и монитор его
финальной строки) убиты БЕЗ записи о завершении. Результата полного прогона нет —
он перезапущен, лог пишется в
`scratchpad/run-all-full.log` (durable, переживает перезапуск чата).

Состояние рабочего дерева на этот момент (не закоммичено, база `main` = `cc425b1`):
`skills/_shared/itd_free_reviewer_producer.py`, `tests/verify_free_reviewer_producer.py`,
`tests/verify_independent_review_efficacy.py`,
`benchmarks/independent-review-efficacy/{results/*.json,history/route-debts/manifest.json,
history/route-debts/diagnostic-68b25d08/*}` (снимок зарегистрирован `git add -N`),
плюс артефакты старта юнита (GOAL/STATE/events, SCOPE_LOCK, ACCEPTANCE_CONTRACT,
DECISIONS, BACKLOG).

Не сделано: полный `run-all`, раунд ревью по РАСШИРЕННОМУ кандидату, машинная
квитанция, чекер, адъюдикация, коммит, live re-pin, публикация.

## 10. Полный run-all: DONE, два ЛИШНИХ красных — не наши (2026-09-09)

```
DONE fails: verify_reviewer_provider_freshness verify_ledger_reconciliation verify_mandatory_keyless_review
MIRROR-COVERAGE: 142 of 153 tests/verify_*.py run here (full mirror)
```

Решающая улика — **чистый detached worktree на `cc425b1`** (`git worktree add --detach`,
ни одного нашего файла, без артефактов активации юнита): оба сьюта падают там ТАК ЖЕ.

- `verify_mandatory_keyless_review` -> `FileNotFoundError: /tmp/keyless-diagnostic-<rand>/prompt.md`
  (`tests/verify_mandatory_keyless_review.py:213`).
- `verify_ledger_reconciliation` -> `80 passed, 3 failed`: дважды
  `the event is appended before STATE is persisted (append_event@-1 save_state@-1)`
  и `repo: blocked lifecycles ... vcr=1.0 blocked=0 verified=10 total=11`.

Оба живут ТОЛЬКО в полном зеркале (142/153), в `--quick` их нет — поэтому серия
RSI-DEBT-1 их не видела, и контракт этого юнита назвал допустимым только
`verify_reviewer_provider_freshness`.

**Решение владельца 2026-09-09: вести юнит дальше, красные — в BACKLOG** (P1
«main is red on two full-mirror suites»), в `.itd/DECISIONS.md` 2026-09-09.
Коммит доставки понесёт явный `COMPLETION_BYPASS` с этими двумя именами.

Кандидат при этом цел и зелёный после операций со stash: продюсер
`sha256 68b25d0863ee5f2f92874b86032cc927b87d3ee30d76b890978bccd4e2a64f81`
(тот же, к которому привязаны efficacy-ноги), `verify_free_reviewer_producer` 307 PASSED,
`verify_independent_review_efficacy` PASSED с `hostParityVerified: true`.

**Ловушка, пойманная здесь:** `git stash push` по путям, часть которых зарегистрирована
через `git add -N`, при `pop` даёт `not uptodate. Cannot merge` и оставляет stash-запись.
Для baseline-замеров используй `git worktree add --detach <sha>`, а не stash.

## 11. Маршрут доставки: где стоим (2026-09-09)

Ветка `fix/rsi-route-p1-transparent-chunks` от `cc425b1`. Застейджено 19 путей:
код + два теста + три ноги + снимок `diagnostic-68b25d08` + манифест + контракты +
леджер + BACKLOG + DECISIONS + этот HANDOFF. Рабочее дерево без неотслеженных правок.

- `/review` r3 (свежая сессия, расширенный кандидат вместе с бухгалтерией улик):
  **PASSED, findings: none**. Проверил и append-only историю: в `git diff` по `history/`
  только `new file`, ни одной правки существующих снимков.
- Машинная квитанция: `.itd-memory/verification-loop/receipts/RSI-ROUTE-P1-machine-r1.json`,
  **PASSED**, unit `RSI-ROUTE-P1`, risk `medium`, база `cc425b1a1e7c8b21187e0ebc9c6cd11cd2f00d1a`,
  дерево `cfa3b6d22c181ae298ba160372d56107f90c0591`, оба оракула внутри изолированного прогона.
- Чекер: промпты `.itd-memory/verification-loop/prompts/RSI-ROUTE-P1-checker-a{1,2}.md`.

### Две новые ловушки маршрута

1. `itd_verification_loop.py machine --input .itd-memory/events.jsonl` теперь ОТВЕРГАЕТСЯ:
   `declared input is already tracked in the staged tree` -> `Remove redundant --input;
   tracked files are materialized automatically`. Рецепт из HANDOFF-S10 §18 устарел.
2. Субагент-чекер с открытой формулировкой упирается в лимит ходов и возвращает частичный
   вывод БЕЗ вердикта (attempt a1). Частичный вывод не улика. Формулируй чекеру жёсткий
   бюджет ходов и явный порядок шагов, где прогон `verificationCommand` идёт ПЕРВЫМ.

### 11.1 Чекер и третья ловушка

Чекер attempt a2 (свежая сессия, sonnet, targeted) на дереве `cfa3b6d2`:
**PASSED, findings [], unverified []**. Он ПРОГНАЛ verificationCommand дословно и привёл
реальный вывод: `{"checks": 307, ..., "status": "PASSED"}` и `{"checks": 97, "status": "PASSED"}`.
Промпт — `prompts/RSI-ROUTE-P1-checker-a2.md`, отчёт — `receipts/RSI-ROUTE-P1-checker-a2-report.json`.

**Ловушка 3.** `itd_verification_loop.py checker` (и `machine`) отказывают с
`working tree differs from the staged candidate`, если хоть один отслеживаемый файл правлен
после `git add`. Практическое следствие: **сначала закрой ВСЁ содержимое кандидата, включая
docs и этот HANDOFF, и только потом чекань квитанции**. Любая последующая правка отслеживаемого
файла обесценивает и машинную квитанцию, и вердикт чекера — они привязаны к дереву.
Квитанции и промпты в `.itd-memory/verification-loop/` git-ignored и дерево не пачкают.

## 12. Раунд r4: одна реальная находка, одна опровергнутая (2026-09-09)

Гейт `check-review-before-commit` заблокировал коммит: кэш требует `/review`-вердикт,
привязанный к ТОЧНОМУ текущему staged-контексту, а r3 проходил на предыдущем дереве
(правки пакета передачи его сдвинули). Свежий раунд r4 на дереве `a4945102` -> **BLOCKED**,
две находки Important.

**r4-1 ПРИНЯТА и оказалась шире.** Юниты `RSI-ROUTE-P1` (in_progress) и `REL-1.104.0`
(pending) несли `evidence`/`verifiedAt` от постороннего rollout-юнита ROUTE-DEBTS, датированные
`2026-09-05` - за три дня до собственного создания. Ревьюер нашёл один, замер показал два.
Очищено до канонической пустой формы; `verify_goal_tools` -> `62 passed, 0 failed`, повторный
скан не находит ни одного не-verified юнита с уликой.

**r4-2 ОПРОВЕРГНУТА замером.** Пункт SCOPE_LOCK про «own follow-on commit» относится к
`tests/fixtures/live-model-evidence/**` (пин CI Gate 1 по `fixture-03-cli-tool`, привязан к
дереву `skills/`+`hooks/`+`agents/`), а не к efficacy-ногам.
`git diff --cached --name-only | grep -c live-model-evidence` -> `0`: этого пути в кандидате
нет. Ноги `benchmarks/independent-review-efficacy/` привязаны к `producerSha256` и обязаны
ехать ВМЕСТЕ с правкой продюсера - отдели их, и `verify_independent_review_efficacy` падает
fail-closed. Диспозиции обеих находок записаны в `.itd/DECISIONS.md` 2026-09-09.

### Ловушки 4 и 5

4. Гейт коммита требует запись в кэше `/review` для ТЕКУЩЕГО контекста. Любая правка дерева
   после раунда ревью обесценивает его: раунд надо гонять на финальном дереве, последним.
5. Отчёт чекера обязан лежать в `.itd-memory/verification-loop/reports/` (НЕ в `receipts/`)
   и быть ИСХОДНЫМ текстом отчёта с каноническим блоком вердикта - собранный вручную JSON
   отвергается: `checker report has no valid verdict/findings/unverified JSON block`.
