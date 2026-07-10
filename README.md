# idea-to-deploy

> Complete project lifecycle methodology for Claude Code — from idea to deployed product in one command.

**Install in 30 seconds:**

```bash
/plugin install hihol-labs/idea-to-deploy
```

Then just describe what you want in Claude Code — methodology routes you automatically. [Full install guide](#quick-start) · [End-to-End Example](#end-to-end-example) · [Skill Contracts](#skill-contracts).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Skills: 40](https://img.shields.io/badge/Skills-40-green.svg)](#skills)
[![Agents: 10](https://img.shields.io/badge/Agents-10-orange.svg)](#subagents)
[![Version: 1.73.0](https://img.shields.io/badge/Version-1.73.0-purple.svg)](.claude-plugin/plugin.json)
[![meta-review](https://github.com/hihol-labs/idea-to-deploy/actions/workflows/meta-review.yml/badge.svg)](https://github.com/hihol-labs/idea-to-deploy/actions/workflows/meta-review.yml)
[![Status: Stable](https://img.shields.io/badge/Status-Stable-brightgreen.svg)](CHANGELOG.md)
[![Type: Claude Code Plugin](https://img.shields.io/badge/Type-Claude%20Code%20Plugin-blueviolet.svg)](.claude-plugin/plugin.json)

**[Русская версия (README.ru.md)](README.ru.md)** · **[Changelog](CHANGELOG.md)** · **[Contributing](CONTRIBUTING.md)** · **[CI](docs/CI.md)**

> This repository is a **Claude Code plugin** (see `.claude-plugin/plugin.json`). Installing it registers 40 skills and 10 subagents into your Claude Code environment — it does not run as a standalone CLI.

## Demo

<p align="center">
  <img src="docs/demo.svg" alt="idea-to-deploy kickstart demo" width="788">
</p>

> See the [End-to-End Example](#end-to-end-example) below for a detailed walkthrough.

---

## The Problem

Claude Code is powerful, but without instructions it works like a builder without blueprints:
- Writes code randomly, skips tests, doesn't document
- Each time produces different structure and quality
- Can break what already works
- No methodology — just chaotic generation

## The Solution

**idea-to-deploy** is a methodology, not just a set of tools. 40 skills + 10 specialized agents that turn Claude Code into a professional developer with a proven pipeline:

```
Idea → Questions → Plan → Architecture → Code → Tests → Review → Deploy
```

Every step is verified. Every feature is tested. Every decision is documented. Every session is preserved.

## Quick Start

### Installation

**Requirements:**
- [Claude Code](https://claude.com/claude-code) CLI ≥ 2.0 (or the VS Code / JetBrains extension) with plugin support
- Claude Pro / Team / Enterprise subscription
- `git` available on `PATH` (used by several skills)

**Install the plugin:**

```bash
/plugin install hihol-labs/idea-to-deploy
```

**Verify the installation:**

After installation, the skills and agents are registered under:

```
~/.claude/plugins/idea-to-deploy/
  ├── skills/          # 40 skill directories
  ├── agents/          # 10 subagent definitions
  └── hooks/           # optional enforcement hooks (not auto-installed)
```

Quick sanity check inside Claude Code:

```
/project
```

If the router prompt appears and offers routes A / B / C, the plugin is live.

**Updating:**

```bash
/plugin update hihol-labs/idea-to-deploy
```

**Uninstalling:**

```bash
/plugin uninstall hihol-labs/idea-to-deploy
```

See the [CHANGELOG](CHANGELOG.md) for release notes.

### Usage

Just say what you want:

```
I want to build a food delivery service
```

Claude Code will:
1. Ask which route you prefer (full cycle / planning only / have docs)
2. Ask clarifying questions about your project
3. Generate architecture and documentation
4. **Show you the plan and wait for your approval**
5. Build the project step by step
6. Test and review after each step
7. Deploy

When you're done for the day, just say:

```
save session
```

Your session context — decisions, progress, blockers, next steps — will be saved and automatically restored in your next session.

## How It Works

```
You: "I want to build a delivery app"
         |
         v
    /project (smart router)
         |
    Asks: A, B, or C?
         |
    +----+--------+--------+
    v              v              v
  A) Full        B) Plan       C) Guide
  Cycle          Only          Only
    |              |              |
    v              v              v
 /kickstart    /blueprint     /guide
    |
    +-- Asks clarifying questions
    +-- Generates 7 documents
    +-- Runs /review (auto-validation)
    +-- PAUSE: shows plan, waits for approval
    +-- Scaffolds project
    +-- Implements step by step:
    |     +-- /test after each feature
    |     +-- Code vs Architecture check
    |     +-- Fix issues before next step
    +-- Deploys
```


## End-to-End Example

A minimal walkthrough of Route A (full cycle):

```
You:   I want to build a Telegram bot that tracks my gym workouts
Claude: [/project] A, B, or C?
You:   A
Claude: [/kickstart] asks 6 clarifying questions
        (users? auth? DB? hosting? budget? deadline?)
You:   personal use, no auth, SQLite, local, $0, this weekend
Claude: generates STRATEGIC_PLAN, PROJECT_ARCHITECTURE,
        IMPLEMENTATION_PLAN, PRD, README, CLAUDE_CODE_GUIDE, CLAUDE.md
        runs /review → PASSED_WITH_WARNINGS (2 nits)
        shows plan, asks: "Approve and start coding?"
You:   yes
Claude: Step 1/9 — scaffold project, commit
        Step 2/9 — DB models + /test
        ...
        Step 9/9 — deploy script + README update
        Done. 42 tests passing. Here is your bot.
```

**Reference fixtures:** reproducible golden-path scenarios used by the test runner live in [`tests/fixtures/`](tests/fixtures/). Run them with [`tests/run-fixtures.sh`](tests/run-fixtures.sh) to see how each skill behaves on a known input.

## Skills

### Entry Points (6 skills)

| Skill | Description |
|-------|-------------|
| `/project` | Smart router for **creating** something — asks one question and routes to /kickstart, /blueprint, or /guide |
| `/task` | Smart router for **working on existing code** — routes to the right daily-work skill (/bugfix, /refactor, /doc, /test, /perf, /review, ...) based on the task type |
| `/adopt` | **New in v1.20.0.** Onboard a legacy project into the methodology — append idempotent `CLAUDE.md` block, register project-level hooks in `.claude/settings.json`, bootstrap memory dir, then voice-chain to `/strategy` or `/blueprint` for plan documents. No reverse-engineering of plan docs. |
| `/discover` | **New in v1.17.0.** Product discovery phase — market analysis (TAM/SAM/SOM), competitor research, user personas, feature prioritization (MoSCoW + RICE). Outputs `DISCOVERY.md` ready for `/blueprint`. |
| `/strategy` | **New in v1.19.0.** Strategic replanning for existing projects — 5-dimension gap analysis, option generation with devil's advocate, ADR for pivot decisions, LAUNCH_PLAN.md updates. |
| `/advisor` | **New in v1.19.0.** Advisory/consulting mode — analysis-only (no code changes), multi-perspective evaluation via business-analyst + devils-advocate subagents. |

### Project Creation (3 skills)

| Skill | Route | What it does |
|-------|-------|-------------|
| `/kickstart` | A) Full cycle | Idea to deployed product: docs, code, tests, deploy |
| `/blueprint` | B) Planning only | 6 documentation files, no code |
| `/guide` | C) Have docs already | You already have architecture and plan docs (from route B, another developer, or another tool) — generates step-by-step prompts to build it |

### Quality Assurance (6 skills)

| Skill | Description |
|-------|-------------|
| `/review` | Validates documentation and code quality via deterministic binary rubric (BLOCKED / PASSED_WITH_WARNINGS / PASSED) |
| `/security-audit` | Read-only OWASP-style security audit (auth, secrets, injection, CORS/CSP, deps) with same status enum as `/review` |
| `/security-guidance-setup` | **New in v1.29.0.** Security companion — sets up & integrates the official [security-guidance plugin](https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance) by Anthropic (free, ships default-on). A shift-left, always-on reviewer of Claude-generated code: regex pattern warnings on every Edit/Write, an LLM diff review on Stop (findings fed back before you see the turn), and an agentic commit/push reviewer tracing cross-file vulns (IDOR, auth bypass, SSRF). Detects install, prints the verified CLI command, maps it onto the lifecycle. **Complements** `/security-audit` (on-demand audit), does **not** replace it; does not vendor upstream code; gates unaffected. |
| `/cross-review` | **New in v1.30.0.** Cross-vendor second-opinion review — runs an INDEPENDENT external model (OpenAI Codex CLI or Gemini CLI) over the current diff to catch blind spots a Claude-only `/review` shares with the code it produced. Scrubs secrets/PII before egress; fail-open chain codex → gemini → native Claude red-team review. **Additive** to `/review` (the mandatory floor), never a gate. Ported from the omnigent cross-vendor-review concept. |
| `/grill-me` | **New in v1.21.0.** Interactive read-only stress-test for plans, designs, architecture, and risky decisions — asks one question at a time (with a recommended answer) to surface assumptions, risks, and dependencies. Runs before `/review`, does not replace it. |
| `/browser-check` | **New in v1.21.0.** Local browser smoke-test for frontend/full-stack/visual flows via a bundled Playwright harness (Browser Use / in-app browser fallback) — checks first render + critical path (navigation, forms, states). Broken render/flow → BLOCKED before deploy. |

### Daily Work (6 skills)

| Skill | Description |
|-------|-------------|
| `/test` | Generate unit, integration, and edge case tests |
| `/bugfix` | Systematically find and fix bugs (was `/debug` before v1.4.0 — renamed to avoid collision with Claude Code's built-in `/debug` slash command) |
| `/perf` | Performance analysis and optimization |
| `/refactor` | Improve code structure without changing behavior |
| `/explain` | Explain how code works with ASCII diagrams |
| `/doc` | Generate documentation matching project style |

### Quality Assurance — Supply Chain (1 skill, new in v1.4.0)

| Skill | Description |
|-------|-------------|
| `/deps-audit` | Read-only dependency audit — parses lockfiles, queries OSV.dev + GitHub Advisory for known CVEs, SPDX license compatibility, abandoned-package detection (> 2y without release). Same status enum as `/review`. |

### Operations (5 skills)

| Skill | Description |
|-------|-------------|
| `/migrate` | Apply database migrations safely — backup, apply, verify, document rollback. Refuses production without explicit confirmation. |
| `/migrate-prod` | **New in v1.19.0.** Migrate running production services between hosts — inventory, setup target, data migration, dual-run, DNS cut-over, rollback plan, decommission. |
| `/deploy` | **New in v1.19.0.** Deploy to production — sync files (tar-over-ssh), regenerate gateway config, build Docker image, restart containers, apply pending migrations, verify healthcheck. Refuses without explicit user confirmation; always calls `/session-save` after. |
| `/harden` | **New in v1.4.0.** Production-readiness hardening rubric — health checks, graceful shutdown, structured logging, rate limiting, Prometheus/Grafana, backup strategy, k6 load tests, SRE runbook. Generates missing artifacts on user approval. |
| `/infra` | **New in v1.4.0.** Infrastructure-as-code generator — Terraform modules (DigitalOcean, AWS, Hetzner), Kubernetes manifests + Helm chart, secrets wiring (Vault, AWS Secrets Manager, Doppler, Sealed Secrets). Remote tfstate with locking enforced for prod. |

### Workflow (5 skills)

| Skill | Description |
|-------|-------------|
| `/session-save` | Save session context to project memory — what was done, key decisions, blockers, next steps. Ensures continuity between Claude Code sessions. |
| `/autopilot` | Auto-pipeline that runs discover → blueprint → kickstart → review → test with minimal human intervention (GSD-inspired). Takes a project idea and produces a full project with all docs, code, tests, and review. |
| `/handoff` | **New in v1.21.0.** Write a compact `HANDOFF.md` context packet to transfer work to the next session/agent when there is no return path — compaction, delegation, AFK run, or recovery. Distinct from `/session-save` (milestone save). |
| `/goal` | **New in v1.44.0.** Long-goal mode — decompose a multi-session goal into ordered verifiable units in `.itd-memory/GOAL.json` (user approval required), drive them one at a time through the standard `/task` pipeline (WIP=1, evidence-gated `verified`), and resume across sessions from the first non-verified unit. Brownfield-first; not a gate — never bypasses `/review`, `/test`, or the DoD. |
| `/retro` | **New in v1.46.0.** Self-proposing improvement cycle for the methodology itself, split FACTS / PROPOSALS / MERGE: `itd_retro_scan.py` deterministically aggregates telemetry (VCR, regressions, active goals, SKILL_BYPASS ledger, cost), the model turns facts into ranked proposals where every one cites evidence (anti-Goodhart: external signals only), and the human merges via the ordinary release pipeline. Never edits the methodology itself; not a gate. |

### Research (2 skills)

| Skill | Description |
|-------|-------------|
| `/market-scan` | **New in v1.21.0.** Fresh public market & community signal scan (~30-day window via the `last30days` engine) for discovery, validation, ICP, competitor, and launch decisions. Normalizes findings into `MARKET_BRIEF.md` (dated append). Distinct from `/discover` (full discovery phase). |
| `/mcp-docs` | **New in v1.21.0.** Read-only lookup of fresh library/framework documentation via MCP providers (Context7) — resolves a library ID, asks a narrow question, records source + decision. Use before adding dependencies or integrating against SDKs. |

### Integration (4 skills)

| Skill | Description |
|-------|-------------|
| `/github-workflow` | **New in v1.21.0.** GitHub Issues / PR / CI / release workflow — inspects PR & check status (connector or `gh`), debugs failing Actions before code changes, prepares branches/changelogs/release notes, keeps `.rubric-status` aligned. Explicit-invocation; no push/merge/close/release without explicit intent. |
| `/tool-sync` | **New in v1.21.0.** Mirror idea-to-deploy artifacts to external tools — GitHub, Linear, Notion, Google Drive, Obsidian. Connector-native reads before writes (reconcile, never clobber), export-only fallback to `.itd-integrations/`. Explicit-invocation. |
| `/obsidian-export` | **New in v1.21.0.** Export planning docs, handoff, memory, state, decisions, and gates into an Obsidian-compatible local knowledge graph under `.itd-integrations/obsidian/`. Derived & regenerable — canonical docs stay the source of truth. |
| `/seo-setup` | **New in v1.28.0.** SEO companion — sets up & integrates the upstream [Claude SEO plugin](https://github.com/AgriciDaniel/claude-seo) (MIT), which ships 25 sub-skills + 18 sub-agents for technical SEO, content quality (E-E-A-T), Schema.org, sitemaps, Core Web Vitals, local SEO, backlinks, AI/GEO, hreflang, and the Google SEO APIs. Detects install, runs/prints the verified CLI commands, and maps it onto the lifecycle (discover→keyword/competitor, blueprint→schema/hreflang, kickstart→on-page, harden→technical/CWV/GEO, deploy→drift baseline + Google APIs). Named `-setup` to avoid colliding with upstream's own `seo` skill. Does **not** vendor upstream code; gates are unaffected. |

### Efficiency (2 skills)

| Skill | Description |
|-------|-------------|
| `/caveman` | **New in v1.26.0.** Token-efficiency communication mode — terse caveman-style replies (`lite`/`full`/`ultra`/`wenyan-*`) that cut output tokens ~75% while keeping full technical accuracy. Port of the public [Caveman plugin](https://github.com/JuliusBrussee/caveman) (MIT). idea-to-deploy gates still win over brevity: never compresses gate status, blockers, verification evidence, security warnings, or destructive confirmations. Style control only — does not replace `/review`, `/test`, or any work route. |
| `/context-mode-setup` | **New in v1.27.0.** Context-window optimization companion — sets up & integrates the upstream [Context Mode plugin](https://github.com/mksglu/context-mode) (ELv2), which sandboxes large tool output into a local FTS5 store so the agent searches it (`ctx-search`) instead of dumping it into context (vendor claim ~98% per-call reduction). Detects install, runs/prints the verified CLI commands, and maps its `ctx-*` skills onto the lifecycle (long `/kickstart` builds, long `/task`/`/bugfix` sessions). Named `-setup` to avoid colliding with upstream's own `context-mode` skill. Does **not** vendor upstream ELv2 code; gates are unaffected. |

## Subagents

Heavy skills run in isolated contexts with specialized agents for better quality:

| Agent | Used by | Specialization |
|-------|---------|---------------|
| `architect` | `/blueprint` | Database schemas, API design, tech stack selection |
| `code-reviewer` | `/review` | Cross-document validation, consistency checks, scoring |
| `test-generator` | `/test` | Comprehensive test coverage, edge cases, mocking |
| `perf-analyzer` | `/perf` | Bottleneck detection, N+1 queries, algorithm optimization |
| `doc-writer` | `/doc` | README, API docs, inline comments, style matching |
| `business-analyst` | `/discover` | Market analysis, competitor research, user personas, feature prioritization |
| `devils-advocate` | `/advisor`, `/strategy`, `/blueprint` | Adversarial reviewer — challenges architectural and strategic decisions, proposes counter-arguments before implementation |
| `researcher` | `/market-scan`, `/mcp-docs`, `/discover` | Bounded market/technical/docs research that changes product, architecture, dependency, or integration decisions |
| `security-reviewer` | `/security-audit`, `/harden` | Read-only security audit — exploitability/impact ranking, remediation plan, never prints secrets |
| `ux-reviewer` | `/browser-check`, `/review` | Browser-based UX/visual/accessibility review of user-facing changes — prefers Playwright evidence over static guesses |

## Skill Contracts

> **Note for users:** in normal use, you do **not** invoke skills manually. Describe your task in natural language (*"I want to build X"*, *"fix this bug"*, *"add tests for this function"*) and Claude Code will route you to the right skill automatically via [skill discovery hooks](hooks/README.md) and trigger-phrase matching in each skill's body. Skills also invoke each other in chains — see the [Call Graph](#call-graph) section below. The contracts table exists to document behavior for debugging, contributions, and power users who want explicit control; it is **not** a "list of commands you must memorize".

Each skill has a documented contract — what it reads, what it writes, what side effects it has, and whether it's safe to run twice.

| Skill | Inputs | Outputs (files written) | Side effects | Idempotent |
|---|---|---|---|:---:|
| `/project` | User idea (text) | None directly — routes to another skill | None | ✅ |
| `/task` | Task description (text) for an existing project | None directly — routes to /bugfix, /refactor, /doc, /test, /perf, /review, /security-audit, /deps-audit, /migrate, /harden, /infra, or /explain | None (router only) | ✅ |
| `/discover` | Product idea or problem statement | `DISCOVERY.md` (market analysis, personas, prioritization) | None (analysis only, no code) | ✅ |
| `/kickstart` | User idea + clarifications | 7 docs + scaffolded project + commits | Git commits, file scaffolding, possible deploy | ⚠️ Resumes from CLAUDE.md status |
| `/blueprint` | User idea + clarifications | 6 docs + CLAUDE.md + .gitignore | None (planning only, no code) | ⚠️ Asks before overwrite |
| `/guide` | Existing PROJECT_ARCHITECTURE.md + IMPLEMENTATION_PLAN.md | CLAUDE_CODE_GUIDE.md | None | ✅ |
| `/review` | All project docs + code (read-only) | Validation report (stdout) + optional fix patches | Optional doc fixes if user agrees | ✅ |
| `/test` | File/function/module path | New test files matching project conventions | New test files only | ✅ |
| `/bugfix` | Error message / stack trace / symptom | Code patch fixing root cause + optional regression test | Source file edits | ⚠️ Should not be re-run after fix |
| `/refactor` | File/function/area | Refactored code preserving behavior | Source file edits | ✅ Behavior preserved |
| `/perf` | File/function/area + perf complaint | Bottleneck report + optimization patches | Source file edits, possibly DB index DDL | ⚠️ Measure between runs |
| `/explain` | File/function/concept | Markdown explanation + ASCII diagrams (stdout) | None | ✅ |
| `/doc` | File/module or "readme"/"api" | New/updated docs (README, API docs, inline comments) | Doc file edits | ✅ |
| `/security-audit` | File/dir/`all` | Audit report (stdout) — Critical/Important/Recommended/Informational tiers | None (read-only by design) | ✅ |
| `/deps-audit` | Manifest file/dir/`all` | Audit report (stdout) — CVE/license/abandoned tiers, same enum as /review | None (read-only, no package mutations) | ✅ |
| `/migrate` | Migration file/`next`/raw SQL | Migration applied + backup file + report with rollback path | DB schema mutation, backup file written to /tmp | ⚠️ Refuses on prod without confirmation |
| `/harden` | Service/dir/`all` | Hardening report + optional generated artifacts (health route, lifespan, logger, k6 script, runbook) | Code additions only with user approval; no deletions | ⚠️ Artifact generation is stateful |
| `/infra` | Stack preset + target (do/aws/hetzner/k8s) | Terraform modules OR Helm chart + README with deploy commands | New files under `infra/`; no cloud API calls (read-only from cloud side) | ✅ Generation is deterministic per input |
| `/session-save` | Session end signal or explicit invocation | `session_YYYY-MM-DD.md` + MEMORY.md update | Writes to `~/.claude/projects/` memory directory | ✅ Creates new file each time |
| `/autopilot` | Project idea (text) | Full project: docs + code + tests + review report | Git commits, file scaffolding, possible deploy (runs discover → blueprint → kickstart → review → test chain) | ⚠️ Stateful pipeline with multiple phases |
| `/strategy` | Existing project + context of what changed | Updated `LAUNCH_PLAN.md` + ADR + `BACKLOG.md` | File writes (plan docs only, no code) | ✅ Creates/overwrites plan docs |
| `/migrate-prod` | Source host + target host + service list | `MIGRATION_PLAN.md` + executed migration steps | SSH, Docker, DNS changes, DB dumps — **production impact** | ⚠️ Production operations, requires confirmation |
| `/advisor` | Question, comparison, or strategic decision | Analysis report (stdout) — pros/cons/risks | None (read-only by design, no Write/Edit) | ✅ |
| `/deploy` | Service name (`web`, `all`, or specific) + git HEAD | Deployed containers + healthcheck result (stdout) | SSH to target host, file sync, Docker build, container restart, optional DB migration — **production impact** | ⚠️ Production operations, requires confirmation |
| `/adopt` | Path to an existing legacy repo (defaults to `cwd`) + optional `skip-chain` flag | `CLAUDE.md` (append-with-marker if exists), `.claude/settings.json` (merge), `MEMORY.md` + sentinel `session_YYYY-MM-DD.md` + `.active-session.lock` | File writes in project root + project memory dir (never touches `~/.claude/settings.json`); voice-chain invokes `/strategy` or `/blueprint` | ✅ Marker-based idempotency — re-runs are no-ops |
| `/grill-me` | Plan / design / architecture / decision (text or repo) | None — questions + analysis (stdout); optional artifact only if the user asks | None (read-only by default; no Write/Edit) | ✅ |
| `/handoff` | Project state + handoff reason (compaction / delegation / AFK / recovery) | `HANDOFF.md` (context packet) + `STATE.json` refresh | Memory-write (`HANDOFF.md` in root + `STATE.json`); no source/code changes | ✅ Overwrites the packet each run |
| `/goal` | Goal text (empty = resume active goal) | `.itd-memory/GOAL.json` (persistent unit ledger) + unit events in `events.jsonl`; units delivered via the standard `/task` pipeline | Memory-write only; code changes happen inside `/task` under its own gates | ✅ Resume-only — an active ledger is never recreated |
| `/retro` | Workspace root(s) to scan (default cwd) | `docs/retros/RETRO-YYYY-MM-DD.md` (scan output + ranked evidence-cited proposals); backlog candidates for the USER to accept | Memory-write of the report only — never edits skills/hooks/docs (no self-merge) | ✅ New dated report each run; scan is deterministic |
| `/market-scan` | Idea / problem / segment / competitor / launch question | `MARKET_BRIEF.md` (dated append) + optional `BACKLOG.md`/`LAUNCH_PLAN.md` updates; structured stdout summary | Local doc writes + external read-only research query (`last30days`); no secrets sent | ⚠️ Dated append — re-runs add new evidence |
| `/mcp-docs` | Library / framework / API / version question | None — structured stdout summary; source + decision recorded in notes | None (read-only; external doc query, no file writes) | ✅ |
| `/github-workflow` | Issue / PR / branch / check run / release | GitHub Issues/PRs/releases (external) + optional `.itd-integrations/github.json`, `BRANCH_FINISH.md`, `.rubric-status` | External writes to GitHub only on explicit intent; reads git status first | ⚠️ External mutations — re-run with care |
| `/tool-sync` | Source artifacts + target tool (GitHub/Linear/Notion/Drive/Obsidian) | External tool state (live) OR `.itd-integrations/<target>.json` export | External writes only on explicit intent; reconciles, never clobbers | ⚠️ External mutations — reconcile-based |
| `/browser-check` | Local URL / route / user flow | None committed — stdout report + screenshots (evidence); temp Playwright script lives outside the project | Launches a local browser (Playwright); no production changes | ✅ |
| `/obsidian-export` | Project artifacts + memory | Generated Obsidian note set under `.itd-integrations/obsidian/` | Local-write (derived export only); canonical docs untouched | ✅ Regenerable from source |
| `/caveman` | `lite`/`full`/`ultra`/`wenyan-*` mode or `normal mode` | None — changes response style only (stdout) | None (read-only; session-scoped style state) | ✅ |
| `/context-mode-setup` | `status`/`install`/`doctor`/`off` | None — stdout (detect state + print/run upstream install commands); no upstream code vendored | None (read-only; detect-and-advise only) | ✅ |
| `/seo-setup` | `status`/`install`/`audit-map`/`off` | None — stdout (detect state + print/run upstream install commands + lifecycle map); no upstream code vendored | None (read-only; detect-and-advise only) | ✅ |
| `/security-guidance-setup` | `status`/`install`/`lifecycle-map`/`off` | None — stdout (detect state + print/run upstream install command + lifecycle map); no upstream code vendored | None (read-only; detect-and-advise only) | ✅ |
| `/cross-review` | diff range / path / empty | None — stdout (ranked second-opinion findings, with the engine that ran named); shells out to an external CLI on a scrubbed diff | None (read-only; additive to `/review`, never a gate) | ✅ |

**Reading the table:**
- **Idempotent ✅** — safe to run twice on the same input. Output is unchanged.
- **Idempotent ⚠️** — has stateful behavior (resume from status, asks before overwrite, expects pre-condition). Re-running may not be safe without inspection.

## Call Graph

Skills can invoke each other. This is the maximum depth and the chains:

```
/project (router, depth 1)
  ├─ /kickstart (depth 2)
  │    ├─ /review (depth 3, automatic Quality Gate 1)
  │    ├─ /test (depth 3, after each implementation step)
  │    ├─ /security-audit (depth 3, before deploy)
  │    ├─ /deps-audit (depth 3, before deploy)     # new in v1.4.0
  │    ├─ /harden (depth 3, before prod deploy)    # new in v1.4.0
  │    └─ /infra (depth 3, optional IaC generation) # new in v1.4.0
  ├─ /blueprint (depth 2)
  │    └─ architect agent (subagent fork, depth 3)
  └─ /guide (depth 2)

/review (standalone or chained)
  └─ code-reviewer agent (subagent fork)

/perf (standalone)
  └─ perf-analyzer agent (subagent fork)

/test (standalone or chained)
  └─ test-generator agent (subagent fork)

/doc (standalone)
  └─ doc-writer agent (subagent fork)

/security-audit (standalone)
  └─ may suggest fixes but never applies them — separation of audit and remediation

/deps-audit (standalone)
  └─ read-only; honors .deps-audit-ignore for accepted-risk entries

/harden (standalone)
  └─ generates artifacts only with explicit user approval per item

/infra (standalone)
  └─ writes files only; never calls cloud APIs directly

/migrate (standalone)
  └─ refuses on production without explicit user confirmation

/session-save (standalone, no subagent)
  └─ writes session memory file + updates MEMORY.md index

/bugfix, /refactor, /explain — leaf skills, no nested invocations.
```

**Recursion guard:** No skill invokes itself directly or through a chain. Maximum observed depth is 3 (`/project` → `/kickstart` → `/review` or any of the other depth-3 skills). If you observe a deeper chain or loop, file an issue — that's a bug.

## Recommended Setup: Skill Discovery Hooks

> **Note:** hooks are an **optional, separate step**. `/plugin install` registers the skills and agents but deliberately does **not** write to `~/.claude/settings.json` or install global hooks — that remains an explicit user decision. If you skip this section, the methodology still works; the hooks only raise the invocation rate under ambiguous prompts.

The methodology is only effective if Claude actually invokes the skills. Trigger word matching in `description` is necessary but not sufficient — under time pressure or with ambiguous prompts, Claude may default to ad-hoc tool calls. The `hooks/` folder contains **27 hooks** — but that number conflates two very different things. **9 are hard gates** that can stop an action (`permissionDecision: "deny"` on PreToolUse, or `decision: "block"` on SubagentStop — exit 2); the other **18 are soft** (reminders, context injection, observability, self-correction — they always exit 0 and never block). The enforcement strength of the harness is the **9 hard gates, not 27**. The taxonomy below makes the split explicit so the count is never read as 27× the blocking power it actually has.

### Hook taxonomy — 9 hard gates vs 18 soft (v1.59.0)

| # | Hard gate (can block/deny) | Event | What it stops |
|---|---|---|---|
| 1 | `check-review-before-commit.sh` | PreToolUse · Bash | a >2-file `git commit` without a diff-bound `/review` (v1.59.0) |
| 2 | `check-dod-before-commit.sh` | PreToolUse · Bash | a commit on a sensitive/payments path without the required `/security-audit` etc. |
| 3 | `check-commit-completeness.sh` | PreToolUse · Bash | committing a `SKILL.md` without its supporting artifacts |
| 4 | `check-skill-completeness.sh` | PreToolUse · Write/Edit | writing a `SKILL.md` without `references/`, fixtures, or trigger phrases |
| 5 | `check-tool-skill.sh` | PreToolUse · Bash/Edit/Write | a raw mutating tool call after 3 ignored skill decisions (with a skill-active grace window) |
| 6 | `pii-egress-guard.sh` | PreToolUse · Bash | a command that would egress secrets/PII to a third party |
| 7 | `narration-final.sh` | SubagentStop | a subagent ending on narration instead of its result/verdict (≤2 block-pings) |
| 8 | `verdict-contract.sh` | SubagentStop | a review subagent ending with a prose verdict and no valid JSON verdict block (≤2 block-pings) |
| 9 | `completion-gate.sh` | PreToolUse · Bash | a `git commit` with source code claiming done while a completion layer is unproven — L2 tests failing or never run (deny, exit 2) |

**Soft (18):** `careful`, `check-skills`, `completion-signals`, `completion-stop`, `context-aware`, `context-budget`, `cost-tracker`, `crash-recovery`, `cross-review-precommit`, `execution-trace`, `freeze`, `handoff-readiness`, `pre-flight-check`, `record-agent-skill`, `risk-score`, `session-open-diagnostic`, `stuck-detection`, `wip-gate` — they raise the invocation rate and quality, but never hard-stop (each self-declares "never blocks" / exit 0).

**Hard-gate coverage** — the metric that keeps the 9 honest: the fraction of hard gates backed by a *behavioural* test that actually drives the gate to `deny`/`block` (a real exit-2/block exercise, not a doc grep). `tests/verify_gate_taxonomy.py` asserts the 9/18/27 split and this README table stay in sync with `hooks/`; `tests/verify_harness_map_fixtures.py` (unit G-003) enforces coverage. **Target: 9/9.**

**Recommended — one command:**

```bash
git clone https://github.com/hihol-labs/idea-to-deploy ~/idea-to-deploy-src
cd ~/idea-to-deploy-src && bash scripts/sync-to-active.sh
```

The script copies all hooks into `~/.claude/hooks/`, patches `~/.claude/settings.json` to register them, and syncs the latest skill/agent definitions. It is idempotent — re-running only updates changed files.

<details>
<summary>Manual install (for users who prefer to see each step)</summary>

```bash
mkdir -p ~/.claude/hooks
cp hooks/check-skills.sh hooks/check-tool-skill.sh hooks/pre-flight-check.sh \
   hooks/check-skill-completeness.sh hooks/check-commit-completeness.sh \
   hooks/check-review-before-commit.sh hooks/session-open-diagnostic.sh \
   ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

Then add the `hooks` block to your `~/.claude/settings.json` — full settings.json snippet and pipe-tests in [`hooks/README.md`](hooks/README.md).

</details>

After installation:
- **`pre-flight-check.sh` (v1.5.0, UserPromptSubmit)** — runs before every user prompt. Loads `git log`, `git status`, and the project memory index (`MEMORY.md`) into Claude's context, and warns if a parallel Claude session has touched the project in the last 10 minutes (via `.active-session.lock`). **Soft context injection — never blocks.** Prevents the v1.13.2 inci­dent class where two parallel sessions independently fixed the same drift.
- **`check-skills.sh` (UserPromptSubmit)** — scans every prompt for ~80 Russian/English triggers and injects a `[SKILL HINT]` reminder when a skill matches. **Soft reminder — never blocks.**
- **`check-tool-skill.sh` (PreToolUse on Bash/Edit/Write/NotebookEdit)** — injects a `[SKILL CHECK]` reminder before raw tool calls, rate-limited to one reminder per 60 seconds. **Escalating hard gate (#5 above):** it reminds for the first 2 ignored skill decisions, then on the 3rd consecutive ignore (no Skill call and no `SKILL_BYPASS`) it **denies** the tool call (exit 2). A skill-active grace window and the read-only-Bash allowlist keep routine recon from tripping it.
- **`check-skill-completeness.sh` (v1.5.1, PreToolUse on Write/Edit/MultiEdit)** — **before** any modification to `skills/*/SKILL.md` inside a methodology repo, parses the pending tool input and verifies that `references/`, trigger phrases in the prompt hook, and regression fixture all exist. **Hard block (exit 2 + `hookSpecificOutput.permissionDecision: "deny"`) — the Write never runs, the file never lands on disk.**
- **`check-commit-completeness.sh` (v1.5.1, PreToolUse on Bash)** — before any `git commit` inside a methodology repo, parses the staged diff and denies the commit if a skill file is staged without its supporting artifacts. **Hard block (exit 2 + `hookSpecificOutput.permissionDecision: "deny"`) — the commit never runs.**

All 27 hooks fire live — no Claude Code restart needed. The v1.40 `handoff-readiness.sh` Stop-hook is on by default (soft, rate-limited) and is disabled per-machine with `ITD_HANDOFF_READINESS=0`. The two v1.5.1 enforcement hooks only fire inside the methodology repo (detected via `.claude-plugin/plugin.json`); they are no-ops on unrelated projects. The three v1.17.0+ safety guardrails (`careful.sh`, `freeze.sh`, `context-budget.sh`) and the v1.21 `execution-trace.sh` observability hook are opt-in per session. The pre-flight hook works on any project with a recognized memory directory; if there's no memory, it injects an empty context block with no warning.

> **Why this matters:** in a 2026-04-07 production-incident retrospective, Claude Code (Opus 4.6) spent ~2 hours doing direct SSH/sed/curl work to fix an auth outage. `/bugfix` would have been the right tool. It was never invoked — nothing forced it. These hooks are the answer. See `hooks/README.md` for the full case study.

## Quality Gates

The methodology includes two automatic quality checkpoints. As of v1.2.0 they use **binary rubrics** (deterministic checklists), not subjective scores.

### Gate 1: Plan Review
After documentation generation, before coding:
- Automatic `/review` validation against the rubric in `skills/review/references/review-checklist.md`
- The rubric is split into **Critical / Important / Nice-to-have** checks
- Gate **passes** only when all Critical checks pass; Important/Nice-to-have produce warnings, not failures
- **Mandatory user approval** — you see the plan + warnings and confirm before any code is written

### Gate 2: Step-by-Step Code Review
After each implementation step:
- Code compiles and runs without errors
- Tests pass
- Code matches architecture document
- No hardcoded secrets or naming inconsistencies
- 3 consecutive failures → STOP and ask user for guidance (no infinite retry)

## What Gets Generated

### Route A (Full Cycle) produces:

**7 Documents:**
- `STRATEGIC_PLAN.md` — strategy, competitors, budget, KPIs, risks
- `PROJECT_ARCHITECTURE.md` — DB schema, API endpoints, auth flow, infrastructure
- `IMPLEMENTATION_PLAN.md` — 8-12 steps with specific files and verification
- `PRD.md` — user stories, requirements (P0/P1/P2), kill criteria
- `README.md` — quick start guide
- `CLAUDE_CODE_GUIDE.md` — copy-paste prompts for each step
- `CLAUDE.md` — project memory and status tracking

**Plus:** working deployed project with tests, Docker, and CI/CD.

### Route B (Planning Only) produces:

**6 Documents:**
- `STRATEGIC_PLAN.md` — strategy, competitors, budget, KPIs, risks
- `PROJECT_ARCHITECTURE.md` — DB schema, API endpoints, auth flow, infrastructure
- `IMPLEMENTATION_PLAN.md` — 8-12 steps with specific files and verification
- `PRD.md` — user stories, requirements (P0/P1/P2), kill criteria
- `README.md` — quick start guide
- `CLAUDE_CODE_GUIDE.md` — copy-paste prompts for each step

**Plus:** `CLAUDE.md` (project memory) and `.gitignore`. No code is written. You can review the plan, share it with a client or team, and later switch to route A to start implementation.

### Route C (Have Docs Already) produces:

**1 Document:**
- `CLAUDE_CODE_GUIDE.md` — step-by-step prompts based on your existing documentation

Takes your existing architecture, plan, and requirements — and converts them into ready-to-use prompts. You copy a prompt, paste it into Claude Code, get the result, and move to the next step. Full manual control over every stage.

## Seamless Route Switching

Routes are not dead ends — you can switch between them at any time without losing work.

| Switch | What you say | What happens |
|--------|-------------|-------------|
| B → A | "Start implementation" | Detects existing docs, validates, skips to coding |
| C → A | "Start implementation" | Detects guide + docs, supplements if needed, starts coding |
| C → B | "Create full documentation" | Reads existing guide, generates missing docs |
| A (interrupted) → A | "Continue the project" | Finds last completed step, resumes from there |

**How it works:** Each skill automatically scans for existing project files on startup. If documentation, code, or a guide already exists — the skill reuses it instead of starting from scratch. One phrase from you — and the system picks up where it left off.

**Nothing is lost.** Switch routes, take breaks, come back later — the methodology remembers your progress.


## Recommended Models

As of v1.3.0, the recommended model is also encoded in each skill's body in a `## Recommended model` section. The table below is the same data in summary form. `/blueprint` and `/kickstart` auto-fall-back to Lite mode on Sonnet and refuse on Haiku.

> **Model-routing policy (v1.31.0):** the per-phase rationale behind these picks —
> expensive tiers on reasoning-heavy phases, cheap tiers on mechanical ones, to
> control OpEx — lives in [`docs/MODEL-ROUTING-POLICY.md`](docs/MODEL-ROUTING-POLICY.md).
> It is a transparent policy applied via `/model` + per-agent `model:` frontmatter, not
> an auto-router (see [ADR-001](docs/adr/ADR-001-no-own-runtime.md)).

| Skill | Minimum | Recommended | Notes |
|-------|---------|-------------|-------|
| `/project` | Haiku | Sonnet | Router only — minimal reasoning |
| `/task` | Haiku | Sonnet | Router for daily-work skills — minimal reasoning |
| `/discover` | Sonnet (Lite) | Opus (Full) | Deep market analysis, competitor research, multi-dimensional prioritization |
| `/blueprint` | Sonnet (Lite) | Opus (Full) | Lite mode auto-active on Sonnet |
| `/kickstart` | Sonnet (Lite) | Opus (Full) | Lite mode auto-active on Sonnet, refuses Haiku |
| `/guide` | Sonnet | Opus | Long prompt sequences benefit from Opus |
| `/review` | Sonnet | Opus | Cross-document validation |
| `/security-audit` | Sonnet | Opus | Cross-file pattern recognition |
| `/test` | Sonnet | Sonnet | Pattern-matching to existing convention |
| `/bugfix` | Sonnet | Sonnet | Opus only for cross-language analysis |
| `/refactor` | Sonnet | Sonnet | Mechanical via Fowler catalog |
| `/perf` | Sonnet | Opus | Cross-layer reasoning helps |
| `/doc` | Sonnet | Sonnet | Style matching is straightforward |
| `/explain` | Haiku | Haiku | Read-only walkthrough; Haiku is fast enough |
| `/migrate` | Sonnet | Sonnet | Mechanical (read SQL → run → verify) |
| `/deps-audit` | Sonnet | Sonnet | Parsing + API lookups; Opus doesn't improve accuracy |
| `/harden` | Sonnet | Opus | Cross-layer reasoning (code + infra + observability) |
| `/infra` | Sonnet | Opus | Networking / IAM / secrets interactions are subtle |
| `/session-save` | Sonnet | Sonnet | Reading git log + writing summary — straightforward |
| `/autopilot` | Sonnet | Opus | Orchestrates full pipeline — benefits from Opus reasoning |
| `/strategy` | Sonnet | Opus | Multi-factor gap analysis + ADR generation |
| `/migrate-prod` | Sonnet | Opus | High-risk production operations need careful reasoning |
| `/advisor` | Sonnet | Opus | Multi-perspective analysis via subagents |
| `/deploy` | Sonnet | Sonnet | Sequential execution of a known checklist; Opus doesn't add value over Sonnet |
| `/adopt` | Sonnet | Sonnet | Declarative templating + file merge + short voice-chain — no architectural reasoning |
| `/grill-me` | Sonnet | Opus | Adversarial questioning + hidden-assumption hunting benefit from Opus |
| `/handoff` | Haiku | Sonnet | Structured summarization of decisions + state — minimal reasoning |
| `/goal` | Sonnet | Opus | Decomposing a fuzzy goal into binary-verifiable units is reasoning; unit bookkeeping itself is mechanical |
| `/retro` | Sonnet | Opus | Interpreting telemetry into ranked improvement proposals is reasoning; the scan itself is a script |
| `/market-scan` | Sonnet | Opus | Synthesis of heterogeneous public signals + adversarial discovery benefit from Opus |
| `/mcp-docs` | Haiku | Sonnet | Library ID resolve + narrow doc query — pointed lookup, not deep reasoning |
| `/github-workflow` | Sonnet | Sonnet | gh/git ops + artifact mapping — structured, not deep reasoning |
| `/tool-sync` | Sonnet | Sonnet | Artifact-to-schema mapping + reconcile — structured |
| `/browser-check` | Sonnet | Sonnet | Writing Playwright checks + interpreting render results — structured |
| `/obsidian-export` | Sonnet | Sonnet | Derived note generation (copy + wikilinks/tags) — mechanical |
| `/caveman` | Haiku | Sonnet | Style control only — no code/doc generation |
| `/context-mode-setup` | Haiku | Sonnet | Orchestrator/bridge — detect install + print commands, no generation |
| `/seo-setup` | Haiku | Sonnet | Orchestrator/bridge — detect install + print commands + lifecycle map, no generation |
| `/security-guidance-setup` | Haiku | Sonnet | Orchestrator/bridge — detect install + print command + lifecycle map, no generation |
| `/cross-review` | Sonnet | Opus | Orchestration — scrub the diff, shell out to an external reviewer, summarize findings |

## Who Is This For

| Audience | Value |
|----------|-------|
| **Freelancers** | Take more orders, deliver faster. One project per weekend instead of two weeks |
| **Startups** | MVP in 2 days instead of a month. No team needed. Professional architecture |
| **Beginners** | No need to know how to structure a project — the system does it for you |
| **Agencies** | Standardize your process. Same quality, predictable timelines for every client |

## Project Types

Works with any project that can be built with code:
- SaaS platforms
- Telegram / Discord bots
- REST APIs and integrations
- Landing pages and web apps
- CLI utilities
- Mini Apps
- E-commerce
- Parsers and scrapers

## What This Methodology Does NOT Do

Setting expectations honestly. As of v1.4.0 this list is **two items** — the remaining limitations are fundamental, not gaps.

- **Does not replace a senior architect on novel systems in regulated industries.** The methodology encodes strong defaults for typical web stacks, but LLMs cannot exercise the judgment that comes from having shipped production systems under SOC 2, HIPAA, PCI DSS, GDPR, or HITRUST audit. For healthcare, fintech, aerospace, or other high-risk domains, treat idea-to-deploy as a starting skeleton — a human expert still owns the compliance posture and the hard architectural tradeoffs.
- **Does not run autonomously forever — by design.** After 3 consecutive step failures in Phase 4, the methodology stops and asks for human input. This is a safety feature, not a limitation. Removing it would let the LLM spin in circles on impossible tasks and burn user budget. Human-in-the-loop is the point.

If either of these is a blocker for your use case, layer your own process on top of the methodology.

### Previously on this list — now covered

Items that used to be in this section and are now handled by the methodology:

| Was a limitation | Now covered by |
|---|---|
| Does not guarantee a production-ready deploy | `/harden` — hardening rubric + artifact generation (health checks, graceful shutdown, structured logs, metrics, backups, load tests, runbook) |
| Does not audit third-party dependencies | `/deps-audit` — OSV.dev + GHSA CVE lookups, license compatibility, abandoned-package detection |
| Does not manage infrastructure | `/infra` — Terraform modules, Helm charts, secrets wiring for DO/AWS/Hetzner/K8s |
| GIGO — vague clarifications produce vague plans | `/kickstart` v1.4.0 — clarification validation with targeted follow-ups and structured confirmation before doc generation |
| Not a substitute for code review by a human on critical paths | `/review` v1.4.0 — expanded code rubric with SOLID checks, cyclomatic complexity, Fowler smells, Google Engineering Practices (still not a full replacement for peer review on truly critical paths, but it's now close) |

See [CHANGELOG v1.4.0](CHANGELOG.md) for the detailed breakdown.

## Troubleshooting / FAQ

**A skill is not being invoked when I expect it to.**
Claude Code may default to ad-hoc tool calls on ambiguous prompts. Install the [skill discovery hooks](#recommended-setup-skill-discovery-hooks) — they inject `[SKILL HINT]` and `[SKILL CHECK]` reminders that raise the invocation rate significantly. You can also invoke a skill explicitly: `/bugfix`, `/test`, etc.

**How do I update the plugin?**
`/plugin update hihol-labs/idea-to-deploy`. Check the [CHANGELOG](CHANGELOG.md) for what changed.

**How do I uninstall?**
`/plugin uninstall hihol-labs/idea-to-deploy`. Hooks in `~/.claude/settings.json` (if you installed them) must be removed manually.

**Conflicts with other plugins.**
Skills are namespaced by plugin, so two plugins can coexist even if both define `/test`. The router will ask which one to use. Hooks are global — if another plugin also registers UserPromptSubmit hooks, they run in the order defined in `settings.json`.

**`/review` flags my plan as BLOCKED but I disagree.**
See the Troubleshooting section in the `/review` skill itself (`skills/review/SKILL.md`) — it documents how to override Critical checks with explicit user consent.

**I'm on Haiku and `/kickstart` refuses to run.**
By design — see the [Recommended Models](#recommended-models) table. `/kickstart` and `/blueprint` require at least Sonnet; Haiku is fine for `/project`, `/explain`, and read-only skills.

**The methodology "forgot" my project.**
Each skill reads `CLAUDE.md` at the project root to resume. If you deleted or renamed it, run `/project` again and say "continue the project" — it will re-scan and rebuild state from existing files.

**How does the methodology preserve context between sessions?**
Three mechanisms work together:
1. **`/session-save` skill (new in v1.10.0)** — saves session context (what was done, key decisions, blockers, next steps) to the project's memory directory (`~/.claude/projects/.../memory/`). Claude reads this at the start of each new session.
2. **Auto-save during work** — Claude automatically saves context after significant milestones (completed feature, bug fix, architectural decision, `/kickstart` phase transition) so that even if the session is abruptly closed, minimal context is lost.
3. **`CLAUDE.md` status table** — `/kickstart` tracks which implementation steps are completed, allowing resumption from the right step.

**Important:** if you close VS Code or the terminal abruptly, the last unsaved fragment may be lost. The auto-save mechanism minimizes this, but for best results say "сохрани сессию" / "save session" before closing. Projects created via `/kickstart` or `/blueprint` include the session-save rule in their generated `CLAUDE.md` automatically.

**Where are my installed skills located?**
`~/.claude/plugins/idea-to-deploy/skills/`. Each skill has a `SKILL.md` you can read to understand its contract.

**How does idea-to-deploy relate to "Dive into Claude Code" (arxiv 2604.14228)?**
The April 2026 paper by Liu et al. ([arxiv 2604.14228](https://arxiv.org/pdf/2604.14228)) and its companion repo [VILA-Lab/Dive-into-Claude-Code](https://github.com/VILA-Lab/Dive-into-Claude-Code) formalize 16 architectural principles behind Claude Code itself. We published [`docs/DESIGN_SPACE.md`](docs/DESIGN_SPACE.md) mapping the methodology against those principles: of the 15 applicable ones, 13 are covered in full or partial form, and 2 (context budgeting and on-disk checkpoints beyond `git`) are acknowledged gaps. The map is honest by design — both gap items are candidate scope for a future v1.21 release once multi-point user signal arrives.

**How does idea-to-deploy relate to "Harness Engineering" (walkinglabs)?**
The [Harness Engineering course](https://walkinglabs.github.io/learn-harness-engineering/ru/) formalizes the discipline: the goal is not to make the model smarter but to build a closed working system (a harness) with explicit rules and boundaries — which is the central thesis of this methodology. We published [`docs/HARNESS_ENGINEERING_MAP.md`](docs/HARNESS_ENGINEERING_MAP.md) mapping the methodology against the course's 5 principles: all 5 are covered in full (constraining behavior, context preservation, preventing premature completion, verification through testing, and observability — live execution tracing landed as the opt-in `execution-trace.sh` hook in v1.21.x). Both course templates are covered too: `AGENTS.md` → `CLAUDE.md` + the `.itd/` contract layer; `feature_list.json` → `ACCEPTANCE_CONTRACT.json` + `VERIFICATION_CONTRACT.json` (machine-readable, fail-closed).

**Something else is broken.**
Open an issue: [github.com/hihol-labs/idea-to-deploy/issues](https://github.com/hihol-labs/idea-to-deploy/issues). Include your Claude Code version, the model in use, the prompt, and the unexpected behavior.

## Contributing

Contributions are welcome. The project is small enough that process is lightweight:

1. **Report issues / suggest skills** — open a GitHub issue with a concrete scenario and expected behavior.
2. **Propose a new skill** — skills live under `skills/<name>/SKILL.md` and follow the shape documented in the existing 40. Each needs: frontmatter (name, description, triggers, allowed-tools, recommended model), Instructions, Examples, Troubleshooting.
3. **Fix a bug or polish a skill** — open a PR against `main`. Run `tests/run-fixtures.sh` locally to sanity-check against fixtures before submitting.
4. **Improve documentation** — both `README.md` and `README.ru.md` must stay in sync. Updates to one require updates to the other.

All PRs are reviewed against the same binary rubric that `/review` uses on generated projects. No subjective scoring.

## Requirements

- Claude Code CLI or VS Code extension (with plugin support)
- Claude Pro / Team / Enterprise subscription
- `git` on `PATH`

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full release history. This project follows [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/).

## License

MIT

## Author

**HiH-DimaN** — [GitHub](https://github.com/HiH-DimaN)
