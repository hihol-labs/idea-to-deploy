# Debugging Patterns by Language and Stack

> Reference for `/debug` skill. The skill body covers the universal 6-step process (Reproduce → Locate → Understand → Fix → Verify → Prevent). This file covers **language-specific tools and idioms** so debugging works the same way regardless of stack.

## Python

### Inspecting state
```python
# pdb breakpoint (Python 3.7+)
breakpoint()

# Print variables with names (3.8+ f-string =)
print(f"{user_id=} {order_total=}")

# Pretty-print
from pprint import pprint
pprint(complex_dict)
```

### Stack traces
```python
import traceback
try:
    risky_call()
except Exception as e:
    traceback.print_exc()  # full trace
    # or get as string:
    tb = traceback.format_exc()
```

### Common pitfalls
- **Mutable default arguments** — `def f(items=[]):` shares the list across calls. Use `def f(items=None): items = items or []`.
- **Late binding in closures** — `[lambda: i for i in range(3)]` all return 2. Capture with `[lambda i=i: i for i in range(3)]`.
- **Async — forgotten await** — `result = async_func()` returns coroutine, not result. Always `await async_func()`.
- **`is` vs `==`** — `is` compares identity; for value comparison use `==`. CPython interns small ints/strings, so `x is 256` may work but `x is 257` may not.

### Tools
- `pytest --pdb` — drop into pdb on first failure
- `pytest -x` — stop on first failure
- `python -X dev your_script.py` — enables development mode (DeprecationWarnings, asyncio debug, etc.)
- `python -m trace --trace your_script.py` — line-by-line execution log

---

## JavaScript / TypeScript

### Inspecting state
```js
// Modern: Object shorthand for logging
console.log({ userId, orderTotal })

// Conditional break
debugger  // halts in DevTools / VSCode

// Stringify circular structures
const seen = new WeakSet()
JSON.stringify(obj, (k, v) => {
  if (typeof v === 'object' && v !== null) {
    if (seen.has(v)) return '[Circular]'
    seen.add(v)
  }
  return v
})
```

### Source maps
- TypeScript/Babel/webpack: ensure `.map` files are emitted (`tsconfig.json`: `"sourceMap": true`)
- DevTools: Sources tab → Settings → "Enable JavaScript source maps"
- Without source maps, stack traces show transpiled positions, not your `.ts`/`.tsx` lines

### Common pitfalls
- **`==` vs `===`** — always use `===` unless you know why you want type coercion
- **`this` in callbacks** — use arrow functions or `.bind(this)`. Class methods passed as event handlers lose `this`
- **Async — unhandled promise rejection** — every `.catch()` or `try/await` matters; unhandled rejections crash Node 15+
- **`undefined` vs `null`** — destructuring with default values `const { x = 'default' } = obj` only triggers default for `undefined`, not `null`
- **Hoisting confusion** — `let`/`const` are hoisted but in temporal dead zone until declaration; using before declaration throws ReferenceError

### Tools
- `node --inspect-brk script.js` + Chrome DevTools → chrome://inspect
- `vitest --inspect-brk --no-file-parallelism` — debug single test
- `node --trace-warnings` — show source location for warnings
- `NODE_OPTIONS=--stack-trace-limit=200` — see deeper stacks

---

## Go

### Inspecting state
```go
// Pretty-print structs
import "fmt"
fmt.Printf("%+v\n", user)  // shows field names
fmt.Printf("%#v\n", user)  // Go syntax representation

// Use spew for deep inspection
import "github.com/davecgh/go-spew/spew"
spew.Dump(complexStruct)
```

### Stack traces
```go
import "runtime/debug"
defer func() {
    if r := recover(); r != nil {
        fmt.Println("Recovered:", r)
        debug.PrintStack()
    }
}()
```

### Common pitfalls
- **Loop variable capture in goroutines** — `for _, v := range items { go func() { use(v) }() }` all see the same `v`. Fix: `go func(v T) { use(v) }(v)` (Go 1.22+ fixes this automatically).
- **nil interface vs nil pointer** — an interface holding a typed nil is NOT nil (`var p *T = nil; var i interface{} = p; i != nil`)
- **Forgotten `defer`** — `defer rows.Close()` immediately after the query, before any error checks
- **Slice aliasing** — `s2 := s1[1:3]` shares backing array; mutating s2 mutates s1
- **Map writes from concurrent goroutines** — fatal error. Use `sync.Mutex` or `sync.Map`.

### Tools
- `dlv debug ./cmd/server` — Delve debugger, supports `b`, `c`, `n`, `s`, `p` commands
- `go test -race ./...` — race detector
- `go test -run TestName -v` — run specific test verbosely
- `GODEBUG=gctrace=1` — log every GC cycle

---

## Shell / Bash

### Inspecting state
```bash
# Print every command before executing
set -x
your_commands_here
set +x

# Or run script with -x
bash -x your_script.sh

# Print line number on error
set -e
trap 'echo "Error on line $LINENO"' ERR
```

### Common pitfalls
- **Unquoted variables** — `rm $file` breaks if `$file` contains spaces. Always `rm "$file"`.
- **Word splitting in command substitution** — `for f in $(ls)` breaks on filenames with spaces. Use globs: `for f in *`.
- **`set -e` in pipelines** — by default, only the last command's exit status is checked. Use `set -o pipefail` to check all.
- **Locale-dependent commands** — `tr '[:upper:]' '[:lower:]'` doesn't lowercase non-ASCII unless `LC_ALL=C.UTF-8` is set. Use Python or `awk` for Unicode.
- **Heredoc quoting** — `<<EOF` interpolates variables, `<<'EOF'` doesn't. Mismatch causes weird "command not found" errors.

### Tools
- `shellcheck script.sh` — lints for these pitfalls (must-have)
- `bashdb` — bash debugger
- `set -euo pipefail` — strict mode at top of every script

---

## Database / SQL

### Inspecting state
```sql
-- PostgreSQL: see what's running right now
SELECT pid, query, state, wait_event_type, wait_event
FROM pg_stat_activity
WHERE state != 'idle';

-- See locks
SELECT * FROM pg_locks WHERE NOT granted;

-- Explain a slow query
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
```

### Common pitfalls
- **Missing index on foreign key** — joins become sequential scans
- **N+1 queries** — fetching child records in a loop instead of joining (use `IN` or join)
- **Implicit type cast** — `WHERE id = '1'` may bypass index if `id` is integer (cast to text first)
- **Migration that locks the table** — `ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT ...` locks the whole table on PostgreSQL < 11. Use `ADD COLUMN` (nullable) → backfill in batches → `SET NOT NULL` separately.
- **`SELECT *` in production** — adds new columns silently change response format and break consumers

### Tools
- `pgbadger` — log analyzer for slow queries
- `EXPLAIN ANALYZE` — actual execution plan with timing
- `pg_stat_statements` extension — top N slowest query patterns

---

## Frontend (React / Vue / Svelte)

### Inspecting state
```jsx
// React DevTools — install browser extension
// Profile tab shows render reasons

// Why did you render?
import { whyDidYouRender } from '@welldone-software/why-did-you-render'
whyDidYouRender(React)
MyComponent.whyDidYouRender = true
```

### Common pitfalls
- **Stale closures in `useEffect`** — referencing state without listing it in deps; React 18+ has `react-hooks/exhaustive-deps` lint
- **Mutating state directly** — `state.list.push(x)` doesn't trigger re-render; use `[...state.list, x]`
- **Effects running twice in dev** — React 18 Strict Mode double-invokes for cleanup detection. Not a bug; production runs once.
- **`useCallback` / `useMemo` cargo cult** — they have overhead; use only when measured to help

### Tools
- React DevTools (Components + Profiler tabs)
- Vue DevTools (similar)
- `console.trace()` — stack trace from any render

---

## Cross-cutting techniques

### Bisecting with git
```bash
git bisect start
git bisect bad           # current commit is broken
git bisect good <hash>   # known good commit
# git checks out a midpoint; you test, then say:
git bisect good   # or: git bisect bad
# Repeat until git finds the bad commit
git bisect reset
```

### Adding logs in a hot loop
- Don't `console.log` 10000 times — buffer and print every Nth iteration
- Or use sampling: `if (Math.random() < 0.01) console.log(...)` for 1%

### Reproducing flaky tests
- Run in a loop: `for i in {1..50}; do pytest -k test_name || break; done`
- Add randomization seed control to expose race conditions
- Run with reduced parallelism: `pytest -n 1` (no parallelism)

### Differential debugging
- "It works on machine A, not B" → diff env (`env > /tmp/env-a.txt`, copy, `diff`)
- "It worked yesterday" → `git log --since=1.day --oneline`
- "It works locally, not in prod" → diff configs, env vars, image versions

---

## When to escalate

If after 30 minutes of debugging you're still guessing, do one of:
1. **Walk away for 10 minutes** — most "impossible" bugs become obvious after a break
2. **Rubber-duck explanation** — write a `## Why this might be failing` section in CLAUDE.md and read it back
3. **Bisect aggressively** — even 50 commits can be bisected in 6 steps
4. **Ask** — describe symptoms + what you've tried + what you ruled out
