# Working deadline mode

`working_deadline` — **opt-in** профиль повседневной работы с ограниченным
дедлайном. Он меняет cadence проверок и момент handoff, но не заменяет
существующую risk policy и не ослабляет evidence-gates.

Машиночитаемый источник истины:
`skills/_shared/WORKING_DEADLINE_POLICY.json`. Профиль наследует обязательные
capabilities и signal contours из
`skills/_shared/PROPORTIONALITY_POLICY.json`; привязка зафиксирована SHA-256.

## Временные границы

- **30 минут** host-observed времени unit — soft checkpoint: показать готовое,
  блокер, остаток и оценку. Это не означает остановку, если unit безопасно
  завершается в оставшееся окно.
- **45 минут** — hard pause до следующей дорогой попытки. Unit получает typed
  `budget_exhausted` / `recovery_required`, partial work не становится
  `verified`, а дешёвые inspection и checkpoint остаются доступны.
- Остановка происходит на безопасной границе; timebox не разрешает бросать
  необратимую операцию посередине и не отменяет rollback.

## Unit и handoff

WIP остаётся равным одному. После каждого independently verifiable vertical
slice выполняется `handoffAfterVerifiedUnit`: результат возвращается
пользователю до активации следующего unit. Это ограничение handoff, а не
host-dependent «один turn». Явно одобренный bounded autonomous run может иметь
другой cadence, но не может обходить WIP, DoD, review или test gates.

После результата выполняется дешёвый checkpoint. Это **не является explicit close**:
тяжёлое закрытие сессии запускается только по явному намерению
пользователя.

### Runtime CLI (PE5-011)

Профиль активируется только явным параметром для low/medium-risk unit:

```bash
sh skills/_shared/itd_py.sh skills/goal/scripts/itd_goal_verify.py \
  --activate G-00X --work-profile working_deadline
```

Host начинает монотонный таймер при успешной активации. Наблюдение передаётся
через `--deadline-check G-00X --elapsed-seconds N`. На 1800 секундах runtime
требует непустые `--checkpoint-ready`, `--checkpoint-blocker`,
`--checkpoint-remainder` и `--checkpoint-estimate`. На 2700 секундах он
возвращает exit 3, сохраняет `recovery_required` и typed
`budget_exhausted` evidence; verificationCommand после границы не запускается.
Если host пропустил soft boundary, полный checkpoint можно безопасно дописать
повторным `--deadline-check` уже в `recovery_required`: stop остаётся активным.
Resume запрещён, пока все четыре поля checkpoint не сохранены.

После verified runtime ставит durable handoff barrier. Адаптер снимает его
только после фактического возврата результата и нового user/host turn:

```bash
sh skills/_shared/itd_py.sh skills/goal/scripts/itd_goal_verify.py \
  --ack-handoff G-00X --reason "result returned; new user turn"
```

До acknowledgement следующий unit не активируется. Возобновление
`recovery_required` также требует явный `--activate G-00X --reason "…"` и
начинает новый host-observed cycle.

## Targeted и release

Профили проверки являются надстройкой над risk policy:

- `targeted` строит risk-derived impact closure и выполняет только обязательные
  capabilities для low/medium unit плюс contours всех обнаруженных сигналов;
- unknown impact, unknown risk и high risk выходят в strict/release path;
- auth, payments, secrets и security всегда добавляют security contour, даже
  если пользователь не включил его в критерии;
- `release` добавляет review, full integration и реальную Windows/WSL matrix.
  Evidence привязывается к exact release-candidate hash; любая правка кандидата
  инвалидирует результат.

Исполняемый selector — `skills/_shared/itd_verification_profiles.py`. Он читает
один bounded JSON manifest и не сканирует репозиторий без входа:

```bash
sh skills/_shared/itd_py.sh skills/_shared/itd_verification_profiles.py \
  --input .itd-memory/verification-request.json
```

Операция `select` возвращает transitive `impactClosure`, выбранные contours и
обязательные capabilities. Операция `release-evidence` принимает только
`PASSED` Windows/WSL и CI/native evidence с тем же `candidateSha256`;
изменившийся кандидат делает старое evidence невалидным. Операции `diagnostics`
и `backlog` проверяют описанные ниже границы и завершаются ненулевым кодом при
неполном или небезопасном evidence. Успешный selector сам по себе не означает,
что verification уже пройдена: в ответе остаётся `verified: false` до отдельной
проверки evidence.

## Review, diagnostics и backlog

Review cache допустим только для успешного verdict, связанного с repository,
base/tree, diff, scope/acceptance contracts, rubric/version и risk tier.
`BLOCKED` и `UNVERIFIED` не удовлетворяют gate. Обычный review сбрасывает только
general risk; security risk оплачивается успешной security-проверкой.

В PE5-013 этот контракт реализован общим producer
`skills/review/scripts/itd_review_cache.py`: commit gate больше не читает legacy
timestamp/tree markers, а `verdict-contract.sh` записывает фактический
machine-readable status. Risk state хранит независимые `general_score` и
`security_score`; после принятого gate накопление соответствующего bucket
начинается с post-gate delta. Запись `PASSED_WITH_WARNINGS` принимается только
при наличии durable warnings с файлом и кратким описанием.

Диагностический прогон сначала собирает независимый failure set. Каскадные
ошибки группируются по root cause, затем исправляется один causal cluster и
выполняется дешёвая различающая проверка. Финальный шаг повторяет исходную
diagnostic-команду; красный повтор не считается успехом.

В backlog уходят только предсуществующие, вне scope, неблокирующие дефекты, не
внесённые текущим diff. Acceptance failures, current-diff regressions, critical
security и data-loss остаются блокерами текущего unit.

## Внешние записи

Email, issue, comment и другая внешняя запись требуют preview точных targets,
полного payload и attachments. Подтверждение связано с canonical tool input и
`payload hash`; изменение текста или адресата инвалидирует approval. Read-only
операции и уже точно одобренный неизменившийся payload не требуют повторного
подтверждения.

В PE5-014 этот контракт исполняет общий
`skills/_shared/itd_external_write_gate.py` на существующей границе
`pii-egress-guard.sh`. Preview включает canonical tool name, targets, полный
payload, attachments и session provenance; локальный approval-ledger не
создаётся. PreToolUse matcher `.*` и native `ask`/`deny` одинаковы для Claude
Code и Codex. Неизвестное
connector-действие считается потенциальной записью; при невыводимом target оно
не может быть одобрено до явного уточнения адресата.

Операционный путь: gate строит exact preview с `approvalHash`/`sessionId` и
возвращает `permissionDecision: ask`. Host показывает preview и разрешает ровно
этот pending tool call только после native user confirmation. Локальный файл,
прямой CLI-флаг `--confirmed-by user` или модель не могут записать approval;
другой session, target, attachment или payload образуют новый hash и новый
host prompt. При невыводимом target/session ответ — hard `deny`, не `ask`.
Политическое правило
`exactAlreadyAuthorizedActionRequiresRepeatApproval: false` относится к тому же
pending invocation: после native approval host исполняет его без повторного
входа в gate. Новый, даже текстуально одинаковый вызов — новое внешнее действие
(иначе письмо/comment можно отправить дважды) и получает новый host prompt.

## Model routing и rollout

Low effort разрешён только для bounded low/medium mechanical work. Review,
security, root-cause, architecture, high-risk и unknown-risk сохраняют текущий
quality floor. Публичные множители скорости или кредитов не являются контрактом
методологии: результат оценивается по host-observed telemetry и frozen A/B.

Исполняемая граница — существующий `hooks/model-policy.sh`. Явный downgrade
medium-роли до `effort=low` проходит тихо только при активном
`working_deadline`, известном low/medium risk и описании slice с префиксом
`[itd:mechanical]`. Для protected/high/unknown/unbounded случая hook возвращает
host-native ASK с WHY/FIX, поэтому понижение не происходит незаметно. Low-effort
решение не меняет targeted/release selector и не удаляет обязательный evidence
contour.

Числовые speed/credit ratios и датированные model IDs — not a methodology
contract. Операционная калибровка опирается только на host-observed telemetry и
frozen A/B для фактического candidate.

Режим остаётся default-off до canary и сопоставимых наблюдений. Contract stage
реализован в PE5-010, runtime timebox/handoff — в PE5-011. Verification
selector и failure boundaries — в PE5-012, cache/risk-budget — в PE5-013.
External-write gate поставлен в PE5-014; model/effort routing — в PE5-015.
PE5-016 выполняет итоговый no-regression benchmark.

### Frozen A/B и финальная regression (PE5-016)

`tests/verify_work_deadline_benchmark.py` читает sealed
`benchmarks/working-deadline/CORPUS.json` и сравнивает одинаковые cases:
always-full baseline против фактического host-neutral selector. Quality — это
полное покрытие требуемых capabilities, а не модельная оценка. Каждый contour
считается одним tool/checker invocation; wall-clock измеряется локальным
монотонным process benchmark с работой, пропорциональной уже замороженным
`normalizedTimeUnits`.

Вывод привязан к SHA-256 identity базового `HEAD`, текущего tracked diff и всех
non-ignored untracked candidate files: поэтому два clean checkout разных
commit не получают один hash. Валидатор независимо пересчитывает binding, а
mutation guard подставляет другой корректный 64-hex hash. Остальные guards
требуют чистый baseline и свой точный diagnostic, чтобы посторонняя ошибка не
маскировала выживший мутант. Вывод содержит quality regressions, high-risk
bypasses и отдельные ratios для tool calls и wall-clock. Это внутреннее
сопоставимое evidence (`externalEvidence: false`), не подмена PE5-008/009.
Финальный verdict требует также текущие Harness/Practical Effectiveness,
adapter, meta-review, quick и full regression из verification command PE5-016.
