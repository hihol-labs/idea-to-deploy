---
name: perf
description: Performance analysis — find bottlenecks and optimize. Covers algorithms, database queries, memory, I/O, and caching. TRIGGER when user says "тормозит", "медленно работает", "лагает", "оптимизируй", "производительность", "узкое место", "bottleneck", "N+1", "slow query", "медленный запрос", "утечка памяти", "memory leak", "высокая нагрузка", "optimize", "make it faster", reports slow page loads, high latency, or memory issues. ALWAYS use this for performance-related complaints — measure first, optimize second.
argument-hint: file, function, or area to analyze
license: MIT
effort: medium
context: fork
agent: perf-analyzer
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: code-quality
  tags: [performance, optimization, profiling, bottleneck]
---


# Perf

## Instructions

### Step 1: Profile
Identify what exactly is slow. Read the code and look for:

1. **Algorithmic complexity** — O(n^2) or worse, unnecessary iterations
2. **Database** — N+1 queries, missing indexes, over-fetching
3. **Memory** — leaks, large allocations, unbounded caches
4. **I/O** — blocking calls, missing batching, sequential when could be parallel
5. **Caching** — missing caching opportunities, cache invalidation issues
6. **Bundle/Load** — unnecessary imports, large dependencies, missing lazy loading
7. **Concurrency** — thread contention, unnecessary locking

### Step 2: Report findings

For each finding:
```
**Impact**: HIGH / MEDIUM / LOW
**Location**: file:line
**Current**: what's slow and why (with complexity if applicable)
**Fix**: concrete optimization
**Trade-off**: any downsides
```

### Step 3: Prioritize
Sort by impact. Focus on real bottlenecks, not micro-optimizations.

### Step 4: Fix
Implement the highest-impact optimizations. Verify with before/after comparison where possible.

## Examples

### Example 1: N+1 query
User says: "страница пользователей грузится 5 секунд"

Analysis:
```
Impact: HIGH
Location: src/api/users.py:45
Current: Loop fetches orders for each user separately (N+1)
  for user in users:
      orders = db.query(Order).filter(user_id=user.id)  # N queries!
Fix: Use eager loading or JOIN
  users = db.query(User).options(joinedload(User.orders)).all()  # 1 query
Trade-off: Higher memory for large datasets — add pagination
```

### Example 2: Frontend bundle
User says: "приложение долго загружается"

Analysis:
```
Impact: HIGH
Location: src/App.tsx:1-10
Current: All routes imported eagerly — 2.5MB bundle
Fix: React.lazy() + Suspense for route-level code splitting
Trade-off: Slight delay on first navigation to each route
```

## Troubleshooting

### Can't reproduce slowness locally
Ask for production metrics. Check if the issue is data-volume dependent (works with 10 rows, breaks with 10K).

### Optimization breaks functionality
The optimization was too aggressive. Revert and apply a safer version. Common cause: caching data that changes frequently.

### Multiple bottlenecks
Fix one at a time, measure after each. Don't optimize everything at once — the biggest bottleneck may mask others.
