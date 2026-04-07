# Test Framework Conventions

> Reference for `/test` skill. The skill detects which framework the project uses and follows existing conventions. This file documents the **idiomatic patterns** for each major framework so generated tests look native.

## Detection order

The skill detects the framework by checking files in this order:

| Framework | Detection signal |
|---|---|
| pytest | `pytest.ini`, `pyproject.toml` with `[tool.pytest]`, or `conftest.py` |
| unittest | Python project without pytest config but with `tests/` containing `unittest.TestCase` |
| vitest | `vitest.config.ts`, `vite.config.ts` with `test:` block, or `package.json` with `"vitest"` dep |
| jest | `jest.config.js`, `package.json` with `"jest"` dep, or `__tests__/` |
| go test | `*_test.go` files |
| cargo test | `Cargo.toml` |
| rspec | `Gemfile` with `rspec`, `spec/` folder |

If multiple frameworks detected, prefer the one with more existing tests.

---

## pytest (Python)

### File layout
```
src/myapp/
  user.py
tests/
  test_user.py
  conftest.py        # shared fixtures
```

### Test naming
- File: `test_<module>.py`
- Function: `test_<scenario>_<expected>`
- Example: `def test_create_user_with_invalid_email_raises():`

### Fixtures
```python
import pytest

@pytest.fixture
def user():
    return User(email="alice@example.com", name="Alice")

@pytest.fixture
def db(tmp_path):
    """Fresh SQLite db per test."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()

def test_save_user(db, user):
    save_user(db, user)
    assert load_user(db, user.id) == user
```

### Parametrize
```python
@pytest.mark.parametrize("email,is_valid", [
    ("alice@example.com", True),
    ("no-at-sign", False),
    ("", False),
    (None, False),
])
def test_email_validation(email, is_valid):
    assert validate_email(email) == is_valid
```

### Async tests
```python
import pytest

@pytest.mark.asyncio
async def test_fetch_user():
    user = await fetch_user(123)
    assert user.id == 123
```
Requires `pytest-asyncio`. Add `asyncio_mode = "auto"` to `pytest.ini`.

### Mocking
```python
from unittest.mock import patch, Mock

@patch("myapp.user.send_email")
def test_create_user_sends_welcome(mock_send):
    create_user("alice@example.com")
    mock_send.assert_called_once_with("alice@example.com", template="welcome")
```

---

## vitest (TypeScript / Vite)

### File layout
```
src/
  user.ts
  user.test.ts       # next to source
```
or
```
src/user.ts
tests/user.test.ts
```

### Test naming
- File: `<module>.test.ts` or `<module>.spec.ts`
- Block: `describe('<unit>', () => { it('<behavior>', () => {}) })`

### Basic test
```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { createUser } from './user'

describe('createUser', () => {
  it('returns a user with the given email', () => {
    const user = createUser({ email: 'alice@example.com' })
    expect(user.email).toBe('alice@example.com')
  })

  it('throws on invalid email', () => {
    expect(() => createUser({ email: 'invalid' })).toThrow(/invalid email/i)
  })
})
```

### Mocking
```ts
import { vi } from 'vitest'

vi.mock('./email-service', () => ({
  sendEmail: vi.fn().mockResolvedValue({ id: 'msg-1' }),
}))

import { sendEmail } from './email-service'
import { createUser } from './user'

it('sends welcome email', async () => {
  await createUser({ email: 'alice@example.com' })
  expect(sendEmail).toHaveBeenCalledWith('alice@example.com', 'welcome')
})
```

### Snapshot
```ts
it('renders the user card', () => {
  const html = renderUserCard({ name: 'Alice' })
  expect(html).toMatchSnapshot()
})
```

### Async
```ts
it('fetches user', async () => {
  const user = await fetchUser(123)
  expect(user.id).toBe(123)
})
```

---

## jest (Node / React)

Almost identical to vitest API. Key differences:

| Feature | jest | vitest |
|---|---|---|
| Mocking | `jest.mock(...)` | `vi.mock(...)` |
| Spy | `jest.fn()` | `vi.fn()` |
| Auto-reset | `jest.config.js: clearMocks: true` | `vitest.config.ts: clearMocks: true` |
| ESM | needs babel/swc config | native |
| Speed | slower (Node-based runner) | faster (Vite-based) |

If both work, **prefer vitest** for new TypeScript projects (faster, native ESM, simpler config).

### React Testing Library (works with both)
```ts
import { render, screen, fireEvent } from '@testing-library/react'
import { LoginForm } from './LoginForm'

it('shows error on empty submit', async () => {
  render(<LoginForm onSubmit={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: /войти/i }))
  expect(await screen.findByText(/email обязателен/i)).toBeInTheDocument()
})
```

---

## go test

### File layout
```
user.go
user_test.go    # same package, _test.go suffix
```

### Basic test
```go
package user

import "testing"

func TestCreateUser(t *testing.T) {
    u, err := Create("alice@example.com")
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if u.Email != "alice@example.com" {
        t.Errorf("expected alice@example.com, got %s", u.Email)
    }
}
```

### Table-driven (idiomatic in Go)
```go
func TestValidateEmail(t *testing.T) {
    tests := []struct {
        name  string
        input string
        want  bool
    }{
        {"valid", "alice@example.com", true},
        {"no @", "noatsign", false},
        {"empty", "", false},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := ValidateEmail(tt.input)
            if got != tt.want {
                t.Errorf("got %v, want %v", got, tt.want)
            }
        })
    }
}
```

### Subtests + parallel
```go
func TestParallel(t *testing.T) {
    t.Parallel()
    // ...
}
```

### Race detector
Always run `go test -race ./...` in CI.

### Mocking
Go has no built-in mocking; common approaches:
1. **Interfaces** — define interface, swap real impl with test impl
2. **`gomock`** — mockgen generates mocks from interfaces
3. **`testify/mock`** — runtime mocks

Idiomatic Go prefers interface-based test doubles over runtime mocks.

---

## Edge cases to always test

For every public function or endpoint, generate tests covering:

| Category | Examples |
|---|---|
| Happy path | Normal valid input → expected output |
| Empty input | `""`, `[]`, `{}`, `None`/`null`, `0` |
| Boundary | min/max length, just-below/just-above limits |
| Wrong type | Number where string expected, etc. |
| Unicode | Emoji, RTL text, combining marks (`café` two ways) |
| Very large | 1MB string, 10000-item array |
| Concurrent | Two writes at once (if applicable) |
| Auth boundary | Authorized user, unauthorized user, wrong role |
| Network failure | Mocked timeout, 500 from upstream |

For each test, follow **Arrange–Act–Assert** structure:
```python
def test_create_order_with_negative_total_rejects():
    # Arrange
    user = make_test_user()
    cart = make_cart(items=[Item(price=-5)])

    # Act
    result = create_order(user, cart)

    # Assert
    assert result.error == "negative_total_not_allowed"
    assert Order.objects.count() == 0
```

---

## Coverage targets

| Project type | Suggested coverage floor |
|---|---|
| Library / SDK | 90%+ (public API users depend on it) |
| Web backend | 70–80% (integration tests cover gaps) |
| Frontend SPA | 60–70% (UI tests expensive) |
| CLI tool | 80%+ |
| Prototype / spike | 40%+ |

**100% coverage is a smell**, not a goal — it usually means tests for trivial getters and setters that catch nothing.

---

## What NOT to test

- Framework code (`React.useState` works)
- Trivial getters/setters
- Constants and config files
- Auto-generated code (migrations, OpenAPI clients)
- Third-party libraries (test the integration boundary, not the lib)

---

## Test isolation rules

1. **Each test must run independently** — no test depends on the previous one passing
2. **Order shouldn't matter** — if reordering breaks tests, you have hidden state
3. **No shared mutable state** — fresh fixtures per test
4. **Database in transaction** — wrap each test in a transaction that rolls back
5. **No real network calls** — mock everything; one integration test path is fine
6. **No real time** — freeze time with `freezegun` (Python) or `vi.useFakeTimers()` (vitest)
