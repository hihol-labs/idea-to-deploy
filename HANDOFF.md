---
project: idea-to-deploy
stage: VERIFY
unit: REL-1.105.0
riskTier: high
branch: chore/release-1.105.0
base: fad7915
from: release-prep session 2026-09-22 (Claude Fable 5.1, canonical checkout)
to: next release-route actor (fresh session or post-compaction continuation, same owner)
date: 2026-09-22
---

# HANDOFF - REL-1.105.0: релизный маршрут v1.105.0 (high, многошаговый)

Пакет заложен **в начале** маршрута по правилу 60%: релиз 1.104.0 занял два дня и
несколько компакций, детали терялись. Дополняй этот файл чекпоинтом после каждой
фазы (см. «Маршрут»), а не в конце.

## 1. From -> To

- **From:** сессия подготовки релиза 2026-09-22, канонический чекаут
  `/home/hihol/projects/idea-to-deploy`, ветка `chore/release-1.105.0` от `fad7915`.
- **To:** актор, который ведет релизный маршрут дальше - свежая сессия или та же
  после компакции. Владелец тот же; egress-шаги (PR, релиз, раскатка) - только по
  его явному go, каждый отдельно.

## 2. Причина передачи

Заложенный заранее handoff для high-risk юнита с длинным маршрутом (бамп ->
ревью -> live re-record -> продюсер -> PR -> merge -> тег -> раскатка WSL+Windows
-> канарейки -> installed-proof -> ОТК -> ledger-close). Ожидаемый расход контекста
> 60%. Компакция еще не случилась.

## 3. Текущее состояние

Цифры репортера харнеса (`itd_goal_report.py`, 2026-09-22): **3/4 юнитов verified
[active]**; `in_progress: 1, verified: 3`; текущий юнит `REL-1.105.0`; открытых
юнитов 1. Verified: `LEDGER-ARCHIVE-1`, `ROUTE-REPAIR-3`, `ROUTE-DEBTS-ORACLE-1`.

**Канонический статус маршрута = ПОСЛЕДНЯЯ запись раздела «Чекпоинты»**; этот раздел
описывает состав кандидата и окружение, а не текущую фазу.

**Git.** `main` == `origin/main` == `fad7915`. Ветка `chore/release-1.105.0`, не запушена.
Релизный коммит создаётся над `fad7915` из полностью застейженного кандидата (индекс ==
рабочее дерево); когда раунд ревью требует правку, коммит возвращается в индекс
`git reset --soft fad7915` и пересоздаётся после чистого PASS - поэтому в разные моменты
ветка имеет 0 или 1 коммит (см. чекпоинты). Состав кандидата:

- бамп `1.104.0 -> 1.105.0` в десяти местах критерия: `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`,
  `docs/HARNESS_DOCS_STATE.json` (`pluginVersion`), бейджи `README.md` и
  `README.ru.md`, `docs/HARNESS_CONFORMANCE_REPORT.md`,
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`, `VERSION` в
  `tests/verify_external_reviewer_release.py`;
- `CHANGELOG.md`: `## [Unreleased]` (пустой цикл после 1.105.0) над
  `## [1.105.0] - 2026-09-22`; преамбула цикла дополнена PR #297/#299/#300 и
  ledger-close #296/#298/#301; секция `### Boundaries` добавлена;
- `.itd/SCOPE_LOCK.md` переписан под `REL-1.105.0`; `.itd/ACCEPTANCE_CONTRACT.json`:
  строки `REL-1.105.0-1-version` и `REL-1.105.0-2-mirror` (`passed`), followup
  `REL-1.105.0` открыт, прежний закрытый ушёл в `closedFollowups`; `.itd/DECISIONS.md`:
  запись про re-record во временном worktree; этот `HANDOFF.md`;
- live-model evidence: `tests/fixtures/live-model-evidence/latest.json` +
  `runs/20260922T094239Z-728ce2e8/` (PASS, provider `openai`, записано на чистом
  временном worktree staged-дерева, tmp-объект `2f11edc3`);
- активация юнита: `.itd-memory/GOAL.json` (`currentUnitId: REL-1.105.0`, статус
  `in_progress`), `.itd-memory/STATE.json` (`currentUnit` = REL-1.105.0, high),
  `.itd-memory/events.jsonl` (+1 строка `activated`, `2026-09-22T09:02:08Z`).

**Что проверено (evidence).** Версия: `version consistent 1.105.0 10/10 places
anchored`. `meta_review` PASSED. `verify_live_model_benchmark.py --require-evidence` на
чистой материализации staged-дерева: 154/0. `/review` code-reviewer: PASS после одной
исправленной находки. Quick-зеркало, машинные квитанции и раунды Sol - ПО РАУНДАМ, см.
раздел «Чекпоинты» (последняя запись = текущее положение; здесь номера раундов не
дублируются, чтобы не устаревать).

**Что НЕ сделано (на момент последнего чекпоинта).** Публикационная цепочка с чистым PASS
на committed-head, регистрация реестра, PR, тег, релиз, раскатка, канарейки,
`INSTALLED.json`, ОТК, ledger-close.

**Окружение (факты на 2026-09-22).**

- Реестр гейтов: `itd gate doctor --repository hihol-labs/idea-to-deploy` ->
  `LOCAL_REVIEWED`, но строка репозитория указывает на чекаут worktree
  `route-debts-oracle-4c8ad3` с квитанцией `ROUTE-DEBTS-ORACLE-1`; `itd pr create` из
  этого чекаута откажет до `register-profile` с квитанцией этого юнита. Бэкап:
  `~/.config/itd/gates.json.bak-rel1105-20260922`.
- Провенанс install-source: `bash scripts/sync-to-active.sh` прогнан с ЭТОГО чекаута,
  `~/.claude/.itd-install-source.json` -> `/home/hihol/projects/idea-to-deploy` (бэкап
  `.bak-rel1105-20260922`) - риск (b) закрыт штатно, без флипа руками.
- Установленные runtime: WSL `~/.local/share/itd/runtime/1.104.0-2e96b3bd835e765c`
  (активный wrapper) + `1.104.0-16dcdb41c6518106`; Windows
  `.../ITD/runtime/1.104.0-ea5ba0746a4e7ada` (активный) + `1.104.0-16dcdb41c6518106`.
  Старые каталоги - rollback-артефакты, не удалять.
- Authority-снимок `~/.cache/itd-review-authority/REL1105-f43de442-a1` создан с дерева
  `f43de442` = дерево `fad7915` (parity exit 0; релиз `skills/_shared` не меняет).
- Windows-копия `C:\itd-src\idea-to-deploy`: detached на `0a1673a` с застейдженными
  остатками transport 1.104.0 и stash `pre-1.104.0 local modifications (kept for the
  owner)` - stash не сбрасывать; шаг `clone` драйвера раскатки стешит обратимо.
- Временный worktree `~/.cache/itd-release-record/rel1105-a1` (tmp `2f11edc3`) - место
  записи evidence; удалить после коммита (`git worktree remove --force`).
- Заброшенный worktree `.claude/worktrees/idea-to-deploy-release-1-105-607570`
  (`f41308d`, чист) - ранний старт, не рабочий чекаут; удаление - по команде владельца.
- Предупреждения валидатора про `GOAL-2026-07-06-axis*.json`, `GOAL-2026-09-20.json`,
  `GOAL-harness-conformance-2026-07-15.json` (verified-юниты без событий) - старые,
  вне скоупа.

## 4. Финальные решения (из [[.itd/DECISIONS.md]] и памяти владельца)

- **Единственный источник критерия - текст юнита в [[.itd-memory/GOAL.json]]**;
  SCOPE_LOCK, контракт и этот файл на него ссылаются и не пересказывают.
- **REL-1.105.0 - отдельной сессией; один пункт плана = одна сессия** (владелец,
  2026-09-22). RSI/GENG/другие юниты в этой сессии не начинать.
- **Нога `--installed-proof` принимается в REL-1.105.0 на релизном дереве**
  (владелец, 2026-09-21): пруф 1.104.0 привязан к runtime тега `v1.104.0`, source
  ушел вперед; перечеканивать старый пруф под текущий source отвергнуто.
- **Релиз = только бамп + CHANGELOG + перепин live-evidence.** Никаких поведенческих
  правок кода (SCOPE_LOCK, `### Boundaries` в CHANGELOG).
- **Механика релиза = [[docs/RELEASE_RUNBOOK.md]]**, не импровизация: свежий
  `origin/main` до ветки и до бампа; тег **только** `gh release create --target
  "$(git rev-parse <полный merge-sha>)"` (прямой push тега блокируется pre-push
  гейтом - ожидаемо); раскатка на оба инсталла + нативная переустановка `itd` и
  `pre-push` на каждом хосте из его собственной source-копии.
- **Live re-record - ДО коммита, во временном detached worktree staged-дерева**
  (DECISIONS 2026-09-22, заменяет двухкоммитную форму 1.104.0): recorder пишет только на
  чистом дереве (`rel6.log.failed-live-pin-dirty`), пин контентный и равен дереву
  кандидата, поэтому один коммит несет бамп и evidence вместе.
- **`/review`-субагент обязателен в маршруте**; продюсер его не заменяет (владелец,
  2026-09-08).
- **Ревьюер по умолчанию `gpt-5.6-sol`**, `terra` - только транспортное падение с
  пометкой `degradedFrom` (решение 2026-08-31).
- **Owner-маршрут - только по явному решению владельца**, событие несет
  `actor: human-owner` (прецедент `REL-1.104.0-owner-close.py`). Без чистого PASS
  продюсера самовольно не закрывать; стоп-правило -> варианты владельцу.
- **Egress и durable-мутации - по явному go на каждый шаг**: `itd pr create`,
  merge, `gh release create`, `sync-to-active`, нативные инсталлеры, перерегистрация
  реестра.

## 5. Требуемые входы (прочитать до старта)

1. [[.itd-memory/GOAL.json]] - юнит `REL-1.105.0`: `criterion` и sealed
   `verificationCommand` - единственный источник; здесь НЕ пересказываются, читать
   там (ноги для ОТК гонятся целиком, одним прогоном).
2. [[docs/RELEASE_RUNBOOK.md]] - конвейер и грабли.
3. [[.itd/DECISIONS.md]] - записи 2026-09-20..22; [[.itd/FORBIDDEN_CHANGES.md]].
4. Шаблон релизного SCOPE_LOCK: `git show df95089:.itd/SCOPE_LOCK.md` (REL-1.104.0);
   заменить версию и строку зеркала на `DONE fails:none`.
5. [[BACKLOG.md]]: «P1 - release-bump вне install-source чекаута: круг двух
   валидаторов (2026-09-01)», «P2 - каждый релиз обязан перечеканивать live-benchmark
   (2026-09-01)», «P1 - четыре замера маршрута ROUTE-DEBTS-ORACLE-1 (2026-09-21)».
6. Переиспользуемые драйверы 1.104.0 (git-ignored, только в каноническом чекауте),
   `.itd-memory/verification-loop/REL-1.104.0-*`: `rollout-wsl.py`
   (checkout/deploy/install/codex/authority/canary), `rollout-windows.py`
   (clone/install/canary/copy через PowerShell, длинный путь `python.exe`, `chcp 65001`),
   `native-canary-producer.py`, `installed-proof-assemble.py` (`--linux-label`/
   `--windows-label`), `canary-close.py` (доставка staged-кандидата на Windows через
   `git bundle` по именованному ref), `mint-authority.py`, шаблоны
   `run-machine-*.py` / `run-sol-*.py` / `adjudicate-*.py`, `owner-close.py`;
   `.itd-memory/deploy-release-1.104.0.sh`, `.itd-memory/refresh_codex_caches.sh`.
   Копировать под `REL-1.105.0-*`, менять версию/head/метки; оригиналы не трогать.
7. Образец `INSTALLED.json` schema v2: `.itd-memory/host-inputs/REL-1.104.0/INSTALLED.json`.
8. Память маршрута 1.104.0 (ловушки): `session_2026-09-10_2.md`, `_3.md`, `_5.md`;
   1.103.0: `.itd-memory/HANDOFF-REL-1.103.0.md` §«Ловушки маршрута»;
   `session_2026-09-21_5.md`, `session_2026-09-22.md` (реестр, `gh pr ready`, merge).
9. Рекордер live-evidence: `tests/run-live-model-benchmark.py` (`--fixture
   fixture-03-cli-tool`, `--provider auto|anthropic|openai`, `--budget 5.00`,
   `--timeout-seconds 1800`); ~10 мин, бесплатно на fixture-03.

## 6. Зоны записи и запреты

**Можно (скоуп релиза, `.itd/SCOPE_LOCK.md` этого юнита):** десять мест версии (уже
правлены); `CHANGELOG.md` (уже правлен); `.itd/SCOPE_LOCK.md` (переписать под
юнит); `HANDOFF.md`; пин `tests/fixtures/live-model-evidence/` - **в этом же кандидате**
(re-record во временном worktree staged-дерева, DECISIONS 2026-09-22);
канонические леджеры `.itd-memory/{GOAL,STATE}.json`, `events.jsonl`; строки этого
юнита в `.itd/ACCEPTANCE_CONTRACT.json`; записи в `.itd/DECISIONS.md` и `BACKLOG.md`;
git-ignored `.itd-memory/host-inputs/REL-1.105.0/` и
`.itd-memory/verification-loop/REL-1.105.0-*`.

**Нельзя:** любое поведенческое изменение кода (`skills/`, `hooks/`, `scripts/`,
`tests/*.py` кроме `VERSION`); `itd_external_reviewer.py`, `itd_review_broker.py`,
`itd_free_reviewer_producer.py`; переписывать/удалять существующие live-прогоны и
efficacy-ноги; удалять runtime-каталоги; править байты установленного runtime
(FORBIDDEN_CHANGES: релизить новую версию, не патчить инсталл); прямой `git push`
(только `itd pr create`), `--no-verify`; сбрасывать stash на `C:\itd-src`; начинать
следующие юниты; заявлять раскатку/релиз без host-observed артефактов; переводить
юнит в `verified` мимо ОТК без решения владельца.

## 7. Маршрут и команды проверки

Фазы по порядку; после каждой - чекпоинт в этот файл (`## Чекпоинт <фаза>`).

- **P0 подготовка (на рабочем дереве) - СДЕЛАНО.** `.itd/SCOPE_LOCK.md` переписан;
  `sh skills/_shared/itd_py.sh tests/meta_review.py` PASSED; `bash tests/run-all.sh
  --quick | tail -1` = `DONE fails:none` (зеркало гоняет `verify_live_model_benchmark`
  без `--require-evidence`, поэтому бамп его НЕ красит; красным пин был бы только в CI
  Gate 1 до re-record); `/review`-субагент по диффу - PASS после одной правки.
- **P1 live re-record ДО коммита (решение DECISIONS 2026-09-22).** Staged-дерево
  кандидата -> `git write-tree` -> `git commit-tree <T> -p fad7915` (временный объект,
  не на ветке) -> `git worktree add --detach ~/.cache/itd-release-record/rel1105-a1 <C>`
  -> в worktree: `sh skills/_shared/itd_py.sh tests/run-live-model-benchmark.py
  --fixture fixture-03-cli-tool --provider openai` (лог
  `.itd-memory/verification-loop/REL-1.105.0-live-record-a1.log`, пара tree/tmp -
  `...-a1.candidate`) -> скопировать `tests/fixtures/live-model-evidence/latest.json` и
  новый `runs/<id>/` в кандидат -> `git add` -> `verify_live_model_benchmark.py
  --require-evidence` на staged-дереве должен быть 85+/0 (пин контентный:
  `.claude-plugin`, `.codex-plugin`, skills/blueprint, ...). Зеркало гоняет этот оракул
  БЕЗ `--require-evidence`, поэтому quick и до re-record зеленый; красным пин был бы
  только в CI Gate 1.
- **Роли маршрута (глоссарий).** Мейкер - `claude-fable-5-1` (anthropic-subscription, эта
  сессия); независимый ревьюер - `gpt-5.6-sol` (openai-subscription) через keyless
  producer из authority `REL1105-f43de442-a1`. «Sol-раунд rel<N>» ниже = раунд ЭТОГО
  кросс-вендорного ревью; Sol никогда не мейкер.
- **P2 один коммит** (бамп + CHANGELOG + SCOPE_LOCK + HANDOFF + DECISIONS + acceptance +
  активация леджера + evidence). До него: `REL-1.105.0-capture-quick-mirror.py --label
  rel1` (host input `source-rel1`, sealed line `DONE fails:none`) -> `run-machine.py
  --label rel1` (unit `REL-1.105.0`, 9 оракулов) -> `run-general-machine.py --label rel1`
  (`REL-1.105.0:general-review`) -> `run-sol.py --label rel1` -> `adjudicate.py --label
  rel1` (оба claim) -> `itd_review_cache.py record` -> commit
  `chore(release): v1.105.0 ...`. Коммит-гейт: см. риск (b).
- **P3 публикация.** Публикационная цепочка на committed-head (`run-machine.py --label
  pub1 --source-label <mirror on committed tree>`, `run-sol.py --label pub1
  --candidate-mode committed-head`, `adjudicate.py --label pub1 --candidate-mode
  committed-head`), стоп-правило -> бэкап `~/.config/itd/gates.json` ->
  `itd gate register-profile` на ЭТОТ чекаут с квитанцией pub1 ->
  `itd gate doctor --repository hihol-labs/idea-to-deploy` = `LOCAL_REVIEWED`, drift `[]`
  -> `sh skills/_shared/itd_py.sh scripts/itd.py pr create --maker-vendor anthropic
  --maker-model claude-fable-5-1 --maker-session efbc1513-875b-40b6-be78-43fae508c403
  --timeout 3600` -> `gh pr ready <n>` -> CI (Gate 1 + windows-verify) -> **merge только по
  команде владельца**: `gh pr merge <n> --squash --match-head-commit <head>`.
- **P4 тег и релиз.** `gh release create v1.105.0 --target "$(git rev-parse
  <merge-sha>)" --title "v1.105.0" --notes-file <секция 1.105.0 из CHANGELOG>`.
  Проверка: `git fetch --tags && git rev-parse v1.105.0^{commit}`;
  `gh release view v1.105.0 --json tagName,isDraft,isPrerelease,publishedAt,targetCommitish`;
  нога «тег на first-parent» из `verificationCommand`.
- **P5 раскатка.** WSL: `REL-1.105.0-rollout-wsl.py --merge-head <sha> --step
  checkout,deploy,install,codex` (шаг `authority` НЕ нужен: бамп не трогает
  `skills/_shared`, snapshot `REL1105-f43de442-a1` остаётся байт-идентичным merged main -
  подтвердить `python3 scripts/itd_authority_check.py --snapshot
  ~/.cache/itd-review-authority/REL1105-f43de442-a1 --repo .` exit 0 на merge-head);
  Windows: `REL-1.105.0-rollout-windows.py --merge-head <sha> --step clone,install`
  (клон `C:\itd-src\idea-to-deploy` сейчас на `0a1673a` со staged-остатками transport
  1.104.0 - шаг `clone` их stash'ит как «pre-1.105.0 local modifications»). Проверка: `bash scripts/sync-to-active.sh --check`;
  `CLAUDE_HOME=/mnt/c/Users/Дмитрий/.claude bash scripts/sync-to-active.sh --check`;
  `ls ~/.local/share/itd/runtime/ /mnt/c/Users/Дмитрий/AppData/Local/ITD/runtime/ | grep 1.105.0`.
- **P6 канарейки и пруф.** `native-canary-producer.py` на каждом хосте нативно
  (WSL `a1`, Windows `a4`, интерпретатор = тот, что в wrapper) на **точном дереве,
  на котором пойдет ОТК** -> `installed-proof-assemble.py --linux-label a1
  --windows-label a4` -> `sh skills/_shared/itd_py.sh tests/verify_route_debts.py
  --installed-proof .itd-memory/host-inputs/REL-1.105.0/INSTALLED.json` exit 0 на хосте.
- **P7 ОТК.** Полный `verificationCommand` одним прогоном; квитанция чекера ->
  `sh skills/_shared/itd_py.sh skills/goal/scripts/itd_goal_verify.py REL-1.105.0
  --verification-receipt <adjudication.json>`. Ожидаемая строка: `VERIFIED REL-1.105.0`,
  цель 4/4. Если квитанция невозможна - стоп, варианты владельцу (прецедент
  owner-маршрута 1.104.0).
- **P8 ledger-close** отдельным docs-only PR (DECISIONS: решения публикации и цена
  маршрута; BACKLOG: замеры; SCOPE_LOCK под закрытие; events), снова
  `register-profile` -> `pr create` -> `gh pr ready` -> merge. Затем
  `/session-save --close`.

## 8. Блокеры и риски

> [!warning]
> (a) **Реестр гейтов stale** - `itd pr create` откажет `checkout is not uniquely
> registered` до `register-profile` с квитанцией ЭТОГО юнита на ЭТОТ чекаут; бэкап
> `gates.json` перед перерегистрацией (прецедент `.bak-route-debts-oracle-20260921`).
>
> (b) **Круг двух валидаторов на release-bump** (BACKLOG P1 2026-09-01): install-source
> указывает не на этот чекаут -> коммит-гейт проверяет квитанцию инсталловым
> валидатором с `methodologyVersion` 1.104.0, репо-валидатор пишет 1.105.0 -> промах
> кэша, ложный блок коммита A. Известные обходы: (1) разовый флип
> `~/.claude/.itd-install-source.json` -> `checkout: /home/hihol/projects/idea-to-deploy`
> с бэкапом и восстановлением (v1.102.0); (2) чеканить цепочку инсталловым loop'ом.
> Выбор - владельцу; `--no-verify` запрещен.
>
> (c) **Live-пин краснеет на бампе** (пин включает `.claude-plugin`/`.codex-plugin`):
> закрыто решением P1 - re-record во временном detached worktree staged-дерева до
> коммита; recorder пишет только на чистом дереве. Любая правка пинуемых файлов после
> записи обесценивает evidence (HANDOFF/DECISIONS/acceptance не пинуются).
>
> (d) **`--installed-proof` привязан к точному дереву кандидата**: канарейки `a1/a4`
> 1.104.0 устарели после одного лишнего PR (#277). Канарейки и ОТК - на одном дереве;
> если ledger-close меняет дерево - перечеканка на staged-кандидате (`canary-close.py`).
>
> (e) **Продюсер может не сойтись** (1.103.0: 16 заходов, 0 чистых PASS; 1.104.0:
> owner-маршрут). Стоп-правило составляет диспозиции, подписывает владелец.
>
> (f) Windows: канарейка только из UTF-8-консоли (`chcp 65001`) и длинного пути
> `python.exe`; изолированные кандидаты только под `.itd-memory/isolated-tmp` (safe.directory);
> у `--shared`-клона нет GitHub-remote -> `GH_REPO=hihol-labs/idea-to-deploy`;
> declared input `.itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256`,
> иначе зеркало кончается `blocked: verify_independent_review_efficacy`.
>
> (g) `itd pr create` создает черновик -> `gh pr ready`; `--timeout 3600`; при
> `UNAVAILABLE` проверять факт (`gh pr view`), не код возврата.
>
> (h) Скретчпад сессии стирается при рестарте - драйверы и логи класть только в
> `.itd-memory/verification-loop/`.
>
> (i) Продюсер требует `--maker-session <id>` текущей сессии Claude Code - записать
> id в чекпоинт до компакции.

Блокеров, останавливающих P0, нет.

## 9. Первое действие

> [!todo]
> Кандидат застейжен целиком; evidence записано и в индексе - НЕ перезапускать recorder
> и не копировать из worktree повторно. Открыть раздел «Чекпоинты», взять ПОСЛЕДНЮЮ запись:
> если её Sol-раунд PASSED - `REL-1.105.0-adjudicate.py --label <N>` ->
> `itd_review_cache.py record` -> коммит (сообщение `REL-1.105.0-commit-message.txt`);
> если BLOCKED - закрыть находки, новый `capture-quick-mirror` -> `run-machine` ->
> `run-general-machine` -> `run-sol` с меткой N+1. Перед мержем: `git rev-parse
> origin/main` должен быть `fad7915` (DECISIONS 2026-09-22, дрейф базы -> re-record на
> merged-дереве).

---

## Чекпоинты

_(дописывать по фазам: дата/время, фаза, sha/дерево, evidence-строка, что дальше)_

- 2026-09-22 P-1 (подготовка пакета): ветка `chore/release-1.105.0` @ `fad7915`, WIP
  13 файлов не закоммичены; нога версии `version consistent 1.105.0 10/10 places
  anchored` exit 0; authority `REL1105-f43de442-a1` создан 12:09 с дерева `f43de442`.
  Дальше: P0.
- 2026-09-22 P0 (подготовка кандидата): SCOPE_LOCK переписан, acceptance-строки
  `REL-1.105.0-1-version` / `-2-mirror` добавлены, followup открыт, DECISIONS дополнен
  (re-record в worktree), `meta_review` PASSED, `verify_live_model_benchmark` без флага
  85/0, с `--require-evidence` красный (ожидаемо до re-record). Temp-объект кандидата:
  tree `5721e251`, commit `2f11edc3`, worktree `~/.cache/itd-release-record/rel1105-a1`;
  recorder запущен в фоне; `/review` (code-reviewer) запущен по staged-диффу.
  Helper-скрипты: `.itd-memory/verification-loop/REL-1.105.0-{capture-quick-mirror,
  run-machine,run-general-machine,run-sol,adjudicate,mint-authority,native-canary-producer,
  rollout-wsl,rollout-windows,installed-proof-assemble,canary-close}.py`,
  `.itd-memory/deploy-release-1.105.0.sh`; оракульные помощники
  `.itd-memory/host-inputs/REL-1.105.0/source-template/`. Дальше: P1 копия evidence.
- 2026-09-22 P1 (live re-record): recorder exit 0 в worktree `rel1105-a1` (tmp `2f11edc3`),
  прогон `20260922T094239Z-728ce2e8` PASS, `latest.json` + `runs/<id>/` добавлены в индекс.
  `verify_live_model_benchmark.py --require-evidence` на ЧИСТОЙ материализации staged-дерева
  (`a88b42ad`, tmp `cb0d5327`, worktree удалён): 154/0; на грязном хосте единственный
  красный - `dirty-state digest is pinned` (структурно: пин чистого статуса, уйдёт после
  коммита). `meta_review` PASSED, версия 10/10. `/review` code-reviewer: 1 important
  (HANDOFF §4 двухкоммитная форма) - исправлена; зеркало `DONE fails:none` подтверждено
  ревьюером независимо. Дальше: P2 capture-quick-mirror -> machine -> Sol -> adjudicate.
- 2026-09-22 P2 rel1: quick-mirror `source-rel1` на дереве `67ef65ec` = `DONE fails:none`;
  machine rel1 PASSED (9/9), general-machine rel1 PASSED; Sol rel1 (gpt-5.6-sol) BLOCKED,
  6 уникальных находок: (1) high - SCOPE_LOCK требовал evidence отдельным follow-on
  коммитом, DECISIONS - одним кандидатом (реальная; SCOPE_LOCK приведён к DECISIONS);
  (2) medium - HANDOFF §3 устарел (переписан); (3) medium - HANDOFF §3/P0 говорили, что
  quick покраснеет до re-record (исправлено: зеркало гоняет пин без
  `--require-evidence`); (4-6) high/medium/medium - содержание сгенерированных моделью
  артефактов live-прогона `runs/20260922T094239Z-728ce2e8/output/PROJECT_ARCHITECTURE.md`
  (stderr/stdout в диаграмме, UTF-8 replacement vs точная группировка, неполный CSV-
  контракт) - это byte-pinned запись модели, править нельзя; SCOPE_LOCK теперь называет
  их immutable и вне предмета ревью. Дальше: rel2 (mirror -> machine -> general -> Sol).
  Если Sol повторит только (4-6) - стоп-правило: диспозиции владельцу.
- 2026-09-22 P2 rel2: quick-mirror `source-rel2` (дерево `9a36e8ad`) `DONE fails:none`; machine
  rel2 + general-machine rel2 PASSED; Sol rel2 BLOCKED, 3 medium, все реальные: SCOPE_LOCK
  «контракт не пересказывает» vs две acceptance-строки с командами (уточнено: строки - узкие
  claim'ы по одной ноге, byte-copy из GOAL.json); HANDOFF §6 «своим коммитом» (исправлено);
  STATE.nextAction устарел (обновлён). Находок по артефактам live-прогона не было. Дальше rel3.
- 2026-09-22 P2 rel3: quick-mirror `source-rel3` (дерево `41f047e7`) `DONE fails:none`; machine
  rel3 + general-machine rel3 PASSED; Sol rel3 BLOCKED, 2 находки, обе реальные: (high)
  DECISIONS утверждал «squash сохраняет дерево кандидата» безусловно - уточнено условием
  неизменной базы + проверкой `origin/main == fad7915` перед мержем и re-record на
  merged-дереве при дрейфе; (medium) §9 «первое действие» устарело - переписано под
  продолжение с чекпоинта. Дальше rel4.
- 2026-09-22 P2 rel4: quick-mirror `source-rel4` (дерево `8bbed94e`) `DONE fails:none`; machine
  rel4 + general-machine rel4 PASSED; Sol rel4 BLOCKED, 1 low, реальная: source строки
  `REL-1.105.0-2-mirror` говорил «без завершающего grep -q», команда - байт-в-байт копия с
  `grep -qx` (текст исправлен). Дальше rel5.
- 2026-09-22 P2 rel5: quick-mirror `source-rel5` `DONE fails:none`; machine rel5 +
  general-machine rel5 PASSED; Sol rel5 BLOCKED, 3 medium: (a) sealed оракул слабо якорит
  conformance-строку (`endswith`) - оракул менять нельзя (инструкция владельца, seal);
  записано как Declared limit в SCOPE_LOCK и P2 в BACKLOG; (b) HANDOFF §5 пересказывал 10
  ног критерия - убрано; (c) §3/§9 устаревали по номерам раундов - переведены на ссылку
  «последний чекпоинт». Дальше rel6.
- 2026-09-22 P2 rel6 -> коммит: Sol rel6 signed PASSED (findings [], unverified []); checker +
  adjudication PASSED для `REL-1.105.0` (check --require-mandatory-route exit 0) и
  `REL-1.105.0:general-review`; review cache record + check exit 0; коммит `986c3e9`
  (дерево `6baf80af`) с `COMPLETION_BYPASS` (строка 1994 леджера сигналов с пустым evidence -
  прогон зеркала субагентом через пайп; заметка `REL-1.105.0-completion-bypass-note.md`).
- 2026-09-22 P3 pub1 (committed-head `986c3e9`): mirror/machine/general PASSED; Sol pub1
  BLOCKED, 2 medium: нога тега sealed-оракула не исключает более ранний first-parent коммит
  с версией (оракул не меняется - Declared limit + BACKLOG); STATE «clean Sol producer PASS»
  читалось как «Sol - мейкер» (переформулировано, добавлен глоссарий ролей). Дальше: rel7 на
  staged -> amend `986c3e9` -> pub2.
- 2026-09-22 rel7 (staged над `fad7915` после `reset --soft`, дерево `0bee3100`): mirror/
  machine/general PASSED; Sol rel7 BLOCKED, 3 medium: нога зеркала sealed-оракула без
  `pipefail` (третий Declared limit + BACKLOG; sidecar quick.json несёт код выхода 0);
  acceptance `-1-version` заявляла «каждое место заякорено» вопреки объявленному пределу
  (уточнено); §3 снова расходился с чекпоинтами (переписан: канон = последний чекпоинт,
  описан цикл commit/reset --soft). Дальше rel8; при новой находке ТОЛЬКО против sealed-
  оракула - стоп-правило, диспозиции владельцу.
- 2026-09-22 rel8 (staged, дерево в source-rel8/expected-tree.txt): mirror/machine/general
  PASSED; Sol rel8 BLOCKED, 1 medium: STATE.nextAction противоречив («закоммичен» и «до
  коммита») - переписан фазово-нейтрально (цикл staged -> route -> commit -> committed-head
  route, текущая фаза = только последний чекпоинт). Дальше rel9.
- 2026-09-22 rel9 (staged): mirror/machine/general PASSED; Sol rel9 BLOCKED, 6 строк = 3
  механизма, ВСЕ - повтор ранее объявленных пределов sealed-оракула (`GOAL.json`: pipefail
  в ноге зеркала, нога тега, conformance-якорь; уже Declared limits в SCOPE_LOCK и BACKLOG
  P2). Один механизм (`.itd-memory/GOAL.json`, correctness) в rel5/pub1/rel7/rel9 при
  изменённом кандидате = **стоп-правило LPD-003-3**: серия остановлена. Маршрут дальше -
  ADR-007 owner-adjudication: BLOCKED-чекер из отчёта rel9, диспозиции класса
  `accepted-trade-off` (оракул запечатан, инструкция владельца - не менять; ноги
  компенсированы машинной квитанцией quick-mirror и планом следующего релизного юнита),
  подпись владельца -> adjudicate -> check --accept-adjudicated-route -> cache ADJUDICATED
  -> коммит -> та же процедура на committed-head (прецедент 1.104.0 pub7) -> register ->
  PR. Скрипт `REL-1.105.0-sign-and-adjudicate.py`; без подписи владельца ничего не
  минтится и не коммитится.

