# Release Runbook — как выпускается релиз методологии

> Появился по итогам упражнения «knowledge visibility gap» (2026-07-10):
> процедура релиза и её грабли жили в session-memory оператора, вне репо.
> Этот файл — экстернализация. Свежесть: сверен с практикой релизов
> v1.75.0–v1.78.1 (шесть релизов за один день, включая параллельные линии).

## Конвейер

1. **Свежий main ПЕРЕД веткой и ПЕРЕД бампом версии** — `git fetch origin
   main && git log origin/main -1`. Параллельные сессии выпускают релизы тем
   же днём: v1.77.0 был занят другой линией, пока готовился «наш v1.77.0» —
   релиз стал v1.78.0. Номер берётся от СВЕЖЕГО main, не от начала работы.
2. Ветка `feat/…` или `fix/…` → правки → тесты (`bash tests/run-all.sh`;
   кросс-платформенно — тот же набор на Windows-питоне, критично
   `PYTHONUTF8=0` для cp1251-класса багов).
3. **Ревью перед мультифайловым коммитом** — обязательный пол (/review или
   узкий code-reviewer-агент по диффу). Известный сбой: ревью-агент
   обрывается на финише без вердикта («finish-line interruption») —
   лечится resume'ом того же агента (SendMessage) с требованием
   контрактного финала (findings + json-блок); не перезапуском с нуля.
4. Версия: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`
   + бейджи `Version-X.Y.Z` в README.md и README.ru.md. CHANGELOG-entry
   сверху. Счётчики хуков/скиллов гейтятся тестами (meta_review M-C15,
   verify_gate_taxonomy, G-005) — при изменении числа хуков идти по их
   фейлам.
5. Commit → `itd pr create` (он же делает guarded push; прямой `git push`
   запрещён) → PR → squash-merge. GitHub API (HTTPS) может моргать при
   VPN/прокси (fake-ip 198.18.x, TLS timeout) — с LPD-002 R3 `itd pr create`
   и `itd gate` сами ретраят транспортные ошибки (<= 5 попыток, паузы
   15 -> 30 с) и не создают второй PR на ту же ветку; 401/403/422 не
   ретраятся. Если вернулся `UNAVAILABLE` с подсказкой «state may have
   applied» — состояние проверять по факту (`gh pr view <ветка>` или
   `gh api repos/<owner>/<repo>/pulls?head=<owner>:<ветка>`), а не по коду
   возврата: пуш мог пройти, PR мог создаться. Ручной цикл повторов больше
   не нужен.
5a. **Тег релиза — только через `gh release create` с полным SHA
   merge-коммита:**
   ```bash
   gh release create vX.Y.Z --target "$(git rev-parse <merge-sha>)" \
     --title "vX.Y.Z" --notes-file <notes>
   ```
   Короткий SHA в `--target` даёт `target_commitish is invalid`; прямой
   `git push origin vX.Y.Z` блокируется pre-push гейтом — это ожидаемо, тег
   не является отревьюенным кандидатом (LPD-002 R3, retro E9/P8).
6. **Раскатка на ОБА инсталла** (изменения хуков/скиллов не активны, пока
   не синкнуты):
   ```bash
   bash scripts/sync-to-active.sh
   CLAUDE_HOME=/mnt/c/Users/<user>/.claude bash scripts/sync-to-active.sh
   ```
   Windows-таргет автодетектится по пути (v1.73.1), интерпретатор
   harvest'ится из существующего settings.json.
   После синка source-копий обязательно переустановить глобальные `itd` и
   `pre-push` на КАЖДОМ нативном хосте — не запускать Windows installer из
   WSL и наоборот:
   ```bash
   # WSL
   python3 -I scripts/itd_install_cli.py --apply --replace-existing
   python3 -I scripts/itd_install_git_hooks.py --apply --replace-existing
   ```
   ```powershell
   # native Windows, из Windows source-копии релиза
   & $ITD_PYTHON -I scripts/itd_install_cli.py --apply --replace-existing
   & $ITD_PYTHON -I scripts/itd_install_git_hooks.py --apply --replace-existing
   ```
   Оба installer-а материализуют один закрытый runtime под host-data
   `.../ITD/runtime/<release>-<digest16>` (WSL:
   `~/.local/share/itd/runtime/...`), сверяют manifest и каждый SHA-256 и
   атомарно переключают wrappers на его `scripts/itd.py` /
   `scripts/itd_pre_push.py`. Старые content-addressed runtime-каталоги
   остаются rollback-артефактами; удалять их во время релиза нельзя.
   Закрытый inventory обязан включать и полный набор транзитивных path-loaded
   зависимостей exact-context (review-cache, review skill, оба rubric-файла);
   release-canary должен вычислять candidate context и запускать revalidation
   receipt из установленного runtime, а не только `--help`, импорт модуля и
   голый fail-closed pre-push.
7. Смоук на живом харнесе: новые/изменённые хуки проверяются реальным
   tool-вызовом (Claude Code подхватывает регистрации горячо, рестарт для
   хуков не нужен — проверено v1.75–v1.78.1).

## SCOPE_LOCK релизного и ledger-close юнита

Шаблоны `.itd/SCOPE_LOCK.md` для двух юнитов публикации. Корневой `HANDOFF.md`
не отслеживается git (`/HANDOFF.md` в `.gitignore`, HANDOFF-UNTRACKED-1): файл
внутри коммита не может записать ревью этого же коммита, и в REL-1.106.0 это
дало находки ревьюера в rel4, rel5 и pub3. Поэтому пакет передачи не входит в
Allowed Change Areas и не добавляется через `git add -f`; живое состояние
передачи — в памяти сессии и в `HANDOFF.md` рабочего дерева. Заменить
`X.Y.Z`, `REL-X.Y.Z` и список юнитов.

```markdown
# REL-X.Y.Z

## Current Task

- REL-X.Y.Z: release X.Y.Z ships <units>. The criterion and the verificationCommand live ONLY
  in `.itd-memory/GOAL.json`; contract and this file reference them and do not restate them.

## Allowed Change Areas

- The version files the unit command enumerates (manifests, READMEs, docs) - the version bump.
- `CHANGELOG.md` - one `## [X.Y.Z]` section right under `## [Unreleased]`.
- `tests/fixtures/live-model-evidence/` - live benchmark evidence re-recorded on the release tree.
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - harness
  projections and events.
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md`
  (this file) - records.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Skills, hooks, agents, scripts and tests beyond the version strings and the live evidence
  above; unit statuses by hand.
- Merge, tag, release and rollout - only on the owner's explicit command.

## Review Rule

A `/review` pass before the multi-file commit. If the diff touches an area outside allowed scope,
pause and reclassify the task before continuing.
```

```markdown
# REL-X.Y.Z ledger-close

## Current Task

- REL-X.Y.Z ledger-close: record the publication and rollout of release X.Y.Z, run the goal
  harness ОТК on this candidate, close the followup and the goal.

## Allowed Change Areas

- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status
  transitions only through the goal harness.
- `.itd/ACCEPTANCE_CONTRACT.json` - the followup moves to `closedFollowups` after the harness
  marks the unit verified.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd-memory/host-inputs/REL-X.Y.Z/` (git-ignored, host-owned) - native canaries and
  `INSTALLED.json`.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Any change to skills, hooks, agents, scripts, tests or the legs of the unit command.
- Editing unit statuses by hand; deleting runtime directories of earlier releases.
- Merge and push - only on the owner's explicit command.

## Review Rule

A `/review` pass before the multi-file commit. If the diff touches an area outside allowed scope,
pause and reclassify the task before continuing.
```

## Грабли (проверено кровью)

- **sed/heredoc с backticks через двойной шелл** (Git Bash → `wsl bash -lc
  "…"`) исполняет backticks как команды и молча портит файлы. Правки строк
  с backticks — только Edit-тулом или python-скриптом, записанным в файл.
- **Вывод хуков — только ASCII-safe JSON** (`ensure_ascii=True`): на
  Windows-инсталле без `-X utf8` пайп хука может быть cp1251 — эмодзи в
  выводе молча гасит хук (exit 0 без вывода). Тест-имена в verify_* — тоже
  только ASCII (windows-verify гоняет PYTHONUTF8=0).
- **`python`/`python3` на Windows может быть Store-заглушкой** — валидируй
  исполнением (`python -c "print(1)"`), в скриптах — фолбэк `py -3`.
- **Раскладка `~/.claude/projects/`**: имя каталога = путь проекта, где
  КАЖДЫЙ не-alnum символ заменён на `-` (включая `_` и не-ASCII; на Windows
  без ведущего дефиса). Локаторы memory-dir обязаны использовать этот
  munging (см. `find_project_memory_dir` в pre-flight/state-guard, v1.76.1).
- **Бамп версии в дереве против инсталлового валидатора — ЗАКРЫТО (LPD-002 R2).**
  Симптом: релизный коммит с пройденным `/review` ложно блокировался
  `check-review-before-commit`. Корень: гейт грузил `itd_review_cache.py` из
  инсталла, у которого `methodologyVersion` читается из ИНСТАЛЛОВОГО
  `.claude-plugin/plugin.json`, а квитанцию `/review` писал валидатор из репо —
  с версией дерева; на релизе версии по построению разные, отсюда промах кэша.
  Теперь гейт грузит валидатор ИЗ РЕПО для того checkout'а, из которого собран
  инсталл: `scripts/sync-to-active.sh` записывает `~/.claude/.itd-install-source.json`,
  и только этот путь получает repo-first. **Предусловие: хотя бы один прогон
  `bash scripts/sync-to-active.sh` после обновления** — без записи провенанса
  поведение прежнее (инсталловый валидатор). Имя плагина в манифесте рабочего
  каталога само по себе НЕ является пропуском: оно самопровозглашённое. Замер до починки: ~25 мин и два лишних перечеканенных
  маршрута на релиз v1.98.0.

- **Global wrapper указывает на development checkout — ЗАКРЫТО (PRG-002).**
  Симптом: изменение/перемещение канонического checkout меняло или ломало уже
  установленный `itd`/`pre-push`; Windows wrapper вдобавок читал WSL checkout
  через UNC. Теперь wrappers исполняют только общий атомарно установленный
  content-addressed runtime с закрытым inventory и `-I -B`. Existing runtime
  с missing/extra/changed bytes блокирует reinstall и не чинится поверх;
  источник checkout в wrapper не сохраняется.

- **Транспортный флейк GitHub как терминальный отказ — ЗАКРЫТО (LPD-002 R3).**
  Симптом (публикация R2, 2026-08-18): `itd pr create` дважды вернул
  `GitHub PR lookup failed` на TLS-таймаутах к `api.github.com`, причём пуш
  уже прошёл, а PR не создан; один отказ пришёл как `command unavailable: git`
  при сетевой причине (таймаут `git ls-remote`). Теперь: read-only вызовы
  (`gh pr view`, `gh api`, `git ls-remote`) идут через bounded retry по
  закрытому словарю транспортных маркеров; `gh pr create` перед КАЖДОЙ
  попыткой проверяет существующий PR ветки; 401/403/422 и любая
  неклассифицированная ошибка не ретраятся; таймаут подпроцесса называется
  `<cmd> timed out after <N>s`; исчерпание — typed `UNAVAILABLE` с подсказкой
  перепроверить `gh pr view`. Мутации (`git push`, ruleset POST) по-прежнему
  не ретраятся — у них нет проверки идемпотентности.

## Открытые кандидаты (следующие релизы)

Из финальной ACID-пересдачи 2026-07-11 (итог ≈8.9: A9/C9/I9/D8.5; оценщик:
«9.0+ достижим одним follow-up-PR по (а)+(б), дальше — убывающая отдача»):

- Осознанный tail-bound trade-off (документировать при касании): contradiction
  старше 512KB-хвоста events.jsonl пропускается молча (absence→WARNING
  деградирует, contradiction за окном — нет).

Закрытые: дрифт-гард run-all↔workflows (v1.79.1, нашёл 4 local-only гейта);
git-перезапись леджера — hard при явном пути + безусловная soft-ревалидация
GIT_REWRITE_RE (v1.80.0); POSIX flock → LOCK_NB с bounded-ретраями (v1.80.0);
bound на events.jsonl в реконсиляции + .gitignore dogfood-артефактов
(v1.80.1); rm-класс леджера (hard) + пачка soft-токенов + git stash/clean +
heartbeat на shell-каналах (v1.81.0 — кандидаты (а)+(б) финальной пересдачи).
