# Project profiles & domain markers (v1.35.0)

idea-to-deploy is greenfield-first by default (idea → discover → blueprint →
kickstart → … → deploy). That is the right shape when you build a product from
scratch. It is the wrong shape when the work is a **feature on a mature existing
codebase** — there the greenfield pipeline is ceremony, and the project's own
`CLAUDE.md` is the real source of truth.

These **opt-in** markers let a project tell the methodology what kind of work it
is. They change nothing by default: a project that sets no marker behaves
exactly as before. Only the project's own `CLAUDE.md` (or `.claude/CLAUDE.md`)
turns them on.

---

## `itd-profile: brownfield` — opt out of the greenfield pipeline

**What it does.** When the current project's `CLAUDE.md` contains this marker,
the skill-hint hook (`hooks/check-skills.sh`) suppresses greenfield-pipeline
hints so they stop firing on day-to-day feature work:

`/project`, `/blueprint`, `/discover`, `/kickstart`, `/guide`, `/strategy`,
`/market-scan`, `/autopilot`.

Everything else stays active — `/task`, `/bugfix`, `/refactor`, `/test`,
`/review`, `/doc`, `/perf`, `/session-save`, `/migrate`, `/security-audit`, …
The review gate and feature-branch discipline are untouched (they are equally
valuable on brownfield).

**How to enable.** Put either form anywhere in the project's `CLAUDE.md`
(case-insensitive, matched in the first 8 KB):

```
<!-- itd:brownfield -->
```

or, inside a YAML/front-matter-ish block:

```
itd-profile: brownfield
```

**When to use.** The project already has a substantial `CLAUDE.md` /
architecture and you are adding features or fixing bugs, not bootstrapping a new
product. `/adopt` can stamp this marker when it onboards a legacy project.

**When NOT to use.** A new product build — leave it unset so the greenfield
pipeline stays available.

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

- **Opt-in, additive.** No marker → no behaviour change. Greenfield projects are
  never affected by these features.
- **Project-declared, not global.** The markers live in the project's own
  `CLAUDE.md`; the global methodology stays greenfield-first.
- **Composable.** A project can set both markers (a brownfield, data-sensitive
  system — the common case for mature line-of-business software).
