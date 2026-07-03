# Fixture 31 — /goal

A user has a goal that is too big for one session (brownfield: e.g. "the payment
calendar forecasts all outflows of the org with ≥91% accuracy") and wants the
methodology to (a) decompose it into verifiable units, (b) drive the units one at
a time through the standard pipeline, and (c) survive session death — a fresh
session resumes from the first non-verified unit instead of re-deriving the plan.

Sample prompts that should route here:
- "поставь цель: календарь прогнозирует все выплаты с точностью 91%"
- "ставлю цель: закрыть Этап 1 автонаполнения календаря"
- "работаем в режиме цели, декомпозируй цель на юниты"
- "продолжай цель" (в проекте уже есть .itd-memory/GOAL.json)
- "goal mode: ship self-serve password reset end-to-end"
- "goal mode: resume"

Expected behavior: `/goal` checks for an existing `.itd-memory/GOAL.json` first
(resume, never recreate); otherwise decomposes the goal into ordered units with
binary criteria + verificationCommand, shows the decomposition and WAITS for
explicit user approval; then drives the first pending unit through the standard
`/task` pipeline (scope → plan → code → /test → /review) at WIP=1, flips it to
`verified` only with evidence, logs unit events to `events.jsonl` (VCR counts
goal work automatically), and moves to the next unit. It is NOT a gate and never
bypasses `/review` or the DoD; it must work on brownfield projects (its main
case) and must NOT be suppressed by the brownfield profile.
