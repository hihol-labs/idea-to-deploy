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
