#!/usr/bin/env python3
"""Prove the residual-credential detector separates code from credentials.

S6-SCRUBBER (BACKLOG 2026-08-11, U16): an ordinary parser assignment —
``token = glued.group(1)`` in hooks/check-predeploy-gate.sh — and prose
quoting that same line both tripped ``contains_residual_credential`` and
refused two review routes outright. A detector that reads ordinary code
as a credential taxes every future candidate; a detector that misses a
literal credential leaks. Both directions are pinned here: every benign
exclusion has a true-positive antipair that must stay caught.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "skills" / "_shared" / "itd_external_reviewer.py"
PRODUCER = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"
spec = importlib.util.spec_from_file_location("itd_scrubber_precision_test", MODULE)
assert spec and spec.loader
reviewer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reviewer
spec.loader.exec_module(reviewer)

CHECKS = 0


def check(condition: bool, label: str) -> None:
    global CHECKS
    if not condition:
        raise AssertionError(label)
    CHECKS += 1


# Every sample below is assembled at runtime so this file's own bytes never
# match the scrubber whose diff they pass through: a plain sample here gets
# REDACTED in the outgoing review diff, mangling the quotes and making the
# file unreadable to an independent reviewer (route finding r5, 2026-08-13;
# same convention as verify_free_reviewer_producer).
_Q = '"'
_PW_NAME = "pass" + "word"
_KEY_NAME = "api" + "_key"
_SECRET_NAME = "sec" + "ret"
_TOKEN_NAME = "tok" + "en"

# --- False-positive corpus: ordinary code and prose about it -----------------
# FP-A: the exact incident shape — a variable named after a parsed word,
# assigned from a call / list element / interpolation, never a literal.
BENIGN = [
    # The recorded incident line (hooks/check-predeploy-gate.sh).
    "        " + _TOKEN_NAME + " = glued.group(1)",
    # Assignment from a list element (the BACKLOG wording of the incident).
    "    " + _TOKEN_NAME + " = tokens[position]",
    "    " + _SECRET_NAME + " = parts[2]",
    # Attribute chains ending in a call.
    _TOKEN_NAME + " = shlex.split(segment)",
    _KEY_NAME + " = os.environ.get(name)",
    # Shell interpolations, quoted and bare.
    _PW_NAME + "=" + _Q + "${parts[2]}" + _Q,
    _TOKEN_NAME + "=" + _Q + "$(parse_field)" + _Q,
    _SECRET_NAME + "=" + "$fields_value",
    _KEY_NAME + ": " + _Q + "${VAULT_REF}" + _Q,
    # FP-B: prose QUOTING the incident line re-triggered the detector while
    # documenting the false positive. Prose must not match either.
    "The route refused because `" + _TOKEN_NAME
    + " = glued.group(1)` looked like a leak.",
    "Renaming was needed after ``" + _SECRET_NAME
    + " = parts[2]`` tripped the detector.",
]

# --- True-positive antipairs: every exclusion above has a literal twin -------
CREDENTIALS = [
    # Quoted literal (antipair of the quoted interpolation).
    _PW_NAME + " = " + _Q + "hunter2" + "hunter2" + _Q,
    _KEY_NAME + ": '" + "sk_live_" + "abcdef123456'",
    # Bare literal (antipair of the bare interpolation / expression).
    _SECRET_NAME + "=" + "AKIA" + "IOSFODNN7EXAMPLE",
    _TOKEN_NAME + "=" + "eyJhbGciOiJIUzI1NiJ9" + ".payload",
    # A value that merely CONTAINS interpolation syntax is not pure code.
    _PW_NAME + " = " + _Q + "$uper" + "$ecretValue" + _Q,
    # Call-lookalike with an embedded quote stays flagged (status quo).
    _KEY_NAME + " = os.environ[" + _Q + "API_KEY" + _Q + "]",
    # QUOTED value that merely looks like a code expression is a string
    # literal, not code: the code-expression exemption is bare-only
    # (route finding r5, 2026-08-13).
    _TOKEN_NAME + " = " + _Q + "fetchKey()" + _Q,
    _SECRET_NAME + " = " + _Q + "parts[2]" + _Q,
    # Newline-continued quoted value (third alternative of the pattern),
    # including the continued call-lookalike.
    _PW_NAME + " =\n+    " + _Q + "hunter2" + "hunter2" + _Q,
    _TOKEN_NAME + " =\n+    " + _Q + "fetchKey()" + _Q,
    # Expression WRAPPERS around a literal are not benign (route finding r6,
    # 2026-08-13): a command substitution with arguments, a brace expansion
    # with a default value, or call arguments containing '#'/whitespace can
    # all embed a credential the scrubber cannot neutralise.
    _TOKEN_NAME + " = $(printf abcd" + "#efgh2026)",
    _SECRET_NAME + "=${x:-abcd" + "#efgh2026}",
    _TOKEN_NAME + " = fetch(abcd" + "#efgh2026)",
    _PW_NAME + " = wrap(hunter2 " + "hunter2)",
]


# --- RSI-DEBT-1: scrub() must agree with the detector on BARE code ----------
# The detector already exempts a bare value that is purely one code
# expression, but scrub() redacted every bare run of six or more characters
# after a secret-named assignment, so an independent reviewer saw
# `token = [REDACTED]` where the code said `token = self.w.HANDLE()` and
# raised a false NameError finding (Sol-fa2, ROUTE-DEBTS-FOLLOWUP-A13).
# Bare code stays intact; every literal shape below is still redacted.
SCRUB_INTACT = [
    # The recorded incident line (skills/_shared/itd_safe_atomic_windows.py).
    "            " + _TOKEN_NAME + " = self.w.HANDLE()",
    _TOKEN_NAME + " = shlex.split(segment)",
    "    " + _TOKEN_NAME + " = tokens[position]",
    "    " + _SECRET_NAME + " = parts[2]",
    # A multi-argument call is one expression for the detector (its bare run
    # admits commas), so scrub() must judge the same run and keep it.
    _PW_NAME + " = config.load(section,default)",
    # The recorded S6 incident line: a pure-digit argument is a name-shaped index.
    "        " + _TOKEN_NAME + " = glued.group(1)",
    # Name-shaped arguments survive: dotted and snake-case names, short words.
    _TOKEN_NAME + " = handler.run(self.value)",
    _SECRET_NAME + " = retry(default_timeout)",
    # Sol-r4: ordinary long identifiers stay readable - a plain word and a
    # short camelCase name are name-shaped even without `_` or `.`.
    _TOKEN_NAME + " = fetch(configuration)",
    _SECRET_NAME + " = cache[identifier]",
    _PW_NAME + " = load(configValue)",
    # Sol-r5: a statement terminator ends the bare run, so a C/JS-style line
    # keeps its call and a second statement on the same line stays visible.
    _TOKEN_NAME + " = fetch(configuration);",
    _PW_NAME + " = load(section); check(default)",
    # Prose quoting the incident line keeps its backtick tail.
    "The line `" + _TOKEN_NAME + " = self.w.HANDLE()` is ordinary code.",
]
SCRUB_REDACTED = [
    # Bare literals: an opaque run is redacted exactly as before.
    _SECRET_NAME + "=" + "AKIA" + "IOSFODNN7EXAMPLE",
    _TOKEN_NAME + "=" + "eyJhbGciOiJIUzI1NiJ9" + ".payload",
    # Quoted values are string literals, call-lookalike or not.
    _PW_NAME + " = " + _Q + "hunter2" + "hunter2" + _Q,
    _TOKEN_NAME + " = " + _Q + "fetchKey()" + _Q,
    # Expression wrappers that can carry a literal are not benign.
    _TOKEN_NAME + " = fetch(abcd" + "#efgh2026)",
    _PW_NAME + " = wrap(hunter2 " + "hunter2)",
    _KEY_NAME + " = os.environ[" + _Q + "API_KEY" + _Q + "]",
    # Whitespace inside call arguments leaves the narrow grammar (route
    # finding r6): the detector flags it, so scrub() must redact it too.
    _PW_NAME + " = config.load(section, default)",
    # Sol-r2 (RSI-DEBT-1): a credential planted as a call argument or index
    # rides inside an otherwise benign expression; the argument is
    # neutralised in place while the callee chain stays readable.
    _TOKEN_NAME + " = fetch(hunter2" + "hunter2)",
    _SECRET_NAME + " = config.load(section,AKIA" + "IOSFODNN7EXAMPLE)",
    _TOKEN_NAME + " = cache[eyJhbGciOiJIUzI1NiJ9" + "payload]",
    # A value that was never six characters before its first "#" used to
    # escape the bare rule whole; the bare run is now the detector's run.
    _TOKEN_NAME + "=abc" + "#def123",
    # Sol-r3: an all-letter or all-digit credential as an argument was
    # redacted wholesale before the exemption; it must not ride through now.
    _TOKEN_NAME + " = fetch(hunter" + "hunterhunter)",
    _SECRET_NAME + " = lookup(1234" + "56789012)",
    # Subagent r5: case mixing is not a name signal - a camelCase passphrase
    # or a random-cased run longer than fourteen letters is still a credential.
    _TOKEN_NAME + " = fetch(correctHorse" + "BatteryStaple)",
    _TOKEN_NAME + " = fetch(Secret" + "PasswordXyz)",
    _KEY_NAME + " = lookup(aBcDeFgH" + "iJkLmNoP)",
    # Sol-r5: the run stops at ';', so the literal is redacted and the
    # statement after it is not swallowed (exact pin below).
    _TOKEN_NAME + "=abcdef" + "ghij;run()",
]


def main() -> int:
    for sample in SCRUB_INTACT:
        clean, redactions = reviewer.scrub(sample)
        check(
            clean == sample and redactions == 0,
            f"scrub() redacted ordinary bare code: {sample!r} -> {clean!r}",
        )
    for sample in SCRUB_REDACTED:
        clean, redactions = reviewer.scrub(sample)
        value = sample.split("=", 1)[1].strip().strip(_Q + "'")
        check(
            redactions >= 1 and "REDACTED" in clean and value not in clean,
            f"scrub() left a literal credential readable: {sample!r} -> {clean!r}",
        )
    # Each neutralised argument is one redaction (subagent review, e5ecf3e9).
    two_args, two_count = reviewer.scrub(
        _TOKEN_NAME + " = data[abcdef" + "123456,ghijkl" + "789012]"
    )
    check(
        two_args == _TOKEN_NAME + " = data[REDACTED-ARGUMENT,REDACTED-ARGUMENT]"
        and two_count == 2,
        f"two neutralised arguments must count as two redactions: {two_args!r} {two_count}",
    )
    callee_kept, _ = reviewer.scrub(_TOKEN_NAME + " = fetch(hunter2" + "hunter2)")
    check(
        callee_kept == _TOKEN_NAME + " = fetch(REDACTED-ARGUMENT)",
        f"neutralised argument did not keep the callee readable: {callee_kept!r}",
    )
    # Sol-r5: the bare run ends at ';', so the statement after a redacted
    # literal stays visible instead of vanishing inside [REDACTED].
    after_semicolon, _ = reviewer.scrub(_TOKEN_NAME + "=abcdef" + "ghij;run()")
    check(
        after_semicolon == _TOKEN_NAME + "=[REDACTED];run()",
        f"statement after ';' was swallowed by the redaction: {after_semicolon!r}",
    )
    # The scrubbed text must never trip the residual detector itself: a
    # neutralised subscript that reads cache[[REDACTED]] is not one subscript
    # for the detector's grammar and would refuse the route on already-safe
    # text (subagent review of RSI-DEBT-1). Pinned for the whole corpus.
    for sample in SCRUB_INTACT + SCRUB_REDACTED:
        clean, _ = reviewer.scrub(sample)
        check(
            not reviewer.contains_residual_credential(clean),
            f"scrubbed output trips the residual detector: {sample!r} -> {clean!r}",
        )
    for sample in BENIGN:
        check(
            not reviewer.contains_residual_credential(sample),
            f"false positive on benign code/prose: {sample!r}",
        )
    for sample in CREDENTIALS:
        check(
            reviewer.contains_residual_credential(sample),
            f"missed literal credential: {sample!r}",
        )

    # The high-confidence and entropy detectors are out of this unit's scope
    # and must keep their behaviour on the incident line.
    check(
        not reviewer.contains_high_confidence_secret(
            _TOKEN_NAME + " = glued.group(1)"
        ),
        "high-confidence detector regressed on ordinary code",
    )

    # --- Producer contract: detection runs on the SCRUBBED text -------------
    # Route contract (itd_free_reviewer_producer._safe_review_text comment):
    # only a credential the scrubber could NOT neutralise refuses the route.
    # The reviewer receives scrubbed text, so a raw-only hit over-refuses.
    source = PRODUCER.read_text(encoding="utf-8")
    check(
        "contains_residual_credential(clean)" in source
        and "contains_residual_credential(text)" not in source,
        "producer must run the residual-credential detector on scrubbed text",
    )
    check(
        "contains_high_confidence_secret(clean)" in source
        and "contains_high_confidence_secret(text)" not in source,
        "producer must run the high-confidence detector on scrubbed text",
    )
    check(
        "contains_high_entropy_token(clean)" in source
        and "contains_high_entropy_token(text)" not in source,
        "producer must run the entropy detector on scrubbed text",
    )

    # A neutralised (scrubbed) credential must still never reach a reviewer:
    # the scrubbed form is inert for every detector.
    clean, redactions = reviewer.scrub(
        _PW_NAME + " = " + _Q + "hunter2" + "hunter2" + _Q
    )
    if redactions:
        check(
            not reviewer.contains_residual_credential(clean),
            "scrubbed output itself trips the detector",
        )
    else:
        # scrub() does not neutralise this shape: detection on clean text
        # must then refuse it — fail-closed is preserved end to end.
        check(
            reviewer.contains_residual_credential(clean),
            "unneutralised credential escaped clean-text detection",
        )

    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
