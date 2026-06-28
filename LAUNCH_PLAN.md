# LAUNCH PLAN — idea-to-deploy: New-SDLC / Vibe-Coding enrichment

**Last reviewed:** 2026-06-28
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

## Backlog / next

- **P2 (deferred):** analyze Day 3 (Context Engineering) and Day 5 (Spec-Driven
  Production) of the series — technically more concrete than Day 1; likely a
  "context-design step for agent products" follow-up on top of `context-mode-setup`.
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
