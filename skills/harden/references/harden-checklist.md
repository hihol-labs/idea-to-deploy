# Production-Readiness Hardening Checklist (binary, deterministic)

> **Shared definitions:** Gate status enum, report format, secret detection patterns, and .env checks are defined in [`skills/_shared/helpers.md`](../../_shared/helpers.md). This file uses those definitions — do not re-declare them here.

> Same tier semantics as `/review` and `/security-audit`. Any Critical failure → status `BLOCKED`. Any Important failure → `PASSED_WITH_WARNINGS`. All pass → `PASSED`.

## Tier 1: Critical (must all pass before production deploy)

### HC-1. Health check endpoint exists and returns 200
**Criterion:** at least one of `/healthz`, `/health`, `/api/health`, `/status/health` exists and returns HTTP 200 on a happy path.
**How to verify:** `curl -sf $SERVICE_URL/healthz` → exit 0.
**Generated artifact on fail:** FastAPI / Express / Gin / net/http health route in the project's primary router file.

### HC-2. Health check includes dependency liveness
**Criterion:** the health route performs at least one round-trip to each declared infra dependency (DB, Redis, external API). Not just `return {"ok": true}`.
**How to verify:** read the handler source — must contain at least one `execute("SELECT 1")` / `ping()` / equivalent per declared dep.
**Generated artifact on fail:** extended health route with `db.execute("SELECT 1")` and `redis.ping()` sections.

### HC-3. Liveness and readiness separated (K8s only)
**Criterion:** if `kind: Deployment` exists in the project, both `livenessProbe` and `readinessProbe` are configured and point to different handlers (`/livez` vs `/readyz`) OR an explicit comment justifies using a single endpoint.
**Rationale:** liveness failures restart the pod, readiness failures remove from service — they should react differently (DB outage should affect readiness, not restart the pod).
**N/A path:** non-K8s deployments auto-pass with a "not applicable" note.

### SH-1. Graceful shutdown on SIGTERM
**Criterion:** the service has a signal handler (language-specific) that on SIGTERM: stops accepting new requests, waits for in-flight requests to finish (with timeout, typically 30s), closes DB pool, closes Redis, flushes logs, then exits.
**How to verify:** grep for one of: `lifespan` context (FastAPI), `signal.signal` (Python), `signal.Notify` (Go), `process.on('SIGTERM')` (Node), equivalent in other stacks.
**Generated artifact on fail:** language-specific graceful shutdown block inserted into `main.py` / `index.js` / `main.go`.

### SEC-1. Secrets loaded from env, not source
**Criterion:** no hardcoded secrets in source (delegates to `/security-audit` rubric — same regex). Secrets come from `process.env.*` / `os.getenv` / `os.Getenv` / equivalent.
**Delegation:** if `/security-audit` already ran and passed `Tier 1 SECRET-*`, this check inherits pass. Do NOT re-implement.

### LOG-1. Structured JSON logs
**Criterion:** logs are emitted as JSON lines (one object per line). No `print()`, no `console.log`, no `fmt.Println` in production code paths (test/CLI code allowed).
**How to verify:** grep production source files for disallowed calls. Must return zero matches OR every match is in a file under `tests/`, `scripts/`, `cli/`.
**Generated artifact on fail:** migration to `structlog` (Python) / `pino` (Node) / `zap` (Go) / `slog` (Go ≥1.21) with a base logger configured at startup.

### LOG-2. Correlation IDs in log records
**Criterion:** logs include `request_id` (and `trace_id` if OpenTelemetry is used). Detect by reading the logging middleware for a call to `logger.bind(request_id=...)` or equivalent, and by checking that at least one log line in the test output carries the field.
**Generated artifact on fail:** middleware that creates a UUID4 on request start, binds it to the logger context, clears on request end.

### BACK-1. Backup strategy documented and automated
**Criterion:** at least one of the following is true:
1. Managed database service is in use (RDS, CloudSQL, Supabase, Neon, PlanetScale, etc.) AND `docs/BACKUP.md` documents the retention period (> 7 days) and restore procedure.
2. `cron` / systemd timer / k8s CronJob performs `pg_dump` / `mysqldump` / equivalent on a schedule AND uploads to S3 / Spaces / GCS AND retention is enforced (at least 7 days).
3. WAL archiving / streaming replication is configured with a documented PITR procedure.
**Generated artifact on fail:** `docs/BACKUP.md` template populated with actual service details, plus a `CronJob` / `cron` entry if managed service is not in use.

---

## Tier 2: Important (warn but pass)

### RL-1. Rate limiting on public endpoints
**Criterion:** at least one of the following is true for each public POST endpoint:
1. Middleware enforces per-IP rate limit (e.g., `slowapi`, `express-rate-limit`, `golang.org/x/time/rate`).
2. Upstream proxy (nginx, Cloudflare, ALB) enforces rate limit — documented in `docs/ARCHITECTURE.md` or equivalent.
3. Endpoint is protected by authentication AND has per-user rate limiting.
**Rationale:** public endpoints without rate limiting are a brute-force / DoS / cost-amplification risk.

### MON-1. `/metrics` endpoint or APM integration
**Criterion:** one of:
1. `/metrics` endpoint exposes Prometheus format (detected by reading the route's content-type: `text/plain; version=0.0.4`).
2. APM SDK is initialized at startup (Datadog `ddtrace`, New Relic, Sentry Performance, etc.).
**Generated artifact on fail:** `prometheus_client` (Python) / `prom-client` (Node) / `prometheus/client_golang` (Go) with Counter + Histogram for HTTP requests.

### MON-2. Dashboards defined
**Criterion:** `infra/` or `monitoring/` contains at least one Grafana dashboard JSON (or Datadog equivalent) with panels for: RPS, p50/p95/p99 latency, error rate, CPU, memory.
**Generated artifact on fail:** `infra/monitoring/dashboard.json` with the 5 panels above wired to the service's metric names.

### ALERT-1. At least 3 alerts defined
**Criterion:** `infra/monitoring/alerts.yaml` (Prometheus AlertManager) or equivalent contains at least 3 alert rules: `HighErrorRate`, `HighLatencyP95`, `ServiceDown`.

### LOAD-1. Load test scaffolding exists
**Criterion:** `loadtest/` directory contains at least one k6 script (`.js`), locust file (`locustfile.py`), or vegeta target file.

### LOAD-2. Load test has been run at least once
**Criterion:** `loadtest/results/` contains at least one run output OR `docs/LOAD_TEST_RESULTS.md` documents baseline numbers.

### RUNBOOK-1. Runbook exists
**Criterion:** `docs/RUNBOOK.md` exists and contains sections: Overview, Dependencies, Restart, Rollback, Common Incidents, Escalation.
**Generated artifact on fail:** runbook from `runbook-template.md` auto-filled with facts extracted from the codebase.

### ERR-1. Error responses do not leak stack traces
**Criterion:** for each error handler, the response body does NOT contain the exception's repr / stringified form with file paths. FastAPI default behavior passes; custom handlers must explicitly filter.

### TIMEOUT-1. Outgoing HTTP calls have explicit timeouts
**Criterion:** every `httpx.Client`, `requests.Session`, `fetch`, `http.Client` construction passes an explicit `timeout` parameter (not default None / infinity). Grep source for these constructors and verify.

### TIMEOUT-2. Database queries have statement timeout
**Criterion:** DB connection string or session config sets a statement timeout (e.g., PostgreSQL `statement_timeout=30s` in connect string, SQLAlchemy `connect_args={"options": "-c statement_timeout=30000"}`).

---

## Tier 3: Nice-to-have

### CHAOS-1. Chaos testing plan documented
**Criterion:** `docs/CHAOS.md` or `loadtest/chaos/` documents at least one chaos scenario (kill pod, drop DB connection, drop Redis).

### CANARY-1. Canary / blue-green deployment strategy
**Criterion:** CI/CD config (`.github/workflows/*`, `.gitlab-ci.yml`) or `infra/` contains a canary strategy (weighted rollout, blue-green swap, or feature flag gated).

### SLO-1. SLOs / SLIs documented
**Criterion:** `docs/SLO.md` documents at least 1 SLI with a target SLO.

### ONCALL-1. On-call rotation documented
**Criterion:** `docs/ONCALL.md` documents escalation order and contact methods.

---

## Reporting format

Same as `/review` and `/security-audit`. Emit sections for each tier, list each check with ✅/❌/⚠️/ℹ️ and a `→ reason` annotation, then the summary table and final status.

**Artifact generation is interactive:** for each failing Critical check, `/harden` offers the user to generate the artifact. The user approves per-item. The skill re-runs only the previously-failing checks after apply — never the whole rubric.
