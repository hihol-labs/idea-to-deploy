---
name: test
description: 'Generate comprehensive tests — unit, integration, edge cases. Detects project test framework (pytest/vitest/jest/go test) and follows existing conventions. TRIGGER when user says "напиши тесты", "покрой тестами", "добавь тесты", or after writing new code / fixing a bug. Generating a regression test for a fix is part of finishing the fix. See `## Trigger phrases` in body for full list.'
argument-hint: file, function, or module to test
license: MIT
paths: ["**/test_*.py", "**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx", "**/tests/**", "**/__tests__/**"]
metadata:
  author: HiH-DimaN
  version: 1.2.0
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

## Troubleshooting

### Tests pass locally but fail in CI
Check for environment differences: timezone, locale, file paths, database state. Use `freezegun` or `vi.useFakeTimers()` for time-dependent tests.

### Can't mock a dependency
If the dependency is tightly coupled, consider refactoring to accept it as a parameter (dependency injection) before writing tests.

### Flaky tests (pass sometimes, fail sometimes)
Common causes: shared state between tests, time-dependent logic, race conditions. Fix: isolate each test, use deterministic data.
