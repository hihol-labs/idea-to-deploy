# Fixture 10 — /task router

Thin fixture to verify the `/task` daily-work router correctly delegates to the right implementation skill based on user signals, matching the routing matrix in `skills/task/references/routing-matrix.md`.

This fixture is intentionally minimal: the router itself doesn't generate code, it just picks the target skill and invokes it via the Skill tool. The downstream skills (`/bugfix`, `/refactor`, `/perf`, `/doc`, `/test`, `/review`, etc.) are already covered by `fixture-07-daily-work-skills` and their own fixtures — we don't duplicate those checks here.

## Context for the router

Imagine a user with an existing project at `/home/user/projects/example` running on production. They come with one of several types of ambiguous or specific maintenance requests. The router should:

1. **Specific phrasings** — invoke the target skill directly, skipping the routing question
2. **Ambiguous phrasings** — ask the routing question once, then dispatch
3. **Context-obvious cases** — infer from `git status` / `MEMORY.md` and dispatch silently
4. **Out-of-scope** — redirect to `/project` (new project) or decline gracefully

## Routing scenarios

See `notes.md` for the full checklist.

### Scenario A — ambiguous tech debt
User says: «у меня NeuroExpert в проде, надо закрыть tech debt с deploy.sh — kong.yml слетает при rsync». Expected: `/task` infers **refactoring** (extract inline envsubst → reusable script) and invokes `/refactor` with a brief explanation.

### Scenario B — direct skill phrasing
User says: «эндпоинт `/users/{id}/orders` тормозит, профилируй». Expected: `/task` skips the routing question and invokes `/perf` directly.

### Scenario C — multi-step chain
User says: «есть задача: сначала отрефактори process_checkout, потом добавь тесты, потом сделай review». Expected: `/task` sequences `/refactor` → `/test` → `/review`, saving context between via `/session-save` if the chain is long.

### Scenario D — out of scope (new project)
User says: «хочу новый проект — CRM для фитнес-клубов». Expected: `/task` recognizes this is a creation request and redirects to `/project` without running any daily-work skill.
