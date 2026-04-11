---
name: Feature request / new skill proposal
about: Suggest a new skill, a rubric check, or a methodology improvement
title: "[FEATURE] "
labels: enhancement
assignees: ''
---

## Type of proposal

- [ ] New skill (e.g. `/cleanup`, `/seed-data`)
- [ ] New rubric check (M-Cxx or M-Ixx)
- [ ] New hook (UserPromptSubmit / PreToolUse / PostToolUse)
- [ ] Methodology improvement (phase, gate, process)
- [ ] Documentation improvement
- [ ] Other:

## Problem

What gap in the current methodology are you trying to close? Be specific about:

- The scenario or task the current 16 skills don't cover well
- Why existing skills (`/bugfix`, `/refactor`, `/review`, `/doc`, etc.) don't already handle it
- Concrete examples of when you ran into the gap

## Proposed skill / check / feature

### One-line summary

### When it triggers

If this is a new skill, list the user phrases (Russian and English) that should auto-invoke it. These will become the canonical `## Trigger phrases` section:

```
- фраза 1, фраза 2, фраза 3
- english phrase 1, english phrase 2
```

### What it reads

Files, directories, external APIs. Be specific.

### What it writes

Files modified, files created, external side effects. Be specific.

### Recommended model

Haiku / Sonnet / Opus and why. See the existing `## Recommended model` sections of other skills for the format.

### Skill contract row

Following the `README.md` Skill Contracts table format, propose the row for your new skill:

```
| `/your-skill` | Input | Output | Side effects | Idempotent? |
```

## Why this is NOT covered by an existing skill

Be specific — the methodology deliberately keeps the skill count small to avoid overlap. If your proposal partially overlaps with an existing skill, explain the boundary.

## Alternatives considered

What else did you consider doing instead? Why doesn't that work?

## Additional context

Any prior art, similar tools, references to Fowler / Clean Code / Google Engineering Practices, etc.
