"""Reviewer independence policy for the maker/reviewer pair (GPG-004).

The closed independence class makes reviewer independence an executable
policy instead of a hard-coded Sol/Terra convention:

- ``cross-vendor``: maker and reviewer belong to different vendors inside
  the closed class {anthropic, openai} — the strongest honest level;
- ``same-vendor-different-model``: honest flagged fallback, selectable only
  after the cross-vendor route returned a typed unavailability;
- ``HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW``: an audited human decision to
  proceed with no independent review at all — never a review outcome.

The module is standalone (stdlib only). The producer keeps its own
PROVIDER_FAMILIES copy until the batched producer slice switches it to this
module; the policy regression suite pins both maps equal so they cannot
drift apart.
"""
from __future__ import annotations

import re
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Provider aliases -> vendor family. Pinned equal to PROVIDER_FAMILIES in
# itd_free_reviewer_producer.py by the policy regression suite.
PROVIDER_FAMILIES = {
    "anthropic": "anthropic",
    "anthropic-subscription": "anthropic",
    "claude": "anthropic",
    "codex": "openai",
    "openai": "openai",
    "openai-codex": "openai",
    "openai-subscription": "openai",
    "gemini": "google",
    "gemini-user": "google",
    "google": "google",
    "antigravity": "google",
    "antigravity-user": "google",
    "github-copilot": "github-copilot",
    "github-copilot-user": "github-copilot",
}

# Closed maker/reviewer independence class. A vendor outside this mapping can
# never anchor an independent pair: typed UNAVAILABLE, fail closed.
INDEPENDENCE_VENDOR_CLASS = {
    "anthropic": ("openai",),
    "openai": ("anthropic",),
}

CROSS_VENDOR = "cross-vendor"
SAME_VENDOR_DIFFERENT_MODEL = "same-vendor-different-model"
INDEPENDENCE_LEVELS = (CROSS_VENDOR, SAME_VENDOR_DIFFERENT_MODEL)
HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW = "HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW"
REVIEW_OUTCOMES = ("PASSED", "ADJUDICATED")

_IDENTITY_KEYS = {"provider", "model", "session"}
_UNAVAILABILITY_KEYS = {"status", "route", "detail"}
_OVERRIDE_KEYS = {
    "outcome", "candidateDigest", "confirmedBy", "reason",
    "crossVendorUnavailability", "fallbackUnavailability",
}


class IndependenceError(Exception):
    """Typed policy failure: status is UNAVAILABLE or UNVERIFIED."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise IndependenceError(
            "UNVERIFIED", f"{label} must be a non-empty trimmed string"
        )
    return value


def _closed_dict(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise IndependenceError(
            "UNVERIFIED",
            f"{label} must be a closed object with keys {sorted(keys)}",
        )
    return value


def _identity(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not (
        set(value) == _IDENTITY_KEYS
        or set(value) == _IDENTITY_KEYS | {"transportExecutableSha256"}
    ):
        raise IndependenceError(
            "UNVERIFIED",
            f"{label} must be a closed identity object with keys "
            f"{sorted(_IDENTITY_KEYS)} (optional transportExecutableSha256)",
        )
    for key in sorted(_IDENTITY_KEYS):
        _text(value[key], f"{label} {key}")
    if "transportExecutableSha256" in value and not (
        isinstance(value["transportExecutableSha256"], str)
        and SHA256_RE.fullmatch(value["transportExecutableSha256"])
    ):
        raise IndependenceError(
            "UNVERIFIED",
            f"{label} transportExecutableSha256 must be 64 lowercase hex",
        )
    return {key: value[key] for key in sorted(_IDENTITY_KEYS)}


def provider_family(provider: Any) -> str:
    family = PROVIDER_FAMILIES.get(_text(provider, "provider").casefold())
    if family is None:
        raise IndependenceError(
            "UNAVAILABLE", "provider is outside the known provider families"
        )
    return family


def independent_reviewer_vendors(maker: Any) -> tuple[str, ...]:
    """Cross-vendor reviewer vendors for a supported maker, fail closed."""
    ident = _identity(maker, "maker identity")
    family = provider_family(ident["provider"])
    vendors = INDEPENDENCE_VENDOR_CLASS.get(family)
    if vendors is None:
        raise IndependenceError(
            "UNAVAILABLE",
            "maker vendor is outside the closed independence class",
        )
    return vendors


def classify_independence(maker: Any, reviewer: Any) -> str:
    """Honest independence level of an observed maker/reviewer pair."""
    maker_ident = _identity(maker, "maker identity")
    reviewer_ident = _identity(reviewer, "reviewer identity")
    if maker_ident["session"] == reviewer_ident["session"]:
        raise IndependenceError(
            "UNVERIFIED",
            "reviewer session must be distinct from the maker session",
        )
    maker_family = provider_family(maker_ident["provider"])
    if maker_family not in INDEPENDENCE_VENDOR_CLASS:
        raise IndependenceError(
            "UNAVAILABLE",
            "maker vendor is outside the closed independence class",
        )
    reviewer_family = provider_family(reviewer_ident["provider"])
    if reviewer_family in INDEPENDENCE_VENDOR_CLASS[maker_family]:
        return CROSS_VENDOR
    if reviewer_family == maker_family:
        if reviewer_ident["model"].casefold() == maker_ident["model"].casefold():
            raise IndependenceError(
                "UNVERIFIED",
                "reviewer model must be distinct from the maker model",
            )
        return SAME_VENDOR_DIFFERENT_MODEL
    raise IndependenceError(
        "UNVERIFIED",
        "reviewer vendor is outside the closed independence class",
    )


def authorize_same_vendor_fallback(
    maker: Any, reviewer: Any, cross_vendor_unavailability: Any,
) -> dict[str, Any]:
    """Authorize the flagged fallback; never silent, never label-laundered."""
    level = classify_independence(maker, reviewer)
    if level != SAME_VENDOR_DIFFERENT_MODEL:
        raise IndependenceError(
            "UNVERIFIED",
            "fallback authorization applies only to a same-vendor "
            "different-model pair",
        )
    evidence = _closed_dict(
        cross_vendor_unavailability, _UNAVAILABILITY_KEYS,
        "cross-vendor unavailability",
    )
    if evidence["status"] != "UNAVAILABLE" or evidence["route"] != CROSS_VENDOR:
        raise IndependenceError(
            "UNVERIFIED",
            "same-vendor fallback requires typed cross-vendor unavailability",
        )
    _text(evidence["detail"], "cross-vendor unavailability detail")
    return {
        "independenceLevel": SAME_VENDOR_DIFFERENT_MODEL,
        "crossVendorUnavailability": dict(evidence),
    }


def validate_human_override(record: Any, candidate_digest: Any) -> dict[str, Any]:
    """HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW: audited, bound, never a review."""
    digest = _text(candidate_digest, "candidate digest")
    if not SHA256_RE.fullmatch(digest):
        raise IndependenceError(
            "UNVERIFIED", "candidate digest must be 64 lowercase hex characters"
        )
    row = _closed_dict(record, _OVERRIDE_KEYS, "human override record")
    if row["outcome"] != HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW:
        raise IndependenceError(
            "UNVERIFIED", "override outcome literal is wrong"
        )
    if row["candidateDigest"] != digest:
        raise IndependenceError(
            "UNVERIFIED", "override is not bound to the exact candidate"
        )
    _text(row["confirmedBy"], "override confirmedBy")
    _text(row["reason"], "override reason")
    expected_routes = {
        "crossVendorUnavailability": CROSS_VENDOR,
        "fallbackUnavailability": SAME_VENDOR_DIFFERENT_MODEL,
    }
    for key, route in expected_routes.items():
        evidence = _closed_dict(row[key], _UNAVAILABILITY_KEYS, key)
        if evidence["status"] != "UNAVAILABLE" or evidence["route"] != route:
            raise IndependenceError(
                "UNVERIFIED",
                f"{key} must be typed UNAVAILABLE for the {route} route",
            )
        _text(evidence["detail"], f"{key} detail")
    return dict(row)


def independent_review_satisfied(outcome: Any) -> bool:
    """True only for a real independent review; the override never counts."""
    value = _text(outcome, "review outcome")
    if value in REVIEW_OUTCOMES:
        return True
    if value == HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW:
        return False
    raise IndependenceError(
        "UNVERIFIED", "review outcome is outside the closed outcome set"
    )


def count_independent_reviewers(identities: Any) -> int:
    """Count distinct reviewer identities by (provider, model, session)."""
    if not isinstance(identities, list):
        raise IndependenceError(
            "UNVERIFIED", "reviewer identities must be a list"
        )
    seen = set()
    for index, value in enumerate(identities):
        ident = _identity(value, f"reviewer identity {index + 1}")
        seen.add((
            ident["provider"].casefold(),
            ident["model"].casefold(),
            ident["session"],
        ))
    return len(seen)


def require_reviewer_quorum(identities: Any, minimum: Any) -> int:
    """Fail closed when distinct reviewer identities miss the contract."""
    if type(minimum) is not int or not 0 <= minimum <= 3:
        raise IndependenceError(
            "UNVERIFIED", "reviewer quorum must be an integer between 0 and 3"
        )
    count = count_independent_reviewers(identities)
    if count < minimum:
        raise IndependenceError(
            "UNVERIFIED",
            "fewer distinct independent reviewers than the contract requires",
        )
    return count
