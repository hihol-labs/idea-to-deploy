# ITD-SIMPLIFY-BASELINE - замер «до» программы ADR-016

Сессия 2 плана изменения ITD ([ADR-016](../adr/ADR-016-itd-default-everywhere-program.md)), 2026-10-21. Состояние:
main `162c9d3` (v1.109.2), установка 1.109.2 на WSL и Windows. Повтор «после» - сессии 3 и 6 (для их приемки) и 13
(целиком, против раздела 2 плана), теми же командами из раздела 8. Скрипты - `docs/measurements/itd-simplify/`
(их тесты: `python3 -I -B docs/measurements/itd-simplify/test_measure_tools.py`, 10 проверок);
основные числа - из перезамера 2026-10-22 07:38-07:45Z исправленными скриптами (после ревью sol a3), его сырые выводы
лежат в git-ignored `.itd-memory/host-inputs/ITD-PLAN-S2/baseline-raw/` (`meta.txt` - нагрузка, аптайм и коды
выхода каждого шага). Выводы первого прогона 2026-10-21 лежали во временном scratchpad сессии и не сохранились (его
очистила перезагрузка WSL); его числа ниже приведены только как разброс. Время - по меткам
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
| permission mode | `bypassPermissions`: `defaultMode` в `settings.json`; в транскриптах с 2026-10-14 - 216 из 216 записей (подсчет 2026-10-21) | `bypassPermissions` в 1129 из 1129 записей транскриптов buying (подсчет 2026-10-21) |
| Модель | сессия замера - `claude-opus-5-5`; в транскриптах ITD с 2026-10-14: opus-5-5 3794 сообщения, fable-5-1 718 (подсчет 2026-10-21) | buying: opus-5-5 29243, fable-5-1 2357 (подсчет 2026-10-21) |

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
прогрев не учитывается, затем 10 измеренных вызовов; цепочка = Pre + Post. Коды выхода хуков проверяются: в этом
прогоне все хуки всех сочетаний вышли с 0 (`nonzeroExits` пуст, exit 0 стенда). Сочетания запускались по очереди,
каждое после спада 1-минутной нагрузки WSL ниже 1.5 (`os.getloadavg`; нагрузку самой Windows он не видит).
Windows-прогон - нативный `python.exe` из копии скрипта в `C:\itd-src\baseline`, запущенный из WSL через interop
(запуск вне измеряемого интервала).

Медиана, мс (мин-макс цепочки); прогон 2026-10-22 07:38-07:43Z (`bench-*.jsonl`):

| Хост x проект | Инструмент | Процессов (Pre+Post) | Pre | Post | Цепочка |
|---|---|---|---|---|---|
| WSL x ITD | Bash | 18 (11+7) | 303 | 242 | 539 (472-1112) |
| WSL x ITD | Edit | 11 (5+6) | 174 | 183 | 352 (297-422) |
| WSL x ITD | Read | 7 (2+5) | 119 | 199 | 343 (287-698) |
| WSL x buying | Bash | 18 (11+7) | 316 | 257 | 672 (456-1604) |
| WSL x buying | Edit | 11 (5+6) | 150 | 178 | 326 (296-656) |
| WSL x buying | Read | 7 (2+5) | 122 | 256 | 398 (295-788) |
| Windows x buying | Bash | 18 (11+7) | 1038 | 751 | 1826 (1382-2024) |
| Windows x buying | Edit | 11 (5+6) | 598 | 588 | 1257 (907-1349) |
| Windows x buying | Read | 7 (2+5) | 1201 | 1561 | 2712 (1462-4628) |
| Windows x ITD | Bash | 18 (11+7) | 1427 | 902 | 2371 (1732-4607) |
| Windows x ITD | Edit | 11 (5+6) | 669 | 776 | 1483 (1226-2015) |
| Windows x ITD | Read | 7 (2+5) | 630 | 896 | 1574 (895-1848) |

Разброс между прогонами того же сочетания большой, особенно на Windows, поэтому сравнение «после» делается той же
командой несколько раз, а не по одному прогону. Первый прогон 2026-10-21 (19:55-20:05Z, скрипт без проверки кодов
выхода, выводы не сохранились), цепочка Bash / Edit / Read: WSL x ITD 580 / 357 / 395, WSL x buying 708 / 453 / 395,
Windows x buying 1276 / 801 / 605, Windows x ITD 1268 / 783 / 646; еще раньше в тот же вечер - WSL x ITD Bash 483 и 768
мс (нагрузка 0.9 и 4.5 перед стартом), Windows x buying Bash 1679, Windows x ITD Bash 1520.

Самые медленные команды на Pre Bash (медиана стенда, `perCommandMedianMs`): Windows x buying -
`cross-review-precommit.sh` 1035 мс, `pii-egress-guard.sh` 820, `completion-gate.sh` 819, `check-predeploy-gate.sh`
812; WSL x ITD - `cross-review-precommit.sh` 296, `pretooluse.mjs` (context-mode) 241, `state-guard.sh` 236.

## 2. Реальные длительности хуков по транскриптам

Хост пишет в транскрипт запись `hook_success` с `durationMs` и командой хука. Записи есть не у всех хуков (наблюдение:
на вызов Bash в этой сессии - 2 записи Pre при 11 зарегистрированных Pre-командах; судя по составу, пишутся хуки с
выводом). Хуки одной фазы идут параллельно, поэтому максимум `durationMs` среди записанных хуков вызова -
НИЖНЯЯ граница задержки фазы. Окно - транскрипты, измененные с 2026-10-14 (`transcript_stats.py --since
2026-10-14`, прогон 2026-10-22 ~07:44Z, `transcripts-*.json`): WSL x ITD - 5 сессий, Windows x buying - 100 (окно
растет с новыми сессиями; 2026-10-21 их было 70).

| Фаза | WSL x ITD: вызовов, медиана нижней границы, мс | Windows x buying: вызовов, медиана, мс |
|---|---|---|
| Bash Pre | 1990, 349 | 5403, 1917 |
| Bash Post | 1923, 234 | 5005, 1458 |
| Edit Pre | 217, 212 | 3499, 910 |
| Edit Post | 217, 220 | 3495, 1068 |
| Read Pre | 22, 140 | 1098, 1480 |
| Read Post | - (записей нет) | 2513, 1447 |

Реальные длительности отдельных хуков (медиана, число записей): WSL x ITD - `completion-gate.sh` 316 (1986),
`state-guard.sh` Pre 324 (1989), `completion-signals.sh` 229 (1923), `pii-egress-guard.sh` 586 (43); Windows x
buying - `completion-gate.sh` 1786 (5415), `state-guard.sh` Pre 1818 (5424), `completion-signals.sh` 1199 (4410),
`posttooluse.mjs` 1418 (5005), а хуки, которые пишут вывод редко, - около 9 с: `careful.sh` 9356 (755),
`pii-egress-guard.sh` на Bash 8707 (998), `check-dod-before-commit.sh` 9550 (793). В окне Windows есть и записи
хуков, снятых ADR-012 (`execution-trace.sh`, `check-tool-skill.sh`, `check-review-before-commit.sh`): окно по mtime
захватывает сессии, начатые до их снятия или в worktree со старыми регистрациями. Реальный вызов Bash на Windows x
buying платит хукам около 3.4 с и больше (сумма медиан нижних границ: 1.9 Pre + 1.5 Post), стенд - 1.8 с. Причина разницы не измерялась (кандидаты: работа хоста вокруг хуков, конкуренция с ним за
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
не считается второй раз). Событие - каждый промпт человека (0 байт, если хуки ничего не добавили) и каждый
служебный ввод (уведомление о задаче, прерывание), в который хук что-то добавил; записи UserPromptSubmit одного
ввода суммируются. Сессия - каждый просмотренный основной транскрипт, в том числе без внедренного текста; медиана по
событию берется по всем сессиям, с 0 там, где событие ничего не добавило. `transcript_stats.py`, то же окно, прогон
2026-10-22 08:24Z (`transcripts-*-a7.json`). Окно включает живую сессию замера и новые сессии buying, поэтому повтор
дает близкие, а не равные числа:

| | WSL x ITD | Windows x buying |
|---|---|---|
| UserPromptSubmit на событие, медиана (макс) | 397 Б (10728), 231 событие | 403 Б (38202), 1200 событий |
| На сессию, медиана, всего | 59865 Б (5 сессий) | 26809 Б (101 сессия) |
| На сессию по событиям, медианы: SessionStart / UserPromptSubmit / PreToolUse / PostToolUse | 8859 / 24806 / 11788 / 16526 | 4631 / 6613 / 4066 / 1832 |

## 5. Время session-save

От сообщения ассистента с вызовом Skill `session-save` до последнего сообщения ассистента перед следующим
вводом с текстом (`transcript_stats.py`, прогон 08:24Z): WSL x ITD - 2 прогона, 62 и 67 с (медиана 64); Windows x
buying - 91 прогон, медиана 154 с (2026-10-21: 63 прогона, медиана 155). Края метода: минимум 0 - вызов был последним
сообщением хода; максимум 34413 с - после session-save ход продолжал другую работу без нового промпта, поэтому
сравнивается медиана, а не максимум.

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

Доктор только читает и печатает проекты с находками (`--json`, поле `count` - число находок). Прогоны 2026-10-21 и
2026-10-22 (`doctor-*.json`) дали одинаковые числа. Установленная копия
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
