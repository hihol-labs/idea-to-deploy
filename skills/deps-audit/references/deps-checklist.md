# Dependency Audit Checklist (binary, deterministic)

> **Shared definitions:** Gate status enum, report format, secret detection patterns, and .env checks are defined in [`skills/_shared/helpers.md`](../../_shared/helpers.md). This file uses those definitions — do not re-declare them here.

> Same tier semantics as `/review` and `/security-audit`. Any Critical failure → status `BLOCKED`. Any Important failure → `PASSED_WITH_WARNINGS`. All pass → `PASSED`.

## Tier 1: Critical (must all pass)

Deal-breakers. `/deps-audit` returns `BLOCKED` on any failure.

### CVE-C1. No Critical-severity CVEs in direct dependencies
**Criterion:** OSV.dev / GHSA returns zero advisories with `database_specific.severity` = `CRITICAL` (or CVSS ≥ 9.0) for any direct dep.
**Data sources:** OSV.dev batch API, GitHub Advisory Database.
**Action on fail:** upgrade to the advisory's `fixed_in` version or apply vendor patch.

### CVE-C2. No High-severity CVEs with known exploits in direct dependencies
**Criterion:** OSV.dev / GHSA returns zero advisories with `CVSS ≥ 7.0` AND `cisa_kev: true` OR `exploit_maturity: high` for any direct dep.
**Rationale:** high-severity-with-exploit is functionally equivalent to Critical — it's being actively used.
**Action on fail:** upgrade immediately.

### YANK-C1. No yanked or deleted packages
**Criterion:** every `(name, version)` tuple resolves on the registry (npm registry, PyPI, crates.io, etc.). `404 Not Found` or `"yanked": true` → fail.
**Rationale:** yanked packages indicate maintainer-declared unsafety (e.g., `event-stream` supply-chain attack, `colors.js` sabotage).
**Action on fail:** pin to the latest non-yanked version or replace the dep.

### LIC-C1. No forbidden-license direct dependencies
**Criterion:** if project is closed-source or proprietary — no `GPL-*`, `AGPL-*`, `SSPL-*`, `BUSL-*` in direct deps. If project is SaaS — no `AGPL-*`, `SSPL-*`, `BUSL-*`.
**Reference matrix:** see `license-matrix.md` if added; otherwise use the SPDX compatibility table in the skill body.
**Action on fail:** replace the dep with a permissive-license alternative.

### MAL-C1. No known-malicious packages
**Criterion:** package name does NOT match any entry in the typosquat lists (PEP 541 / npm security advisories) and does NOT appear in the GHSA "malware" category for its ecosystem.
**Rationale:** typosquats (`reqeusts` vs `requests`, `electron-native-notify` vs `electron-notify`) are common supply-chain attack vectors.
**Action on fail:** remove immediately, audit the environment for signs of execution (cached builds, CI runs).

### ABANDON-C1. No direct dep unmaintained for > 5 years
**Criterion:** registry metadata `time.modified` (npm) / `urls[0].upload_time` (PyPI) / equivalent > 5 years before today, AND there's no explicit "feature-complete" marker in `.deps-audit-ignore`.
**Rationale:** 5-year silence on a dep that's still pulling security fixes downstream is a de-facto CVE delivery mechanism.
**Action on fail:** migrate off the dep.

---

## Tier 2: Important (warn but pass)

Quality issues that should be fixed but don't block proceeding.

### CVE-I1. No Medium-severity CVEs in direct dependencies
**Criterion:** zero advisories with `4.0 ≤ CVSS < 7.0` for any direct dep.
**Action on fail:** schedule upgrade in the next sprint; warn.

### CVE-I2. No High-severity CVEs in transitive dependencies reachable from direct deps
**Criterion:** OSV.dev returns zero `CVSS ≥ 7.0` advisories for transitive deps that are actually called by the project (not just present in the lockfile).
**Rationale:** not all transitives are executed — be pragmatic.
**Action on fail:** check if a direct-dep bump pulls in the patched transitive; if not, use an override.

### LOCK-I1. Lockfile exists
**Criterion:** project has a lockfile for every declared ecosystem (package-lock.json, poetry.lock, Cargo.lock, etc.). Manifest-only → fail.
**Rationale:** without a lockfile, audit results are best-effort on declared ranges, not actual installed versions.
**Action on fail:** run `npm install` / `poetry lock` / `cargo generate-lockfile` / `go mod download`.

### ABANDON-I1. No direct dep unmaintained for > 2 years
**Criterion:** registry last-modified > 2 years AND no explicit "feature-complete" justification in `.deps-audit-ignore`.
**Action on fail:** evaluate alternatives; if dep is feature-complete, document in `.deps-audit-ignore`.

### LIC-I1. License compatibility for copyleft in distributed software
**Criterion:** if software is distributed (not SaaS), direct deps licensed under `LGPL-*`, `MPL-*`, `EPL-*` require either (a) dynamic linking only, (b) separate compilation, or (c) explicit legal review note in `LICENSE_NOTES.md`.
**Action on fail:** add the note or switch to permissive-license equivalent.

### LIC-I2. SPDX identifier present
**Criterion:** every direct dep declares a valid SPDX license identifier in its manifest (not `LicenseRef-*`, not empty, not "see LICENSE file").
**Rationale:** license scanning tools (FOSSA, ScanCode, tldrlegal) rely on SPDX.
**Action on fail:** for in-house / forked deps, add SPDX to the manifest.

### VER-I1. No direct dep > 1 major version behind latest stable
**Criterion:** for each direct dep, current major version vs latest stable on the registry — difference must be ≤ 1.
**Rationale:** > 1 major version behind often means missing security fixes AND a hard migration later.
**Action on fail:** schedule a migration story.

### DEP-I1. No dep with `engines` / Python version constraint incompatible with CI
**Criterion:** every dep's declared runtime version constraint overlaps with the project's declared version.
**Action on fail:** update project runtime or replace dep.

### DEP-I2. No duplicate transitive versions
**Criterion:** no single package name appears more than twice in the full dep tree with different versions.
**Rationale:** duplicate versions mean wasted bundle size (Node), wasted memory (Python), or subtle runtime bugs (two copies of a class fail `isinstance` checks).
**Action on fail:** use `npm dedupe` / `poetry update` / equivalent; may require manual resolution.

---

## Tier 3: Recommended (nice-to-have)

### VER-N1. No direct dep > 1 minor version behind latest stable
**Criterion:** minor version diff ≤ 1.
**Action on fail:** bump on next chore PR.

### CVE-N1. No Low-severity CVEs
**Criterion:** zero advisories with `CVSS < 4.0` for any direct dep.
**Action on fail:** note in report; fix opportunistically.

### DEP-N1. All direct deps have a recent release (< 12 months)
**Criterion:** last release within 12 months.
**Action on fail:** informational — may be a feature-complete package.

---

## Tier 4: Informational

Not scored, but included in reports for context:
- Total number of dependencies (direct vs transitive).
- Total lockfile size (bytes).
- Ecosystems present.
- Fraction of deps with SPDX identifiers.
- `.deps-audit-ignore` entries currently active.

---

## Reporting format

The skill MUST output in this exact format so `/kickstart` Phase 5 can parse it:

```markdown
## /deps-audit report

**Scope:** <path>
**Ecosystems:** <list>
**Total dependencies:** <N direct, M transitive>
**Data sources:** OSV.dev, GHSA, <native tool if used>

### Tier 1: Critical
- ✅ CVE-C1: No Critical CVEs in direct deps
- ❌ CVE-C2: High-severity CVE with known exploit
       → lodash@4.17.15 — CVE-2020-8203 (CVSS 7.4, CISA KEV)
       → upgrade to >=4.17.19
- ✅ YANK-C1: No yanked packages
- ✅ LIC-C1: No forbidden licenses
- ✅ MAL-C1: No typosquats or known malware
- ✅ ABANDON-C1: No 5+ year abandoned direct deps

### Tier 2: Important
- ⚠️ CVE-I1: 1 Medium-severity CVE
       → axios@0.21.0 — CVE-2021-3749 (CVSS 5.3) — upgrade to >=0.21.4
- ✅ CVE-I2: No reachable transitive Highs
- ✅ LOCK-I1: package-lock.json present
- ⚠️ ABANDON-I1: 1 dep > 2y abandoned
       → left-pad@1.3.0 — last release 2018-07
- ...

### Tier 3: Recommended
- ℹ️ VER-N1: 2 deps > 1 minor version behind

### Tier 4: Informational
- Total deps: 247 (42 direct, 205 transitive)
- SPDX coverage: 44/44 direct (100%)
- .deps-audit-ignore entries: 0

### Summary
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | 5 | 6 | ❌ BLOCKED |
| Important | 7 | 9 | ⚠️ |
| Recommended | 2 | 3 | ℹ️ |

**Final status:** BLOCKED (must fix CVE-C2 before deploy)
```
