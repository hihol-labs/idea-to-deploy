---
project: idea-to-deploy
stage: VERIFY
unit: REL-1.106.0
riskTier: high
branch: chore/release-1.106.0
base: 2a1ea19
from: release-prep session 2026-09-27 (Claude Opus 5.5, canonical checkout)
to: next release-route actor (fresh session or post-compaction continuation, same owner)
date: 2026-09-27
---

# HANDOFF - REL-1.106.0 (указатель)

Этот файл - только указатель и журнал чекпоинтов. Он не пересказывает ни критерий, ни
маршрут: пересказ устаревал с каждым раундом ревью и дал стоп-правило `REDESIGN_OR_DISCARD`
(решение владельца 2026-09-27 - сузить файл до указателя, DECISIONS 2026-09-27).

## Источники истины

- Критерий и команда проверки юнита - `.itd-memory/GOAL.json` (юнит `REL-1.106.0`).
- Что разрешено, что обязательно до коммита, что запрещено, объявленные пределы -
  `.itd/SCOPE_LOCK.md`.
- Механика релиза (ветка, бамп, PR, тег, раскатка) - `docs/RELEASE_RUNBOOK.md`.
- Решения юнита - `.itd/DECISIONS.md` (записи с `REL-1.106.0` в заголовке).
- Скрипты маршрута - `.itd-memory/verification-loop/REL-1.106.0-*.py` и `*.sh` (git-ignored,
  локально; назначение и вызов - в docstring или шапке-комментарии каждого).

## Первое действие

Прочитать последнюю запись «Чекпоинтов» и раздел Required в `.itd/SCOPE_LOCK.md`; продолжить
с первого требования, для которого в чекпоинтах нет подтверждения на текущем staged-дереве
(`git write-tree`). Egress-шаги (push/PR, merge, тег/релиз, раскатка на Windows) - только по
явной команде владельца, каждый отдельно.

## Чекпоинты

Записи датированы и не переписываются задним числом; «Дальше» в каждой - план на момент
записи. Метки фаз из прежней редакции файла: P0 - подготовка кандидата, P1 - live re-record,
P2 - ревью до коммита.

- 2026-09-27 P0: ветка `chore/release-1.106.0` @ `2a1ea19`; REL-1.106.0 активирован харнесом;
  бамп + CHANGELOG + SCOPE_LOCK + строки приемки + followup + BACKLOG + DECISIONS; поправка
  команды (24/0); authority `REL1106-0a60e71e-a1` parity 0; всё в индексе. Дальше: P1.
- 2026-09-27 P1: re-record `a1` - `PASS live-model: fixture-03-cli-tool ->
  20260926T213612Z-b152bdfe`, recorder exit 0; `latest.json` и `runs/20260926T213612Z-b152bdfe/`
  скопированы в кандидат (байт-идентичны worktree), worktree рекордера удален. Пин
  `verify_live_model_benchmark.py --require-evidence` на чистой материализации staged-дерева
  `3115acff` (`REL-1.106.0-pin-check.sh p1`): 154 passed, 0 failed. В рабочем чекауте до коммита
  проверка `dirty-state digest` красная по построению (кандидат в индексе).
- 2026-09-27 /review (code-reviewer): BLOCKED - 1 important (CHANGELOG: #311 якобы не меняет
  контрактов, а добавляет строки G-005 в ACCEPTANCE_CONTRACT) + 2 minor (#303 правит и записи
  юнита; сдвинутые ссылки на строки `itd_goal_verify.py` в BACKLOG P2 2026-09-27). Все три
  исправлены. Дальше: захват зеркала `rel1`, дельта-проверка ревьюера, машинный маршрут.
- 2026-09-27 P2 на дереве `216c480c`: дельта `/review` PASSED (0 находок). Захват `rel1` NOT_READY
  - `DONE fails: verify_adjudication_channel` (`receipt belongs to another unit`; флейк BACKLOG P1
  2026-09-11, обратный шаг часов WSL2 и выбор квитанции по `st_mtime`), отдельно сьют зеленый
  дважды (65/0). Захват `rel2` READY (exit 0, `DONE fails:none`); машинные квитанции `rel2`
  (9 оракулов) и general `rel2` PASSED. Sol `rel2` (первый раунд gpt-5.6-sol) BLOCKED: 2 находки
  (каждая дважды) - evidence строки версии называла подсчет строк подсчетом вхождений (в бейджах
  README версия дважды на строке); `STATE.nextAction` велел доделать уже сделанный re-record.
  Обе исправлены. Дальше: захват `rel3` -> машинные `rel3` -> Sol `rel3`.
- 2026-09-27 P2 на дереве `fabcf137`: цепочка `rel3` - захват READY (exit 0, `DONE fails:none`),
  машинная (9/9 exit 0) и general PASSED; Sol `rel3` BLOCKED: 1 находка (дважды) - раздел 3
  HANDOFF называл строку `-2-mirror` pending. Исправлено; разделы 3 и 5 переписаны без
  утверждений, зависящих от раунда (метка и дерево - только в чекпоинтах). Дальше: цепочка `rel4`.
- 2026-09-27 P2 на дереве `1d949045`: цепочка `rel4` - захват READY, машинная и general PASSED;
  Sol `rel4` BLOCKED: 1 находка (дважды) - переписанный в `rel3` маршрут P2 потерял шаг
  `/review`, раздел 3 не фиксировал пройденный `/review`. Исправлено (шаг и состояние
  возвращены). Дальше: дельта-`/review` и цепочка `rel5`.
- 2026-09-27 P2 на дереве `4d919b0a`: дельта-`/review` BLOCKED - 2 important (фраза «пол перед
  коммитом» прочитана как обрубок; `STATE.nextAction` не называл дельта-`/review`). Цепочка
  `rel5` - захват READY, машинная и general PASSED; Sol `rel5` BLOCKED: 1 находка high (дважды) -
  SCOPE_LOCK и HANDOFF утверждали запись live-evidence «на точном staged-дереве», а привязка на
  деле - контентный пин (DECISIONS 2026-09-22). Стоп-правило (`scripts/itd_stop_rule.py`, история
  `REL-1.106.0-stop-history-rel2-rel5.json`): `REDESIGN_OR_DISCARD` на `rel5` - механизм
  `HANDOFF.md::specification-compliance` в `rel4` и `rel5`. Решение владельца: переделать форму.
  Сделано: HANDOFF сужен до указателя, SCOPE_LOCK называет контракт контентного пина и
  дельта-`/review`, `STATE.nextAction` исправлен. Дальше: пин-чек и дельта-`/review` на новом
  дереве, затем один раунд Sol `rel6`.
- 2026-09-27 на дереве `6aa9a7bc`: пин-чек `p2` 154/0; цепочка `rel6` - захват READY, машинная и
  general PASSED, Sol `rel6` PASSED (0 находок, 0 unverified). Дельта-`/review` (opus) BLOCKED:
  1 important - последняя нога команды гоняла верификатор live-evidence без `--require-evidence`,
  а SCOPE_LOCK утверждал обратное; 3 minor. Решение владельца: добавить флаги CI в ногу. Сделано
  (DECISIONS 2026-09-27, RED/GREEN на дереве `6be6ba05`), SCOPE_LOCK и HANDOFF поправлены.
  Дальше: пин-чек, дельта-`/review` и цепочка `rel7` на новом дереве.
