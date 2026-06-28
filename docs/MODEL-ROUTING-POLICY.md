# Model-routing policy (per-phase, economics-aware)

> **Added v1.31.0** — New-SDLC port (Google "The New SDLC With Vibe Coding", 2026:
> "intelligent model routing" — expensive models on reasoning-heavy phases, cheap
> models on mechanical phases, to control OpEx).
>
> **This is a POLICY, not an auto-router.** idea-to-deploy ships no cross-vendor
> routing engine and no daemon (see [ADR-001](adr/ADR-001-no-own-runtime.md)). The
> policy is *applied* by mechanisms that already exist in the harness: the `/model`
> command, each skill's own `## Recommended model` section, and per-agent `model:`
> frontmatter on subagents. This file is the single rationale table those pointers
> share — it explains *why* a tier fits a phase, so the choice is transparent rather
> than hidden inside a router.

## Why route at all

Token economics is the dominant operating cost (OpEx) of agent-heavy products. The
reasoning-heavy phases (requirements, architecture, cross-document review) genuinely
need a frontier model; the mechanical, high-volume phases (test-gen against known
conventions, routing, summarizing, doc formatting) do not. Spending a frontier model
on every phase is the easiest avoidable cost. Routing by phase, not by habit, is the
lever — and because the choice is explicit (`/model` + frontmatter), there is no
opaque router to debug.

## Policy table — phase → tier → rationale

| Phase / skill | Recommended tier | Why this tier is safe / needed |
|---|---|---|
| Requirements, discovery (`/discover`, `/blueprint` strategy) | **opus** | Open-ended reasoning, market/spec synthesis — frontier judgment pays for itself. |
| Architecture, design (`/blueprint` architecture, `architect`/`devils-advocate` agents) | **opus** | Cross-cutting trade-offs held in working memory; cheap models miss interactions. |
| Cross-document / code review (`/review`, `code-reviewer`) | **opus** | Must hold 6 docs + ~30 rubric checks at once; the quality floor of the whole methodology. |
| Security & production judgment (`/security-audit`, `/harden`) | **opus** | Exploitability reasoning and cross-layer hardening are high-stakes, low-volume. |
| Implementation (`/kickstart` codegen, `/bugfix`, `/refactor`) | **opus → sonnet** | Opus for novel/complex logic; sonnet once the pattern is established and the change is mechanical. |
| Test generation (`/test`) | **sonnet** | Pattern-matching against existing test conventions; sonnet covers all major frameworks. |
| Routing & wrap-up (`/task`, `/session-save`, `/doc` formatting) | **sonnet (haiku-class acceptable)** | Mechanical: one routing question, summarize git log, format prose. High volume → cheapest safe tier. |
| LM-judge in eval-suites (`/test` Step 3.5) | **distinct from the generator** | A model judging its own output is biased; pick a different model (often a cheaper one suffices for rubric scoring). |

Tiers are Claude families (opus / sonnet / haiku). The exact model id is whatever is
current — see the `claude-api` skill for live ids; do not hardcode an id here.

## How to apply it

1. **Interactive (conductor mode):** set the tier with `/model <tier>` before invoking
   a phase's skill. Each skill's `## Recommended model` section already names its tier;
   this table is the cross-phase rationale behind those names.
2. **Orchestrated (subagents):** set `model:` in the subagent's frontmatter / the
   `Agent(model: …)` call so each delegated step runs at its phase-appropriate tier.
3. **Cost feedback:** `hooks/cost-tracker.sh` + `/session-save` Step 4.6 make the
   actual spend visible, so the policy can be tuned against real numbers rather than
   guessed. (Accounting only — not an observability platform; see ADR-001.)

## Non-goals (explicit)

- **No automatic cross-vendor routing.** The harness picks one model per agent; this
  policy informs that pick, it does not override it at runtime.
- **No routing daemon / state machine.** Rejected in ADR-001 — it would break the
  "plugin, not CLI" property and add a maintained runtime.
- **No silent downgrade.** Routing to a cheaper tier is a deliberate, visible choice
  (`/model` / frontmatter), never an automatic quality reduction the user can't see.
