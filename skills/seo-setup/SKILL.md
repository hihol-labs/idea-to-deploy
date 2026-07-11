---
name: seo-setup
description: 'SEO companion — sets up and integrates the upstream Claude SEO plugin (AgriciDaniel/claude-seo, MIT) into idea-to-deploy. Claude SEO ships 25 sub-skills + 18 sub-agents for technical SEO, content quality (E-E-A-T), Schema.org, sitemaps, Core Web Vitals, local SEO, backlinks, AI/GEO, ecommerce, hreflang, and Google APIs. Use when a project needs SEO — audits, schema, Core Web Vitals, AI Overviews/GEO visibility, keyword/competitor research, on-page or technical SEO — and you want it wired into the discover/blueprint/kickstart/harden/deploy lifecycle. Detects install, prints the verified CLI commands, and maps the plugin onto the lifecycle; does NOT vendor upstream code.'
argument-hint: status, install, audit-map, or off
license: MIT
allowed-tools: Read, Bash
metadata:
  effort: low
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.83.0
  category: integration
  tags: [seo, geo, schema, core-web-vitals, technical-seo, eeat, integration]
---


# SEO Setup

SEO companion for idea-to-deploy. The upstream **Claude SEO** plugin turns Claude
Code into a full SEO toolkit: it runs sub-skills and specialist sub-agents in
parallel across technical SEO (crawlability, indexability, Core Web Vitals/INP),
content quality (E-E-A-T), Schema.org markup, sitemaps, image SEO, local SEO,
backlinks, AI/GEO (AI Overviews / ChatGPT / Perplexity), e-commerce, hreflang/i18n,
and the Google SEO APIs (Search Console, PageSpeed, CrUX, Indexing, GA4). Every
audit produces a prioritized action plan grounded in primary-source Google guidance.

This is the idea-to-deploy-native **setup/integration** skill: it tells you *when*
in the methodology to reach for SEO, detects whether the plugin is installed,
gives the verified install commands, and maps its components onto the lifecycle. It
is named `seo-setup` on purpose — the upstream plugin ships its own orchestrator
skill literally named `seo` (invoked as `/seo audit <url>`), so this skill carries
a distinct name to avoid a collision when both are installed.

It does **not** vendor or re-implement the upstream plugin — that plugin is a large
surface (25 skills + 18 agents) with a heavy Python toolchain (`playwright`,
`lxml`, `weasyprint`, `Pillow`, `matplotlib`, `google-api-python-client`, …), and
idea-to-deploy stays bash/python/markdown with no heavy native deps.

Use this skill when the user asks about SEO, search ranking, an SEO audit, Schema/
structured data, Core Web Vitals, sitemaps, E-E-A-T, AI Overviews / GEO, keyword or
backlink research, technical or on-page SEO, or wants search visibility wired into
the project lifecycle.

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- seo, сео, поисковая оптимизация, seo audit, seo-аудит, сео-аудит
- schema markup, structured data, микроразметка, разметка schema, json-ld
- core web vitals, web vitals
- sitemap, карта сайта
- e-e-a-t, eeat
- ai overviews, geo optimization, generative engine optimization, ai search visibility
- technical seo, технический seo, on-page seo
- search ranking, поисковая выдача, ранжирование сайта
- backlinks, обратные ссылки, ссылочный профиль
- keyword research, ключевые слова, semantic clustering, кластеризация ключей

## Recommended model

**sonnet** — This skill is an orchestrator/bridge: it explains fit, checks install
state, and prints commands. No code or doc generation, no heavy reasoning. Sonnet
is plenty.

## Upstream

Integrates the public **Claude SEO** plugin —
`https://github.com/AgriciDaniel/claude-seo` by
[@AgriciDaniel](https://github.com/AgriciDaniel) (license **MIT**). This skill is
also MIT (our own orchestration text); it ships **no** upstream source — it points
at the plugin and prints its documented install commands. Attribution to
@AgriciDaniel is kept intact.

The FLOW framework prompts bundled in the upstream plugin (`seo-flow`) are © Daniel
Agrici under **CC BY 4.0** — another reason not to vendor: re-distributing them
would carry the attribution obligation. The marketplace install is the supported
path.

## What Claude SEO provides

Verified against the upstream repo (`plugin.json` / `marketplace.json`, version
2.2.0):

- **25 sub-skills** — the orchestrator `seo` (invoked `/seo <command> <url>`) plus
  21 core skills (`seo-audit`, `seo-page`, `seo-technical`, `seo-content`,
  `seo-content-brief`, `seo-schema`, `seo-sitemap`, `seo-images`, `seo-image-gen`,
  `seo-geo`, `seo-local`, `seo-maps`, `seo-hreflang`, `seo-google`, `seo-backlinks`,
  `seo-cluster`, `seo-sxo`, `seo-drift`, `seo-ecommerce`, `seo-programmatic`,
  `seo-competitor-pages`), the `seo-flow` framework skill, and 2 extension mirrors
  (`seo-dataforseo`, plus a Firecrawl mirror). (Note: the upstream `seo` skill name
  is why this idea-to-deploy skill is `seo-setup`.)
- **18 sub-agents** — `seo-technical`, `seo-content`, `seo-schema`, `seo-sitemap`,
  `seo-performance`, `seo-visual`, `seo-geo`, `seo-local`, `seo-maps`,
  `seo-backlinks`, `seo-cluster`, `seo-sxo`, `seo-drift`, `seo-ecommerce`,
  `seo-image-gen`, `seo-flow`, `seo-google`, `seo-dataforseo` — spawned in parallel
  by `/seo audit`.
- **1 hook** — a `PostToolUse: Edit|Write` hook (`run-python-hook.js` →
  `validate-schema.py`) that validates JSON-LD/Schema.org files when you edit them.
- **8 optional MCP extensions** — DataForSEO, Firecrawl, Banana, Ahrefs, SE Ranking,
  Profound, Bing Webmaster, Unlighthouse — each off by default and needing its own
  API key.

**Cost tradeoff:** this is a large plugin with a Python toolchain and many skills/
agents. It pays off for projects that actually ship a website / public surface and
care about organic + AI-search visibility; it is overkill for an internal tool, a
library, or a CLI with no web presence.

Requirements: **Python 3.10+** with pip, **Git**, and **Claude Code ≥ 1.0.33**.
Optional **Playwright** (Chromium) for screenshots / headless rendering. The Google
APIs and premium extensions need their own credentials.

## Install / detect

`/seo-setup` never installs anything silently. It detects state and, only with your
go-ahead, runs (or prints) the documented commands.

**Detect** whether it is installed (read-only):

```bash
claude --version                                  # need ≥ 1.0.33
python3 --version                                  # need ≥ 3.10 for the engine (win-ok: probe)
claude plugin list 2>/dev/null | grep -i claude-seo || echo "claude-seo: NOT installed"
claude plugin details claude-seo 2>/dev/null       # components, if installed
```

**Install** — marketplace add then plugin install (verified from the upstream
INSTALLATION guide):

```bash
# CLI
claude plugin marketplace add AgriciDaniel/claude-seo
claude plugin install claude-seo@agricidaniel-claude-seo
```

```text
# or in-app, inside Claude Code
/plugin marketplace add AgriciDaniel/claude-seo
/plugin install claude-seo@agricidaniel-claude-seo
```

The plugin then needs its **Python dependencies**. The installer creates a venv at
`~/.claude/skills/seo/.venv/`; if that step is skipped, install manually:

```bash
~/.claude/skills/seo/.venv/bin/pip install -r ~/.claude/skills/seo/requirements.txt
```

Then **restart Claude Code** (plugins load at startup) and verify with
`/seo audit <url>` on a known page, or `claude plugin details claude-seo` for the
component list. To remove later: `claude plugin uninstall claude-seo`.

If `python3 --version` is below 3.10, or the venv / Python deps are not installed,
report the blocker plainly — do **not** claim Claude SEO is active when its Python
toolchain cannot run.

## idea-to-deploy fit

Claude SEO is an **optional capability companion**, not a work route. It adds SEO
analysis *into* the lifecycle; it never changes *what the methodology requires*. The
gates still win: `/review`, `/test`, `/security-audit`, DoD, and the skill-decision
line are unaffected.

Where it pays off most in the lifecycle:

| Lifecycle step | Why Claude SEO helps |
|---|---|
| `/discover`, `/market-scan` | Keyword & competitor research, SERP intent, backlink landscape: `/seo cluster <seed>`, `/seo backlinks <url>`, `/seo competitor-pages`, `/seo flow find`. Feeds personas/positioning with real search demand. |
| `/blueprint` | Information architecture, Schema.org plan, i18n: `/seo schema <url>`, `/seo hreflang`, `/seo plan <business-type>`. Bake structured data + URL/i18n strategy into the design, not retrofit it. |
| `/kickstart` | On-page SEO scaffolding: `/seo page <url>`, `/seo content-brief <topic>`, `/seo sitemap generate`. Pages ship with titles/meta/schema/sitemap in place. |
| `/harden` | Technical SEO + Core Web Vitals + GEO before launch: `/seo technical <url>`, `/seo audit <url>`, `/seo geo <url>`. Treats crawlability/indexability/CWV as a production-readiness gate, alongside health checks & monitoring. |
| `/deploy` | Capture a drift baseline and wire Google APIs: `/seo drift baseline <url>`, `/seo google <gsc|pagespeed|crux>`. Post-deploy regressions in ranking/CWV become observable. |

**Do not** enable it for projects with no public web surface (internal tools,
libraries, CLIs) — the Python toolchain and large skill/agent surface cost more
than they return when there is nothing to rank.

## Coexistence with idea-to-deploy hooks

idea-to-deploy registers its enforcement hooks (PreToolUse/PostToolUse/
UserPromptSubmit/Stop/PreCompact/SessionStart). Claude SEO registers **one**
`PostToolUse: Edit|Write` hook (JSON-LD/Schema.org validation). Claude Code runs
multiple plugins' hooks side by side, so confirm there is no interference after
install:

- Claude SEO's schema hook fires on **every** Edit/Write and shells out to
  `node` + `validate-schema.py` (needs the Python deps). On a repo with no schema
  files it is a no-op, but if Python deps are missing it can emit errors on each
  edit — install the venv or it will be noisy.
- Sanity-check that idea-to-deploy gates still fire: a >2-file commit without a
  review must still be blocked by `check-review-before-commit.sh`; the
  skill-enforcement counter must still escalate; the DoD pre-commit gate must still
  run. Claude SEO validates schema files, it must not swallow our hooks' stderr
  guidance.
- If a conflict appears (a gate stops firing, or guidance is hidden), report it; do
  not paper over it. The two plugins are independent — `claude plugin disable
  claude-seo` reverts Claude SEO without touching idea-to-deploy.

## Self-validation

Before responding, check:

- Install state was actually detected (not assumed) — if Claude SEO is not
  installed, say so and offer the install commands; never claim it is active.
- Python ≥ 3.10 and Claude Code ≥ 1.0.33 were checked, and the Python deps / venv
  status noted, before declaring it usable.
- The mechanism is described per the upstream repo (25 skills + 18 agents + 1
  schema hook + 8 optional MCP extensions), not invented tools.
- No upstream MIT/CC-BY source was copied into the repo; attribution to
  @AgriciDaniel is intact.
- idea-to-deploy gates/verification/commit-status are reported truthfully and were
  not affected by the integration.

## Examples

### Example 1: Project needs SEO, plugin not installed

User: «нужно сделать SEO-аудит сайта, как подключить?»

Actions:
1. Recognize an SEO need → this skill.
2. Detect: run `claude plugin list | grep claude-seo`. Not installed.
3. Explain the fit (where SEO slots into the lifecycle — `/harden` technical audit,
   `/blueprint` schema) and run/print the two CLI install commands + the Python
   deps step. Note Python ≥ 3.10 / CC ≥ 1.0.33.
4. After they install + restart, have them run `/seo audit <url>` to confirm.
5. Remind: idea-to-deploy gates are unaffected; this only adds SEO capability.

### Example 2: Already installed — map onto the current phase

User: «claude-seo стоит, мы на этапе harden — что прогнать?»

Actions:
1. Run `claude plugin details claude-seo` (component list); report it.
2. Map `/harden` → `/seo technical <url>`, `/seo audit <url>`, `/seo geo <url>`
   (CWV, crawlability, AI-search visibility as a pre-launch gate).
3. Confirm idea-to-deploy gates still fire (review gate blocks an unreviewed
   multi-file commit; DoD gate runs). Report pass/fail honestly.

### Example 3: No web surface — recommend against

User (internal CLI tool): «давай прикрутим SEO-плагин»

Actions:
1. The project has no public web surface → nothing to rank.
2. Recommend against installing it here; reserve it for projects shipping a website
   or public content. The Python toolchain + large surface are not worth it.

### Example 4: License / vendoring boundary

User: «давай просто скопируем все seo-скиллы к нам в репозиторий»

Actions:
1. Decline by default: the upstream is large (25 skills + 18 agents) with a heavy
   Python toolchain, and the FLOW prompts are CC BY 4.0 (attribution obligation).
   Vendoring would bloat idea-to-deploy and break its no-heavy-dep design.
2. Offer the supported path instead: marketplace install + this skill.
3. No upstream source is copied into the repo; attribution to @AgriciDaniel intact.

## Troubleshooting

### `python3 --version` < 3.10
The upstream toolchain needs Python ≥ 3.10. Report the blocker; do not claim Claude
SEO is active. Suggest upgrading Python, then re-run the install / venv step.

### Schema-validation hook errors on every edit
Claude SEO's `PostToolUse: Edit|Write` hook needs `node` + the Python deps. If the
venv was not created, install it (`pip install -r ~/.claude/skills/seo/requirements.txt`).
This does not affect idea-to-deploy's own hooks.

### A gate stopped firing after installing Claude SEO
Report it as a real conflict — do not work around it silently. Verify by temporarily
checking the gate (e.g. attempt a >2-file commit without review). The two plugins
are independent; if needed, `claude plugin disable claude-seo` to confirm the gate
returns, then file the conflict.

### User wants the plugin vendored into idea-to-deploy
Decline by default: the upstream is a large plugin (25 skills + 18 agents) with a
heavy Python toolchain (`playwright`, `weasyprint`, `lxml`, Google APIs), and its
FLOW prompts are CC BY 4.0. Vendoring would bloat the methodology and break its
no-heavy-dep design. The marketplace install + this integration is the supported
path.

## Rules (hard)

- Never perform a global/network install or edit shell profiles / plugin config
  without explicit user approval — detect and print/run commands on their say-so.
- Never copy upstream source (skills, agents, FLOW prompts) into this repo; keep
  attribution to @AgriciDaniel.
- Never claim Claude SEO is installed/active without detecting it (`claude plugin
  list` / `claude plugin details`) and confirming the Python toolchain can run.
- Describe the mechanism per the upstream repo (25 skills + 18 agents + 1 schema
  hook + 8 optional MCP extensions), not invented tools.
- Never let the integration hide or weaken an idea-to-deploy gate, verification
  result, or the skill-decision line.
- This skill is a capability companion; it does **not** replace `/review`, `/test`,
  `/security-audit`, or any work route.
