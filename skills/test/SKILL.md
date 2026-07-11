---
name: test
description: 'Generate comprehensive tests — unit, integration, edge cases. Detects project test framework and follows existing conventions.'
argument-hint: file, function, or module to test
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  effort: medium
  side_effect: command-execution
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.5.0
  category: testing
  tags: [unit-tests, integration-tests, edge-cases, tdd]
---


# Test


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- напиши тесты, покрой тестами, добавь тесты, нет тестов, добавь покрытие
- coverage, юнит-тесты, интеграционные тесты, регрессионный тест
- pytest, vitest, jest, go test, RSpec
- add tests, test this, generate tests
- автоматически после нового кода или после фикса бага

## Recommended model

**sonnet** — Pattern-matching against existing test conventions. Sonnet covers all major frameworks. Opus only adds value when designing test strategy for very complex domain logic.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 1: Detect test framework
Check the project for existing test setup:

```bash
# Look for test config
ls jest.config* vitest.config* pytest.ini pyproject.toml conftest.py
# Look for existing tests
ls -d tests/ __tests__/ *.test.* *.spec.*
```

If none found, ask the user which framework to use.

For idiomatic patterns in each major framework (pytest fixtures, vitest mocks, jest snapshots, go test table-driven, React Testing Library) — consult `references/test-frameworks.md`. It also covers detection priority, edge-case checklist (empty/boundary/unicode/concurrent/auth), coverage targets per project type, and what NOT to test.

### Step 2: Analyze the code
Read the target file/function. Identify:
- Public API surface (what to test)
- External dependencies (what to mock)
- Edge cases (what can go wrong)

### Step 3: Write tests

Cover these categories:
- **Happy path** — normal expected behavior
- **Edge cases** — empty input, null, zero, max values, unicode, special chars
- **Error cases** — invalid input, network failures, timeouts
- **Boundary conditions** — off-by-one, limits, overflow

Follow quality rules:
- Each test tests ONE thing with a clear name describing the behavior
- Use Arrange-Act-Assert pattern
- Avoid testing implementation details — test behavior
- Use realistic test data, not "foo" / "bar"
- Mock external dependencies only, not internal code

### Step 3.5: Eval-suite branch — for AI/LLM/agent code (opt-in, scoped — New-SDLC port, v1.31.0)

**Trigger this branch only when** the code under test itself calls an LLM/agent or
produces non-deterministic output (`side_effect: agent`/`command-execution` with an
LLM in the loop), OR the user explicitly asks for an eval. For ordinary
deterministic code (CRUD, pure functions, UI), **skip this branch entirely** — the
normal Steps 3–6 are sufficient.

Why this exists: tests assert *deterministic* contracts (same input → same output).
LLM/agent outputs are *non-deterministic* — a passing unit test says nothing about
whether the model's answer is actually good. The discipline that covers that gap is
an **eval**: a rubric + a judge + (for multi-step agents) a trajectory check. Without
both, shipping an AI feature is still vibe coding. (Source: Google "The New SDLC With
Vibe Coding", 2026 — evals are the non-deterministic counterpart to tests.)

**This is opt-in and scoped — NOT a global gate.** It never blocks a commit and never
runs for non-AI projects. (Deliberate: a hard global eval gate would falsely block
ordinary work — the same failure mode that retired the score≥7 gate and the
acceptance-gate experiment. Eval signal is generated and made visible, not enforced.)

Generate the eval-suite **into the user's project** (an `evals/` dir), never into the
methodology repo. Three artifacts (see `references/test-frameworks.md` →
"LLM / agent eval patterns" for full templates):

1. **`evals/<feature>.rubric.md`** — the scoring rubric: 3–7 binary or 1–5 scaled
   criteria the output must satisfy (e.g. for a product-card generator: *factually
   grounded in the source SKU, no hallucinated specs, on-brand tone, within length,
   valid target language*). The rubric is the contract — "an eval without a clear
   rubric measures nothing."
2. **`evals/<feature>.judge.py`** (or `.ts`) — an **LM-judge stub**: feeds (input,
   output, rubric) to a judge model and returns per-criterion pass/score + rationale.
   Stub, because the project wires its own model client; ships the prompt + parsing
   shape, marked `TODO: wire model client`.
3. **`evals/<feature>.trajectory.json`** — a **trajectory-eval scaffold** for
   multi-step agents only (auto-buying, reconciliation, customer-service loops):
   golden input → expected tool-call sequence / decision checkpoints, so a regression
   in the agent's *path* (not just final answer) is caught.

Set a regression threshold (e.g. "judge pass-rate must stay ≥ baseline") and record
it next to the rubric — but enforcement is the project's CI choice, not this skill's.

**Memory-quality dimension (stateful agents — Day-3 port, v1.32.0).** If the agent has
long-term memory, add memory-specific criteria to the rubric: *recall* (the right past
fact is retrieved when relevant), *freshness* (stale records are not used past their
TTL), *consolidation correctness* (merging duplicates/contradictions does not corrupt a
fact), and *no poisoning* (untrusted input does not become a trusted memory). These are
eval criteria, not unit tests — memory quality is non-deterministic like any LLM output.

The same fail-closed rule (Step 5) applies: an eval reported `passed` requires an
actual judge run with visible output. "I wrote a rubric" is not an eval pass.

### Step 4: Place tests
Follow the project's existing conventions:
- Co-located: `src/utils/parse.test.ts` next to `src/utils/parse.ts`
- Separate dir: `tests/test_parse.py` for `src/parse.py`

### Step 5: Run and verify

```bash
pytest tests/test_new.py -v        # Python
npx vitest run src/new.test.ts     # Vitest
npx jest src/new.test.ts           # Jest
```

All tests must pass before finishing.

**Fail-closed verification (v1.21 — PFO port):** a verification status of `passed` requires *evidence you actually produced* — a real test run with visible output. If the suite was not run, the command errored, or the output is ambiguous, the status is **not** `passed`; report it as a blocker (`RECOVERY_REQUIRED`), not as success. "I wrote tests that should pass" is not a pass. This mirrors `.itd/VERIFICATION_CONTRACT.json` (`failClosed`): missing or un-run verification can never be reported green.

**TDD evidence gate (v1.21 — PFO port):** for a behavior change (new feature or bugfix), prefer writing the test **first** and capturing red→green evidence: the test fails on the old code, passes on the new. Note both states explicitly ("red: AssertionError … → green: 1 passed"). When red-first is genuinely impractical (UI glitch, race condition, env-specific bug), state that exception explicitly rather than silently skipping it.

### Step 5.5: Refute pass — mutation-check each new test before you trust it as coverage (v1.60.0 — Ось 2, agentic engineering)

The refute pass from `/review` Step 2.6, applied to the test verify fleet. Here
the "finding" is a new test's implicit claim «this asserts real behavior». A
test that passes on BOTH the correct and the broken code is vacuous coverage — a
green that proves nothing and lies to every later reader. This pass adversarially
challenges that claim before the suite's green is trusted.

For each **behavior-asserting** test just written (not trivial getters /
formatting / snapshot-only tests), run a **fresh** mutation check: break the code
path the test claims to cover — invert a condition, drop a guard, return a wrong
constant (or dispatch `Agent(subagent_type: "test-generator", …)` with a refute
prompt to attempt it) — and confirm the test now **FAILS**. A test that stays
green under the mutation is **refuted as meaningful coverage**. This is the
red→green TDD gate (Step 5) run in reverse: green→red-under-mutation. **Default
to `refuted: true` under uncertainty** — if you cannot make the test fail by
breaking what it supposedly checks, treat its coverage claim as unproven.

- Refuted (survives the mutation) → the test is vacuous: fix it (tighten the
  assertion) or drop it; do not count it as coverage.
- Confirmed (fails under mutation) → real coverage, keep it.
- **Trivial / non-behavioral tests are NOT mutation-checked** — the cost is not
  justified.

**Invariant:** the refute pass can only REMOVE vacuous tests from the trusted
coverage set; it never fabricates a passing test and never reports mutation
evidence it did not actually run. When a real mutation run is impractical
(env-specific, flaky), state that exception explicitly rather than silently
claiming the coverage is proven — same honesty rule as the TDD gate above.

### Step 6: Mark `/test` as done for this session (v1.23.0)

Final step of every `/test` invocation, **after the suite has actually run and passed** (see the fail-closed gate above). Write a session marker so `hooks/check-dod-before-commit.sh` knows `/test` was run — this is what unblocks a `git commit` the DoD gate flags as test-requiring (DB migrations, brand-new source files). The sentinel asserts "tests were run this session", so only write it when verification genuinely passed — never to silence the gate.

```bash
# Dual-write (/tmp + platform temp) — см. v1.42.0 platform symmetry
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || python -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"  # win-ok: цепочка падает в /tmp (шим exit!=0)
mkdir -p /tmp 2>/dev/null || true
echo "$(date +%s)" | tee "/tmp/claude-test-done-${CLAUDE_SESSION_ID:-$$}" > "$tmpd/claude-test-done-${CLAUDE_SESSION_ID:-$$}" 2>/dev/null || echo "$(date +%s)" > "$tmpd/claude-test-done-${CLAUDE_SESSION_ID:-$$}"
```

The marker is session-scoped and lives in `/tmp`, so it auto-expires at reboot and does not leak between sessions. The `Skill` tool does not route through `PreToolUse` hooks, so this in-skill write is the only reliable signal that `/test` ran.

## Examples

### Example 1: Test a utility function
User says: "напиши тесты для src/utils/formatPrice.ts"

Result:
```typescript
describe("formatPrice", () => {
  it("formats integer price with currency symbol", () => {
    expect(formatPrice(1000, "RUB")).toBe("1 000 ₽");
  });

  it("handles zero", () => {
    expect(formatPrice(0, "RUB")).toBe("0 ₽");
  });

  it("handles decimal prices", () => {
    expect(formatPrice(99.9, "USD")).toBe("$99.90");
  });

  it("throws on negative price", () => {
    expect(() => formatPrice(-1, "RUB")).toThrow();
  });
});
```

### Example 2: Test an API endpoint
User says: "покрой тестами POST /api/orders"

Result: Tests for valid creation, missing fields, unauthorized access, duplicate prevention.

## Rules

1. Тестируй поведение, а не реализацию — тест проверяет ЧТО функция делает (вход → выход), а не КАК (порядок внутренних вызовов, приватные методы). Рефакторинг не должен ломать тесты
2. Следуй конвенциям проекта — если в проекте pytest с fixtures в conftest.py, не создавай unittest.TestCase. Если тесты в `tests/`, не клади их рядом с кодом
3. Edge cases обязательны — пустой ввод, null/None, граничные значения, unicode, спецсимволы, максимальные размеры. Happy path без edge cases — неполное покрытие
4. Один тест = одно утверждение о поведении. Имя теста описывает проверяемое поведение: `test_expired_token_returns_401`, не `test_auth_3`
5. Используй реалистичные данные — `"Иван Петров"` вместо `"foo"`, `"user@example.com"` вместо `"test"`. Мокай только внешние зависимости (HTTP, DB, файловая система), не внутренний код
6. Все тесты должны проходить перед завершением скилла — если тест падает, это баг в тесте или в коде, разберись и исправь

## Self-validation

Before presenting tests to user, verify:
- [ ] Tests actually run and pass (execute test suite)
- [ ] Tests cover the specific functionality requested by user
- [ ] Both happy path and edge cases included
- [ ] Test naming follows project conventions
- [ ] No tests depend on external services without mocks
- [ ] Test file location follows project structure conventions

## Troubleshooting

### Tests pass locally but fail in CI
Check for environment differences: timezone, locale, file paths, database state. Use `freezegun` or `vi.useFakeTimers()` for time-dependent tests.

### Can't mock a dependency
If the dependency is tightly coupled, consider refactoring to accept it as a parameter (dependency injection) before writing tests.

### Flaky tests (pass sometimes, fail sometimes)
Common causes: shared state between tests, time-dependent logic, race conditions. Fix: isolate each test, use deterministic data.
