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

## Portability boundary

The load-bearing shared policy is **risk/capability monotonicity**: higher-risk
review and security work may not be silently routed below its declared floor,
and model choice may never remove an evidence contour. The concrete
Opus/Sonnet/Haiku names, `/model` command, and `model:` frontmatter below are
the current **Claude Code adapter mapping**, not a cross-provider equivalence
claim.

Codex transports the same risk and effort constraints through its native
model/effort controls and `model-policy.sh` adapter path. Other providers and
hosts are unvalidated until an adapter declares its mapping and passes the
required parity/degradation checks.

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
| Cross-document review — interactive `/review` conductor | **opus** | Must hold 6 docs + ~30 rubric checks at once; the quality floor of the whole methodology. |
| Code review — the `code-reviewer` **subagent** (thin, one focused diff) | **sonnet + high effort** | Dispatched with a thin prompt against one target by path, it holds a bounded diff, not 6 docs — `sonnet`+`high` covers it (per `AGENT_EFFORT_TIERS.md`); `effort` buys the depth here, not `model`. |
| Security & production judgment (`/security-audit`, `/harden`, `security-reviewer`) | **opus** | Exploitability reasoning and cross-layer hardening are high-stakes, low-volume — and, being the higher-risk verify class, its model tier must never sit below the code reviewer's (see "Risk-tier ⇒ model monotonicity" below). |
| Implementation (`/kickstart` codegen, `/bugfix`, `/refactor`) | **opus → sonnet** | Opus for novel/complex logic; sonnet once the pattern is established and the change is mechanical. |
| Test generation (`/test`) | **sonnet** | Pattern-matching against existing test conventions; sonnet covers all major frameworks. |
| Routing & wrap-up (`/task`, `/session-save`, `/doc` formatting) | **sonnet (haiku-class acceptable)** | Mechanical: one routing question, summarize git log, format prose. High volume → cheapest safe tier. |
| LM-judge in eval-suites (`/test` Step 3.5) | **distinct from the generator** | A model judging its own output is biased; pick a different model (often a cheaper one suffices for rubric scoring). |

Tiers are Claude families (opus / sonnet / haiku). The exact model id is whatever is
current — see the `claude-api` skill for live ids; do not hardcode an id here.

## How to apply it

1. **Claude Code interactive mode:** set the tier with `/model <tier>` before invoking
   a phase's skill. Each skill's `## Recommended model` section already names its tier;
   this table is the cross-phase rationale behind those names.
2. **Claude Code orchestrated mode:** set `model:` in the subagent's frontmatter / the
   `Agent(model: …)` call so each delegated step runs at its phase-appropriate tier.
3. **Supported-host cost feedback:** `hooks/cost-tracker.sh` + `/session-save` Step 4.6 make the
   actual spend visible, so the policy can be tuned against real numbers rather than
   guessed. (Accounting only — not an observability platform; see ADR-001.)

Speed claims, credit ratios and dated model IDs are **not a methodology contract**.
Provider behaviour changes independently of this repository. Routing economics are
accepted only from host-observed telemetry and the frozen A/B comparison for the
actual candidate; documentation must not turn a temporary public multiplier into a
stable SLA.

## Risk-tier ⇒ model monotonicity (invariant, v1.60.0 — Ось 2)

Routing to a cheaper tier is legitimate — but the **higher-risk** a verify agent's
surface is, the **higher** (never lower) its model tier must be. Concretely: the
`security-reviewer` gates the highest-stakes surface (exploitability, production
safety), so its `model` frontmatter is never below the `code-reviewer`'s. Today
`security-reviewer` = `opus`, `code-reviewer` = `sonnet` — monotone. This is not a
comment we hope stays true: `tests/verify_model_risk_monotonic.py` parses the
`model:` frontmatter of both agents and FAILS CI if the ordering ever inverts (a
future cost-cut that quietly drops `security-reviewer` to `sonnet` while
`code-reviewer` is `opus`, say). The gate also pins this table and
`AGENT_EFFORT_TIERS.md` to the actual frontmatter, so the *contract* (the docs)
can no longer invert from the *model* (the frontmatter) — the class of drift this
invariant exists to kill.

## Low-effort eligibility (PE5-015)

`effort` is a reasoning-budget dial, not permission to remove evidence. Automatic
low effort is limited to a bounded, mechanical slice of an active
`working_deadline` unit whose risk is known to be low/medium. A per-call downgrade
must make the slice visible by starting its `description` with
`[itd:mechanical]`; the existing `model-policy.sh` hook checks the active ledger.

Review, security, root-cause, architecture, high-risk and unknown-risk work retain
their declared quality floor. The protected agents (`code-reviewer`,
`security-reviewer`, `architect`, `devils-advocate`, `perf-analyzer`, and
`test-generator`) are never silently lowered to `effort=low`. An unsafe explicit
override produces a host-native ASK with WHY/FIX; keeping the frontmatter default
is silent. This remains an oversight/policy boundary, not a new hard gate, and the
user's model/effort choice can never remove a review, security, test, release, or
other required evidence contour.

## Non-goals (explicit)

- **No automatic cross-vendor routing.** The harness picks one model per agent; this
  policy informs that pick, it does not override it at runtime.
- **No routing daemon / state machine.** Rejected in ADR-001 — it would break the
  "plugin, not CLI" property and add a maintained runtime.
- **No silent downgrade.** Routing to a cheaper tier is a deliberate, visible choice
  (`/model` / frontmatter), never an automatic quality reduction the user can't see.
