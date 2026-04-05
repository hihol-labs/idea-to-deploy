---
name: test
description: Generate comprehensive tests for code — unit, integration, edge cases. Detects the project's test framework and follows existing conventions. TRIGGER when user says "напиши тесты", "покрой тестами", "add tests", "test this", or after writing new code, implementing a feature, or fixing a bug. Always run this after significant code changes.
argument-hint: file, function, or module to test
license: MIT
effort: medium
paths: ["**/test_*.py", "**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx", "**/tests/**", "**/__tests__/**"]
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: testing
  tags: [unit-tests, integration-tests, edge-cases, tdd]
---


# Test

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
