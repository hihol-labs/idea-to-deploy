# ADR-009 — Graph Contract Layer (GENG program), host-neutral, no owned runtime

- **Status:** accepted (user approval 2026-08-10 — approval gate v1.42.0);
  **программа НЕ стартует по результату GATE G0 (вердикт владельца
  2026-08-22) — см. статус-ноту ниже. Решение не отменяется и не
  переписывается: ADR-010, который переписал бы эту запись, был
  предусмотрен только для ветки GO и не создаётся.**
- **Date:** 2026-08-10
- **Review date:** 2026-09-28 — jointly with the ADR-001 review, as proposed in
  the originating Codex (GPT 5.6) session.
- **Amends:** [ADR-001](ADR-001-no-own-runtime.md) — refines, does not revoke:
  ITD still builds no runtime of its own; graph *contracts, policies, and
  proofs* are ITD-owned, graph *execution* stays native to the host.
- **Numbering note (amendment 1):** the originating plan named this record
  "ADR-007". That number was already taken on `main` by
  [ADR-007-human-adjudication-of-independent-review.md](ADR-007-human-adjudication-of-independent-review.md)
  (and by `ADR-007-vendor-neutral-independent-review.md` in the frozen GPG-003
  candidate). The next number, ADR-008, is already reserved by
  `.itd/DECISIONS.md` (entry 2026-08-09) for the deferred
  reviewer-independence-ladder ADR that ADR-007 explicitly defers. The GENG
  decision record therefore takes the next free number after that reservation,
  **ADR-009**. All references to "GENG-ADR" resolve here.

## Статус-нота 2026-08-22 — GATE G0: программа не стартует (GENG-S05)

Программа исполнялась по «Плану GE 2 Final» (решение владельца 2026-08-21) —
value-gated: сначала измерение G0, GO/NO-GO на S05. **Вердикт владельца
2026-08-22 (вариант 1 пакета решения): NO-GO по B и A; C — один bounded-
эксперимент.**

- **GENG-B — NO-GO.** Потолок кэша по 743 квитанциям / 134 юнитам: медиана
  0.00 мин/юнит, p90 0.80, максимум 29.0 при пороге 30; 0 из 134 юнитов
  берут порог. DoD программы §8 «срок окупаемости положительный» по B не
  выполняется до старта.
- **GENG-A — NO-GO** как следствие: по конструкции (роадмап §3) A не
  закрывает ни одной измеренной минуты.
- **GENG-C — один bounded-юнит** (12 пар, default-off, без A и B) через
  обычный `/task`, а не 8 сессий предварительной работы.
- **Остальное — в LPD-003** (план сокращения): fail-fast + targeted вместо
  run-all как оракула; сужение `METHODOLOGY_TREE_ROOTS`; правила остановки
  «находки в САМОЙ правке -> выбросить правку»; консолидация сьютов.

Ключевая поправка к тексту этого ADR: раздел «Decision» строил ценность
GENG-003 на «пере-доказывании всего с нуля на каждом изменении». Замер это
не подтвердил — полный `run-all` на каждом кандидате оказался дефектом
ОБЪЯВЛЕНИЯ оракула (`.itd/VERIFICATION_CONTRACT.json` называет run-all
read-only входом), а не структурной необходимостью: impact-замыкание
`skills/_shared/itd_verification_loop.py` — 13 сьютов из 153, медиана по
репо 2. Пере-доказывание лечится маршрутом, а не контрактным слоем графа.

S06 (ADR-010) и S07 (леджер пула) не открываются. Review 2026-09-28
сохраняется — совместно с ревью ADR-001.

Полный пакет решения с числами, обоснованием и ограничениями честности
замера (вне репо, референс замера): `~/.claude/geng/S05/G0_DECISION_PACKAGE.md`
(+ `cacheable_ceiling.py` — воспроизводимый расчёт); замеры
`~/.claude/geng/S02/BASELINE_G0.md`, `~/.claude/geng/S04/BASELINE_POST_R6.md`,
`~/.claude/geng/S04b/ROUNDS.md`. Запись вердикта: `.itd/DECISIONS.md`
(2026-08-22).

## Context

Advisory session 2026-08-07 (`/advisor`; business-analyst
PASSED_WITH_WARNINGS, devils-advocate BLOCKED for any runtime-owning variant)
analyzed the proposal to bring Graph Engineering into idea-to-deploy, against
five public sources (LangChain "3 Years of Graph Engineering", the Claude
dynamic-workflows blog, a deep-research workflow gist, Anthropic Institute
RSI, 0xCodez "14-step Graph Engineering"). In a parallel Codex (GPT 5.6)
session the user approved **variant B: "Codex-first host-neutral Graph
Contract Layer"**, program **GENG-000 … GENG-010**, and then approved three
amendments to that plan (recorded 2026-08-07 in project memory,
`project_geng_plan_amendments.md`). Formalization was deliberately deferred
until GPG-004 closed (WIP=1, Scope Lock); GPG-004 is `verified` and released
in v1.96.0, so the deferral condition is met.

Host constraints confirmed against the harness contract: dynamic-workflow
concurrency min(16, cores−2), 1000-agent ceiling, resume only within the same
session ⇒ a host checkpoint is a cache, never canonical durability.

## Decision

Adopt the Graph Contract Layer under these locked invariants:

1. **No owned graph runtime.** ITD owns graph contracts, policies, and proof
   formats; execution is native to the host (per ADR-001).
2. **Proposal ≠ authorization.** Claude/Codex may *propose* a graph; only the
   human authorizes, and authorizes an **exact `graphDigest`**.
3. **Verification Loop stays the single completion authority.** No graph
   mechanism mints `verified`.
4. **Durability lives in `.itd-memory` + receipts.** Host checkpoints are
   cache only.

### Amendment 2 — entry criterion for GENG-004 (Codex Shadow Mode)

GENG-004 may not start until the **Codex isolated transport is demonstrably
stable**, established by a dedicated transport-stability check (repeated
clean isolated-transport passes), not inferred from unit closure. The
GPG-004 U8 line is closed, but its closure criterion was acceptance on one
exact candidate via a human-adjudicated route — that closure does not itself
certify transport stability. Rationale: 13 probes showed non-deterministic
Codex transport failure depending on the shape of `CODEX_HOME`; the
mechanism remains unknown and is not to be guessed at. Until the dedicated
check passes, the **serial fallback is first-class**, not an emergency path.

### Amendment 3 — incremental proof graph as a separate GENG-003 exit criterion

GENG-003 is not done without **content-addressed node receipts** binding:
graph version + node version + input digest + dependency digests + policy
digest + candidate/tree + provenance — with **downstream-only invalidation**
(a changed node re-proves itself and its descendants, nothing upstream).
The **final integration oracle always runs over the single exact candidate**;
node-level receipts never substitute for it. This is the element that
addresses the pain of multi-day runs re-proving everything from scratch.

## Alternatives considered

- **ITD-owned graph runtime / scheduler** — rejected (devils-advocate
  BLOCKED): contradicts ADR-001, the harness-best-effort invariant, WIP=1,
  and exact-candidate adjudication. Also already in the BACKLOG icebox
  ("Ralph or any ITD-owned scheduler/runtime").
- **Do nothing (no graph work)** — rejected: multi-day proof runs re-execute
  the full ladder on every change; the contract layer attacks that cost
  without new runtime surface.
- **Keep the plan's original "ADR-007" number** — rejected: collides with the
  merged ADR-007 on `main`.

## Consequences

- **Positive:** graph work becomes plannable as ordered GENG units under the
  existing /goal + Verification Loop machinery; incremental proof receipts
  bound re-verification cost; the transport entry criterion prevents building
  Shadow Mode on a flaky channel.
- **Negative / cost:** proof-graph receipt schemas are new security-relevant
  surface; contract-only ownership means host behavior changes can still
  invalidate assumptions (mitigated by the best-effort invariant: a missing
  host feature degrades to the serial path, never to a false green).
- **Risks:** Codex transport root cause stays unknown — GENG-004 may stay
  gated for a long time; that is intended fail-closed behavior.

## Follow-up

The full GENG-000…GENG-010 unit text lives in the two originating session
transcripts and project memory; it enters the repo as a `/goal` unit ledger
when GENG-000 (Harness Readiness Freeze) is started as the next unit after
the currently queued GPG follow-ups (U6/U16/U17). No GENG code before that.

**Отменено результатом GATE G0 (2026-08-22):** GENG-000 не стартует,
GENG-000…GENG-010 (variant B) уходит в BACKLOG icebox. Из программы остаётся
единственный bounded-юнит GENG-C-EXP (12 пар, default-off), который идёт через
обычный `/task` и не импортирует текст программы. См. статус-ноту выше.
