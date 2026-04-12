# Security Audit Checklist

> **Shared definitions:** Gate status enum, report format, secret detection patterns, and .env checks are defined in [`skills/_shared/helpers.md`](../../_shared/helpers.md). This file uses those definitions — do not re-declare them here.

> Reference for `/security-audit`. Binary checks organized into 4 tiers. Modeled on OWASP Top 10 + practical pitfalls observed in real production incidents.

The 4 tiers map to gate behavior:

| Tier | On failure | Gate behavior |
|---|---|---|
| **Critical** | Block deploy | `BLOCKED` |
| **Important** | Warn loudly | `PASSED_WITH_WARNINGS` |
| **Recommended** | Inform | `PASSED` |
| **Informational** | Mention in report | `PASSED` |

---

## Tier 1: Critical (block deploy)

### AUTH-1: Every protected route has auth middleware applied
**Check:** for each route file (e.g., `routes/`, `app/api/`, `views.py`), verify the middleware is applied. No "I forgot to add `@requires_auth` to this admin route".

Look for:
- Routes under `/admin`, `/api/admin`, `/internal`, `/system` — must have role check
- Routes that mutate data (POST/PUT/DELETE) on user-owned resources — must verify ownership
- Routes returning user PII — must verify the requester is the owner or admin

### AUTH-2: Token verification uses constant-time comparison
**Check:** JWT verification, API key comparison, HMAC signature comparison — must NOT use `==` on bytes/strings. Use `hmac.compare_digest` (Python), `crypto.timingSafeEqual` (Node), `subtle.ConstantTimeCompare` (Go).

### SECRET-1: No hardcoded secrets in source files
**Check:** grep all source files for these patterns and verify each match is either an env var reference OR a placeholder:
- `password\s*=\s*['"][^'"]*['"]` (excluding `<password>`, `xxx`, `${...}`)
- `api[_-]?key\s*=\s*['"][^'"]*['"]`
- `secret\s*=\s*['"][^'"]*['"]`
- `token\s*=\s*['"][^'"]*['"]`
- `Bearer [a-zA-Z0-9._-]{20,}`
- `sk-[a-zA-Z0-9]{20,}` (OpenAI key prefix)
- `AKIA[0-9A-Z]{16}` (AWS access key prefix)
- `ghp_[a-zA-Z0-9]{36}` (GitHub personal token)
- `xox[abp]-[0-9a-zA-Z]{10,48}` (Slack token)

False-positive filtering: ignore matches in `tests/`, `docs/`, `examples/`, `*.md`, `*.example`.

### SECRET-2: .env is gitignored
**Check:** `.gitignore` contains `.env` (or `.env*`). If absent, this is a critical leak risk.

### SECRET-3: .env.example exists and matches .env shape
**Check:** `.env.example` should list every variable from `.env` with placeholder values. Catches "I forgot to document this required env var".

### INJECT-1: No SQL string concatenation
**Check:** scan for SQL with string concat:
- Python: `f"SELECT ... WHERE id = {user_input}"` — bad
- Python: `cursor.execute(f"...{x}...")` — bad
- JS: `` `SELECT ... WHERE id = ${user_input}` `` passed to query — bad
- Should use parameterized queries: `cursor.execute("... WHERE id = %s", (user_input,))` or ORM

### INJECT-2: No shell=True with user input
**Check:** Python `subprocess.run(cmd, shell=True)` where `cmd` includes user input — RCE risk. Same for Node `child_process.exec(...)` (vs `execFile`).

### INJECT-3: No eval() / exec() / Function() on user input
**Check:** any `eval(...)`, `exec(...)`, `new Function(...)` whose argument traces back to user input.

### DESERIALIZE-1: No pickle/marshal on untrusted data
**Check:** Python `pickle.loads(...)`, `marshal.loads(...)`, Java `ObjectInputStream`, `unserialize()` in PHP — all unsafe on untrusted data.

### CRYPTO-1: No MD5/SHA-1 for password hashing or signatures
**Check:** password hashing should use bcrypt/argon2/scrypt. SHA-256 of a password is also wrong (no salt, no work factor).

---

## Tier 2: Important (must address)

### CSRF-1: CSRF protection on state-changing routes
**Check:** for traditional cookie-session apps, verify CSRF tokens (csurf in Express, csrf_token in Django, etc.). Skip for API-only apps using Bearer tokens.

### HASH-1: Password hashing uses bcrypt/argon2 with adequate cost
**Check:** if bcrypt, cost factor ≥ 10. If argon2, time_cost ≥ 2 and memory_cost ≥ 65536.

### RATE-1: Login and password-reset endpoints have rate limiting
**Check:** look for rate-limit middleware on `/api/auth/login`, `/api/auth/reset-password`. Without this, credential stuffing is trivial.

### COOKIE-1: Auth cookies have HttpOnly + Secure + SameSite
**Check:** session/JWT cookies must have `HttpOnly: true`, `Secure: true` (in production), `SameSite: Lax` or `Strict`.

### IDOR-1: Object access checks ownership
**Check:** routes like `GET /api/orders/:id` must verify `order.user_id == current_user.id` (or admin role). Without this, any logged-in user can read any order.

### SESSION-1: Sessions invalidate on password change
**Check:** when user changes password, all existing sessions/tokens must be invalidated. Otherwise, an attacker who stole a token keeps access.

### CORS-1: CORS does not allow `*` with credentials
**Check:** if `Access-Control-Allow-Credentials: true`, then `Access-Control-Allow-Origin` must be a specific origin, not `*`. Browsers block this combo, but server should be safe by default.

### HEADERS-1: Security headers present
**Check:** response includes:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` or CSP frame-ancestors
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HTTPS only)

### UPLOAD-1: File uploads validate type and size
**Check:** if the app accepts file uploads, verify MIME type whitelist (NOT blacklist), max size limit, and storage outside web root.

---

## Tier 3: Recommended

### CSP-1: Content-Security-Policy header configured
**Check:** at minimum `Content-Security-Policy: default-src 'self'`. Stricter is better.

### VALIDATE-1: Input validation library used at API boundary
**Check:** Pydantic (Python), zod (TS), Joi (Node), validator (Go) — applied to every endpoint. Manual `if not isinstance(...)` is fragile.

### ERROR-1: Error responses don't leak stack traces
**Check:** in production mode, 500 responses return generic message, not the Python/JS stack trace. Stack traces in errors give attackers free reconnaissance.

### LOG-1: Audit logging for sensitive actions
**Check:** login attempts (success + fail), password changes, role changes, admin actions — all logged with timestamp + user_id + IP.

### LOG-2: No PII in logs
**Check:** logs do NOT contain passwords, full credit cards, full tokens. Sometimes "log everything" leaks credentials.

### TIMING-1: Login takes the same time for "user not found" and "wrong password"
**Check:** the auth handler should hash a dummy password when the user is not found, to avoid timing-based username enumeration.

---

## Tier 4: Informational

### DEP-1: Known-vulnerable dependency versions
**Check:** scan `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml` for versions with known CVEs. Recognized patterns:
- `axios < 0.21.4` — CVE-2021-3749 SSRF
- `lodash < 4.17.21` — CVE-2020-8203 prototype pollution
- `node-fetch < 2.6.1` — CVE-2020-15168 SSRF
- `pyyaml < 5.4` — CVE-2020-14343 arbitrary code execution
- `jinja2 < 2.10.1` — CVE-2019-10906 sandbox escape

This is a partial list — for full coverage, run `npm audit`, `pip-audit`, `govulncheck`, etc.

### MFA-1: 2FA available for sensitive accounts
**Check:** is there a path to enable TOTP/WebAuthn for admin users? Not required for MVPs but expected for production with paying customers.

### ROTATION-1: Refresh token rotation
**Check:** refresh tokens are rotated on each use (old refresh token invalidated when new one issued). Detects token theft.

### PEN-TEST-1: Penetration test history
**Check:** is there documented pen test or bug bounty? Not always applicable, but worth asking before launch.

---

## Stack-specific gotchas

### Next.js / React
- **Server actions** can be invoked from anywhere — verify auth in the action body, not just the page that renders the form
- **`dangerouslySetInnerHTML`** — verify input is sanitized (DOMPurify or similar)
- **Image component with user URLs** — restrict allowed domains in `next.config.js` to prevent SSRF via image proxy

### FastAPI / Starlette
- **`Depends()` not applied** — endpoint without `Depends(get_current_user)` is unauthenticated
- **CORS middleware order** — must be added before route definitions
- **Pydantic models with `extra="allow"`** — accepts arbitrary fields, can lead to mass assignment

### Django
- **`@csrf_exempt`** — used "temporarily" then forgotten. Always a smell.
- **`SECRET_KEY` from settings.py** — must come from env in production
- **`DEBUG = True`** in production — exposes everything

### Node.js / Express
- **`express.json({ limit })`** — without limit, attacker can send huge JSON to OOM the server
- **`cookie-parser` without secret** — cookies aren't signed
- **`req.body` trusted directly** — always validate before passing to DB query

### Go
- **`html/template` vs `text/template`** — `text/template` doesn't escape, vulnerable to XSS
- **`net/http` ServeMux** — no path traversal protection by default; sanitize before serving files
- **`crypto/md5`, `crypto/sha1`** — never for passwords or tokens

---

## Extended Checks (v1.17.0, Tier 4 — Informational)

These checks are inspired by claude-code-skills' 9-auditor model. They do NOT affect the gate status (informational only) but provide valuable insights for code health.

### DEAD-1: Unreachable exports / unused public functions
**Check:** scan for exported functions/classes that are never imported anywhere in the project. Use `grep -r` on the function name across all source files. Report as informational — dead code is tech debt, not a security risk.
**Common patterns:**
- Python: `def public_func()` defined but never imported
- TypeScript: `export function helper()` but no `import { helper }` anywhere
- Go: `func PublicFunc()` (capitalized) but not called from any other package

### DEAD-2: Unused dependencies
**Check:** for each direct dependency in lockfile (package.json, requirements.txt, go.mod), verify at least one import/require exists in source files. Report unused deps as informational.
**Why it matters:** unused deps increase attack surface (supply chain) and slow builds.

### OBS-1: Structured logging present
**Check:** verify the project uses structured logging (JSON format) instead of plain `print()` / `console.log()` for production code. Acceptable: `structlog`, `loguru` with JSON sink (Python), `pino`, `winston` with JSON transport (Node), `zerolog`, `zap` (Go).
**Why it matters:** unstructured logs are unparseable by log aggregators (Grafana Loki, ELK, Datadog).

### OBS-2: Error tracking integration
**Check:** look for Sentry, Bugsnag, Rollbar, or equivalent error tracking SDK in dependencies and initialization code. Report as informational suggestion if absent.

### CONC-1: Database connection pool configured
**Check:** if using a database, verify connection pool settings are explicit (not defaults). Look for `pool_size`, `max_overflow` (SQLAlchemy), `connectionLimit` (MySQL2/pg), `SetMaxOpenConns` (Go database/sql).
**Why it matters:** default pool sizes under load → connection exhaustion → cascading failure.

### CONC-2: Rate limiting on public endpoints
**Check:** verify rate limiting middleware exists on at least the auth endpoints (login, register, password reset). Look for `slowapi` / `fastapi-limiter` (Python), `express-rate-limit` (Node), custom middleware with Redis counters.
**Why it matters:** without rate limiting, brute-force attacks on auth are trivial.

---

## Reporting format

Use the same format as `/review` so downstream skills can parse the output. See `skills/review/references/review-checklist.md` for the exact structure.

The status enum is identical:
- `BLOCKED` — at least one Critical issue
- `PASSED_WITH_WARNINGS` — at least one Important issue
- `PASSED` — all Critical and Important pass
