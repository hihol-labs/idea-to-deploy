# ROADMAP v1.21 — Deliberate Pause

> **Status:** 🟡 **DEFERRED — no code release planned for v1.21.**
> Decision made 2026-04-17 via `/advisor` session (business-analyst +
> devils-advocate subagents). Methodology is stable at v1.20.2; the
> correct next step is adoption/metrics work, not more code.

---

## The decision in one paragraph

After closing Gap #8 (`/adopt`, v1.20.0) and three retrospective gaps
(v1.20.1 + v1.20.2) the methodology sits at `25 skills + 7 subagents +
13 hooks`, all three quality axes at 10/10, zero open critical bugs.
There are four candidate v1.21 directions in community feedback
(adversarial debates, decision trees, SAFe patterns, flexible entry
points). Each is based on **n=1** signal. The monetisation strategy
(`project_monetization_strategy.md`) explicitly sequences **adoption
→ community → monetization**, and the plugin is still in phase 1.
Shipping a v1.21 code-release now adds complexity to a solo-maintainer
surface without changing adoption-funnel throughput. The correct
trade is to pause code, instrument, and wait for multi-point signal
before architecting v1.21 scope.

---

## What we considered

| # | Proposal | Effort | Validation gate | Adoption impact | Verdict |
|---|---|:---:|:---:|:---:|---|
| 1 | Adversarial debates between subagents | 5-7d | **Absent** (no deterministic test for LLM debates) | Low — feature hidden deep in `/blueprint` Step 2 | Rejected |
| 2 | Decision trees (Mermaid) in skills | 2-3d | Static, low risk | None — solution in search of a problem | Rejected (fallback option) |
| 3 | SAFe-inspired enterprise patterns | 10+d | N/A | None — audience mismatch | Rejected |
| 4 | Flexible entry points (persona routers) | 3-5d | Partial | Low — marketing layer, not architecture | Rejected |
| **0** | **No code release — adoption work instead** | 0d code | N/A | **Direct** (metrics, content, tech-debt) | ✅ **Chosen** |

Full rationale per option lives in the /advisor session transcript
saved in memory as `session_2026-04-17_3.md` (or wherever the next
save lands).

---

## What we do instead (next 6-8 weeks)

### A. Instrument the adoption funnel

- Repo-level weekly dashboard: stars, issues opened/closed, discussions,
  marketplace-install counts (if exposed by any of the 7 directories we
  submitted to), `/plugin install HiH-DimaN/idea-to-deploy` telemetry.
- **Nothing to decide until there are numbers.** All v1.21 candidates
  are currently based on n=1 — decisions on that signal are cargo-cult.

### B. Finish the v1.19 content batch

From `session_2026-04-12-d.md`: content drafts are ready, the B-batch
was never posted. One-shot first-touch posts to Dev.to / Habr / Reddit
+ the v1.19.x/v1.20.x update summary. Not re-posting existing channels
(see `feedback_promotion_oneshot.md`).

### C. Respond to **real** user feedback

One live external user with one specific pain = more signal than all
four n=1 proposals combined. The community-feedback items stay on
`project_community_feedback.md`; no code commitment until a concrete
request arrives from someone who installed the plugin.

### D. Low-risk tech-debt pass (optional)

If the maintainer needs "velocity feeling" without adding scope:
- Walk the CHANGELOG, close edge-case TODOs.
- Expand fixture stubs (`fixture-11` through `fixture-17` — all
  currently `status: pending`) into real behavioural fixtures.
- Audit the `check-review-before-commit.sh` → `sync-to-active.sh`
  gap recurrence-prevention story end-to-end (M-C17 or similar).

These are **not** v1.21 scope; they are ordinary tech-debt maintenance
and can ship as `v1.20.3`, `v1.20.4`, etc., without a ROADMAP doc.

---

## When to revisit v1.21

Criteria for re-opening this doc and actually scoping a v1.21 release:

1. **Multi-point community signal (n ≥ 5)** on the same request, OR
2. **One activated external user** (real install + non-trivial usage)
   reports a specific pain the methodology fails to address, OR
3. **Competitor lands a differentiating feature** that materially
   shifts the positioning we built (136-skill cognitive-overload
   narrative, 3-tier testing, self-improvement loop).

None of (1)(2)(3) hold today. Re-evaluate monthly; if still unmet
after 8 weeks, this document graduates to `LESSONS_v1.21.md` as a
record of the deliberate pause.

---

## What changed in the methodology since v1.20.0

For context when this doc is re-read later:

- **v1.20.0** — `/adopt` skill (Gap #8). 25 skills total. (PR #46)
- **v1.20.1** — 10/10 hardening: `check-review-before-commit.sh` finally
  in `sync-to-active.sh`; `verify-sync-to-active.sh` CI guard;
  `disable-model-invocation: true` on `/deploy`, `/migrate`,
  `/migrate-prod`. (PR #47)
- **v1.20.2** — M-C12 regex catches Markdown-bold; competitor-section
  awareness; `sync-to-active.sh` backup rotation; stale `19 skills` →
  `25 skills` drift in `hn-headless-claude-poc.md` caught by the new
  regex. (PR #48)

---

## Anti-pattern this doc prevents

"Methodology velocity" for its own sake. Solo maintainers often ship
versions to feel productive, not because the version is needed. The
next version should be driven by **signal from users**, not by the
maintainer's discomfort with pause. This document exists to make
that pause explicit, dated, and falsifiable.
