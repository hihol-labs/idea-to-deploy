---
project: idea-to-deploy
stage: S9 — четыре харнес-фикса; U4, U3 и U2 закрыты, U1 в работе
from: сессия 2026-08-15 (исполнитель S9, часть 2)
to: следующая сессия-исполнитель S9
created: 2026-08-15
reason: приближение к порогу контекста на границе между юнитами
tags: [handoff, gpg-004-followups, s9, harness]
---

# HANDOFF — S9: U4, U3 и U2 закрыты, U1 в работе

## 1. From → To

**From:** сессия 2026-08-15, часть 2. U4, U3 и U2 доведены до конца полным
маршрутом.
**To:** следующая сессия — маршрут U1, один живой re-record, публикация,
общий релиз S8+S9.

## 2. Причина передачи

Порог контекста на чистой границе: юнит закрыт, дерево чистое, ничего не
висит в индексе. Работа НЕ заблокирована.

## 3. Текущее состояние — ФАКТЫ

- Ветка **`fix/s9-harness-debts`** от main `e3131c9`, **8 коммитов**:
  `39bfbf5`+`4191213` (U4, дерево `a0759746`) · `f2638f2` пакет ·
  `57252a0`+`0d6f013` (U3, дерево `2d6a4f47`) · `0ac7c80` пакет ·
  `3df0309`+`e56284e` (U2, дерево `c08a4822`).
- Ветка **не запушена**.
- **U1 реализован, локально зелёный, НЕ закоммичен.** В рабочем дереве:
  `skills/_shared/itd_free_reviewer_producer.py` (`freeze_packet` принимает
  `candidate_mode`; committed-head резолвит родителя из
  `git rev-list --parents -n 1 HEAD`, отвергает не-single-parent, требует
  индекс == `HEAD^{tree}`; CLI-флаг `review --candidate-mode`),
  `tests/verify_free_reviewer_producer.py` 174→184 PASSED
  (`liveExternalCalls: 0`), два мутационных доказательства. Плюс бухгалтерия:
  контракт `.itd-memory/contracts/S9-U1-COMMITTED-HEAD.md`, BACKLOG (пункт
  закрыт), активация `S9-U1-COMMITTED-HEAD` с `riskTier`, `rootCause` в
  acceptance. `.itd/SCOPE_LOCK.md` уже объявлял эту зону.
- Остался маршрут U1 по рецепту из поля 5. Набор `--command` для машинной
  квитанции: `producer=sh skills/_shared/itd_py.sh
  tests/verify_free_reviewer_producer.py`, `quick=bash tests/run-all.sh --quick`.
  Маршрут U1 НЕ использует сам продюсер (машинные оракулы + чекер-субагент),
  поэтому «продюсер не ревьюит сам себя» соблюдено по построению.
- `.itd/ACCEPTANCE_CONTRACT.json` → `activeFollowup.unitId = "S9"`,
  `in_progress`, riskTier **medium**; `rootCause` указывает на контракт
  активного юнита.
- **Live-evidence пин сожжён** правками `hooks/` (U3) и `skills/` (U2, U1).
  Один живой re-record — после закрытия U1, на чистом дереве.

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
7. **Completion-гейт классифицирует прогон только по эху `EXIT: $?`, и
   вердикт берёт ПОСЛЕДНИЙ прогон на строку команды.** `outcome_from`
   (`hooks/completion_lib.py:361-378`) берёт код из `EXIT: N`; без него зелёный
   прогон пишется как `outcome: unknown`. Поэтому перед коммитом гоняй проверку
   **одиночной** командой вида
   `sh skills/_shared/itd_py.sh tests/<verifier>.py; echo "EXIT: $?"`.
   Хуже другое: независимый чекер восстанавливает мутированные файлы уникальной
   составной командой, вывод которой текстовая эвристика читает как провал —
   а «латест-на-команду» означает, что ЭТУ строку нельзя перепрогнать зелёной
   никогда. На U3 это стоило штатного аудируемого `COMPLETION_BYPASS: <причина>`
   в description коммит-вызова (запись легла в `.itd-memory/events.jsonl`).
   На U2 повторилось один в один. Ожидай того же на U1; честный выход —
   именно аудируемый обход с точной причиной, не отключение гейта. Долг
   записан в BACKLOG.

## 5. Маршрут одного юнита — рецепт, проверенный на U4, U3 и U2

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

| # | Долг | Якоря | Статус |
|---|------|-------|--------|
| U4 | `itd pr create` no-op push | `scripts/itd.py` `remote_branch_head` | **verified** (`39bfbf5`/`4191213`) |
| U3 | completion-ledger schema | писатель `hooks/record-agent-skill.sh`; оценщики `hooks/completion-gate.sh` и `docs/templates/itd/itd_hygiene.py` | **verified** (`57252a0`/`0d6f013`) |
| U2 | doctor independence label | `skills/_shared/itd_gate_control.py`, `tests/verify_gate_profile_doctor.py` | **verified** (`3df0309`/`e56284e`) |
| U1 | producer committed-head — **реализован, ждёт маршрута** | `skills/_shared/itd_free_reviewer_producer.py` (`freeze_packet` + CLI `--candidate-mode`), `tests/verify_free_reviewer_producer.py` | открыт |

**U1 не ревьюит сам себя по построению**: его маршрут — изолированные
машинные оракулы плюс свежий чекер-субагент другой модели; ни один из них не
загружает `itd_free_reviewer_producer.py` в роли ревьюера.

## 6b. ЗАКРЫТО: три efficacy-ноги перечеканены

U1 обесценил подписанные ноги (`producerSha256` биндит точные байты продюсера)
— все три перечеканены живыми прогонами на финальном дереве и лежат в
кандидате. Итог верификатора: `status: PASSED`, `hostParityVerified: true`,
`cleanFalseBlockRate` 0.0 на всех ногах, обнаружение 1.0; полный `run-all` →
`DONE fails:none`.

Как это было сделано (для следующей правки продюсера — повторится один в один):

- **WSL-ноги** (`wsl.json`, `u12-cross-vendor-wsl.json`) — раннер
  `tests/run-independent-review-efficacy.py` из WSL, ключ
  `…-20260803.key`, `--key-id gpg003-local-producer-20260803`, ревьюер
  `gpt-5.6-sol`, `--proxy-sha256 01ba4719…` (= sha256 от `\n`, прямой
  транспорт), maker `gpt-5.6-terra`/`openai-subscription` и
  `claude-opus-5`/`anthropic-subscription` соответственно.
- **Windows-нога** — тем же раннером, но через WSL-interop: PowerShell полным
  путём `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`
  (голого `powershell.exe` в PATH нет), `py -3` против UNC
  `\\wsl.localhost\Ubuntu-24.04\home\hihol\projects\idea-to-deploy`,
  ключ `…-20260803.windows.key` (DPAPI, расшифровывается под тем же
  пользователем). Отдельный git-чекаут на Windows НЕ нужен.
- **Пины транспорта разъехались** и это законно: проверено по коду —
  `verify_independent_review_efficacy` требует от `transportExecutableSha256`
  только корректный формат, конкретное значение не пинится. Ноги перечеканены
  на текущих бинарях (WSL `37e6f595…`, Windows вендорный `F29F6093…`), смена
  версии честно записана в конверт.
- **Раунд 1 WSL-ноги был честно красный** (`cleanFalseBlockRate 0.25`:
  same-vendor ревьюер вернул `PASSED_WITH_WARNINGS` с одним `unverified` на
  чистом кейсе — метрика засчитывает чистый кейс только при PASSED с пустыми
  `findings` И `unverified`). Израсходован разрешённый пользователем ОДИН
  повтор; артефакты раунда 1 сохранены в
  `.itd-memory/efficacy-evidence/s9-round1/`, прежние ноги — в `s9-pre-u1/`.
- **Транспорт рвался трижды** (`event stream transport is unavailable`) — один
  раз на Windows, дважды на одном кейсе в WSL. Возобновление с чекпоинта —
  штатная механика (`.itd/GPG-004_A16_TRANSPORT.md`), качественный повтор она
  НЕ расходует.

Оба раунда журналированы в `.itd/DECISIONS.md`.

**Порядок остатка S9:** маршрут U1 → evidence- и ledger-коммиты U1 → один
живой re-record бенчмарка на чистом дереве → публикация через `itd pr create`
→ релиз S8+S9.

## 6c. ОТКРЫТО: публикации нужен mandatory keyless route (одна команда)

Сделано и лежит готовым: claim `S9-EVIDENCE` открыт, обе машинные квитанции
отчеканены на committed-head (`receipts/bcd19b10edf85776/`), свежий чекер
`claude-sonnet-5` вернул PASSED 0 findings по всей ветке, обе adjudication —
PASSED (`S9-EVIDENCE-adjudication.json`, `S9-EVIDENCE-gr-adjudication.json`).

**Но этого НЕ хватает, и это не дефект.** Прогон валидатора ровно так, как его
зовёт `profile_doctor_entry`, даёт точную причину:

```json
{"why": "mandatory keyless route evidence is missing",
 "fix": "Run the shared fresh opposite-GPT producer and bind its signed
         phase-one receipt."}
```

То есть публикационный гейт принимает НЕ claude-чекера (им закрывались юниты),
а **общий свежий opposite-GPT продюсер** — `gpt-5.6-terra` через codex, с
подписанной phase-one квитанцией. Прежняя запись в этом поле угадывала иначе;
проверено исполнением, а не рассуждением.

Второй факт из того же прогона: реестр `~/.config/itd/gates.json` пришпилен к
предыдущему claim'у (`localReviewUnitId: "S8-PUBLISH2"`, `localReviewRiskTier:
"high"`, receipt `S8-PUBLISH2-adjudication.json`). Проверка на tier `high`
отвечает `receipt risk tier does not match adjudication` — значит квитанцию S9
надо чеканить под ТОТ ЖЕ tier, что будет прописан в реестре, и реестр
перерегистрировать на неё.

**Что осталось сделать — по шагам:**

1. Прогнать `skills/_shared/itd_free_reviewer_producer.py review` с
   `--candidate-mode committed-head` (именно ради этого делался U1 — до него
   продюсер не умел закоммиченный кандидат). Аргументы: `--root .`,
   `--base e3131c9`, `--repository hihol-labs/idea-to-deploy`,
   `--scope .itd/SCOPE_LOCK.md`, `--acceptance .itd/ACCEPTANCE_CONTRACT.json`,
   `--machine-receipt <S9-EVIDENCE-machine из receipts/bcd19b10edf85776/>`,
   `--signing-key .itd-memory/verification-loop/keys/gpg003-local-producer-20260803.key`,
   `--key-id gpg003-local-producer-20260803`, `--codex <ELF из vendor-пакета>`,
   `--codex-sha256 37e6f595…`, `--proxy-sha256 01ba4719…`,
   `--maker-provider anthropic --maker-model claude-opus-5 --maker-session <id>`,
   `--reviewer-model gpt-5.6-terra`, плюс `--prompt-output/--report-output/--output`.
   Транспорт рвётся — у продюсера, в отличие от efficacy-раннера, чекпоинта
   НЕТ (см. `.itd/GPG-004_A16_TRANSPORT.md`), обрыв стоит всю попытку.
2. Отчеканить adjudication поверх подписанной phase-one квитанции, tier —
   согласовать с реестром (в S8 было `high`).
3. Перерегистрировать `~/.config/itd/gates.json` на новый
   `localReviewUnitId` / `localReviewReceiptFile` / `localReviewRiskTier`.
4. `sh skills/_shared/itd_py.sh scripts/itd.py pr create --maker-vendor
   anthropic --maker-model claude-opus-5 --maker-session <id>`.
5. После merge — релиз S8+S9 по `docs/RELEASE_RUNBOOK.md`, затем
   `scripts/sync-to-active.sh`.

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
