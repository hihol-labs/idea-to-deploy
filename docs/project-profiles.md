# Project profiles & domain markers (v1.36.0)

idea-to-deploy is greenfield-first by default (idea → discover → blueprint →
kickstart → … → deploy). That is the right shape when you build a product from
scratch. It is the wrong shape when the work is a **feature on a mature existing
codebase** — there the greenfield pipeline is ceremony, and the project's own
`CLAUDE.md` is the real source of truth.

Two markers let a project tell the methodology what kind of work it is:

- **`itd-profile`** (brownfield vs greenfield) is **auto-detected** by repo
  maturity from v1.36.0, and can be **overridden** explicitly in either
  direction. Greenfield stays the default for a fresh project.
- **`itd-domain: data-sensitive`** is **opt-in** — set it only when the project
  mutates irreplaceable data.

Markers live in the project's own `CLAUDE.md` (or `.claude/CLAUDE.md`),
case-insensitive, matched in the first 8 KB.

---

## `itd-profile: brownfield` / `greenfield` — pick the right pipeline

**What it does.** On a **brownfield** project the skill-hint hook
(`hooks/check-skills.sh`) suppresses greenfield-pipeline hints so they stop
firing on day-to-day feature work:

`/project`, `/blueprint`, `/discover`, `/kickstart`, `/guide`, `/strategy`,
`/market-scan`, `/autopilot`.

Everything else stays active — `/task`, `/bugfix`, `/refactor`, `/test`,
`/review`, `/doc`, `/perf`, `/session-save`, `/migrate`, `/security-audit`, …
The review gate and feature-branch discipline are untouched (equally valuable on
brownfield). A hint is matched by its own **primary** skill (the `/skill` after
`используй`), never by a greenfield skill merely mentioned in the prose — so the
`/adopt` hint, which references `/blueprint`, is not suppressed.

**How it is resolved (v1.36.0).**

1. **Explicit marker wins**, in either direction. Put either form anywhere in
   the project's `CLAUDE.md`:

   ```
   <!-- itd:brownfield -->      itd-profile: brownfield
   <!-- itd:greenfield -->      itd-profile: greenfield
   ```

2. **Otherwise auto-detect by repo maturity.** An established git history
   (`git rev-list --count HEAD` ≥ `ITD_BROWNFIELD_MIN_COMMITS`, default **25**)
   → brownfield; a fresh or empty project (fewer commits, or no git repo)
   → greenfield. Tune the threshold with the `ITD_BROWNFIELD_MIN_COMMITS`
   environment variable.

**When to override.** A mature repo where you want the greenfield pipeline back
for a big new feature → set `itd-profile: greenfield`. A brand-new project you
want treated as brownfield immediately → set `itd-profile: brownfield` (or let
it flip automatically once history accrues). `/adopt` can stamp `brownfield`
when it onboards a legacy project.

---

## `itd-domain: data-sensitive` — read-only-before-mutate gate

**What it does.** Declares that the project mutates production, financial, or
otherwise irreplaceable data. In such a project the standing convention is:

> **Model the change read-only first, show the before/after, get explicit
> confirmation, and only then mutate.** Never run a data-mutating operation
> (production write, mass re-post, destructive migration, money movement)
> straight from an ad-hoc command.

This is guidance the agent must follow, reinforced by the existing safety hooks
(`careful.sh`, `risk-score.sh`) — it does not silently auto-block, it makes the
"dry-run first" step mandatory and visible.

**How to enable.** Same mechanism, in the project's `CLAUDE.md`:

```
<!-- itd:data-sensitive -->
```

or

```
itd-domain: data-sensitive
```

**When to use.** Accounting/ERP systems, anything touching a live customer DB,
payment flows, bulk re-processing jobs. Example: the payment-calendar work on
the OneOfS accounting platform models plan/fact read-only across all legal
entities before any write, and never touches the live DB until a before/after is
approved.

---

## Design guarantees

- **Safe default.** A fresh project (few commits, or no git) stays greenfield —
  the pipeline is available exactly as before. Auto-detection only flips an
  *established* repo to brownfield, which is where the pipeline was ceremony
  anyway; an explicit `itd-profile: greenfield` always overrides.
- **`data-sensitive` is opt-in.** It never activates on its own — set it
  deliberately.
- **Override always wins.** An explicit `itd-profile:` marker beats
  auto-detection in either direction; the project owner has the final say.
- **Composable.** A project can set both markers (a brownfield, data-sensitive
  system — the common case for mature line-of-business software).

---

## Recommended skill sets by scenario (v1.37.0)

The profile picks *which pipeline* fits; this matrix maps the **scenario** to the
skills that carry it. It removes the last of the "the model guesses" heuristic
for point-1 (projects of different kind/complexity). Use it as guidance, not a
hard gate — the skill-hint hook still routes per prompt.

| Scenario | Recommended skills (in order) |
|---|---|
| **New product from an idea** (greenfield) | `/discover` → `/blueprint` → `/kickstart` → `/review` → `/test` → `/harden` → `/deploy` |
| **New feature on an existing codebase** (brownfield) | `/task` → (`/bugfix` \| `/refactor` \| `/perf`) → `/test` → `/review` → `/session-save` |
| **Bug fix** | `/bugfix` (root-cause gate) → `/test` (regression) → `/review` |
| **Refactor / tech debt** | `/refactor` → `/test` → `/review`; `/deps-audit` if dependencies |
| **Data-sensitive change** (`itd-domain: data-sensitive`) | model read-only first → `/task` → `/migrate` (backup + rollback) → `/review`; **never** mutate prod from an ad-hoc command |
| **Security-critical** (auth / payments / secrets) | `/security-audit` + security-guidance plugin → `/review` |
| **Legacy onboarding** | `/adopt` → `/strategy` or `/blueprint` |
| **Advisory / "analyze, don't code"** | `/advisor` (or `/grill-me` to stress-test a decision) — read-only |
| **Docs** | `/doc` |
| **Trivial / small script** | minimal — `Скилл: не нужен` (or `SKILL_BYPASS`); no ceremony |

**Complexity axis (how much ceremony):**

- **Trivial** (one-liner, throwaway script) → skip the pipeline; declare `не нужен`.
- **Small** (single-file feature/fix) → the relevant single skill + `/review`.
- **Medium** (multi-file feature) → `/task` router + `/test` + `/review` + `/session-save`.
- **Large** (new product / subsystem) → the full greenfield or brownfield chain above.

Always-on regardless of size: the review gate before a multi-file commit, tests
for new source, and a session checkpoint at meaningful state changes.
