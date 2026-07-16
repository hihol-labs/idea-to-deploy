# Shared Helpers — Common Patterns for Audit-Style Skills

> This file is the single source of truth for patterns shared across
> `/review`, `/security-audit`, `/deps-audit`, and `/harden`.
> Skills reference it via `skills/_shared/helpers.md` instead of
> re-declaring these definitions locally.
>
> Added in v1.17.0 to reduce token consumption by ~190 lines across
> 4 audit checklists (inspired by BMAD's helper pattern).

---

## 1. Gate Status Enum

Every audit-style skill produces a final status using this 3-level enum:

| Status | Condition | Meaning |
|--------|-----------|---------|
| **BLOCKED** | Any Critical check fails | The artifact MUST NOT proceed (merge, deploy, release) until fixed |
| **PASSED_WITH_WARNINGS** | All Critical pass, any Important fails | Can proceed with acknowledged tech debt; fix before next milestone |
| **PASSED** | All Critical + all Important pass | Ready to proceed |

Nice-to-have checks do NOT affect the gate status — they are informational only.

---

## 2. Report Format Template

All audit skills produce a markdown report with this structure:

```markdown
# {Skill Name} Report

## Summary
- **Project:** {name}
- **Date:** {date}
- **Status:** {BLOCKED | PASSED_WITH_WARNINGS | PASSED}
- **Score:** {pass_count}/{total_count}

## Critical Tier
{For each check: ✅ PASS or ❌ FAIL with explanation}

## Important Tier
{For each check: ✅ PASS or ⚠️ WARNING with explanation}

## Nice-to-Have Tier
{For each check: ✅ PASS or ℹ️ SUGGESTION with explanation}

## Results Table
| Tier | Pass | Total | Status |
|------|------|-------|--------|
| Critical | X | Y | ��� / ❌ |
| Important | X | Y | ✅ / ⚠️ |
| Nice-to-have | X | Y | ✅ / ℹ️ |

## Final Status: {BLOCKED | PASSED_WITH_WARNINGS | PASSED}
```

Icons:
- `✅` �� check passed
- `❌` — Critical check failed (blocks)
- `⚠️` — Important check failed (warning)
- `ℹ️` — Nice-to-have suggestion (informational)

---

## 3. Secret Detection Patterns

Canonical regex list for detecting hardcoded secrets in source code.
Used by `/review` (C10), `/security-audit` (SECRET-1), `/harden` (SEC-1).

```
# API keys and tokens
password\s*=\s*["'][^"']+["']
api_key\s*=\s*["'][^"']+["']
secret\s*=\s*["'][^"']+["']
token\s*=\s*["'][^"']+["']

# Bearer tokens in code
Bearer\s+[a-zA-Z0-9_\-\.]+

# Provider-specific patterns
sk-[a-zA-Z0-9]{20,}              # OpenAI / Stripe secret keys
ghp_[a-zA-Z0-9]{36}              # GitHub personal access tokens
ghs_[a-zA-Z0-9]{36}              # GitHub server tokens
AKIA[0-9A-Z]{16}                 # AWS access key IDs
xox[bprs]-[a-zA-Z0-9\-]+        # Slack tokens
glpat-[a-zA-Z0-9\-]{20,}        # GitLab personal access tokens
```

**Exclusions** (NOT secrets):
- `.env.example` with placeholder values (`YOUR_KEY_HERE`, `changeme`, `xxx`)
- Test fixtures with obviously fake values
- Documentation examples

---

## 4. Environment File Checks

Standard checks for `.env` handling (shared across `/review`, `/security-audit`, `/harden`):

| Check | What to verify |
|-------|---------------|
| `.env` in `.gitignore` | `.gitignore` contains `.env` (not just `*.env`) |
| `.env.example` exists | Template file with all required vars and placeholder values |
| No real secrets in `.env.example` | Values are `changeme`, `YOUR_KEY`, empty, or obviously fake |
| `.env` not committed | `git log --all -- .env` returns empty |

---

## 5. Stack Detection Heuristic

When a skill needs to know the project's tech stack, use this detection order:

| Signal | Stack | Confidence |
|--------|-------|-----------|
| `pyproject.toml` or `requirements.txt` | Python | High |
| `package.json` | Node.js/TypeScript | High |
| `go.mod` | Go | High |
| `Cargo.toml` | Rust | High |
| `pom.xml` or `build.gradle` | Java | High |
| `Gemfile` | Ruby | High |
| `composer.json` | PHP | High |
| `*.csproj` or `*.sln` | .NET | High |

Framework sub-detection (Python):
- `fastapi` in deps → FastAPI
- `django` in deps → Django
- `flask` in deps → Flask

Framework sub-detection (Node.js):
- `next` in deps → Next.js
- `nuxt` or `vue` in deps → Vue/Nuxt
- `express` in deps → Express

Skills should detect once and cache the result for the session.

---

## 6. Process-Cost Tiers (complexity routing)

> Added in v1.21 (PFO plugin-native port, item 15). Scales how much methodology a
> task gets to its actual risk — a README typo must not drag the full lifecycle, and
> a production migration must not slip through a light path. Based on PFO's
> `product-classifier` **COMPLEXITY** signal (low/medium/high), **not** any fixed
> "minimal/standard/full" profile.

Classify by signals, then apply the matching process cost:

| Tier | Signals | Contracts | Gates applied |
|---|---|---|---|
| **trivial** | typo, rename, one-line fix, comment/doc tweak, obvious cause | none | sanity check only — do it directly |
| **standard** | normal feature/refactor/bugfix in existing code, single module | `SCOPE_LOCK.md` | spec-compliance (Stage A) + fail-closed verify + `/review` + `/test` |
| **high-risk** | production mutation, schema change, deploy, infra/provisioning, auth/payment/security-sensitive, autonomous run, cross-module | full `.itd/` set + `PERMISSION_MATRIX` | all standard gates + acceptance contract + root-cause (if bugfix) + branch-finish + **explicit user approval** |

The **high-risk** tier aligns with skills carrying `explicit_invocation: true` in their
frontmatter (`migrate`, `migrate-prod`, `deploy`, `infra`, `autopilot`). When routing
to one of those, default to the high-risk path. When in doubt between two tiers, pick
the higher one — under-processing a risky change is the expensive mistake.

The executable contour contract is `skills/_shared/PROPORTIONALITY_POLICY.json`:
`trivial/standard/high-risk` normalize to `low/medium/high`, the matching
`riskRoutes` entry supplies the minimum contours and capabilities, and
`signalContours` adds domain-specific evidence. Do not replace it with a prose
guess or an always-full default. Low-risk work must not pay `review`, `security`
or `full` contour cost without a matching signal; unknown risk fails closed to
high. The frozen paired A/B oracle is
`tests/verify_proportionality_benchmark.py`.

The host-neutral executable consumer is
`skills/_shared/itd_verification_profiles.py`. It accepts one explicit JSON
manifest via `--input` and derives the transitive targeted contour set, exact
release-candidate evidence binding, diagnostic-cluster completion, or backlog
eligibility decision. No input is a quiet no-op. A nonzero decision is a real
gate failure with `why` + `fix`, not permission to fall back to narration.

**Micro-path regression cadence (v1.66.0, retro-2026-07-08 P4).** Within the
**standard** tier, a task of ≤1–2 units with a small diff scales the *cadence*,
not the gate: per-unit verification stays mandatory (the unit's own verification
command must go green before the next step), but the cumulative regression suite
may run ONCE as a final full pass instead of after every unit. Measured evidence:
after-every-unit regression on a micro-task cost ×3.5 wall-clock and ×7 tool
calls versus a free run at zero difference in verified-completion rate — the
re-runs were the whole multiplier. Classify by unit count, not by feel: 3+
units, cross-module effects, or any high-risk signal → after-every-unit
regression as before.

---

## 7. Context Budget

> Added in v1.21 (PFO plugin-native port, item 16). Long tasks degrade when raw dumps
> flood the context window. Spend context like a budget.

Rules for large tool outputs (logs, HTTP responses, `cat` of big files, wide `grep`/`rg`):

- **Summarize, don't dump.** Capture the signal (counts, the 3–5 relevant lines, the error) — not the whole stream.
- **Artifact + path, not inline.** When the full output matters, write it to a file and reference the path (`see /tmp/run-1234.log`), rather than pasting thousands of lines into the conversation.
- **Bound at the source.** Prefer `… | head -50`, `rg -m 20`, `--max-count`, `tail -n 100` over unbounded reads. Read the slice you need (Read with `offset`/`limit`), not the whole 2000-line file.
- **No raw remote bodies.** Never paste an entire raw HTTP/API response; extract the fields in question.

The soft hook `hooks/context-budget.sh` nudges when a command is likely to dump a large
unbounded output. It is a reminder, never a block — judgment stays with the skill.

## 8. Delegation Intent Template (v1.50.0)

> Fable 5-era models perform measurably better when they understand the intent
> behind a request — they connect the task to relevant context instead of
> inferring intent on their own. This matters most for delegated subagents,
> which see none of the parent conversation.

When spawning ANY subagent (architect, code-reviewer, test-generator, Explore,
researcher, …), the prompt MUST carry three intent lines before the request:

```
Я работаю над [большая задача] для [кто потребитель результата].
Результат нужен, чтобы [что он разблокирует / как будет использован].
С учётом этого: [конкретный запрос к субагенту].
```

Two companion rules:

- **Prescriptive triggers, not capability lists.** When the subagent gets
  tools/скиллы, say WHEN to use each ("зови `/test`, когда меняешь
  исполняемый код; НЕ зови для чистых доков"), not merely that they exist —
  trigger conditions in the instruction give measurable lift on should-call
  rate (vendor guidance, Opus 4.7+/Fable 5).
- **Report-back contract.** Tell the subagent its final message is a return
  value, not a user-facing chat: outcome first, evidence attached,
  «Не успел проверить: …» tail when applicable (pairs with
  `hooks/narration-final.sh`).
- **Declared-source contract.** Передаёшь источник по пути (файл инструкций,
  данных, чек-лист) — см. §11: пометь его обязательность и продиктуй
  READ_FAILED-отказ; молчаливая подмена источника недопустима.
- **Re-verify after BLOCKED with a FRESH narrow agent, not a resume (v1.53.0,
  retro 2026-07-05, P4).** When a review returns BLOCKED and you fix the
  findings, confirm the fix by dispatching a NEW subagent scoped to just the
  changed points — do not resume the original long transcript. Evidence: a
  resumed re-check stalled (600s watchdog, no progress) while a fresh narrow
  agent returned PASSED in 84s. A fresh agent starts from a thin context (cheaper,
  less stall-prone) and its verdict is independent of the finder's prior
  reasoning — the same fresh-context property the refute pass relies on. Pass the
  specific findings + fixed file paths by value; keep the scope to "is each prior
  finding resolved + any new defect introduced," not a from-scratch re-review.

## 9. Stall-resilience — fresh narrow agent as the AUTOMATIC stall fallback (v1.60.0 — Ось 2)

> Generalizes §8's post-BLOCKED fresh-agent rule to EVERY stall. A subagent that
> stalls — autocompact-thrashes until it dies, trips a watchdog with no progress,
> or returns empty/truncated — used to force a manual «resume or retry?» decision.
> That manual step is itself a stall in the loop. This makes the recovery
> **mechanical and automatic**: on a detected stall, spawn a fresh narrow agent —
> do not deliberate, do not ask the user.

**Detect a stall by MECHANICAL signals, not by judgement:**

- a watchdog/turn timeout elapsed with no new tool call or output (no-progress);
- the subagent died mid-run (autocompact death, terminal API error after retries)
  and returned nothing usable;
- the returned final is empty or truncated (no deliverable / no verdict marker —
  overlaps `/review` Step 2.7's absence check).

**Class check first (v1.72.0 — root cause 2026-07-09): finish-line
interruption ≠ true stall.** Mechanical signals of the finish-line class (all
must hold):

- the run was labelled «completed» (or died on a terminal API error), yet the
  final message is empty/truncated;
- the transcript tail is live tool activity (`tool_use`/`tool_result`) right
  up to the cut — no no-progress window, no autocompact churn.

That is a **finish-line interruption**: the deliverable is most likely already
computed in the subagent's context. Recovery order for THIS class:

1. the dispatcher passed a report-file path → **read that file FIRST**: a
   complete report on disk needs no ping at all;
2. no file / file incomplete → **ONE resume re-ping** (`SendMessage` — same
   mechanism as `/review` Step 2.7).

Evidence: 3/3 review agents recovered
instantly on 2026-07-09 (one with zero extra tool calls), where a fresh agent
would have repeated 9–15 minutes of work
(`methodology-memory/ROOT_CAUSE-empty-review-finals-2026-07-09.md`). The ping
did not produce the deliverable, or the stall shows no-progress/autocompact
signals → it is a TRUE stall; proceed below.

**Automatic response to a TRUE stall — a fresh narrow agent, NOT a manual choice:**

1. **Spawn fresh, do not resume.** Dispatch a NEW `Agent(...)` from a thin
   context — never resume the stalled transcript (a resumed long transcript
   re-loads the same bloat that caused the stall; §8 evidence: resume stalled at
   the 600s watchdog while a fresh narrow agent returned in 84s; the finish-line
   class above is the deliberate exception — there the transcript is healthy
   and holds the result).
2. **Narrow the scope.** Split the original task into the smallest independently
   useful slice (one dimension, one file, one finding) and pass inputs by value /
   by path — a smaller prompt is both cheaper and far less stall-prone.
3. **This is the default path, not an option to weigh.** Do not stop to ask
   «resume or retry?» — for a detected stall the fresh narrow agent IS the
   procedure. Proceed automatically (reversible, in-scope recovery).
4. **Bounded, then escalate.** At most `ITD_STALL_MAX_RESPAWNS` (default 2) fresh
   respawns per task; still stalling → surface a visible blocker to the user with
   what was and wasn't done — a persistently stuck task is a reported blocker,
   never a silent drop.

Belt-and-suspenders with the hooks: `hooks/narration-final.sh` catches a
verdict-less stop at the subagent boundary; this §9 is the caller-side procedure
when the subagent stalls hard enough that nothing usable comes back at all. The
layers are independent — if a harness drops the hook (best-effort invariant), the
documented fresh-narrow fallback still recovers.

## 10. Out-of-scope findings — chip transport (v1.61.0 — Ось 3)

WIP=1 says an out-of-scope finding spotted mid-task goes to the backlog, not into
the current diff. When the harness offers a task-chip surface (`spawn_task`),
ALSO raise the finding as a chip — the chip **transports** the finding to the
user's UI so it is visible now, it does not REPLACE the durable record.

- **`BACKLOG.md` (or the project's memory backlog) stays the contract.** The
  canonical, vendor-neutral record is the file; the chip is a best-effort
  notification on top. Write the finding to the backlog first, then (if available)
  mirror it as a chip.
- **Fallback:** no chip surface → the backlog file alone, exactly as before. A
  harness that drops `spawn_task` loses visibility, never the finding.
- **Scope, not replacement.** Using chips AS the backlog (dropping the file) stays
  rejected (red-team, egress/durability) — this is the narrower *complement* use,
  the kind of safe adoption the /retro abstention re-review (`itd_ledger_abstentions.py`)
  is meant to surface.

## 11. Declared-source read contract — no silent continuation (v1.77.0 — retro 2026-07-10 №2)

> Замер lost-in-the-middle 2026-07-10: 6 из 21 субагентов, не сумев прочитать
> ЗАЯВЛЕННЫЙ файл инструкций (флаки-путь), молча выполнили задачу из ДРУГИХ
> источников (контекст проекта) — без критического правила и без единого слова
> о подмене. Недоступный источник = тихая потеря правил; молчание неотличимо
> от успеха. Контракт двусторонний:

**Subagent side.** Если промпт называет файл/путь ЕДИНСТВЕННЫМ или обязательным
источником (инструкций, данных, чек-листа), а прочитать его не удалось после
разумных попыток (ретрай Read, Glob по имени рядом):

- НЕ выполняй задачу из других источников и НЕ выдумывай содержимое;
- финальное сообщение начинается строкой `READ_FAILED: <путь>` + одна строка
  «что пробовал»; дальше — только то, что диспетчер явно разрешил как fallback.

**Dispatcher side (дополняет §8).** Называя источник в thin-prompt:

- пометь обязательность («твой ЕДИНСТВЕННЫЙ источник — файл X»);
- продиктуй отказ дословно: «файл не читается → ответь ровно READ_FAILED»;
- получив `READ_FAILED` — почини доступ и перезапусти (в замере виновником был
  UNC-путь `\\wsl.localhost` под конкуренцией; лечение — локальная копия файла);
  ответ, собранный из незаявленных источников, не принимается как результат.

Evidence: в том же замере добавление отказ-инструкции в промпт дало 6/6
корректных прогонов (0 тихих подмен против 6/21 без неё).

## 12. Python в bash-сниппетах скиллов — только через запускатель (v1.83.0 — retro 2026-07-11 P2)

На Windows Git Bash `python`/`python3` указывают на WindowsApps-шим
(Store-заглушку): вызов падает с exit 49, а под пайпом молча отдаёт мусор
(live-инцидент 2026-07-11 — Step 1 `/retro` печатал «Python» вместо скана).
Правило для ЛЮБОГО python-вызова в ```bash-сниппете скилла:

```bash
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
sh "$SHD/itd_py.sh" path/to/script.py args...   # порядок: $ITD_WIN_PYTHON -> python вне WindowsApps -> py -3
```

- Резолвер-строку вставляй в НАЧАЛО каждого shell-вызова (состояние между
  tool-вызовами не живёт) — как с `GT=` в /goal.
- Осознанные исключения помечай маркером `win-ok` на той же строке: цепочки с
  собственным фолбэком до `py -3`/`/tmp`, probes окружения, команды, которые
  записываются в проект пользователя под ЕГО окружение.
- Гейт: `tests/verify_no_bare_python3.py` (fenced bash/sh-блоки skills/**/*.md).
- Хуков это не касается — их интерпретатор жёстко прописан sync-to-active
  (`ITD_WIN_PYTHON` harvest из settings.json).

## 13. WSL-мост из Windows — только через itd_wsl.sh (v1.84.0 — retro 2026-07-11 W1)

Inline-команды `wsl -d <distro> -- sh -c '...'` из Git Bash мнутся по дороге:
MSYS конвертирует ведущие `/пути` (`sh /home/...` → `C:/Program Files/Git/home/...`),
`$(...)`-подстановки и wildcard'ы дают ложные нули и «No such file» на
существующих директориях (воспроизведено ×3 за один день). Правило:

```bash
SHD="skills/_shared"; [ -f "$SHD/itd_wsl.sh" ] || SHD="$HOME/.claude/skills/_shared"
sh "$SHD/itd_wsl.sh" 'cd ~/projects/x && команды с $(...) и wildcard'   # или -f script.sh
```

Хелпер увозит команду в WSL base64-строкой (MSYS её не трогает) и декодирует
уже там; exit-код команды сохраняется. Вне Windows-хоста честно отказывает
(exit 2). Ручной фолбэк прежний: скрипт-файл в репо + `wsl sh -c "sh /абс/путь"`.

## 14. Гейт-статусы грепай точной строкой (v1.84.0 — слабый сигнал №3, урок 2026-07-04)

`grep FINAL` в bash-цепочке НЕ гейтит BLOCKED (подстрока есть в обоих статусах).
Проверяя вердикт meta_review/гейтов в цепочке — грепай точную строку:
`grep -q 'FINAL STATUS: PASSED'` (после squash-найденного urока: цепочка с
`grep FINAL` прошла мимо BLOCKED).

## 15. Границы вместо чекпоинтов (v1.84.0 — дизайн-урок D3, 2026-07-05)

«Add human checkpoints» ≠ harness engineering. Харденя скилл/флоу, сначала
спроси: «закрывает ли это уже механический харнесс?» Правильная форма — границы
в САМОМ харнессе (механические гейты, fire на каждом tool-call, skill-agnostic)
плюс ОДНА жёсткая граница на необратимом крае; НЕ человеческий «да/нет» на
каждом шаге (пойман пользователем как анти-харнесс в 1-м черновике harden
/autopilot).
