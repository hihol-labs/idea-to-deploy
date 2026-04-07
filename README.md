# idea-to-deploy

> Complete project lifecycle methodology for Claude Code — from idea to deployed product in one command.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Skills: 11](https://img.shields.io/badge/Skills-11-green.svg)](#skills)
[![Agents: 5](https://img.shields.io/badge/Agents-5-orange.svg)](#subagents)
[![Version: 1.2.0](https://img.shields.io/badge/Version-1.2.0-purple.svg)](.claude-plugin/plugin.json)

**[Русская версия (README.ru.md)](README.ru.md)**

---

## The Problem

Claude Code is powerful, but without instructions it works like a builder without blueprints:
- Writes code randomly, skips tests, doesn't document
- Each time produces different structure and quality
- Can break what already works
- No methodology — just chaotic generation

## The Solution

**idea-to-deploy** is a methodology, not just a set of tools. 11 skills + 5 specialized agents that turn Claude Code into a professional developer with a proven pipeline:

```
Idea → Questions → Plan → Architecture → Code → Tests → Review → Deploy
```

Every step is verified. Every feature is tested. Every decision is documented.

## Quick Start

### Installation

```bash
/plugin install HiH-DimaN/idea-to-deploy
```

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


## Skills

### Entry Point (1 skill)

| Skill | Description |
|-------|-------------|
| `/project` | Smart router — asks one question and routes to the right workflow |

### Project Creation (3 skills)

| Skill | Route | What it does |
|-------|-------|-------------|
| `/kickstart` | A) Full cycle | Idea to deployed product: docs, code, tests, deploy |
| `/blueprint` | B) Planning only | 6 documentation files, no code |
| `/guide` | C) Have docs already | You already have architecture and plan docs (from route B, another developer, or another tool) — generates step-by-step prompts to build it |

### Quality Assurance (1 skill)

| Skill | Description |
|-------|-------------|
| `/review` | Validates documentation and code quality with scoring (1-10), cross-reference matrix, and actionable fix suggestions |

### Daily Work (6 skills)

| Skill | Description |
|-------|-------------|
| `/test` | Generate unit, integration, and edge case tests |
| `/debug` | Systematically find and fix bugs |
| `/perf` | Performance analysis and optimization |
| `/refactor` | Improve code structure without changing behavior |
| `/explain` | Explain how code works with ASCII diagrams |
| `/doc` | Generate documentation matching project style |

## Subagents

Heavy skills run in isolated contexts with specialized agents for better quality:

| Agent | Used by | Specialization |
|-------|---------|---------------|
| `architect` | `/blueprint` | Database schemas, API design, tech stack selection |
| `code-reviewer` | `/review` | Cross-document validation, consistency checks, scoring |
| `test-generator` | `/test` | Comprehensive test coverage, edge cases, mocking |
| `perf-analyzer` | `/perf` | Bottleneck detection, N+1 queries, algorithm optimization |
| `doc-writer` | `/doc` | README, API docs, inline comments, style matching |

## Skill Contracts

Each skill has a documented contract — what it reads, what it writes, what side effects it has, and whether it's safe to run twice.

| Skill | Inputs | Outputs (files written) | Side effects | Idempotent |
|---|---|---|---|:---:|
| `/project` | User idea (text) | None directly — routes to another skill | None | ✅ |
| `/kickstart` | User idea + clarifications | 7 docs + scaffolded project + commits | Git commits, file scaffolding, possible deploy | ⚠️ Resumes from CLAUDE.md status |
| `/blueprint` | User idea + clarifications | 6 docs + CLAUDE.md + .gitignore | None (planning only, no code) | ⚠️ Asks before overwrite |
| `/guide` | Existing PROJECT_ARCHITECTURE.md + IMPLEMENTATION_PLAN.md | CLAUDE_CODE_GUIDE.md | None | ✅ |
| `/review` | All project docs + code (read-only) | Validation report (stdout) + optional fix patches | Optional doc fixes if user agrees | ✅ |
| `/test` | File/function/module path | New test files matching project conventions | New test files only | ✅ |
| `/debug` | Error message / stack trace / symptom | Code patch fixing root cause + optional regression test | Source file edits | ⚠️ Should not be re-run after fix |
| `/refactor` | File/function/area | Refactored code preserving behavior | Source file edits | ✅ Behavior preserved |
| `/perf` | File/function/area + perf complaint | Bottleneck report + optimization patches | Source file edits, possibly DB index DDL | ⚠️ Measure between runs |
| `/explain` | File/function/concept | Markdown explanation + ASCII diagrams (stdout) | None | ✅ |
| `/doc` | File/module or "readme"/"api" | New/updated docs (README, API docs, inline comments) | Doc file edits | ✅ |

**Reading the table:**
- **Idempotent ✅** — safe to run twice on the same input. Output is unchanged.
- **Idempotent ⚠️** — has stateful behavior (resume from status, asks before overwrite, expects pre-condition). Re-running may not be safe without inspection.

## Call Graph

Skills can invoke each other. This is the maximum depth and the chains:

```
/project (router, depth 1)
  ├─ /kickstart (depth 2)
  │    ├─ /review (depth 3, automatic Quality Gate 1)
  │    └─ /test (depth 3, after each implementation step)
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

/debug, /refactor, /explain — leaf skills, no nested invocations.
```

**Recursion guard:** No skill invokes itself directly or through a chain. Maximum observed depth is 3 (`/project` → `/kickstart` → `/review`). If you observe a deeper chain or loop, file an issue — that's a bug.

## Recommended Setup: Skill Discovery Hooks

The methodology is only effective if Claude actually invokes the skills. Trigger word matching in `description` is necessary but not sufficient — under time pressure or with ambiguous prompts, Claude may default to ad-hoc tool calls. The `hooks/` folder contains two enforcement scripts that close this gap:

```bash
mkdir -p ~/.claude/hooks
cp hooks/check-skills.sh hooks/check-tool-skill.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

Then add the `hooks` block to your `~/.claude/settings.json` — full instructions, settings.json snippet, and pipe-tests in [`hooks/README.md`](hooks/README.md).

After installation:
- `check-skills.sh` (UserPromptSubmit) scans every prompt for ~80 Russian/English triggers and injects a `[SKILL HINT]` reminder when a skill matches.
- `check-tool-skill.sh` (PreToolUse on Bash/Edit/Write/NotebookEdit) injects a `[SKILL CHECK]` reminder before raw tool calls.

Both hooks fire live — no Claude Code restart needed.

> **Why this matters:** in a 2026-04-07 production-incident retrospective, Claude Code (Opus 4.6) spent ~2 hours doing direct SSH/sed/curl work to fix an auth outage. `/debug` would have been the right tool. It was never invoked — nothing forced it. These hooks are the answer. See `hooks/README.md` for the full case study.

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

| Skill | Minimum | Recommended |
|-------|---------|-------------|
| `/project` | Sonnet | Sonnet |
| `/blueprint`, `/kickstart` | Sonnet | Opus |
| `/review`, `/guide` | Sonnet | Opus |
| `/test`, `/debug`, `/refactor`, `/doc` | Sonnet | Sonnet |
| `/perf` | Sonnet | Opus |
| `/explain` | Haiku | Sonnet |

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

## Requirements

- Claude Code CLI or VS Code extension
- Claude Pro / Team / Enterprise subscription

## License

MIT

## Author

**HiH-DimaN** — [GitHub](https://github.com/HiH-DimaN)
