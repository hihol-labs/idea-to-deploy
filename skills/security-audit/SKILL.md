---
name: security-audit
description: 'Audit code for security vulnerabilities — auth, secrets, injection, CORS/CSP, CVEs, file uploads, error leaks. Read-only report.'
argument-hint: file, directory, or "all" for full project
license: MIT
allowed-tools: Read Glob Grep
metadata:
  effort: medium
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.83.0
  category: quality-assurance
  tags: [security, audit, vulnerabilities, owasp]
---

# Security Audit

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- проверь безопасность, security audit, найди уязвимости
- проверь auth, проверь токены, проверь секреты
- secrets check, exposed credentials, утечка ключа
- CORS check, CSP check, security headers
- проверь PR на безопасность, перед продакшеном проверить
- OWASP, vulnerability scan, security review

## Recommended model

**opus** — Security review benefits from cross-file pattern recognition (a vulnerability often spans config + code + test). Sonnet is acceptable for narrow scopes (single file, single auth flow). Haiku is not enough — security false negatives are dangerous.

Set via `/model opus` before invoking this skill.

## Instructions

You are a defensive-security reviewer. Your job is to find common security mistakes BEFORE they ship. Apply OWASP-style checks and stack-specific gotchas. Read-only — you propose fixes, you do not apply them.

### Step 1: Determine scope

If `$ARGUMENTS` specifies a path, audit only that. Otherwise audit the whole project.

Identify the stack (Python/Node/Go/etc.) and frameworks (Express/FastAPI/Django/Next.js/...). The applicable checks differ by framework.

### Step 2: Run the checklist

Consult `references/security-checklist.md` for the full set of checks. The checklist has 4 tiers:

- **Tier 1 — Critical** (block before deploy): hardcoded secrets in source/config, missing auth on protected routes, SQL/command injection, dangerous deserialization
- **Tier 2 — Important** (must be addressed): missing CSRF, weak password hashing, missing rate limiting, predictable IDs, unsigned cookies, missing security headers
- **Tier 3 — Recommended**: missing CSP, no input validation library, error messages leak stack, no audit logging
- **Tier 4 — Informational**: outdated dependencies, missing 2FA option, no penetration test history

**Context & memory integrity (AI/agent targets only — Day-3 port, v1.32.0).** When the
target is an AI agent / LLM app with a context window or a memory store, additionally run
the `MEM-*` checks in `references/security-checklist.md`: prompt-injection trust
boundary, memory poisoning, cross-tenant memory isolation, PII/secrets in context or
store, memory exfiltration, and unreviewed async memory writers. N/A for non-AI targets.
The memory store *is* an attack surface — the agentic analogue of injection/auth.

For each check, look at specific files:
- Auth: middleware, login/register routes, token issuance/verification
- Secrets: `.env`, `config/*`, anything matching `password=`/`api_key=`/`Bearer ` not pointing to env vars
- Injection: any string concatenation passed to SQL/shell/eval/Function constructor
- CORS/CSP: server response headers, middleware setup
- Dependencies: `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml` — flag known-vulnerable versions if recognizable

### Step 2.5: Refute pass — adversarially verify each Critical/Important finding before it escalates (v1.60.0 — Ось 2, agentic engineering)

The refute pass from `/review` Step 2.6, applied to the security verify fleet. A
plausible-but-wrong vulnerability that survives to the report is a false alarm
that erodes trust in the gate and wastes remediation effort — this pass exists to
kill exactly those. Before writing the report, put every **Critical and
Important** candidate finding through an independent refutation.

For each such finding, dispatch a **fresh-context** subagent via the **Agent
tool** (`Agent(subagent_type: "security-reviewer", …)`) with a **refute prompt**:
state the single finding verbatim (its `file:line`, the vuln class, the claimed
exploit path) and instruct the agent to **REFUTE exploitability** — read the
actual code and look for a **concrete** reason it is NOT exploitable (input
sanitized upstream, route unreachable / behind auth, the "secret" is a test
fixture, the sink is not attacker-reachable). Fresh context is load-bearing: the
refuter must not inherit your reasoning, or it will rubber-stamp — pass the
finding by value, the target by path.

- A finding **refuted with a concrete reason** → move it to "Informational" with
  a `refuted` note; it no longer gates.
- A finding **not refuted** → keep it at its tier. Security-specific tie-break:
  vague doubt is **not** a refutation — «я не смог подтвердить» drops nothing
  (false-negative on a real vuln is worse than a false-positive here).
- **Minor / Recommended / Informational findings are NOT refuted** — they never
  gate, so the cost is not justified; report them as observations.

**Invariant:** the refute pass can only REMOVE unconfirmed findings from
escalation; it never invents a new vulnerability and never downgrades a
*confirmed* Critical. If subagents cannot be dispatched in this runner, do the
refutation inline as a separate adversarial reasoning pass and say so ("refute
pass: inline"). This is distinct from `--redblue` (Step 5), which *models*
attack/defense pairs; the refute pass *filters* the findings already surfaced.

### Step 3: Generate report

Use this exact format (parseable by `/review` and other downstream skills):

```markdown
## /security-audit report

### Tier 1: Critical
- ❌ AUTH-1: GET /api/admin/* has no auth middleware
       → routes/admin.ts:12 — add `requireRole('admin')`
- ✅ SECRET-1: No hardcoded API keys in source
- ❌ INJECT-1: SQL string concat in user search
       → db/search.py:34 — use parameterized query
- ❌ MEM-1: tool/RAG output flows into the prompt as instructions (injection)
       → agents/researcher.py:88 — label retrieved text as data, not instructions

### Tier 2: Important
- ⚠️ CSRF-1: No CSRF protection on POST /api/profile
       → suggest: `csurf` middleware or double-submit cookie
- ✅ HASH-1: bcrypt with cost factor 12 (good)

### Tier 3: Recommended
- ℹ️ CSP-1: No Content-Security-Policy header
- ℹ️ ERROR-1: Stack traces returned in 500 responses

### Tier 4: Informational
- ℹ️ DEP-1: `axios@0.21.0` has known CVE-2021-3749 — bump to >=0.21.4

### Summary
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | 1 | 3 | ❌ BLOCKED |
| Important | 1 | 2 | ⚠️ |
| Recommended | 0 | 2 | ℹ️ |
| Informational | 0 | 1 | ℹ️ |

**Final status:** BLOCKED (must fix AUTH-1 and INJECT-1 before deploy)
```

### Step 4: Offer guidance

For each Critical or Important issue, propose a fix WITHOUT applying it. Format:

```markdown
**AUTH-1: GET /api/admin/* has no auth middleware**

Suggested fix:
\`\`\`ts
// routes/admin.ts
import { requireRole } from '../middleware/auth'
router.use(requireRole('admin'))  // add at top
\`\`\`

Apply this fix? [yes/no]
```

If user says yes, ask them to invoke `/bugfix` or use the Edit tool directly — `/security-audit` is read-only by design (allowed-tools: Read Glob Grep). This separation prevents the auditor from also being the fixer, which is a common audit anti-pattern.

### Step 5: Adversarial Mode (--redblue flag, v1.17.0)

If user passes `--redblue` or says "red team / blue team":

**Red Team phase** — think like an attacker:
1. Identify the 3 most valuable targets in the app (user data, admin panel, payment flow)
2. For each target, describe a concrete attack scenario:
   - **Attack vector:** how would you get in?
   - **Exploit steps:** 1-2-3 sequence
   - **Impact:** what data/access is compromised?
   - **Likelihood:** Low/Medium/High based on exposed surface

**Blue Team phase** — fix each Red Team finding:
1. For each attack scenario, propose a specific defense
2. Classify defense as: Prevention (blocks the attack), Detection (alerts on attempt), Recovery (limits damage)
3. Prioritize defenses by effort/impact ratio

Present as a table:

```markdown
### Red Team / Blue Team Analysis

| # | Target | Attack Vector | Impact | Defense | Defense Type | Priority |
|---|--------|-------------|--------|---------|-------------|----------|
| 1 | Admin panel | Brute-force login | Full admin access | Rate limit + account lockout + 2FA | Prevention | P0 |
| 2 | User data | IDOR on /api/users/:id | PII leak | Ownership check middleware | Prevention | P0 |
| 3 | Payment flow | Replay attack on webhook | Double-charge | Idempotency key + signature verification | Prevention | P1 |
```

This mode is inspired by AI-DLC's Red/Blue Team hat separation. It adds ~5 minutes to the audit but surfaces attack scenarios that checklist-based audits miss.

### Step 6: Record the exact-context `/security-audit` verdict

Final step of every `/security-audit` invocation. Persist the real verdict
against the same exact context key used by `/review`. Only an accepted security
verdict may satisfy the DoD security sentinel and pay down the **security** risk
bucket. A general review cannot reset this bucket; `BLOCKED` and `UNVERIFIED`
must leave the gate closed.

```bash
RC="skills/review/scripts/itd_review_cache.py"
[ -f "$RC" ] || RC="$HOME/.claude/idea-to-deploy/skills/review/scripts/itd_review_cache.py"
SHD="skills/_shared"
[ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/idea-to-deploy/skills/_shared"
sh "$SHD/itd_py.sh" "$RC" record --root . --kind security --verdict PASSED
```

For `PASSED_WITH_WARNINGS`, pass durable `--warning "path: summary"` values.
The authenticated workflow caller must perform this write explicitly after it
accepts the independent audit verdict. `hooks/verdict-contract.sh` validates
the machine-readable shape but cannot infer a trusted security-audit producer
from generic SubagentStop text and therefore never writes cache evidence.

## Quality Gate

This skill returns the same status enum as `/review`:

- `BLOCKED` → at least one Critical issue
- `PASSED_WITH_WARNINGS` → no Critical, at least one Important
- `PASSED` → all Critical and Important pass

`/kickstart` Phase 5 (Deployment) should call `/security-audit` and refuse to deploy on `BLOCKED`.

## Examples

### Example 1: Auth audit before launch
User says: "Перед продакшеном проверь безопасность auth"

Actions:
1. Find auth middleware, login/register routes, token verification
2. Check that every protected route applies the middleware
3. Check JWT signing key is from env, not hardcoded
4. Check refresh token rotation
5. Check password hashing (bcrypt cost ≥ 10)
6. Generate report

Result: 2 Critical issues found (admin route unprotected, JWT secret hardcoded). Blocked deploy until fixed.

### Example 2: Secrets sweep
User says: "secrets check, проверь нет ли в коде ключей"

Actions:
1. Grep all source files for: `password=`, `api_key=`, `secret=`, `token=`, `Bearer `, `sk-`, `AKIA`
2. Filter out: env var references (`process.env.X`, `os.getenv("X")`), placeholder values (`xxx`, `<your_key>`)
3. Report each remaining match with file:line and suggested env var name

Result: 1 hardcoded ChatGPT API key in `lib/openai.ts:8`. Suggested fix: `process.env.OPENAI_API_KEY`.


## Self-validation

Before presenting audit report, verify:
- [ ] All OWASP Top 10 categories checked (or marked N/A with justification)
- [ ] Each finding has severity level (Critical/High/Medium/Low/Info)
- [ ] No false positives from generic patterns (verify each finding against actual code)
- [ ] Report is READ-ONLY — no fixes applied, only recommendations
- [ ] If --redblue mode: both Red Team (attack vectors) and Blue Team (defenses) documented

## Troubleshooting

### Too many false positives
Tighten the regex patterns in `references/security-checklist.md` for your stack. Common false-positive sources: test fixtures, example files, documentation snippets.

### Audit on huge project times out
Limit scope: pass a specific directory like `src/auth/` instead of the whole repo.

### Issue is in a third-party dep
Document it as Tier 4 informational with the CVE number. Recommend upgrade. Do not try to patch the dep inline.

## Rules

- READ-ONLY. Never apply fixes. Suggest, don't execute.
- Use the same status enum as `/review` so downstream skills can chain reliably.
- Be specific: file:line for every finding, never "somewhere in auth".
- Escalate, don't hide: when unsure if something is a vulnerability, report it as Recommended with reasoning.
- Match the language of the user's request for the report (if user wrote in Russian, report in Russian).
