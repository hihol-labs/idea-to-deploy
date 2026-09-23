#!/usr/bin/env python3
"""verify_risk_tier_default.py — G-001 RISK-TIER-1: proportionality is the default.

Audit 2026-09-22 (advisor x3): the proportionality machinery exists but is not applied —
30 high / 21 medium / 5 low units in the ledgers while the project template defaults to
`medium` and nothing forces `high` where it is non-negotiable. Contract of this unit:

  1. `docs/templates/itd/COMPLETION_POLICY.json` (what /adopt installs into a target
     project) carries `defaultRiskTier: low`; the methodology repository itself has no
     `.itd/COMPLETION_POLICY.json` and its built-in defaults in `hooks/completion-gate.sh`
     and `docs/templates/itd/itd_hygiene.py` stay `medium` (fail-closed for a project that
     never wrote a policy file).
  2. `skills/_shared/PROPORTIONALITY_POLICY.json` carries a machine-readable
     `strictClasses` object with exactly money / prod-config / db-schema / auth / secrets,
     each with non-empty `keywords`, non-empty `paths` and `tier: high`.
  3. `skills/task/scripts/itd_unit_log.py activate` forces `riskTier=high` when the goal
     text or the Allowed Change Areas of the neighbouring `.itd/SCOPE_LOCK.md` match a strict
     class, prints the class and the matched pattern, records `riskTierMatch` in
     `STATE.currentUnit` for every hit and `riskTierForced` only when a lower declared
     tier was raised; an existing but unreadable SCOPE_LOCK fails the activation closed;
     a policy without a valid `strictClasses` makes activate refuse before writing
     anything; `--risk-tier` stays mandatory (regression pin).
  4. ADR-011 records the default change; the oracle is registered in tests/run-all.sh.

`--mutations` copies the product tree into a temp dir, applies four independent
mutations and requires the suite to go RED on every one of them (lethality proof).
Run: sh skills/_shared/itd_py.sh tests/verify_risk_tier_default.py [--mutations]
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_CLASSES = {"money", "prod-config", "db-schema", "auth", "secrets"}

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_module(path: Path, name: str):
    # an explicit source loader: `hooks/completion-gate.sh` is Python behind a .sh suffix
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def activate(root: Path, goal: str, tier: str | None, scope_bullets: list[str] | None = None):
    """Run activate in a throwaway project; return (rc, stdout+stderr, STATE.currentUnit|None)."""
    with tempfile.TemporaryDirectory() as project:
        mem = Path(project) / ".itd-memory"
        mem.mkdir()
        if scope_bullets is not None:
            itd = Path(project) / ".itd"
            itd.mkdir()
            (itd / "SCOPE_LOCK.md").write_text(
                "# Scope Lock\n\n## Current Task\n\n- x\n\n## Allowed Change Areas\n\n"
                + "".join(f"- `{b}`\n" for b in scope_bullets)
                + "\n## Forbidden Change Areas\n\n- `skills/_shared/`\n", encoding="utf-8")
        cmd = [sys.executable, str(root / "skills" / "task" / "scripts" / "itd_unit_log.py"),
               "activate", "U-1", "--goal", goal, "--dir", str(mem)]
        if tier:
            cmd += ["--risk-tier", tier]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=project)
        state = mem / "STATE.json"
        cu = None
        if state.is_file():
            cu = json.loads(state.read_text(encoding="utf-8")).get("currentUnit")
        return r.returncode, r.stdout + r.stderr, cu


def suite(root: Path, quiet: bool = False) -> list[str]:
    """Return the list of failed check names for the product tree at `root`."""
    local_fails: list[str] = []

    def c(name: str, cond: bool, detail: str = "") -> None:
        if not quiet:
            check(name, cond, detail)
        if not cond:
            local_fails.append(name)

    # 1. template default low, built-in defaults medium, repo has no policy file or medium
    template = json.loads(read(root / "docs" / "templates" / "itd" / "COMPLETION_POLICY.json"))
    c("template-defaultRiskTier-low", template.get("defaultRiskTier") == "low",
      f"got {template.get('defaultRiskTier')!r}")
    c("template-strictRiskTiers-still-high", template.get("strictRiskTiers") == ["high"])
    gate_src = read(root / "hooks" / "completion-gate.sh")
    c("completion-gate-builtin-default-medium",
      re.search(r'DEFAULT_POLICY\s*=\s*\{[^}]*"defaultRiskTier":\s*"medium"', gate_src, re.S) is not None)
    hyg_src = read(root / "docs" / "templates" / "itd" / "itd_hygiene.py")
    c("hygiene-builtin-default-medium",
      re.search(r'DEFAULT_COMPLETION_POLICY\s*=\s*\{[^}]*"defaultRiskTier":\s*"medium"', hyg_src, re.S) is not None)
    # the methodology repository stays on the BUILT-IN medium default: introducing a repo
    # policy file would change which policy source governs it (PUB2 reviewer)
    c("methodology-repo-has-no-policy-file", not (root / ".itd" / "COMPLETION_POLICY.json").exists())
    # PUB4 F6: exercise the EFFECTIVE defaults, not only the source text - import both
    # resolvers and resolve a project with no policy file and no STATE/GOAL
    with tempfile.TemporaryDirectory() as empty:
        try:
            hyg = load_module(root / "docs" / "templates" / "itd" / "itd_hygiene.py", "itd_hygiene_for_oracle")
            c("hygiene-effective-default-medium",
              hyg.DEFAULT_COMPLETION_POLICY.get("defaultRiskTier") == "medium"
              and hyg.active_risk_tier(Path(empty), dict(hyg.DEFAULT_COMPLETION_POLICY)) == "medium")
        except Exception as exc:  # noqa: BLE001
            c("hygiene-effective-default-medium", False, repr(exc))
        try:
            gate = load_module(root / "hooks" / "completion-gate.sh", "completion_gate_for_oracle")
            policy = gate.load_policy(Path(empty))
            c("completion-gate-effective-default-medium",
              policy.get("defaultRiskTier") == "medium"
              and gate.active_risk_tier(Path(empty), policy) == "medium")
        except Exception as exc:  # noqa: BLE001
            c("completion-gate-effective-default-medium", False, repr(exc))

    # 2. strictClasses shape
    policy = json.loads(read(root / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"))
    sc = policy.get("strictClasses")
    c("strictClasses-present", isinstance(sc, dict))
    sc = sc if isinstance(sc, dict) else {}
    c("strictClasses-exact-set", set(sc) == REQUIRED_CLASSES, f"got {sorted(sc)}")
    for cls, spec in sorted(sc.items()):
        ok = (isinstance(spec, dict)
              and isinstance(spec.get("keywords"), list) and spec["keywords"]
              and all(isinstance(k, str) and k.strip() for k in spec["keywords"])
              and isinstance(spec.get("paths"), list) and spec["paths"]
              and all(isinstance(p, str) and p.strip() for p in spec["paths"])
              and spec.get("tier") == "high")
        c(f"strictClass-{cls}-well-formed", ok)
    c("riskRoutes-untouched", set(policy.get("riskRoutes") or {}) == {"low", "medium", "high"})

    # 3. shared loader: fail-closed on malformed policy, deterministic matcher
    loader_path = root / "skills" / "_shared" / "itd_risk_classes.py"
    c("loader-module-present", loader_path.is_file())
    if loader_path.is_file():
        rc_mod = load_module(loader_path, "itd_risk_classes_under_test")
        classes: dict = {}  # a rejected policy leaves the matcher empty and the checks below RED
        try:
            classes = rc_mod.load_strict_classes(policy)
            c("loader-accepts-shipped-policy", set(classes) == REQUIRED_CLASSES)
        except Exception as exc:  # noqa: BLE001
            c("loader-accepts-shipped-policy", False, repr(exc))
        for label, broken in (
            ("missing", {k: v for k, v in policy.items() if k != "strictClasses"}),
            ("extra-class", {**policy, "strictClasses": {**sc, "ui": {"keywords": ["css"], "paths": ["*.css"], "tier": "high"}}}),
            ("tier-not-high", {**policy, "strictClasses": {**sc, "auth": {**sc.get("auth", {}), "tier": "medium"}}}),
            ("empty-keywords", {**policy, "strictClasses": {**sc, "money": {**sc.get("money", {}), "keywords": []}}}),
        ):
            try:
                rc_mod.load_strict_classes(broken)
                c(f"loader-rejects-{label}", False, "no exception")
            except Exception:  # noqa: BLE001
                c(f"loader-rejects-{label}", True)
        hit = rc_mod.match_strict_class("Add refund endpoint for payments", "", classes) if loader_path.is_file() else None
        c("matcher-keyword-money", bool(hit) and hit[0] == "money", repr(hit))
        hit = rc_mod.match_strict_class("Rename helper in docs generator", "", classes)
        c("matcher-neutral-none", hit is None, repr(hit))
        hit = rc_mod.match_strict_class("Tokens telemetry for the goal schema oracle", "", classes)
        c("matcher-no-false-positive-on-token-schema", hit is None, repr(hit))
        scope = ("# Scope Lock\n\n## Current Task\n\n- x\n\n## Allowed Change Areas\n\n"
                 "- `db/migrations/0004_add_index.sql`\n\n## Forbidden Change Areas\n\n- `app/payments/`\n")
        hit = rc_mod.match_strict_class("Reindex", scope, classes)
        c("matcher-path-db-schema", bool(hit) and hit[0] == "db-schema" and hit[3] == "SCOPE_LOCK", repr(hit))
        # a strict path listed only under Forbidden Change Areas must NOT force the tier
        scope_forbidden_only = ("# Scope Lock\n\n## Allowed Change Areas\n\n- `docs/README.md`\n\n"
                                "## Forbidden Change Areas\n\n- `db/migrations/`\n")
        hit = rc_mod.match_strict_class("Reindex", scope_forbidden_only, classes)
        c("matcher-forbidden-area-ignored", hit is None, repr(hit))
        # checker c2 F1: dotfiles and multi-dot names must tokenize as paths
        for goal_txt, cls_exp in (("rotate values in .env", "secrets"),
                                  ("copy .env.example", "secrets"),
                                  ("tune app.prod.yaml limits", "prod-config")):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-dotfile-{cls_exp}-{goal_txt.split()[-1]}", bool(hit) and hit[0] == cls_exp, repr(hit))
        # PUB3 F3: Markdown presentation around a path must not hide it from the matcher
        for area, cls_exp in (("**db/schema.rb**", "db-schema"), ("[src/auth/login.py]", "auth"),
                              ("~~config/production.yaml~~", "prod-config"), ("_migrations/0001.sql_", "db-schema"),
                              ("**`payments/refund.py`**", "money")):
            scope_md = f"# Scope Lock\n\n## Allowed Change Areas\n\n- {area}\n\n## Forbidden Change Areas\n\n- x\n"
            hit = rc_mod.match_strict_class("Reindex", scope_md, classes)
            c(f"matcher-markup-wrapped-path-{cls_exp}-{area.strip('*[]~_`')[:12]}",
              bool(hit) and hit[0] == cls_exp and hit[3] == "SCOPE_LOCK", f"{area!r} -> {hit!r}")
        # checker c14: markup followed by sentence punctuation, in either nesting order
        for area, cls_exp in (("**db/schema.rb**.", "db-schema"), ("[db/schema.rb].", "db-schema"),
                              ("_config/production.yaml_?", "prod-config"), ("**payments/refund.py**?", "money")):
            scope_md = f"# Scope Lock\n\n## Allowed Change Areas\n\n- {area}\n\n## Forbidden Change Areas\n\n- x\n"
            hit = rc_mod.match_strict_class("Reindex", scope_md, classes)
            c(f"matcher-markup-then-punct-{cls_exp}-{area.strip('*[]~_.?')[:12]}",
              bool(hit) and hit[0] == cls_exp and hit[3] == "SCOPE_LOCK", f"{area!r} -> {hit!r}")
        # checker c14: the underscore guard is pinned on the token itself, not only on "no hit"
        toks = rc_mod._path_tokens("wire __init__.py and _config.yml and **_db/schema.rb_**. and **.env**.")
        c("matcher-dunder-tokens-preserved", "__init__.py" in toks and "_config.yml" in toks
          and "db/schema.rb" in toks and ".env" in toks, repr(toks))
        hit = rc_mod.match_strict_class("wire __init__.py exports", "", classes)
        c("matcher-dunder-file-not-mangled", hit is None, repr(hit))
        # checker c2 F2: keywords apply to Allowed Change Areas too, not only paths
        scope_kw = "# Scope Lock\n\n## Allowed Change Areas\n\n- payment refund handler logic\n\n## Forbidden Change Areas\n\n- x\n"
        hit = rc_mod.match_strict_class("tidy handler", scope_kw, classes)
        c("matcher-keyword-in-allowed-areas", bool(hit) and hit[0] == "money" and hit[3] == "SCOPE_LOCK", repr(hit))
        # checker c2 F3: '_' and digits end a word; letters do not
        for goal_txt, exp in (("refactor auth_service wiring", "auth"), ("expose payments_api", "money"),
                              ("OAuth2 callback", "auth"), ("clean unauthorized helper naming", None)):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-boundary-{goal_txt.split()[0]}", (hit[0] if hit else None) == exp, repr(hit))
        # checker c2 F4: docs/fixture paths that used to force high for no reason
        for goal_txt in ("document skills/deploy/SKILL.md", "rename tests/fixtures/author.py"):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-no-false-positive-{goal_txt.split('/')[-1]}", hit is None, repr(hit))
        c("matcher-no-dead-token-regex", "_TOKEN_RE" not in read(loader_path))
        # checker c3 finding 1: repo-root infra paths must hit as well as nested ones
        for goal_txt, cls_exp in (("edit k8s/deployment.yaml", "prod-config"), ("bump helm/values.yaml", "prod-config"),
                                  ("fix deploy/run.sh", "prod-config"), ("tune terraform/prod.tfvars", "prod-config"),
                                  ("tidy auth.py", "auth"), ("rotate keys/id_rsa", "secrets"),
                                  ("edit settings/production.py", "prod-config"), ("touch Dockerfile.prod", "prod-config"),
                                  ("rename .github/workflows/deploy.yml", "prod-config"), ("read API_KEY from env", "secrets")):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-root-or-artefact-{goal_txt.split()[-1]}", bool(hit) and hit[0] == cls_exp, repr(hit))
        # checker c4: plain migration goals, schema artefacts, payment providers must force high
        for goal_txt, cls_exp in (("add migration for users table", "db-schema"),
                                  ("create Django migration for orders", "db-schema"),
                                  ("новая миграция для таблицы users", "db-schema"),
                                  ("edit db/schema.rb", "db-schema"), ("update prisma/schema.prisma", "db-schema"),
                                  ("Stripe webhook handler", "money"), ("integrate YooKassa", "money")):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-c4-{goal_txt.split()[-1]}", bool(hit) and hit[0] == cls_exp, repr(hit))
        # checker c5: camelCase identifiers on the Vue/TS stack, Rails migrate dir, token vocab
        for goal_txt, cls_exp in (("fix token refresh in AuthService", "auth"), ("tidy src/stores/authStore.ts", "auth"),
                                  ("restyle src/views/LoginView.vue", "auth"), ("extract useAuth.ts composable", "auth"),
                                  ("cache getApiKey result", "secrets"), ("add db/migrate/20260101_add_users.rb", "db-schema"),
                                  ("rotate the Telegram bot token", "secrets"), ("signup form validation", "auth")):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-c5-{goal_txt.split()[-1]}", bool(hit) and hit[0] == cls_exp, repr(hit))
        scope_camel = "# Scope Lock\n\n## Allowed Change Areas\n\n- `src/stores/authStore.ts`\n\n## Forbidden Change Areas\n\n- x\n"
        hit = rc_mod.match_strict_class("tidy the store", scope_camel, classes)
        c("matcher-c5-scope-camel-path", bool(hit) and hit[0] == "auth", repr(hit))
        # checker c6: snake_case / SCREAMING_CASE multi-word keys, ACRONYMWord, stems
        for goal_txt, cls_exp in (("persist access_token in redis", "secrets"), ("read BOT_TOKEN from settings", "secrets"),
                                  ("rotate the refresh-token", "secrets"), ("add JWTBearer dependency", "auth"),
                                  ("wrap JWTAuth middleware", "auth"), ("mark route authenticated", "auth"),
                                  ("предоплата за заказ", "money")):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-c6-{goal_txt.split()[-1]}", bool(hit) and hit[0] == cls_exp, repr(hit))
        # checker c7: whitespace runs, alternate scope headings, declared-stack vocabulary
        hit = rc_mod.match_strict_class("rotate the bot\n  token", "", classes)
        c("matcher-c7-line-wrap", bool(hit) and hit[0] == "secrets", repr(hit))
        hit = rc_mod.match_strict_class("run ALTER\tTABLE users", "", classes)
        c("matcher-c7-tab", bool(hit) and hit[0] == "db-schema", repr(hit))
        scope_in = "# Scope\n\n### In scope:\n\n- `db/migrations/0009.sql`\n\n## Out of scope\n\n- x\n"
        hit = rc_mod.match_strict_class("reindex", scope_in, classes)
        c("matcher-c7-in-scope-heading", bool(hit) and hit[0] == "db-schema" and hit[3] == "SCOPE_LOCK", repr(hit))
        for goal_txt, cls_exp in (("handle pre_checkout_query", "money"), ("sell Telegram Stars packs", "money"),
                                  ("read MinIO access key from env", "secrets"), ("load TELEGRAM_TOKEN", "secrets"),
                                  ("wire get_current_user dependency", "auth"), ("edit app/core/security.py", "auth"),
                                  ("подключить ЮKassa", "money")):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-c7-{goal_txt.split()[-1]}", bool(hit) and hit[0] == cls_exp, repr(hit))
        # PUB4 F3: a fence line with an info string is content, not a closer (CommonMark)
        scope_info = ("# Scope Lock\n\n## Allowed Change Areas\n\n```bash\n```not-a-closing-fence\n"
                      "## Forbidden Change Areas\n```\n\n- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n")
        hit = rc_mod.match_strict_class("tidy the handler", scope_info, classes)
        c("matcher-pub4-info-string-fence-not-a-closer", bool(hit) and hit[0] == "money" and hit[3] == "SCOPE_LOCK", repr(hit))
        # PUB5 F3: ATX closing hashes and inline presentation around the heading title
        for idx, heading in enumerate(("## Allowed Change Areas ##", "## **In scope**", "## _Allowed Change Areas_:",
                                       "### `In scope` ###", "##   In   scope   :  ", "## **Allowed Change Areas:**"), 1):
            scope_h = f"# Scope Lock\n\n{heading}\n\n- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n"
            hit = rc_mod.match_strict_class("tidy the handler", scope_h, classes)
            c(f"matcher-pub5-heading-form-{idx}-{heading.strip('#* _:`').replace(' ', '-')[:24]}",
              bool(hit) and hit[0] == "money" and hit[3] == "SCOPE_LOCK", f"{heading!r} -> {hit!r}")
        # a heading that only CONTAINS the words is not a scope heading
        scope_not = "# Scope Lock\n\n## Not in scope\n\n- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n"
        c("matcher-pub5-not-in-scope-heading-ignored", rc_mod.match_strict_class("tidy the handler", scope_not, classes) is None)
        # checker c17: a line starting with inline triple-backtick code is NOT a fence opener
        scope_inline = ("# Scope Lock\n\n```rm -rf``` is forbidden here\n\n## Allowed Change Areas\n\n"
                        "- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n")
        hit = rc_mod.match_strict_class("tidy the handler", scope_inline, classes)
        c("matcher-c17-inline-backtick-line-not-a-fence-opener", bool(hit) and hit[0] == "money", repr(hit))
        scope_tilde_inline = ("# Scope Lock\n\n## Allowed Change Areas\n\n~~~text with `code`\n## Not a heading\n~~~\n\n"
                              "- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n")
        hit = rc_mod.match_strict_class("tidy the handler", scope_tilde_inline, classes)
        c("matcher-c17-tilde-info-string-with-backtick-still-a-fence", bool(hit) and hit[0] == "money", repr(hit))
        # PUB4 F4: a nested allowed heading never discards what was collected; a later
        # deeper heading stays inside; a second allowed section unions with the first
        areas = rc_mod.allowed_areas("# Scope Lock\n\n## Allowed Change Areas\n\n- `app/billing/stripe.py`\n\n"
                                     "### In scope\n\n- docs\n\n### Backend\n\n- `app/auth/router.py`\n\n"
                                     "## Forbidden Change Areas\n\n- `db/migrations/`\n")
        c("matcher-pub4-nested-allowed-heading-keeps-content",
          "stripe.py" in areas and "router.py" in areas and "migrations" not in areas, repr(areas))
        areas = rc_mod.allowed_areas("# Scope Lock\n\n## Allowed Change Areas\n\n- docs/x.md\n\n"
                                     "## Forbidden Change Areas\n\n- `db/migrations/`\n\n## In scope\n\n- `app/billing/stripe.py`\n")
        c("matcher-pub4-second-allowed-section-unions",
          "docs/x.md" in areas and "stripe.py" in areas and "migrations" not in areas, repr(areas))
        # checker c8: sub-headings and fenced code do not end the scope section
        scope_nested = ("# Scope Lock\n\n## Allowed Change Areas\n\n### Backend\n\n- `app/auth/router.py`\n\n"
                        "### Frontend\n\n- `src/views/Home.vue`\n\n## Forbidden Change Areas\n\n- x\n")
        hit = rc_mod.match_strict_class("tidy routers", scope_nested, classes)
        c("matcher-c8-nested-subheading", bool(hit) and hit[0] == "auth" and hit[3] == "SCOPE_LOCK", repr(hit))
        scope_fenced = ("# Scope Lock\n\n## Allowed Change Areas\n\n```bash\n# run tests\npytest\n```\n\n"
                        "- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n")
        hit = rc_mod.match_strict_class("tidy the handler", scope_fenced, classes)
        c("matcher-c8-fenced-comment", bool(hit) and hit[0] == "money" and hit[3] == "SCOPE_LOCK", repr(hit))
        scope_mismatch = ("# Scope Lock\n\n## Allowed Change Areas\n\n```bash\n~~~\n# run\n```\n\n"
                          "- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n")
        hit = rc_mod.match_strict_class("tidy the handler", scope_mismatch, classes)
        c("matcher-pub2-mismatched-fence-marker-stays-fenced", bool(hit) and hit[0] == "money", repr(hit))
        scope_longer = ("# Scope Lock\n\n## Allowed Change Areas\n\n````\n```\n# run\n````\n\n"
                        "- `app/billing/stripe.py`\n\n## Forbidden Change Areas\n\n- x\n")
        hit = rc_mod.match_strict_class("tidy the handler", scope_longer, classes)
        c("matcher-pub2-shorter-marker-does-not-close", bool(hit) and hit[0] == "money", repr(hit))
        scope_ends = ("# Scope Lock\n\n## Allowed Change Areas\n\n- `docs/README.md`\n\n## Forbidden Change Areas\n\n"
                      "- `app/billing/stripe.py`\n")
        hit = rc_mod.match_strict_class("tidy docs", scope_ends, classes)
        c("matcher-c8-same-level-heading-ends-section", hit is None, repr(hit))
        for goal_txt in ("reproduce on the host checkout", "git checkout the release branch"):
            hit = rc_mod.match_strict_class(goal_txt, "", classes)
            c(f"matcher-git-checkout-not-money-{goal_txt.split()[0]}", hit is None, repr(hit))
        hit = rc_mod.match_strict_class("починить оплату заказа", "", classes)
        c("matcher-russian-stem-money", bool(hit) and hit[0] == "money", repr(hit))
    # checker c2 F5: /goal activation must not inherit a stale riskTierForced
    gv_path = root / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
    c("goal-activate-drops-stale-forced-flag", read(gv_path).count('cur.pop("riskTierForced", None)') >= 2)
    # behavioural pin (checker c4 minor): a STATE carrying a stale riskTierForced from a
    # /task unit loses it when a goal unit is projected as activated
    try:
        gv_mod = load_module(gv_path, "itd_goal_verify_under_test")
        with tempfile.TemporaryDirectory() as tmp:
            mem = Path(tmp) / ".itd-memory"; mem.mkdir()
            goal_path = mem / "GOAL.json"
            goal_path.write_text(json.dumps({"version": 1, "goal": "g", "status": "active", "createdAt": "2026-01-01T00:00:00Z",
                                             "updatedAt": "2026-01-01T00:00:00Z", "currentUnitId": "",
                                             "units": [{"id": "G-9", "criterion": "c", "verificationCommand": "true",
                                                        "status": "pending", "riskTier": "low"}]}), encoding="utf-8")
            (mem / "STATE.json").write_text(json.dumps({"version": 1, "currentUnit": {"id": "U-old", "status": "verified",
                                                        "riskTier": "high", "riskTierForced": {"declared": "low", "class": "money", "match": "x"},
                                                        "riskTierMatch": {"class": "money", "match": "x"}}}), encoding="utf-8")
            unit = json.loads(goal_path.read_text(encoding="utf-8"))["units"][0]
            proj = gv_mod.state_projection(goal_path, unit, "activated")
            gv_mod.write_state_projection(proj, goal_path, unit, "activated")
            cu = json.loads((mem / "STATE.json").read_text(encoding="utf-8")).get("currentUnit") or {}
            c("goal-activate-projection-has-no-stale-forced-flag",
              cu.get("id") == "G-9" and "riskTierForced" not in cu and "riskTierMatch" not in cu, repr(cu)[:200])
            # non-activation branch (PUB2): a 'verified' projection over a stale forced note
            (mem / "STATE.json").write_text(json.dumps({"version": 1, "currentUnit": {"id": "G-9", "status": "in_progress",
                                                        "riskTier": "high", "riskTierForced": {"declared": "low", "class": "money", "match": "x"},
                                                        "riskTierMatch": {"class": "money", "match": "x"}}}), encoding="utf-8")
            proj = gv_mod.state_projection(goal_path, unit, "verified")
            gv_mod.write_state_projection(proj, goal_path, unit, "verified")
            cu2 = json.loads((mem / "STATE.json").read_text(encoding="utf-8")).get("currentUnit") or {}
            c("goal-verified-projection-has-no-stale-forced-flag",
              cu2.get("id") == "G-9" and cu2.get("status") == "verified" and "riskTierForced" not in cu2
              and "riskTierMatch" not in cu2, repr(cu2)[:200])
    except Exception as exc:  # noqa: BLE001
        c("goal-activate-projection-has-no-stale-forced-flag", False, repr(exc)[:200])

    # 4. activate wiring
    rc, out, cu = activate(root, "тестовый юнит", None)
    c("activate-without-risk-tier-refused", rc != 0 and "--risk-tier" in out and cu is None)
    rc, out, cu = activate(root, "Add refund endpoint for payments", "low")
    forced = (cu or {}).get("riskTierForced") or {}
    c("activate-money-goal-forced-high",
      rc == 0 and (cu or {}).get("riskTier") == "high" and forced.get("declared") == "low"
      and forced.get("class") == "money" and "money" in out
      and "keyword 'payments'" in out and "in goal" in out, f"rc={rc} out={out!r} cu={cu}")
    rc, out, cu = activate(root, "Rename helper in docs generator", "low")
    c("activate-neutral-goal-stays-low",
      rc == 0 and (cu or {}).get("riskTier") == "low" and "riskTierForced" not in (cu or {}),
      f"rc={rc} cu={cu}")
    rc, out, cu = activate(root, "Reindex the catalogue", "medium", ["db/migrations/0004_add_index.sql"])
    forced = (cu or {}).get("riskTierForced") or {}
    c("activate-scope-lock-path-forced-high",
      rc == 0 and (cu or {}).get("riskTier") == "high" and forced.get("class") == "db-schema"
      and "SCOPE_LOCK" in out, f"rc={rc} out={out!r} cu={cu}")
    rc, out, cu = activate(root, "Reindex the catalogue", "medium", ["docs/CATALOGUE.md"])
    c("activate-scope-lock-neutral-path-stays-medium",
      rc == 0 and (cu or {}).get("riskTier") == "medium" and "riskTierForced" not in (cu or {}),
      f"rc={rc} cu={cu}")
    rc, out, cu = activate(root, "rotate the OAuth client secret", "unknown")
    c("activate-unknown-plus-strict-forced-high",
      rc == 0 and (cu or {}).get("riskTier") == "high", f"rc={rc} cu={cu}")
    rc, out, cu = activate(root, "Add refund endpoint for payments", "high")
    c("activate-declared-high-records-match-not-forced",
      rc == 0 and (cu or {}).get("riskTier") == "high" and "riskTierForced" not in (cu or {})
      and ((cu or {}).get("riskTierMatch") or {}).get("class") == "money" and "matched" in out,
      f"rc={rc} out={out!r} cu={cu}")
    rc, out, cu = activate(root, "Add refund endpoint for payments", "low")
    c("activate-forced-also-records-match",
      rc == 0 and ((cu or {}).get("riskTierMatch") or {}).get("class") == "money"
      and ((cu or {}).get("riskTierForced") or {}).get("declared") == "low", f"cu={cu}")
    rc, out, cu = activate(root, "Rename helper in docs generator", "low")
    c("activate-neutral-goal-no-match-note", rc == 0 and "riskTierMatch" not in (cu or {}), f"cu={cu}")
    # F5 (PUB2): an EXISTING but unreadable SCOPE_LOCK fails closed - nothing is written
    with tempfile.TemporaryDirectory() as project:
        mem = Path(project) / ".itd-memory"; mem.mkdir()
        itd = Path(project) / ".itd"; itd.mkdir()
        (itd / "SCOPE_LOCK.md").write_bytes(b"\xff\xfe## Allowed Change Areas\n- `app/billing/x.py`\n")
        r = subprocess.run([sys.executable, str(root / "skills" / "task" / "scripts" / "itd_unit_log.py"),
                            "activate", "U-1", "--goal", "tidy the handler", "--risk-tier", "low", "--dir", str(mem)],
                           capture_output=True, text=True, timeout=30, cwd=project)
        c("activate-unreadable-scope-lock-fails-closed",
          r.returncode != 0 and "SCOPE_LOCK" in (r.stdout + r.stderr)
          and not (mem / "STATE.json").exists() and not (mem / "events.jsonl").exists(),
          f"rc={r.returncode} out={(r.stdout + r.stderr)[:160]!r}")
    with tempfile.TemporaryDirectory() as project:
        mem = Path(project) / ".itd-memory"; mem.mkdir()
        itd = Path(project) / ".itd"; itd.mkdir()
        os.symlink(itd / "missing-target.md", itd / "SCOPE_LOCK.md")   # dangling symlink
        r = subprocess.run([sys.executable, str(root / "skills" / "task" / "scripts" / "itd_unit_log.py"),
                            "activate", "U-1", "--goal", "tidy the handler", "--risk-tier", "low", "--dir", str(mem)],
                           capture_output=True, text=True, timeout=30, cwd=project)
        c("activate-dangling-scope-lock-symlink-fails-closed",
          r.returncode != 0 and not (mem / "STATE.json").exists(), f"rc={r.returncode}")

    # PUB4 F5: a malformed strictClasses policy fails the ACTIVATION closed - not only the
    # loader - and nothing is written (STATE/events absent)
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        shutil.copytree(root / "skills", tree / "skills")
        pol = tree / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"
        broken = json.loads(pol.read_text(encoding="utf-8")); broken.pop("strictClasses", None)
        pol.write_text(json.dumps(broken), encoding="utf-8")
        project = Path(tmp) / "project"; mem = project / ".itd-memory"; mem.mkdir(parents=True)
        r = subprocess.run([sys.executable, str(tree / "skills" / "task" / "scripts" / "itd_unit_log.py"),
                            "activate", "U-1", "--goal", "Add refund endpoint for payments", "--risk-tier", "low",
                            "--dir", str(mem)], capture_output=True, text=True, timeout=30, cwd=project)
        c("activate-malformed-policy-fails-closed-no-write",
          r.returncode != 0 and "strictClasses" in (r.stdout + r.stderr)
          and not (mem / "STATE.json").exists() and not (mem / "events.jsonl").exists(),
          f"rc={r.returncode} out={(r.stdout + r.stderr)[:160]!r}")

    # 5. ADR + registration
    adr = root / "docs" / "adr" / "ADR-011-default-risk-tier-low.md"
    c("adr-011-present", adr.is_file())
    if adr.is_file():
        adr_text = read(adr)
        c("adr-011-names-both-changes", "defaultRiskTier" in adr_text and "strictClasses" in adr_text)
    c("oracle-registered-in-run-all", "verify_risk_tier_default" in read(root / "tests" / "run-all.sh"))
    return local_fails


def copy_product(dst: Path) -> None:
    for rel in ("skills", "docs/templates/itd", "docs/adr", "hooks"):  # skills/ includes goal/scripts
        shutil.copytree(ROOT / rel, dst / rel)
    (dst / "tests").mkdir()
    shutil.copy2(ROOT / "tests" / "run-all.sh", dst / "tests" / "run-all.sh")


def mutate_policy(root: Path, fn) -> None:
    p = root / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"
    policy = json.loads(read(p))
    fn(policy)
    p.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mutations() -> None:
    def m_no_strict(policy: dict) -> None:
        policy.pop("strictClasses", None)

    def m_money_keywords_empty(policy: dict) -> None:
        policy["strictClasses"]["money"]["keywords"] = []

    def m_unit_log_no_enforcement(root: Path) -> None:
        p = root / "skills" / "task" / "scripts" / "itd_unit_log.py"
        src = read(p)
        marker = "forced = RC.match_strict_class("
        assert marker in src, "enforcement marker missing in unit_log"
        p.write_text(src.replace(marker, "forced = None and RC.match_strict_class(", 1), encoding="utf-8")

    def m_template_medium(root: Path) -> None:
        p = root / "docs" / "templates" / "itd" / "COMPLETION_POLICY.json"
        t = json.loads(read(p))
        t["defaultRiskTier"] = "medium"
        p.write_text(json.dumps(t, indent=2) + "\n", encoding="utf-8")

    cases = (
        ("strictClasses-removed", lambda r: mutate_policy(r, m_no_strict)),
        ("money-keywords-emptied", lambda r: mutate_policy(r, m_money_keywords_empty)),
        ("unit-log-enforcement-disabled", m_unit_log_no_enforcement),
        ("template-default-back-to-medium", m_template_medium),
    )
    for label, apply in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "product"
            copy_product(root)
            apply(root)
            red = suite(root, quiet=True)
            check(f"mutation-{label}-lethal", bool(red), "suite stayed green")


def main() -> int:
    baseline = suite(ROOT)
    if "--mutations" in sys.argv[1:]:
        if baseline:
            print("skip mutations: baseline suite is red")
        else:
            mutations()
    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
