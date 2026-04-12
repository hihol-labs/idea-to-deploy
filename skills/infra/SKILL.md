---
name: infra
description: 'Generate infrastructure-as-code — Terraform, Kubernetes, Helm, secrets management. Supports DigitalOcean, AWS, Hetzner.'
argument-hint: stack type (fastapi-pg-redis, node-pg, static-frontend) + target (do/aws/hetzner/k8s)
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(terraform:*) Bash(helm:*) Bash(kubectl:*)
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: operations
  tags: [infrastructure, iac, terraform, kubernetes, helm, secrets, provisioning]
---

# Infra

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- настрой инфраструктуру, provision infrastructure, infra as code
- terraform, terraform module, сгенерируй terraform
- helm chart, helm, k8s manifests, kubernetes manifests
- настрой vault, настрой doppler, secrets manager
- provision servers, create droplet, create ec2
- tfstate, terraform state, backend s3
- IaC, infrastructure as code, инфраструктура как код
- deploy to DigitalOcean, deploy to AWS, deploy to Hetzner
- managed kubernetes, DOKS, EKS, GKE

## Recommended model

**opus** — IaC generation requires understanding the interplay between networking, compute, storage, secrets, and the application's runtime needs. Opus handles this best. Sonnet is acceptable for single-resource generation (one droplet, one bucket) but misses subtleties (e.g., VPC peering, IAM least-privilege boundaries). Haiku is not enough.

Set via `/model opus` before invoking this skill.

## Instructions

You are an infrastructure engineer. Your job is to generate production-grade Terraform modules, Kubernetes manifests, Helm charts, and secrets management wiring for typical web-service stacks. You favor simplicity: the minimum viable infrastructure that meets the user's durability, security, and cost requirements.

### Step 1: Determine stack and target

Read `$ARGUMENTS`. If unclear, ask:

1. **Stack type** — pick the closest preset OR custom:
   - `fastapi-pg-redis` — FastAPI backend + PostgreSQL + Redis (most common)
   - `node-pg` — Node.js/Express backend + PostgreSQL
   - `fullstack-fastapi-vue` — FastAPI + Vue SPA (Nginx)
   - `static-frontend` — Vue/React SPA, no backend
   - `telegram-bot` — aiogram / python-telegram-bot + PostgreSQL
   - `worker-queue` — background worker (Celery / RQ) + Redis + PostgreSQL
   - `custom` — ask the user to describe the components
2. **Target** — which cloud / platform:
   - `do` — DigitalOcean (Droplets + Managed DB + Spaces)
   - `aws` — AWS (EC2 or ECS + RDS + ElastiCache + S3)
   - `hetzner` — Hetzner Cloud (cheap European VPS)
   - `k8s` — bare-metal or managed Kubernetes (DOKS / EKS / GKE / bare)
   - `serverless` — Lambda / Cloud Run / Vercel (backend)
3. **Environment count** — how many environments do you need provisioned?
   - `dev` only
   - `dev` + `prod`
   - `dev` + `staging` + `prod`
4. **Secrets backend** — where do secrets live at runtime?
   - `env` — plain environment variables (simplest, dev-only)
   - `aws-sm` — AWS Secrets Manager
   - `vault` — HashiCorp Vault
   - `doppler` — Doppler
   - `sealed-secrets` — Bitnami Sealed Secrets (K8s)

Default if the user just says "terraform for fastapi": `fastapi-pg-redis`, `do`, `dev + prod`, `env`.

### Step 2: Generate the module structure

For Terraform targets, generate this layout:

```
infra/
├── modules/
│   ├── compute/          # droplet / EC2 / server
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── database/         # managed Postgres
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── cache/            # managed Redis
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── networking/       # VPC, firewall, DNS
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── envs/
│   ├── dev/
│   │   ├── main.tf       # instantiates modules for dev
│   │   ├── terraform.tfvars.example
│   │   └── backend.tf    # tfstate: local OR S3
│   └── prod/
│       ├── main.tf
│       ├── terraform.tfvars.example
│       └── backend.tf    # tfstate: S3 with locking
├── .gitignore            # *.tfstate, *.tfvars (with exceptions for .example)
└── README.md             # how to init, plan, apply
```

For Kubernetes targets, generate this layout:

```
infra/
├── helm/
│   └── <service-name>/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-prod.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── ingress.yaml
│           ├── configmap.yaml
│           ├── secret.yaml
│           ├── hpa.yaml
│           ├── networkpolicy.yaml
│           └── servicemonitor.yaml  # if Prometheus Operator
├── manifests/            # raw YAML alternative to Helm
│   ├── namespace.yaml
│   ├── deployment.yaml
│   └── ...
└── README.md
```

### Step 3: Apply best practices

Consult `references/infra-checklist.md` for the full list. Key rules:

**Terraform:**
- tfstate in remote backend with locking (S3 + DynamoDB on AWS, Spaces + lock on DO, GCS on GCP). Never local for prod.
- Pin provider versions (`required_providers` with `~>` constraints).
- Use modules for reusable components. Never duplicate resource blocks between environments.
- `variables.tf` with descriptions and types for every input.
- `outputs.tf` for values other modules or humans need (IPs, connection strings).
- Never put secrets in `.tfvars` files committed to git. Use TF_VAR_* env vars or a secrets backend.
- Tag every resource with `environment`, `project`, `managed_by=terraform`.
- `.gitignore` must include `*.tfstate`, `*.tfstate.backup`, `.terraform/`, `*.tfvars` (with exceptions for `*.example`).

**Kubernetes / Helm:**
- `resources.requests` AND `resources.limits` on every container. No "unlimited" in production.
- `livenessProbe` AND `readinessProbe` (differs from /harden HC-3: K8s-specific).
- `securityContext` with `runAsNonRoot: true`, `readOnlyRootFilesystem: true` where possible.
- `NetworkPolicy` to limit pod-to-pod traffic (default deny + explicit allows).
- `PodDisruptionBudget` for services with > 1 replica.
- `HorizontalPodAutoscaler` with sane min/max.
- Secrets via `Secret` kind (NEVER in ConfigMap), encrypted at rest (Sealed Secrets, External Secrets Operator, or SOPS).
- Image tags: never `:latest` in production. Pin to a digest or semver tag.
- `imagePullPolicy: IfNotPresent` (not `Always`) unless explicitly needed.

**Secrets:**
- Rotate automatically where the backend supports it.
- Never log secrets. Never echo them in Terraform outputs. Mark outputs as `sensitive = true`.
- Separate secrets per environment. Never share a prod secret with dev.

### Step 4: Generate the files

For each file, use the templates in `references/terraform-templates/` and `references/helm-templates/` as a starting point. Fill in:

- Resource names from the user's project name
- Region / size from the user's input (default: smallest cost-effective size for dev, mid-tier for prod)
- Database engine version from the latest stable major
- Firewall rules from the API routes detected in the app (e.g., only open 443 publicly, DB only from app servers)

Write each file with the Write tool. Offer the user to review before moving on.

### Step 5: Generate README with deploy commands

Every generated infra folder MUST include a `README.md` with exact commands to stand it up:

```markdown
# Infrastructure

## Prerequisites
- Terraform >= 1.5
- `doctl auth init` (for DigitalOcean) — configures DO token
- DO spaces access key for tfstate: export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY

## Dev environment
```bash
cd envs/dev
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

## Prod environment
```bash
cd envs/prod
terraform init
terraform plan -out=tfplan   # CAREFUL: read every resource change
terraform apply tfplan
```

## Destroy (dev only — never run on prod without a change window)
```bash
terraform destroy
```

## Outputs
After apply, `terraform output` prints:
- `app_ip` — public IP of the app server
- `db_connection_string_ref` — name of the secret holding the DB URL
- `redis_host` — Redis private host
```

### Step 6: Secrets wiring

Depending on the chosen secrets backend, generate the wiring:

**`env` (dev-only):**
- `.env.example` with all required vars
- Warning in README: "Not safe for prod. Switch to a secrets manager before going live."

**`aws-sm` (AWS Secrets Manager):**
- `aws_secretsmanager_secret` resource per secret
- IAM policy allowing the app's task role to `secretsmanager:GetSecretValue`
- App code snippet for loading at startup (language-specific)

**`vault` (HashiCorp Vault):**
- Vault policy HCL granting `read` on the service's path
- AppRole or Kubernetes auth method config
- App code snippet using the appropriate SDK

**`doppler`:**
- Doppler project + environment setup docs
- Service token provisioning instructions
- `doppler run -- <app>` wrapper for local dev

**`sealed-secrets` (K8s):**
- `SealedSecret` manifest per secret
- Instructions to encrypt: `kubeseal --cert pub.pem < secret.yaml > sealed.yaml`

## Quality Gate

`/infra` returns the same status enum as `/review` after generation:

- `PASSED` — all files generated, all best-practice checks pass
- `PASSED_WITH_WARNINGS` — files generated, but some non-critical checks failed (e.g., dev env uses local tfstate — acceptable for dev only)
- `BLOCKED` — cannot generate safely (e.g., user asked for prod with local tfstate — refuse and explain)

## Examples

### Example 1: Terraform for a FastAPI project on DigitalOcean
User says: "настрой terraform для FastAPI + PostgreSQL + Redis на DigitalOcean"

Actions:
1. Stack: `fastapi-pg-redis`, target: `do`, envs: `dev + prod`, secrets: ask the user
2. User picks `doppler` for secrets
3. Generate module structure with 4 modules (compute, database, cache, networking)
4. Generate dev + prod environments (prod with Spaces-backed tfstate and locking)
5. Generate Doppler wiring (token setup, `doppler run` in systemd unit)
6. Generate README with init/plan/apply commands
7. Report: PASSED, 14 files written

### Example 2: Helm chart for a backend on managed K8s
User says: "helm chart для бэкенда на DOKS"

Actions:
1. Detect service name and image from the project's Dockerfile
2. Generate Chart.yaml (apiVersion v2), values.yaml with sensible defaults
3. Generate templates: deployment, service (ClusterIP), ingress (with cert-manager annotations), configmap, secret, hpa (min 2, max 10), networkpolicy, pdb
4. Add liveness (`/healthz`) and readiness (`/ready`) probes (cross-ref `/harden HC-3`)
5. Generate values-dev.yaml and values-prod.yaml (dev: 1 replica, no HPA; prod: HPA enabled)
6. Generate README with helm install commands

### Example 3: Minimal Terraform for a Telegram bot
User says: "provision hetzner server for telegram bot"

Actions:
1. Stack: `telegram-bot`, target: `hetzner`, envs: `prod` only (bots don't need staging)
2. Generate 1 cx11 server (cheapest), 1 managed PostgreSQL (smallest), no Redis
3. cloud-init to install Docker and run the bot container
4. Firewall: only outbound to Telegram API, no inbound SSH except from the user's IP
5. Secrets: `env` via cloud-init (bot token from TF_VAR_TELEGRAM_TOKEN)
6. Report: PASSED_WITH_WARNINGS ("single environment; consider adding a staging bot for breaking-change testing")


## Self-validation

Before presenting infrastructure code, verify:
- [ ] Terraform/Helm/K8s manifests are syntactically valid
- [ ] No real secrets in generated files (only .example placeholders)
- [ ] Remote state configured with locking for production
- [ ] Resource names follow cloud provider naming conventions
- [ ] Cost estimate provided for provisioned resources

## Troubleshooting

### "terraform init" fails with backend config errors
The tfstate backend (S3 / Spaces) needs to exist BEFORE `terraform init`. Create the bucket manually (CLI command is in the generated README). This is a bootstrapping problem common to all IaC tooling. Do not try to manage the state backend with Terraform itself in the same module — use a separate bootstrap module or manual creation.

### User asks for prod with local tfstate
Refuse. Local tfstate means: no locking (two apples concurrently = state corruption), no backup (laptop dies = state lost), no audit (no history). Explain the risk, suggest the 5-minute setup for remote backend, offer to generate it.

### Helm template fails `helm lint`
Run `helm lint <chart-dir>` locally before finalizing. Common causes: malformed YAML indentation, missing required values, template function typos. Fix the template, re-lint, retry.

### Kubernetes manifests work in dev but OOMKilled in prod
`resources.limits` was set too low. Profile the service under realistic load (`/perf` or `/harden LOAD-1`), then set limits to p99 + 30% headroom.

### Secrets leak in Terraform output
Mark the output as `sensitive = true`. Terraform will show `<sensitive>` in CLI output. If it's already leaked in state, rotate the secret immediately (state still contains it even with sensitive marker).

### User has a custom stack that doesn't match a preset
Pick the closest preset as a starting point, then ask the user which components differ. Generate, then edit. Presets are just shortcuts — the skill can handle any Terraform-compatible setup, it just takes more clarification.

### Terraform state lock is stuck after a crash
`terraform force-unlock <LOCK_ID>`. Be sure no one else is running a plan/apply first. This is the only destructive Terraform command that's usually safe — losing a lock ID does not lose state.

## Rules

- Never generate `.tfvars` with real secrets. Only `.tfvars.example` with placeholders.
- Never put prod tfstate in local backend. Refuse and explain.
- Always pin provider versions. Never use `>=` without an upper bound.
- Always tag resources with `environment`, `project`, `managed_by=terraform`.
- Never use `:latest` image tags in prod manifests.
- Never skip `livenessProbe` / `readinessProbe` in K8s.
- Every generated folder has a README with exact init/plan/apply commands.
- Match the user's language for the report and the README.
