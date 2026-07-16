# LAUNCH PLAN — idea-to-deploy: New-SDLC / Vibe-Coding enrichment

**Last reviewed:** 2026-07-16
**Source:** Google whitepaper *The New SDLC With Vibe Coding* (Day 1; Osmani, Saboo,
Kartakis; 2026). Decision record: [ADR-001](docs/adr/ADR-001-no-own-runtime.md).

**Decision (locked):** enrich the methodology with all four identified points, but as
**врезки into existing skills (not new skills)** — avoids the ~4-artifact + doc-cascade
cost per new skill. Scoped / opt-in, honestly named (else our own `meta_review` M-C12
"docs vs code" would flag over-claiming). Order: **A + D (P0) → C (P1) → B (P1).**

**Target:** lift the methodology into the paper's "agentic engineering" vocabulary
without inflating surface; `meta_review.py` Critical = 0 at every step; skills 38 → 38,
hooks 19 → 19 (no count cascade).

**Portfolio rationale:** the user's near-term products are mostly AI/agents over
marketplace commerce (repricing, SKU unit-economics, demand assortment, auto-buying,
auto-buyout + auto-order, FX/treasury, financial autopilot — invoice/report parsing &
reconciliation, AI content/translation, customer-service + non-buyout predictor, and
the NeuroExpert product). Several move real money → evals (A) become first-class, not
niche, and the irreversible-action human-gate (D) is mandatory.

---

## Block A — Eval-branch in /test (+/harden) — P0 — ✅ DONE (v1.31.0)

When `side_effect: agent/LLM`, generate an eval-suite (rubric + LM-judge stub +
trajectory scaffold) into the user's `evals/`, not just tests. **Opt-in/scoped, NOT a
global gate** (acceptance-gate lesson — false blocks).

- `skills/test/SKILL.md` — `Step 3.5: Eval-suite branch`.
- `skills/test/references/test-frameworks.md` — "LLM / agent eval patterns" section.
- `skills/harden/SKILL.md` — Tier-3 informational check `EVAL-1`.

## Block D — "80%-problem" checklist in /review — P0 — ✅ DONE (v1.31.0)

Catch the failure-prone last 20% of vibe-coded output. (`/code-review` is a harness
command, not our skill → врезка lands in `/review` only.)

- `skills/review/references/review-checklist.md` — `C-code-5` slopsquatting/hallucinated
  deps (Critical), `C-code-6` irreversible external action without human-gate
  (Critical), `I-code-10` business invariants, `I-code-11` edge-case completeness.
- `skills/review/SKILL.md` — tier ranges + "New in v1.31.0" note.

## Block C — token/OpEx cost-accounting врезки — P1 — ✅ DONE (v1.31.0)

Lightweight accounting on top of the EXISTING `cost-tracker.sh` + ctx-stats. **No new
hook, not an observability platform.**

- `skills/session-save/SKILL.md` — `Step 4.6: Cost snapshot`.
- `skills/task/SKILL.md` — cost-awareness nudge in Step 1b.
- `skills/context-mode-setup/SKILL.md` — "Cost visibility" section.

## Block B — model-routing policy — P1 — ✅ DONE (v1.31.0)

Phase → tier → rationale, applied via native `/model` + per-agent frontmatter. **Not an
auto-router.**

- `docs/MODEL-ROUTING-POLICY.md` — the policy table; pointer from README Recommended
  Models section.

---

## Block E — Day-3 Context Engineering (memory & context) — P1 — ✅ DONE (v1.32.0)

Source: Google *New SDLC With Vibe Coding*, Day 3 (*Context Engineering: Sessions,
Memory* — Milam, Gulli, Nawalgaria, 2026). Two-lens review (business-analyst +
devils-advocate): ~80% is product-design, not process → lands as opt-in врезки the
methodology emits when designing a stateful agent, plus one money-portfolio guardrail.

- **Design (output):** `/blueprint` Step 1.6 memory-architecture checklist (opt-in,
  stateful-agent), `/discover` Step 7.5 statefulness flag.
- **Security (most differentiated):** `/security-audit` `MEM-1…MEM-6` agent-memory
  threat model.
- **Gate (money portfolio):** `/review` `C-code-7` context integrity + `MEMORY_RE`
  signal in the DoD pre-commit hook (requires `/security-audit` on agent-memory paths).
- **Runtime + eval + hygiene:** `/harden` `MEM-1`, `/test` Step 3.5 memory-quality
  dimension, `/session-save` pointer to `consolidate-memory`. ADR-001 Day-3 note.
- Counts unchanged (38/19); no new skill, no new hook file. `verify_dod_gate.py`
  19/19. Decisions: gate (not advice) + opt-in flag (not new product type) — confirmed
  by the user.

## Block F — Day-5 Spec-Driven Production (Zero-Trust + SDD) — P1 — ✅ DONE (v1.33.0)

Source: Google *New SDLC With Vibe Coding*, Day 5 (*Spec-Driven Production* — Boonstra
et al., 2026). Two-lens review: ~70% already covered (evals, prompt-injection,
agent-memory, cross-review, cost/routing from Day-1/3). Real delta = Zero-Trust runtime
guardrails (no prior coverage) + spec-driven culture shift. Scope C (Zero-Trust + SDD),
semantic gating advisory-only — user-confirmed.

- **Zero-Trust (the differentiated gap):** `/harden` `ZT-1` (policy server, sandbox,
  HITL, advisory semantic gating), `/security-audit` `MEM-7` (context hygiene /
  tool-arg sanitization), `/blueprint` Step 1.6 point 8 (guardrail-layer design).
- **SDD culture:** `/blueprint` spec-as-source + single-AGENTS.md pointer, `/adopt`
  instructional-fragmentation flag, `/review` Conditional-LGTM / Bundled-Risk format.
- **Icebox (ADR-001):** `agents-cli` owned runtime rejected; semantic gating = ASK,
  never a hard inferential gate (retired score-gate lesson).
- Counts unchanged (38/19); no new skill, no new hook file. ADR-001 Day-5 note.

## Block G — `working_deadline` throughput profile — P0 — 🚧 ACTIVE (PE5-010…PE5-016)

Implement the approved opt-in working-deadline mode without weakening the
frozen Practical Effectiveness or Harness Conformance oracles:

- **PE5-010 — contract first:** freeze the 30/45-minute boundaries, one-unit
  handoff, risk-preserving targeted/release semantics, exact review/external
  action bindings and rollback triggers before runtime changes.
- **PE5-011 — runtime:** host-observed checkpoint/hard-pause enforcement and
  typed recovery state; partial work never becomes verified.
- **PE5-012 — verification cadence:** impact-closed targeted checks for daily
  work and exact-candidate release evidence; diagnostic failure collection and
  backlog boundaries.
- **PE5-013 — review/risk:** successful context-bound cache only; separate
  general and security risk-budget paydown.
- **PE5-014 — external writes:** preview and approval bound to exact targets and
  canonical payload hash.
- **PE5-015 — model routing:** low effort only for bounded mechanical work;
  review/security/root-cause/architecture retain their quality floor.
- **PE5-016 — no-regression:** frozen A/B plus current HE/PE, host-adapter,
  meta-review, quick and full local evidence.

The profile remains default-off through the contract/runtime rollout. It may
become a default only after the sealed canary/comparable-unit thresholds pass;
external adoption evidence remains independent and is never synthesized from
this internal benchmark.

## Backlog / next

- **P2 (deferred):** analyze Day 3 (Context Engineering) and Day 5 (Spec-Driven
  Production) of the series — technically more concrete than Day 1; likely a
  "context-design step for agent products" follow-up on top of `context-mode-setup`.- **P2 (deferred):** analyze Day 5 (Spec-Driven Production) of the series. Day 3
  (Context Engineering) — ✅ done in v1.32.0 (Block E above).- **Series complete.** Day 1 (v1.31.0, Blocks A/D/C/B), Day 3 (v1.32.0, Block E),
  Day 5 (v1.33.0, Block F) all ported. No further whitepaper days outstanding.
- **Marketing (free win):** use the whitepaper as external validation in
  `docs/competitive-analysis.md` / promo ("structure scales, vibes don't", "agent =
  model + harness") — the user's portfolio *is* the agentic-engineering thesis.

## Icebox (rejected — ADR-001)

Standalone eval-runner / CLI; auto cross-vendor model router; own observability
platform; `itd` daemon / state machine.

## Release / gates per merge

врезки = MINOR bump. Bump `plugin.json` + `marketplace.json` + both README badges +
`CHANGELOG.md` + git tag + GitHub Release + `scripts/sync-to-active.sh`. Skill/hook
counts unchanged (38/19). Gates: `python tests/meta_review.py --verbose` → PASSED
(Critical 0); `python scripts/verify_skill_profiles.py`; `/review --self`.
