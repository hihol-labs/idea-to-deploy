#!/usr/bin/env python3
"""Trust-primitive tests that do not import review orchestration."""
from __future__ import annotations

import base64
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "skills" / "_shared" / "itd_review_broker_primitives.py"
spec = importlib.util.spec_from_file_location("itd_broker_primitives_test", MODULE)
assert spec and spec.loader
primitive = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = primitive
spec.loader.exec_module(primitive)
CHECKS = 0


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def rejects(status: str, fn, label: str) -> None:
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except primitive.BrokerError as exc:
        if exc.status != status:
            raise AssertionError(f"{label}: {exc.status} != {status}") from exc
    else:
        raise AssertionError(f"{label}: mutation passed")


HEAD = "a" * 40
BASE = "b" * 40
REPO = "hihol-labs/example"
APP_ID = 424242
CLIENT_ID = "Iv1a2b3c4d5e6f7g8"
INSTALLATION = 73
CHECK_AUTH = "installation-token-fixture"
PROVENANCE_PRIVATE_KEY = primitive.Ed25519PrivateKey.generate()
PROVENANCE_PUBLIC_KEY = PROVENANCE_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)


def payload(event: str = "pull_request") -> dict[str, Any]:
    common: dict[str, Any] = {
        "action": "synchronize" if event == "pull_request" else "checks_requested",
        "installation": {"id": INSTALLATION},
        "repository": {"full_name": REPO},
    }
    if event == "pull_request":
        common.update(
            {
                "number": 9,
                "pull_request": {
                    "head": {"sha": HEAD, "repo": {"full_name": REPO}},
                    "base": {"sha": BASE, "repo": {"full_name": REPO}},
                },
            }
        )
    else:
        common["merge_group"] = {"head_sha": HEAD, "base_sha": BASE}
    return common


def provenance(
    key_id: str = "current",
    *,
    pull_request: int = 9,
    head_sha: str = HEAD,
    base_sha: str = BASE,
    vendor: str = "openai",
    model: str = "gpt-5.6-sol",
    nonce: str = "n" * 24,
) -> dict[str, Any]:
    unsigned = {
        "repository": REPO,
        "pullRequest": pull_request,
        "headSha": head_sha,
        "baseSha": base_sha,
        "makerVendor": vendor,
        "makerModel": model,
        "makerSession": f"maker-session-{pull_request}",
        "issuedAt": primitive.now_iso(),
        "nonce": nonce,
        "keyId": key_id,
    }
    return primitive.sign_provenance(unsigned, PROVENANCE_PRIVATE_KEY)


def provenance_key_record(
    key_id: str = "current",
    vendor: str = "openai",
    model: str = "gpt-5.6-sol",
) -> dict[str, Any]:
    return {
        "repository": REPO,
        "keyId": key_id,
        "authorizedMakerVendor": vendor,
        "authorizedMakerModel": model,
        "publicKey": primitive.b64url(PROVENANCE_PUBLIC_KEY),
        "issuerPrincipal": "windows-user-dmitry",
        "status": "active",
    }


def enrollment_receipt(
    app_id: int = APP_ID,
    *,
    ruleset_id: int = 101,
) -> dict[str, Any]:
    return {
        "repository": REPO,
        "rulesetId": ruleset_id,
        "rulesetEnforcement": "active",
        "rulesetTarget": "branch",
        "defaultBranchRef": "refs/heads/main",
        "protectedRefPatterns": {
            "~DEFAULT_BRANCH": True,
            "refs/heads/release/*": True,
        },
        "excludedRefPatterns": {},
        "requiredPullRequest": True,
        "requireUpToDate": True,
        "requiredStatusChecks": {
            "externalReview": {
                "name": "ITD external review gate",
                "expectedPublisher": "github-app-integration-id",
                "integrationId": app_id,
            },
            "machineOracle": {
                "name": "ITD machine oracle",
                "expectedPublisher": "github-actions",
                "integrationId": 15368,
                "authority": "organization-ruleset-workflow",
                "workflowRepository": "hihol-labs/idea-to-deploy",
                "workflowRepositoryId": 515151,
                "workflowPath": ".github/workflows/itd-machine-oracle.yml",
                "workflowSha": "1" * 40,
            },
        },
        "githubAppClientId": CLIENT_ID,
        "githubAppSlug": "itd-review-gate",
        "githubAppOwner": "hihol-labs",
        "githubAppNodeId": "MDM6QXBwMTIzNDU2",
        "blockDeletion": True,
        "blockForcePush": True,
        "mergeGroupEventsRequired": True,
        "bypassActors": [],
        "policyId": "itd-central-review-broker-v1",
        "observedAt": primitive.now_iso(),
    }


class TokenApi:
    def __init__(
        self,
        live_installation_id: int = INSTALLATION,
        live_app_id: int = APP_ID,
    ) -> None:
        self.data: dict[str, Any] | None = None
        self.live_installation_id = live_installation_id
        self.live_app_id = live_app_id

    def request_json(
        self, method: str, path: str, token: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        check(token.count(".") == 2, "App JWT supplied")
        if method == "GET":
            check(
                path == f"/repos/{REPO}/installation",
                "live repository installation lookup",
            )
            check(data is None, "live installation lookup has no body")
            return {
                "id": self.live_installation_id,
                "app_id": self.live_app_id,
            }
        check(method == "POST", "installation token uses POST")
        check(
            path == f"/app/installations/{INSTALLATION}/access_tokens",
            "exact installation",
        )
        self.data = data
        return {"token": "installation-token-fixture"}


class CheckObservationApi(primitive.GitHubApi):
    def __init__(self, publication: dict[str, Any] | None) -> None:
        self.publication = copy.deepcopy(publication)
        self.last_path: str | None = None

    def request_json(
        self, method: str, path: str, token: str,
        data: dict[str, Any] | None = None,
        limit: int = primitive.MAX_JSON_BYTES,
    ) -> dict[str, Any]:
        del limit
        self.last_path = path
        if method != "GET" or token != "installation-token-fixture" or data is not None:
            raise primitive.BrokerError(
                "UNVERIFIED", "check observation request is not exact"
            )
        if self.publication is None:
            return {}
        return {
            "id": self.publication["id"],
            "app": {"id": self.publication["appIntegrationId"]},
            "name": self.publication["name"],
            "head_sha": self.publication["headSha"],
            "external_id": self.publication["externalId"],
            "status": self.publication["status"],
            "conclusion": self.publication["conclusion"],
        }


class StaticResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers: dict[str, str] = {}

    def __enter__(self) -> "StaticResponse":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]

    def geturl(self) -> str:
        return "https://api.github.com/test"


def main() -> int:
    rfc_sample = {
        "numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27],
        "string": "€$\x0f\nA'B\"\\\\\"/",
        "literals": [None, True, False],
    }
    rfc_sample_bytes = bytes.fromhex(
        "7b226c69746572616c73223a5b6e756c6c2c747275652c66616c73655d2c"
        "226e756d62657273223a5b3333333333333333332e333333333333332c31"
        "652b33302c342e352c302e3030322c31652d32375d2c22737472696e6722"
        "3a22e282ac245c75303030665c6e4127425c225c5c5c5c5c222f227d"
    )
    check(
        primitive.canonical_json(rfc_sample) == rfc_sample_bytes,
        "RFC 8785 canonical example",
    )

    sorting_vector = {
        "€": "Euro Sign",
        "\r": "Carriage Return",
        "דּ": "Hebrew Letter Dalet With Dagesh",
        "1": "One",
        "😀": "Emoji: Grinning Face",
        "\u0080": "Control",
        "ö": "Latin Small Letter O With Diaeresis",
    }
    ordered_pairs = json.loads(
        primitive.canonical_json(sorting_vector),
        object_pairs_hook=lambda pairs: pairs,
    )
    check(
        [item for _, item in ordered_pairs]
        == [
            "Carriage Return",
            "One",
            "Control",
            "Latin Small Letter O With Diaeresis",
            "Euro Sign",
            "Emoji: Grinning Face",
            "Hebrew Letter Dalet With Dagesh",
        ],
        "RFC 8785 UTF-16 property ordering",
    )

    number_vectors = [
        ("0000000000000000", b"0"),
        ("8000000000000000", b"0"),
        ("0000000000000001", b"5e-324"),
        ("8000000000000001", b"-5e-324"),
        ("7fefffffffffffff", b"1.7976931348623157e+308"),
        ("ffefffffffffffff", b"-1.7976931348623157e+308"),
        ("4340000000000000", b"9007199254740992"),
        ("c340000000000000", b"-9007199254740992"),
        ("4430000000000000", b"295147905179352830000"),
        ("44b52d02c7e14af5", b"9.999999999999997e+22"),
        ("44b52d02c7e14af6", b"1e+23"),
        ("44b52d02c7e14af7", b"1.0000000000000001e+23"),
        ("444b1ae4d6e2ef4e", b"999999999999999700000"),
        ("444b1ae4d6e2ef4f", b"999999999999999900000"),
        ("444b1ae4d6e2ef50", b"1e+21"),
        ("3eb0c6f7a0b5ed8c", b"9.999999999999997e-7"),
        ("3eb0c6f7a0b5ed8d", b"0.000001"),
        ("41b3de4355555553", b"333333333.3333332"),
        ("41b3de4355555554", b"333333333.33333325"),
        ("41b3de4355555555", b"333333333.3333333"),
        ("41b3de4355555556", b"333333333.3333334"),
        ("41b3de4355555557", b"333333333.33333343"),
        ("becbf647612f3696", b"-0.0000033333333333333333"),
        ("43143ff3c1cb0959", b"1424953923781206.2"),
    ]
    for bits, expected in number_vectors:
        value = struct.unpack(">d", bytes.fromhex(bits))[0]
        check(
            primitive.canonical_json(value) == expected,
            f"RFC 8785 number vector {bits}",
        )
    for nonfinite in (float("nan"), float("inf"), float("-inf")):
        rejects(
            "UNVERIFIED",
            lambda value=nonfinite: primitive.canonical_json(value),
            "non-finite JCS number",
        )
    rejects(
        "UNVERIFIED",
        lambda: primitive.canonical_json(2**53),
        "unsafe Python integer",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.canonical_json({1: "not a string key"}),
        "non-string JCS key",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.canonical_json({"bad": "\ud800"}),
        "lone surrogate JCS value",
    )
    check(
        primitive.canonical_json({"é": 1})
        != primitive.canonical_json({"e\u0301": 1}),
        "JCS preserves Unicode without normalization",
    )
    with tempfile.TemporaryDirectory(prefix="itd-jcs-") as directory:
        duplicate_path = Path(directory) / "duplicate.json"
        duplicate_path.write_text('{"same":1,"same":2}', encoding="utf-8")
        rejects(
            "UNVERIFIED",
            lambda: primitive.read_json(duplicate_path),
            "duplicate JSON names",
        )
        nonfinite_path = Path(directory) / "nonfinite.json"
        nonfinite_path.write_text('{"value":NaN}', encoding="utf-8")
        rejects(
            "UNVERIFIED",
            lambda: primitive.read_json(nonfinite_path),
            "non-finite parsed JSON number",
        )

    policy = primitive.load_policy()
    check(policy["id"] == "itd-central-review-broker-v1", "frozen policy")
    check(
        primitive.classify_maker("openai", "gpt-5.6-sol", policy)
        == "solMaker"
        and primitive.select_reviewer(
            "solMaker", "openai", "gpt-5.6-sol", policy
        ) == "openai-responses-terra",
        "Sol maker routes to Terra",
    )
    check(
        primitive.classify_maker("openai", "gpt-5.6-terra", policy)
        == "terraMaker"
        and primitive.select_reviewer(
            "terraMaker", "openai", "gpt-5.6-terra", policy
        ) == "openai-responses",
        "Terra maker routes to Sol",
    )
    check(
        primitive.classify_maker("anthropic", "claude-opus-4", policy)
        == "claudeMaker",
        "Claude maker classification is provenance-derived",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.select_reviewer(
            "unknownMaker", "unknown", "unknown", policy
        ),
        "unknown maker cannot enter the automatic provider route",
    )
    changed = copy.deepcopy(policy)
    changed["candidate"]["executeCandidateCode"] = True
    rejects("UNVERIFIED", lambda: primitive.validate_policy(changed), "candidate execution")

    fixture_material = b"It's a Secret to Everybody"
    signature = (
        "sha256="
        "757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"
    )
    primitive.verify_webhook_signature(
        b"Hello, World!", signature, fixture_material, policy
    )
    check(True, "official GitHub HMAC vector")
    check(
        primitive.read_bounded_body(
            __import__("io").BytesIO(b"bounded"), 7
        ) == b"bounded",
        "webhook body is read through the bounded stream primitive",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.read_bounded_body(
            __import__("io").BytesIO(b"oversized"), 8
        ),
        "streaming webhook limit rejects before unbounded buffering",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.verify_webhook_signature(
            b"Hello, World!.", signature, fixture_material, policy
        ),
        "tampered webhook",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.verify_webhook_signature(
            b"x"
            * (policy["github"]["webhooks"]["maxBodyBytes"] + 1),
            signature,
            fixture_material,
            policy,
        ),
        "webhook policy body bound",
    )

    pull = primitive.normalize_webhook(
        "pull_request", "synchronize", payload(), policy
    )
    check(pull.pull_request == 9 and pull.subject_type == "pull_request", "PR coordinates")
    mismatched_event = payload()
    rejects(
        "UNVERIFIED",
        lambda: primitive.normalize_webhook(
            "merge_group", "synchronize", mismatched_event, policy
        ),
        "signed payload shape must match the event header",
    )
    mismatched_action = payload()
    mismatched_action["action"] = "opened"
    rejects(
        "UNVERIFIED",
        lambda: primitive.normalize_webhook(
            "pull_request", "synchronize", mismatched_action, policy
        ),
        "action argument must match the signed payload",
    )
    fork_pull = payload()
    fork_pull["pull_request"]["head"]["repo"]["full_name"] = "contributor/example"
    rejects(
        "UNVERIFIED",
        lambda: primitive.normalize_webhook(
            "pull_request", "synchronize", fork_pull, policy
        ),
        "fork pull request",
    )
    wrong_base = payload()
    wrong_base["pull_request"]["base"]["repo"]["full_name"] = "other/example"
    rejects(
        "UNVERIFIED",
        lambda: primitive.normalize_webhook(
            "pull_request", "synchronize", wrong_base, policy
        ),
        "base repository mismatch",
    )
    group = primitive.normalize_webhook(
        "merge_group", "checks_requested", payload("merge_group"), policy
    )
    check(group.pull_request == 0 and group.subject_type == "merge_group", "group coordinates")
    check(
        primitive.normalize_webhook("push", "created", {}, policy) is None,
        "unsubscribed webhook ignored",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.Coordinates(
            "owner/.", 9, HEAD, BASE, INSTALLATION
        ).validate(),
        "dot-only repository names are rejected",
    )

    signed = provenance()
    verified = primitive.verify_provenance(
        signed, {"current": provenance_key_record()}, policy
    )
    check(verified["keyId"] == "current", "rotatable provenance key selected")
    rejects(
        "UNVERIFIED",
        lambda: primitive.verify_provenance(
            signed, {"previous": provenance_key_record("previous")}, policy
        ),
        "unknown provenance key id",
    )
    forged = dict(signed)
    forged["makerModel"] = "gpt-5.6-terra"
    rejects(
        "UNVERIFIED",
        lambda: primitive.verify_provenance(
            forged, {"current": provenance_key_record()}, policy
        ),
        "forged maker",
    )
    uppercase_sha = provenance()
    uppercase_sha["headSha"] = HEAD.upper()
    rejects(
        "UNVERIFIED",
        lambda: primitive.sign_provenance(
            {
                key: value
                for key, value in uppercase_sha.items()
                if key != "signature"
            },
            PROVENANCE_PRIVATE_KEY,
        ),
        "noncanonical provenance SHA",
    )
    stale = provenance()
    stale["issuedAt"] = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stale = primitive.sign_provenance(
        {key: value for key, value in stale.items() if key != "signature"},
        PROVENANCE_PRIVATE_KEY,
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.verify_provenance(
            stale, {"current": provenance_key_record()}, policy
        ),
        "stale provenance",
    )
    wrong_authorization = provenance_key_record(model="gpt-5.6-terra")
    rejects(
        "UNVERIFIED",
        lambda: primitive.verify_provenance(
            signed, {"current": wrong_authorization}, policy
        ),
        "maker identity must equal key registry authorization",
    )

    sol_keyring = {"current": provenance_key_record()}
    store = primitive.BrokerStore(
        ":memory:", provenance_keyring=sol_keyring
    )
    active_receipt_sha = store.enroll(enrollment_receipt())
    store.require_enrolled(REPO, APP_ID)
    enrollment = store.enrollment_status(REPO, APP_ID)
    check(
        enrollment["repository"] == REPO
        and enrollment["appId"] == APP_ID
        and enrollment["receiptSha256"] == active_receipt_sha,
        "doctor-visible enrollment is bound to the active receipt",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.require_enrolled(REPO, APP_ID + 1),
        "wrong App enrollment",
    )
    rotation_store = primitive.BrokerStore(":memory:")
    first_enrollment = enrollment_receipt()
    first_receipt_sha = rotation_store.enroll(first_enrollment)
    check(
        rotation_store.enroll(copy.deepcopy(first_enrollment))
        == first_receipt_sha,
        "exact active enrollment is idempotent",
    )
    rejects(
        "UNVERIFIED",
        lambda: rotation_store.enroll(
            enrollment_receipt(APP_ID + 1, ruleset_id=202)
        ),
        "active enrollment cannot be rebound to another App",
    )
    rejects(
        "UNVERIFIED",
        lambda: rotation_store.enroll(enrollment_receipt(ruleset_id=202)),
        "active enrollment receipt is immutable even for the same App",
    )
    rejects(
        "UNVERIFIED",
        lambda: rotation_store.disable_enrollment(
            REPO, "f" * 64, "planned App rotation"
        ),
        "disable must bind the exact active enrollment receipt",
    )
    rotation_store.disable_enrollment(
        REPO, first_receipt_sha, "planned App rotation"
    )
    rejects(
        "UNVERIFIED",
        lambda: rotation_store.require_enrolled(REPO, APP_ID),
        "disabled enrollment cannot authorize review publication",
    )
    rejects(
        "UNVERIFIED",
        lambda: rotation_store.enroll(copy.deepcopy(first_enrollment)),
        "disabled enrollment cannot be re-enabled from its stale receipt",
    )
    second_receipt_sha = rotation_store.enroll(
        enrollment_receipt(APP_ID + 1, ruleset_id=202)
    )
    rotation_store.require_enrolled(REPO, APP_ID + 1)
    check(
        second_receipt_sha != first_receipt_sha
        and rotation_store.db.execute(
            "SELECT COUNT(*) FROM enrollment_receipts WHERE repository=?",
            (REPO,),
        ).fetchone()[0]
        == 2
        and rotation_store.db.execute(
            "SELECT COUNT(*) FROM enrollment_events WHERE repository=?",
            (REPO,),
        ).fetchone()[0]
        == 3,
        "rotation retains both immutable receipts and every state transition",
    )
    check(
        store.record_delivery_candidate(
            "delivery-0001",
            "pull_request",
            "synchronize",
            "c" * 64,
            pull,
        ),
        "delivery and job accepted atomically",
    )
    check(
        not store.record_delivery_candidate(
            "delivery-0002",
            "pull_request",
            "synchronize",
            "c" * 64,
            pull,
        ),
        "same authenticated body under another delivery is acknowledged only",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.record_delivery_candidate(
            "delivery-0001",
            "pull_request",
            "synchronize",
            "d" * 64,
            pull,
        ),
        "same delivery id with a different body is rejected",
    )
    check(
        store.claim() is None,
        "candidate waits for maker provenance",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.put_provenance_and_queue(forged, pull),
        "forged maker is rejected at the queue trust boundary",
    )
    bad_signature = dict(signed)
    bad_signature_bytes = bytearray(
        primitive.b64url_decode(
            bad_signature["signature"], 64, "test signature"
        )
    )
    bad_signature_bytes[0] ^= 1
    bad_signature["signature"] = primitive.b64url(bytes(bad_signature_bytes))
    rejects(
        "UNVERIFIED",
        lambda: store.put_provenance_and_queue(bad_signature, pull),
        "bad signature is rejected at the queue trust boundary",
    )
    unknown_key = provenance(key_id="unknown", nonce="u" * 24)
    rejects(
        "UNVERIFIED",
        lambda: store.put_provenance_and_queue(unknown_key, pull),
        "unknown provenance key is rejected at the queue trust boundary",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.put_provenance_and_queue(stale, pull),
        "stale provenance is rejected at the queue trust boundary",
    )
    unauthorized_store = primitive.BrokerStore(
        ":memory:",
        provenance_keyring={
            "current": provenance_key_record(model="gpt-5.6-terra")
        },
    )
    rejects(
        "UNVERIFIED",
        lambda: unauthorized_store.put_provenance_and_queue(signed, pull),
        "unauthorized maker is rejected at the queue trust boundary",
    )
    unauthorized_store.close()
    check(
        store.put_provenance_and_queue(signed, pull),
        "provenance stored and exact candidate queued atomically",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.put_provenance_and_queue(signed, pull),
        "provenance nonce replay cannot enqueue or route",
    )
    component = store.get_component_provenance([pull])
    check(
        len(component) == 1
        and component[0]["model"] == "gpt-5.6-sol",
        "merge-group component provenance aggregates exact PR coordinates",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.get_component_provenance([group]),
        "synthetic merge coordinate cannot replace PR provenance",
    )
    claimed = store.claim()
    check(claimed is not None and claimed[1] == pull, "exact job claimed")
    review_diff_sha = "f" * 64
    redaction_manifest = {
        "version": 1,
        "sanitizerVersion": "itd-scrubber-v1",
        "status": "clean",
        "reviewDiffSha256": review_diff_sha,
        "redactions": [],
    }
    candidate_manifest = {
        "version": 1,
        "repository": REPO,
        "subjectType": "pull_request",
        "pullRequest": 9,
        "headSha": HEAD,
        "baseSha": BASE,
        "checkSha": "d" * 40,
        "provenanceReceiptSha256": component[0]["payloadSha256"],
        "source": "github-api-complete-file-list-plus-full-blobs",
        "files": {
            "src/new.py": {
                "previousPath": None,
                "baseBlobSha": None,
                "headBlobSha": HEAD,
                "baseBytes": 0,
                "headBytes": 12,
                "status": "added",
            }
        },
        "pagination": {"pageCount": 1, "complete": True},
        "totalDecodedBlobBytes": 12,
        "reviewDiffSha256": review_diff_sha,
        "reviewDiffBytes": 120,
        "sanitizerVersion": "itd-scrubber-v1",
        "redactionManifestSha256": primitive.sha256_bytes(
            primitive.canonical_json(redaction_manifest)
        ),
    }
    candidate_sha = primitive.sha256_bytes(
        primitive.canonical_json(candidate_manifest)
    )
    verdict = {"verdict": "PASSED", "findings": [], "unverified": []}
    verdict_sha = primitive.sha256_bytes(primitive.canonical_json(verdict))
    usage = {"inputTokens": 100, "outputTokens": 10}
    settlement_reservation = store.reserve(
        "openai-responses-terra", candidate_sha
    )
    settlement = store.settle(settlement_reservation, usage)
    check(settlement is not None, "immutable primary-usage settlement created")
    external_id_payload = {
        "repository": REPO,
        "subjectType": "pull_request",
        "pullRequest": 9,
        "headSha": HEAD,
        "baseSha": BASE,
        "checkSha": "d" * 40,
        "provenanceReceiptSha256": component[0]["payloadSha256"],
        "candidateManifestSha256": candidate_sha,
        "verdictSha256": verdict_sha,
    }
    external_id_sha = primitive.sha256_bytes(
        primitive.canonical_json(external_id_payload)
    )
    prompt = "sanitized prompt"
    exact_receipt = {
        "repository": REPO,
        "subjectType": "pull_request",
        "pullRequest": 9,
        "headSha": HEAD,
        "baseSha": BASE,
        "installationId": INSTALLATION,
        "checkSha": "d" * 40,
        "provenanceReceiptSha256": component[0]["payloadSha256"],
        "checkPublication": {
            "id": 101,
            "appIntegrationId": APP_ID,
            "name": "ITD external review gate",
            "headSha": "d" * 40,
            "externalId": external_id_sha,
            "status": "completed",
            "conclusion": "success",
        },
        "makerClass": "solMaker",
        "checkerReviewerId": "openai-responses-terra",
        "policySha256": primitive.sha256_bytes(primitive.POLICY_PATH.read_bytes()),
        "candidateManifestSha256": candidate_sha,
        "budgetSettlementSha256": primitive.sha256_bytes(
            primitive.canonical_json(settlement)
        ),
        "externalIdPayloadSha256": external_id_sha,
        "reviewDiffSha256": review_diff_sha,
        "reviewDiffBytes": 120,
        "sanitizerVersion": "itd-scrubber-v1",
        "redactionManifest": redaction_manifest,
        "providerRequestSha256": primitive.sha256_bytes(prompt.encode()),
        "providerRequestBytes": len(prompt.encode()),
        "fileCount": 1,
        "paginationComplete": True,
        "verdictSha256": verdict_sha,
        "usage": usage,
        "status": "PASSED",
        "observedAt": primitive.now_iso(),
    }
    record_args = {
        "provider_request": prompt.encode("utf-8"),
        "candidate_manifest": candidate_manifest,
        "verdict": verdict,
        "budget_settlement": settlement,
        "external_id_payload": external_id_payload,
    }
    exact_observer = CheckObservationApi(exact_receipt["checkPublication"])
    preparing_publication = copy.deepcopy(exact_receipt["checkPublication"])
    preparing_publication["status"] = "in_progress"
    preparing_publication["conclusion"] = None
    preparation_id = store.prepare_review(
        exact_receipt,
        prompt,
        CheckObservationApi(preparing_publication),
        CHECK_AUTH,
        **record_args,
    )
    check(
        len(preparation_id) == 32,
        "exact review evidence is durable before publication",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.record_review(
            exact_receipt,
            prompt,
            CheckObservationApi(None),
            CHECK_AUTH,
            **record_args,
        ),
        "missing observed GitHub check cannot be persisted",
    )
    mismatched_observation = copy.deepcopy(exact_receipt["checkPublication"])
    mismatched_observation["conclusion"] = "action_required"
    rejects(
        "UNVERIFIED",
        lambda: store.record_review(
            exact_receipt,
            prompt,
            CheckObservationApi(mismatched_observation),
            CHECK_AUTH,
            **record_args,
        ),
        "self-attested publication cannot replace observed GitHub state",
    )
    receipt_id = store.record_review(
        exact_receipt, prompt, exact_observer, CHECK_AUTH, **record_args
    )
    check(len(receipt_id) == 32, "exact running candidate receipt recorded")
    check(
        exact_observer.last_path == f"/repos/{REPO}/check-runs/101",
        "post-publication observation reads the exact GitHub check-run id",
    )
    check(
        store.record_review(
            exact_receipt, prompt, exact_observer, CHECK_AUTH, **record_args
        )
        == receipt_id,
        "repeated final observation is idempotent",
    )
    forged_receipt = dict(exact_receipt)
    forged_receipt["headSha"] = "c" * 40
    rejects(
        "UNVERIFIED",
        lambda: store.record_review(
            forged_receipt, prompt, exact_observer, CHECK_AUTH, **record_args
        ),
        "arbitrary review coordinates rejected",
    )
    unbound_clean_receipt = copy.deepcopy(exact_receipt)
    unbound_clean_receipt["redactionManifest"]["reviewDiffSha256"] = "a" * 64
    rejects(
        "UNVERIFIED",
        lambda: store.record_review(
            unbound_clean_receipt,
            prompt,
            exact_observer,
            CHECK_AUTH,
            **record_args,
        ),
        "clean redaction evidence must bind the exact review diff",
    )
    wrong_publisher = copy.deepcopy(exact_receipt)
    wrong_publisher["checkPublication"]["appIntegrationId"] = APP_ID + 1
    rejects(
        "UNVERIFIED",
        lambda: store.record_review(
            wrong_publisher, prompt, exact_observer, CHECK_AUTH, **record_args
        ),
        "published check must belong to the enrolled App integration",
    )
    wrong_external_id = copy.deepcopy(exact_receipt)
    wrong_external_id["checkPublication"]["externalId"] = "a" * 64
    rejects(
        "UNVERIFIED",
        lambda: store.record_review(
            wrong_external_id, prompt, exact_observer, CHECK_AUTH, **record_args
        ),
        "published check must expose the bound external id",
    )
    store.finish_job(claimed[0], True, {"status": "PASSED"})
    check(
        store.claim() is None,
        "one exact candidate produces one review job",
    )
    check(
        not store.record_delivery_candidate(
            "delivery-0003",
            "pull_request",
            "synchronize",
            "d" * 64,
            pull,
        ),
        "distinct body cannot enqueue an already reviewed exact candidate",
    )
    check(store.claim() is None, "distinct delivery cannot requeue candidate")

    merge_store = primitive.BrokerStore(
        ":memory:",
        provenance_keyring={
            "current": provenance_key_record(),
            "terra": provenance_key_record(
                "terra", model="gpt-5.6-terra"
            ),
        },
    )
    merge_store.enroll(enrollment_receipt())
    merge_components: list[primitive.Coordinates] = []
    merge_provenance: list[dict[str, Any]] = []
    for index, (pull_number, head_sha, base_sha, nonce) in enumerate(
        [
            (9, HEAD, BASE, "p" * 24),
            (10, "c" * 40, "d" * 40, "q" * 24),
        ],
        start=1,
    ):
        coordinates = primitive.Coordinates(
            REPO, pull_number, head_sha, base_sha, INSTALLATION
        )
        check(
            merge_store.record_delivery_candidate(
                f"delivery-component-{index:04d}",
                "pull_request",
                "synchronize",
                str(index) * 64,
                coordinates,
            ),
            "merge component webhook candidate stored",
        )
        signed_component = provenance(
            pull_request=pull_number,
            head_sha=head_sha,
            base_sha=base_sha,
            nonce=nonce,
        )
        verified_component = primitive.verify_provenance(
            signed_component,
            {"current": provenance_key_record()},
            policy,
        )
        check(
            merge_store.put_provenance_and_queue(signed_component, coordinates),
            "merge component provenance stored",
        )
        merge_components.append(coordinates)
        merge_provenance.append(
            merge_store.get_provenance(coordinates)
        )
    for _ in merge_components:
        component_job = merge_store.claim()
        check(component_job is not None, "component job claimable")
        merge_store.finish_job(
            component_job[0], True, {"status": "component-ready"}
        )

    merge_coordinates = primitive.Coordinates(
        REPO, 0, "e" * 40, "f" * 40, INSTALLATION
    )
    check(
        merge_store.record_delivery_candidate(
            "delivery-merge-0001",
            "merge_group",
            "checks_requested",
            "3" * 64,
            merge_coordinates,
        ),
        "merge-group webhook candidate stored",
    )
    queued_components = merge_store.queue_merge_group(
        merge_coordinates, merge_components
    )
    check(
        [row["payloadSha256"] for row in queued_components]
        == [row["payloadSha256"] for row in merge_provenance],
        "merge group queues only exact homogeneous component provenance",
    )
    merge_job = merge_store.claim()
    check(
        merge_job is not None and merge_job[1] == merge_coordinates,
        "exact merge-group job claimed",
    )
    merge_manifest = {
        "version": 1,
        "repository": REPO,
        "subjectType": "merge_group",
        "headSha": merge_coordinates.head_sha,
        "baseSha": merge_coordinates.base_sha,
        "source": "github-api-complete-file-list-plus-full-blobs",
        "files": {
            "src/merge.py": {
                "previousPath": None,
                "baseBlobSha": BASE,
                "headBlobSha": HEAD,
                "baseBytes": 12,
                "headBytes": 14,
                "status": "modified",
            }
        },
        "components": {
            str(row.pull_request): {
                "pullRequestHeadSha": row.head_sha,
                "pullRequestBaseSha": row.base_sha,
                "provenanceReceiptSha256":
                    merge_provenance[index]["payloadSha256"],
            }
            for index, row in enumerate(merge_components)
        },
        "pagination": {"pageCount": 1, "complete": True},
        "totalDecodedBlobBytes": 26,
        "reviewDiffSha256": review_diff_sha,
        "reviewDiffBytes": 140,
        "sanitizerVersion": "itd-scrubber-v1",
        "redactionManifestSha256": primitive.sha256_bytes(
            primitive.canonical_json(redaction_manifest)
        ),
    }
    merge_manifest_sha = primitive.sha256_bytes(
        primitive.canonical_json(merge_manifest)
    )
    merge_settlement_id = merge_store.reserve(
        "openai-responses-terra", merge_manifest_sha
    )
    merge_settlement = merge_store.settle(merge_settlement_id, usage)
    check(merge_settlement is not None, "merge-group budget settled")
    merge_external_id = {
        "repository": REPO,
        "subjectType": "merge_group",
        "pullRequests": {"9": True, "10": True},
        "headSha": merge_coordinates.head_sha,
        "baseSha": merge_coordinates.base_sha,
        "candidateManifestSha256": merge_manifest_sha,
        "verdictSha256": verdict_sha,
    }
    merge_external_sha = primitive.sha256_bytes(
        primitive.canonical_json(merge_external_id)
    )
    merge_receipt = {
        "repository": REPO,
        "subjectType": "merge_group",
        "headSha": merge_coordinates.head_sha,
        "baseSha": merge_coordinates.base_sha,
        "installationId": INSTALLATION,
        "checkPublication": {
            "id": 201,
            "appIntegrationId": APP_ID,
            "name": "ITD external review gate",
            "headSha": merge_coordinates.head_sha,
            "externalId": merge_external_sha,
            "status": "completed",
            "conclusion": "success",
        },
        "makerClass": "solMaker",
        "checkerReviewerId": "openai-responses-terra",
        "policySha256": primitive.sha256_bytes(
            primitive.POLICY_PATH.read_bytes()
        ),
        "candidateManifestSha256": merge_manifest_sha,
        "budgetSettlementSha256": primitive.sha256_bytes(
            primitive.canonical_json(merge_settlement)
        ),
        "externalIdPayloadSha256": merge_external_sha,
        "reviewDiffSha256": review_diff_sha,
        "reviewDiffBytes": 140,
        "sanitizerVersion": "itd-scrubber-v1",
        "redactionManifest": redaction_manifest,
        "providerRequestSha256": primitive.sha256_bytes(prompt.encode()),
        "providerRequestBytes": len(prompt.encode()),
        "fileCount": 1,
        "paginationComplete": True,
        "verdictSha256": verdict_sha,
        "usage": usage,
        "status": "PASSED",
        "observedAt": primitive.now_iso(),
    }
    merge_args = {
        "provider_request": prompt.encode("utf-8"),
        "candidate_manifest": merge_manifest,
        "verdict": verdict,
        "budget_settlement": merge_settlement,
        "external_id_payload": merge_external_id,
    }
    merge_observer = CheckObservationApi(merge_receipt["checkPublication"])

    wrong_route_settlement_id = merge_store.reserve(
        "openai-responses", merge_manifest_sha
    )
    wrong_route_settlement = merge_store.settle(
        wrong_route_settlement_id, usage
    )
    wrong_route_receipt = copy.deepcopy(merge_receipt)
    wrong_route_receipt["makerClass"] = "terraMaker"
    wrong_route_receipt["checkerReviewerId"] = "openai-responses"
    wrong_route_receipt["budgetSettlementSha256"] = primitive.sha256_bytes(
        primitive.canonical_json(wrong_route_settlement)
    )
    rejects(
        "UNVERIFIED",
        lambda: merge_store.prepare_review(
            wrong_route_receipt,
            prompt,
            CheckObservationApi(
                {
                    **wrong_route_receipt["checkPublication"],
                    "status": "in_progress",
                    "conclusion": None,
                }
            ),
            CHECK_AUTH,
            provider_request=prompt.encode("utf-8"),
            candidate_manifest=merge_manifest,
            verdict=verdict,
            budget_settlement=wrong_route_settlement,
            external_id_payload=merge_external_id,
        ),
        "merge-group reviewer route is derived from stored component makers",
    )

    forged_merge_manifest = copy.deepcopy(merge_manifest)
    forged_merge_manifest["components"]["9"][
        "provenanceReceiptSha256"
    ] = "a" * 64
    forged_merge_sha = primitive.sha256_bytes(
        primitive.canonical_json(forged_merge_manifest)
    )
    forged_settlement_id = merge_store.reserve(
        "openai-responses-terra", forged_merge_sha
    )
    forged_settlement = merge_store.settle(forged_settlement_id, usage)
    forged_external_id = copy.deepcopy(merge_external_id)
    forged_external_id["candidateManifestSha256"] = forged_merge_sha
    forged_external_sha = primitive.sha256_bytes(
        primitive.canonical_json(forged_external_id)
    )
    forged_merge_receipt = copy.deepcopy(merge_receipt)
    forged_merge_receipt["candidateManifestSha256"] = forged_merge_sha
    forged_merge_receipt["budgetSettlementSha256"] = primitive.sha256_bytes(
        primitive.canonical_json(forged_settlement)
    )
    forged_merge_receipt["externalIdPayloadSha256"] = forged_external_sha
    forged_merge_receipt["checkPublication"][
        "externalId"
    ] = forged_external_sha
    rejects(
        "UNVERIFIED",
        lambda: merge_store.prepare_review(
            forged_merge_receipt,
            prompt,
            CheckObservationApi(
                {
                    **forged_merge_receipt["checkPublication"],
                    "status": "in_progress",
                    "conclusion": None,
                }
            ),
            CHECK_AUTH,
            provider_request=prompt.encode("utf-8"),
            candidate_manifest=forged_merge_manifest,
            verdict=verdict,
            budget_settlement=forged_settlement,
            external_id_payload=forged_external_id,
        ),
        "merge-group receipt cannot substitute component provenance hashes",
    )

    merge_preparing = {
        **merge_receipt["checkPublication"],
        "status": "in_progress",
        "conclusion": None,
    }
    merge_preparation_id = merge_store.prepare_review(
        merge_receipt,
        prompt,
        CheckObservationApi(merge_preparing),
        CHECK_AUTH,
        **merge_args,
    )
    check(len(merge_preparation_id) == 32, "merge-group evidence prepared")
    merge_receipt_id = merge_store.record_review(
        merge_receipt, prompt, merge_observer, CHECK_AUTH, **merge_args
    )
    check(len(merge_receipt_id) == 32, "exact merge-group receipt recorded")
    check(
        merge_store.record_review(
            merge_receipt, prompt, merge_observer, CHECK_AUTH, **merge_args
        )
        == merge_receipt_id,
        "merge-group final observation is idempotent",
    )
    merge_store.finish_job(merge_job[0], True, {"status": "PASSED"})

    terra_coordinates = primitive.Coordinates(
        REPO, 11, "7" * 40, "8" * 40, INSTALLATION
    )
    check(
        merge_store.record_delivery_candidate(
            "delivery-component-terra",
            "pull_request",
            "synchronize",
            "4" * 64,
            terra_coordinates,
        ),
        "mixed-maker component webhook stored",
    )
    signed_terra = provenance(
        key_id="terra",
        pull_request=11,
        head_sha=terra_coordinates.head_sha,
        base_sha=terra_coordinates.base_sha,
        model="gpt-5.6-terra",
        nonce="t" * 24,
    )
    verified_terra = primitive.verify_provenance(
        signed_terra,
        {"terra": provenance_key_record("terra", model="gpt-5.6-terra")},
        policy,
    )
    check(
        merge_store.put_provenance_and_queue(signed_terra, terra_coordinates),
        "mixed-maker component provenance stored",
    )
    mixed_group = primitive.Coordinates(
        REPO, 0, "5" * 40, "6" * 40, INSTALLATION
    )
    check(
        merge_store.record_delivery_candidate(
            "delivery-merge-mixed",
            "merge_group",
            "checks_requested",
            "5" * 64,
            mixed_group,
        ),
        "mixed-maker merge webhook stored",
    )
    rejects(
        "UNVERIFIED",
        lambda: merge_store.queue_merge_group(
            mixed_group, [merge_components[0], terra_coordinates]
        ),
        "mixed merge-group makers cannot enter automatic review routing",
    )
    merge_store.close()

    rejects(
        "UNAVAILABLE",
        lambda: store.reserve("unpriced-reviewer", candidate_sha),
        "missing frozen reviewer pricing",
    )
    rejects(
        "UNVERIFIED",
        lambda: store.reserve("openai-responses-terra", "bad"),
        "invalid candidate digest",
    )
    overspend = store.reserve("openai-responses-terra", candidate_sha)
    rejects(
        "UNVERIFIED",
        lambda: store.settle(
            overspend, {"inputTokens": 0, "outputTokens": 50001}
        ),
        "derived provider overspend fails closed after accounting",
    )
    check(
        store.budget_status()["spentMicrousd"] == 750415,
        "provider overspend remains in ledger",
    )
    finite = store.reserve("openai-responses-terra", candidate_sha)
    rejects(
        "UNVERIFIED",
        lambda: store.settle(
            finite,
            {"inputTokens": 500, "outputTokens": 100, "totalTokens": 600},
        ),
        "caller-supplied total token count is rejected",
    )
    settlement = store.settle(
        finite, {"inputTokens": 500, "outputTokens": 100}
    )
    check(
        settlement is not None
        and settlement["usage"] == {"inputTokens": 500, "outputTokens": 100}
        and "costUsd" not in settlement
        and settlement["reservationMicrousd"] == 750000,
        "settlement stores primary usage and derives cost from frozen pricing",
    )
    reservations = [
        store.reserve("openai-responses-terra", candidate_sha)
        for _ in range(12)
    ]
    rejects(
        "UNAVAILABLE",
        lambda: store.reserve("openai-responses-terra", candidate_sha),
        "monthly atomic microusd cap",
    )
    for reservation in reservations:
        store.settle(
            reservation, {"inputTokens": 0, "outputTokens": 0}
        )
    budget = store.budget_status()
    check(
        budget
        == {
            "period": budget["period"],
            "reservedMicrousd": 0,
            "spentMicrousd": 753165,
        },
        "budget released and overspend retained",
    )

    signer = lambda value: hashlib.sha256(value).digest()
    api = TokenApi()
    auth = primitive.GitHubAppAuth(
        CLIENT_ID,
        Path("/not-used"),
        api=api,
        signer=signer,
        signer_algorithm="RS256",
    )
    jwt_value = auth.jwt(now=1_800_000_000)
    header, claims, _ = jwt_value.split(".")
    header_json = json.loads(base64.urlsafe_b64decode(header + "=="))
    claims_json = json.loads(base64.urlsafe_b64decode(claims + "=="))
    check(header_json == {"alg": "RS256", "typ": "JWT"}, "RS256 JWT")
    check(claims_json["iss"] == CLIENT_ID, "JWT issuer is enrolled client id")
    check(claims_json["exp"] - claims_json["iat"] == 600, "JWT lifetime")
    check(
        auth.installation_token(INSTALLATION, REPO, APP_ID)
        == "installation-token-fixture",
        "repository-scoped installation token",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.GitHubAppAuth(
            CLIENT_ID,
            Path("/not-used"),
            api=TokenApi(live_installation_id=INSTALLATION + 1),
            signer=signer,
            signer_algorithm="RS256",
        ).installation_token(INSTALLATION, REPO, APP_ID),
        "webhook installation id is revalidated against live GitHub state",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.GitHubAppAuth(
            CLIENT_ID,
            Path("/not-used"),
            api=TokenApi(live_app_id=APP_ID + 1),
            signer=signer,
            signer_algorithm="RS256",
        ).installation_token(INSTALLATION, REPO, APP_ID),
        "live repository installation must belong to the enrolled App",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.GitHubAppAuth(
            CLIENT_ID,
            Path("/not-used"),
            signer=signer,
            signer_algorithm="ES256",
        ),
        "non-RS256 injected signer rejected",
    )
    rejects(
        "UNAVAILABLE",
        lambda: primitive.GitHubAppAuth(
            "bad", Path("/not-used"), signer=signer, signer_algorithm="RS256"
        ),
        "malformed GitHub App client id is rejected",
    )
    check(
        api.data == {
            "permissions": {
                "checks": "write",
                "contents": "read",
                "pull_requests": "read",
            },
            "repositories": ["example"],
        },
        "least-privilege installation token",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.RejectRedirectHandler().redirect_request(
            None,
            None,
            307,
            "Temporary Redirect",
            {},
            "https://attacker.example.test/token",
        ),
        "GitHub credential redirect rejected before resend",
    )
    rejects(
        "UNVERIFIED",
        lambda: primitive.GitHubApi(
            "https://api.github.com"
            "@attacker.example.test"
        ),
        "GitHub API userinfo confusion rejected",
    )
    github = primitive.GitHubApi()
    rejects(
        "UNVERIFIED",
        lambda: github.pages("/repos/x/y/pulls/1/files", "token", 0, 100),
        "zero page size rejected before network",
    )
    for body, label in [
        (b'{"id":1,"id":2}', "duplicate GitHub API property"),
        (b'{"value":NaN}', "non-finite GitHub API number"),
        (b'{"value":"\\ud800"}', "invalid GitHub API Unicode"),
        (b'{"value":9007199254740992}', "unsafe GitHub API integer"),
    ]:
        strict_github = primitive.GitHubApi(
            opener=lambda _request, timeout, raw=body: StaticResponse(raw)
        )
        rejects(
            "UNVERIFIED",
            lambda api=strict_github: api.request_json(
                "GET", "/test", "installation-token-fixture"
            ),
            label,
        )
    store.close()
    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
