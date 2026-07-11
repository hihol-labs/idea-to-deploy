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
5. Commit → push (SSH работает стабильнее HTTPS) → PR → squash-merge.
   GitHub API (HTTPS) может моргать при VPN/прокси (fake-ip 198.18.x, TLS
   timeout) — merge/PR ретраить циклом с паузами; push по SSH проходит.
6. **Раскатка на ОБА инсталла** (изменения хуков/скиллов не активны, пока
   не синкнуты):
   ```bash
   bash scripts/sync-to-active.sh
   CLAUDE_HOME=/mnt/c/Users/<user>/.claude bash scripts/sync-to-active.sh
   ```
   Windows-таргет автодетектится по пути (v1.73.1), интерпретатор
   harvest'ится из существующего settings.json.
7. Смоук на живом харнесе: новые/изменённые хуки проверяются реальным
   tool-вызовом (Claude Code подхватывает регистрации горячо, рестарт для
   хуков не нужен — проверено v1.75–v1.78.1).

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

## Открытые кандидаты (следующие релизы)

Из финальной ACID-пересдачи 2026-07-11 (итог ≈8.9: A9/C9/I9/D8.5; оценщик:
«9.0+ достижим одним follow-up-PR по (а)+(б), дальше — убывающая отдача»):

- (а) state-guard: `rm` леджера невидим обоим слоям (deny-достойная операция
  под чужим локом проходит молча — топ-пробел); пачка soft-токенов с FP~0
  (`perl -i`, `sponge`, `install`, `rsync`, `Copy-Item`/`New-Item`,
  `python script.py` без `-c`); `git stash`/`git clean` в GIT_REWRITE_RE.
- (б) heartbeat лока и на shell-каналы (сейчас только Write/Edit — чисто
  Bash/PowerShell-сессия протухает свой лок за 10 мин, вторая сессия
  легитимно заберёт single-writer посреди работы первой).
- Осознанный tail-bound trade-off (документировать при касании): contradiction
  старше 512KB-хвоста events.jsonl пропускается молча (absence→WARNING
  деградирует, contradiction за окном — нет).

Закрытые: дрифт-гард run-all↔workflows (v1.79.1, нашёл 4 local-only гейта);
git-перезапись леджера — hard при явном пути + безусловная soft-ревалидация
GIT_REWRITE_RE (v1.80.0); POSIX flock → LOCK_NB с bounded-ретраями (v1.80.0);
bound на events.jsonl в реконсиляции + .gitignore dogfood-артефактов
(v1.80.1).
