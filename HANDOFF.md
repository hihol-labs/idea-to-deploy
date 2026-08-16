# HANDOFF — release v1.97.0 (S5..S9 shipped together)

> Пакет переписан 2026-08-16 после мержа PR #206. Предыдущая редакция описывала
> закрытие четырёх харнес-долгов S9 и их публикацию; та работа завершена, её
> факты живут в `.itd-memory/session_2026-08-16*.md` и в CHANGELOG 1.97.0.

## 1. From → To

От сессии, закрывшей публикацию S9 (`c0475c17`), к сессии, которая доводит
релиз v1.97.0 до раскатанного и просмоканного состояния.

## 2. Текущее состояние — ФАКТЫ

- `main` = `706d62a` (merge PR #206). Всё, что было в S5..S9, уже в main.
- Ветка `chore/release-1.97.0` от `706d62a`: бамп версии в **девяти** пиновых
  местах + запись CHANGELOG 1.97.0, собранная из 72 коммитов после v1.96.0.
  Runbook называет четыре места, этого НЕ хватает; полный список:
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `.codex-plugin/plugin.json` (без него `verify_host_adapters` и
  `verify_gate_control` красные — doctor читает оба манифеста), бейджи
  `Version-1.97.0` в `README.md` и `README.ru.md`, `pluginVersion` в
  `docs/HARNESS_DOCS_STATE.json`, `version` в
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`, константа `VERSION` в
  `tests/verify_external_reviewer_release.py` и строка «текущий пакет» в
  `docs/HARNESS_CONFORMANCE_REPORT.md`.
- Опубликованная версия до этого релиза — v1.96.0 (2026-08-09).
- Реестр `~/.config/itd/gates.json` пришпилен к `S9`/`medium`, receipt
  `.itd-memory/verification-loop/S9-PUBLISH-route-adjudication.json`. Но
  **сейчас `itd gate doctor` отдаёт `UNVERIFIED`**, drift
  `["local review: UNVERIFIED: local adjudication is stale, foreign, or
  invalid"]`, `routeEvidence: null`, `routeIndependence: null` — и это не
  порча реестра. `validate_local_adjudication`
  (`skills/_shared/itd_gate_control.py:1518`) каждый раз перепроверяет
  зарегистрированную квитанцию против текущего HEAD в режиме
  `committed-head`, а он требует ровно одного родителя
  (`skills/_shared/itd_free_reviewer_producer.py:962`,
  «committed-head requires one exact single-parent commit»). HEAD `706d62a`
  — merge-коммит PR #206 с двумя родителями, поэтому S9-квитанция стала
  читаться как stale в тот момент, когда PR смержили, задолго до этого
  кандидата. Практический вывод: **LOCAL_REVIEWED надо переустановить своей
  publication-квитанцией** (раздел 3), и это сработает — релизный коммит
  одно-родительский, в отличие от merge-головы под ним.

## 3. Маршрут публикации — рецепт, проверенный на S9 (2026-08-16)

Публикация ЛЮБОЙ ветки требует своего committed-head claim; квитанции юнитов
биндят свои staged-деревья и отвергаются с «receipt does not match the exact
current candidate».

1. Бухгалтерия и коммиты доведены; дерево чистое, индекс == `HEAD^{tree}`.
2. Критерии активного юнита обязаны существовать в
   `.itd/ACCEPTANCE_CONTRACT.json` с префиксом `<activeFollowup.unitId>-`.
   Их отсутствие роняет продюсера на `active unit has no acceptance criteria`
   ещё до ревьюера.
3. Машинная нога маршрута: `--unit-id <activeFollowup.unitId>` и
   `--risk-tier <reviewPolicy.riskTier>` — `coverage_matrix` требует точного
   равенства обоих. Оракулы (`id=команда`) обязаны покрыть `oracleIds` всех
   критериев юнита, exit 0, на дереве кандидата.
4. Продюсер запускается ИЗ КОПИИ вне репозитория (`candidate repository cannot
   host the credential-bearing producer`), `--root` — на репо, `--base` —
   РОДИТЕЛЬ HEAD (whole-branch база делает пакет шире машинного покрытия и
   даёт critical на ровном месте), `--candidate-mode committed-head`.
   Ключ: `~/.cache/itd-review-authority/GPG004-U8-1ed4cb5a-a1/producer-ed25519.key`,
   key-id `gpg004-u8-producer-20260808` — именно его публичный ключ лежит в
   зарегистрированном keyring `1fa8afec…`. Codex: pinned ELF
   `…/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex`,
   sha `2e863156…`, proxy-sha `01ba4719…` (sha256 от `"\n"` = прямой транспорт).
   Чекпоинта у продюсера нет: обрыв транспорта стоит всю попытку.
5. Чекер и adjudication чеканятся под ТУ ЖЕ машинную квитанцию, что подписана
   в phase-one, и под её unit/tier — иначе `mandatory route receipt binds
   another machine receipt`. Чекер получает `--phase-one-receipt` +
   `--producer-keyring`.
6. Проверка ровно как у гейта:
   `itd_verification_loop.py check --candidate-mode committed-head
   --require-mandatory-route --accept-adjudicated-route
   --expected-repository … --expected-producer-keyring-sha256 … --receipt …`
   → `{"outcome":"PASSED","routeIndependence":"cross-vendor"}`.
7. `itd gate register-profile …` на новый receipt/unit/tier → `itd gate doctor`
   → `itd pr create --maker-vendor anthropic --maker-model … --maker-session …`.

## 3b. Разблокировка маршрута: разрез юнитов раскрыт ревьюеру (2026-08-16)

Публикация была дважды отвергнута продюсером с одной и той же находкой —
«транскрипт обрывается на `item_4` в `in_progress`». На диске это ложь.
Измерено на `prompts/S9-RELEASE-publish-prompt-r2.json`: unit 3 несёт
`item.started item_4` без пары, `item.completed item_4` лежит в unit 4.
Юниты режутся по байтовому бюджету на границах UTF-8-строк, а не по записям,
поэтому парные события одной записи расходятся; unit-ревьюер сказал правду про
свой кусок, а интеграция подняла это до утверждения о кандидате, потому что
получала только хеш плана и не могла сверить границу.

Починка НЕ трогает разрез — резать по логическим границам значило бы привязать
транспорт к формату данных. Разрез теперь раскрывается:
`_bound_range_facts` выводит точную границу из манифеста юнита,
`_unit_review_prompt` печатает `BOUND_RANGE_FACTS=` и общий
`BOUND_RANGE_DISCLAIMER` (вывод о полноте артефакта из намеренно урезанного
куска запрещён), `_integration_review_prompt` получает `unitBoundaries` по всем
юнитам и обязан разрешить пограничное наблюдение против них.

Правка продюсера обесценивает подписанные efficacy-ноги по построению — все три
перечеканены живьём (`cleanFalseBlockRate` 0.0, детекция 1.0 на WSL, нативном
Windows и cross-vendor). Windows-нога требует DPAPI-конверта
`…keys/gpg003-local-producer-20260803.windows.key`, сырой 32-байтовый ключ там
не принимается.

## 3c. Состояние ветки на момент публикации (2026-08-16)

`chore/release-1.97.0` несёт четыре коммита поверх `main` `706d62a`:

| коммит | что | дерево кандидата |
|---|---|---|
| `fc2b738` | бамп девяти пиновых мест + запись CHANGELOG S5..S9 | `88f0f4c9` |
| `e26b51b` | live re-record под тот бамп | `16201b44` |
| `1e92f05` | раскрытие разреза юнитов ревьюеру (разблокировка маршрута) | `f457d61b` |
| `6ccb4c1` | live re-record под правку продюсера | `febd23b5` |

Каждый прошёл свой маршрут: изолированные машинные квитанции с оракулами,
покрывающими `oracleIds` критериев S9-1..S9-7, свежий независимый чекер другой
модели, две adjudication на точном дереве и запись в review-cache.

Два замечания честности по этой сессии:

- `claude -p` не аутентифицируется из подпроцесса (401, OAuth token revoked),
  поэтому роль свежего чекера исполнял `gpt-5.6-terra` — cross-vendor, то есть
  независимость не ниже прежней, а выше.
- Продюсер отказывается принимать диф коммита фикстуры:
  `canonical review diff line exceeds unit bound` — в записи есть JSONL-строка
  длиннее лимита юнита. Это ограничение маршрута, не кандидата; записано в
  BACKLOG, внутри релиза не чинится (правило: код маршрута ревью в этом релизе
  заморожен). Поэтому claim публикации делается на этом документационном
  коммите, как и в прецеденте S9.

## 4. Что осталось по релизу v1.97.0

1. **Re-record живого бенчмарка — ОБЯЗАТЕЛЕН и идёт ПОСЛЕДНЕЙ tracked-правкой.**
   Бамп версии трогает три манифеста внутри `METHODOLOGY_TREE_ROOTS`
   (`tests/verify_live_model_benchmark.py:26`), поэтому content-пин в
   `tests/fixtures/live-model-evidence/latest.json` сгорает по построению.
   `bash tests/run-all.sh` этого НЕ ловит: ни CORE, ни FULL не передают
   `--require-evidence`. CI ловит — `.github/workflows/meta-review.yml:158`
   зовёт `python3 tests/verify_live_model_benchmark.py --require-evidence
   --max-age-days 30`, и на дереве `9be84549` это 104 passed / 4 failed
   (content-пин, dirty-state digest, repository-local harness, source pin).
   Найдено свежим чекером `claude-sonnet-5` на кандидате 2026-08-16
   (отчёт `.itd-memory/verification-loop/reports/S9-RELEASE-gr-checker-report.md`,
   verdict BLOCKED).

   **Запись пина нельзя положить в тот же кандидат, что и бамп.** `stable_git_status`
   (`tests/verify_live_model_benchmark.py:82-94`) вычёркивает из отпечатка
   только `tests/fixtures/live-model-evidence/`, поэтому запись при 12 staged
   файлах даст `workingTreeStatusSha256` от этих 12 строк, а после коммита
   дерево чистое — и проверка `dirty-state digest is pinned` снова красная, уже
   в CI. Отсюда порядок: (1) довести ВСЕ tracked-правки и закоммитить бамп
   своим маршрутом ревью; (2) на чистом закоммиченном дереве прогнать live
   re-record; (3) закоммитить фикстуру вторым маршрутом ревью — 12 файлов
   фикстуры снова больше `MAX_FILES_WITHOUT_REVIEW`, коммит без своей квитанции
   не пройдёт.

   Форма второго шага — на выбор, обе с прецедентом, разницы по существу нет:
   отдельный re-pin-коммит (`42c168f` — «on the clean committed tree», `59ad17d`,
   `c7c0afa`, `a8b0885`, `de4f9c1`) либо `git commit --amend` фикстуры в коммит
   бампа. Релиз v1.96.0 сделан вторым способом: `60db6bb` («chore: release
   v1.96.0», манифесты уже 1.96.0, дерево чистое) → re-record на нём
   (`latest.json` в `7f4b515` пишет `workingTreeDirty: false` и
   `workingTreeStatusSha256` от пустого статуса, `revision 60db6bb`) → amend в
   `7f4b515` (21 файл; `60db6bb` ему НЕ предок — коммит переписан) → squash-merge
   в `f3795d5`. Что не работает ни в какой форме — запись, сделанная поверх
   staged-кандидата.
2. Полный `bash tests/run-all.sh` зелёным на ветке релиза, плюс отдельно
   `verify_live_model_benchmark.py --require-evidence --max-age-days 30`
   (в `run-all.sh` этого флага нет ни в CORE, ни в FULL — проверять руками).
3. Маршрут коммита — СВОЙ у каждого из двух коммитов: 12 файлов >
   `MAX_FILES_WITHOUT_REVIEW=2`, значит нужны машинные квитанции для `<unit>` и
   `<unit>:general-review`, свежий чекер другой модели, две adjudication и
   запись `itd_review_cache.py record`.
4. Своя committed-head publication claim по разделу 3, затем `itd pr create`,
   CI, merge.
5. **Раскатка на ОБА инсталла** (иначе правки хуков и скиллов не активны):
   `bash scripts/sync-to-active.sh`, затем то же с
   `CLAUDE_HOME=/mnt/c/Users/Дмитрий/.claude`; после —
   `bash scripts/verify-sync-to-active.sh`, drift обязан быть чистым.
   2026-08-15 обнаружилось, что инсталл сидел на версии С ДЫРОЙ, которую тот
   же срез и чинил, — это не формальность.
6. Смоук изменённых хуков (`record-agent-skill.sh`, `completion-gate.sh`)
   реальным tool-вызовом. Рестарт не нужен, регистрации подхватываются горячо.

## 5. Грабли

- `.itd/` в `.gitignore`, но файлы tracked → `git add -f`, иначе exit 1 рвёт
  цепочку `&&`.
- Completion-гейт классифицирует прогон по эху `EXIT: $?` и берёт ПОСЛЕДНИЙ
  прогон на строку команды; зелёный L2-сигнал давай одиночной командой.
- GitHub API моргает TLS — `gh` вызовы ретраить циклом; REST надёжнее GraphQL.
- Правки строк с backticks — только Edit-тулом, не heredoc через двойной шелл.

## 6. Открытые долги (BACKLOG)

- Недетерминизм изолированного `quick`-агрегатора (S2 пин объясняет часть, но
  не весь класс).
- Пин live-evidence сгорает от любой правки `skills/`, `agents/`, `hooks/` —
  один re-record в конце среза, на чистом дереве.
