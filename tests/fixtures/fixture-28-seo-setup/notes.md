# Manual verification — fixture 28 (/seo-setup)

`/seo-setup` is a **read-only** orchestrator/integration skill for the upstream
[Claude SEO plugin](https://github.com/AgriciDaniel/claude-seo) by @AgriciDaniel
(license **MIT**; bundled FLOW prompts CC BY 4.0). The upstream plugin ships 24
sub-skills + 18 sub-agents covering technical SEO, content quality (E-E-A-T),
Schema.org, sitemaps, Core Web Vitals, local SEO, backlinks, AI/GEO, e-commerce,
hreflang, and the Google SEO APIs. This skill ships **no** upstream source: it
detects install state, runs/prints the verified install commands, and maps the
plugin onto the idea-to-deploy lifecycle. It MUST NOT modify project files. This
fixture regressionally fixes the detect-before-claim rule, the no-vendoring
contract, the accurate-mechanism rule, the lifecycle fit, and the gate-coexistence
guarantee.

Named `seo-setup`, not `seo`: the upstream plugin ships its own orchestrator skill
literally named `seo` (invoked `/seo audit <url>`), so a bare `/seo` would collide.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor`,
`fixture-21-mcp-docs`, `fixture-26-caveman`, and `fixture-27-context-mode-setup`
(read-only, detect/advise stdout flow). For now: manual checklist below. The stub
satisfies `check-skill-completeness.sh`.

## /seo-setup — Scenario A: SEO need, not installed (happy path)

User pastes the prompt from `idea.md`: needs an SEO audit + schema markup.

### Critical contract: no files written

After the run, `output/` must contain no skill-authored files. `/seo-setup` only
detects and advises.

### Expected output shape

- Recognizes an SEO need → routes to /seo-setup.
- Runs read-only detection (`claude plugin list | grep claude-seo`); finds it NOT
  installed → says so explicitly (never claims it is active).
- Runs/prints the verified CLI install commands, the Python deps / venv step, and
  the Python ≥ 3.10 / Claude Code ≥ 1.0.33 requirement.
- After install + restart, instructs to run `/seo audit <url>` (or
  `claude plugin details claude-seo`) to confirm.

## /seo-setup — Scenario B: already installed, map onto the phase

User: "claude-seo стоит, мы на этапе harden — что прогнать?"

### Expected

- Runs `claude plugin details claude-seo` (component list); reports it.
- Maps `/harden` → `/seo technical <url>`, `/seo audit <url>`, `/seo geo <url>`
  (Core Web Vitals, crawlability, AI-search visibility as a pre-launch gate).
- Confirms idea-to-deploy gates still fire: a >2-file commit without a review is
  still blocked by `check-review-before-commit.sh`; the DoD gate still runs.
  Reports pass/fail honestly.

## /seo-setup — Scenario C: license / vendoring boundary

User: "давай просто скопируем все seo-скиллы к нам в репозиторий"

### Expected

- Declines by default: upstream is large (25 skills + 18 agents) with a heavy
  Python toolchain, and the FLOW prompts are CC BY 4.0 (attribution obligation).
  Vendoring would bloat idea-to-deploy and break its no-heavy-dep design.
- Offers the supported path instead: marketplace install + this skill.
- No upstream source is copied into the repo; attribution to @AgriciDaniel intact.

## /seo-setup — Scenario D: no web surface, recommend against

User (internal CLI tool): "давай прикрутим SEO-плагин".

### Expected

- The project has no public web surface → nothing to rank.
- Recommends against installing it here; reserves it for projects shipping a
  website or public content.

## Why pending (not active)

Phase 1 snapshot validation is file-shaped (`verify_snapshot.py` checks written
files against `expected-files.txt`). `/seo-setup` writes nothing and only affects a
detect/advise stdout flow, so structural automation is deferred to the Phase 2
stdout-snapshot scheme. This stub anchors the contract for manual regression until
then.
