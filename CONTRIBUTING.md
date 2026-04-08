# Contributing to idea-to-deploy

Thank you for your interest — this methodology grows through real use, and external contributions are welcome. The process is deliberately lightweight because the project is small, but there are a few non-negotiable rules that protect the quality bar this methodology exists to enforce.

**TL;DR — before opening a PR:**

```bash
python3 tests/meta_review.py --verbose
```

This must print `FINAL STATUS: PASSED` with 0 Critical and 0 Important failures. If it doesn't, fix the findings before submitting. CI will block the merge otherwise (see [`docs/CI.md`](docs/CI.md)).

---

## Ground rules

### 1. The `SKILL.md` body is canonical

Every skill's `## Trigger phrases` section is the **single source of truth** for what user input should invoke that skill. The regex in `hooks/check-skills.sh` must match every canonical phrase and route to the right skill. If there is drift between the two, the drift verifier (`tests/verify_triggers.py`, enforced by meta-review check M-C11) will catch it and block the commit.

**When adding or editing a skill:**
1. Update the `## Trigger phrases` section of `SKILL.md`
2. Update the corresponding regex in `hooks/check-skills.sh` to cover the new phrases
3. Run `python3 tests/verify_triggers.py` — must return 0 drift

### 2. Every new skill needs three things

If you're adding a new skill under `skills/<name>/`, the following must all exist **in the same PR**:

- **`skills/<name>/SKILL.md`** — with frontmatter (`name`, `description`, `license`, `allowed-tools`, `metadata.version`), body sections: `## Trigger phrases`, `## Recommended model`, `## Instructions`, at least 2 `## Examples`, `## Troubleshooting`.
- **`skills/<name>/references/`** — if your `SKILL.md` mentions `references/...` anywhere in the body, the folder must exist and contain the referenced file(s). The completeness hook will block the Write otherwise.
- **`hooks/check-skills.sh`** — a new `TRIGGERS` entry with Russian and English regex patterns matching every phrase from your `## Trigger phrases` section.
- **`tests/fixtures/fixture-*-<name>/`** — at least one regression fixture directory with `idea.md`, `expected-files.txt`, and `notes.md` covering the skill's main use case.

This is enforced by both the local `check-skill-completeness.sh` hook AND by the `/review --self` meta-rubric (checks M-C2, M-C3, M-C4). See `hooks/README.md` for details.

### 3. Run the meta-review before committing

```bash
python3 tests/meta_review.py --verbose
```

This runs all 11 Critical + 8 Important rubric checks including hook schema compliance (M-C10), trigger drift (M-C11), and per-skill structural integrity. Your PR will fail CI if this doesn't pass. If you want to iterate faster locally, install the enforcement hooks — see `hooks/README.md`.

### 4. SemVer applies

- **Patch (`X.Y.Z → X.Y.Z+1`)**: bug fixes in existing skills, hooks, or rubric without adding new behavior. No new skills, no new rubric checks.
- **Minor (`X.Y.Z → X.Y+1.0`)**: new skill, new rubric check, new hook, or new observable feature without breaking existing contracts.
- **Major (`X.Y.Z → X+1.0.0`)**: breaking changes to skill contracts, hook JSON schemas, or rubric semantics. Requires migration notes.

Bump `plugin.json`, both `README.md` / `README.ru.md` badges, and add a `CHANGELOG.md` entry in the same PR. The meta-review verifies version consistency (checks M-C5, M-C6).

---

## Reporting bugs

Open a GitHub issue using the bug report template (`.github/ISSUE_TEMPLATE/bug_report.md`). Please include:

- Claude Code version (`claude --version`)
- Plugin version (from `plugin.json` or the README badge)
- Which model was in use (Haiku / Sonnet / Opus and version)
- The exact prompt or command that triggered the bug
- The observed behavior and the expected behavior

If you can reproduce the bug with a minimal fixture added under `tests/fixtures/`, that accelerates the fix significantly.

## Proposing new skills

Open a GitHub issue using the feature request template and describe:

- **What the skill does** — one-line summary
- **When it should trigger** — example user phrases in Russian and English
- **What it reads and writes** — similar to the Skill Contracts table in `README.md`
- **Why it's not covered by an existing skill** — be specific; `/debug` + `/refactor` cover a lot of daily work

Maintainer will respond within 1–2 days on whether the skill fits the methodology's scope and how to proceed.

## Pull request checklist

Before clicking "Create pull request":

- [ ] `python3 tests/meta_review.py --verbose` prints `FINAL STATUS: PASSED`
- [ ] `python3 tests/verify_triggers.py` reports 0 drift
- [ ] `plugin.json` version bumped, both README badges match
- [ ] `CHANGELOG.md` has a new entry for your version
- [ ] If adding a new skill: `references/`, triggers, fixture all in the PR
- [ ] If changing a hook: the hook pipe-tests in `hooks/README.md` still work (run them manually)
- [ ] If changing the rubric: the new check is documented in `skills/review/references/meta-review-checklist.md` with binary criterion, failure modes, and action-on-fail guidance

## Code review

Maintainer reviews use the same binary rubric that `/review` uses on user projects. No subjective scoring. If a Critical check fails, the PR is blocked until fixed. Important warnings are discussed but do not block.

## License

By contributing, you agree that your contributions will be licensed under the repository's MIT license.
