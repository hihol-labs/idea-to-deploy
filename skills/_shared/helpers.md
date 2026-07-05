# Shared Helpers — Common Patterns for Audit-Style Skills

> This file is the single source of truth for patterns shared across
> `/review`, `/security-audit`, `/deps-audit`, and `/harden`.
> Skills reference it via `skills/_shared/helpers.md` instead of
> re-declaring these definitions locally.
>
> Added in v1.17.0 to reduce token consumption by ~190 lines across
> 4 audit checklists (inspired by BMAD's helper pattern).

---

## 1. Gate Status Enum

Every audit-style skill produces a final status using this 3-level enum:

| Status | Condition | Meaning |
|--------|-----------|---------|
| **BLOCKED** | Any Critical check fails | The artifact MUST NOT proceed (merge, deploy, release) until fixed |
| **PASSED_WITH_WARNINGS** | All Critical pass, any Important fails | Can proceed with acknowledged tech debt; fix before next milestone |
| **PASSED** | All Critical + all Important pass | Ready to proceed |

Nice-to-have checks do NOT affect the gate status — they are informational only.

---

## 2. Report Format Template

All audit skills produce a markdown report with this structure:

```markdown
# {Skill Name} Report

## Summary
- **Project:** {name}
- **Date:** {date}
- **Status:** {BLOCKED | PASSED_WITH_WARNINGS | PASSED}
- **Score:** {pass_count}/{total_count}

## Critical Tier
{For each check: ✅ PASS or ❌ FAIL with explanation}

## Important Tier
{For each check: ✅ PASS or ⚠️ WARNING with explanation}

## Nice-to-Have Tier
{For each check: ✅ PASS or ℹ️ SUGGESTION with explanation}

## Results Table
| Tier | Pass | Total | Status |
|------|------|-------|--------|
| Critical | X | Y | ��� / ❌ |
| Important | X | Y | ✅ / ⚠️ |
| Nice-to-have | X | Y | ✅ / ℹ️ |

## Final Status: {BLOCKED | PASSED_WITH_WARNINGS | PASSED}
```

Icons:
- `✅` �� check passed
- `❌` — Critical check failed (blocks)
- `⚠️` — Important check failed (warning)
- `ℹ️` — Nice-to-have suggestion (informational)

---

## 3. Secret Detection Patterns

Canonical regex list for detecting hardcoded secrets in source code.
Used by `/review` (C10), `/security-audit` (SECRET-1), `/harden` (SEC-1).

```
# API keys and tokens
password\s*=\s*["'][^"']+["']
api_key\s*=\s*["'][^"']+["']
secret\s*=\s*["'][^"']+["']
token\s*=\s*["'][^"']+["']

# Bearer tokens in code
Bearer\s+[a-zA-Z0-9_\-\.]+

# Provider-specific patterns
sk-[a-zA-Z0-9]{20,}              # OpenAI / Stripe secret keys
ghp_[a-zA-Z0-9]{36}              # GitHub personal access tokens
ghs_[a-zA-Z0-9]{36}              # GitHub server tokens
AKIA[0-9A-Z]{16}                 # AWS access key IDs
xox[bprs]-[a-zA-Z0-9\-]+        # Slack tokens
glpat-[a-zA-Z0-9\-]{20,}        # GitLab personal access tokens
```

**Exclusions** (NOT secrets):
- `.env.example` with placeholder values (`YOUR_KEY_HERE`, `changeme`, `xxx`)
- Test fixtures with obviously fake values
- Documentation examples

---

## 4. Environment File Checks

Standard checks for `.env` handling (shared across `/review`, `/security-audit`, `/harden`):

| Check | What to verify |
|-------|---------------|
| `.env` in `.gitignore` | `.gitignore` contains `.env` (not just `*.env`) |
| `.env.example` exists | Template file with all required vars and placeholder values |
| No real secrets in `.env.example` | Values are `changeme`, `YOUR_KEY`, empty, or obviously fake |
| `.env` not committed | `git log --all -- .env` returns empty |

---

## 5. Stack Detection Heuristic

When a skill needs to know the project's tech stack, use this detection order:

| Signal | Stack | Confidence |
|--------|-------|-----------|
| `pyproject.toml` or `requirements.txt` | Python | High |
| `package.json` | Node.js/TypeScript | High |
| `go.mod` | Go | High |
| `Cargo.toml` | Rust | High |
| `pom.xml` or `build.gradle` | Java | High |
| `Gemfile` | Ruby | High |
| `composer.json` | PHP | High |
| `*.csproj` or `*.sln` | .NET | High |

Framework sub-detection (Python):
- `fastapi` in deps → FastAPI
- `django` in deps → Django
- `flask` in deps → Flask

Framework sub-detection (Node.js):
- `next` in deps → Next.js
- `nuxt` or `vue` in deps → Vue/Nuxt
- `express` in deps → Express

Skills should detect once and cache the result for the session.

---

## 6. Process-Cost Tiers (complexity routing)

> Added in v1.21 (PFO plugin-native port, item 15). Scales how much methodology a
> task gets to its actual risk — a README typo must not drag the full lifecycle, and
> a production migration must not slip through a light path. Based on PFO's
> `product-classifier` **COMPLEXITY** signal (low/medium/high), **not** any fixed
> "minimal/standard/full" profile.

Classify by signals, then apply the matching process cost:

| Tier | Signals | Contracts | Gates applied |
|---|---|---|---|
| **trivial** | typo, rename, one-line fix, comment/doc tweak, obvious cause | none | sanity check only — do it directly |
| **standard** | normal feature/refactor/bugfix in existing code, single module | `SCOPE_LOCK.md` | spec-compliance (Stage A) + fail-closed verify + `/review` + `/test` |
| **high-risk** | production mutation, schema change, deploy, infra/provisioning, auth/payment/security-sensitive, autonomous run, cross-module | full `.itd/` set + `PERMISSION_MATRIX` | all standard gates + acceptance contract + root-cause (if bugfix) + branch-finish + **explicit user approval** |

The **high-risk** tier aligns with skills carrying `explicit_invocation: true` in their
frontmatter (`migrate`, `migrate-prod`, `deploy`, `infra`, `autopilot`). When routing
to one of those, default to the high-risk path. When in doubt between two tiers, pick
the higher one — under-processing a risky change is the expensive mistake.

---

## 7. Context Budget

> Added in v1.21 (PFO plugin-native port, item 16). Long tasks degrade when raw dumps
> flood the context window. Spend context like a budget.

Rules for large tool outputs (logs, HTTP responses, `cat` of big files, wide `grep`/`rg`):

- **Summarize, don't dump.** Capture the signal (counts, the 3–5 relevant lines, the error) — not the whole stream.
- **Artifact + path, not inline.** When the full output matters, write it to a file and reference the path (`see /tmp/run-1234.log`), rather than pasting thousands of lines into the conversation.
- **Bound at the source.** Prefer `… | head -50`, `rg -m 20`, `--max-count`, `tail -n 100` over unbounded reads. Read the slice you need (Read with `offset`/`limit`), not the whole 2000-line file.
- **No raw remote bodies.** Never paste an entire raw HTTP/API response; extract the fields in question.

The soft hook `hooks/context-budget.sh` nudges when a command is likely to dump a large
unbounded output. It is a reminder, never a block — judgment stays with the skill.

## 8. Delegation Intent Template (v1.50.0)

> Fable 5-era models perform measurably better when they understand the intent
> behind a request — they connect the task to relevant context instead of
> inferring intent on their own. This matters most for delegated subagents,
> which see none of the parent conversation.

When spawning ANY subagent (architect, code-reviewer, test-generator, Explore,
researcher, …), the prompt MUST carry three intent lines before the request:

```
Я работаю над [большая задача] для [кто потребитель результата].
Результат нужен, чтобы [что он разблокирует / как будет использован].
С учётом этого: [конкретный запрос к субагенту].
```

Two companion rules:

- **Prescriptive triggers, not capability lists.** When the subagent gets
  tools/скиллы, say WHEN to use each ("зови `/test`, когда меняешь
  исполняемый код; НЕ зови для чистых доков"), not merely that they exist —
  trigger conditions in the instruction give measurable lift on should-call
  rate (vendor guidance, Opus 4.7+/Fable 5).
- **Report-back contract.** Tell the subagent its final message is a return
  value, not a user-facing chat: outcome first, evidence attached,
  «Не успел проверить: …» tail when applicable (pairs with
  `hooks/narration-final.sh`).
