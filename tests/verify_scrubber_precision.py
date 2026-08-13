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


def main() -> int:
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
