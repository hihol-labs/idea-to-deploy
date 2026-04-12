# Show r/ClaudeAI: idea-to-deploy v1.17 -- self-improving methodology plugin

- **Platform:** Reddit r/ClaudeAI
- **Target length:** 500-800 words
- **Tags/Flair:** Show (or Project Showcase, depending on subreddit rules)
- **Hook:** I built a Claude Code plugin that audits itself and gets stricter with every release. Here's what 20 skills, 25 meta-review gates, and 3 tiers of testing look like in practice.
- **CTA:** MIT-licensed at https://github.com/HiH-DimaN/idea-to-deploy -- would love feedback, especially on the testing approach.

---

## Show r/ClaudeAI: idea-to-deploy v1.17 -- self-improving methodology plugin

I built a Claude Code plugin that audits itself and gets stricter with every release. Here is what 20 skills, 25 meta-review gates, and 3 tiers of testing look like in practice.

### What it is

idea-to-deploy is a Claude Code plugin (installed via `/plugin install HiH-DimaN/idea-to-deploy`) that gives Claude Code a structured development methodology instead of ad-hoc generation.

**20 skills** covering the full lifecycle:
- **Entry points:** `/project` (router), `/task` (daily work router), `/discover` (product discovery with MoSCoW/RICE)
- **Project creation:** `/kickstart` (full lifecycle), `/blueprint` (planning only), `/guide` (copy-paste prompts)
- **Daily work:** `/bugfix`, `/refactor`, `/doc`, `/test`, `/perf`, `/explain`
- **Quality:** `/review` (binary rubric), `/security-audit` (with Red/Blue Team mode), `/deps-audit`
- **Operations:** `/migrate`, `/harden`, `/infra`
- **Session:** `/session-save` (context persistence between sessions)

**7 subagents** (architect, code-reviewer, test-generator, perf-analyzer, doc-writer, business-analyst) for specialized deep work.

**Safety guardrails:** `/careful` warns before destructive commands (rm -rf, DROP TABLE, force push). `/freeze <path>` restricts edits to a specific directory. Both opt-in.

### What makes it different

There are other Claude Code skill collections out there (gstack at 70K stars, BMAD at 44K, claude-code-skills with over a hundred skills). What we focus on that they do not:

**Self-improving methodology.** We have 25+ automated meta-review gates that run on every PR. Each gate catches a specific class of documentation/configuration drift. The interesting part: 5 of those gates were added because a user found a bug that existing gates missed. Each user report produces a new permanent gate.

Example: a user counted skills in our README category headings and found "Operations (4 skills)" with only 3 table rows. Also found that `/task` was missing from comprehensive tables for 11 months. We added gate M-C16 (two modes) that now catches both category subtotal drift and per-table completeness.

**Three-tier testing:**
1. **Structural** (CI, every PR) -- `meta_review.py` with 25+ checks on metadata, versions, counts, cross-references
2. **Snapshot** (local, free) -- `verify_snapshot.py` validates generated output against JSON contracts (required files, sections, content markers, count constraints)
3. **Behavioural** (headless) -- `run-fixture-headless.sh` runs `claude -p` non-interactively, generates output, and validates it

Most Claude Code plugins have zero testing. We have three tiers catching different failure modes.

**Operations stack.** `/migrate` (safe DB migrations with backup/rollback), `/harden` (production readiness checklist), `/infra` (Terraform/Kubernetes/Helm generation). These cover the "last mile" that skill collections usually skip.

**Daily work router.** Say "fix the auth bug" and `/task` routes to `/bugfix`. Say "it's slow" and it routes to `/perf`. 12 daily-work skills behind one entry point.

### The v1.13.2 to v1.17.0 journey

The recent release series was a marathon of self-improvement:

- **v1.13.2:** Documentation drift audit, marketplace.json gates (M-C13, M-C14)
- **v1.15.0:** Snapshot validation system, 10 fixture schemas
- **v1.16.0:** Headless behavioural testing via `claude -p`, 3 fixtures fully automated
- **v1.16.2:** Hook count gate (M-C15) after user spotted missing hooks in README
- **v1.16.3:** Table integrity gate (M-C16) after user counted skills in headings
- **v1.17.0:** Product discovery skill (`/discover`), business-analyst subagent, safety guardrails (`/careful`, `/freeze`)

9 PRs, 25+ meta-review checks, 3 active behavioural fixtures, and the methodology catches more drift with every cycle.

### Quick start

```bash
# Install
/plugin install HiH-DimaN/idea-to-deploy

# Start a new project
/project

# Or route daily work
/task
```

### What I'd love feedback on

1. **The testing approach** -- is three-tier testing for LLM methodologies overkill, or does anyone else find that structural checks alone are not enough?
2. **The operations skills** -- are `/migrate`, `/harden`, `/infra` useful in practice, or are you using other tools for that?
3. **The safety guardrails** -- do you use any kind of destructive-command warning in your Claude Code workflow?

MIT-licensed: [github.com/HiH-DimaN/idea-to-deploy](https://github.com/HiH-DimaN/idea-to-deploy)

Happy to answer questions about the architecture, testing setup, or anything else.
