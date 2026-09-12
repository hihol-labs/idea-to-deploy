#!/usr/bin/env python3
"""Oracle: exhaustive enumeration inside one review call's bound material
(ROUTE-REPAIR-1, 2026-09-12).

Measured cause, not a hunch. RSI-DEBT-2 ran ten consecutive live cross-vendor
rounds on one medium-risk unit, zero false positives, no clean PASS. The
per-round reports were read while they still existed in the producing session's
working directory: 16 finding rows, 14 distinct file-and-line pairs, across four
files. The earlier session's own record says twelve findings were closed; the
two counts disagree, the source reports are no longer on disk, so the
discrepancy is recorded here rather than reconciled.

The conclusion does not rest on the exact count. It rests on per-round yield and
on locality: one to two findings per round for ten rounds, with round 1 naming
line 74 of one file, round 2 line 69, round 3 line 72. The reviewer looked at
the same place each round and returned the next defect a few lines away. So the
surface was not growing - the yield of ONE call was one to two findings while
the bound material held several simultaneous defects.

The prompt contract never asked for more. `PASSED requires findings=[]` means a
single high finding already justifies BLOCKED, so enumerating the rest earns the
call nothing. This oracle binds the missing duty:

  1. single source - the requirement is emitted from one module constant and
     reaches the direct, unit and integration prompts verbatim, never as a
     private per-kind copy;
  2. trusted position - it sits after all untrusted review material, inside the
     trusted output block, so candidate bytes cannot override it;
  3. content - list every defect located in the bound material; a BLOCKED
     verdict naming fewer defects than the call located is itself a defect of
     the review; severity rank licenses no omission; nothing unfound is
     invented, because the measured false-positive count of this route is zero
     and guesses would buy that class back.

Two check families, and the difference matters. Everything structural -
single source, verbatim inheritance by each prompt kind, the trusted tail as the
prompt's SUFFIX, the clean example parsed as JSON, both verdict schemas pinned by
digest - is proven by whole-object equality on really generated prompts built
from the producer's own partition code. The textual duties are polarity
properties over the constant, so a rewording survives and a semantic removal or
a direct negation fails.

DECLARED LIMIT, stated rather than papered over. No check here proves that the
prompt contains no semantic contradiction ANYWHERE. Four separate reviews found
that same class - keyword presence accepting its inversion (round 1), a direct
negation carrying every keyword of the positive form (round 5), substring checks
on the closed-output contract (the publication round), and a contradiction added
in other words elsewhere in the prompt (the targeted checker). Each fix narrowed
the hole and left the class, because the property is not decidable by pattern
matching over arbitrary text.

Contradicting text has TWO entry channels, and only one of them is guarded.
Editing the producer's prompt builders is a code change the mutation set and the
reviewers see. The candidate diff is the other one: it is attacker-controlled and
emitted verbatim into the same prompt before the trusted tail, so a contradiction
can ride in a code comment or a spoofed note to the reviewer without touching
producer code at all. Against that channel this oracle proves only position - the
trusted tail is the suffix, so the instruction is read last - while the rest is
the prose rule that candidate text is data and never instructions, which is
instruction-following, not a proof. Naming that gap is the point of this
paragraph.
Self-contained:  sh skills/_shared/itd_py.sh tests/verify_review_enumeration.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"

PASSED = 0
FAILED = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  - " + detail) if detail else ""))


# Every untrusted section each prompt kind embeds. The trusted tail must follow
# all of them, and none of them may follow the tail.
UNTRUSTED_MARKERS = {
    "direct": (
        "FROZEN SCOPE", "FROZEN ACCEPTANCE", "MACHINE EVIDENCE",
        "EVIDENCE COVERAGE", "BEGIN UNTRUSTED REVIEW DIFF",
    ),
    "unit": (
        "BOUND_RANGE_FACTS=", "FILE_INVENTORY=", "FROZEN_SCOPE=",
        "FROZEN_ACTIVE_ACCEPTANCE=", "MACHINE_EVIDENCE_SUMMARY=",
        "EVIDENCE_COVERAGE=", "BEGIN UNTRUSTED DIFF UNIT",
    ),
    "integration": (
        "HIERARCHICAL_REVIEW_EVIDENCE=", "FROZEN_SCOPE=",
        "FROZEN_ACTIVE_ACCEPTANCE=", "EVIDENCE_COVERAGE=",
    ),
}

# The exact trusted tail each prompt kind must END with. Asserting the suffix
# is what proves no untrusted payload follows the trusted instruction.
TAILS = {
    "direct": lambda m: m._trusted_json_output_contract(m.VERDICT_SCHEMA),
    "unit": lambda m: m._trusted_json_output_contract(
        m.UNIT_VERDICT_SCHEMA, unit=True),
    "integration": lambda m: m._trusted_json_output_contract(m.VERDICT_SCHEMA),
}

# The exact sentence each prompt kind emits for the empty-list condition.
# Whole-sentence equality, not substring presence, is what makes a negated
# variant impossible to satisfy.
PASSED_CONDITION = {
    "direct": "PASSED requires findings=[] and unverified=[].",
    "integration": (
        "PASSED requires complete unit coverage, findings=[], and unverified=[]."
    ),
}


def clean_output_example(prompt: str) -> dict | None:
    """Parse the single CLEAN_OUTPUT_EXAMPLE the prompt emits, or None."""
    matches = re.findall(r"^CLEAN_OUTPUT_EXAMPLE=(.*)$", prompt, flags=re.MULTILINE)
    if len(matches) != 1:
        return None
    try:
        value = json.loads(matches[0])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


# Frozen by this unit's scope: neither verdict schema changes.
SCHEMA_PINS = {
    "VERDICT_SCHEMA":
        "68e8fce79a78929511e5ffaa1e2e804d7e721943470f2725c462bc17eda28fe9",
    "UNIT_VERDICT_SCHEMA":
        "d1b791a949ff1b6b991311170fd3ee9800e7bc6a7df39b2fb7342ad6de029bdf",
}

DUTIES = (
    ("every located defect must be listed",
     "the clause does not demand the complete list"),
    ("a short BLOCKED list is a defect of the review itself",
     "the clause does not name an incomplete BLOCKED list as a defect"),
    ("severity rank licenses no omission",
     "the clause does not DENY severity rank as a reason to stop"),
    ("nothing unfound is invented",
     "the clause does not FORBID guessing, so it buys false findings"),
    ("the duty is bounded to this call's own material",
     "the clause does not bind the duty to the call's own range"),
)


def content_violations(text: str) -> set[str]:
    """Name the duties this text fails, by polarity rather than by keyword.

    A keyword-presence check accepts its own inversion: "Severity rank licenses
    omission" contains `severity`, and "Invent a defect to lengthen the list"
    contains `invent`. Each rule below therefore requires the negative form,
    and `inverted_clauses` proves the rules discriminate.
    """
    low = re.sub(r"\s+", " ", text.casefold())
    failed: set[str] = set()
    # Requiring the keywords is not enough even with a permissive-phrase guard:
    # "Do not list every defect you located" carries every keyword and states
    # the opposite duty. Each rule therefore also rejects its own negated form.
    negated = r"(do not|do  not|don't|never|no need to|need not)\s+"
    if (
        "every defect" not in low
        or not re.search(r"locate|found", low)
        or re.search(r"(?<!not )only the (strongest|most severe|highest)", low)
        or re.search(negated + r"(list|report|name|enumerate)[^.]*every defect", low)
        or re.search(r"every defect[^.]*(is|are) not (required|needed)", low)
    ):
        failed.add("every located defect must be listed")
    if (
        not re.search(r"blocked verdict[^.]*fewer defects", low)
        or not re.search(r"itself a defect|defect of this review", low)
        or re.search(r"(is|are) not (itself )?a defect", low)
    ):
        failed.add("a short BLOCKED list is a defect of the review itself")
    if not re.search(
        r"severity[^.]*(licenses no omission|licences no omission"
        r"|does not discharge|no licence to omit|no license to omit)", low
    ):
        failed.add("severity rank licenses no omission")
    if not re.search(r"(do not|don't|never)[^.]*(invent|guess|speculat)", low):
        failed.add("nothing unfound is invented")
    if not re.search(r"bound (material|range)", low):
        failed.add("the duty is bounded to this call's own material")
    return failed


def inverted_clauses(clause: str) -> list[tuple[str, str, str]]:
    """One inversion per duty, built by replacing the clause's own sentences."""
    plans = [
        ("severity rank is allowed to license omission",
         "Severity rank licenses no omission, so a high finding does not "
         "discharge the duty to list the medium ones beside it.",
         "Severity rank licenses omission, so a high finding discharges the "
         "duty to list the medium ones beside it.",
         "severity rank licenses no omission"),
        ("invention is instructed instead of forbidden",
         "Do not invent or guess a defect to lengthen the list",
         "Invent or guess a defect to lengthen the list",
         "nothing unfound is invented"),
        ("a one-item BLOCKED list is called complete",
         "A BLOCKED verdict that names fewer defects than you located is "
         "itself a defect of this review",
         "A BLOCKED verdict that names one defect is a complete review",
         "a short BLOCKED list is a defect of the review itself"),
        ("only the strongest defect is requested",
         "List every defect you located inside the bound material you were "
         "given, not only the strongest one.",
         "List only the strongest defect you located inside the bound "
         "material you were given.",
         "every located defect must be listed"),
        ("the duty loses its bound scoping",
         "bound material you were given",
         "candidate you were given",
         "the duty is bounded to this call's own material"),
        # Round 5 of independent review found this class: a DIRECT negation
        # carries every keyword the positive form carries.
        ("the completeness duty is directly negated",
         "List every defect you located inside the bound material you were "
         "given, not only the strongest one.",
         "Do not list every defect you located inside the bound material you "
         "were given.",
         "every located defect must be listed"),
        ("the BLOCKED duty is directly negated",
         "is itself a defect of this review",
         "is not itself a defect of this review",
         "a short BLOCKED list is a defect of the review itself"),
    ]
    result: list[tuple[str, str, str]] = []
    for label, source, replacement, duty in plans:
        variant = clause.replace(source, replacement)
        if duty == "the duty is bounded to this call's own material":
            variant = variant.replace("a bound range you reviewed",
                                      "a candidate you reviewed")
        result.append((label, variant, duty))
    return result


def load_producer():
    spec = importlib.util.spec_from_file_location("itd_review_enumeration", PRODUCER)
    if spec is None or spec.loader is None:
        raise AssertionError("keyless review producer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_packet(producer) -> dict[str, object]:
    """Build one hierarchical packet from the producer's own partition code.

    The plan and its bound units come from `_attach_review_plan`, which reuses
    the broker's frozen partition, so the packet this oracle reviews is shaped
    by production code rather than by a hand-written fixture.
    """
    # Two files, each over the direct bound, so the frozen partition really
    # produces more than one unit and the hierarchical prompts are reachable.
    # Total must land between the direct bound (80 KB) and the
    # hierarchical bound (1.2 MB) so the frozen partition really splits.
    filler = "+" + ("enumeration bound material " * 60) + "\n"
    LINES = 62
    chunks: list[tuple[str, str]] = []
    for index in (1, 2):
        path = f"src/bound_{index}.py"
        body = "".join(filler for _ in range(LINES))
        chunk = (
            f"diff --git a/{path} b/{path}\n"
            "new file mode 100644\n"
            "index 0000000000000000000000000000000000000000..1111111111111111111111111111111111111111\n"
            f"--- /dev/null\n+++ b/{path}\n"
            f"@@ -0,0 +1,{LINES} @@\n"
            f"{body}"
        )
        chunks.append((path, chunk))
    diff_text = "".join(chunk for _path, chunk in chunks)
    encoded = diff_text.encode("utf-8")
    representation = producer._attach_review_plan(diff_text, chunks, {
        "algorithm": "git-binary-full-index-v1",
        "reviewDiffSha256": producer.sha256_bytes(encoded),
        "reviewDiffBytes": len(encoded),
        "transparentFileCount": 0,
    })
    if representation.get("reviewMode") != "hierarchical":
        raise AssertionError(
            "oracle fixture stayed direct; the partition bound changed"
        )
    return {
        "version": 1,
        "kind": "itd-free-review-packet",
        "target": {
            "repository": "hihol-labs/idea-to-deploy",
            "pullRequest": None,
            "expectedHeadSha": None,
        },
        "candidate": {
            "baseCommit": "0" * 40,
            "parentCommit": "1" * 40,
            "tree": "2" * 40,
            "diffSha256": producer.sha256_bytes(encoded),
            "diffBytes": len(encoded),
        },
        "scope": {"sha256": "3" * 64, "text": "frozen scope for the oracle"},
        "acceptance": {"sha256": "4" * 64, "value": {"criterion": "bound"}},
        "machineEvidence": {"sha256": "5" * 64, "kind": "machine", "runs": []},
        "reviewRepresentation": representation,
        "diff": diff_text,
    }


def unit_report(producer) -> dict[str, object]:
    return {
        "verdict": "PASSED",
        "findings": [],
        "unverified": [],
        "summary": "bound range reviewed; no cross-unit interface at risk",
    }


def main() -> int:
    producer = load_producer()
    source = PRODUCER.read_text(encoding="utf-8")

    clause = getattr(producer, "ENUMERATION_REQUIREMENT", None)
    check(
        "single source: producer exposes ENUMERATION_REQUIREMENT",
        isinstance(clause, str) and bool(clause.strip()),
        "the requirement has no single module constant to be emitted from",
    )
    if not isinstance(clause, str) or not clause.strip():
        print(f"\n{PASSED} passed, {FAILED} failed")
        return 1

    # --- content of the requirement, by polarity not by keyword presence ----
    for duty, detail in DUTIES:
        check(
            f"content: {duty}",
            duty not in content_violations(clause),
            detail,
        )

    # --- negative cases: an inverted clause must NOT satisfy its duty ------
    # Keyword presence alone would accept "Severity rank licenses omission" and
    # "Invent a defect to lengthen the list", because both carry the keyword.
    # Each variant below inverts exactly one duty and must be rejected for it.
    for label, variant, expected_duty in inverted_clauses(clause):
        check(
            f"negative case rewrites the clause: {label}",
            variant != clause,
            "the replacement did not apply, so this negative case proves nothing",
        )
        check(
            f"negative case is rejected: {label}",
            expected_duty in content_violations(variant),
            f"an inverted clause still satisfies {expected_duty}",
        )

    # --- single source: no private per-kind copies in the module ------------
    # Compare with quotes and whitespace squeezed out, so the check survives
    # the constant being split across adjacent string literals but still
    # catches a second copy pasted into one prompt builder.
    sentence = clause.strip().split(".")[0].strip()
    squeezed_source = re.sub(r'["\s]+', "", source)
    squeezed_sentence = re.sub(r'["\s]+', "", sentence)
    copies = squeezed_source.count(squeezed_sentence)
    check(
        "single source: the clause text appears once in the module",
        len(squeezed_sentence) > 20 and copies == 1,
        f"copies={copies}; a per-kind copy can drift",
    )
    emissions = source.count("{ENUMERATION_REQUIREMENT}")
    check(
        "single source: the constant is emitted from exactly one place",
        emissions == 1,
        f"emissions={emissions}; each prompt kind must inherit the one tail",
    )

    # --- the trusted tail carries it for both schemas -----------------------
    direct_tail = producer._trusted_json_output_contract(producer.VERDICT_SCHEMA)
    unit_tail = producer._trusted_json_output_contract(
        producer.UNIT_VERDICT_SCHEMA, unit=True,
    )
    check(
        "trusted tail (direct schema) carries the requirement exactly once",
        direct_tail.count(clause) == 1,
        f"occurrences={direct_tail.count(clause)}",
    )
    check(
        "trusted tail (unit schema) carries the requirement exactly once",
        unit_tail.count(clause) == 1,
        f"occurrences={unit_tail.count(clause)}",
    )
    for label, tail in (("direct", direct_tail), ("unit", unit_tail)):
        begin = tail.find("BEGIN TRUSTED OUTPUT CONTRACT")
        end = tail.find("END TRUSTED OUTPUT CONTRACT")
        position = tail.find(clause)
        check(
            f"trusted block ({label}) encloses the requirement",
            -1 < begin < position < end,
            f"begin={begin} clause={position} end={end}",
        )

    # --- really generated prompts of all three kinds ------------------------
    packet = synthetic_packet(producer)
    plan, units = producer._hierarchical_units(packet)
    check(
        "fixture: the frozen partition produced a hierarchical plan",
        plan is not None and len(units) > 1,
        f"units={len(units)}",
    )
    if plan is None or not units:
        print(f"\n{PASSED} passed, {FAILED} failed")
        return 1

    direct_packet = dict(packet)
    direct_representation = {
        key: value for key, value in packet["reviewRepresentation"].items()
        if key != "reviewPlan"
    }
    direct_representation["reviewMode"] = "direct"
    direct_packet["reviewRepresentation"] = direct_representation
    direct_prompt = producer.review_prompt(direct_packet)
    unit, unit_diff = units[0]
    unit_prompt = producer._unit_review_prompt(packet, plan, unit, unit_diff)
    reports = [
        {"unit": row_unit, "report": unit_report(producer)}
        for row_unit, _text in units
    ]
    integration_prompt = producer._integration_review_prompt(packet, plan, reports)

    prompts = {
        "direct": (direct_prompt, UNTRUSTED_MARKERS["direct"]),
        "unit": (unit_prompt, UNTRUSTED_MARKERS["unit"]),
        "integration": (integration_prompt, UNTRUSTED_MARKERS["integration"]),
    }
    for label, (prompt, markers) in prompts.items():
        occurrences = prompt.count(clause)
        check(
            f"{label} prompt carries the requirement verbatim exactly once",
            occurrences == 1,
            f"occurrences={occurrences}",
        )
        position = prompt.find(clause)
        # Marker OFFSETS are not enough, in either direction. A start token is
        # not an end marker: a prompt could emit the marker name, open the
        # trusted block with the clause, and only then append the section body,
        # satisfying every offset comparison while the attacker-controlled
        # payload still follows the trusted instruction. The property that
        # actually holds is stronger and simpler - the trusted tail is the
        # SUFFIX of the prompt, so by construction nothing follows it.
        tail = TAILS[label](producer)
        check(
            f"{label} prompt ends with the trusted tail, so nothing follows it",
            prompt.endswith(tail),
            "the trusted tail is not the prompt's suffix; something follows it",
        )
        check(
            f"{label} trusted tail carries the requirement",
            tail.count(clause) == 1,
            f"occurrences in the tail={tail.count(clause)}",
        )
        offsets = {name: prompt.find(name) for name in markers}
        check(
            f"{label} prompt fixture carries every untrusted section",
            all(offset >= 0 for offset in offsets.values()),
            f"absent={sorted(n for n, o in offsets.items() if o < 0)}",
        )
        begin = prompt.find("BEGIN TRUSTED OUTPUT CONTRACT")
        end = prompt.find("END TRUSTED OUTPUT CONTRACT")
        check(
            f"{label} prompt emits every untrusted section before the trusted block",
            begin >= 0 and offsets and max(offsets.values()) < begin,
            f"last untrusted={max(offsets.values(), default=-1)} begin={begin}",
        )
        check(
            f"{label} prompt keeps the requirement inside the trusted block",
            -1 < begin < position < end,
            f"begin={begin} clause={position} end={end}",
        )

    # --- byte-for-byte identity across the three kinds ----------------------
    check(
        "the three prompt kinds carry byte-identical requirement text",
        all(clause in prompt for prompt, _markers in prompts.values()),
        "a kind carries a reworded copy instead of the shared constant",
    )

    # --- the requirement does not weaken the closed output contract ---------
    check(
        "the closed output contract still demands one JSON object",
        all(
            "exactly one RFC 8259 JSON object" in prompt
            for prompt, _markers in prompts.values()
        ),
        "the trusted tail lost its closed-output instruction",
    )
    # The empty-list condition is stated differently per kind, so assert it per
    # kind rather than only where the phrase happens to appear. The direct and
    # integration prompts spell the condition out in prose; the unit prompt
    # carries it through its clean example and its pinned schema, so a unit-only
    # deletion cannot hide behind the other two.
    # Presence of `findings=[]` proves nothing about polarity: the publication
    # round found that "PASSED does not require findings=[]" satisfies it, the
    # same hole the enumeration duties already closed. Match the whole sentence
    # each kind actually emits, and reject any negation of it.
    for label, prompt, sentence in (
        ("direct", direct_prompt, PASSED_CONDITION["direct"]),
        ("integration", integration_prompt, PASSED_CONDITION["integration"]),
    ):
        low = re.sub(r"\s+", " ", prompt.casefold())
        check(
            f"{label} prompt states the empty-list condition for PASSED verbatim",
            sentence in re.sub(r"\s+", " ", prompt),
            "the sentence the producer emits is not present unchanged",
        )
        # DECLARED LIMIT. This is a tripwire for the literal negated forms, not
        # a proof that no contradiction exists anywhere in the prompt. That
        # stronger property is undecidable by pattern matching over arbitrary
        # text: a targeted checker reproduced a prompt that keeps the positive
        # sentence verbatim and cancels it in other words elsewhere, and every
        # wider regex would have the same shape of hole. What IS proven is the
        # structural part above - the sentence and the clause come from the
        # producer's own constants, and the trusted tail is the prompt's
        # suffix - so contradicting text can only enter by editing the prompt
        # builders, which is a code change the mutations and the reviewers see.
        check(
            f"{label} prompt carries no LITERAL negation of the condition (tripwire)",
            not re.search(r"passed[^.]*(does not require|need not|without)[^.]*findings=\[\]", low),
            "a literally negated form of the condition appears in the prompt",
        )
    # Two independent substrings would let a non-empty PASSED example pass when
    # any unrelated empty list survives elsewhere. Parse the example instead.
    example = clean_output_example(unit_prompt)
    check(
        "unit prompt carries exactly one parseable clean example",
        example is not None,
        "CLEAN_OUTPUT_EXAMPLE is absent, duplicated or not valid JSON",
    )
    check(
        "the unit clean example is PASSED with empty findings and unverified",
        example is not None
        and example.get("verdict") == "PASSED"
        and example.get("findings") == []
        and example.get("unverified") == [],
        f"clean example={json.dumps(example, sort_keys=True) if example else None}",
    )
    # Two key names present would survive a changed verdict vocabulary, new
    # required fields, a relaxed additionalProperties or any edit to the unit
    # schema. The frozen requirement is that BOTH schemas stay untouched, so
    # both are pinned by digest. A deliberate schema change must update this
    # pin in the same commit that changes the schema.
    for name, pinned in SCHEMA_PINS.items():
        schema = getattr(producer, name, None)
        actual = (
            hashlib.sha256(
                json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if schema is not None else "absent"
        )
        check(
            f"{name} is untouched by this unit",
            actual == pinned,
            f"digest {actual[:16]} != pinned {pinned[:16]}",
        )

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
