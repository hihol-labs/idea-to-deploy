---
name: review
description: 'Validate project documentation and code via binary rubric. Checks consistency between PRD, architecture, plan, and code.'
argument-hint: project path or specific document to review
license: MIT
allowed-tools: Read Glob Grep
context: fork
agent: code-reviewer
report_only: true
metadata:
  effort: medium
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.83.0
  category: quality-assurance
  tags: [validation, quality-check, review, consistency, solid, code-smells, methodology-review]
---

# Review


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- проверь документацию, проверь код, проверь архитектуру, проверь PR
- валидация проекта, ревью, code review, review project
- найди косяки, оцени качество, найди баги в коде
- check quality, validate, audit
- автоматически перед коммитом >2 файлов

You are a quality validator for project documentation and code. Your job is to find gaps, inconsistencies, and missing pieces BEFORE implementation begins.

## Recommended model

**opus** — Cross-document validation requires holding all 6 documents in working memory simultaneously and checking ~25 rubric items. Opus is recommended; the code-reviewer subagent fork is also Sonnet-capable.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 0 (pre): Runner selection — avoid fork-thrash on a large CLAUDE.md (v1.24.0)

**First thing, before loading any more context**:

```bash
wc -c CLAUDE.md 2>/dev/null   # > ~12000 bytes → prefer Agent-tool dispatch over fork
```

Small / absent `CLAUDE.md` → the normal fork path is fine, continue below.
Large → do NOT rely on the fork (it inherits the bloated conversation and
autocompact-thrashes to death); dispatch the review instead:

- `Agent(subagent_type: "code-reviewer", …)` with a **thin prompt**: review
  target + files/dirs **by path** — never paste `CLAUDE.md` or file bodies
  (the agent reads them itself).
- Tell the agent the review mode (methodology self-review vs regular project —
  Step 0 detection below; `agents/code-reviewer.md` carries matching logic).
- **Pass a report-file path** (`claude-review-<slug>.md`, предпочтительно вне
  git-дерева цели) and require INCREMENTAL writes — file = contract, final
  message = transport. При обрыве/пустом финале: сначала прочитай report-файл,
  потом Step 2.7 re-ping, затем fresh narrow (helpers §9).

Обоснования (fork-thrash механика, история v1.72.0, детали контракта
report-файла, stall-resilience) — `references/runner-and-recovery.md` §0.

### Step 0.4: Resolve the review TARGET path (v1.42.0 — do not silently review cwd)

`$ARGUMENTS` may point the review at a DIFFERENT repo/path than the current
working directory (live incident 2026-07-02: args named a WSL repo, the fork
reviewed cwd and reported «nothing to review»). Rule:

1. Extract any absolute path / repo reference from `$ARGUMENTS` (POSIX path,
   Windows path, `\\wsl.localhost\...` UNC, or an explicit «репо X»).
2. If it differs from `pwd` — `cd` into it for every git/inspection command
   (or prefix commands with `git -C <target>`); when the path is not reachable
   from this fork (другая машина/окружение) — do NOT fall back to cwd:
   **delegate** to the `code-reviewer` agent with the explicit target path in
   its prompt and relay its verdict as this review's result (the sentinel in
   Step "mark done" is still written — the review DID happen, by delegation).
3. If no path in args — cwd is the target (default, старое поведение).
4. Never report «нет изменений» from a directory the user did not ask about:
   name the resolved target in the report header so a mismatch is visible.

### Step 0: Detect review mode (v1.13.0)

Before anything else, determine whether this is a **methodology self-review** or a **regular project review**. The two modes use different rubrics and different runners — mixing them produces nonsense reports.

Methodology self-review is active when ANY of:

1. `$ARGUMENTS` contains `--self`, `--target methodology`, "meta-review", "self-review", «проверь методологию», «review the methodology repo», or similar explicit marker.
2. `pwd` (or the path in `$ARGUMENTS`) contains `.claude-plugin/plugin.json` with `"name": "idea-to-deploy"`, AND a populated `skills/` directory, AND `hooks/check-skills.sh`.
3. The current git diff (or the path under review) touches `skills/*/SKILL.md`, `hooks/*.sh`, `.claude-plugin/plugin.json`, or `tests/meta_review.py` — i.e. methodology surfaces, not project surfaces.

**If methodology self-review is active:**

```bash
cd <repo_root>
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
sh "$SHD/itd_py.sh" tests/meta_review.py --verbose
```

The script implements the full three-tier rubric from `references/meta-review-checklist.md` (same Critical/Important/Nice-to-have structure as project review). Parse its output:

- `FINAL STATUS: PASSED` → report `PASSED`
- `FINAL STATUS: PASSED_WITH_WARNINGS` → report `PASSED_WITH_WARNINGS` with the Important findings
- `FINAL STATUS: BLOCKED` → report `BLOCKED` with the Critical findings and offer fixes (Step 4)

Do NOT run the project-level rubric (Steps 1-2 below) in methodology mode — it would look for `PRD.md` / `STRATEGIC_PLAN.md` / `IMPLEMENTATION_PLAN.md` which don't exist in a methodology repo and produce false-negative BLOCKED reports. This was the v1.12.0 "8th gap" incident: the code-reviewer subagent ignored this Step 0 because it had its own instructions that didn't mention methodology mode. Fixed in v1.13.0 by syncing `agents/code-reviewer.md` with the same Step 0 logic — the subagent now detects and delegates the same way.

**If regular project review is active:** proceed to Stage A, then Step 1 below with the standard rubric.

### Stage A: Spec-compliance gate (v1.21 — PFO port)

Two-stage review: **spec compliance first, code quality second.** Beautiful code that does not solve the requested task must not pass. This stage runs before the quality rubric.

Check the diff/output against, in priority order:

1. `.itd/ACCEPTANCE_CONTRACT.json` — does every `criterion` have attached `evidence` and a `status` of `passed`? A criterion with no evidence or an un-run `verificationCommand` is **not** satisfied.
2. `.itd/UNIT_CONTEXT_MANIFEST.json` `goal` and `allowedWriteAreas` — does the change deliver the goal and stay inside scope?
3. `.itd/SCOPE_LOCK.md` — does the diff touch any Forbidden Change Area?

Verdict:

- **Spec FAIL** (a criterion unmet, scope breached, or goal not delivered) → gate status `BLOCKED` regardless of code quality. Report which criterion/scope rule failed. Do **not** proceed to the quality rubric — fixing style on code that solves the wrong problem is wasted work.
- **Spec PASS** → proceed to Step 1 (Stage B: code quality).
- **No `.itd/` contracts present** (most current projects) → this stage is a soft no-op: note "Stage A skipped — no acceptance contract" and proceed to Step 1. Backward-compatible; nothing breaks.

Fail-closed rule: if you cannot determine spec compliance because evidence is missing or ambiguous, treat it as **not passed** — never assume green.

**Stage A.5: Contract health (v1.67.0 — init-audit gap #3).** When `.itd/` exists, before reading the contracts as gates, verify they are trustworthy sensors — rubric check **I10** (Important tier, see `references/review-checklist.md`):

```bash
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
sh "$SHD/itd_py.sh" .itd/check_contract_drift.py            # derived contracts vs CLAUDE.md
sh "$SHD/itd_py.sh" .itd/check_contract_drift.py --filled   # key contracts are not template prose
```

- Any `DRIFT` line, or `FORBIDDEN_CHANGES.md` / `SCOPE_LOCK.md` / `VERIFICATION_CONTRACT.json` reported as `TMPL`/`MISS` → mark **I10 fail** (Important warning in the report, gate still passes) and say explicitly which gates are running blind on template prose. Do NOT escalate to BLOCKED — a stale contract is a warning about the sensors, not proof the change is wrong.
- The project's `.itd/` copy may predate the `--filled` flag — fall back to the read-only Grep checks described in I10.
- No `.itd/` → I10 is N/A, silent skip.

### Step 1: Detect what to review

Read available project files:
- STRATEGIC_PLAN.md
- PROJECT_ARCHITECTURE.md
- IMPLEMENTATION_PLAN.md
- PRD.md
- README.md
- CLAUDE_CODE_GUIDE.md
- CLAUDE.md
- Source code (if exists)

If  specifies a file or path, focus on that. Otherwise review everything available.

### Step 2: Run the binary rubric

**Read `references/review-checklist.md`** — it is the single source of truth for what to check. The rubric is split into three tiers:

- **Tier 1 (Critical)** — checks C1–C12 (and C-code-1 … C-code-6 when source code exists). Failure of any single Critical check sets gate status to `BLOCKED`.
- **Tier 2 (Important)** — checks I1–I10 (and I-code-1 … I-code-11). Failures produce warnings but the gate passes (`PASSED_WITH_WARNINGS`).
- **Tier 3 (Nice-to-have)** — checks N1–N4 (and N-code-1 … N-code-4). Failures are informational only.

**New in v1.4.0:** the code-only rubric now includes SOLID violations (God class, long parameter list, feature envy, Interface Segregation, Dependency Inversion), cyclomatic complexity > 10, Fowler code smells (shotgun surgery, magic numbers, duplication), and Google Engineering Practices (small change size). Full definitions live in `references/review-checklist.md` under "Code-quality checks".

**New in v1.31.0 (New-SDLC port — the "80% problem"):** the code-only rubric adds checks targeting the failure-prone last 20% of vibe-coded output: `C-code-5` hallucinated/slopsquatting dependencies (Critical), `C-code-6` irreversible external actions without a human-gate (Critical — money movement, auto-orders, FX, payouts), `I-code-10` unenforced business invariants (Important), `I-code-11` edge-case completeness on AI-generated logic (Important). Full definitions live in `references/review-checklist.md` under "AI-generated code checks — the '80% problem'". These complement, and pair with, the eval-suite generated by `/test` Step 3.5.

**New in v1.32.0 (Day-3 Context Engineering port):** `C-code-7` (Critical) — context integrity for AI/agent code: untrusted input (tool/RAG/web/user content) must not reach the model context, system prompt, or long-term memory without a trust boundary, and writes to agent memory (especially async/out-of-band writers) must be validated, not blind upserts. This is the agentic analogue of injection; it protects the very inputs that drive the `C-code-6` irreversible actions. Pairs with the `/security-audit` context & memory integrity section and the `MEMORY_RE` DoD signal. See ADR-001 async-memory note.

For each check:
1. Read the referenced files (PROJECT_ARCHITECTURE.md, PRD.md, IMPLEMENTATION_PLAN.md, CLAUDE_CODE_GUIDE.md, CLAUDE.md, source code).
2. Apply the binary criterion exactly as written in the rubric.
3. Mark ✅ (pass), ❌ (fail), or ⚠️ (partial — only for Important tier).
4. Capture a one-line `→ reason` annotation when failing.

Do NOT invent your own criteria. If the rubric does not cover something, note it in the "Additional observations" section but do not let it affect gate status.

**Coverage-first collection (v1.51.0 — release C, part a).** At the finding
stage optimise for **recall, not precision**: surface EVERY candidate issue,
including uncertain and low-severity ones, each tagged `severity`
(critical/important/minor) + `confidence` (high/medium/low). Do not silently
drop a finding because it feels unsure or minor — the refute pass (Step 2.6)
filters, not you. This does NOT touch the binary rubric or the deterministic
gate (Rule 4): coverage-first only widens the candidate list feeding the refute
pass and the report; gate status is still computed from the PASS/FAIL rubric
checks alone.

### Step 2.6: Refute pass — adversarially verify each surfaced finding (v1.51.0 — release C, part b)

Before writing the report, put every **Critical and Important** candidate
finding through an independent refutation. A plausible-but-wrong finding that
survives to the report wastes the caller's time and erodes trust in the gate;
this pass exists to kill exactly those.

For each such finding, dispatch a **fresh-context** subagent via the **Agent
tool** — `Agent(subagent_type: "code-reviewer", …)` with a **refute prompt**:

- state the single finding verbatim (its `file:line`, claim, why-it-matters) and
  instruct the agent to **REFUTE** it — read the actual code/doc and look for the
  reason it is NOT real (guarded elsewhere, false premise, already handled, N/A
  path). Tell it to **default to `refuted: true` under uncertainty**.
- fresh context is load-bearing: the refuter must not inherit your reasoning, or
  it will rubber-stamp. Pass the finding by value, the target by path — nothing
  else.
- the refuter returns a one-finding verdict block (`BLOCKED` = confirmed real,
  `PASSED` = refuted). A finding refuted survives → **drop it** from the escalated
  set (move to "Additional observations" with a `refuted` note, do not let it
  affect gate status). A finding confirmed → keep it at its tier.

Scale: for a handful of findings, verify each. For many, batch the Agent
dispatches in one message so they run concurrently. If you cannot dispatch
subagents in this runner (e.g. a constrained fork), do the refutation inline in
a separate reasoning pass with the same adversarial framing and say so in the
report ("refute pass: inline"). Minor/low findings are NOT refuted — they never
gate, so the cost is not justified; report them as observations.

**Gate interaction:** the refute pass can only REMOVE unconfirmed findings from
escalation; it never turns a rubric-Critical FAIL into a pass. If a Critical
rubric check itself fails, that is deterministic and stands regardless of any
finding-level refutation (Rule 4).

### Step 2.7: Caller-side verdict-completeness — auto-re-ping a subagent that returned without a verdict (v1.60.0 — Ось 2, agentic engineering)

Every subagent this skill dispatches via the **Agent tool** — the Step 0
delegation to `code-reviewer`, and each Step 2.6 refuter — is contracted to end
on a verdict. Rule — after each dispatch returns, **before** you use its result:

1. **Detect by ABSENCE of the contract marker, not by pattern-matching the
   prose.** Marker = the ```json verdict block from Step 3 (canonical), or the
   bare verdict words (`PASSED` / `PASSED_WITH_WARNINGS` / `BLOCKED` /
   `FINAL STATUS` / `Verdict` / `Вердикт` / `Итог`) — deliberate tolerance for
   garbled JSON fencing. Marker present → accept, done. Never classify by
   whether prose «looks like» narration — the only question is «есть ли маркер».
2. **Absent → auto-re-ping ONCE, without asking the user**: continue the same
   subagent with «Заверши: выдай вердикт одним сообщением — verdict-блок
   (PASSED / PASSED_WITH_WARNINGS / BLOCKED + findings). Не пересказывай
   процесс.» **Empty return = the same case (v1.72.0)** — a harness mislabel
   of a mid-stream kill (finish-line interruption class); but FIRST read the
   report file you passed in the dispatch prompt: a complete file on disk IS
   the result, no ping needed.
3. **Bounded.** At most `ITD_AUTOPING_MAX` (default 2) re-pings per subagent;
   still no verdict → escalate to the user with what the subagent DID return —
   a stuck subagent becomes a visible blocker, not a silent green.

This caller-side step is the *belt*; the *suspenders* are two SubagentStop
hooks — `hooks/narration-final.sh` and `hooks/verdict-contract.sh` — and the
two layers degrade independently (best-effort invariant), never to a false
green. История отказа (×4 ручных пинга за сессию), rationale маркер-детекции
и детали слоёв — `references/runner-and-recovery.md` §2.7.

### Step 3: Generate report

Output the report in **exactly** the format specified at the bottom of `references/review-checklist.md` (`## Reporting format` section). The format is parseable so other skills (`/kickstart` Quality Gate 1) can consume it.

The summary table is mandatory:

```markdown
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | X | 12 | ✅/❌ |
| Important | Y | 10 | ✅/⚠️ |
| Nice-to-have | Z | 4 | ✅/ℹ️ |
```

The derived score (0–10) is computed as:
```
score = ((Critical_pass / Critical_total) * 0.6
       + (Important_pass / Important_total) * 0.3
       + (Nice_pass / Nice_total) * 0.1) * 10
```
and is reported as **informational only** — never used for gating.

**Vendor-neutral JSON verdict block (v1.51.0 — release C, part c).** End the
report with a fenced ```json block carrying the machine-readable verdict — the
stable contract downstream consumers parse (`/kickstart` Quality Gate 1, tiering,
the refute-pass ledger) instead of re-parsing prose. It is plain text, not a
harness tool-call, so it survives a vendor/version switch; a native
`ReportFindings` call is only an OPTIONAL transport, never the contract (harness
best-effort invariant). Emit it every run — the `verdict-contract.sh`
SubagentStop hook blocks a prose verdict that ships without it. `findings` holds
the **escalated** (Critical + Important, post-refute) findings; the array may be
empty. Schema:

```json
{
  "verdict": "PASSED | PASSED_WITH_WARNINGS | BLOCKED",
  "findings": [
    { "severity": "critical|important|minor",
      "confidence": "high|medium|low",
      "file": "path/to/file",
      "line": 42,
      "summary": "one-line statement of the defect" }
  ],
  "unverified": ["area or claim you could not check"]
}
```

> **High-velocity report add-ons (Day-5, optional — not new checks).** For fast-moving
> teams the report may additionally surface a **Bundled Summary + Risk Assessment** (one
> paragraph: what changed + the single biggest risk) and a **Conditional LGTM** —
> "approve provided X is fixed" — instead of escalating a non-Critical warning. These
> are *reporting formats* over the same binary rubric; they never turn a Critical
> `BLOCKED` into a pass.

### Step 4: Offer fixes

For each Critical failure (and optionally each Important warning), ask:
"Хотите, чтобы я исправил [check_id]: [reason]?"

If user agrees, fix the documents directly. Then re-run only the previously-failing checks to confirm the fix. Do not re-run the entire rubric — that's wasteful.

### Step 5: Mark `/review` as done for this session

This is the final step of every `/review` invocation, regardless of status. Write a marker file that signals `hooks/check-review-before-commit.sh` that `/review` has been run in this Claude Code session, unblocking subsequent multi-file `git commit` calls.

Use the Bash tool:

```bash
# tree:<git-write-tree> = diff-binding (v1.59.0); dual-write /tmp + tempdir =
# platform symmetry (v1.42.0). Rationale: references/runner-and-recovery.md §5.
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || python -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"  # win-ok: цепочка падает в /tmp (шим exit!=0)
mkdir -p /tmp 2>/dev/null || true
tree="$(git write-tree 2>/dev/null)"
if [ -n "$tree" ]; then marker="tree:$tree"; else marker="$(date +%s)"; fi
echo "$marker" | tee "/tmp/claude-review-done-${CLAUDE_SESSION_ID:-$$}" > "$tmpd/claude-review-done-${CLAUDE_SESSION_ID:-$$}" 2>/dev/null || echo "$marker" > "$tmpd/claude-review-done-${CLAUDE_SESSION_ID:-$$}"
```

Why in the skill, why dual-write, why tree-hash (and the safe-direction
timestamp fallback) — `references/runner-and-recovery.md` §5.

## Quality Gate

The gate status is **deterministic** — same documents always produce the same status:

| Status | Meaning | Caller behavior |
|---|---|---|
| `BLOCKED` | At least one Critical check failed | `/kickstart` Quality Gate 1 refuses to proceed; user must fix or override |
| `PASSED_WITH_WARNINGS` | All Critical pass, at least one Important fail | `/kickstart` proceeds but shows warnings to user |
| `PASSED` | All Critical and Important pass (Nice-to-have may fail) | `/kickstart` proceeds silently |

**Changed in v1.2.0:** the previous `score >= 7/10` gate has been removed because score values varied between model invocations on the same input. The binary rubric is deterministic.

## Examples

### Example 1: Missing endpoints
User runs: /review
You find: PRD has "user can reset password" but architecture has no /api/auth/reset endpoint.
Report: Critical issue — missing endpoint for password reset story.
Fix: Add POST /api/auth/reset-password to architecture with request/response format.

### Example 2: Inconsistent naming
Architecture says table "clients", implementation plan says "customers", code has "users".
Report: Critical issue — inconsistent entity naming across documents.
Fix: Standardize to one name across all documents.

## Rules

1. Бинарная рубрика — каждый check имеет ровно два состояния: pass или fail. Субъективные оценки ("код неплохой", "архитектура нормальная") запрещены
2. Каждый finding привязан к конкретному месту: `file:line` для кода, `DOCUMENT.md § Section` для документации. Абстрактные замечания без локации невалидны
3. Не изобретай собственные критерии — используй только checks из `references/review-checklist.md` (или `references/meta-review-checklist.md` для methodology mode). Дополнительные наблюдения выноси в отдельную секцию, не влияющую на gate status
4. Gate status детерминирован — одни и те же документы/код всегда дают одинаковый статус. Никогда не понижай BLOCKED до PASSED_WITH_WARNINGS по просьбе пользователя
5. Score (0-10) — informational only, никогда не используется для gating. Единственный gate — бинарный статус (BLOCKED / PASSED_WITH_WARNINGS / PASSED)

## Self-validation

Before presenting review results, verify:
- [ ] Every rubric item has a PASS/FAIL/N-A verdict with justification
- [ ] Overall score is consistent with individual item verdicts
- [ ] BLOCKED status used only when Critical items fail
- [ ] All referenced files actually exist in the project
- [ ] Improvement suggestions are actionable (not vague "improve code quality")

## Troubleshooting

### A Critical check fails but the user insists the project is fine
The rubric is deterministic — if a Critical check fails, there's a real gap between what the documents promise and what they deliver. Do not soften the status to please the user. Instead:
1. Re-read the failing check criterion from `references/review-checklist.md`
2. Re-verify against the actual document content
3. If the check is truly inapplicable (e.g., C2 database check on a no-DB CLI tool), the rubric explicitly allows the "no database" justification path — verify the document has that justification, then the check passes
4. If the user wants to override anyway, return `BLOCKED` and let them invoke `/kickstart` with explicit `--skip-review` (not currently supported, but a future flag) — never silently downgrade the status

### Two consecutive runs give different results
This should not happen with the binary rubric. If it does, the cause is almost always:
- A document was edited between runs
- The rubric's source files have additions (e.g., a new fixture appeared)
- A source code file was added/removed (affects code-only checks)

Diff the `references/review-checklist.md` against what was used in the previous run.

### Rubric check is missing a case I care about
Add it to `references/review-checklist.md` in the appropriate tier (Critical / Important / Nice-to-have). Choose Important by default — Critical checks block deploys, so the bar should be high. Document the new check's binary criterion explicitly, not as a vague guideline.

### Code-only checks fail because there's no source code yet
That's expected. The rubric's code-only checks (C-code-1, C-code-2, I-code-1, I-code-2, N-code-1) are skipped when no source files exist. Report status is computed only over the doc-level checks. This is documented in `references/review-checklist.md` — verify it's accurate.

### Status is `PASSED_WITH_WARNINGS` but the user wants it to pass cleanly
The Important warnings are real issues — fix them, don't hide them. Each warning has a `→ reason` annotation showing what to add or change. Apply the fix, re-run only that check, status becomes `PASSED`.
