---
name: perf
description: 'Performance analysis — find bottlenecks and optimize. Covers algorithms, DB queries, memory, I/O, caching. Measure first, optimize second.'
argument-hint: file, function, or area to analyze
license: MIT
allowed-tools: Read Edit Glob Grep Bash
context: fork
agent: perf-analyzer
metadata:
  effort: medium
  side_effect: command-execution
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.83.0
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

### Step 0 (pre): Runner selection — avoid fork-thrash on a large CLAUDE.md (v1.24.0)

This skill is declared `context: fork`; the fork inherits a **copy of the current
conversation** including the project root `CLAUDE.md`. If that `CLAUDE.md` is
large (> ~12 KB) or you have already seen autocompact churn this session, the
fork starts near the context limit and **thrashes until it dies** before
finishing. **Fallback:** don't fork — dispatch the `perf-analyzer` agent via the
Agent tool (`Agent(subagent_type: "perf-analyzer", …)`) with a **thin prompt**
that references files/dirs **by path** (don't paste `CLAUDE.md` or large file
bodies; the agent reads them itself). Quick check: `wc -c CLAUDE.md` — if
small/absent, the normal fork path below is fine. **Caveat:** this Step runs
*inside* the fork, but the Agent tool is still callable from there — so do the
check and switch first thing if `CLAUDE.md` is large.

### Step 0: Auto-freeze scope (v1.17.0)

After identifying the target file/directory from $ARGUMENTS or profiling results, automatically activate scope freeze:

```bash
# Write freeze state — limits edits to the optimization target (dual-write: /tmp + platform temp)
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || python -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"  # win-ok: цепочка падает в /tmp (шим exit!=0)
mkdir -p /tmp 2>/dev/null || true
echo "/path/to/perf/directory" | tee "/tmp/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" > "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" 2>/dev/null || echo "/path/to/perf/directory" > "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state"
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

### Step 2.5: Refute pass — adversarially verify each surfaced bottleneck before you trust it (v1.60.0 — Ось 2, agentic engineering)

The refute pass from `/review` Step 2.6, applied to the perf verify fleet. A
plausible-but-wrong bottleneck (a hot-looking loop that is actually cold, an N+1
on a 3-row table, an "optimization" that trades against a real constraint)
wastes effort and can regress correctness — this pass filters them before they
reach the prioritized list. Put every **HIGH and MEDIUM** finding through an
independent refutation.

For each such finding, run a **fresh** adversarial verification (a separate
reasoning pass, or `Agent(subagent_type: "perf-analyzer", …)` with a refute
prompt) that tries to prove the finding is NOT worth acting on — read the code
and the evidence and look for the reason: **is it actually on the hot path**
(measured, not guessed — this skill's «measure first» rule is the refutation's
teeth), is the input size real, would the proposed fix *measurably* help, does
the trade-off cost more than it saves. **Default to `refuted: true` under
uncertainty**: a bottleneck you cannot back with a measurement or a concrete
hot-path argument is dropped, not shipped as a guess.

- Refuted (cold path / negligible N / fix wouldn't help / bad trade-off) → move
  to "Additional observations" with a `refuted` note; it does not gate priority.
- Confirmed (measured on the hot path, fix helps) → keep it, ranked by impact.
- **LOW-impact / micro-optimization findings are NOT refuted** — they never gate,
  so the cost is not justified.

**Invariant:** the refute pass can only REMOVE unconfirmed findings from the
prioritized set; it never invents a new bottleneck and never manufactures a
measurement it did not take.

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

- **Субагентский контракт** — промпт любого Agent-запуска начинай с env-преамбулы из `skills/_shared/subagent-contract.md`; сдачу субагента принимай только с evidence либо явной пометкой «НЕ ПРОВЕРЕНО» (там же, секция 2).
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

## Fail-closed gate (v1.42.0)

«Оптимизировано» без чисел — не статус. Каждое perf-изменение обязано иметь:
**baseline-замер ДО** и **замер ПОСЛЕ тем же инструментом/нагрузкой** (профайлер,
k6, EXPLAIN ANALYZE, timeit — что уместно). Нет пары до/после → результат
помечается `UNVERIFIED` (не «улучшено»), и это явно выносится в финальный отчёт.
Ожидание («должно стать быстрее») никогда не записывается как факт.
