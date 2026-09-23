#!/usr/bin/env python3
"""itd_risk_classes.py — strict risk classes that force `riskTier=high` (G-001, v1.106.0).

Audit 2026-09-22: the proportionality route exists, but 91% of units were opened as
medium/high by habit, and nothing guaranteed `high` where it is non-negotiable. This
module is the single reader of `strictClasses` in `PROPORTIONALITY_POLICY.json`:

  * `load_strict_classes(policy)` — fail-closed: exactly the five classes
    (money / prod-config / db-schema / auth / secrets), each with non-empty `keywords`,
    non-empty `paths` and `tier: "high"`; anything else raises `StrictClassPolicyError`,
    and the unit writer refuses to activate on a broken policy instead of guessing.
  * `match_strict_class(goal, scope_text, classes)` — lexical floor, not a classifier.
    Both the unit goal and the Allowed Change Areas section of `.itd/SCOPE_LOCK.md` are
    matched against keywords AND path patterns. Keywords match as whole words bounded by
    non-letters (case-insensitive; camelCase/ACRONYMWord are split and `_`/`-` become
    spaces first, so `auth_service`, `OAuth2`, `AuthService`, `JWTBearer`, `access_token`,
    `BOT_TOKEN` and `getApiKey` hit;
    a trailing `*` makes a stem match, e.g. `оплат*`); path patterns match with `fnmatch`
    against path-like tokens (anything with a `/` or a dot-extension, dotfiles included:
    `.env`, `.env.example`, `app.prod.yaml`, `db/migrations/0004.sql`). The scope section is
    `## Allowed Change Areas` or `## In scope` at any heading level and runs until a heading of
    the same or a higher level; deeper sub-headings and fenced code stay inside it (a fence
    closes only with the same delimiter character and at least the opening length).
    Returns `(class, kind, pattern, where)` for the first hit in class order, else None.

Only stdlib. Shared by `skills/task/scripts/itd_unit_log.py`; tests:
`tests/verify_risk_tier_default.py`.
"""
from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

REQUIRED_CLASSES = ("money", "prod-config", "db-schema", "auth", "secrets")
FORCED_TIER = "high"
# The scope section is recognised by heading text, not by exact bytes: any `#` level, an
# optional trailing colon, and the two spellings the templates use (checker c7).
_ALLOWED_HEADINGS = ("allowed change areas", "in scope")
# A heading needs whitespace after the hashes (a shell comment `#run` is not one) and the
# section ends only at a heading of the SAME or HIGHER level than the one that opened it, so
# `### Backend` sub-sections stay inside `## Allowed Change Areas`; fenced code is skipped
# (checker c8).
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})[ \t]+(.+?)\s*:?\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
# Split on whitespace and the punctuation Markdown bullets wrap paths in; a token is
# path-like when it carries a slash or a dot-extension (leading dot allowed).
_SPLIT_RE = re.compile(r"[\s`'\"(),;:<>]+")
_MARKUP_CHARS = "*[]!~|\\#=+"
_SENTENCE_CHARS = ".?"
_PATH_LIKE_RE = re.compile(r"\.[\w\-]+(?:\.[\w\-]+)*|[\w\-]+(?:\.[\w\-]+)+")
# A keyword is bounded by non-letters: `_`, digits and punctuation end a word, so
# `auth_service`, `payments_api` and `oauth2` hit while `unauthorized` does not.
_LETTER = r"[^\W\d_]"
# camelCase / PascalCase identifiers (AuthService, authStore.ts, getApiKey) are split at
# every lower->Upper transition BEFORE lower-casing, otherwise the word boundary vanishes
# and `auth` / `api key` never hit (checker c5).
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
# snake_case / kebab-case / SCREAMING_CASE identifiers (access_token, BOT_TOKEN, refresh-token)
# become space-separated words so multi-word keywords such as `access token` hit (checker c6).
_JOINER_RE = re.compile(r"[_\-]+")


_WS_RE = re.compile(r"\s+")


def _words(text: str) -> str:
    """Word-form of a text: camelCase and ACRONYMWord split, `_`/`-` joiners and any
    whitespace run (tabs, double spaces, Markdown line wraps) -> one space, lowered."""
    return _WS_RE.sub(" ", _JOINER_RE.sub(" ", _CAMEL_RE.sub(" ", text or ""))).lower()


class StrictClassPolicyError(ValueError):
    """The policy's strictClasses block is missing or malformed (fail-closed)."""


def load_strict_classes(policy: dict) -> dict[str, dict]:
    block = policy.get("strictClasses") if isinstance(policy, dict) else None
    if not isinstance(block, dict):
        raise StrictClassPolicyError("PROPORTIONALITY_POLICY.strictClasses is missing or not an object")
    if set(block) != set(REQUIRED_CLASSES):
        raise StrictClassPolicyError(
            "strictClasses must contain exactly " + ", ".join(REQUIRED_CLASSES)
            + f"; got {sorted(block)}")
    out: dict[str, dict] = {}
    for cls in REQUIRED_CLASSES:
        spec = block[cls]
        if not isinstance(spec, dict):
            raise StrictClassPolicyError(f"strictClasses.{cls} must be an object")
        for field in ("keywords", "paths"):
            values = spec.get(field)
            if (not isinstance(values, list) or not values
                    or not all(isinstance(v, str) and v.strip() for v in values)):
                raise StrictClassPolicyError(f"strictClasses.{cls}.{field} must be a non-empty list of strings")
        if spec.get("tier") != FORCED_TIER:
            raise StrictClassPolicyError(f"strictClasses.{cls}.tier must be '{FORCED_TIER}'")
        out[cls] = {"keywords": [k.strip().lower() for k in spec["keywords"]],
                    "paths": [p.strip().lower() for p in spec["paths"]],
                    "tier": FORCED_TIER}
    return out


def _keyword_hit(keyword: str, text: str) -> bool:
    if keyword.endswith("*"):
        return re.search(r"(?<!" + _LETTER + ")" + re.escape(keyword[:-1]), text) is not None
    return re.search(r"(?<!" + _LETTER + ")" + re.escape(keyword) + r"(?!" + _LETTER + ")",
                     text) is not None


def allowed_areas(scope_text: str) -> str:
    """Return the body of the `Allowed Change Areas` / `In scope` section of a SCOPE_LOCK.md
    text ('' if absent); heading level and a trailing colon do not matter."""
    if not scope_text:
        return ""
    out: list[str] = []
    level = 0          # heading level that opened the section; 0 = not inside
    fence = ""         # the delimiter that opened the current fence ("" = not fenced)
    for line in scope_text.splitlines():
        fm = _FENCE_RE.match(line)
        # a backtick marker whose info string contains a backtick is inline code, not a
        # fence (CommonMark; checker c17): `\`\`\`rm -rf\`\`\` is forbidden` opens nothing
        if fm and not fence and fm.group(1)[0] == "`" and "`" in fm.group(2):
            fm = None
        if fm:
            marker, rest = fm.group(1), fm.group(2)
            if not fence:
                fence = marker                      # open: remember char + length
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip():
                fence = ""                          # close: same char, not shorter, bare
            # a mismatched marker or a marker with an info string (```text) inside a
            # fence is fenced content, not a closer (CommonMark; PUB4 F3)
            if level:
                out.append(line)
            continue
        m = None if fence else _HEADING_RE.match(line)
        if m:
            depth = len(m.group(1))
            title = m.group(2).strip().lower()
            if title in _ALLOWED_HEADINGS:
                if not level:
                    level = depth                   # open a scope section
                elif depth > level:
                    out.append(line)                # nested `### In scope` is a sub-heading
                else:
                    level = depth                   # another scope section: union, never discard
                continue
            if level and depth <= level:
                level = 0                           # section over; a later one may reopen
                continue
            if level:
                out.append(line)      # a deeper sub-heading stays inside the section
        elif level:
            out.append(line)
    return "\n".join(out)


def _strip_markup(tok: str) -> str:
    """Drop Markdown presentation around a token: `**db/schema.rb**`, `[x.py]`, `~~old~~`,
    `_italic/path_` (PUB3 F3). A leading `_` is kept unless the token is wrapped on both
    sides, so `__init__.py` and `_config.yml` survive."""
    # Markup and sentence punctuation nest in either order (`**x**.`, `.**x**`, `_x_?`),
    # so strip both until the token is stable (checker c14).
    while True:
        before = tok
        # a leading dot is a dotfile (`.env`), so sentence punctuation goes only from the right
        tok = tok.strip(_MARKUP_CHARS).rstrip(_SENTENCE_CHARS)
        while len(tok) > 2 and tok[0] == "_" and tok[-1] == "_":
            tok = tok[1:-1]
        if tok == before:
            return tok


def _path_tokens(text: str) -> list[str]:
    out: list[str] = []
    for raw in _SPLIT_RE.split(text):
        tok = _strip_markup(raw).lower()
        if not tok:
            continue
        if "/" in tok or _PATH_LIKE_RE.fullmatch(tok):
            out.append(tok)
    return out


def _path_hit(token: str, pattern: str) -> bool:
    """fnmatch with a virtual leading slash so `*/k8s/*` also hits repo-root `k8s/x.yaml`
    and `*/auth.py` hits a bare `auth.py` (checker c3 finding 1)."""
    return fnmatch.fnmatchcase(token, pattern) or fnmatch.fnmatchcase("/" + token, pattern)


def match_strict_class(goal: str, scope_text: str, classes: dict[str, dict]):
    areas = allowed_areas(scope_text or "")
    # keywords see camel-split words; path patterns see the raw lower-cased tokens
    goal_plain = (goal or "").lower()
    areas_plain = areas.lower()
    # both forms are tried: the camel-split one finds `AuthService`, the plain one keeps
    # brand names such as `YooKassa` whole
    goal_l = _words(goal) + "\n" + goal_plain
    areas_l = _words(areas) + "\n" + areas_plain
    goal_paths = _path_tokens(goal_plain)
    scope_paths = _path_tokens(areas_plain)
    for cls in REQUIRED_CLASSES:
        spec = classes.get(cls) or {}
        for kw in spec.get("keywords", ()):
            if _keyword_hit(kw, goal_l):
                return (cls, "keyword", kw, "goal")
            if _keyword_hit(kw, areas_l):
                return (cls, "keyword", kw, "SCOPE_LOCK")
        for pattern in spec.get("paths", ()):
            for tok in goal_paths:
                if _path_hit(tok, pattern):
                    return (cls, "path", pattern, "goal")
            for tok in scope_paths:
                if _path_hit(tok, pattern):
                    return (cls, "path", pattern, "SCOPE_LOCK")
    return None


def read_scope_lock(mem_dir: Path) -> str:
    """SCOPE_LOCK.md lives next to the memory dir: <project>/.itd/SCOPE_LOCK.md.

    A missing file is an empty scope (legitimate); an EXISTING file that cannot be read or
    decoded is a safety input that failed - fail closed instead of silently matching nothing.
    """
    path = Path(mem_dir).resolve().parent / ".itd" / "SCOPE_LOCK.md"
    # lexists: a dangling or looping symlink still IS an entry the owner put there - a
    # failure to read it must not degrade into "no scope" (checker c12)
    if not os.path.lexists(path):
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise StrictClassPolicyError(f"{path} exists but cannot be read as UTF-8 text: {exc}") from exc


def describe(hit) -> str:
    cls, kind, pattern, where = hit
    return f"strict class '{cls}' matched {kind} '{pattern}' in {where}"
