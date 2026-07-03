# Contracts & Gates — the `.itd/` layer

> Plugin-native port of the executable-methodology ideas from **product-factory-os** (PFO, a Codex CLI runtime) into idea-to-deploy **without** building a standalone runtime.

## Decision: plugin, not runtime

PFO turned the methodology into an executable runtime: a `pfo` CLI, Python validators, an `install.sh`, and on-disk state. idea-to-deploy is, by design, a **Claude Code plugin** that "does not run as a standalone CLI" (see `README.md`).

We audited PFO's improvements against that identity. The result:

- **~19 of PFO's mechanisms are plugin-native** — they are just **templates + hooks + CI scripts**, and idea-to-deploy already has all three substrates (`skills/`, `hooks/`, `tests/` + GitHub Actions).
- **Only 2 genuinely require a runtime** — the `itd` CLI and `install.sh` workspace installer — and those are the **lowest-ROI** items for a plugin. They are explicitly **out of scope** here. If a runtime is ever wanted, it belongs in a separate optional repo, not in the plugin core.

So idea-to-deploy stays a plugin and absorbs ~90% of PFO's value as **contracts (what must stay true) + gates (what blocks) + evidence (what proves done)**, instead of "we hope the agent followed the instruction".

## The contract layer

Per-project, idea-to-deploy scaffolds a `.itd/` directory (project-owned, machine + human readable) plus a `.itd-memory/` directory (structured state, kept separate from the existing freeform memory/`MEMORY.md`). Templates live in `docs/templates/itd/` and `docs/templates/`.

**Who scaffolds it (v1.40.0 — closes the "templates without a creator" gap):** greenfield — `/kickstart` Phase 3 step 7 creates `.itd/` + `.itd-memory/STATE.json` as part of the dedicated initialization phase, gated by the Initialization Acceptance Checklist; brownfield — `/adopt` Step 3.5 offers the same scaffold as a recommended **opt-in** (the v1.39.0 tradeoff stands: contracts are never forced onto an existing project). Before v1.40.0 the templates existed and the gates consumed them, but no skill ever created the files — a contract that is not on disk blocks nothing.

| Artifact | What it pins down |
|---|---|
| `.itd/PROJECT_CONTRACT.md` | Invariants, real data sources, provider/output/deploy contracts |
| `.itd/SCOPE_LOCK.md` | Allowed vs forbidden change areas for the current task |
| `.itd/GOLDEN_FLOWS.md` | Smallest user journeys that prove the product still works |
| `.itd/FORBIDDEN_CHANGES.md` | Changes blocked unless explicitly scoped |
| `.itd/DATA_POLICY.md` | Real vs synthetic data rules + required evidence |
| `.itd/FALLBACK_POLICY.md` | Allowed vs forbidden fallbacks (no silent substitution) |
| `.itd/VERIFICATION_CONTRACT.json` | Executable verify commands; **fail-closed** |
| `.itd/ACCEPTANCE_CONTRACT.json` | "Done" as a proof checklist derived from the user request |
| `.itd/EXECUTION_POLICY.json` | Command / write / network / approval policy |
| `.itd/PERMISSION_MATRIX.{json,md}` | Who/what may read, write, execute, publish |
| `.itd/TOOL_CAPABILITY_REGISTRY.json` | Tool/connector side-effects, auth, risk, fallback |
| `.itd/LEARNING_PROMOTION_GATE.md` | Gate for promoting session learnings into durable docs |
| `.itd/UNIT_CONTEXT_MANIFEST.json` | Fresh, bounded context for a single execution node (template lives at `docs/templates/UNIT_CONTEXT_MANIFEST.json`; created per unit, NOT part of the 13-file `.itd/` scaffold) |
| `.itd-memory/STATE.json`, `events.jsonl`, `LEARNINGS.jsonl` | Structured state, audit log, learnings |
| `ROOT_CAUSE.md`, `BRANCH_FINISH.md` | Bugfix root-cause record; branch-finish decision |

## Port status — 19 plugin-native mechanisms

Legend: ✅ done · 🚧 in progress · ⬜ planned · vector = how it lands in the plugin.

### Wave 0 — contract foundation (templates)
| # | Mechanism | Vector | Status |
|---|---|---|---|
| 1 | `.itd/` contracts (SCOPE_LOCK, GOLDEN_FLOWS, FORBIDDEN_CHANGES, PROJECT_CONTRACT, DATA/FALLBACK, VERIFICATION) | templates | ✅ |
| 2 | Acceptance contract from request | template `ACCEPTANCE_CONTRACT.json` | ✅ |
| 3 | Unit Context Manifest | template `UNIT_CONTEXT_MANIFEST.json` | ✅ |
| 4 | Root-cause record | template `ROOT_CAUSE.md` | ✅ |
| 5 | Branch-finish record | template `BRANCH_FINISH.md` | ✅ |
| 6 | Tool capability registry + permission matrix | templates `TOOL_CAPABILITY_REGISTRY.json`, `PERMISSION_MATRIX.*`, `EXECUTION_POLICY.json` | ✅ |
| 7 | Learning promotion gate | template `LEARNING_PROMOTION_GATE.md` | ✅ |

### Wave 1 — gates (hooks + skill wording)
| # | Mechanism | Vector | Status |
|---|---|---|---|
| 8 | Fail-closed verification (no evidence → not `passed`) | `/test` Step 5, `/review` Stage A wording | ✅ |
| 9 | Root-cause gate for `/bugfix` (require `ROOT_CAUSE.md`) | `/bugfix` Step 3 | ✅ |
| 10 | Two-stage `/review` (spec compliance → code quality) | `/review` Stage A pre-gate | ✅ |
| 11 | TDD evidence gate (red/green) | `/test` Step 5 | ✅ |
| 12 | Branch-finish workflow | `/session-save` Step 4.8 | ✅ |
| 13 | Skill-contract frontmatter (`effort`/`side_effect`/`explicit_invocation`) + validator | frontmatter on all 25 `skills/*/SKILL.md` + `scripts/verify_skill_profiles.py` | ✅ |

### Wave 2 — state, routing, research skills
| # | Mechanism | Vector | Status |
|---|---|---|---|
| 14 | State schema (`STATE.json` + `events.jsonl`) + `validate_state.py` | `docs/templates/itd-memory/` + `scripts/validate_state.py` | ✅ |
| 15 | Complexity-based routing (signals, not "minimal/standard/full") | `_shared/helpers.md` §6 + `/task` Step 1b + `/project` Step 3b | ✅ |
| 16 | Context budget (summary + artifact path, not raw dumps) | `_shared/helpers.md` §7 + `hooks/context-budget.sh` (soft) | ✅ |
| 17 | Metrics (`itd_metrics`) | `scripts/itd_metrics.py` | ✅ |
| 18 | `/browser-check`, `/github-workflow`, `/market-scan`, `/mcp-docs`, `/tool-sync`, `/obsidian-export`, `/grill-me`, `/handoff` | new skills | ✅ 8/8 — all ported (commits 817df60, 5b61142, 97fbb82, + browser-check/obsidian-export). New README categories "Research" (market-scan+mcp-docs) and "Integration" (github-workflow+tool-sync+obsidian-export); browser-check → Quality Assurance. github-workflow/tool-sync are explicit-invocation. browser-check ships its Playwright runtime under `skills/browser-check/playwright/`. |
| 19 | Enhance `/adopt` analyzer; golden-paths + starters; new agents pack | skill + templates + agents | ✅ — golden-paths (5) + starters (5) in `golden-paths/`+`starters/` (616754c); reviewer agents pack researcher/security-reviewer/ux-reviewer, 7→10 (d040636); `/adopt` Step 0.6 product-type analyzer → starter/golden-path hint into the `/blueprint` chain. |

## Explicitly out of scope (runtime, low ROI)
- `itd` standalone CLI (`itd new/adopt/validate/status/resume`) — conflicts with plugin identity.
- `install.sh` workspace installer — plugins install via `/plugin install`.
- PFO skills not present in PFO's own `skills/`: there is **no `/seo` and no `/brainstorm`** in PFO (a prior analysis hallucinated them) — not ported.
- `/skill-create` — already covered by the Anthropic `skill-creator` skill; low marginal value.

## Known follow-up (doc drift)

**✅ RESOLVED (v1.21.0 docs-sync pass).** All published descriptions now carry the
current counts — **39 skills + 10 specialized subagents + 19 enforcement hooks**:
`.claude-plugin/plugin.json` `description` (also lists the new capabilities:
research, browser smoke-testing, MCP docs, context handoff, external-tool sync,
Obsidian export, decision stress-testing), `.claude-plugin/marketplace.json`,
`README.md` / `README.ru.md` (badges + prose + Skill Contracts + Recommended
Models), and the M-C12-checked promo/draft docs (`marketplace-submissions.md`,
`habr-*`). The M-C12/M-C13/M-C15-checked surfaces are enforced by CI.

**Intentionally left as dated historical snapshots** (not live claims, skipped by
M-C12): `docs/DESIGN_SPACE.md` (the `v1.20.3` commit-`df2c25e` snapshot + its
principle-table analysis) and `docs/competitive-analysis.md` (a dated competitor
comparison). These describe the repo *as analysed on a specific date*; rewriting
them would falsify the snapshot. Update them only when the analysis itself is
redone.

## Note on enforcement
Templates are inert until wired. Wave 1 is what makes them bite: idea-to-deploy's hooks (`check-*`, `freeze.sh`, `pre-flight-check.sh`) and CI (`tests/meta_review.py`) are the enforcement substrate. Until a gate hook references a contract, the contract is documentation, not a sensor — Wave 1 closes that gap.
