# Task - strict route

Read this file when Step 0 of `SKILL.md` chose the strict route: the project declares `itd-route: strict` or
`itd-domain: data-sensitive`, the arguments contain `--strict`, or the task falls in a strict class of the global
rules (ITD's own critical mechanisms, money, access, deploy, migrations, production data) - which includes routing to
`/migrate`, `/migrate-prod`, `/deploy`, `/infra` or `/autopilot`. These steps run together with Steps 1-4 of
`SKILL.md`; on the minimal path none of them runs.

## S1. Process-cost classification and proportionality

Before routing, classify the task's **process-cost tier** so the methodology scales to the risk — see `skills/_shared/helpers.md` §6:

- **trivial** (typo, rename, one-liner, obvious cause) → do it directly, skip the routing question and the contract/gate machinery.
- **standard** (normal change in one module) → route to the target skill; it applies `SCOPE_LOCK` + spec-compliance + fail-closed verify + `/review`/`/test`.
- **high-risk** (the target is `migrate`/`migrate-prod`/`deploy`/`infra`/`autopilot`, or the change touches production data, schema, auth, payments, or security) → apply the full `.itd/` contract set + permission matrix + branch-finish + **explicit user approval** before acting.

State the tier in one line when you route ("это standard-задача → /refactor"). When unsure between two tiers, pick the higher one.

The machine-readable source for verification proportionality is
`skills/_shared/PROPORTIONALITY_POLICY.json` (installed fallback:
`$HOME/.claude/skills/_shared/PROPORTIONALITY_POLICY.json`). Normalize
`trivial → low`, `standard → medium`, `high-risk → high`; run only that
`riskRoutes.<risk>.contours` set plus any matching `signalContours`. Every
listed `requiredCapabilities` remains mandatory evidence. In particular, the
low path MUST NOT run `review`, `security`, or `full` without a matching risk
signal; final cumulative regression follows the micro-path rule below. Unknown
risk fails closed to `high`; an unknown signal is surfaced and does not invent
an unreviewed contour.

The executable daily/release selector is
`skills/_shared/itd_verification_profiles.py`. Feed it one bounded JSON manifest
with `--input`: it computes transitive impact closure, selects `targeted` or
`strict.release`, binds release evidence to the exact candidate SHA-256, and
validates diagnostic/backlog boundaries. With no input it is a quiet no-op;
never replace its fail-closed result with a prose guess. In this repository the
impact graph is committed data — `.itd/IMPACT_GRAPH.json`, fed through
`impactGraphPath` and audited for completeness/proportionality by the
`impact-audit` operation (see `docs/WORKING_DEADLINE_MODE.md`).

**Cost-awareness (v1.31.0 — New-SDLC port):** for a **high-risk** tier or a heavy
target (`/kickstart`, `/autopilot`, long `/perf`/`/bugfix` sweeps) note that
`hooks/cost-tracker.sh` keeps a per-session token/USD ledger and will ASK at the
budget ceiling — set `ITD_COST_CEILING_TOKENS` (and `ITD_COST_PER_1M_USD`) per project
to make the ceiling meaningful, and `/session-save` will attach the cost snapshot at
wrap-up. This is a one-line nudge, not a gate — never block routing on it. (Token
economics is the OpEx lever for agent-heavy products; see ADR-001 — accounting rides
the existing hook, we don't build our own collector.)

**Micro-path — regression cadence for tiny tasks (v1.66.0, retro-2026-07-08 P4):**
for a **standard**-tier task of **≤1–2 units** with a small diff, per-unit
verification stays MANDATORY (the unit's own verification command goes green
before anything else starts), but the **cumulative regression suite runs ONCE as
a final full pass** instead of after every unit. Evidence: the measured cost of
after-every-unit regression on a micro-task was ×3.5 wall-clock and ×7 tool calls
at zero difference in verified-completion rate. Classify by unit count, not by
feel: 3+ units, cross-module effects, or any high-risk signal → back to
after-every-unit regression (see `skills/_shared/helpers.md` §6).

## S2. Read the module-quality queue (when present)

If `.itd/QUALITY.json` exists, read it before fixing scope. Prefer the executable
view (**`itd_hygiene.py quality`**) so stale or evidence-less grades cannot look
authoritative:

```bash
T="skills/_shared"; for d in "$HOME/.claude/skills/_shared" "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-/nonexistent}}/skills/_shared"; do [ -f "$d/itd_tool.sh" ] && T="$d"; done
[ "$T" = skills/_shared ] && C=$(ls -d "$HOME"/.codex/plugins/cache/*/idea-to-deploy/*/skills/_shared 2>/dev/null | awk -F/ '{print $(NF-2), $0}' | sort -k1,1V | tail -1 | cut -d" " -f2-) && [ -f "${C:-/}/itd_tool.sh" ] && T="$C"
sh "$T/itd_tool.sh" itd_hygiene.py quality --root .
```

Surface the lowest-grade module and its first priority in the routing context.
It is the default maintenance priority, not permission to override an explicit
user task: if the user asked for another module, keep their scope and record the
lower-grade finding as backlog. Missing `.itd/QUALITY.json` is a soft no-op for
pre-adoption projects; an invalid/stale ledger is a visible quality warning.

When `.itd/QUALITY_SCORECARD.json` exists, prefer the newest local
`.itd-memory/hygiene/quality-score-*.json` for ordering modules: its
`computedGrade`, weighted `score`, minimum breach, and `overstatedGrade` are
executable evidence, while the prose ledger remains the human explanation. Do
not rerun a potentially expensive scorecard on every routing turn. Refresh it
only when the user asks for a fresh assessment, the periodic record is due, or
no record exists and the task is explicitly quality-oriented:

```bash
T="skills/_shared"; for d in "$HOME/.claude/skills/_shared" "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-/nonexistent}}/skills/_shared"; do [ -f "$d/itd_tool.sh" ] && T="$d"; done
[ "$T" = skills/_shared ] && C=$(ls -d "$HOME"/.codex/plugins/cache/*/idea-to-deploy/*/skills/_shared 2>/dev/null | awk -F/ '{print $(NF-2), $0}' | sort -k1,1V | tail -1 | cut -d" " -f2-) && [ -f "${C:-/}/itd_tool.sh" ] && T="$C"
sh "$T/itd_tool.sh" itd_hygiene.py quality --root . --scorecard .itd/QUALITY_SCORECARD.json --record
```

The scorer never promotes the tracked grade automatically. A computed grade
below the declared grade or below `minimumScore` is a visible fail-closed
quality finding; a computed grade above the declaration only shows that the
human ledger is conservative.

## S3. PIV-lite façade - a new feature in brownfield (v1.94.0)

The daily-work case the matrix used to miss: implementing a NEW feature in an
existing project is neither `/bugfix` nor `/refactor`, and `/kickstart` is
forbidden here. For this route `/task` acts as the pipeline conductor — it does
not write the code "as a router", it walks the standard chain around the
implementation:

This existing chain is exposed as **PIV-lite: Plan → Implement → Validate →
Review**. `PIV_LITE_ROUTE.json` is a provider-neutral map of this façade, not a
new command or lifecycle skill. The labels mean:

- **Plan** — scope lock, task contract, bounded plan, and human approval.
- **Implement** — surgical, WIP=1, scope-bound edits through the routed skill.
- **Validate** — the existing `/test` plus exact-candidate machine producer.
- **Review** — `/review`, the risk-tier checker, adjudication, and receipt
  recheck.

Only the existing Verification Loop may complete the unit. PIV-lite narration,
diagnostics, a standalone review, or a sentinel file are never completion
evidence.

PIV-lite requires an adopted brownfield project with both
`.itd/SCOPE_LOCK.md` and `.itd-memory/STATE.json`; that is how its unconditional
WIP=1 claim is enforced. Without these stores, offer `/adopt strict` first. If the
user declines, run the same steps 1-6 below without the stores (scope stated in one
message, no unit ledger, no Task Contract file): plan approval, `/test`, `/review`
and the declared verification still apply, but it must not label the run PIV-lite or
claim machine-enforced WIP.

1. **Scope first.** If `.itd/` exists — fill `SCOPE_LOCK.md` (Current Task +
   Allowed/Forbidden Change Areas) and open a unit per S4. Without
   `.itd/` — state the scope in one message (files/modules to touch, what is
   explicitly out of scope).
1b. **Task Contract (Sprint Contract per-задача, v1.88.0).** До первой
   правки кода зафиксируй контракт юнита в
   `.itd-memory/contracts/<unit-id>.md` по шаблону
   `docs/templates/itd/TASK_CONTRACT.md`: Scope / Verification Standards /
   Exclusions (Verification = verificationCommand юнита или его
   эквивалент). Генератор и оценщик согласуют контракт ДО старта: ОТК
   исполняет Verification, DoD-гейт на git commit даёт advisory-строку,
   если у активного юнита контракта нет (не блокирует). Один экран, не
   спецификация. Без `.itd-memory/` — шаг пропускается молча.
2. **Plan → approve.** Every PIV-lite feature, including a one-file PIV-lite
   feature, requires a short plan (steps, files, verification per step) and
   explicit user approval before code. The trivial direct path outside
   PIV-lite may still skip this ceremony. For a large/risky feature offer
   `/grill-me` on the plan first.
2a. **Deployment baseline — дефолтная планка (v1.89.0, GO-005).** Даже БЕЗ
   явного Task Contract каждая feature-задача применяет этот deployment-floor
   (замер A/B сет-4: агент без контракта промахивался именно здесь — 3.5/6):
   - **Exit-семантика**: CLI/скрипт возвращает ненулевой код при найденной
     проблеме и 0 при чистоте; «нашёл, но exit 0» — дефект.
   - **Diff-scoped / no-op по умолчанию**: инструмент проверки работает по
     переданному срезу (`--files`), без аргументов — no-op, а не полный скан
     живого репо.
   - **Actionable-вывод**: на нарушении — путь + строка + WHY + FIX-подсказка,
     не голое «ERROR».
   - **Тихий успех**: при отсутствии находок — без шум-сводки в stdout.
   - **Zero-dep, если так задано**: не тянуть пакеты/AST, если задача просила
     stdlib.
   - **Самопроба**: прогнать на позитивной И негативной фикстуре, показать
     фактические exit-коды.
   Явный Task Contract (шаг 1b) переопределяет/дополняет планку; при его
   отсутствии планка — и есть контракт по умолчанию.

3. **Implement** — surgical edits inside the declared scope; the normal gates
   stay armed (wip-gate, careful, DoD). **Producer-first rule** (retro
   2026-07-04, класс «assumed producer shape» — 2 Important в одном ревью):
   если фича ЧИТАЕТ файл/леджер/формат, который пишет другой код — сначала
   прочитай код продюсера (реальные имена полей/форм), и тесты сей реальными
   образцами продюсера, а не предположенной формой.
4. **Validate (existing Verify gate)** — `/test` for new code (fail-closed:
   evidence required; for
   projects without a test runner use the project's declared verification —
   lint/build/domain checks from `.itd/VERIFICATION_CONTRACT.json` or
   CLAUDE.md). Execute the declared commands through the machine producer in
   `docs/VERIFICATION_LOOP.md`; a narrated command result is not completion.
5. **Review — `/review` + adjudicate** before PIV-lite completion or commit,
   including a one-file PIV-lite feature (mandatory floor).
   Low risk adjudicates the machine receipt alone. Medium adds a targeted
   fresh-session checker; high/unknown adds a full checker from a fresh session
   and different model/provider. Mint the unit receipt with claim id equal to
   the active unit, validate it again with `itd_verification_loop.py check`, and
   only then mark the unit verified. `/review` separately records its
   `<unit>:general-review` receipt for the exact-context cache.
6. Commit per the project's branch/PR rules; `/session-save` at the block end.

Tier note (S1): a feature is **standard** by default; escalate to
**high-risk** when it touches prod data, schema, auth, payments, or security.

Stall-resilience: when any step here dispatches a subagent (the routed skill's
verify/review agents, an Explore/refute agent) and it **stalls** — watchdog
timeout, autocompact death, empty return — the recovery is **automatic**: spawn a
fresh narrow agent scoped to the smallest useful slice, do not stop to ask
«resume or retry?». This is the shared rule in `skills/_shared/helpers.md` §9,
not a per-skill judgement call.

## S4. Unit bookkeeping - WIP=1 (writer: the harness; only when `.itd-memory/` exists)

If `$PROJECT_ROOT/.itd-memory/STATE.json` exists, keep the machine-readable
scope surface honest around the routing. Переходами unit-статусов управляет
скрипт `skills/task/scripts/itd_unit_log.py` — **не пиши JSON в
STATE.json/events.jsonl руками** (диагноз G-004, retro 2026-07-11: ручная
запись теряла activation-события — 4 юнита verified без activated, слепой VCR).

Резолв путей (в начале каждого shell-вызова; python — только через запускатель):

```bash
TT="skills/task/scripts"; [ -f "$TT/itd_unit_log.py" ] || TT="$HOME/.claude/skills/task/scripts"
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
```

1. **Before activating** — read `STATE.json.currentUnit`. If its `status` is
   `verifying` / `recovery_required` (unfinished unit) → do NOT silently start
   the new unit. Tell the user: «Текущий unit `<id>` не доведён до verified
   (<status>). WIP=1: сначала доводим его верификацию, или осознанно
   закрываем/переклассифицируем?» Proceed only after an explicit choice.
   (Скрипт продублирует WIP=1 fail-closed — но спросить пользователя обязан ты.)
2. **On activation** —
   `sh "$SHD/itd_py.sh" "$TT/itd_unit_log.py" activate U-<next> --goal "<one-line task>" --risk-tier <low|medium|high|unknown>`
   (`--risk-tier` обязателен: маршрут ревью пропорционален тиру, а тир не
   выводится из имени юнита; неклассифицированный риск объявляется как
   `unknown` и идёт по строгому маршруту). **Strict-классы (ADR-011, G-001):**
   если текст `--goal` или Allowed Change Areas в `.itd/SCOPE_LOCK.md` попадают
   в `strictClasses` политики (`money` / `prod-config` / `db-schema` / `auth` /
   `secrets`), писатель печатает класс и совпадение и записывает `riskTierMatch`
   в STATE; если объявленный тир ниже `high` - поднимает его и записывает
   `riskTierForced` — не спорь с ним и не
   переформулируй goal ради дешёвого маршрута; тир меняется правкой политики.
   SCOPE_LOCK читается в момент активации — пиши его ДО `activate`, иначе
   матчер увидит области предыдущего юнита. **Исключение tests-only
   (TIER-SOURCE-1):** если каждая непустая строка Allowed Change Areas - один
   пункт списка (`-`, `*`, `+`, `1.`, `1)`) ровно с одним путём (можно в `code`)
   и необязательной пометкой `(new)` или `(updated)`, а первая строка Current Task начинается с id активируемого юнита
   (`- U-3: …`), текст `--goal` не источник strict-классов: совпадение в goal
   печатается и пишется как `riskTierExempt` (и рядом с `riskTierForced` или
   `riskTierMatch`, если тир поднят самой областью), тир из-за goal не поднимается. Тестовый путь -
   каталог `tests/`, `test/`, `__tests__/` или файл кода `test_*.py`, `*_test.*`,
   `*.test.*`, `*.spec.*`, `conftest.py` из ASCII `[A-Za-z0-9_./*?-]` без `\` и без `..`. Любая другая строка
   (проза, два пути, продолжение пункта) снимает исключение. Путь или ключевое
   слово strict-класса в самой области по-прежнему поднимает тир до `high`.
   **Область-список путей (TIER-WORDING-2):** то же исключение действует, когда
   пункты той же грамматики называют тестовый путь или один конкретный файл
   (без `*` и `?`, без `..`, имя с непустой основой и расширением из закрытого
   набора `_FILE_EXTS` в `skills/_shared/itd_risk_classes.py`): тир не зависит от
   формулировки goal, причина в `riskTierExempt` - `a list of paths`. Каталог
   (`src/`, `src/fx`), глоб (`src/*`), имя без расширения (`Dockerfile`,
   dot-файл без расширения вроде `.gitignore`) и прочие расширения оставляют
   goal источником. То же делает нестандартная раскладка SCOPE_LOCK: пункт,
   который `hooks/wip-gate.sh` читает как разрешенную область, а матчер не
   прочел (секция `## Allowed Change Areas (continued)`, пункты после `# Notes`,
   заголовок области с отступом или внутри fence), либо заголовок, который лишь
   начинается с названия области. Перечисляй в Allowed Change Areas файлы,
   которые реально меняешь: для такого юнита пол strict-классов - это список
   путей, а не слова goal. Файл с нейтральным именем (`scripts/release.sh`,
   `config/app.yaml`, `service-account.json`) тир сам не поднимает - если правка
   касается денег, прод-конфига, схемы БД, auth или секретов, объявляй
   `--risk-tier high` явно.
   — скрипт сам выставит `currentUnit` (атомарно) и запишет событие
   `activated` (actor: harness).
3. **On verified completion** (the target skill's adjudication receipt passed
   `itd_verification_loop.py check` for this exact unit/risk/candidate) —
   `sh "$SHD/itd_py.sh" "$TT/itd_unit_log.py" verified U-<id> --evidence "<вывод проверки>"`
   — verified без evidence или без парного activation-события скрипт отклонит
   (осознанная реконсиляция истории: `backfill-activation U-<id> --note "…"`).
   Include the receipt path and digest in `<вывод проверки>`; plain reviewer
   prose is not evidence. These events feed `itd_metrics.py` VCR (verified/activated) and the
   `wip-gate.sh` hook.

Skip this step entirely when there is no `.itd-memory/` — do not create it
from `/task` (that's `/adopt` / `/kickstart` territory).

## S5. Conditional Graph Lite project policy (ADR-014)

For an explicitly opted-in project, after task scope/contracts and before final validation, materialize .itd-memory/graph-request.json from the current unit, changed tracked files, original task, declared contracts and function inventory. Do not guess risk from filenames or model confidence. Invoke skills/graph/scripts/itd_graph_policy.py prepare with the real host session. A graph decision is owner policy authorization to execute its exact read-only native-agent plan; run the three v2 nodes in layers and record their unedited outputs. A recorded decision reuses the immutable report. A single decision keeps the ordinary path. Invalid/stale permission must not become inferred approval. The graph is additive and cannot replace this task pipeline, any risk-tier checker, or human approval for external actions. Without policy/request the hook is quiet and no graph runs.
