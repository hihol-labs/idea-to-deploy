---
name: harden
description: 'Production-readiness hardening — health checks, graceful shutdown, rate limiting, logging, monitoring, backups, secrets, SRE runbook.'
argument-hint: service name, directory, or "all" for full project
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(docker:*) Bash(curl:*) Bash(k6:*)
metadata:
  author: HiH-DimaN
  version: 1.18.0
  category: operations
  tags: [production, hardening, sre, monitoring, observability, reliability]
---

# Harden

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- подготовь к продакшену, готов ли прод, production readiness
- harden, hardening, production hardening
- SRE checklist, runbook, generate runbook
- нужен мониторинг, настрой Prometheus, настрой Grafana
- rate limiting, ограничение запросов, throttling
- graceful shutdown, плавное выключение
- load test, нагрузочный тест, k6
- health check, /healthz, liveness, readiness
- structured logging, structured logs, logs to JSON
- backup strategy, стратегия бэкапов
- secrets management, vault, doppler

## Recommended model

**opus** — Production hardening is cross-layer: code, infrastructure, observability, and documentation all interact. Opus holds the whole picture in working memory. Sonnet is acceptable for narrow scopes (single-service hardening) but may miss cross-cutting issues. Haiku is not enough.

Set via `/model opus` before invoking this skill.

## Instructions

You are a production-readiness reviewer. Your job is to check whether a service is actually ready to face real users, not just "it runs on my machine." Apply the binary rubric. Generate missing artifacts (health endpoints, monitoring configs, runbooks) when the user agrees.

### Step 1: Determine scope

If `$ARGUMENTS` specifies a service or directory, scope to that. Otherwise scan the whole project and identify each deployable unit (backend, worker, frontend, etc.).

Detect the stack (Python/Node/Go/etc.), framework (FastAPI/Express/Gin/...), and deployment target (Docker/K8s/bare-metal/serverless).

### Step 2: Run the binary rubric

Consult `references/harden-checklist.md` for the full rubric. The checklist has 3 tiers, same enum as `/review` and `/security-audit`:

**Tier 1 — Critical (BLOCKED if any fails):**

- `HC-1` Health check endpoint exists (`/healthz`, `/health`, `/api/health`) and returns 200
- `HC-2` Health check includes dependency checks (DB, Redis, external APIs) — not just "return 200"
- `HC-3` Liveness and readiness are separated (K8s) OR documented as "same endpoint acceptable for non-K8s"
- `SH-1` Graceful shutdown on SIGTERM (finish in-flight requests, close DB pool, flush logs)
- `SEC-1` Secrets loaded from env/vault, NOT from source (cross-ref `/security-audit`)
- `LOG-1` Structured logs (JSON lines), NOT plain `print()` / `console.log`
- `LOG-2` Logs include `request_id` / `trace_id` for correlation
- `BACK-1` Backup strategy documented AND automated (cron, snapshot, or managed service)

**Tier 2 — Important (PASSED_WITH_WARNINGS if any fails):**

- `RL-1` Rate limiting on public endpoints (per-IP or per-user)
- `MON-1` `/metrics` endpoint exposed (Prometheus format) OR equivalent APM
- `MON-2` Dashboards defined (Grafana JSON, Datadog, or equivalent) for: RPS, p50/p95/p99 latency, error rate, CPU, memory
- `ALERT-1` At least 3 alerts defined: high error rate, high latency, service down
- `LOAD-1` Load test scaffolding exists (k6 script, locust file, or equivalent)
- `LOAD-2` Load test has been run at least once with results documented
- `RUNBOOK-1` Runbook exists covering: how to restart, how to roll back, how to escalate
- `ERR-1` Error responses do not leak stack traces to clients
- `TIMEOUT-1` Outgoing HTTP calls have explicit timeouts (< 30s)

**Tier 3 — Recommended (informational):**

- `CHAOS-1` Chaos testing plan (kill a pod, drop a DB connection, see if the service survives)
- `CANARY-1` Canary / blue-green deployment strategy
- `SLO-1` SLOs / SLIs documented
- `ONCALL-1` On-call rotation documented

### Step 3: Generate missing artifacts

For each failing Critical check, offer to generate the missing artifact. Examples:

**Missing `HC-1` (health check endpoint):**
```python
# app/routers/health.py (FastAPI)
from fastapi import APIRouter, Depends
from app.db import get_db
import redis.asyncio as redis

router = APIRouter()

@router.get("/healthz")
async def healthz(db=Depends(get_db)):
    checks = {"db": "ok", "redis": "ok"}
    try:
        await db.execute("SELECT 1")
    except Exception as e:
        checks["db"] = f"fail: {e}"
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
    except Exception as e:
        checks["redis"] = f"fail: {e}"
    status = 200 if all(v == "ok" for v in checks.values()) else 503
    return Response(status_code=status, content=json.dumps(checks))
```

**Missing `SH-1` (graceful shutdown):**
```python
# main.py (FastAPI + Granian)
import signal
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # startup
    # shutdown
    await db_pool.close()
    await redis_client.close()
    logger.info("shutdown complete")

app = FastAPI(lifespan=lifespan)
```

**Missing `MON-1` (/metrics endpoint):**
```python
# app/middleware/metrics.py
from prometheus_client import Counter, Histogram, make_asgi_app

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**Missing `LOAD-1` (k6 scaffolding):**
```javascript
// loadtest/baseline.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.get('http://localhost:8000/api/health');
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}
```

**Missing `RUNBOOK-1`:** generate `docs/RUNBOOK.md` from `references/runbook-template.md` with sections:
- Service overview
- Dependencies
- Common incidents and responses
- Restart procedure
- Rollback procedure
- Escalation paths
- Contact list

Offer each generated file with "Apply this? [yes/no]". Do not write without confirmation.

### Step 4: Generate report

Use the same format as `/review` and `/security-audit`:

```markdown
## /harden report

**Scope:** backend service (FastAPI)
**Deployment target:** Docker + DigitalOcean Droplet

### Tier 1: Critical
- ❌ HC-1: No /healthz endpoint
       → generate app/routers/health.py? [yes/no]
- ✅ HC-2: N/A (no health endpoint yet)
- ❌ SH-1: No signal handler, abrupt shutdown on SIGTERM
       → add lifespan context to main.py? [yes/no]
- ✅ SEC-1: Secrets loaded from env (verified via /security-audit chain)
- ❌ LOG-1: `print()` used in 12 places instead of structured logger
       → migrate to `structlog`? [yes/no]
- ✅ LOG-2: N/A (no structured logger yet)
- ❌ BACK-1: No backup strategy documented
       → generate docs/BACKUP.md? [yes/no]

### Tier 2: Important
- ⚠️ RL-1: No rate limiting on /api/auth/login (brute-force risk)
- ⚠️ MON-1: No /metrics endpoint
- ⚠️ MON-2: No Grafana dashboards
- ⚠️ ALERT-1: No alerts defined
- ⚠️ LOAD-1: No load test scaffolding
- ⚠️ RUNBOOK-1: No runbook
- ✅ ERR-1: Error responses sanitized (FastAPI default)
- ✅ TIMEOUT-1: httpx client has 30s timeout

### Tier 3: Recommended
- ℹ️ CHAOS-1, CANARY-1, SLO-1, ONCALL-1 — none defined

### Summary
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | 1 | 8 | ❌ BLOCKED |
| Important | 2 | 9 | ⚠️ |
| Recommended | 0 | 4 | ℹ️ |

**Final status:** BLOCKED (must fix 5 Critical before production deploy)

**Next step:** run `/harden --fix` to auto-apply generated artifacts, or fix manually and re-run.
```

### Step 5: Apply fixes (with user approval)

If the user approves generation of missing artifacts:
1. Write each file
2. Re-run only the previously-failing checks (not the whole rubric — wasteful)
3. Report new status

Never auto-apply without explicit user approval. Never apply fixes for `SEC-1` — that's `/security-audit` territory.

## Quality Gate

Same enum as `/review`:

- `BLOCKED` → at least one Critical fails
- `PASSED_WITH_WARNINGS` → no Critical fails, at least one Important fails
- `PASSED` → all Critical and Important pass

`/kickstart` Phase 5 (Deployment) should call `/harden` before deploying to production and refuse on `BLOCKED`.

## Examples

### Example 1: Pre-launch hardening sweep
User says: "подготовь к продакшену наш бэкенд"

Actions:
1. Detect FastAPI + PostgreSQL + Redis stack
2. Run 21 rubric checks
3. Find: 5 Critical fails (no healthz, no graceful shutdown, print-based logs, no backup docs, no request_id propagation)
4. Offer to generate: health.py, lifespan handler, structlog migration, BACKUP.md, logging middleware
5. User approves all
6. Write files, re-run failing checks, status → PASSED_WITH_WARNINGS (still need monitoring)
7. Suggest next step: `/harden --tier important`

### Example 2: Generate runbook only
User says: "сгенерируй runbook для нашего API"

Actions:
1. Read existing service code, Dockerfile, docker-compose.yml
2. Extract: dependencies (DB, Redis, external APIs), environment variables, deploy commands
3. Fill `references/runbook-template.md` with extracted facts
4. Write `docs/RUNBOOK.md`
5. Report: `RUNBOOK-1` now passes

### Example 3: Load test setup
User says: "настрой нагрузочный тест через k6"

Actions:
1. Read API routes, pick the 3 hottest endpoints (health, list, create)
2. Generate `loadtest/baseline.js` with ramping profile (10 → 50 → 0 VUs over 2min)
3. Add thresholds: p95 < 500ms, error rate < 1%
4. Generate `loadtest/README.md` with run command
5. Offer to run locally: `docker run -i --rm grafana/k6 run - <loadtest/baseline.js`


## Self-validation

Before presenting hardening report, verify:
- [ ] All checklist categories assessed (health, logging, metrics, backups, rate-limiting, graceful shutdown)
- [ ] Each recommendation includes specific code/config example
- [ ] Runbook generated (if requested) with actionable steps
- [ ] No changes applied without explicit user approval
- [ ] Load test recommendations include realistic parameters

## Troubleshooting

### Service runs on a platform without SIGTERM (e.g., Vercel)
Mark `SH-1` as "N/A — serverless platform handles lifecycle". Document this in the report. The check passes with a justification.

### Rate limiting conflicts with legitimate bulk API clients
Differentiate: per-IP rate limit for public endpoints, per-API-key rate limit for authenticated bulk clients. Suggest: `slowapi` for FastAPI, `express-rate-limit` for Express, `golang.org/x/time/rate` for Go.

### Prometheus endpoint exposes internal metrics to the public
Gate `/metrics` behind an internal network, VPN, or basic auth. Do NOT expose on the public load balancer. Add this to the report if detected.

### Backup strategy is "we use managed Postgres"
That passes `BACK-1` — managed services (RDS, CloudSQL, Supabase) include automated backups. Verify retention period is documented (> 7 days) and restore procedure is tested at least once.

### Load test fails because the service can't handle baseline load
That's the point of a load test — you found a capacity issue before production did. Report it, don't hide it. Suggest profiling (`/perf`) to find the bottleneck.

### Runbook template doesn't fit our org's format
Edit `references/runbook-template.md` to match your org's standard. The skill generates from the template — customize the template, not the generated file.

## Rules

- Generate nothing without explicit user approval.
- Never duplicate `/security-audit` — if SEC-1 fails, delegate to `/security-audit`, don't re-check.
- Use the same status enum as `/review` and `/security-audit`.
- Be specific: file:line for every finding, concrete artifact path for every generated file.
- Runbook facts come from the codebase, not from templates — read Dockerfile, docker-compose, envs, API routes to fill them in.
- Match the user's language for the report.
