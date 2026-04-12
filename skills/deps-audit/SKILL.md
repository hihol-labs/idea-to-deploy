---
name: deps-audit
description: 'Audit third-party dependencies for known CVEs, license issues, and abandoned packages. Read-only report with severity tiers.'
argument-hint: manifest file, directory, or "all" for full project
license: MIT
allowed-tools: Read Glob Grep Bash(npm:*) Bash(pip:*) Bash(cargo:*) Bash(go:*)
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: quality-assurance
  tags: [dependencies, audit, cve, supply-chain, licenses, osv]
---

# Deps Audit

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- проверь зависимости, проверь пакеты, audit deps
- dependency audit, dep audit, check dependencies
- найди уязвимые пакеты, найди CVE в зависимостях
- проверь лицензии, license check, license audit
- lockfile audit, package-lock.json audit, requirements.txt audit
- supply chain audit, проверка цепочки поставок
- abandoned packages, заброшенные пакеты, устаревшие зависимости
- OSV, GHSA, GitHub Advisory, vulnerability scan dependencies

## Recommended model

**sonnet** — Parsing manifests and correlating with advisory databases is mechanical. Sonnet is sufficient and cost-effective. Opus does not meaningfully improve accuracy here. Haiku is not enough — false negatives on CVE matching are dangerous.

Set via `/model sonnet` before invoking this skill.

## Instructions

You are a supply-chain auditor. Your job is to find known-vulnerable, license-incompatible, or abandoned dependencies BEFORE they ship. Read-only — you propose upgrades, you do not apply them.

### Step 1: Determine scope and detect manifests

If `$ARGUMENTS` specifies a file or directory, scope to that. Otherwise scan the whole project.

Look for these manifest files (in order of preference — lockfile beats manifest):

| Ecosystem | Lockfile (preferred) | Manifest |
|---|---|---|
| Node.js | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` | `package.json` |
| Python | `poetry.lock`, `Pipfile.lock`, `requirements.txt` (pinned) | `pyproject.toml`, `requirements.txt` |
| Go | `go.sum` | `go.mod` |
| Rust | `Cargo.lock` | `Cargo.toml` |
| Ruby | `Gemfile.lock` | `Gemfile` |
| Java | — | `pom.xml`, `build.gradle` |
| PHP | `composer.lock` | `composer.json` |

Report which ecosystems were found. If multiple, audit each separately.

### Step 2: Extract the dependency graph

From the lockfile (preferred) or manifest, build a list of `(name, version, direct|transitive)` tuples.

**Prefer lockfiles** — they pin exact versions including transitive deps. Manifests only show direct deps with ranges, which makes CVE matching unreliable.

If only a manifest exists (no lockfile), flag this as an **Important** finding: "No lockfile — audit results are best-effort based on declared ranges. Run `npm install` / `poetry lock` / `cargo generate-lockfile` to produce one."

### Step 3: Run the checklist

Consult `references/deps-checklist.md` for the full set of checks. The checklist has 4 tiers:

- **Tier 1 — Critical** (block before deploy): known CVE with `Critical` or `High` CVSS, package yanked/deleted from registry, license forbids redistribution (GPL in closed-source, SSPL in SaaS), known-malicious package (typosquat, event-stream style supply-chain attack)
- **Tier 2 — Important** (must be addressed): known CVE with `Medium` CVSS, GPL/LGPL in a project that claims MIT, package with no release in > 2 years (abandoned), transitive dependency with direct-dep bypass available
- **Tier 3 — Recommended**: CVE with `Low` CVSS, copyleft with weak obligations (MPL, EPL) without legal review, major version > 1 behind latest
- **Tier 4 — Informational**: minor version behind, no SPDX license identifier declared, pre-1.0 package in production

### Step 4: Query the advisory database

For each `(name, version)` tuple, check these sources in order:

1. **OSV.dev** — `https://api.osv.dev/v1/query` (POST body: `{"package":{"name":"<name>","ecosystem":"<eco>"},"version":"<ver>"}`) — unified API, covers npm/PyPI/Go/crates/Maven/RubyGems
2. **GitHub Advisory Database** — `https://api.github.com/advisories?ecosystem=<eco>&affects=<name>@<ver>` — sometimes has advisories before OSV picks them up
3. **Ecosystem native** (fallback only):
   - Node: `npm audit --json`
   - Python: `pip-audit` if installed
   - Rust: `cargo audit` if installed
   - Go: `govulncheck` if installed

If no network access is available (sandboxed environment), fall back to the native tools only and note "OSV/GHSA skipped — no network" in the report.

**Rate limiting:** batch queries where the API supports it. OSV.dev accepts batch POSTs — use them. Do not hammer `api.github.com` without a token.

### Step 5: License check

For each direct dependency, extract the declared SPDX license identifier from the manifest. Compare against the project's own license (from `LICENSE` file or `package.json#license`).

License compatibility matrix (common cases):

| Project license | Compatible deps |
|---|---|
| MIT / BSD / Apache-2.0 | MIT, BSD, Apache-2.0, MPL-2.0, ISC |
| GPL-3.0 | Anything GPL-compatible (NOT Apache-2.0 in GPL-2.0) |
| Proprietary / closed source | MIT, BSD, Apache-2.0, ISC — **NOT** GPL, AGPL, SSPL |
| SaaS (not distributed) | All except SSPL, AGPL, BUSL |

Flag any incompatibility as Tier 1 (Critical) or Tier 2 (Important) depending on whether the dep is direct or transitive.

### Step 6: Abandoned package detection

For each direct dependency, check the "last release date":
- Node: `npm view <name> time.modified` or parse registry JSON
- Python: PyPI JSON API `https://pypi.org/pypi/<name>/json` → `urls[0].upload_time`
- Go: `go list -m -json <name>@latest` → `Time`
- Rust: `https://crates.io/api/v1/crates/<name>` → `updated_at`

Thresholds:
- Last release > 2 years ago → **Important** (abandoned)
- Last release > 5 years ago → **Critical** (unmaintained, almost certainly has unfixed CVEs)
- Repo URL returns 404 → **Critical** (deleted / yanked)

### Step 7: Generate report

Use this exact format (parseable by `/review` and other downstream skills — same enum as `/security-audit`):

```markdown
## /deps-audit report

**Scope:** <path or "all project">
**Ecosystems found:** Node.js (package-lock.json), Python (poetry.lock)
**Total dependencies:** 247 (42 direct, 205 transitive)
**Data sources:** OSV.dev, GHSA, native `npm audit`

### Tier 1: Critical
- ❌ CVE-1: `lodash@4.17.15` — CVE-2020-8203 (High CVSS 7.4, prototype pollution)
       → upgrade to `>=4.17.19`
- ❌ LIC-1: `some-gpl-lib@1.0.0` — GPL-3.0 in a proprietary project
       → replace with MIT alternative: `alternative-lib`
- ✅ YANK-1: No yanked packages

### Tier 2: Important
- ⚠️ CVE-2: `axios@0.21.0` — CVE-2021-3749 (Medium CVSS 5.3)
       → upgrade to `>=0.21.4`
- ⚠️ ABANDON-1: `left-pad@1.3.0` — last release 2018-07-03 (>5y ago)
       → consider replacing with built-in `String.prototype.padStart`

### Tier 3: Recommended
- ℹ️ VER-1: `react@17.0.2` — 2 major versions behind (latest 19.x)
- ℹ️ VER-2: `webpack@4.46.0` — 1 major version behind (latest 5.x)

### Tier 4: Informational
- ℹ️ SPDX-1: 3 direct deps missing SPDX identifier (`custom-utils`, `in-house-lib`, `my-fork`)

### Summary
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | 1 | 3 | ❌ BLOCKED |
| Important | 0 | 2 | ⚠️ |
| Recommended | 0 | 2 | ℹ️ |
| Informational | 0 | 1 | ℹ️ |

**Final status:** BLOCKED (must fix CVE-1 and LIC-1 before deploy)
```

### Step 8: Offer upgrade guidance

For each Critical or Important finding, propose an exact upgrade command WITHOUT running it:

```markdown
**CVE-1: `lodash@4.17.15` — CVE-2020-8203**

Suggested fix:
\`\`\`bash
npm install lodash@^4.17.21
npm audit fix  # verify
\`\`\`

Apply this fix? [yes/no]
```

If user says yes, ask them to invoke `/migrate` style flow or use Bash directly — `/deps-audit` is read-only by design. This separation prevents the auditor from also being the fixer.

## Quality Gate

This skill returns the same status enum as `/review` and `/security-audit`:

- `BLOCKED` → at least one Critical issue
- `PASSED_WITH_WARNINGS` → no Critical, at least one Important
- `PASSED` → all Critical and Important pass

`/kickstart` Phase 5 (Deployment) should call `/deps-audit` alongside `/security-audit` and refuse to deploy on `BLOCKED` from either.

## Examples

### Example 1: Node.js project CVE sweep
User says: "проверь зависимости в проекте"

Actions:
1. Detect `package-lock.json` → Node.js ecosystem
2. Extract 247 `(name, version)` tuples
3. Batch POST to OSV.dev API
4. Cross-check with `npm audit --json` if offline
5. License check against `package.json#license: "MIT"`
6. Abandoned-package check via `npm view ... time.modified`
7. Generate report

Result: 2 Critical (lodash CVE, GPL dependency), 1 Important (axios CVE), status BLOCKED.

### Example 2: Multi-ecosystem monorepo
User says: "dependency audit all"

Actions:
1. Detect `package.json`, `pyproject.toml`, `go.mod` — 3 ecosystems
2. Run audit per ecosystem in parallel (OSV.dev supports batch)
3. Aggregate results per ecosystem
4. Report with separate sections per ecosystem

Result: 1 Critical in Python (old Django CVE), clean on Node and Go. Status BLOCKED until Django upgrade.

### Example 3: License audit before open-sourcing
User says: "проверь лицензии, мы открываем код под Apache-2.0"

Actions:
1. Parse all direct deps
2. Extract SPDX from each
3. Compare against Apache-2.0 compatibility matrix
4. Flag any GPL, AGPL, SSPL, BUSL as incompatible
5. Suggest MIT/BSD/Apache alternatives for each

Result: 3 Important findings (2 GPL deps, 1 SSPL). Alternatives suggested.


## Self-validation

Before presenting audit report, verify:
- [ ] All dependency files scanned (package.json, requirements.txt, go.mod, etc.)
- [ ] Each CVE finding includes advisory ID and severity
- [ ] License check covers all direct dependencies
- [ ] Abandoned package check uses last publish date + maintainer activity
- [ ] Report is READ-ONLY — no packages installed or updated

## Troubleshooting

### "No lockfile found"
The project has a manifest but no lockfile. Audit results will be best-effort. Recommend: `npm install` / `poetry lock` / `cargo generate-lockfile` / `go mod download` to create one, then re-run `/deps-audit`.

### OSV.dev rate limit / timeout
OSV batch API accepts up to 1000 queries per request. If still rate-limited, fall back to the native tool (`npm audit`, `pip-audit`, `cargo audit`, `govulncheck`) and note the fallback in the report.

### False positive on a CVE that's already patched
If you're sure the CVE does not apply (e.g., you use a backport or a vendored patch), document it in a `.deps-audit-ignore` file at the project root with format `<package>@<version> <CVE-ID> <reason>`. The skill reads this file on startup and marks matched findings as "ignored (justification in .deps-audit-ignore)".

### Abandoned-package check is wrong for a "finished" library
Some mature libs legitimately don't need updates (e.g., `lodash.debounce`). The skill flags >2y as Important, not Critical — downgrade manually if the lib is feature-complete. Add a note in `.deps-audit-ignore` so the next run skips it.

### Cannot reach api.osv.dev
Sandboxed environment without network. Fall back to `npm audit --json` / `pip-audit --format json` / `cargo audit --json` / `govulncheck -json`. Report will say "OSV/GHSA skipped — no network".

### Transitive dep has a CVE but direct dep is pinned
Check if a newer version of the direct dep bundles a patched transitive. If yes, suggest upgrading the direct dep. If no, suggest an override (`npm overrides`, `poetry` `[tool.poetry.dependencies]`, Cargo `[patch.crates-io]`).

## Rules

- READ-ONLY. Never run `npm install`, `pip install`, `cargo update`, or any dependency mutation. Suggest, don't execute.
- Use the same status enum as `/review` and `/security-audit` so downstream skills can chain reliably.
- Prefer lockfiles over manifests. Flag "no lockfile" as Important.
- Batch API calls. Do not query OSV.dev 247 times in a row when one batch call works.
- Match the language of the user's request for the report.
- Respect `.deps-audit-ignore` — don't re-flag something the user has explicitly accepted the risk on.
- Never auto-upgrade. The user decides when to merge an upgrade, based on changelogs.
