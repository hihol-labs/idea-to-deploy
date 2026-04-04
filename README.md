# idea-to-deploy

> Complete project lifecycle methodology for Claude Code — from idea to deployed product in one command.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Skills: 11](https://img.shields.io/badge/Skills-11-green.svg)](#skills)
[![Agents: 5](https://img.shields.io/badge/Agents-5-orange.svg)](#subagents)
[![Version: 1.1.0](https://img.shields.io/badge/Version-1.1.0-purple.svg)](.claude-plugin/plugin.json)

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

## Quality Gates

The methodology includes two automatic quality checkpoints:

### Gate 1: Plan Review
After documentation generation, before coding:
- Automatic `/review` validation (score must be >= 7/10)
- **Mandatory user approval** — you see the plan and confirm before any code is written

### Gate 2: Step-by-Step Code Review
After each implementation step:
- Code compiles and runs without errors
- Tests pass
- Code matches architecture document
- No hardcoded secrets or naming inconsistencies

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
