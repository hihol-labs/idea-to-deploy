# Fable 5 / harness-native feature ledger

Единый проверяемо-полный реестр **харнесс-нативных фич** (Claude Code / Fable 5
surface, а также codex / gemini) и осознанного решения методологии по каждой:
**adopt** или **abstain**, с **evidence** (реальный артефакт в этом репо) и
**fallback** — vendor-нейтральным путём, который включается, если фича исчезла
или недоступна.

Реестр консолидирует то, что раньше было разбросано: invariant-блок
`docs/templates/global-claude-md.md` («Harness-native features — best-effort
invariant»), Fable-релизы A–D в `CHANGELOG.md` и пересечения с
`docs/DESIGN_SPACE.md` (K-принципы). До этого фичи были *name-dropped*; здесь
каждая — *сознательно решена с обоснованием*.

## Потолок (явно)

**Цель оси — ~9/10, НЕ 10.** Литеральное «методология вобрала ВСЁ» = 10 — **это
не цель**. Ценность — в осознанном adopt/abstain с evidence и доказанным
fallback'ом, а не в ширине абсорбции. Абстенция с обоснованием — такой же
результат, как адопция. Последние 0.5–1 балла до 10 = внешнее evidence / red-team,
а не добор фич. (Инвариант: харнесс-фича может *транспортировать* контракт, но
никогда *быть* им — контракт остаётся vendor-нейтральным.)

## Легенда

- **Решение** — `adopt` (вписано в методологию) или `abstain` (сознательно не
  берём; для egress/mutation-фич — по red-team или data-sensitive gate).
- **Evidence** — путь к реальному артефакту в репо, подтверждающему решение.
- **Fallback** — vendor-нейтральный путь; при «тихом исчезновении» фичи система
  деградирует сюда, а не в ложное «all green».

## Реестр

| # | Фича | Решение | Evidence | Fallback (vendor-neutral) |
|---|---|---|---|---|
| F-01 | Субагенты / Task-tool (summary-only returns) | adopt | `docs/DESIGN_SPACE.md` (K9) | Инлайн-работа в основном контексте без fork'а |
| F-02 | PreToolUse-хуки (гейты + zero-context напоминания) | adopt | `docs/HARNESS_ENGINEERING_MAP.md` | Текстовые напоминания внутри `SKILL.md` |
| F-03 | SubagentStop-хук (авто-дожатие нарратив-финала) | adopt | `hooks/narration-final.sh` | Ручной re-ping «выдай итог одним сообщением» |
| F-04 | Inter-agent messaging / авто-пинг-за-вердиктом (SendMessage) | adopt | `tests/verify_review_autoping.py` | Ручной re-ping вердикта в прозе |
| F-05 | git worktree isolation (file-only refactor) | adopt | `skills/refactor/references/worktree-isolation.md` | `hooks/freeze.sh` scope-guard |
| F-06 | Cross-vendor external CLI (Codex / Gemini) | adopt | `docs/adr/ADR-002-cross-review-opt-in-precommit.md` | Native Claude red-team self-review (`skills/cross-review/SKILL.md`) |
| F-07 | Execution tracing (PreToolUse jsonl-trace, K15) | adopt | `hooks/execution-trace.sh` | Post-hoc `/session-save` summary + cost-tracker |
| F-08 | On-disk unit ledger (GOAL.json, append-only) | adopt | `skills/goal/SKILL.md` | `session_*.md` proza-заметки |
| F-09 | Model routing / per-role effort tiers | adopt | `docs/MODEL-ROUTING-POLICY.md` | Единая дефолт-модель |
| F-10 | Machine-readable DoD / structured contract | adopt | `docs/templates/itd/VERIFICATION_CONTRACT.json` | Проза done-signal в `SKILL.md` |
| F-11 | Fresh narrow agent как fallback при столле | adopt | `skills/_shared/helpers.md` (§9) | Ручной перезапуск сессии человеком |
| F-12 | Context-budget nudge (compaction awareness) | adopt (partial) | `hooks/context-budget.sh` | `context-aware.sh` 40-prompt nudge → `/session-save` |
| F-13 | Typed / structured tool-call outputs | adopt (transport only) | `docs/templates/global-claude-md.md` (invariant) | Text/JSON в транскрипте — контракт vendor-нейтрален |
| F-14 | Artifact publishing (egress отчётов review/retro) | abstain | `CHANGELOG.md` (red-team: secret egress) | Findings остаются в репо (`claude-*.md` notes / транскрипт) |
| F-15 | Background agents с mutation-правами | abstain | `docs/templates/global-claude-md.md` (invariant: read-only reporters) | Read-only reporter + human-approved mutation (data-sensitive gate) |
| F-16 | spawn_task chips как замена BACKLOG.md | abstain | `CHANGELOG.md` (red-team) | `BACKLOG.md` файл в репо |
| F-17 | Transcript search / mining к внешней модели | abstain | `docs/DESIGN_SPACE.md` (K10 file-based memory) | `MEMORY.md` pointer-index + `session_*.md` |
| F-18 | Graduated compaction / context budgeting (full, K4) | abstain (defer) | `docs/DESIGN_SPACE.md` (§5.2, ROADMAP DEFERRED) | `hooks/context-budget.sh` + `/session-save` nudge |
| F-19 | On-disk checkpoints помимо git (K16) | abstain (defer) | `docs/DESIGN_SPACE.md` (§5.8) | git commits/branches + `/migrate` `/tmp` backup |
| F-20 | Graduated trust / 7 permission modes (K1) | abstain | `docs/DESIGN_SPACE.md` (§5.1) | `hooks/careful.sh` / `hooks/freeze.sh` + explicit confirm на `/deploy`,`/migrate` |

Все 5 фич, названных в invariant-блоке — **typed tool-calls** (F-13), **chips**
(F-16), **artifacts** (F-14), **background agents** (F-15), **transcript search**
(F-17) — присутствуют строкой.

## Как реестр остаётся полным

- **G-002 drift-guard** (`tests/verify_feature_ledger_completeness.py`): каждый
  харнесс-фича-токен, name-dropped в invariant-блоке И в Fable-секциях
  `CHANGELOG.md`, обязан иметь строку здесь. Новый name-drop без строки → FAIL.
- **G-003 fixture-proof** (`tests/verify_feature_ledger_fallbacks.py`):
  симулирует «фича отсутствует» и ассертит, что включается именно задекларированный
  здесь fallback (минимум F-05 worktree→freeze, F-06 cross-review→native).
- **G-004 ре-review абстенций** (`/retro`): периодически поднимает `abstain`-строки —
  «не появился ли безопасный юз?».

При добавлении/изменении харнесс-фичи или закрытии gap'а — правь строку здесь и
синхронно её evidence/fallback.
