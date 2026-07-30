---
project: /home/hihol/projects/idea-to-deploy
stage: implementation
from_role: active Codex implementation session
to_role: post-compaction Codex implementation session
reason: context threshold handoff during active bugfix
branch: codex/harness-lifecycle-trust
head: e0384d62b356064b12e336e92ffc775001cdf7b2
head_kind: git-commit-before-staged-wip
candidate_binding: external-git-write-tree-and-adjudication-receipt
---

# Handoff — 2026-07-30

> [!todo] Первое действие
> Проверь exact staged tree и актуальный adjudication receipt, затем уменьши
> или безопасно раздели полный canonical candidate PR #177 до `<= 1.2 MB` и
> `<= 15 units` без ослабления лимитов; не принимай oversized candidate.

## From → To и причина

- Передача внутри продолжающейся implementation-сессии после compaction.
- Причина: сохранить доказуемое состояние текущего WIP и следующий шаг без
  повторного начала работы.

## Текущее состояние

- Активная high-risk единица: `GPG-001` — глобальный fail-closed PR/API gate
  для Windows и WSL. Статус остаётся `in_progress`; завершение не заявлено.
- Ветка `codex/harness-lifecycle-trust`, Draft PR
  [#177](https://github.com/hihol-labs/idea-to-deploy/pull/177). Поле `head`
  выше — текущий Git commit, на котором лежит staged WIP, а не hash staged
  tree. Exact tree нельзя встраивать в этот файл без самоссылки: его нужно
  вычислить после полного staging через `git write-tree` и принять только по
  внешнему adjudication receipt с тем же hash.
- В `e0384d6` принят bounded hierarchical review: direct до 80 KB,
  hierarchical до 1.2 MB, максимум 15 units плюс integration verdict.
  Exact tree `ffeec83e005a5eaf0935b8f7a1a18bfe3aaf6b4c` прошёл machine oracle,
  fresh `gpt-5.6-terra` checker и adjudication; quick suite был green.
- Незакоммиченный staged WIP нужно сохранить целиком. Он включает broker,
  frozen policy/schema, runtime schema, focused tests, docs и task evidence;
  не откатывать и не подменять его прежним RED-тестом.
- Исходный RED на gzip byte `0x8b` закрыт bounded single-member transform
  только для `.jsonl.gz`; raw/logical bytes hash-bound, strict UTF-8/JSONL и
  secret scan fail closed, а undeclared binary остаётся `UNVERIFIED`.
- Transparent-review implementation прошёл focused broker 472, primitives
  152, policy 128, API-reviewer 77, external release, host adapters,
  meta-review (`Critical 0`, `Important 0`) и quick `DONE fails:none`.
  Fresh `gpt-5.6-terra` hierarchical checker вернул чистый `PASSED` с
  нулём findings/unverified; после любой новой tracked правки receipts нужно
  получать заново для нового exact tree.
- Полная локальная canonical-реконструкция от подтверждённого GitHub base
  `c52eca984ae61ce474fa1151a894bde2382e064d` до staged tree дала 92 файла,
  один declared transparent файл и `1,287,112` байт при лимите `1,200,000`.
  Даже прежний PR head `e0384d6` давал `1,244,538` байт. Поэтому полный PR
  остаётся `UNVERIFIED`; повышать лимит или заявлять completion нельзя.
- Обязательная live-evidence проверка дала 91 PASS / 4 FAIL только на stale
  methodology/dirty-tree pins. Штатный refresh не стартовал:
  `codex CLI has no external credential/auth session`; evidence не изменён.
- Обязательный
  `tests/fixtures/live-model-evidence/runs/20260730T065213Z-d5716dad/transcript.jsonl.gz`
  теперь имеет объявленное transparent-review представление. Любой другой
  generic binary по-прежнему должен блокироваться как `UNVERIFIED`.
- Старый persistent goal имеет 36/38 verified; `PE5-008/009` остаются
  заблокированы отдельно приостановленным external outcome pilot. Не смешивать
  этот статус с `GPG-001`.

## Финальные решения

- Обязательная проверка выполняется серверным dedicated GitHub App на exact
  GitHub test-merge SHA после создания Draft PR; локальные hooks/CLI — ранний
  UX/advisory слой, не trust boundary.
- API outage, zero balance, missing/stale provenance, oversized или неполный
  candidate дают fail-closed и блокируют merge.
- Routing: Sol-authored code проверяется fresh Terra как independent
  same-vendor review; Codex/Gemini CLI остаются advisory. Same-vendor review
  не называть cross-vendor.
- Для `.jsonl.gz` допустим только явно объявленный logical transform:
  bounded streaming decompression, один gzip member, UTF-8 без NUL, валидный
  JSONL, secret scrub, raw и logical hashes/bytes в manifest/evidence.
  Не включать generic `allowBinary`, не извлекать архив на диск и не исполнять
  candidate code.
- Пользователь явно разрешил использовать ранее раскрытый OpenAI key для
  независимого API-reviewer и отменил прежнее требование об отзыве. Значение
  допустимо только как runtime secret broker-процесса: не выводить, не искать
  в логах и не сохранять в repository, plugin cache, prompts, receipts,
  Windows User env или WSL profiles.
- Установленный plugin cache не редактировать: изменения выпускаются новой
  версией ITD и устанавливаются штатным plugin manager.

## Требуемые входы

- `AGENTS.md`, [[STATE]], [[GOAL]], `.itd/SCOPE_LOCK.md`,
  `.itd/FORBIDDEN_CHANGES.md`, `.itd/DECISIONS.md`.
- `ROOT_CAUSE.md`, `.itd-memory/session_2026-07-30.md`.
- Исходный утверждённый девятичастный план:
  `C:\Users\Дмитрий\.codex\attachments\ed58000a-fc06-4a28-be39-541fc31568cc\pasted-text-1.txt`.
- Для продолжения workflow прочитать `skills/bugfix/SKILL.md`; перед принятием
  exact candidate применить shared Verification Loop и project contracts.
- Секреты отсутствуют в handoff. Для финального live API review разрешён
  существующий пользовательский OpenAI key только через runtime secret
  injection без раскрытия или персистентности.

## Зоны записи / запреты

- Менять в ближайшем unit: broker runtime/primitives, frozen broker policy и
  schema, focused broker tests, API-reviewer docs/contracts и task evidence,
  только насколько требуется для bounded `.jsonl.gz` representation.
- Сохранять WIP=1 и текущие незакоммиченные файлы; не откатывать их.
- Запреты: `.itd/FORBIDDEN_CHANGES.md`; никакого generic binary allow,
  truncation, caller-supplied success/cost, API-key persistence, candidate
  execution с reviewer credentials, ослабления exact-candidate/App-bound
  checks, редактирования plugin cache или merge-ready заявления до receipt.

## Команды проверки

```bash
# Focused regression: прежний gzip RED теперь обязан быть GREEN
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_review_broker.py

# Полный focused и adapter набор
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_review_broker.py
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_review_broker_primitives.py
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_review_broker_policy.py
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_api_reviewer.py
python3 tests/verify_host_adapters.py
bash tests/run-all.sh --quick

# Финальный live evidence refresh — только после последней кодовой правки
sh skills/_shared/itd_py.sh tests/verify_live_model_benchmark.py --require-evidence --max-age-days 30
```

После текущего exact receipt нужно сократить или безопасно разделить полный
canonical diff PR #177, доказать `<= 1.2 MB`, `<= 15 units` и exact
reconstruction, а затем получить receipts уже для полного GitHub candidate.

> [!warning] Блокеры и риски
> Полный PR candidate сейчас превышает hierarchical limit примерно на 87 KB;
> не лечить это truncation, generic binary исключением или молчаливым
> повышением лимитов. Серверный контур также ещё не завершён: нужен стабильный HTTPS broker host,
> разрешённый пользователем OpenAI key должен подаваться только через private
> runtime secret file, затем нужны dedicated GitHub App, двухфазный bootstrap
> protected-base contract, App-bound ruleset, глобальный registry,
> release/install 1.95.0 и negative canaries. GitHub Organization `hihol-labs`
> на Free; private org-wide rulesets требуют Team/Enterprise либо
> per-repository protection. `claude auth login` ранее завис в ожидании browser
> callback и Claude нельзя считать доступным до end-to-end проверки.
> Live-model benchmark refresh также остаётся `UNVERIFIED`, пока Codex/Claude
> CLI не имеет внешней auth-сессии; наличие API key не разрешает сохранять CLI
> login или передавать secret candidate-процессу.
