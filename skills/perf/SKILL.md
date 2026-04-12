---
name: perf
description: 'Performance analysis — find bottlenecks and optimize. Covers algorithms, DB queries, memory, I/O, caching. Measure first, optimize second.'
argument-hint: file, function, or area to analyze
license: MIT
allowed-tools: Read Edit Glob Grep Bash
context: fork
agent: perf-analyzer
metadata:
  author: HiH-DimaN
  version: 1.3.1
  category: code-quality
  tags: [performance, optimization, profiling, bottleneck]
---


# Perf


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- тормозит, медленно работает, лагает, оптимизируй, производительность
- узкое место, bottleneck, N+1, slow query, медленный запрос
- утечка памяти, memory leak, высокая нагрузка
- optimize, make it faster, slow page load
- любой жалобный запрос на скорость, latency, throughput

## Recommended model

**opus** — Bottleneck identification often requires reasoning across multiple layers (algorithm → DB index → caching → I/O). Opus catches issues Sonnet misses; perf-analyzer subagent can be Sonnet.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 0: Auto-freeze scope (v1.17.0)

After identifying the target file/directory from $ARGUMENTS or profiling results, automatically activate scope freeze:

```bash
# Write freeze state — limits edits to the optimization target
echo "/path/to/perf/directory" > /tmp/claude-freeze-${CLAUDE_SESSION_ID:-default}.state
```

This prevents accidental edits outside the performance optimization scope. The freeze is cleared when the skill completes. If the optimization legitimately requires changes outside the frozen scope (e.g., adding a database index migration), the freeze hook will warn and ask for confirmation.

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

## Rules

1. Measure before optimizing — без baseline-замера (время, количество запросов, размер) оптимизация запрещена. "Кажется медленно" — не метрика
2. Никаких premature optimizations — оптимизируй только подтверждённые bottleneck'и. Если профилирование не показывает проблему в этом месте, не трогай его
3. После каждой оптимизации — benchmark "до" и "после" с конкретными числами в отчёте (Step 2 формат обязателен)
4. Одна оптимизация за раз — не применяй 5 фиксов одновременно, иначе невозможно понять какой дал эффект
5. Trade-off обязателен — каждая оптимизация имеет цену (память, читаемость, сложность). Явно указывай компромисс в отчёте


## Self-validation

Before presenting performance analysis, verify:
- [ ] Bottleneck identified with evidence (measurements, not guesses)
- [ ] Optimization suggestions include expected impact estimate
- [ ] No premature optimization of non-bottleneck code
- [ ] Suggestions are actionable with specific code changes
- [ ] Trade-offs documented (memory vs speed, complexity vs performance)

## Troubleshooting

### Can't reproduce slowness locally
Ask for production metrics. Check if the issue is data-volume dependent (works with 10 rows, breaks with 10K).

### Optimization breaks functionality
The optimization was too aggressive. Revert and apply a safer version. Common cause: caching data that changes frequently.

### Multiple bottlenecks
Fix one at a time, measure after each. Don't optimize everything at once — the biggest bottleneck may mask others.
