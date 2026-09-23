# G-001 RISK-TIER-1 - proportionality becomes the default

Unit `G-001` (medium) is `verified` in `.itd-memory/GOAL.json` (harness transition
2026-09-23T11:07:49Z, receipt `G-001-adjudication-a3-ch.json`, committed-head over `8f843d3`);
the criterion and the verificationCommand live ONLY there and are not restated here. This
candidate is the ledger-close package: GOAL/STATE/events transitions written by the harness,
DECISIONS 2026-09-23, BACKLOG P2/P3 2026-09-23, this file. Review claim ids:
`G-001`, `G-001:general-review`.

Measured before the first edit: criterion part (1) - `itd_unit_log.py activate` refusing
without `--risk-tier` - is ALREADY enforced (`skills/task/scripts/itd_unit_log.py:403-408`,
pinned by `tests/verify_unit_log.py` "activate-without-risk-tier-refused"). The audit claim
"optional flag" was wrong; the new oracle pins it as a regression, no product change there.
The repository has NO `.itd/COMPLETION_POLICY.json`: its completion gate runs on the
built-in `DEFAULT_POLICY` (medium) in `hooks/completion-gate.sh:142` and
`docs/templates/itd/itd_hygiene.py:170`; "the methodology repo stays medium" therefore means
those two defaults stay `medium` and no repo policy file is introduced.

## In scope

- `skills/_shared/PROPORTIONALITY_POLICY.json`: new `strictClasses` object (money,
  prod-config, db-schema, auth, secrets), each with `keywords[]`, `paths[]`, `tier: high`.
- `skills/_shared/itd_risk_classes.py` (new): fail-closed loader + matcher shared by the
  unit writer; keywords and path patterns are both matched over the goal text AND the
  "Allowed Change Areas" bullets of `.itd/SCOPE_LOCK.md` next to the memory dir (when it
  exists): keywords as whole words bounded by non-letters after camelCase/ACRONYM splitting
  and `_`/`-` joiners -> spaces (tried on both the split and the plain form), path patterns
  by fnmatch with a virtual leading slash over path-like tokens (dotfiles included).
- `skills/task/scripts/itd_unit_log.py` `activate`: after the tier check, a strict-class
  match forces `riskTier=high`, prints the class + matched pattern, and records
  `riskTierForced{declared,class,match}` in `STATE.currentUnit`.
- `docs/templates/itd/COMPLETION_POLICY.json`: `defaultRiskTier` medium -> low + note.
- `docs/adr/ADR-011-default-risk-tier-low.md` (new).
- `tests/verify_risk_tier_default.py` (new, registered in `tests/run-all.sh`),
  mutations by copying `skills/` into a temp dir.
- `skills/task/SKILL.md` Step 3.5 (one paragraph), `CHANGELOG.md` [Unreleased].
- `skills/goal/scripts/itd_goal_verify.py` state projection: one `cur.pop("riskTierForced")`
  so a goal unit never inherits a /task unit's forced-tier note (checker c2 F5).
- Checker round c2 (BLOCKED, `reports/G-001-targeted-c2.md`): F1 dotfile tokens, F2
  keywords over Allowed Change Areas, F3 word boundaries, F4 narrower path patterns, F5
  above, F6 dead regex, F7 template note - all closed in the candidate; the oracle pins each.
- Checker round c3 (BLOCKED, `reports/G-001-targeted-c3.md`): the F4 narrowing lost
  repo-root `k8s/`, `helm/`, `deploy/`, `terraform/` paths -> `_path_hit` tries a virtual
  leading slash (pinned positive); `checkout` keyword dropped (git phrasing), never-covered
  artefacts added (`*production*`, `dockerfile.prod*`, workflows deploy, `id_rsa`, `api_key`);
  ADR-011 "only writer" wording corrected; SCOPE_LOCK-at-activation limit declared. Live
  benchmark pin (minor 6) is re-recorded after the commit, as every skills/docs change requires.
- Checker round c4 (BLOCKED, `reports/G-001-targeted-c4.md`): the c3 db-schema keyword
  narrowing dropped plain `migration`/`migrations`/`миграци*` (fail-open) -> restored; ADR-011
  rule applied explicitly: a false positive raises review cost, a false negative lowers safety,
  so the stem stays even though it also hits reviewer-migration wording. Added schema artefacts
  (`*/schema.rb`, `*.prisma`, `*/models.py`, `*/migrations.*`) and payment-provider vocabulary
  (stripe, yookassa/юкасс*, paypal, cloudpayments, эквайринг*, tariff/тариф*). F5 now pinned
  behaviourally (write_state_projection on a STATE carrying a stale `riskTierForced`).
- Checker round c5 (BLOCKED, `reports/G-001-targeted-c5.md`): camelCase identifiers on the
  owner's Vue/TS stack (`AuthService`, `authStore.ts`, `LoginView.vue`, `getApiKey`) never hit
  because the text was lower-cased before the word boundary -> `_words()` splits camelCase
  first and keywords are tried on both forms (brand names like `YooKassa` stay whole);
  Rails `*/migrate/*`, signin/signup, bot/vault/access/refresh token, `.npmrc`/`.netrc`
  added; ADR-011 now states the template default is the FALLBACK tier (route cost is set by
  the declared tier + forced classes) and lists the accepted false positives (3/61
  historical goals). The lexical floor's vocabulary is NOT claimed complete: the claim is
  the five classes, the oracle-pinned cases and the declared limits.
- Checker round c6 (BLOCKED, `reports/G-001-targeted-c6.md`): snake_case/SCREAMING_CASE
  identifiers never hit multi-word keywords (`access_token`, `BOT_TOKEN`) and ACRONYMWord
  stayed fused (`JWTBearer`) -> `_words()` also splits ACRONYM->Word and turns `_`/`-` into
  spaces; `authentic*`/`authoriz*` stems, prefixed money forms; the non-activation branch of
  the goal projection also drops `riskTierForced`; SCOPE_LOCK matching description corrected;
  two more accepted false positives listed in ADR-011.
- Checker round c7 (PASSED_WITH_WARNINGS, `reports/G-001-targeted-c7.md`; the loop accepts
  only a clean PASSED): whitespace runs/line wraps now collapse in `_words()`; the scope
  section is recognised as `Allowed Change Areas` or `In scope` at any heading level with an
  optional colon; declared-stack vocabulary (aiogram `pre_checkout_query`, Telegram Stars,
  MinIO access/secret key, `TELEGRAM_TOKEN`, python-jose, `security.py`/`get_current_user`,
  bearer, `ЮKassa`); ADR-011 figure 3 -> 5 of 61 with the three new accepted false positives;
  template note says FALLBACK.
- Checker round c8 (BLOCKED, `reports/G-001-targeted-c8.md`): the c7 heading regex ended the
  scope section at ANY heading (`### Backend` sub-sections, a fenced `# comment`) -> the
  section now runs until a heading of the same or a higher level, headings need whitespace
  after the hashes, fenced code is skipped; three cases pinned (nested, fenced, same-level end).
- Publication round PUB2 (keyless opposite-GPT producer, gpt-5.6-sol, BLOCKED, 8 unique
  findings): G-001 criterion wording aligned with what was built (object, no repo policy
  file - DECISIONS 2026-09-23 correction); a strict-class match is now recorded as
  `riskTierMatch` for every declared tier, `riskTierForced` only when raised; fence closing
  requires the opening delimiter char and length; an existing unreadable SCOPE_LOCK fails
  the activation closed; the oracle asserts the repo policy file is absent and pins the
  non-activation goal projection behaviourally; the live-transcript self-check finding is
  declared out of scope (above). PUB1 was UNVERIFIED because no acceptance followup was open
  (the whole 507 KB contract went into each unit prompt) - fixed by commit 0f535c9.
- Checker rounds c12 (PASSED_WITH_WARNINGS, tree 141bdbcc) and c13 (PASSED, tree 64560089,
  commit 5f5db74): the goal projection drops `riskTierMatch` in every decision; a dangling
  or looping SCOPE_LOCK symlink is an existing entry that fails to read (`os.path.lexists`);
  the oracle asserts the printed match pattern.
- Publication round PUB3 (gpt-5.6-sol on 5f5db74, BLOCKED, 9 unique findings reported
  twice by the unit and integration reviewers): `_path_tokens` strips Markdown presentation
  (`**db/schema.rb**`, `[x.py]`, `~~x~~`, `_x_`) before matching, five cases + the
  `__init__.py` guard pinned; STATE.currentUnit.goal mirror synced to the amended criterion
  by hand (no status transition; `--reconcile` is a NOOP on text-only drift - BACKLOG P3);
  `.itd-memory/contracts/G-001.md`, CHANGELOG and the oracle docstring aligned with the
  riskTierMatch/riskTierForced contract; the four architecture-content findings on the
  recorded benchmark output are declared out of scope (Declared limits, widened).
- Checker round c14 (BLOCKED, `reports/G-001-targeted-c14.md`): markup and sentence
  punctuation nest in either order (`**db/schema.rb**.`), so `_strip_markup` now iterates
  to a fixed point (markup both sides, `.?` right side only - dotfiles keep their dot); the
  underscore guard is pinned on the tokens themselves (`__init__.py`, `_config.yml`, `.env`).
- Checker round c15 (PASSED_WITH_WARNINGS, tree 0220d251): CHANGELOG and the task contract
  said forced high applies to declared low/medium; the code raises every tier below high,
  `unknown` included (oracle `activate-unknown-plus-strict-forced-high`) - wording fixed.
- Publication round PUB4 (gpt-5.6-sol on ef7d368, BLOCKED, 6 unique findings reported
  twice): a fence line with an info string (```text) is content, not a closer (CommonMark);
  a nested `### In scope` inside an open section is a sub-heading and never discards what
  was collected, a non-scope heading at the same or a higher level closes the section
  without ending the scan, so a later `## In scope` unions with the first (the c9
  observation in BACKLOG P3, now fixed and pinned); the oracle exercises the EFFECTIVE
  built-in medium defaults (imports `itd_hygiene.py` and `hooks/completion-gate.sh`,
  resolves an empty project) and pins the activation-level fail-closed on a malformed
  policy (no STATE/events written); the verified receipt of G-001 is re-anchored to the
  final head with `itd_goal_verify.py --recheck --candidate-mode committed-head` after
  this fix commit, and the acceptance evidence text is refreshed to the final round.
- Checker round c17 (PASSED_WITH_WARNINGS, tree d33c56b4): a backtick marker whose info
  string contains a backtick (a line starting with inline ```code```) opened a fence and hid
  every later heading (pre-existing, same family as PUB4 F3) -> such a line is not a fence
  opener (CommonMark); a `~~~` info string may still contain backticks; both pinned.
- `.itd/IMPACT_GRAPH.json` regeneration (`tests/build_impact_graph.py`) so the new suite
  and module are attached.
- Frozen-digest cascade, mechanical only (no semantic change to either policy):
  `PROPORTIONALITY_POLICY.json` sha256 re-pinned in
  `skills/_shared/WORKING_DEADLINE_POLICY.json` (`inheritsVerificationPolicy.sha256`),
  `benchmarks/proportionality/CORPUS.json` (`policySha256`) and
  `benchmarks/working-deadline/CORPUS.json` (`inheritedPolicySha256`, plus the
  working-deadline policy's own `policySha256`); both `CORPUS.sha256` seals recomputed.

## Required evidence

- `sh skills/_shared/itd_py.sh tests/verify_risk_tier_default.py`: RED on pre-fix bytes
  (recorded), GREEN after, >=3 lethal mutations reported by the oracle itself.
- `sh skills/_shared/itd_py.sh tests/verify_unit_log.py` and
  `tests/verify_proportionality_benchmark.py` stay green (policy shape consumers).
- `bash tests/run-all.sh --quick` last line `DONE fails:none`.

## Declared limits

- SCOPE_LOCK Allowed Change Areas are matched as read at activation time, unbound to the
  unit (checker c3 minor 2); the goal text is the primary input.
- `tests/fixtures/live-model-evidence/runs/20260923T110238Z-e468a267/**` is RECORDED
  model output of the live benchmark (fixture-03-cli-tool: the model's own PRD,
  PROJECT_ARCHITECTURE, transcript and self-check), re-recorded by commit 8f843d3 only
  because the evidence pin binds to the skills tree. Its content is evidence of what the
  model produced, not product code of this unit: the benchmark verifier pins hashes and
  structure and does not re-judge the architecture merit of the recorded documents
  (unbounded counters, CSV key mutation, timezone buckets, line-length bounds, the 4-story
  self-check - PUB2 F6, PUB3 F5-F8). Editing those files would falsify the evidence. Out of
  this unit's scope; the self-check gap is BACKLOG P3 2026-09-23.
- Forced `high` has no CLI escape hatch; the owner edits the policy file to change a class.
- Matching is lexical; a goal text that hides its money/auth nature is not detected - the
  reviewer contour on high units remains the backstop, this is a floor, not a classifier.
- `/goal --activate` writes `riskTier` from `GOAL.json` through the same STATE writer but
  does NOT run the strict-class matcher (goal units are owner-approved with an explicit
  tier at decomposition); recorded as a follow-up, not silently claimed.

## Out of scope

- `hooks/*` early exit by tier (G-003), pre-flight sentinel (G-002), hook auto-install
  (G-004), external pilot (G-005).
- Changing `RISK_TIERS`, `riskRoutes`, `signalContours` or any contour cost.
- `hooks/completion-gate.sh` / `itd_hygiene.py` built-in defaults (stay medium).
- The archived `GOAL-2026-09-20.json` event gap (BACKLOG P3).
