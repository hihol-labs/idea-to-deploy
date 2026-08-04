# Scope Lock — GPG-003 unified mandatory keyless independent review

## Current Task

Replace the conflicting review surfaces with one mandatory pre-PR independent
review workflow. The authoritative producer must try an isolated fresh
different OpenAI model/session through ChatGPT subscription auth first, then
Anthropic subscription auth, then official GitHub Copilot user auth in free
`auto` mode. The route
must never require
`OPENAI_API_KEY`, silently dispatch a paid API request, inherit development
context, or accept caller consent as a bypass. If every route is unavailable or
unverified, PR publication remains blocked. WIP=1.

"Mandatory" means no caller may bypass or substitute the independent route
selected by Verification Loop. The existing risk policy remains authoritative:
low risk is machine-only, while medium/high/unknown require the checker route.

## Allowed Change Areas

- `skills/_shared/itd_free_reviewer_producer.py` shared keyless routing,
  isolation, provenance and typed failure logic
- `/review`, `/cross-review`, Verification Loop and host-adapter documentation
  needed to point at the same producer and authority
- focused reviewer-routing, release, host-parity and mutation tests
- hooks/fixtures whose pinned wording currently advertises advisory/fail-open
  cross-review behavior
- the guarded Draft-PR updater and focused mutation tests, only to support an
  exact reviewed amend via observed-SHA `--force-with-lease` without weakening
  the pre-push receipt, maker, registry, or local-review checks
- the portable v2 `local-review` doctor, guarded push and Draft-PR preparation,
  only to let an intentionally unadopted product checkout use its current exact
  adjudication; App-backed and legacy profiles retain adoption and machine
  preflight
- GPG-003 acceptance, verification, state, decision, root-cause, handoff and
  release records
- standard patch-release metadata in a separate release candidate after the
  implementation PR merges

## Forbidden Change Areas

- adding a second completion/review authority beside Verification Loop
- using `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, Google API keys,
  or any automatically paid provider call in the default route
- allowing caller/user consent, `--force`, outage, missing auth, quota failure,
  malformed output, incomplete coverage, same model/session, inherited context,
  tool use, stale candidate or prose to count as PASS
- exposing subscription/OAuth material, reviewer environment, repository files,
  network tools or mutation tools to the reviewing model
- changing the order OpenAI fresh model -> Anthropic -> GitHub Copilot
- restoring the retired Gemini CLI/GitHub Models backends or the
  location-ineligible Antigravity account route as mandatory, or treating
  their retirement/ineligibility as reviewer evidence
- falling back after a valid reviewer returns findings or an unverified contour;
  only typed transport `UNAVAILABLE` may advance to the next provider
- weakening exact staged/committed-head binding, WIP=1, MEM-8, maker/checker
  separation, human merge/deploy authority, secret scrub or receipt validation
- claiming App-backed `PROTECTED` enforcement for the portable local-review
  profile
- accepting a local-review push whose ref is not the checkout's exact committed
  `HEAD`, or whose adjudication is missing, stale, foreign or non-PASSED
- editing an installed plugin cache instead of publishing and installing a new
  release

## Acceptance Boundary

GPG-003 is accepted only when RED reproduces the old paid/advisory split; the
shared producer deterministically enforces the ordered keyless route and one
closed verdict schema; `/review`, `/cross-review` and Verification Loop name it
as the sole mandatory pre-PR reviewer; all-unavailable is fail-closed with no
bypass; paid API remains only a separately named, separately authorized
operation; WSL and native Windows mutation/parity tests pass; a fresh
different-model high-risk checker and exact adjudication accept the staged
candidate; the implementation PR and patch release merge with required checks;
and the clean release is installed and verified on WSL and Windows Codex and
Claude Code. The result remains `LOCAL_REVIEWED`, never `PROTECTED`.
