#!/usr/bin/env python3
"""verify_tier_wording.py — TIER-WORDING-2: a path-list scope takes the goal text out of the floor.

TIER-SOURCE-1 closed the tests-only half of BACKLOG P1 2026-09-25 ("the strict-class tier depends
on the wording of the goal, not on the code"); for a scope with a non-test path the same change
still went `low` or `high` by the words its goal happened to use. Owner rule (variant A,
`.itd/DECISIONS.md` 2026-10-01): when the Current Task opens with the unit being activated and
every non-blank line of the Allowed Change Areas is one list item with exactly one path - a test
path or one concrete file - the goal text (keywords and paths) is not a strict-class source. A
strict path or keyword inside the areas still forces `high`. A directory, a glob, an
extensionless name (a dotfile without an extension included), an extension outside the closed
set, prose, two paths, `..`, a backslash, a SCOPE_LOCK whose headings leave the plain layout, no
SCOPE_LOCK and a scope of another unit keep the goal as a source.

Contract of this oracle (all fixtures are synthetic):

  1. `is_file_path` / `path_list` accept the declared files and refuse directories, globs,
     extensionless names, unknown extensions, `..` anywhere in the token, non-ASCII look-alikes
     and an empty scope (fail-closed, never vacuous); every accepted file is a token the strict
     path matcher reads (`_path_tokens`), and the extension set is pinned as a closed list.
  2. Pairs - a template goal vs a detailed description with a strict word or a strict path - get
     one tier over the same non-test Allowed Change Areas, through `match_strict_class` and end
     to end through `skills/task/scripts/itd_unit_log.py activate` (declared `low` stays `low`,
     declared `medium` stays `medium`, the set-aside hit is recorded as `riskTierExempt` with the
     path-list reason, no `riskTierForced`). A control check proves each pair's detailed goal does
     hit a strict class without the scope, so the pair exercises the rule.
  3. The floor stays: a strict path or keyword inside a path-list scope forces `high` for a lower
     declared tier (the set-aside goal hit is recorded next to it), and every scope outside the
     grammar, a SCOPE_LOCK outside the plain layout (`hooks/wip-gate.sh` reads an item the
     strict reader did not, or a heading only starts with a scope title - review r1, checker c1,
     BACKLOG P2 2026-09-26; `gate_items` mirrors the hook's reader and a drift guard pins it),
     a scope of another unit (activate prints a hint) and a missing SCOPE_LOCK keep the goal hit
     and record no `riskTierExempt`.
  4. The docs name the rule and the oracle is registered in tests/run-all.sh.

`--mutations` copies the product tree into a temp dir, applies independent mutations (including
the pre-fix bytes of the two changed modules from commit 90c4a16) and requires the suite to go RED
on every one of them.
Run: sh skills/_shared/itd_py.sh tests/verify_tier_wording.py [--mutations]
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX_COMMIT = "90c4a16"
TEMPLATE = "Change {path} ({doc}); behaviour per the unit contract"

# (label, raw Allowed Change Areas lines, template goal, detailed goal, class hit by the detailed goal)
PAIRS = (
    ("fx-money-keyword", ["- `src/fx/rates.py`"],
     TEMPLATE.format(path="src/fx/rates.py", doc="Convert an amount between two currencies at the daily rate"),
     "Round the converted amount of every customer payment before it is settled", "money"),
    ("notify-auth-keyword", ["- `app/notify.py`", "- `tests/unit/test_notify.py` (new)"],
     TEMPLATE.format(path="app/notify.py", doc="Send a text message to a user"),
     "Retry the notifier that sends the login code and the password reset link", "auth"),
    ("report-money-keyword", ["- lib/report.py (updated)"],
     TEMPLATE.format(path="lib/report.py", doc="Build a monthly summary"),
     "Sort the monthly report that lists invoices, refunds and the ledger balance", "money"),
    ("price-money-goal-path", ["- `src/fmt/price.py`"],
     TEMPLATE.format(path="src/fmt/price.py", doc="Format a price with two decimals"),
     "Align the price formatter with the one in src/checkout_utils/fmt.py", "money"),
    ("sverka-money-ru", ["* `src/sverka.py`"],
     TEMPLATE.format(path="src/sverka.py", doc="Сверка двух выгрузок по номеру заказа"),
     "Ускорить сверку оплат с выгрузкой маркетплейса", "money"),
    ("client-secrets-keyword", ["- `web/src/client.ts`", "- `web/src/retry.ts`"],
     TEMPLATE.format(path="web/src/client.ts", doc="HTTP client with retries"),
     "Retry the HTTP client that attaches the access token to every request", "secrets"),
    ("guide-db-schema-numbered", ["1. `docs/guide.md` (updated)", "2) scripts/build.sh (new)"],
     TEMPLATE.format(path="docs/guide.md", doc="Build guide"),
     "Describe the alembic migration step in the build guide", "db-schema"),
)
HOT_GOAL = PAIRS[0][3]          # a goal that hits `money` on its own
NEUTRAL_GOAL = TEMPLATE.format(path="src/gw.py", doc="Gateway adapter")
LIST_LINES = ["- `src/fx/rates.py`"]

FILE_PATHS = ("src/fx/rates.py", "a.py", "./src/a.ts", "/src/a.py", "docs/guide.md", "scripts/build.sh",
              "config/app.yaml", "web/src/App.vue", "pkg/__init__.py", "data/rates.json",
              ".eslintrc.json", "src/My-File_2.py", "SRC/A.PY", "src/a.test.ts", "src/.hidden.py")
NOT_FILE_PATHS = ("", "src/", "src/fx", "Dockerfile", "Makefile", ".gitignore", ".github", "src/*",
                  "src/*.py", "src/a?.py", "**/*", "*", "/", "./", ".", "..", "src/../a.py", "../a.py",
                  "src\\a.py", " src/a.py", "src/a.py ", "\u00a0src/a.py", "src/a\u3164b.py",
                  "src/\u0442.py", "src/a.p\u0443", "src/a.py|src/b.py", "src/a.py,src/b.py",
                  "src/a.py+src/b.py", "nginx/conf.d", "v1.2", "src/a.", "src/.py", "data/rates.bin",
                  "src/a.py/", "a.b.unknownext", "\u201csrc/a.py\u201d",
                  # `..` anywhere: `_path_tokens` does not read a slash-less double-dot name
                  "x..sql", "..sql", "nginx..conf", "app.prod..yml", "src/a..py", "a...py")
# the closed set beyond the code extensions of TIER-SOURCE-1 (`_CODE_EXTS`), pinned literally
EXTRA_FILE_EXTS = ("bash", "bat", "c", "cc", "cfg", "cmd", "conf", "cpp", "css", "csv", "dart", "ex",
                   "exs", "h", "hpp", "htm", "html", "ini", "json", "jsonl", "less", "lock", "lua", "m",
                   "md", "pl", "ps1", "r", "rst", "sass", "scala", "scss", "sh", "sql", "toml", "txt",
                   "xml", "yaml", "yml")

PATH_LIST = (
    ("- `src/a.py`", True),
    ("- src/a.py (new)\n- `tests/test_a.py` (updated)", True),
    ("- `tests/`\n- `src/a.py`", True),
    ("- `tests/*`\n\n- `src/a.py`", True),
    ("1. `docs/guide.md`\n2) scripts/build.sh", True),
    ("\t- `src/a.py`\t(NEW)", True),
    ("", False),
    ("\n\n", False),
    ("- the code", False),
    ("- `src/`", False),
    ("- `src/fx`", False),
    ("- `src/*`", False),
    ("- `src/*.py`", False),
    ("- `Dockerfile`", False),
    ("- `.gitignore`", False),
    ("- `src/a.py` and more", False),
    ("- `src/a.py` - the helper", False),
    ("- `src/a.py` `src/b.py`", False),
    ("- src/a.py, src/b.py", False),
    ("- src/a.py|src/b.py", False),
    ("- `src/a.py` (created)", False),
    ("- `src/a.py`\n  continuation", False),
    ("- `src/a.py`\n### Backend\n- `src/b.py`", False),
    ("- `src/a.py`\n```\nrm -rf src\n```", False),
    ("Files:\n- `src/a.py`", False),
    ("- **src/a.py**", False),
    ("- `src/a.py`.", False),
    ("- `src/../a.py`", False),
    ("- src\\a.py", False),
    ("- `\u00a0src/a.py`", False),
    ("- src/a.py\u3164src/b.py", False),
    ("- `src/a.py`\n- `src/`", False),
)

# (label, raw Allowed Change Areas lines, expected class): a path-list scope whose own path or
# keyword is strict - high stays high whatever the goal says
FLOOR_IN_LIST = (
    ("money-path", ["- `src/payments/gateway.py`"], "money"),
    ("auth-path", ["- `app/auth/session.py`"], "auth"),
    ("db-schema-path", ["- `db/migrations/0004_add.sql`"], "db-schema"),
    ("prod-config-path", ["- `deploy/app.prod.yaml`"], "prod-config"),
    ("money-keyword-in-file-name", ["- `src/refund_rules.py`"], "money"),
    ("auth-keyword-in-file-name", ["- `src/fx/rates.py`", "- `web/src/login_form.vue`"], "auth"),
)

# (label, raw Allowed Change Areas lines): outside the grammar - HOT_GOAL keeps forcing `money`
FLOOR_NOT_LIST = (
    ("prose-in-item", ["- `src/fx/rates.py` - the rounding helper"]),
    ("pathless-item", ["- the rate converter"]),
    ("two-paths-in-item", ["- `src/fx/rates.py` `src/fx/table.py`"]),
    ("two-paths-comma", ["- src/fx/rates.py, src/fx/table.py"]),
    ("glued-token", ["- src/fx/rates.py|src/fx/table.py"]),
    ("dotdot-escape", ["- `src/fx/../rates.py`"]),
    ("backslash-path", ["- src\\fx\\rates.py"]),
    ("glob-everything", ["- `**/*`"]),
    ("glob-root", ["- `/`"]),
    ("glob-dot", ["- `.`"]),
    ("glob-under-directory", ["- `src/*`"]),
    ("glob-of-files", ["- `src/fx/*.py`"]),
    ("directory-trailing-slash", ["- `src/`"]),
    ("directory-without-slash", ["- `src/fx`"]),
    ("extensionless-name", ["- `Dockerfile`"]),
    ("dotfile", ["- `.gitignore`"]),
    ("unknown-extension", ["- `data/rates.bin`"]),
    ("dot-directory", ["- `nginx/conf.d`"]),
    ("file-next-to-directory", ["- `src/fx/rates.py`", "- `src/fx/`"]),
    ("continuation-line", ["- `src/fx/rates.py`", "  and the table"]),
    ("sub-heading", ["- `src/fx/rates.py`", "### Backend", "- `src/fx/table.py`"]),
    ("fence", ["- `src/fx/rates.py`", "```", "rm -rf src", "```"]),
    ("prose-line", ["The converter:", "- `src/fx/rates.py`"]),
    ("unknown-marker", ["- `src/fx/rates.py` (created)"]),
    ("markup-around-path", ["- **src/fx/rates.py**"]),
    ("nbsp-padded-code-span", ["- `\u00a0src/fx/rates.py`"]),
    ("invisible-letter-join", ["- src/fx/rates.py\u3164src/fx/table.py"]),
    ("cyrillic-extension", ["- src/fx/rates.p\u0443"]),
    ("double-dot-name", ["- x..py"]),
)

HEAD = "# Scope Lock\n\n## Current Task\n\n- U-1: x\n\n"
AREAS = "## Allowed Change Areas\n\n- `src/fx/rates.py`\n\n"
FORBIDDEN = "## Forbidden Change Areas\n\n- `vendor/`\n"
# (label, SCOPE_LOCK text): the areas are a path list, but the SCOPE_LOCK is outside the plain
# layout - `hooks/wip-gate.sh` reads an item the strict reader did not (it matches the
# `## allowed change areas` prefix on the stripped line, splits on `## ` only and knows no
# fences), or a heading only starts with a scope title - so HOT_GOAL keeps forcing `money`
LAYOUT_NOT_PLAIN = (
    ("continued-section", HEAD + AREAS + "## Allowed Change Areas (continued)\n\n- `src/`\n\n" + FORBIDDEN),
    ("continued-section-before", HEAD + "## Allowed Change Areas - backend\n\n- `src/`\n\n" + AREAS + FORBIDDEN),
    ("prefixed-in-scope", HEAD + AREAS + "### In scope for the backend\n\n- `src/`\n\n" + FORBIDDEN),
    ("top-level-heading-after-areas", HEAD + AREAS + "# Notes\n\n- `src/`\n\n" + FORBIDDEN),
    # checker c1: the strict reader ignores both, the hook opens a section on both
    ("scope-heading-indented-by-four", HEAD + AREAS + FORBIDDEN + "\n    ## Allowed Change Areas\n\n- `src/`\n"),
    ("scope-heading-inside-a-fence", HEAD + AREAS + FORBIDDEN + "\n```\n## Allowed Change Areas\n- `src/`\n```\n"),
    ("scope-heading-inside-a-tilde-fence", HEAD + "~~~text\n## allowed change areas\n- `src/`\n~~~\n\n" + AREAS + FORBIDDEN),
    ("setext-scope-heading", HEAD + AREAS + FORBIDDEN + "\nIn scope\n--------\n\n- `src/`\n"),
    ("setext-prefixed-scope-heading", HEAD + AREAS + FORBIDDEN + "\nAllowed Change Areas (extra)\n===\n\n- `src/`\n"),
)
# (label, SCOPE_LOCK text): the layout is plain, the goal is kept by the path-list grammar itself -
# a top-level scope heading after the areas swallows the next `## ` section into the scope
LAYOUT_PLAIN_NOT_A_LIST = (
    ("higher-level-second-scope-heading", HEAD + AREAS + "# In scope\n\n- `src/fx/table.py`\n\n" + FORBIDDEN),
)
# (label, SCOPE_LOCK text): still the plain layout - the goal hit is set aside
LAYOUT_PLAIN = (
    ("extra-section-of-the-same-level", HEAD + AREAS + "## Notes\n\n- `src/`\n\n" + FORBIDDEN),
    ("deeper-heading-in-another-section", HEAD + AREAS + FORBIDDEN + "\n### Vendored\n\n- `third_party/`\n"),
    ("top-level-heading-after-forbidden", HEAD + AREAS + FORBIDDEN + "\n# Appendix\n\n- `src/`\n"),
    ("two-exact-scope-sections", HEAD + AREAS + "## In scope\n\n- `src/fx/table.py`\n\n" + FORBIDDEN),
    ("lower-case-scope-heading", (HEAD + AREAS + FORBIDDEN).replace("## Allowed Change Areas\n", "## allowed change areas\n")),
    ("crlf-line-endings", (HEAD + AREAS + FORBIDDEN).replace("\n", "\r\n")),
    ("closing-hashes-and-colon", (HEAD + AREAS + FORBIDDEN).replace("## Allowed Change Areas\n", "## Allowed Change Areas: ##\n")),
    ("setext-heading-of-another-section", HEAD + AREAS + FORBIDDEN + "\nNotes\n-----\n\n- `src/`\n"),
)

fails: list[str] = []
checked = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global checked
    checked += 1
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_module(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scope_md(lines: list[str], unit: str = "U-1", forbidden: tuple[str, ...] = ("- `vendor/`",)) -> str:
    return (f"# Scope Lock\n\n## Current Task\n\n- {unit}: x\n\n## Allowed Change Areas\n\n"
            + "".join(line + "\n" for line in lines)
            + "\n## Forbidden Change Areas\n\n" + "".join(line + "\n" for line in forbidden))


def activate(root: Path, goal: str, tier: str, lines: list[str] | None, unit: str = "U-1",
             forbidden: tuple[str, ...] = ("- `vendor/`",), scope_text: str | None = None):
    """Run activate of U-1 in a throwaway project whose SCOPE_LOCK names `unit` (or is exactly
    `scope_text`); return (rc, output, STATE.currentUnit|None)."""
    with tempfile.TemporaryDirectory() as project:
        mem = Path(project) / ".itd-memory"
        mem.mkdir()
        if lines is not None or scope_text is not None:
            (Path(project) / ".itd").mkdir()
            text = scope_text if scope_text is not None else scope_md(lines, unit, forbidden)
            (Path(project) / ".itd" / "SCOPE_LOCK.md").write_bytes(text.encode("utf-8"))
        cmd = [sys.executable, str(root / "skills" / "task" / "scripts" / "itd_unit_log.py"),
               "activate", "U-1", "--goal", goal, "--risk-tier", tier, "--dir", str(mem)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=project)
        state = mem / "STATE.json"
        cu = json.loads(read(state)).get("currentUnit") if state.is_file() else None
        return r.returncode, r.stdout + r.stderr, cu


def suite(root: Path, quiet: bool = False) -> list[str]:
    """Return the list of failed check names for the product tree at `root`."""
    local_fails: list[str] = []

    def c(name: str, cond: bool, detail: str = "") -> None:
        if not quiet:
            check(name, cond, detail)
        if not cond:
            local_fails.append(name)

    rc = load_module(root / "skills" / "_shared" / "itd_risk_classes.py", "itd_risk_classes_tw")
    policy = json.loads(read(root / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"))
    classes = rc.load_strict_classes(policy)
    is_file_path = getattr(rc, "is_file_path", None)
    path_list = getattr(rc, "path_list", None)
    exempt_goal_hit = getattr(rc, "exempt_goal_hit", None)
    plain_scope_layout = getattr(rc, "plain_scope_layout", None)
    c("api-is_file_path", callable(is_file_path))
    c("api-path_list", callable(path_list))
    c("api-plain_scope_layout", callable(plain_scope_layout))

    # 1. the predicates
    if callable(is_file_path):
        for p in FILE_PATHS:
            c(f"file-path {p!r}", is_file_path(p) is True)
        for p in NOT_FILE_PATHS:
            c(f"not-a-file-path {p!r}", is_file_path(p) is False)
        # a concrete file is a token the strict path matcher reads, or no path pattern sees it
        for p in FILE_PATHS:
            c(f"file-path-is-a-path-token {p!r}", rc._path_tokens(p.lower()) == [p.lower()],
              f"tokens={rc._path_tokens(p.lower())}")
        extra = sorted(getattr(rc, "_FILE_EXTS", frozenset()) - rc._CODE_EXTS)
        c("file-extension-set-is-the-pinned-closed-list", extra == sorted(EXTRA_FILE_EXTS)
          and rc._CODE_EXTS <= getattr(rc, "_FILE_EXTS", frozenset()), f"extra={extra}")
        for ext in EXTRA_FILE_EXTS:
            c(f"file-extension {ext!r}", is_file_path(f"dir/name.{ext}") is True
              and is_file_path(f"dir/name.{ext}x9") is False)
    if callable(path_list):
        for text, want in PATH_LIST:
            c(f"path-list {text!r}", path_list(text) is want)

    # 2. pairs over a non-test scope: one tier whatever the wording
    for label, lines, template, detailed, cls in PAIRS:
        scope = scope_md(lines)
        control = [rc.match_strict_class(g, "", classes) for g in (template, detailed)]
        c(f"pair-{label}-control-template-clean-detailed-hits-{cls}",
          control[0] is None and bool(control[1]) and control[1][0] == cls, f"control hits={control}")
        c(f"pair-{label}-scope-itself-clean", rc.match_strict_class("", scope, classes, "U-1") is None)
        hits = [rc.match_strict_class(g, scope, classes, "U-1") for g in (template, detailed)]
        c(f"pair-{label}-matcher-one-tier", hits == [None, None], f"hits={hits}")
        for declared in ("low", "medium"):
            tiers = []
            for which, goal in (("template", template), ("detailed", detailed)):
                code, out, cu = activate(root, goal, declared, lines)
                tiers.append((cu or {}).get("riskTier"))
                c(f"pair-{label}-{declared}-{which}-activate-rc0", code == 0, out.strip()[-300:])
                c(f"pair-{label}-{declared}-{which}-not-forced", bool(cu) and "riskTierForced" not in cu
                  and "riskTierMatch" not in cu, f"currentUnit={cu}")
                exempt = (cu or {}).get("riskTierExempt")
                if which == "detailed":
                    c(f"pair-{label}-{declared}-exempt-recorded",
                      isinstance(exempt, dict) and exempt.get("class") == cls
                      and "list of paths" in str(exempt.get("reason", ""))
                      and "tests-only" not in str(exempt.get("reason", ""))
                      and "in goal" in str(exempt.get("match", "")), f"riskTierExempt={exempt}")
                    c(f"pair-{label}-{declared}-exempt-printed",
                      "strict class not applied" in out and "list of paths" in out, out.strip()[-300:])
                else:
                    c(f"pair-{label}-{declared}-template-no-exempt-note", exempt is None, f"riskTierExempt={exempt}")
            c(f"pair-{label}-{declared}-activate-one-tier", tiers == [declared, declared], f"tiers={tiers}")

    # 3a. the floor stays: a strict path or keyword of the path list itself
    for label, lines, cls in FLOOR_IN_LIST:
        if callable(path_list):
            c(f"in-list-{label}-is-a-path-list", path_list("\n".join(lines)) is True)
        for goal_label, goal in (("neutral-goal", NEUTRAL_GOAL), ("hot-goal", HOT_GOAL)):
            hit = rc.match_strict_class(goal, scope_md(lines), classes, "U-1")
            c(f"in-list-{label}-{goal_label}-matcher-{cls}-from-scope",
              bool(hit) and hit[0] == cls and hit[3] == "SCOPE_LOCK", f"hit={hit}")
            code, out, cu = activate(root, goal, "low", lines)
            forced = (cu or {}).get("riskTierForced") or {}
            c(f"in-list-{label}-{goal_label}-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
              and forced.get("class") == cls and forced.get("declared") == "low", f"rc={code} currentUnit={cu}")
            exempt = (cu or {}).get("riskTierExempt")
            if goal is HOT_GOAL:
                c(f"in-list-{label}-exempt-recorded-next-to-forced",
                  isinstance(exempt, dict) and exempt.get("class") == "money"
                  and "list of paths" in str(exempt.get("reason", "")), f"riskTierExempt={exempt}")
            else:
                c(f"in-list-{label}-no-exempt-note-for-neutral-goal", exempt is None, f"riskTierExempt={exempt}")
    code, out, cu = activate(root, HOT_GOAL, "high", FLOOR_IN_LIST[0][1])
    c("in-list-declared-high-match-and-exempt",
      code == 0 and (cu or {}).get("riskTier") == "high" and "riskTierForced" not in (cu or {})
      and ((cu or {}).get("riskTierMatch") or {}).get("class") == "money"
      and isinstance((cu or {}).get("riskTierExempt"), dict), f"rc={code} currentUnit={cu}")

    # 3b. the floor stays: a scope outside the grammar keeps the goal as a source
    for label, lines in FLOOR_NOT_LIST:
        hit = rc.match_strict_class(HOT_GOAL, scope_md(lines), classes, "U-1")
        c(f"not-list-{label}-matcher-money-from-goal",
          bool(hit) and hit[0] == "money" and hit[3] == "goal", f"hit={hit}")
        code, out, cu = activate(root, HOT_GOAL, "low", lines)
        forced = (cu or {}).get("riskTierForced") or {}
        c(f"not-list-{label}-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
          and forced.get("class") == "money", f"rc={code} currentUnit={cu}")
        c(f"not-list-{label}-no-exempt-note", "riskTierExempt" not in (cu or {}),
          f"riskTierExempt={(cu or {}).get('riskTierExempt')}")
        c(f"not-list-{label}-no-hint", "does not open with" not in out, out.strip()[-300:])

    # 3b'. the floor stays: a path list inside a SCOPE_LOCK whose headings leave the plain layout
    for label, text in LAYOUT_NOT_PLAIN + LAYOUT_PLAIN_NOT_A_LIST:
        if callable(plain_scope_layout):
            want = (label, text) in LAYOUT_PLAIN_NOT_A_LIST
            c(f"layout-{label}-plain-is-{want}", plain_scope_layout(text) is want)
        hit = rc.match_strict_class(HOT_GOAL, text, classes, "U-1")
        c(f"layout-{label}-matcher-money-from-goal",
          bool(hit) and hit[0] == "money" and hit[3] == "goal", f"hit={hit}")
        code, out, cu = activate(root, HOT_GOAL, "low", None, scope_text=text)
        c(f"layout-{label}-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
          and "riskTierExempt" not in (cu or {}), f"rc={code} currentUnit={cu}")
    for label, text in LAYOUT_PLAIN:
        if callable(plain_scope_layout):
            c(f"layout-{label}-is-plain", plain_scope_layout(text) is True)
        hit = rc.match_strict_class(HOT_GOAL, text, classes, "U-1")
        c(f"layout-{label}-matcher-none", hit is None, f"hit={hit}")
        code, out, cu = activate(root, HOT_GOAL, "low", None, scope_text=text)
        c(f"layout-{label}-activate-low", code == 0 and (cu or {}).get("riskTier") == "low"
          and isinstance((cu or {}).get("riskTierExempt"), dict), f"rc={code} currentUnit={cu}")
    gate_items = getattr(rc, "gate_items", None)
    c("api-gate_items", callable(gate_items))
    if callable(gate_items):
        # the mirror of the hook's reader: stripped lines, `## ` toggles, prefix match, `- ` items
        for text, want in (
                ("## Allowed Change Areas\n- `a.py`\n* `b.py`\n1. `c.py`\n", ["- `a.py`"]),
                ("## ALLOWED CHANGE AREAS (more)\n  - a.py\n### Sub\n- b.py\n# Top\n- c.py\n## Other\n- d.py\n",
                 ["- a.py", "- b.py", "- c.py"]),
                ("    ## Allowed Change Areas\n\t- a.py\n", ["- a.py"]),
                ("```\n## Allowed Change Areas\n- a.py\n```\n", ["- a.py"]),
                ("### Allowed Change Areas\n- a.py\n", []),
                ("## In scope\n- a.py\n", []),
                ("##Allowed Change Areas\n- a.py\n", []),
                ("", [])):
            c(f"gate-items {text!r}", gate_items(text) == want, f"got={gate_items(text)}")
    # drift guard: `gate_items` mirrors these three lines of the hook; when the hook's reader
    # changes, the mirror has to be revisited (one shared reader is BACKLOG P2 2026-09-26)
    hook = read(root / "hooks" / "wip-gate.sh")
    c("hook-reader-unchanged", all(marker in hook for marker in (
        'if stripped.startswith("## "):',
        'in_section = stripped.lower().startswith("## allowed change areas")',
        'if in_section and stripped.startswith("- "):')))
    if callable(plain_scope_layout):
        c("layout-empty-text-is-plain", plain_scope_layout("") is True)
        c("layout-fenced-prefix-heading-keeps-the-goal",
          plain_scope_layout(HEAD + AREAS + "```\n## Allowed Change Areas (old)\n```\n" + FORBIDDEN) is False)
        c("layout-shell-comment-is-not-a-heading",
          plain_scope_layout(HEAD + AREAS + FORBIDDEN + "\n#run the suite\n") is True)
    # a tests-only scope gets the same guard (the BACKLOG P2 2026-09-26 case)
    tests_areas = "## Allowed Change Areas\n\n- `tests/test_fx_rates.py`\n\n"
    hit = rc.match_strict_class(HOT_GOAL, HEAD + tests_areas + "# Notes\n\n- `src/fx/`\n", classes, "U-1")
    c("layout-tests-only-with-top-level-heading-keeps-the-goal",
      bool(hit) and hit[0] == "money" and hit[3] == "goal", f"hit={hit}")

    # 3c. the floor stays: the scope of another unit, no unit id, no SCOPE_LOCK
    hit = rc.match_strict_class(HOT_GOAL, scope_md(LIST_LINES, "U-7"), classes, "U-1")
    c("stale-scope-of-U-7-matcher-money", bool(hit) and hit[0] == "money" and hit[3] == "goal", f"hit={hit}")
    code, out, cu = activate(root, HOT_GOAL, "low", LIST_LINES, unit="U-7")
    c("stale-scope-of-U-7-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
      and "riskTierExempt" not in (cu or {}), f"rc={code} currentUnit={cu}")
    c("stale-scope-of-U-7-hint-printed",
      "does not open with U-1" in out and "list of paths" in out and "tests-only" not in out, out.strip()[-300:])
    code, out, cu = activate(root, HOT_GOAL, "low", LIST_LINES, unit="U-7", forbidden=("- U-1 is the next unit",))
    c("stale-scope-names-U-1-in-forbidden-activate-high",
      code == 0 and (cu or {}).get("riskTier") == "high" and "riskTierExempt" not in (cu or {}),
      f"rc={code} currentUnit={cu}")
    # the hint is about a path list only: a scope of another unit outside the grammar gets none
    code, out, cu = activate(root, HOT_GOAL, "low", ["- `src/fx/` and the helpers"], unit="U-7")
    c("stale-prose-scope-of-U-7-high-without-hint", code == 0 and (cu or {}).get("riskTier") == "high"
      and "does not open with" not in out, out.strip()[-300:])
    code, out, cu = activate(root, HOT_GOAL, "low", LIST_LINES, unit="U-12")
    c("stale-scope-of-U-12-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
      and "riskTierExempt" not in (cu or {}), f"rc={code} currentUnit={cu}")
    hit = rc.match_strict_class(HOT_GOAL, scope_md(LIST_LINES), classes)
    c("no-unit-id-matcher-money", bool(hit) and hit[0] == "money" and hit[3] == "goal", f"hit={hit}")
    code, out, cu = activate(root, HOT_GOAL, "low", None)
    c("no-scope-lock-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
      and "riskTierExempt" not in (cu or {}), f"rc={code} currentUnit={cu}")
    code, out, cu = activate(root, NEUTRAL_GOAL, "low", LIST_LINES)
    c("neutral-goal-on-path-list-stays-low-without-notes", code == 0 and (cu or {}).get("riskTier") == "low"
      and not any(k in (cu or {}) for k in ("riskTierForced", "riskTierMatch", "riskTierExempt")),
      f"rc={code} currentUnit={cu}")
    if callable(exempt_goal_hit):
        eh = exempt_goal_hit(HOT_GOAL, scope_md(LIST_LINES), classes, "U-1")
        c("exempt-hit-reported-on-path-list", bool(eh) and eh[0] == "money" and eh[3] == "goal", f"hit={eh}")
        c("exempt-hit-none-without-unit-id", exempt_goal_hit(HOT_GOAL, scope_md(LIST_LINES), classes) is None)
        c("exempt-hit-none-on-directory-scope",
          exempt_goal_hit(HOT_GOAL, scope_md(["- `src/fx/`"]), classes, "U-1") is None)
    # a tests-only scope keeps its own reason (TIER-SOURCE-1 wording is not rewritten)
    code, out, cu = activate(root, HOT_GOAL, "low", ["- `tests/test_fx_rates.py`"])
    reason = str(((cu or {}).get("riskTierExempt") or {}).get("reason", ""))
    c("tests-only-scope-keeps-its-reason", code == 0 and (cu or {}).get("riskTier") == "low"
      and "tests-only" in reason and "list of paths" not in reason, f"rc={code} currentUnit={cu}")

    # 4. docs and registration
    skill = " ".join(read(root / "skills" / "task" / "SKILL.md").split())
    c("task-skill-documents-path-list", "TIER-WORDING-2" in skill and "riskTierExempt" in skill
      and "a list of paths" in skill and "_FILE_EXTS" in skill)
    adr = " ".join(read(root / "docs" / "adr" / "ADR-011-default-risk-tier-low.md").split())
    c("adr-011-amended", "TIER-WORDING-2" in adr and "Amendment 2026-10-01" in adr
      and "a list of paths" in adr and "_FILE_EXTS" in adr and "plain layout" in adr)
    runall = read(root / "tests" / "run-all.sh")
    c("registered-in-run-all", "verify_tier_wording" in runall)
    return local_fails


def copy_product(dst: Path) -> None:
    for rel in ("skills", "docs/adr"):
        shutil.copytree(ROOT / rel, dst / rel, ignore=shutil.ignore_patterns("__pycache__"))
    for rel in ("tests/run-all.sh", "hooks/wip-gate.sh"):
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst / rel)


def append(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.write_text(read(p) + "\n" + text + "\n", encoding="utf-8")


def replace_once(root: Path, rel: str, old: str, new: str) -> None:
    p = root / rel
    src = read(p)
    assert src.count(old) == 1, f"mutation marker must occur exactly once in {rel}: {old!r} ({src.count(old)})"
    p.write_text(src.replace(old, new, 1), encoding="utf-8")


RC_REL = "skills/_shared/itd_risk_classes.py"
LOG_REL = "skills/task/scripts/itd_unit_log.py"


def m_prefix_bytes(root: Path) -> None:
    for rel in (RC_REL, LOG_REL):
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{PREFIX_COMMIT}:{rel}"],
                           capture_output=True, timeout=30)
        if r.returncode:
            raise RuntimeError(f"cannot read pre-fix bytes of {rel} at {PREFIX_COMMIT}")
        (root / rel).write_bytes(r.stdout)


def mutations() -> None:
    cases = (
        (f"prefix-bytes-{PREFIX_COMMIT}", m_prefix_bytes),
        ("goal-kept-on-a-path-list", lambda r: replace_once(
            r, RC_REL, "if path_list_scope(scope_text, unit_id):\n        goal = \"\"",
            "if tests_only(areas) and names_unit(scope_text, unit_id):\n        goal = \"\"")),
        ("every-token-is-a-file", lambda r: append(r, RC_REL, "is_file_path = lambda token: True")),
        ("wildcard-is-a-file", lambda r: replace_once(
            r, RC_REL, ' or "*" in path or "?" in path', "")),
        ("file-charset-ignored", lambda r: replace_once(
            r, RC_REL, "if not _SAFE_PATH_RE.fullmatch(path)", "if not path")),
        ("file-dotdot-allowed", lambda r: replace_once(
            r, RC_REL, 'if ".." in path:', "if False:")),
        ("file-dotdot-only-as-a-segment", lambda r: replace_once(
            r, RC_REL, 'if ".." in path:', 'if ".." in path.split("/"):')),
        ("layout-guard-dropped", lambda r: replace_once(
            r, RC_REL, " and plain_scope_layout(scope_text)", "")),
        ("prefixed-scope-heading-allowed", lambda r: replace_once(
            r, RC_REL, "return False        # a scope-titled heading the strict reader does not open",
            "pass")),
        ("setext-scope-heading-allowed", lambda r: replace_once(
            r, RC_REL, "return False            # a setext scope heading is not opened either",
            "pass")),
        ("gate-containment-dropped", lambda r: replace_once(
            r, RC_REL, "return False                # the hook reads an item the strict reader did not",
            "pass")),
        ("gate-mirror-keeps-the-indent", lambda r: replace_once(
            r, RC_REL, "        stripped = line.strip()\n        if stripped.startswith(\"## \"):",
            "        stripped = line.rstrip()\n        if stripped.startswith(\"## \"):")),
        ("gate-mirror-is-case-sensitive", lambda r: replace_once(
            r, RC_REL, "inside = stripped.lower().startswith(_GATE_SCOPE_PREFIX)",
            "inside = stripped.startswith(_GATE_SCOPE_PREFIX)")),
        ("gate-mirror-closes-on-any-heading", lambda r: replace_once(
            r, RC_REL, "        if stripped.startswith(\"## \"):\n            inside =",
            "        if stripped.startswith(\"#\"):\n            inside =")),
        ("hook-reader-changed", lambda r: replace_once(
            r, "hooks/wip-gate.sh", 'stripped.lower().startswith("## allowed change areas")',
            'stripped.lower().startswith("## allowed")')),
        ("extension-set-widened", lambda r: append(r, RC_REL, "_FILE_EXTS = _FILE_EXTS | {'bin', 'd'}")),
        ("any-extension-is-a-file", lambda r: replace_once(
            r, RC_REL, "and ext.lower() in _FILE_EXTS", "and bool(ext)")),
        ("stemless-name-is-a-file", lambda r: replace_once(
            r, RC_REL, "return bool(stem and dot) and", "return bool(dot) and")),
        ("extensionless-name-is-a-file", lambda r: append(r, RC_REL, (
            "_orig_is_file_path = is_file_path\n"
            "is_file_path = lambda token: _orig_is_file_path(token) or bool(re.fullmatch('[A-Za-z0-9_/-]*[A-Za-z0-9_-]', token or ''))"))),
        ("directory-is-a-file", lambda r: append(r, RC_REL, (
            "_orig_is_file_path = is_file_path\n"
            "is_file_path = lambda token: _orig_is_file_path(token) or (token or '').endswith('/')"))),
        ("non-item-lines-skipped", lambda r: replace_once(
            r, RC_REL, "return False            # a line outside the grammar", "continue  #")),
        ("vacuous-path-list", lambda r: append(r, RC_REL, (
            "_orig_path_list = path_list\n"
            "path_list = lambda areas: _orig_path_list(areas) or not (areas or '').strip()"))),
        ("trailing-text-allowed", lambda r: replace_once(
            r, RC_REL, r"(?:[ \t]+\((?:new|updated)\))?[ \t]*$", r"(?:[ \t]+\((?:new|updated)\))?.*$")),
        ("unit-binding-ignored", lambda r: append(r, RC_REL, "names_unit = lambda scope_text, unit_id: True")),
        ("unit-id-anywhere", lambda r: append(r, RC_REL, (
            "names_unit = lambda scope_text, unit_id: bool(unit_id) and unit_id in (scope_text or '')"))),
        ("exemption-drops-the-areas-too", lambda r: append(r, RC_REL, (
            "_orig_match = match_strict_class\n"
            "def match_strict_class(goal, scope_text, classes, unit_id=''):\n"
            "    if path_list_scope(scope_text, unit_id):\n"
            "        return None\n"
            "    return _orig_match(goal, scope_text, classes, unit_id)"))),
        ("exempt-note-not-recorded", lambda r: replace_once(
            r, LOG_REL, 'state["currentUnit"]["riskTierExempt"] = exempt_note', "pass")),
        ("exempt-dropped-when-forced", lambda r: replace_once(
            r, LOG_REL, "exempt = RC.exempt_goal_hit(", "exempt = None if forced else RC.exempt_goal_hit(")),
        ("exempt-print-suppressed", lambda r: replace_once(
            r, LOG_REL, 'print(f"strict class not applied (', 'str(f"strict class not applied (')),
        ("reason-always-tests-only", lambda r: replace_once(
            r, LOG_REL, 'else "a list of paths"', 'else "tests-only"')),
        ("reason-never-tests-only", lambda r: replace_once(
            r, LOG_REL, 'areas_kind = "tests-only" if', 'areas_kind = "a list of paths" if False and')),
        ("hint-only-for-tests-only", lambda r: replace_once(
            r, LOG_REL, 'and RC.path_list(RC.allowed_areas(scope_text))',
            'and RC.tests_only(RC.allowed_areas(scope_text))')),
        ("hint-on-any-scope", lambda r: replace_once(
            r, LOG_REL, 'and RC.path_list(RC.allowed_areas(scope_text))', '')),
    )
    for label, apply in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "product"
            copy_product(root)
            try:
                apply(root)
            except (AssertionError, RuntimeError) as exc:
                check(f"mutation-{label}-applied", False, str(exc))
                continue
            try:
                red = suite(root, quiet=True)
            except Exception as exc:  # a mutant that crashes the suite is caught too
                red = [f"crash: {exc!r}"]
            check(f"mutation-{label}-lethal", bool(red), "suite stayed green")


def main() -> int:
    baseline = suite(ROOT)
    if "--mutations" in sys.argv[1:]:
        if baseline:
            print("skip mutations: baseline suite is red")
        else:
            mutations()
    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed ({checked - len(fails)} passed)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
