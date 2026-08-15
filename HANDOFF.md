---
project: idea-to-deploy
stage: S9 — четыре харнес-фикса; U4 закрыт, U3 в работе, остались U2 → U1
from: сессия 2026-08-15 (исполнитель S9, часть 2)
to: следующая сессия-исполнитель S9
created: 2026-08-15
reason: приближение к порогу контекста на границе между юнитами
tags: [handoff, gpg-004-followups, s9, harness]
---

# HANDOFF — S9: U4 закрыт, U3 в работе, дальше U2 → U1

## 1. From → To

**From:** сессия 2026-08-15, часть 2. U4 доведён до конца полным маршрутом.
**To:** следующая сессия — маршрут U3, затем U2 и U1, один живой re-record,
публикация, общий релиз S8+S9.

## 2. Причина передачи

Порог контекста на чистой границе: юнит закрыт, дерево чистое, ничего не
висит в индексе. Работа НЕ заблокирована.

## 3. Текущее состояние — ФАКТЫ

- Ветка **`fix/s9-harness-debts`** от main `e3131c9`, **3 коммита**:
  - `39bfbf5` — evidence U4 (дерево `a0759746`);
  - `4191213` — ledger U4 (юнит → `verified`);
  - `f2638f2` — обновлённый этот пакет.
- Ветка **не запушена**.
- **U3 реализован, локально зелёный, НЕ закоммичен.** В рабочем дереве:
  `hooks/record-agent-skill.sh` (писатель подписывается
  `itd-record-agent-skill`), `hooks/completion-gate.sh` и
  `docs/templates/itd/itd_hygiene.py` (оба строгих оценщика выводят слой 0 из
  провенанс-проверки, пока политика не объявила его runtime-слоем),
  `tests/verify_completion_gate.py` 16→27 PASSED,
  `tests/verify_strict_completion_policy.py` 56→58 PASSED, оба мутационно
  доказаны. Плюс бухгалтерия: контракт `.itd-memory/contracts/S9-U3-LEDGER.md`,
  поправка зоны в `.itd/SCOPE_LOCK.md`, `BACKLOG` (пункт закрыт + два новых
  остатка), активация `S9-U3-LEDGER` с `riskTier` в `STATE.json`.
- Остался только маршрут U3 по рецепту из поля 5.
- `.itd/ACCEPTANCE_CONTRACT.json` → `activeFollowup.unitId = "S9"`,
  `in_progress`, riskTier **medium**, `rootCause` → контракт U3.

## 4. Финальные решения (уже приняты, не переоткрывать)

1. **Порядок U4 → U3 → U2 → U1** и один живой re-record в самом конце.
2. **Активация юнита едет в evidence-коммите, `verified` — в ledger-коммите.**
   Значит `.itd-memory/STATE.json` **входит в кандидата**.
3. **Коммит-гейт биндится к claim-id `<unit>:general-review`**, а не к голому
   `unitId`. На юнит нужны ДВЕ тройки квитанций.
4. **Машинный оракул гоняет `tests/run-all.sh --quick`, не полный**: полный
   агрегатор падает в изоляции семью суитами по окружению. Полный `run-all.sh`
   остаётся отдельной уликой на рабочем дереве.
5. **Обязателен `--input .itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256`**
   — без него `verify_independent_review_efficacy` падает в изоляции.
6. **`currentUnit` в `STATE.json` обязан нести `riskTier`.** `itd_unit_log.py
   activate` его не пишет (`skills/task/scripts/itd_unit_log.py:116`), а
   `detected_risk_tier` без него отдаёт `unknown` — и коммит-гейт отвергает
   квитанцию, отчеканенную как `medium`, с сообщением «нет успешного /review
   для exact current context». Проставляй руками ДО чеканки: это правка внутри
   кандидата, после неё все квитанции надо чеканить заново.
7. **Completion-гейт классифицирует прогон только по эху `EXIT: $?`.**
   `outcome_from` (`hooks/completion_lib.py:361-378`) берёт код из
   `EXIT: N`; без него зелёный прогон пишется как `outcome: unknown`, а
   красный от мутационного эксперимента чекера остаётся последним
   классифицированным L2-сигналом и вечно валит коммит. Перед коммитом
   прогони проверку **одиночной** командой вида
   `sh skills/_shared/itd_py.sh tests/<verifier>.py; echo "EXIT: $?"`.

## 5. Маршрут одного юнита — рецепт, проверенный на U4

Инвариант: **чеканить на том дереве, которое лежит в индексе прямо сейчас**,
при индекс == рабочее дерево. Сначала вся бухгалтерия, потом чеканка.

```bash
git write-tree                       # текущий кандидат; сверяй с ним всё ниже
```

1. Довести бухгалтерию (контракт юнита, SCOPE_LOCK при необходимости,
   BACKLOG, `STATE.json` с активацией И `riskTier`, HANDOFF).
2. Обе машинные квитанции — для `<unit>` и `<unit>:general-review`:

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

   (набор `--command` подгоняй под юнит: для U3 добавь оракулы completion,
   для U2 — `verify_gate_profile_doctor.py`, для U1 — `verify_free_reviewer_producer.py`.)
3. Свежий чекер другой модели (на U4 работал `claude-sonnet-5`, `--mode full`)
   по промпту `.itd-memory/verification-loop/prompts/<unit>-checker-prompt.md`;
   строку `Reviewed tree` обнови под текущее дерево. Чекер мутирует код и
   обязан восстановить его побайтово — после него сверь `git write-tree`.
4. `checker` ×2 → `adjudicate` ×2. Имена выходных файлов новые на каждый
   раунд: квитанции иммутабельны, перезапись отвергается.
5. `review_cache record --risk-tier medium --kind general --verdict PASSED
   --session <id> --verification-receipt <gr-adjudication>`; проверить
   так, как это делает хук:
   `cache_allows(Path.cwd())` без явного tier должен вернуть `True`.
6. Зелёный L2-сигнал одиночной командой с `echo "EXIT: $?"` (см. п. 4.7).
7. Evidence-коммит, затем **отдельный** ledger-коммит
   (`itd_unit_log.py verified <unit>` + правка `nextAction`).

## 6. Юниты (якоря)

| # | Долг | Якоря | Жжёт live-пин? |
|---|------|-------|----------------|
| U3 | completion-ledger schema — **реализован, ждёт маршрута** | писатель `hooks/record-agent-skill.sh` (подпись `itd-record-agent-skill`); оценщики `hooks/completion-gate.sh` (`signal_schema_error`) и `docs/templates/itd/itd_hygiene.py` (explicit-close). Леджер `.claude/completion/signals.jsonl` НЕ править — он улика. | да |
| U2 | doctor independence label | `skills/_shared/itd_gate_control.py:1492` (`validate_local_adjudication`, контракт `str \| None` ~1561), заглушка `tests/verify_gate_profile_doctor.py:201-262` | да |
| U1 | producer committed-head | `skills/_shared/itd_free_reviewer_producer.py` — `_staged_file_records()` ~681 и `git diff --cached` на ~974/979/1013; образец: `skills/_shared/itd_verification_loop.py:251-261, 1830-1855, 2131-2133` | да |

**U1 не может отревьюить сам себя** — маршрут поедет на копии продюсера,
снятой ДО фикса. Снимай свежую копию `_shared` после каждого изменения.

## 7. Блокеры и риски

> [!warning] Live-evidence пин сгорает от правок `skills/`, `agents/`, `hooks/`
> U3, U2, U1 попадают в `METHODOLOGY_TREE_ROOTS`. Один живой re-record —
> в самом конце, после последней правки в пиновой зоне, на чистом дереве.

> [!warning] Недетерминизм изолированного `quick`-агрегатора — НЕ объяснён
> На идентичном дереве `962f862c` три прогона зелёных, один красный.
> Записано в BACKLOG как открытый долг; красная квитанция не удалена.
> На дереве `a0759746` (U4) все четыре прогона были зелёными.

Прочие риски: сеть к GitHub API нестабильна (gh GraphQL → TLS handshake
timeout, REST работает); external-write гейт классифицирует по тексту команды —
такие файлы писать инструментом Write, не через heredoc.

## 8. После четырёх юнитов

Один живой re-record бенчмарка на чистом дереве, публикация через
`itd pr create` (прямой `git push` запрещён), общий релиз S8+S9 по
`docs/RELEASE_RUNBOOK.md`.

## 9. Первое действие

> [!todo] `git status --short` и `git log --oneline -3`. Если U3 ещё не
> закоммичен — довести бухгалтерию до состояния «описывает ветку как она
> есть», затем маршрут из поля 5 для claim-id `S9-U3-LEDGER` и
> `S9-U3-LEDGER:general-review`. Набор `--command` для машинной квитанции U3:
> `gate=sh skills/_shared/itd_py.sh tests/verify_completion_gate.py`,
> `strict=sh skills/_shared/itd_py.sh tests/verify_strict_completion_policy.py`,
> `quick=bash tests/run-all.sh --quick`.

---

Артефакты: `.itd/SCOPE_LOCK.md` · `.itd/ACCEPTANCE_CONTRACT.json` ·
`.itd-memory/contracts/S9-U4-PRCREATE.md` · [[STATE]] · [[BACKLOG]] ·
[[DECISIONS]] · [[FORBIDDEN_CHANGES]]
