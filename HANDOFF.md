---
project: idea-to-deploy
stage: S9 — четыре харнес-фикса; U4 доведён до готового к коммиту кандидата
from: сессия 2026-08-15 (исполнитель S9, часть 1)
to: свежая сессия-исполнитель S9 (продолжение)
created: 2026-08-15
reason: исчерпание контекстного окна на середине маршрута U4
tags: [handoff, gpg-004-followups, s9, harness]
---

# HANDOFF — S9: U4 готов, остались U3 → U2 → U1

## 1. From → To

**From:** сессия 2026-08-15, исполнитель S9 (часть 1). Ветка создана, U4
реализован и отревьюирован, коммита ещё НЕТ.
**To:** свежая сессия — доделать коммит U4, затем U3 → U2 → U1, один живой
re-record, публикация.

## 2. Причина передачи

Исчерпание контекста. Работа НЕ заблокирована по существу: U4 машинно зелёный,
последний фикс по находке ревьюера внесён, требуется только перечеканка
квитанций на финальном дереве и коммит.

## 3. Текущее состояние — ФАКТЫ

- Ветка: **`fix/s9-harness-debts`** от main `e3131c9`. Коммитов на ветке **0**.
- В индексе (staged) лежит кандидат U4, 8 файлов:
  `scripts/itd.py`, `tests/verify_itd_cli.py`, `BACKLOG.md`,
  `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json`,
  `.itd-memory/contracts/S9-U4-PRCREATE.md`, `.itd-memory/STATE.json`,
  `HANDOFF.md`.
- `.itd/ACCEPTANCE_CONTRACT.json` → `activeFollowup.unitId = "S9"`,
  `status = in_progress`, riskTier **medium**, rootCause →
  `.itd-memory/contracts/S9-U4-PRCREATE.md`.
- `.itd-memory/STATE.json` → `currentUnit = S9-U4-PRCREATE / in_progress`
  (активация едет в evidence-коммите — см. поле 4, п. 2).
- `.itd/SCOPE_LOCK.md` **переписан под S9** целиком: состав ветки, порядок
  юнитов, зона live-evidence, запреты.
- Всё изменённое застейджено, рабочее дерево совпадает с индексом. Первое, что
  делает следующий актор, — `git status --short` и `git write-tree`; дерево,
  которое он там увидит, и есть кандидат. Номер дерева в этом пакете намеренно
  не зафиксирован (см. урок в поле 5).

## 4. Финальные решения (уже приняты, не переоткрывать)

1. **Порядок U4 → U3 → U2 → U1** и один живой re-record в самом конце.
2. **Активация юнита едет в evidence-коммите, `verified` — в ledger-коммите.**
   Проверено на истории ветки S8: `40a1bc0` (evidence) ставит
   `id: S8-U4-CRLF / in_progress`, следующий `4dabc62` (ledger) переводит в
   `verified`. Значит `.itd-memory/STATE.json` **входит в кандидата** — иначе
   `review_cache` не резолвит юнит, а грязное дерево ломает биндинг.
3. **Коммит-гейт биндится к claim-id `<unit>:general-review`**, а не к голому
   `unitId`. Поэтому на юнит нужны ДВЕ тройки квитанций: `S9-U4-PRCREATE`
   (существо) и `S9-U4-PRCREATE:general-review` (то, что открывает гейт).
   Отсюда парные `-gr-*` файлы в S7/S8.
4. **Машинный оракул гоняет `tests/run-all.sh --quick`, не полный**: изоляция
   `git clone --shared` + `read-tree` не содержит host-owned входов, полный
   агрегатор падает там семью суитами по окружению. Полный `run-all.sh`
   остаётся отдельной уликой на рабочем дереве (прогнан, `DONE fails:none`).
5. **Обязателен `--input .itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256`**
   — без него `verify_independent_review_efficacy` падает в изоляции.
6. **`currentUnit` в `STATE.json` обязан нести `riskTier`.** `itd_unit_log.py
   activate` его не пишет (`skills/task/scripts/itd_unit_log.py:116`), а
   `detected_risk_tier` без него отдаёт `unknown` — и коммит-гейт отвергает
   квитанцию, отчеканенную как `medium`, с сообщением «нет успешного /review
   для exact current context». Прецедент S8 (`40a1bc0`) поле содержит.
   Проставляй его руками ДО чеканки: это правка внутри кандидата, после неё
   все квитанции надо чеканить заново. Каждый следующий юнит S9 наступит на
   это снова.

## 5. Что сделано по U4 — с уликами

**Root cause.** `create_draft_pr` (`scripts/itd.py`) выводил решение о пуше из
**существования PR**, а не из **состояния удалённого рефа**: при `pr_view →
None` он всегда пушил, даже когда удалённая голова уже равна локальной. No-op
пуш даёт пустой pre-push update stream, который `parse_updates`
(`scripts/itd_pre_push.py:55`) отвергает fail-closed.

**Фикс.** Новый `remote_branch_head(root, branch, timeout=120)` резолвит голову
через `git ls-remote --heads origin refs/heads/<branch>`; ветка `value is None`
пропускает пуш, если она уже равна локальному `HEAD`. `parse_updates` НЕ
ослаблен; `pr_view` НЕ переставлен перед пушем (обоснование — в контракте,
раздел Exclusions).

**Улики (не привязаны к раунду):**
- `tests/verify_itd_cli.py`: 75 checks PASSED (было 63). RED-first подтверждён
  (`AttributeError: ... does not have the attribute 'remote_branch_head'`).
- Мутация: подмена условия на `if False` валит ровно новый кейс
  `synced remote without PR skips the empty-stream push`; восстановление —
  снова зелёный. Ревьюер воспроизвёл мутацию независимо.
- `verify_git_gate_hooks.py` 30 PASSED, `verify_gate_registry_profiles.py`
  24 PASSED, полный `bash tests/run-all.sh` на рабочем дереве →
  `DONE fails:none`.
- Машинные квитанции чеканились на каждом дереве-кандидате; актуальные лежат
  в `.itd-memory/verification-loop/receipts/<digest>/`, где `<digest>` отвечает
  ТЕКУЩЕМУ `git write-tree`. Ищи по `candidate.reviewedTree`, а не по имени.
- Свежие чекеры `claude-sonnet-5`, `--mode full`, четыре раунда. Существо кода
  прошло с первого раза (**PASSED, 0 findings** на дереве `562cc45d`). Раунды
  r2/r3/r4 нашли по одной ошибке ОДНОГО класса — устаревшая бухгалтерия внутри
  кандидата: `HANDOFF.md` описывал S9 как не начатый (r2), `STATE.json.nextAction`
  говорил «Not started» (r3), затем `HANDOFF.md` §5/§6/§9 описывал состояние
  двух раундов назад (r4). Все три закрыты. Отчёты — `reports/S9-U4-PRCREATE-checker-report*.md`.

> [!important] Устойчивый урок этого юнита
> Кандидат содержит собственный контекст-пакет, поэтому **любая правка
> бухгалтерии меняет дерево и обесценивает квитанции**. Не описывай в пакете
> «что осталось» в терминах конкретного дерева или номера раунда — иначе текст
> протухает ровно тем действием, которым ты его чинишь. Порядок, который
> сходится: сначала довести ВСЮ бухгалтерию до состояния «описывает ветку как
> она есть», и только потом чеканить квитанции и звать чекера.

## 6. Что осталось по U4

Существо готово; открыт только маршрут. Инвариант: **чеканить на том дереве,
которое лежит в индексе прямо сейчас**, при индекс == рабочее дерево.

```bash
git write-tree                       # текущий кандидат; сверяй с ним всё ниже
```

Для каждого из двух claim-id — `S9-U4-PRCREATE` и
`S9-U4-PRCREATE:general-review`:

```bash
sh skills/_shared/itd_py.sh skills/_shared/itd_verification_loop.py machine \
  --unit-id "<claim-id>" --risk-tier medium \
  --command "cli=sh skills/_shared/itd_py.sh tests/verify_itd_cli.py" \
  --command "hooks=sh skills/_shared/itd_py.sh tests/verify_git_gate_hooks.py" \
  --command "profiles=sh skills/_shared/itd_py.sh tests/verify_gate_registry_profiles.py" \
  --command "quick=bash tests/run-all.sh --quick" \
  --input .itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256 \
  --timeout 1800
```

Затем свежий чекер другой модели по промпту
`.itd-memory/verification-loop/prompts/S9-U4-PRCREATE-checker-prompt.md`
(обнови в нём строку `Reviewed tree` под текущее дерево), затем `checker` ×2,
`adjudicate` ×2 и

```bash
python3 skills/review/scripts/itd_review_cache.py record --risk-tier medium \
  --kind general --verdict PASSED --session <session-id> \
  --verification-receipt .itd-memory/verification-loop/S9-U4-PRCREATE-gr-adjudication.json
```

и коммит `fix(transport): itd pr create must not issue a no-op push`.
**Ledger-коммит отдельный**, следом: `itd_unit_log.py verified S9-U4-PRCREATE`
+ `STATE.json`.

`checker`/`adjudicate`/`record` требуют, чтобы рабочее дерево совпадало с
индексом — держи его чистым на этих шагах.

## 7. Оставшиеся юниты (якоря — прежние)

| # | Долг | Якоря | Жжёт live-пин? |
|---|------|-------|----------------|
| U3 | completion-ledger schema | писатель `hooks/record-agent-skill.sh:95-106` → `hooks/completion_lib.py:637` (`append_signal` не ставит `producer`, ср. `hooks/completion-signals.sh:94`); оценщик `hooks/completion-gate.sh:287-296` (`signal_schema_error` валит строку). Починить писателя И научить оценщика пропускать layer-0 telemetry, а не падать закрыто. Конкретная строка: `.claude/completion/signals.jsonl:1130`. Леджер НЕ править. | да |
| U2 | doctor independence label | `skills/_shared/itd_gate_control.py:1492` (`validate_local_adjudication`, контракт `str \| None` ~1561), заглушка `tests/verify_gate_profile_doctor.py:201-262` | да |
| U1 | producer committed-head | `skills/_shared/itd_free_reviewer_producer.py` — `_staged_file_records()` ~681 и `git diff --cached` на ~974/979/1013; образец: `skills/_shared/itd_verification_loop.py:251-261, 1830-1855, 2131-2133` | да |

**U1 не может отревьюить сам себя** — маршрут поедет на копии продюсера,
снятой ДО фикса. Снимай свежую копию `_shared` после каждого изменения.

## 8. Блокеры и риски

> [!warning] Live-evidence пин сгорает от правок `skills/`, `agents/`, `hooks/`
> U3, U2, U1 попадают в `METHODOLOGY_TREE_ROOTS`. Один живой re-record —
> в самом конце, после последней правки в пиновой зоне, на чистом дереве.

> [!warning] Недетерминизм изолированного `quick`-агрегатора — НЕ объяснён
> На идентичном дереве `962f862c` с тем же `--input`: три прогона зелёных,
> один красный (`quick` exit 1) — квитанция
> `.itd-memory/verification-loop/receipts/a1770aa1284c11fa/S9-U4-PRCREATE-general-review-machine-fe28e0ca6cf6c519.json`
> против зелёных `1c9a2c1ea68e118c` и `40bc24b82d532974`. Квитанция хранит
> только хеши, поэтому имя упавшей суиты неизвестно. Ручная репродукция в
> `git clone --shared` + `read-tree` показала только детерминированный отказ
> `verify_independent_review_efficacy (host-owned efficacy keyring pin is not
> provisioned)` — то есть подозрение на гонку в провижининге declared-input.
> Записано в BACKLOG как открытый долг; **красная квитанция не удалена**.

Прочие риски: сеть к GitHub API нестабильна (gh GraphQL → TLS handshake
timeout, REST работает); external-write гейт классифицирует по тексту команды —
такие файлы писать инструментом Write, не через heredoc.

## 9. Первое действие

> [!todo] Проверь, что вся бухгалтерия в кандидате описывает ветку как она
> есть (это единственный класс находок, который тут всплывал). Затем — поле 6:
> обе машинные квитанции, свежий чекер, adjudicate ×2, `review_cache record`,
> evidence-коммит U4, отдельный ledger-коммит. Дальше U3.

---

Артефакты: `.itd/SCOPE_LOCK.md` · `.itd/ACCEPTANCE_CONTRACT.json` ·
`.itd-memory/contracts/S9-U4-PRCREATE.md` · [[STATE]] · [[BACKLOG]] ·
[[DECISIONS]] · [[FORBIDDEN_CHANGES]]
