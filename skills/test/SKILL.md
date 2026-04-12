---
name: test
description: 'Generate comprehensive tests — unit, integration, edge cases. Detects project test framework and follows existing conventions.'
argument-hint: file, function, or module to test
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash
paths: ["**/test_*.py", "**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx", "**/tests/**", "**/__tests__/**"]
metadata:
  author: HiH-DimaN
  version: 1.3.1
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
