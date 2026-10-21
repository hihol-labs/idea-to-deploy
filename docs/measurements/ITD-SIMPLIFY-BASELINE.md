# ITD-SIMPLIFY-BASELINE - замер «до» программы ADR-016

Сессия 2 плана изменения ITD ([ADR-016](../adr/ADR-016-itd-default-everywhere-program.md)), 2026-10-21. Состояние:
main `162c9d3` (v1.109.2), установка 1.109.2 на WSL и Windows. Повтор «после» - сессии 3 и 6 (для их приемки) и 13
(целиком, против раздела 2 плана), теми же командами из раздела 8. Скрипты - `docs/measurements/itd-simplify/`
(их тесты: `python3 -I -B docs/measurements/itd-simplify/test_measure_tools.py`, 7 проверок);
сырые выводы прогонов лежат в git-excluded scratchpad сессии, сюда перенесены числа. Время - по меткам
транскриптов, хуков и `perf_counter` стенда, не по оценке агента.

## 0. Условия замера

| | WSL | Windows |
|---|---|---|
| ОС, CPU | WSL2, ядро 6.6.87.2-microsoft-standard-WSL2, 8 vCPU (`uname -r`, `nproc`) | тот же ПК, WSL-VM делит с ним CPU |
| Claude Code (харнесс десктопа) | 2.1.304 (поле `version` последних записей транскриптов; с 2026-10-14 встречаются 2.1.295, 2.1.299, 2.1.304) | 2.1.304 (то же поле в последнем транскрипте buying) |
| Claude Code npm CLI | 2.1.186 (`claude --version`) | 2.1.186 (`npm/node_modules/@anthropic-ai/claude-code/package.json`) |
| Codex CLI | 0.146.0 (`codex --version`) | 0.157.1 (`npm/node_modules/@openai/codex/package.json`) |
| Интерпретатор хуков | Python 3.12.3 `/usr/bin/python3.12` (`python3 --version`) | `C:/Users/Дмитрий/AppData/Local/Programs/Python/Python312/python.exe -X utf8` (команды в `settings.json`) |
| Node (хуки context-mode) | v22.23.1 (`node --version`) | v24.11.1 (`node.exe --version`) |
| Оболочка хуков в стенде | `/bin/bash` | Git Bash `C:/Program Files/Git/bin/bash.exe` |
| ITD runtime | `~/.local/share/itd/runtime/1.109.2-4a575f29644e1989` (`~/.local/bin/itd`) | `%LOCALAPPDATA%\ITD\runtime\1.109.2-4a575f29644e1989` (wrapper `%USERPROFILE%\.local\bin\itd.cmd`) |
| Дайджест дерева runtime (`runtime_digest.py`, 51 файл) | `f7e78a42b67be1ffe7d16cb608a950dd206e9aaf7431e01aa47540869f8ed0c2` | тот же |
| Плагины с хуками | только `context-mode@context-mode` 1.0.168 (`enabledPlugins` в `~/.claude/settings.json`; `installPath` в `plugins/installed_plugins.json`, в кэше одна версия) | то же |
| permission mode | `bypassPermissions`: `defaultMode` в `settings.json`; в транскриптах с 2026-10-14 - 216 из 216 записей | `bypassPermissions` в 1129 из 1129 записей транскриптов buying |
| Модель | сессия замера - `claude-opus-5-5`; в транскриптах ITD с 2026-10-14: opus-5-5 3794 сообщения, fable-5-1 718 | buying: opus-5-5 29243, fable-5-1 2357 |

Проекты: ITD - `~/projects/idea-to-deploy` на WSL и нативная копия релиза `C:\itd-src\idea-to-deploy-1.109.2` на
Windows; buying - `C:\Users\Дмитрий\AI\buying` (на WSL - тот же каталог через `/mnt/c`). Реальная работа идет в
сочетаниях WSL x ITD и Windows x buying: транскриптов ITD на Windows и buying на WSL нет
(`ls ~/.claude/projects`, `ls C:\Users\Дмитрий\.claude\projects`).

## 1. Цепочка хуков: синтетический стенд, 10 вызовов на инструмент

`hook_bench.py` повторяет то, что хост делает вокруг одного вызова инструмента: все хуки с совпавшим matcher из
пользовательского `settings.json`, проектных `.claude/settings*.json` и `hooks.json` включенных плагинов
запускаются параллельно на PreToolUse, затем на PostToolUse, с JSON на stdin, через bash (`/bin/bash`, на Windows -
Git Bash; какой оболочкой хуки запускает сам Windows-хост, стенд не проверяет).
Нагрузки инертны (Bash `git status --short`, Read и Edit файла `README.md`; инструмент не исполняется). Один
прогрев не учитывается, затем 10 измеренных вызовов; цепочка = Pre + Post. Сочетания запускались по очереди, каждое
после спада 1-минутной нагрузки WSL ниже 1.5 (`os.getloadavg`). Windows-прогон - нативный `python.exe` из копии
скрипта в `C:\itd-src\baseline`, запущенный из WSL через interop (запуск вне измеряемого интервала).

Медиана, мс (мин-макс цепочки); прогон 2026-10-21 19:55-20:05Z:

| Хост x проект | Инструмент | Процессов (Pre+Post) | Pre | Post | Цепочка |
|---|---|---|---|---|---|
| WSL x ITD | Bash | 18 (11+7) | 351 | 234 | 580 (513-677) |
| WSL x ITD | Edit | 11 (5+6) | 175 | 183 | 357 (348-427) |
| WSL x ITD | Read | 7 (2+5) | 169 | 227 | 395 (293-590) |
| WSL x buying | Bash | 18 (11+7) | 390 | 301 | 708 (541-947) |
| WSL x buying | Edit | 11 (5+6) | 203 | 234 | 453 (404-759) |
| WSL x buying | Read | 7 (2+5) | 171 | 224 | 395 (341-453) |
| Windows x buying | Bash | 18 (11+7) | 802 | 491 | 1276 (1159-1791) |
| Windows x buying | Edit | 11 (5+6) | 383 | 410 | 801 (711-1095) |
| Windows x buying | Read | 7 (2+5) | 257 | 359 | 605 (570-765) |
| Windows x ITD | Bash | 18 (11+7) | 814 | 464 | 1268 (1167-1428) |
| Windows x ITD | Edit | 11 (5+6) | 369 | 416 | 783 (733-890) |
| Windows x ITD | Read | 7 (2+5) | 270 | 368 | 646 (595-757) |

Разброс между прогонами того же сочетания заметен, поэтому сравнение «после» делается той же командой при той же
нагрузке. Предыдущие прогоны в этой сессии, той же командой: WSL x ITD Bash 483 мс (нагрузка 0.9 перед стартом) и
768 мс (4.5 - сразу после других прогонов); Windows x buying Bash 1679 мс, Edit 1165, Read 725; Windows x ITD Bash
1520, Edit 1166, Read 880; WSL x buying Bash 808.

Самые медленные команды (медиана стенда): на Windows x buying - `cross-review-precommit.sh` 1071 мс,
`check-dod-before-commit.sh` 895, `state-guard.sh` 810, `check-predeploy-gate.sh` 793 на Pre Bash; на WSL x ITD -
`cross-review-precommit.sh` 271, `pii-egress-guard.sh` 229, `pretooluse.mjs` (context-mode) 229.

## 2. Реальные длительности хуков по транскриптам

Хост пишет в транскрипт запись `hook_success` с `durationMs` и командой хука. Записи есть не у всех хуков (наблюдение:
на вызов Bash в этой сессии - 2 записи Pre при 11 зарегистрированных Pre-командах; судя по составу, пишутся хуки с
выводом). Хуки одной фазы идут параллельно, поэтому максимум `durationMs` среди записанных хуков вызова -
НИЖНЯЯ граница задержки фазы. Окно - транскрипты, измененные с 2026-10-14 (`transcript_stats.py --since
2026-10-14`): WSL x ITD - 5 сессий, Windows x buying - 70.

| Фаза | WSL x ITD: вызовов, медиана нижней границы, мс | Windows x buying: вызовов, медиана, мс |
|---|---|---|
| Bash Pre | 1834, 366 | 3709, 1929 |
| Bash Post | 1773, 242 | 3434, 1530 |
| Edit Pre | 192, 228 | 2697, 920 |
| Edit Post | 192, 228 | 2696, 1082 |
| Read Pre | 19, 147 | 805, 1502 |
| Read Post | - (записей нет) | 2095, 1354 |

Реальные длительности отдельных хуков выше стенда (медиана, число записей): WSL x ITD - `completion-gate.sh` 328
(1830), `state-guard.sh` Pre 335 (1833), `completion-signals.sh` 235 (1773), `pii-egress-guard.sh` 590 (42);
Windows x buying - `completion-gate.sh` 1790 (3715), `state-guard.sh` Pre 1834 (3719), `completion-signals.sh`
1246 (3013), `posttooluse.mjs` 1470 (3434), а хуки, которые пишут вывод редко, - около 9 с: `careful.sh` 9756
(506), `pii-egress-guard.sh` на Bash 8652 (692), `check-dod-before-commit.sh` 9622 (542). Значит, реальный вызов
Bash на Windows x buying платит хукам около 3.4 с и больше (сумма медиан нижних границ: 1.9 Pre + 1.5 Post), а
стенд показывает 1.3 с. Причина разницы не измерялась (кандидаты: работа хоста вокруг хуков, конкуренция с ним за
CPU, реальные payload); цель сессии 6 проверяется обеими командами.

## 3. Процессы на вызов

Каждая команда хука - отдельный процесс интерпретатора (все 17 файлов `~/.claude/hooks/*.sh` этих
цепочек - Python с `#!/usr/bin/env python3`, `head -1`; хуки context-mode - `node`), поэтому число процессов на вызов
= число команд с совпавшим matcher (раздел 1, поле `processes` вывода `hook_bench.py`); дочерние процессы внутри
хуков (git и т.п.) не считаются. Bash 18 = 16 пользовательских (10 Pre + 6 Post) + 2 context-mode, Edit 11, Read 7,
одинаково на обоих хостах. Проектный хук buying (`PostToolUse` на `Write`) в эти три инструмента не входит.

Ложные deny ядра, наблюденные в сессии замера (метрика раздела 2 плана): `check-predeploy-gate.sh` отказывает на
подстановке `$(...)` рядом с `cd ~/...` или `cd` в каталог buying (2 случая, воспроизведены подачей payload в
установленный хук, BACKLOG P2); external-write gate 1.109.2 отказал (deny без подтверждения: «exact external
targets cannot be derived») на команде `ls -d ... ; echo "$(git rev-parse ...)"; grep -E "...curl..." ...` -
смешанная команда с подстановкой остается под проверкой всего текста намеренно (CHANGELOG 1.109.2), поэтому в
счет ложных deny она не входит; та же работа прошла раздельными командами.

## 4. Байты контекста от хуков

Записи хоста `hook_additional_context` - текст, который хуки добавили в контекст модели (тот же текст внутри stdout
не считается второй раз). Событие UserPromptSubmit - один ввод в сессию (промпт человека или уведомление), его записи
суммируются (в этих данных хост пишет одну запись на событие со строкой от каждого хука). `transcript_stats.py`, то
же окно, прогон 2026-10-21 ~21:10Z; окно включает живую сессию замера, поэтому повтор дает близкие, а не равные
числа:

| | WSL x ITD | Windows x buying |
|---|---|---|
| UserPromptSubmit на событие, медиана (макс) | 397 Б (10728), 209 событий | 444 Б (14050), 542 события |
| На сессию, медиана, всего | 39281 Б | 22799 Б |
| На сессию по событиям, медианы: SessionStart / UserPromptSubmit / PreToolUse / PostToolUse | 8859 / 21857 / 9411 / 5054 | 10194 / 9406 / 4446 / 2182 |

## 5. Время session-save

От сообщения ассистента с вызовом Skill `session-save` до последнего сообщения ассистента перед следующим
промптом человека (`transcript_stats.py`, то же окно): WSL x ITD - 2 прогона, 62 и 67 с (медиана 64); Windows x
buying - 63 прогона, медиана 155 с, минимум 0 (вызов был последним сообщением хода), максимум 954 с.

## 6. Цена закрытия релизов

REL-1.109.1 (`grep '"name": "REL-1.109.1"' .itd-memory/events.jsonl`, `gh pr view 368|369 --json
createdAt,mergedAt,changedFiles,additions,deletions`, `.itd-memory/verification-loop/REL-1.109.1-work-state.json`
поле `completedAtUtc`, `ls -l --time-style=full-iso .itd-memory/verification-loop/*REL-1.109.1-close*
.itd-memory/verification-loop/reports/*REL-1.109.1-close*`):

| Метрика | Значение |
|---|---|
| Активация -> verified | 2026-10-17 18:31:08Z -> 20:55:16Z (2 ч 24 мин); PR #368 смержен 20:10:55Z |
| Учетное закрытие: verified -> мерж PR #369 -> финальная проверка | 20:55:16Z -> 22:20:21Z (85 мин) -> 22:29:16Z (94 мин) |
| Дифф закрытия | PR #369: 3 файла, +6/-3 |
| Модельных сессий в закрытии | 6: чекеры `close-precommit-a1`, `close-precommit-a2` и его дозавершение, рефутеры `close-refute-schema-a1` и `close-refute-provenance-a1`, canonical Terra `close-canonical-a1` (BLOCKED ложной находкой о провенансе parent/child, опровергнута, итог ADJUDICATED `d1e6cc09`) |
| Полный прогон в закрытии | квитанция `REL-1.109.1-close-machine-a1.json` записана 21:39:30Z (скрипт запуска `close-full-a1.py` создан 21:12:42Z); `REL-1.109.1-work-state.json`, поле `currentLedgerClose.fullResult`: 8/8 ног, full 172 из 185 сьютов, fails:none |

REL-1.109.2 (`grep '"name": "REL-1.109.2"' .itd-memory/events.jsonl`, `gh pr view 370`,
`git log --oneline f1aefe5..14a34e8`, файлы `.itd-memory/verification-loop/REL-1.109.2-*` и `reports/`):

| Метрика | Значение |
|---|---|
| Активация -> мерж PR #370 -> verified | 2026-10-20 14:00:48Z -> 2026-10-21 17:32:32Z -> 19:43:07Z (verified записан в этой сессии после повторной приемки) |
| Коммитов ветки | 11 (`8e7fee4` сессии 1 и 10 в сессии публикации, `816e4fc`..`14a34e8`) |
| Отчетов предкоммитного чекера | 19 (a1-a8, a10-a20): BLOCKED 3 (a1 critical, a2, a5), PASSED 16, из них 15 с minor-находками; принятых квитанций чекера и adjudication - по 11 |
| Предкоммитных machine-квитанций | 19 |
| Committed-head machine-квитанций | 10 (a1-a10), FAILED одна - a3, `verify_graph_study` при аптайме меньше 1800 с (BACKLOG P3) |
| Попыток ревью GPT | 13: gpt-5.6-sol a1, a3, a4, a5 - без вердикта (`reports/*-canonical-aN.out`: транспорт `openai-subscription` UNAVAILABLE в a1, a4, a5 - по HANDOFF это Codex 429 - и обрыв потока событий в a3); gpt-5.6-terra a2, a6-a12 - BLOCKED, a13 - PASSED |
| Причины BLOCKED у terra | реальные дефекты и пробелы тестов, исправленные новым кандидатом: a2 (вход исполнителя без кода, PowerShell-двойники, промахи списка инструментов хоста), a6 (формулировки AC3/SCOPE_LOCK, «без перенаправлений», одинарные кавычки cmd), a7 (PowerShell-двойники), a8 (незаякоренный `>/dev/null`), a9 (`RIPGREP_CONFIG_PATH`), a10 (перенаправление вплотную к аргументу); вне области: содержимое образца H4 в a6, a7, a10 и только оно в a12; a11 - одна ложная находка (`^&` в cmd), отклонена с обоснованием (`.itd/DECISIONS.md`, запись REL-1.109.2) |

В памяти сессии публикации это записано как «14 раундов по находкам чекеров и ревью GPT»; документ считает
файлы, а не раунды.

## 7. Инвентарь проектов (`itd_projects_doctor.py`)

Доктор только читает и печатает проекты с находками (`--json`, поле `count` - число находок). Установленная копия
на обоих хостах побайтно равна `skills/_shared/itd_projects_doctor.py` main (`cmp`).

| | WSL: `itd_projects_doctor.py ~/projects --json` | Windows, нативно: `python.exe -X utf8 -I %USERPROFILE%\.claude\skills\_shared\itd_projects_doctor.py C:\Users\Дмитрий\AI C:\Users\Дмитрий\projects --json` |
|---|---|---|
| Каталогов в корнях (`ls -d <корень>/*/`) | 71 | 152 |
| Проектов с находками | 2 (`buy-sfpause`, `buy-wlb`) | 135 (127 - buying и его worktree, плюс `152 - ФЗ`, `portfolio-cases`, `site`, `invoices`, `invoices_wt-hm-lk`, `invoices_wt-zal-requests`, `inv-wt-t355`, `inv-wt-t372`) |
| Находок всего | 4 | 283 |
| `project-hooks` | 2 | 127 (buying*) |
| `shadow-skill` | 2 | 127 (`.claude/skills/deploy` в buying*) |
| `tool-copy` | 0 | 27 (копии `.itd/*.py` старого `/adopt`) |
| `duplicate-hooks` | 0 | 2 (`portfolio-cases`, `site`) |

Это вход сессии 12 («ITD по умолчанию на всей машине»): очистка по этому отчету идет только с подтверждения
владельца на каждую правку в продуктовом репо.

## 8. Как повторить

```bash
# 1. стенд (WSL; каждое сочетание - после спада нагрузки)
python3 docs/measurements/itd-simplify/hook_bench.py --home ~/.claude --project ~/projects/idea-to-deploy --runs 10
python3 docs/measurements/itd-simplify/hook_bench.py --home ~/.claude --project "/mnt/c/Users/Дмитрий/AI/buying" --runs 10
# Windows, нативно (копия скрипта в C:\itd-src\baseline):
#   python.exe -X utf8 C:\itd-src\baseline\hook_bench.py --home C:/Users/Дмитрий/.claude
#     --project C:/Users/Дмитрий/AI/buying --bash "C:/Program Files/Git/bin/bash.exe" --runs 10
# 2. транскрипты (хуки, байты контекста, session-save)
python3 docs/measurements/itd-simplify/transcript_stats.py ~/.claude/projects/-home-hihol-projects-idea-to-deploy --since 2026-10-14
python3 docs/measurements/itd-simplify/transcript_stats.py "/mnt/c/Users/Дмитрий/.claude/projects/C--Users---------AI-buying" --since 2026-10-14
# 3. приемка установленного гейта (exit 1, если решение хоть одного случая не совпало с ожидаемым)
python3 docs/measurements/itd-simplify/egress_acceptance_probe.py ~/.claude/settings.json /tmp
python3 docs/measurements/itd-simplify/egress_acceptance_probe.py /mnt/c/Users/Дмитрий/.claude/settings.json /mnt/c/Users/Дмитрий
# 4. runtime на обоих хостах
python3 docs/measurements/itd-simplify/runtime_digest.py ~/.local/share/itd/runtime/1.109.2-4a575f29644e1989 \
  "/mnt/c/Users/Дмитрий/AppData/Local/ITD/runtime/1.109.2-4a575f29644e1989"
# 5. инвентарь проектов (Windows - нативно, см. раздел 7)
sh skills/_shared/itd_py.sh skills/_shared/itd_projects_doctor.py ~/projects --json
```

## Ограничения

- Стенд измеряет только хуки: запуск инструмента и работу хоста вокруг хуков он не включает, поэтому его числа ниже
  реальных (раздел 2). Цель сессии 6 (медиана -50%) проверяется обеими командами.
- Нижняя граница из транскриптов видит только хуки с выводом; набор таких хуков зависит от команды (например,
  `careful.sh` пишет предупреждение только на опасные команды).
- Стенд пишет телеметрию самих хуков (сигналы завершения, стоимость, трассы) в проекты и домашние каталоги с
  `session_id` `itd-baseline-bench`; файлов проекта он не меняет.
- Числа одного вечера на одной машине; нагрузка записана перед каждым сочетанием.
