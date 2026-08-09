"""Reviewer independence policy regression (GPG-004 PC1..PC3).

Proves the closed maker/reviewer independence class {anthropic, openai},
the flagged same-vendor-different-model fallback, the audited
HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW class, and identity-deduplicated
reviewer quorum counting. The producer section carries the RED-first pin of
the live anthropic-maker dead-end: it turns GREEN only when the batched
producer slice teaches the mandatory route the independence class.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "skills" / "_shared" / "itd_reviewer_independence.py"
PRODUCER = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"

checks = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(f"{name}: {detail}"[:400])


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load_module(POLICY, "itd_reviewer_independence_under_test")
producer = load_module(PRODUCER, "itd_free_reviewer_producer_under_test")


def status_of(callable_, *args):
    """Run a policy call and return its typed status or 'ACCEPTED'."""
    try:
        callable_(*args)
    except policy.IndependenceError as error:
        return error.status
    return "ACCEPTED"


def maker(provider="anthropic-subscription", model="opus", session="maker-1"):
    return {"provider": provider, "model": model, "session": session}


def reviewer(provider="openai-subscription", model="gpt-5.6-terra",
             session="reviewer-1"):
    return {"provider": provider, "model": model, "session": session}


UNAVAILABLE_CROSS = {
    "status": "UNAVAILABLE", "route": "cross-vendor",
    "detail": "anthropic transport is not part of the mandatory keyless route",
}
UNAVAILABLE_FALLBACK = {
    "status": "UNAVAILABLE", "route": "same-vendor-different-model",
    "detail": "no same-vendor alternate model is installed",
}

# --- Drift guards: the policy map cannot diverge from the producer ---

check(
    "drift/provider-families-equal",
    policy.PROVIDER_FAMILIES == producer.PROVIDER_FAMILIES,
    "policy PROVIDER_FAMILIES diverges from the producer copy",
)
check(
    "drift/alternates-symmetric",
    all(
        producer.OPENAI_REVIEW_MODEL_ALTERNATES.get(v) == k
        for k, v in producer.OPENAI_REVIEW_MODEL_ALTERNATES.items()
    ),
    "OPENAI_REVIEW_MODEL_ALTERNATES is not symmetric",
)

# --- PC1: closed class, unknown vendors fail closed, no self-review ---

check(
    "class/anthropic-maker-resolves-openai",
    policy.independent_reviewer_vendors(maker()) == ("openai",),
)
check(
    "class/openai-maker-resolves-anthropic",
    policy.independent_reviewer_vendors(
        maker(provider="openai-subscription", model="gpt-5.6-sol")
    ) == ("anthropic",),
)
check(
    "class/claude-alias-resolves",
    policy.independent_reviewer_vendors(maker(provider="claude")) == ("openai",),
)
check(
    "class/codex-alias-resolves",
    policy.independent_reviewer_vendors(
        maker(provider="codex", model="gpt-5.6-sol")
    ) == ("anthropic",),
)
for provider in ("gemini", "google", "antigravity-user", "github-copilot"):
    check(
        f"class/outside-class-unavailable-{provider}",
        status_of(policy.independent_reviewer_vendors, maker(provider=provider))
        == "UNAVAILABLE",
        "a vendor outside {anthropic, openai} anchored an independent pair",
    )
check(
    "class/unknown-provider-unavailable",
    status_of(policy.independent_reviewer_vendors, maker(provider="mystery-ai"))
    == "UNAVAILABLE",
)
check(
    "class/malformed-maker-unverified",
    status_of(policy.independent_reviewer_vendors, {"provider": "claude"})
    == "UNVERIFIED",
)

check(
    "classify/anthropic-openai-cross-vendor",
    policy.classify_independence(maker(), reviewer()) == policy.CROSS_VENDOR,
)
check(
    "classify/sol-terra-same-vendor",
    policy.classify_independence(
        maker(provider="openai-subscription", model="gpt-5.6-sol"),
        reviewer(),
    ) == policy.SAME_VENDOR_DIFFERENT_MODEL,
)
check(
    "classify/same-model-rejected",
    status_of(
        policy.classify_independence,
        maker(provider="openai-subscription", model="gpt-5.6-terra"),
        reviewer(model="GPT-5.6-TERRA"),
    ) == "UNVERIFIED",
    "a same-model pair was classified as independent",
)
check(
    "classify/self-review-rejected",
    status_of(
        policy.classify_independence,
        maker(session="shared"), reviewer(session="shared"),
    ) == "UNVERIFIED",
    "a shared maker/reviewer session was classified as independent",
)
check(
    "classify/reviewer-outside-class-unverified",
    status_of(
        policy.classify_independence, maker(), reviewer(provider="gemini"),
    ) == "UNVERIFIED",
)
check(
    "classify/maker-outside-class-unavailable",
    status_of(
        policy.classify_independence, maker(provider="gemini"), reviewer(),
    ) == "UNAVAILABLE",
)

# --- PC2: flagged fallback — never silent, never laundered ---

granted = policy.authorize_same_vendor_fallback(
    maker(provider="openai-subscription", model="gpt-5.6-sol"),
    reviewer(), dict(UNAVAILABLE_CROSS),
)
check(
    "fallback/honest-label",
    granted["independenceLevel"] == policy.SAME_VENDOR_DIFFERENT_MODEL
    and granted["independenceLevel"] != policy.CROSS_VENDOR
    and granted["crossVendorUnavailability"] == UNAVAILABLE_CROSS,
    "fallback authorization did not carry the honest label and evidence",
)
check(
    "fallback/silent-selection-rejected",
    status_of(
        policy.authorize_same_vendor_fallback,
        maker(provider="openai-subscription", model="gpt-5.6-sol"),
        reviewer(), None,
    ) == "UNVERIFIED",
    "a fallback was granted without typed cross-vendor unavailability",
)
check(
    "fallback/untyped-evidence-rejected",
    status_of(
        policy.authorize_same_vendor_fallback,
        maker(provider="openai-subscription", model="gpt-5.6-sol"),
        reviewer(),
        {**UNAVAILABLE_CROSS, "status": "ERROR"},
    ) == "UNVERIFIED",
)
check(
    "fallback/wrong-route-evidence-rejected",
    status_of(
        policy.authorize_same_vendor_fallback,
        maker(provider="openai-subscription", model="gpt-5.6-sol"),
        reviewer(),
        {**UNAVAILABLE_CROSS, "route": "same-vendor-different-model"},
    ) == "UNVERIFIED",
)
check(
    "fallback/cross-vendor-pair-not-laundered",
    status_of(
        policy.authorize_same_vendor_fallback,
        maker(), reviewer(), dict(UNAVAILABLE_CROSS),
    ) == "UNVERIFIED",
    "fallback authorization accepted a pair that is not same-vendor",
)
check(
    "fallback/same-model-pair-rejected",
    status_of(
        policy.authorize_same_vendor_fallback,
        maker(provider="openai-subscription", model="gpt-5.6-terra"),
        reviewer(), dict(UNAVAILABLE_CROSS),
    ) == "UNVERIFIED",
)

# --- PC3: audited human override is never a review ---

DIGEST = "d" * 64
override = {
    "outcome": policy.HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW,
    "candidateDigest": DIGEST,
    "confirmedBy": "hihol",
    "reason": "no reviewer transport is reachable on this host",
    "crossVendorUnavailability": dict(UNAVAILABLE_CROSS),
    "fallbackUnavailability": dict(UNAVAILABLE_FALLBACK),
}
validated = policy.validate_human_override(dict(override), DIGEST)
check(
    "override/valid-record-accepted",
    validated["outcome"] == policy.HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW,
)
check(
    "override/never-counts-as-review",
    policy.independent_review_satisfied(validated["outcome"]) is False,
    "the override was counted as an independent review",
)
check(
    "override/passed-and-adjudicated-count",
    policy.independent_review_satisfied("PASSED") is True
    and policy.independent_review_satisfied("ADJUDICATED") is True,
)
check(
    "override/unknown-outcome-fails-closed",
    status_of(policy.independent_review_satisfied, "REVIEWED") == "UNVERIFIED",
)
check(
    "override/foreign-digest-rejected",
    status_of(policy.validate_human_override, dict(override), "e" * 64)
    == "UNVERIFIED",
    "an override bound to a foreign candidate was accepted",
)
check(
    "override/missing-confirmation-rejected",
    status_of(
        policy.validate_human_override,
        {**override, "confirmedBy": ""}, DIGEST,
    ) == "UNVERIFIED",
)
check(
    "override/wrong-literal-rejected",
    status_of(
        policy.validate_human_override,
        {**override, "outcome": "ADJUDICATED"}, DIGEST,
    ) == "UNVERIFIED",
)
check(
    "override/extra-key-rejected",
    status_of(
        policy.validate_human_override,
        {**override, "elevatedClaim": "cross-vendor"}, DIGEST,
    ) == "UNVERIFIED",
)
check(
    "override/missing-fallback-evidence-rejected",
    status_of(
        policy.validate_human_override,
        {**override, "fallbackUnavailability": dict(UNAVAILABLE_CROSS)},
        DIGEST,
    ) == "UNVERIFIED",
    "an override without typed fallback unavailability was accepted",
)

# --- PC4 support: quorum counts distinct identities only ---

BASE = {"provider": "openai-subscription", "model": "gpt-5.6-terra",
        "session": "quorum-a"}
check(
    "quorum/duplicate-identity-cannot-pad",
    status_of(
        policy.require_reviewer_quorum,
        [dict(BASE), {**BASE, "model": "GPT-5.6-TERRA"}], 2,
    ) == "UNVERIFIED",
    "one reviewer identity satisfied a quorum of two",
)
check(
    "quorum/distinct-identities-count",
    policy.require_reviewer_quorum(
        [dict(BASE),
         {"provider": "openai-subscription", "model": "gpt-5.6-sol",
          "session": "quorum-b"}], 2,
    ) == 2,
)
check(
    "quorum/reviewer-transport-sha-accepted",
    policy.count_independent_reviewers(
        [{**BASE, "transportExecutableSha256": "a" * 64}]
    ) == 1,
)
check(
    "quorum/malformed-identity-rejected",
    status_of(policy.count_independent_reviewers, [{"provider": "x"}])
    == "UNVERIFIED",
)
check(
    "quorum/out-of-range-minimum-rejected",
    status_of(policy.require_reviewer_quorum, [dict(BASE)], 4)
    == "UNVERIFIED",
)

# --- PC3 CLI channel: mint-override records an audited non-review outcome ---

import subprocess
import tempfile

LOOP = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
work = Path(tempfile.mkdtemp(prefix="itd-override-"))
subprocess.run(["git", "init", "-q", str(work)], check=True)
override_out = work / ".itd-memory" / "verification-loop" / "override.json"
override_cmd = [
    sys.executable, str(LOOP), "mint-override",
    "--root", str(work), "--unit-id", "U-override", "--risk-tier", "high",
    "--confirmed-by", "hihol",
    "--reason", "no reviewer transport is reachable on this host",
    "--cross-vendor-detail", "anthropic transport is not installed",
    "--fallback-detail", "no same-vendor alternate model is installed",
    "--output", str(override_out),
]
minted = subprocess.run(
    [*override_cmd, "--candidate-digest", "d" * 64],
    capture_output=True, text=True, cwd=str(work),
)
minted_row = (
    json.loads(override_out.read_text(encoding="utf-8"))
    if override_out.is_file() else {}
)
check(
    "cli/mint-override-happy-path",
    minted.returncode == 0
    and minted_row.get("outcome")
    == policy.HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW
    and minted_row.get("kind") == "itd-human-override-no-independent-review-v1"
    and minted_row.get("candidateDigest") == "d" * 64,
    f"exit {minted.returncode}: {minted.stderr[:200] or minted.stdout[:200]}",
)
check(
    "cli/mint-override-is-not-a-review",
    minted_row.get("outcome") not in ("PASSED", "ADJUDICATED")
    and policy.independent_review_satisfied(
        minted_row.get("outcome", "")
    ) is False
    if minted_row else False,
    "the minted override record was shaped as a review outcome",
)
rejected = subprocess.run(
    [*override_cmd, "--candidate-digest", "not-a-digest"],
    capture_output=True, text=True, cwd=str(work),
)
check(
    "cli/mint-override-rejects-bad-digest",
    rejected.returncode != 0 and "UNVERIFIED" in rejected.stdout,
    f"exit {rejected.returncode}: {rejected.stdout[:200]}",
)

# --- Producer pins: the live dead-end (RED until the producer batch) ---

try:
    producer.require_opposite_openai_model(
        {"provider": "anthropic-subscription", "model": "opus",
         "session": "maker-1"},
        {"provider": "openai-subscription", "model": "gpt-5.6-terra",
         "session": "reviewer-1",
         "transportExecutableSha256": "a" * 64},
    )
except producer.FreeReviewError as error:
    check(
        "producer/cross-vendor-anthropic-maker-accepted",
        False,
        f"RED (expected until the producer batch): typed {error.status} "
        "— an anthropic maker still cannot obtain the mandatory "
        "independent review",
    )
else:
    check("producer/cross-vendor-anthropic-maker-accepted", True)

print(json.dumps({
    "checks": checks, "failures": failures,
    "status": "PASSED" if not failures else "FAILED",
}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
