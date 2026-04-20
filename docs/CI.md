# CI — Server-side Gate 1 via GitHub Actions

Added in **v1.8.0**. Runs the meta-review rubric on every push to `main` and every pull request. This is the defense-in-depth layer below the local enforcement hooks — the last line before broken methodology changes land in `main`.

## What it does

The workflow `.github/workflows/meta-review.yml` executes two commands on every push and PR:

```bash
python3 tests/meta_review.py --verbose
python3 tests/verify_triggers.py
```

Both must exit 0. Any Critical failure (exit 1 from `meta_review.py` or non-zero from `verify_triggers.py`) fails the job, which then blocks the PR from being merged if branch protection is enabled (see below).

The workflow uses only Python 3.11 stdlib — no `pip install` step — because both scripts are intentionally zero-dependency. Typical runtime: 20–40 seconds.

## Why it exists

Locally, four hooks enforce the methodology's quality gates at commit time. But local hooks only protect the machine where they are installed. As soon as:

- A first external contributor submits a PR without local hooks set up,
- A second Claude session (different machine, different setup) starts committing,
- The maintainer force-pushes from an unprepared environment,

…the local enforcement is bypassed. CI closes that gap by running the same rubric server-side, where nobody can `--no-verify` their way around it.

The trigger for adding CI was **3 GitHub stars within 24h of publishing v1.7.0** — a traction signal that flipped the earlier cost/benefit calculation ("wait for first PR") because a first PR became a matter of days, not months. See `CHANGELOG.md [1.8.0]` for the full reasoning.

## Defense-in-depth layers

CI is the outermost of four layers. They are ordered from earliest feedback to latest:

| Layer | When | What it catches | Can be bypassed? |
|---|---|---|---|
| **1. `check-skills.sh`** (UserPromptSubmit) | Before Claude's first response to a prompt | Ambiguous prompts that should trigger a skill but weren't being routed | Soft reminder only — not a bypass concern |
| **2. `check-tool-skill.sh`** (PreToolUse) | Before every raw Bash/Edit/Write | Claude about to do ad-hoc work when a skill would fit | Soft reminder only — not a bypass concern |
| **3. Enforcement hooks** (PreToolUse) | Before Write/Edit on SKILL.md and before `git commit` | Incomplete skills (missing references/triggers/fixtures), incomplete commits (staged SKILL.md without supporting artifacts) | Only via documented `.methodology-self-extend-override` file |
| **4. CI (this workflow)** | On push to main and on every PR | Everything in the meta-rubric: all 11 Critical + 8 Important checks. Catches anything the local hooks missed OR scenarios where local hooks were never installed | Only by admin override of branch protection (leaves audit trail) |

If a contributor has no local hooks, layers 1–3 are silent and layer 4 is the only gate. If the maintainer has all four layers, the first Write that introduces drift is caught at layer 3, never reaching layer 4.

## Required setup — branch protection

The workflow **runs** automatically once merged to `main`, but to make it **blocking** (PRs cannot be merged until it passes), you must enable branch protection in the GitHub UI. This cannot be provisioned from code.

### Step-by-step

1. Open the repo on GitHub: `https://github.com/hihol-labs/idea-to-deploy`
2. Navigate: **Settings** → **Branches** → **Branch protection rules** → **Add rule** (or edit existing)
3. Set **Branch name pattern**: `main`
4. Enable: **Require a pull request before merging**
   - Optional but recommended: **Require approvals** = 1 (if the project grows beyond solo)
5. Enable: **Require status checks to pass before merging**
   - Check: **Require branches to be up to date before merging**
   - In the "Status checks that are required" search box, type `meta-review` and select `Gate 1 — meta-review rubric`
     - **Note:** this check will only appear in the search box AFTER the workflow has run at least once. If you don't see it, push a commit to `main`, wait for the workflow to complete, then come back to this page.
6. Enable: **Do not allow bypassing the above settings** (recommended — prevents admins from force-merging without the check)
7. Click **Create** (or **Save changes**)

After this, any PR whose meta-review fails will show a red ❌ next to the check and the merge button will be disabled until the failing commits are fixed.

### Emergency override

If you absolutely need to merge without the check (e.g. CI itself is broken and needs fixing), you have two options:

1. **Admin override** — if "Do not allow bypassing" is NOT enabled, admins can merge anyway. GitHub logs this in the audit trail.
2. **Temporary branch protection removal** — go to Settings → Branches → edit the rule → uncheck "Require status checks" → merge → re-enable.

Either path leaves a trace. Neither is silent. This is intentional: emergency overrides should be obvious, not accidental.

## How to run the same checks locally

Before pushing or opening a PR:

```bash
python3 tests/meta_review.py --verbose
python3 tests/verify_triggers.py
```

If both exit 0, your commit will pass CI. If either fails, fix the findings first. The scripts are identical to what CI runs — no environment differences.

## Troubleshooting

### "CI passed locally but fails on GitHub"

Most likely causes:
- You committed something that wasn't staged locally (check `git status` and `git log --oneline origin/main..HEAD`)
- Your local Python is older than 3.11 and the rubric uses a 3.11-only syntax
- A file permission issue (`tests/*.py` must be readable by CI)

Run `python3 tests/meta_review.py --verbose` on the exact commit that's failing and compare the output to the CI logs.

### "The meta-review check doesn't appear in branch protection"

Status checks only appear after the workflow has run at least once. Push a dummy commit to a branch, open a PR, wait for the action to complete, then the check will be selectable. (Alternatively, push directly to main — not recommended but works.)

### "I want to add another CI job"

Add it to `.github/workflows/meta-review.yml` as a new `jobs.<name>` entry, or create a separate workflow file under `.github/workflows/`. If the new job should also be required, add it to branch protection after its first run.

### "CI takes too long"

Typical runtime is under 30 seconds because both scripts are stdlib-only. If it's taking significantly longer, check for:
- A new skill with a massive SKILL.md that slows verify_triggers (unlikely — the parser is O(n))
- A GitHub Actions runner queue delay (check the GitHub Actions status page)

## Related

- `hooks/README.md` — local enforcement hooks (layers 1–3)
- `CONTRIBUTING.md` — what contributors need to do before opening a PR
- `tests/meta_review.py` — the rubric runner itself
- `skills/review/references/meta-review-checklist.md` — the rubric definition
- `CHANGELOG.md [1.8.0]` — context on why CI was added now
