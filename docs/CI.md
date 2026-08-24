# CI — Server-side Gate 1 via GitHub Actions

Added in **v1.8.0**. Runs the meta-review rubric on every push to `main` and every pull request. This is the defense-in-depth layer below the local enforcement hooks — the last line before broken methodology changes land in `main`.

## What it does

The workflow `.github/workflows/meta-review.yml` executes two commands on every push and PR:

```bash
bash tests/run-all.sh            # весь локальный CI-эквивалент (v1.79.0)
bash tests/run-all.sh --quick    # быстрый статический костяк
# точечно: python3 tests/meta_review.py --verbose / python3 tests/verify_triggers.py
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

## Scheduled hygiene and objective quality

The separate workflow `.github/workflows/hygiene-schedule.yml` is the external
clock for contracts that cannot be made periodic by prose alone:

| Cadence (UTC) | Job | Evidence |
|---|---|---|
| Monday 03:17 (`17 3 * * 1`) | manifest cleanup, quality freshness, weekly structural/benchmark checks, objective module scorecard | `weekly-*.json`, `quality-score-*.json` |
| First day of month 04:29 (`29 4 1 * *`) | reversible baseline/disabled ablation of the configured component | `ablation-*.json` |

Both jobs have only `contents: read`. They never commit a generated grade,
delete a harness component, open an issue, or merge a change. Records under
`.itd-memory/hygiene/` are uploaded with `actions/upload-artifact` even when a
minimum score, overstated declared grade, or ablation regression makes the job
red. The workflow also supports `workflow_dispatch` for an immediate weekly or
monthly run.

The objective score is not an LLM opinion. `docs/QUALITY_SCORECARD.json` maps
each module's five dimensions to executable probes and weights totalling 100.
Probe results are cached within a run; `attempts: 2` provides repeatability
evidence for stability dimensions. The runner computes the grade, enforces the
module minimum, and fails if `QUALITY.json` declares a grade better than the
computed evidence:

```bash
python3 docs/templates/itd/itd_hygiene.py quality \
  --scorecard docs/QUALITY_SCORECARD.json --root . --record --json
```

GitHub only evaluates scheduled workflows from the default branch, so this
clock becomes active after the workflow is merged to `main`. An adopted GitHub
project can opt in by copying `docs/templates/github/itd-hygiene.yml` to
`.github/workflows/itd-hygiene.yml`; `/adopt` must ask before adding recurring
external CI and must fill `.itd/QUALITY_SCORECARD.json` with real project probes.

## Defense-in-depth layers

CI is the outermost of four layers. They are ordered from earliest feedback to latest:

| Layer | When | What it catches | Can be bypassed? |
|---|---|---|---|
| **1. `check-skills.sh`** (UserPromptSubmit) | Before Claude's first response to a prompt | Ambiguous prompts that should trigger a skill but weren't being routed | Soft reminder only — not a bypass concern |
| **2. `check-tool-skill.sh`** (PreToolUse) | Before every raw Bash/Edit/Write | Claude about to do ad-hoc work when a skill would fit | Soft reminder only — not a bypass concern |
| **3. Enforcement hooks** (PreToolUse) | Before Write/Edit on SKILL.md and before `git commit` | Incomplete skills (missing references/triggers/fixtures), incomplete commits (staged SKILL.md without supporting artifacts) | Only via documented `.methodology-self-extend-override` file |
| **4. CI (this workflow)** | On push to main and on every PR | Everything in the meta-rubric: all 11 Critical + 8 Important checks. Catches anything the local hooks missed OR scenarios where local hooks were never installed | Only by admin override of branch protection (leaves audit trail) |

If a contributor has no local hooks, layers 1–3 are silent and layer 4 is the only gate. If the maintainer has all four layers, the first Write that introduces drift is caught at layer 3, never reaching layer 4.

## Required setup — App-bound ruleset

The scalable merge boundary is the canonical organization ruleset,
not a local hook or a repository-held API key. Provision the dedicated review
App and broker first. The App must be installed on the repository and must have
published its check at least once before GitHub can bind that check to the App
as an expected source.

This path has a billing-plan prerequisite: private organization-wide rulesets
and required-workflow enforcement need GitHub Team or Enterprise. The current
`hihol-labs` handoff records GitHub Free, so operators MUST NOT attempt the
organization activation below until that prerequisite is satisfied. During
this bootstrap PR, keep both repository branch-protection checks:
`meta-review / Gate 1 — meta-review rubric` and `ITD external review gate`;
accept the exact candidate only with its current external Verification Loop
adjudication receipt. Do not require/advertise the staged machine oracle: it
stays outside `.github/workflows/` until its verifier anchors are protected.

After this reviewed bootstrap is merged, retain
`.github/workflows/external-review-gate.yml` as compatibility transport and let
the broker publish its App-owned check once. Through the branch-protection
required-status-checks API, add `checks[]` entry
`{"context":"ITD external review gate","app_id":<ITD_GITHUB_APP_ID>}`
(the App ID, not its installation ID)
alongside meta-review; name-only `contexts[]` is forbidden. Read the protection
back and require that exact pair before enabling merge. Install machine-oracle
only in the separate anchor-preserving follow-up, without changing protected
verifiers. A missing pair/check blocks merge. This Free-plan boundary is not
the canonical organization ruleset, so `itd gate doctor` must not report
`PROTECTED`; organization rollout remains pending on the plan prerequisite.

Create the App through the official manifest flow after the broker has a
stable HTTPS origin:

```bash
python scripts/itd_github_app_manifest.py \
  --organization hihol-labs \
  --broker-url https://review.example.org \
  --output-dir /secure/itd-review-app \
  --plan

python scripts/itd_github_app_manifest.py \
  --organization hihol-labs \
  --broker-url https://review.example.org \
  --output-dir /secure/itd-review-app \
  --serve --apply
```

Install the resulting private App only on controlled repositories. Its manifest
contains the exact broker webhook, least-privilege permissions, and only
`pull_request`/`merge_group` events. Keep the generated private key and webhook
secret in the broker credential boundary.

The ruleset commands below are post-bootstrap operations. Do not use `--apply`
until all of these facts are independently verified: the billing-plan
prerequisite is satisfied; this bootstrap contract and all verifier anchors are
already in the protected base; a separate anchor-preserving PR has copied the
template to `.github/workflows/itd-machine-oracle.yml` without changing those
anchors; and `<PINNED_ITD_RELEASE_SHA>` is an immutable release commit in
`<ITD_RELEASE_REPOSITORY_ID>` containing that exact workflow. The App-owned
check must also have been published once. If any fact is missing or the preview
differs, do not apply the ruleset and leave merge blocked.

Preview the exact payload, then apply it with an administrator-authorized
GitHub CLI session:

```bash
itd gate ruleset \
  --repository hihol-labs/idea-to-deploy \
  --scope organization \
  --app-id <ITD_APP_INTEGRATION_ID> \
  --workflow-repository-id <ITD_RELEASE_REPOSITORY_ID> \
  --workflow-sha <PINNED_ITD_RELEASE_SHA>

itd gate ruleset \
  --repository hihol-labs/idea-to-deploy \
  --scope organization \
  --app-id <ITD_APP_INTEGRATION_ID> \
  --workflow-repository-id <ITD_RELEASE_REPOSITORY_ID> \
  --workflow-sha <PINNED_ITD_RELEASE_SHA> \
  --apply
```

The canonical ruleset:

- requires a pull request;
- requires the `ITD machine oracle` ruleset workflow from
  `hihol-labs/idea-to-deploy` at an immutable release SHA;
- requires `ITD external review gate` from the dedicated App integration ID;
- requires checks against the current base;
- covers the default branch and `release/*`;
- blocks branch deletion and non-fast-forward pushes;
- has no bypass actors.

Before enabling that workflow rule, provision an ephemeral self-hosted runner
whose immutable image digest is bound to the dedicated
`itd-machine-oracle-v1` label. Rotate the image as a reviewed control-plane
change; do not map this gate to mutable GitHub-hosted `*-latest` images or to a
shared long-lived runner.

For a local-submission profile, no App, ruleset, broker, or administrator grant
is required. Freeze and independently adjudicate the staged candidate, then
commit exactly that index as one normal single-parent commit. Do not amend the
tree or add another commit. Register the adjudication and run the canonical
doctor:

```bash
itd gate register-profile \
  --repository <owner/repository> \
  --checkout <absolute-git-root> \
  --repository-owner-type <user-or-organization> \
  --deployment-profile local-submission \
  --protection-profile local-review \
  --local-review-receipt-file <absolute-current-adjudication.json> \
  --local-review-unit-id <unit-id>:general-review \
  --local-review-risk-tier high \
  --local-review-producer-keyring-sha256 <trusted-keyring-sha256>

itd gate doctor --repository <owner/repository>
```

The expected claim is `LOCAL_REVIEWED`, never `PROTECTED`. This portable route
does not require an adoption verification contract: its guarded push validates
the current exact independent adjudication instead of running an
adoption-contract machine preflight. The doctor and guarded transport use
Verification Loop `--candidate-mode committed-head`: the clean `HEAD` must have
exactly one parent equal to the reviewed `baseCommit`, the same full tree, and
the same binary diff. An amended tree, merge commit, or second commit requires
a new adjudication and registry update. Evidence may also be refreshed after
the commit by running the machine, checker, and adjudicate commands with
`--candidate-mode committed-head`. App-backed profiles retain adoption and
contract-machine requirements.
In both cases the checker must bind the shared producer's signed phase-one v2
receipt and trusted producer keyring. The doctor adds
`--require-mandatory-route`; a generic fresh-session checker/adjudication is
not publication evidence. The host registry's producer-keyring SHA-256 is
passed into the installed validator, so a candidate cannot authorize its own
replacement phase-one key.

For the strongest organization-workflow profile, register each checkout with
its active ruleset/enrollment coordinates and Ed25519 maker key, then run:

```bash
itd gate enrollment \
  --repository hihol-labs/idea-to-deploy \
  --scope organization \
  --ruleset-id <active-ruleset-id> \
  --app-id <ITD_APP_INTEGRATION_ID> \
  --app-slug <ITD_APP_SLUG> \
  --workflow-repository-id <ITD_RELEASE_REPOSITORY_ID> \
  --workflow-sha <PINNED_ITD_RELEASE_SHA> \
  --output /secure/idea-to-deploy-enrollment.json \
  --apply

itd gate adopt \
  --root <checkout> \
  --broker-url <broker-https-url> \
  --app-id <ITD_APP_INTEGRATION_ID> \
  --scope organization \
  --ruleset-id <active-ruleset-id> \
  --workflow-repository-id <ITD_RELEASE_REPOSITORY_ID> \
  --workflow-sha <PINNED_ITD_RELEASE_SHA> \
  --provenance-key-id <active-key-id> \
  --provenance-key-file <host-protected-key-file>

itd gate doctor --all
```

`PROTECTED` is valid only when the protected-base contract, pinned central
workflow and immutable runner label, contract-v2 shell-free argv, isolated
interpreters and exact content-bound verifier-side Git objects, installed ITD version, live
ruleset, broker policy/reviewer routes, active App enrollment receipt, budget
admission, and local signing key all match. A
repository-level ruleset is deliberately rejected because GitHub
only provides ruleset-workflow authority at organization/enterprise scope. API
outage or exhausted budget may leave development available, but the App check
fails and merge remains blocked.
`itd gate adopt` refuses to persist a registry entry when any live control
differs or when the default branch does not already contain the active
verification contract. Bootstrap that first contract through the repository's
existing controls or an explicit audited temporary ruleset exclusion, restore
the canonical ruleset, and then register the checkout.

After this, any PR whose meta-review fails will show a red ❌ next to the check and the merge button will be disabled until the failing commits are fixed.

### Emergency recovery

There is no ordinary or admin bypass actor. An emergency merge requires an
explicit administrator change to the ruleset, an audit record and immediate
restoration. The action never creates an ITD PASS receipt, and
`itd gate doctor --all` reports the protection drift.

## How to run the same checks locally

Before pushing or opening a PR:

```bash
bash tests/run-all.sh            # весь локальный CI-эквивалент (v1.79.0)
bash tests/run-all.sh --quick    # быстрый статический костяк
bash tests/run-all.sh --targeted # только сьюты, связанные картой с правкой
bash tests/run-all.sh --fail-fast  # остановиться на первом красном сьюте
# точечно: python3 tests/meta_review.py --verbose / python3 tests/verify_triggers.py
```

**Targeted-профиль (LPD-003-1).** Полный прогон был входом по умолчанию даже
для однофайловой правки — по замеру G0 это 82% всего машинного слоя. Режим
`--targeted` берёт набор из `.itd/IMPACT_GRAPH.json` через
`scripts/itd_regression_select.py`, а пути, которые нельзя перечислить узлами
(контракты юнитов, записи live-прогонов, квитанции), разрешает правилами
`.itd/IMPACT_PATTERNS.json`. Границы объявлены явно и печатаются:

* `OUTSIDE-MIRROR` — карта связывает сьют с правкой, но зеркало его не гоняет
  (нужен свой `--phase`, свой кандидат или релизный пин). Такие сьюты
  **названы, но не прогнаны**: безусловный прогон дал бы false-red, молчание —
  false-green.
* `NO-IMPACT by rule` — путь исключён правилом; каждое правило `no-impact`
  машинно судится против сгенерированной карты в
  `tests/verify_targeted_regression.py` (как только сьют начнёт читать такой
  путь, правило падает).
* `MIRROR-COVERAGE` в полном прогоне — сколько `tests/verify_*.py` зеркало
  реально гоняет, чтобы `DONE fails:none` не читалось шире, чем есть.

Селектор судит **только тот репозиторий, в котором лежит**: карта, правила и
зеркало берутся от его собственного расположения, и ни один публичный флаг не
называет читаемый файл (решение 2026-08-24, `.itd/DECISIONS.md`). Чтобы
передать путь, начинающийся с дефисов, поставьте `--` — всё после него
трактуется как пути: `bash tests/run-all.sh --targeted --changed -- --path.py`.

Замер на этом репозитории (WSL, один хост, август 2026): полный прогон 301 с
(129 сьютов); targeted на однофайловой правке хука — 99 с (17 сьютов, −67%);
на трёх реальных юнитах (`0c842ed`, `e7bf0f3`, `e9e5fe1`) — 210/223/202 с
(46/63/39 сьютов, −30/−26/−33%). Экономия по времени меньше, чем по числу
сьютов: несколько тяжёлых сьютов попадают почти в любое замыкание.

Targeted — не гейт и не замена релизной улике: приёмка остаётся за Verification
Loop, а PR/релиз идут полным прогоном.

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
- `.github/workflows/hygiene-schedule.yml` — weekly/monthly external clock
- `docs/QUALITY_SCORECARD.json` — active objective module scorecard
