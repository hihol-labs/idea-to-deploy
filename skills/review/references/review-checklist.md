# Review Rubric (binary, deterministic)

> **Shared definitions:** Gate status enum, report format, secret detection patterns, and .env checks are defined in [`skills/_shared/helpers.md`](../../_shared/helpers.md). This file uses those definitions — do not re-declare them here.

> This rubric replaces the old `score 1–10` system. Two different model invocations on the same documents will now produce the **same** pass/fail result, because every check is binary (yes/no), not subjective.

The rubric has three tiers:

| Tier | Behavior on failure | Gate behavior |
|---|---|---|
| **Critical** | Block — gate fails until fixed | `/review` exits with status `BLOCKED` |
| **Important** | Warn — gate passes but warning emitted | `/review` exits with status `PASSED_WITH_WARNINGS` |
| **Nice-to-have** | Inform — informational only | `/review` exits with status `PASSED` |

The skill MUST report each check by name with ✅ / ❌ / ⚠️ and produce a summary like:

```
Critical:        12/12 ✅
Important:       7/9 ⚠️ (2 warnings)
Nice-to-have:    3/4 ⚠️ (1 info)
Status:          PASSED_WITH_WARNINGS
Derived score:   8.5/10  (informational only — not used for gating)
```

The derived score is `(Critical_pass_pct * 0.6) + (Important_pass_pct * 0.3) + (Nice_pass_pct * 0.1)`, scaled to 0–10. Used for human-readable reporting only. **Do not use it as a gate.**

---

## Tier 1: Critical (must all pass)

These are dealbreakers. If any fail, `/review` returns `BLOCKED` and the calling skill (`/kickstart` Quality Gate 1) refuses to proceed.

### C1. PROJECT_ARCHITECTURE.md exists
Check: file present at project root or in `docs/`.

### C2. Architecture has at least one database table OR an explicit "no database" justification
Check: `## Database` or `## Schema` section present, with at least 1 table definition (not just "PostgreSQL" — actual `CREATE TABLE` or markdown table with fields). OR an explicit line like "Database: none — uses external API only".

### C3. Every database table has all columns with types
Check: each table block has at least 2 columns, each column has a type (text/int/uuid/timestamp/...).

### C4. Architecture has at least one API endpoint OR explicit "no API" justification
Check: `## API` or `## Endpoints` section with at least 1 endpoint OR explicit "API: none".

### C5. Every API endpoint has method + path + auth requirement
Check: each endpoint specifies HTTP method, URL path, and one of `auth: public/user/admin/none`.

### C6. Every P0 user story in PRD maps to at least one endpoint
Check: cross-reference PRD's P0 stories against architecture endpoints. Every P0 story must have at least one supporting endpoint OR an explicit "no API needed" note.

### C7. Every architecture entity name matches PRD and IMPLEMENTATION_PLAN
Check: entity names (`users`, `orders`, `products`, ...) appear identically across all 3 documents. No `users` in PRD but `accounts` in architecture.

### C8. Tech stack identical across STRATEGIC_PLAN, ARCHITECTURE, IMPLEMENTATION_PLAN, README
Check: language, framework, database, deployment target — same names everywhere.

### C9. IMPLEMENTATION_PLAN.md has at least 4 steps with verifiable deliverables
Check: at least 4 numbered steps; each step has at least one specific file mentioned and at least one verification command (curl, pytest, npm test, ...).

### C10. No hardcoded secrets in any document
Check: regex scan for `password=`, `api_key=`, `Bearer `, `sk-`, `token=` followed by anything that's not `<placeholder>` / `${ENV_VAR}` / `xxx`.

### C11. .env.example exists OR is mentioned with all required variables
Check: file exists at root, OR architecture document explicitly lists required environment variables in a `## Environment` section.

### C12. CLAUDE.md exists with project status table
Check: `CLAUDE.md` exists and has a markdown table with rows representing implementation steps.

---

## Tier 2: Important (warn but pass)

These are quality issues that should be fixed but don't block proceeding. They produce warnings.

### I1. STRATEGIC_PLAN.md has at least 3 competitors analyzed
Check: `## Competitors` or `## Competition` section with at least 3 named entities and a comparison.

### I2. STRATEGIC_PLAN.md has budget estimation
Check: `## Budget` section with concrete numbers (currency + amount, not "TBD").

### I3. STRATEGIC_PLAN.md has at least 3 risks identified
Check: `## Risks` section with at least 3 distinct items.

### I4. PRD has at least 5 user stories with role/want/benefit format
Check: at least 5 stories matching the pattern `As <role>, I want <action>, so that <benefit>` (or close variant).

### I5. PRD has acceptance criteria for every P0 story
Check: each P0 story has an `Acceptance criteria:` block with at least 2 conditions.

### I6. PRD has kill criteria
Check: `## Kill criteria` section explaining what would make the project a failure (used to know when to stop).

### I7. Auth flow described step-by-step (not just "JWT")
Check: architecture has a section describing auth flow with at least 4 steps (registration → email verification → login → token refresh, or similar). "JWT auth" alone is not enough.

### I8. Every implementation step has time estimation
Check: each numbered step has an `Estimated: Xh` or `Estimated: X-Yh` annotation.

### I9. CLAUDE_CODE_GUIDE.md exists with prompts matching steps
Check: file exists; for each step in IMPLEMENTATION_PLAN.md, there is a corresponding section in the guide with a copy-paste prompt.

---

## Tier 3: Nice-to-have (inform only)

These are polish items. Failure is informational, not a warning.

### N1. README.md has a working "Quick Start in 30 seconds" section
Check: top of README has a code block users can copy-paste to get the project running locally.

### N2. PROJECT_ARCHITECTURE.md mentions at least one database index
Check: at least one `INDEX` or `CREATE INDEX` declaration on a frequently-queried column.

### N3. Error responses documented for endpoints (400, 401, 403, 404, 500)
Check: at least one endpoint specifies what error codes it returns and under what conditions.

### N4. Folder structure section in architecture
Check: `## Folder structure` or `## Project layout` with a tree diagram showing where major components live.

---

## Code-only checks (when source code exists)

If the project has been scaffolded and code is present, additionally run:

### C-code-1. (Critical) No hardcoded secrets in source files
Check: grep source files for the same secret patterns as C10. Block if found.

### C-code-2. (Critical) Folder structure matches architecture
Check: directories described in architecture's "folder structure" section actually exist in the repo.

### I-code-1. (Important) All architecture endpoints implemented
Check: for each endpoint in `## API`, there's a corresponding route handler in code. Missing endpoints → warning.

### I-code-2. (Important) All architecture tables have model files
Check: for each table in `## Database`, there's a model/entity file in code (Django model, SQLAlchemy model, Drizzle schema, ...).

### N-code-1. (Nice-to-have) Tests exist for at least 50% of P0 stories
Check: count P0 stories that have at least one test referencing them by name or feature.

---

## Code-quality checks (SOLID, smells, complexity) — added in v1.4.0

These checks run only when source code exists. They encode common sources of real bugs from Fowler's *Refactoring*, Martin's *Clean Code*, and the [Google Engineering Practices](https://google.github.io/eng-practices/) code review guide. They are **not** a full static analysis replacement — they're the checks that have the highest real-bug signal with the lowest false-positive rate at LLM-review speed.

### C-code-3. (Critical) No God classes / God functions
**Criterion:** no single class > 500 LOC AND no single function > 80 LOC.
**Rationale:** classes/functions past these thresholds reliably correlate with defects and are hard to test. (Google's internal threshold is 200 LOC per function; 80 is the conservative external equivalent.)
**Action on fail:** `/refactor` with Extract Class / Extract Method.

### C-code-4. (Critical) No circular imports between modules
**Criterion:** static import analysis — module A imports module B and module B imports module A (directly or via chain).
**Rationale:** circular imports cause runtime errors that tests often miss (they show up only on cold import order), and they indicate broken boundaries.
**Action on fail:** `/refactor` — extract shared types to a third module, or invert the dependency.

### I-code-3. (Important) Cyclomatic complexity ≤ 10 per function
**Criterion:** count branches (if/elif/else, for, while, case, try/except, &&, ||, ternary) per function. Fail if any function > 10.
**Rationale:** McCabe's original research: functions > 10 branches have measurably more defects and are harder to test fully. Fowler's *Refactoring* catalog targets this metric directly.
**Action on fail:** `/refactor` with Decompose Conditional, Replace Conditional with Polymorphism, or Extract Method.

### I-code-4. (Important) No "long parameter list" smell
**Criterion:** no function takes > 5 positional parameters (keyword/default args are exempt if they have sensible defaults).
**Rationale:** long parameter lists indicate the function is doing too much OR a missing parameter object. One of the top 5 smells in Fowler's catalog.
**Action on fail:** `/refactor` with Introduce Parameter Object or Preserve Whole Object.

### I-code-5. (Important) No "feature envy" smell on critical paths
**Criterion:** a method in class A calls > 3 methods/properties of class B without using A's own state. Check route handlers, services, domain models.
**Rationale:** the method belongs in B, not in A. Common SRP (Single Responsibility Principle) violation. Fowler's canonical smell.
**Action on fail:** `/refactor` with Move Method.

### I-code-6. (Important) No "shotgun surgery" hotspots
**Criterion:** a single conceptual change (e.g., adding a field) forces edits to > 5 files. Detected by: if the user's recent commit touches > 5 files for what the commit message describes as a single feature, flag as warning on next review.
**Rationale:** the opposite of Divergent Change. Indicates missing abstraction.
**Action on fail:** `/refactor` — introduce the missing abstraction (interface, base class, shared config).

### I-code-7. (Important) SOLID: no Interface Segregation violation
**Criterion:** no interface / abstract class has > 7 methods AND has at least one implementation that raises `NotImplementedError` / throws / returns null for some of them.
**Rationale:** clients shouldn't be forced to depend on methods they don't use. Classic SOLID-I violation.
**Action on fail:** `/refactor` — split the interface.

### I-code-8. (Important) SOLID: no Dependency Inversion violation in business logic
**Criterion:** business-logic modules (services, domain) do not directly `import` concrete infrastructure (DB driver, HTTP client, framework-specific types). They should depend on interfaces or dependency injection.
**Rationale:** makes tests require real DBs/networks. Pattern across years of legacy rewrites.
**Action on fail:** `/refactor` — extract a repository/port interface, inject the implementation.

### I-code-9. (Important) Google Engineering Practices: small change size
**Criterion:** the current git diff (staged + unstaged) touches ≤ 400 LOC across ≤ 10 files. Larger changes are reviewed with reduced confidence.
**Rationale:** Google internal research: review quality drops sharply above 400 LOC per CL. This check warns — it does not block.
**Action on fail:** suggest splitting the commit/PR. Warning only.

### N-code-2. (Nice-to-have) No duplicated code blocks > 10 LOC
**Criterion:** detect token-level duplication of blocks > 10 LOC across files.
**Rationale:** DRY violations. Not blocking — sometimes duplication is cheaper than the wrong abstraction (Sandi Metz).
**Action on fail:** consider Extract Function / Extract Module. Informational.

### N-code-3. (Nice-to-have) Test coverage signal for modified files
**Criterion:** for each modified source file, a corresponding test file exists (same stem, `_test` or `test_` prefix). Not a line-coverage check — just "does a test file exist for this module".
**Rationale:** cheapest proxy for "was this tested at all". Line coverage requires running tests; file-existence check is free.
**Action on fail:** suggest `/test` on the uncovered file. Informational.

### N-code-4. (Nice-to-have) No magic numbers in business logic
**Criterion:** literal numeric values (except `0`, `1`, `-1`) used in conditionals / arithmetic without a named constant. Whitelist: `len(x) == 0`, indices, test fixtures.
**Rationale:** `if age >= 18` vs `if age >= LEGAL_AGE` — the second survives requirement changes. Clean Code chapter 17.
**Action on fail:** suggest Extract Constant. Informational.

---

## Reporting format

The skill MUST output in this exact format so it can be parsed:

```markdown
## /review report

### Tier 1: Critical
- ✅ C1: PROJECT_ARCHITECTURE.md exists
- ✅ C2: Architecture has at least one database table
- ❌ C3: Every database table has all columns with types
       → table `orders` is missing column types for status, total
- ✅ C4: Architecture has at least one API endpoint
- ...

### Tier 2: Important
- ⚠️ I1: STRATEGIC_PLAN.md has at least 3 competitors analyzed
       → only 2 competitors found; suggest adding 1 more
- ✅ I2: STRATEGIC_PLAN.md has budget estimation
- ...

### Tier 3: Nice-to-have
- ℹ️ N1: README.md has a working "Quick Start in 30 seconds" section
       → no quick-start block found
- ...

### Summary
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | 11 | 12 | ❌ BLOCKED |
| Important | 7 | 9 | ⚠️ |
| Nice-to-have | 3 | 4 | ℹ️ |

**Final status:** BLOCKED (must fix C3 before proceeding)
**Derived score:** 8.5/10 (informational only — not used for gating)

### Suggested fixes
1. **C3 (Critical)** — add type annotations to columns `orders.status` (text), `orders.total` (decimal). Apply now? [yes/no]
2. **I1 (Important)** — add Twilio Segment to competitor analysis in STRATEGIC_PLAN.md.
```
