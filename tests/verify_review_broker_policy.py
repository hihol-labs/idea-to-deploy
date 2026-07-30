#!/usr/bin/env python3
"""Closed policy and runtime-schema checks for the central review broker."""
from __future__ import annotations

import copy
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "skills" / "_shared" / "REVIEW_BROKER_POLICY.json"
SCHEMA = ROOT / "skills" / "_shared" / "REVIEW_BROKER_POLICY.schema.json"
RUNTIME_SCHEMA = (
    ROOT / "skills" / "_shared" / "REVIEW_BROKER_RUNTIME.schema.json"
)
VERDICT_SCHEMA = (
    ROOT / "skills" / "_shared" / "EXTERNAL_REVIEW_VERDICT_SCHEMA.json"
)
CHECKS = 0


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def validate(value: dict[str, Any], schema: dict[str, Any]) -> None:
    required = set(schema["required"])
    if set(value) != required:
        raise ValueError("policy fields are not closed")
    for name in required:
        expected = schema["properties"][name]["const"]
        if value[name] != expected:
            raise ValueError(f"policy field drift: {name}")


def runtime_validator(runtime: dict[str, Any], name: str) -> Draft202012Validator:
    return Draft202012Validator(
        {
            "$schema": runtime["$schema"],
            "$defs": runtime["$defs"],
            "$ref": f"#/$defs/{name}",
        }
    )


def expect_rejected(validator: Draft202012Validator, value: dict[str, Any],
                    label: str) -> None:
    try:
        validator.validate(value)
    except ValidationError:
        check(True, label)
    else:
        raise AssertionError(label)


def main() -> int:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME_SCHEMA.read_text(encoding="utf-8"))
    verdict_schema = json.loads(VERDICT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(runtime)
    Draft202012Validator.check_schema(verdict_schema)
    check(True, "runtime and verdict schemas are valid draft 2020-12 schemas")
    check(schema["additionalProperties"] is False, "top-level schema is closed")
    validate(policy, schema)
    check(True, "canonical policy validates")
    check(
        policy["runtimeSchemas"]
        == {
            "candidateManifest":
                "REVIEW_BROKER_RUNTIME.schema.json#/$defs/candidateManifest",
            "redactionManifest":
                "REVIEW_BROKER_RUNTIME.schema.json#/$defs/redactionManifest",
            "externalIdPayload":
                "REVIEW_BROKER_RUNTIME.schema.json#/$defs/externalIdPayload",
            "provenanceRecord":
                "REVIEW_BROKER_RUNTIME.schema.json#/$defs/provenanceRecord",
            "budgetSettlement":
                "REVIEW_BROKER_RUNTIME.schema.json#/$defs/budgetSettlement",
            "brokerReceipt":
                "REVIEW_BROKER_RUNTIME.schema.json#/$defs/brokerReceipt",
            "enrollmentReceipt":
                "REVIEW_BROKER_RUNTIME.schema.json#/$defs/enrollmentReceipt",
            "reviewerVerdict": "EXTERNAL_REVIEW_VERDICT_SCHEMA.json",
        },
        "policy names every closed runtime evidence schema",
    )
    check(
        policy["github"]["apiVersion"] == "2026-03-10"
        and policy["github"]["apiVersionSupportSource"]
        == "https://docs.github.com/en/rest/about-the-rest-api/api-versions"
        and policy["github"]["apiVersionLastVerified"] == "2026-07-29",
        "GitHub API version has dated official support evidence",
    )
    external = policy["github"]["externalCheck"]
    enrollment = policy["repositoryEnrollment"]
    publisher = external["publisherBinding"]
    check(
        external["expectedPublisher"] == "github-app-integration-id"
        and publisher["source"] == "repository-enrollment-receipt"
        and publisher["field"]
        == "requiredStatusChecks.externalReview.integrationId"
        and publisher["type"] == "positive-integer"
        and publisher["mustEqualRulesetIntegrationId"] is True
        and publisher["mustEqualObservedCheckRunAppId"] is True
        and publisher["immutableWhileEnrollmentActive"] is True
        and publisher["environmentOverrideAllowed"] is False,
        "external check requires a concrete GitHub App integration id",
    )
    success = external["successPredicate"]
    check(
        success["validatedVerdict"] == "PASSED"
        and success["findings"] == []
        and success["unverified"] == []
        and success["candidateAcquisitionComplete"] is True
        and success["candidatePolicyChecksPassed"] is True
        and success["provenanceVerified"] is True
        and success["makerRouteEligible"] is True
        and success["redactionManifestEmpty"] is True
        and success["exactCoordinatesRevalidatedBeforePublish"] is True
        and success["allConditionsRequired"] is True
        and success["consumerOverrideAllowed"] is False,
        "success is allowed only for a complete exact passing review",
    )
    binding = external["candidateBinding"]
    external_id = binding["externalId"]
    check(
        binding["checkRunHeadShaSource"]
        == {
            "pull_request": "candidate-manifest-checkSha",
            "merge_group": "candidate-manifest-headSha",
        }
        and external_id["algorithm"] == "sha256"
        and external_id["canonicalization"]
        == "rfc8785-json-canonicalization-scheme"
        and external_id["payloadSchema"]
        == "REVIEW_BROKER_RUNTIME.schema.json#/$defs/externalIdPayload"
        and external_id["commonFields"]
        == [
            "repository",
            "subjectType",
            "headSha",
            "baseSha",
            "candidateManifestSha256",
            "verdictSha256",
        ]
        and external_id["subjectFields"]["pull_request"]
        == ["pullRequest", "checkSha", "provenanceReceiptSha256"]
        and external_id["subjectFields"]["merge_group"]
        == ["pullRequests"]
        and external_id["pullRequestFieldsSource"] == "candidate-manifest"
        and external_id["mergeGroupPullRequestsSource"]
        == "closed-object-with-component-keys-and-true-values"
        and external_id["candidateManifestSha256Source"]
        == "persisted-candidate-manifest"
        and external_id["verdictSha256Source"]
        == "persisted-validated-verdict"
        and external_id["publishedValue"]
        == "lowercase-hex-sha256-of-rfc8785-payload"
        and external_id["receiptField"] == "externalIdPayloadSha256"
        and external_id["publishedValueMustEqualReceiptField"] is True
        and binding["pullRequestCoordinatesMustEqualManifest"] is True
        and binding["mergeGroupHeadBaseAndPullRequestsMustEqualManifest"] is True
        and binding["rejectCoordinateDriftBeforePublish"] is True,
        "check publication is bound to the exact reviewed candidate",
    )
    check(
        enrollment["requiredStatusChecks"]
        == [
            {
                "name": external["name"],
                "expectedPublisher": external["expectedPublisher"],
                "integrationIdSource":
                    "publisherBindingReceipt.requiredStatusChecks.externalReview.integrationId",
            },
            {
                "name": policy["github"]["machineCheck"]["name"],
                "expectedPublisher": policy["github"]["machineCheck"]["expectedPublisher"],
                "integrationId": policy["github"]["machineCheck"]["integrationId"],
                "authority": "organization-ruleset-workflow",
                "workflowRepository": "hihol-labs/idea-to-deploy",
                "workflowPath": ".github/workflows/itd-machine-oracle.yml",
                "workflowRepositoryIdSource":
                    "publisherBindingReceipt.requiredStatusChecks.machineOracle.workflowRepositoryId",
                "workflowShaSource":
                    "publisherBindingReceipt.requiredStatusChecks.machineOracle.workflowSha",
            },
        ]
        and enrollment["repositoryRulesetFallback"] is False
        and policy["github"]["machineCheck"]["immutableWorkflowShaRequired"]
        is True
        and policy["github"]["machineCheck"]["contractSource"]
        == "target-protected-base-head"
        and enrollment["requirePublisherBinding"] is True,
        "enrollment binds the App check and protected machine workflow",
    )
    publisher_receipt = enrollment["publisherBindingReceipt"]
    check(
        publisher_receipt["requiredFields"]
        == [
            "repository",
            "rulesetId",
            "rulesetEnforcement",
            "rulesetTarget",
            "defaultBranchRef",
            "protectedRefPatterns",
            "excludedRefPatterns",
            "requiredPullRequest",
            "requireUpToDate",
            "requiredStatusChecks",
            "githubAppClientId",
            "githubAppSlug",
            "githubAppOwner",
            "githubAppNodeId",
            "blockDeletion",
            "blockForcePush",
            "mergeGroupEventsRequired",
            "bypassActors",
            "policyId",
            "observedAt",
        ]
        and publisher_receipt["liveRulesetSnapshotRequired"] is True
        and publisher_receipt["rulesetEnforcementMustBeActive"] is True
        and publisher_receipt["rulesetTargetMustBeBranch"] is True
        and publisher_receipt["protectedRefPatternRepresentation"]
        == "canonical-object-set-keys-with-true-values"
        and publisher_receipt["protectedRefPatternsMustContain"]
        == ["~DEFAULT_BRANCH", "refs/heads/release/*"]
        and publisher_receipt["excludedRefPatternsMustEqual"] == []
        and publisher_receipt["requiredPullRequestMustEqualPolicy"] is True
        and publisher_receipt["requireUpToDateMustEqualPolicy"] is True
        and publisher_receipt["externalCheckIntegrationIdType"]
        == "positive-integer"
        and publisher_receipt["rulesetExternalIntegrationIdMustEqualReceipt"] is True
        and publisher_receipt["rulesetMachineWorkflowMustEqualReceipt"] is True
        and publisher_receipt["blockDeletionMustEqualPolicy"] is True
        and publisher_receipt["blockForcePushMustEqualPolicy"] is True
        and publisher_receipt["mergeGroupEventsMustEqualPolicy"] is True
        and publisher_receipt["rulesetBypassActorsMustEqual"] == []
        and publisher_receipt["activeReceiptMutable"] is False
        and publisher_receipt["policyId"] == "itd-central-review-broker-v1"
        and publisher_receipt["rotation"]
        == "disable-merge-reenroll-and-revalidate-before-enable"
        and publisher_receipt["driftDisposition"]
        == "disable-merge-and-reenroll"
        and enrollment["adminBypassAllowed"] is False
        and enrollment["anyBypassActorAllowed"] is False,
        "active enrollment binds the live ruleset without bypass actors",
    )
    manifest = policy["candidate"]["manifest"]
    check(
        manifest["version"] == 1
        and manifest["fieldTypes"]["version"] == "constant-integer-1"
        and manifest["canonicalization"] == "rfc8785-json-canonicalization-scheme"
        and manifest["completeValue"] is True
        and {
            "version",
            "totalDecodedBlobBytes",
            "reviewDiffSha256",
            "reviewDiffBytes",
            "pagination",
            "files",
        }.issubset(manifest["commonRequiredFields"]),
        "candidate manifest binds complete raw and sanitized inputs",
    )
    check(
        manifest["subjectRequiredFields"]["pull_request"]
        == ["pullRequest", "checkSha", "provenanceReceiptSha256"]
        and manifest["subjectRequiredFields"]["merge_group"] == ["components"]
        and manifest["conditionalRequiredFields"]
        == {
            "transparentReviewPresent": ["totalReviewBytes"],
            "transparentFileRecord": ["baseReview", "headReview"],
        }
        and manifest["fieldTypes"]["totalReviewBytes"] == "nonnegative-integer"
        and manifest["fileFields"][-2:] == ["baseReview", "headReview"]
        and set(manifest["fileFieldTypes"]) == set(manifest["fileFields"])
        and manifest["fileFieldTypes"]["baseReview"]
        == "declared-transparent-review-binding-or-null"
        and manifest["fileFieldTypes"]["headReview"]
        == "declared-transparent-review-binding-or-null"
        and manifest["subjectRepresentations"]["pullRequest"]["checkSha"]
        == "current-github-test-merge-commit-for-exact-head-and-base"
        and manifest["subjectRepresentations"]["pullRequest"][
            "provenanceReceiptSha256"
        ]
        == "current-verified-exact-pr-provenance-receipt"
        and manifest["subjectRepresentations"]["mergeGroup"]["components"]
        == "nonempty-object-keyed-by-canonical-pull-request-number"
        and manifest["subjectRepresentations"]["mergeGroup"]["checkRunSha"]
        == "derived-from-headSha",
        "candidate manifest canonically binds PR and merge-group composition",
    )
    check(
        set(manifest["fieldTypes"])
        == set(manifest["commonRequiredFields"])
        | set(manifest["subjectRequiredFields"]["pull_request"])
        | set(manifest["subjectRequiredFields"]["merge_group"])
        | set(manifest["conditionalRequiredFields"]["transparentReviewPresent"])
        and {
            "file-object-keys-are-unique-paths-and-rfc8785-canonicalization-orders-them",
            "component-keys-are-canonical-positive-pull-request-numbers",
            "external-pullRequests-object-keys-equal-component-keys-and-values-are-true",
            "pull-request-checkSha-is-current-test-merge-commit-with-base-and-head-parents",
            "merge-group-checkRunSha-is-derived-from-headSha",
            "pull-request-provenance-receipt-binds-repository-pullRequest-headSha-baseSha-and-is-revalidated-before-review-and-publish",
            "pull-request-compare-request-base-equals-baseSha-and-head-equals-headSha",
            "merge-group-compare-request-base-equals-baseSha-and-head-equals-headSha",
            "every-file-content-is-full-blob-with-decoded-size-and-git-blob-sha-verified",
            "totalDecodedBlobBytes-equals-sum-of-every-baseBytes-and-headBytes-and-does-not-exceed-maxTotalDecodedBlobBytes",
            "reviewDiff-is-itd-canonical-unified-diff-v1-over-all-manifest-files",
            "reviewDiff-covers-every-manifest-file-exactly-once-in-path-order",
            "sanitizerVersion-is-pinned-and-allowlisted",
            "redactionManifest-binds-all-transformations",
            "clean-redactionManifest-reviewDiffSha256-equals-candidate-reviewDiffSha256",
            "reviewable-candidate-requires-clean-redactionManifest",
            "reviewDiff-is-the-unmodified-canonical-review-input-diff-raw-for-text-logical-for-transparent-after-clean-scan",
            "declared-transparent-representations-bind-raw-git-bytes-and-logical-review-bytes",
            "totalReviewBytes-equals-sum-of-raw-text-and-logical-transparent-base-and-head-review-inputs-and-does-not-exceed-maxTotalDecodedBlobBytes",
            "any-redaction-blocks-provider-dispatch-and-success",
        }
        == set(manifest["invariants"]),
        "manifest types and transformations form a closed exact-candidate contract",
    )
    acquisition = policy["candidate"]["acquisition"]
    check(
        acquisition["changedFileList"]
        == "github-compare-json-complete-pagination"
        and acquisition["githubPatchFieldsTrusted"] is False
        and acquisition["fileContent"] == "github-git-blob-api-base64"
        and acquisition["blobResourceLimits"]
        == {
            "encodedResponseReadMode": "bounded-stream",
            "maxEncodedResponseBodyBytesPerBlobSource":
                "candidate.maxEncodedBlobResponseBytes",
            "encodedOversizeDetection":
                "reject-before-buffering-first-byte-over-limit",
            "maxDecodedBytesPerBlobSource": "candidate.maxDecodedBlobBytes",
            "decodedOversizeDetection":
                "reject-before-full-decode-hash-or-diff",
            "maxAggregateDecodedBytesSource":
                "candidate.maxTotalDecodedBlobBytes",
            "aggregateAccounting":
                "sum-every-baseBytes-and-headBytes-including-zero-sides",
            "limitEnforcementBefore": [
                "full-response-buffer",
                "blob-hash",
                "canonical-diff",
                "provider-request",
            ],
            "violationDisposition":
                "UNVERIFIED-action_required-no-provider-call",
        }
        and policy["candidate"]["maxEncodedBlobResponseBytes"] == 1500000
        and policy["candidate"]["maxDecodedBlobBytes"] == 1048576
        and policy["candidate"]["maxTotalDecodedBlobBytes"] == 16777216
        and acquisition["canonicalDiffAlgorithm"]
        == "itd-canonical-unified-diff-v1"
        and acquisition["pathSafety"]
        == {
            "profile": "git-posix-relative-path-v1",
            "appliesTo": ["files-object-keys", "fileRecord.previousPath"],
            "rejectAbsolute": True,
            "rejectWindowsDrivePrefix": True,
            "rejectBackslash": True,
            "rejectEmptyOrDotSegments": True,
            "rejectDotDotSegments": True,
            "rejectControlCharacters": True,
            "maxCodePoints": 4096,
        }
        and acquisition["coverageChecks"]
        == [
            "all-paginated-files-have-required-base-and-head-blobs",
            "each-manifest-file-emitted-exactly-once",
            "emission-order-is-rfc8785-canonical-file-key-order",
            "emitted-file-count-equals-files-object-property-count",
        ]
        and acquisition["incompleteOrMismatchedBlobDisposition"]
        == "UNVERIFIED-action_required-no-provider-call",
        "candidate diff is rebuilt from complete verified blobs",
    )
    check(
        policy["candidate"]["transparentReview"]
        == {
            "representations": {
                "gzip-jsonl-utf8-v1": {
                    "pathSuffix": ".jsonl.gz",
                    "rawSource": "verified-complete-git-blob",
                    "transform": "bounded-stream-single-gzip-member",
                    "maxLogicalBlobBytesSource":
                        "candidate.maxDecodedBlobBytes",
                    "maxAggregateLogicalBytesSource":
                        "candidate.maxTotalDecodedBlobBytes",
                    "utf8Required": True,
                    "nulAllowed": False,
                    "everyJsonlLineMustParse": True,
                    "duplicateJsonKeysAllowed": False,
                    "nonStandardJsonConstantsAllowed": False,
                    "trailingOrAdditionalGzipMembersAllowed": False,
                    "logicalManifestFields": ["encoding", "sha256", "bytes"],
                    "fileBindingFields": ["baseReview", "headReview"],
                    "presentSideBinding":
                        "closed-object-with-logicalManifestFields",
                    "absentSideBinding":
                        "required-null-for-added-base-or-removed-head",
                    "aggregateBindingField": "totalReviewBytes",
                    "aggregateAccounting":
                        "sum-raw-text-bytes-plus-logical-transparent-bytes-for-every-base-and-head-side",
                    "secretScanScope":
                        "complete-canonical-logical-diff-before-partition",
                }
            },
            "invalidOrMismatchedDisposition":
                "UNVERIFIED-action_required-no-provider-call",
            "undeclaredBinaryDisposition":
                "UNVERIFIED-action_required-no-provider-call",
        },
        "only declared bounded transparent representations are reviewable",
    )
    violation = policy["candidate"]["violationDisposition"]
    sanitization = policy["candidate"]["sanitization"]
    check(
        sanitization["selectedVersion"] == "itd-scrubber-v1"
        and sanitization["allowedVersions"] == ["itd-scrubber-v1"]
        and sanitization["redactionManifestSchema"]
        == "REVIEW_BROKER_RUNTIME.schema.json#/$defs/redactionManifest"
        and sanitization["redactionManifestPersisted"] is True
        and sanitization["providerRequestIncludesRedactionManifest"] is True
        and sanitization["reviewableCandidateRequiresCleanManifest"] is True
        and sanitization["cleanManifestBinding"]
        == {
            "field": "reviewDiffSha256",
            "mustEqualCandidateManifestField": "reviewDiffSha256",
            "mustEqualBrokerReceiptField": "reviewDiffSha256",
            "verifyBefore": ["provider-dispatch", "check-publication"],
            "mismatchDisposition":
                "UNVERIFIED-action_required-no-provider-call",
        }
        and sanitization["nonmatchingBytesMustBeIdentical"] is True
        and sanitization["diffHeadersAndLineStructureMustBeIdentical"] is True
        and sanitization["redactionRecordsSortedAndNonoverlapping"] is True
        and sanitization["originalSecretBytesPersisted"] is False
        and sanitization["anyRedactionDisposition"]
        == {
            "providerCallAllowed": False,
            "status": "UNVERIFIED",
            "externalCheckConclusion": "action_required",
            "successAllowed": False,
            "resolution": "remove-sensitive-content-and-build-a-fresh-candidate",
        },
        "sanitization is pinned and every redaction fails closed",
    )
    check(
        policy["candidate"]["mergeGroupCoordinates"]
        == {
            "fields": ["repository", "pullRequests", "headSha", "baseSha"],
            "checkRunHeadShaSource": "headSha",
            "compositionSource": "github-api-associated-pulls",
            "candidateSource": "github-api-complete-file-list-plus-full-blobs",
            "makerAggregation": "all-exact-pr-provenance",
            "mixedOrUnknownMaker": "manual-blocking-review",
        },
        "merge-group coordinates have one authoritative check-run SHA",
    )
    check(
        policy["candidate"]["maxRawDiffBytes"] == 80000
        and policy["candidate"]["maxHierarchicalRawDiffBytes"] == 1200000
        and policy["candidate"]["maxReviewUnits"] == 15
        and policy["candidate"]["hierarchicalReview"]
        == {
            "activation": "canonical-diff-bytes-gt-maxRawDiffBytes",
            "partition":
                "deterministic-complete-file-then-utf8-line-boundary",
            "fullDiffScrubbedBeforePartition": True,
            "reviewPlanBoundByCandidateManifest": True,
            "allUnitsRequiredForSuccess": True,
            "integrationVerdictRequiredForSuccess": True,
            "partialOrMissingUnitDisposition":
                "UNVERIFIED-action_required",
            "silentUnitTruncationAllowed": False,
        },
        "large candidates require complete bounded hierarchical review",
    )
    check(
        {
            "maxFiles",
            "maxEncodedBlobResponseBytes",
            "maxDecodedBlobBytes",
            "maxTotalDecodedBlobBytes",
            "maxRawDiffBytes",
            "maxHierarchicalRawDiffBytes",
            "maxReviewUnits",
            "maxProviderRequestBytes",
            "incompletePagination",
            "binaryContent",
            "transparentRepresentationFailure",
            "forkPullRequest",
            "redactionsDetected",
        }
        == set(violation["appliesTo"])
        and violation["providerCallAllowed"] is False
        and violation["externalCheckConclusion"] == "action_required"
        and violation["status"] == "UNVERIFIED"
        and violation["partialReviewAllowed"] is False
        and violation["successAllowed"] is False,
        "candidate limit or completeness violations block without partial review",
    )
    dedup = policy["github"]["webhooks"]["deduplication"]
    check(
        dedup
        == {
            "primaryKey": "sha256-exact-authenticated-raw-body-bytes",
            "secondaryKey": "X-GitHub-Delivery",
            "bodyDigestComputedAfterHmacVerification": True,
            "recordFields": [
                "bodySha256",
                "deliveryId",
                "derivedEventType",
            ],
            "store": "sqlite",
            "transaction": "begin-immediate-insert-two-unique-keys",
            "retention": "permanent",
            "sameBodyAnyDeliveryIdDisposition":
                "ack-no-enqueue-no-publish",
            "sameDeliveryDifferentBodyDisposition":
                "http-409-no-enqueue-no-publish",
        },
        "authenticated webhook bodies and delivery ids are atomically deduplicated",
    )
    webhooks = policy["github"]["webhooks"]
    check(
        webhooks["signatureInput"] == "exact-raw-request-body-bytes"
        and webhooks["secretConfig"] == "ITD_GITHUB_WEBHOOK_SECRET"
        and webhooks["eventHeader"] == "X-GitHub-Event"
        and webhooks["constantTimeComparisonRequired"] is True
        and webhooks["verifyBefore"] == ["parse", "deduplicate", "enqueue", "publish"]
        and webhooks["invalidSignatureDisposition"] == "http-401-no-state-change",
        "webhook HMAC authenticates raw bytes before every stateful action",
    )
    check(
        webhooks["maxBodyBytes"] == 2097152
        and webhooks["bodyLimitEnforcement"]
        == {
            "byteAccounting": "exact-raw-request-body-bytes",
            "readMode": "bounded-stream",
            "bufferLimitSource": "maxBodyBytes",
            "oversizeDetection":
                "reject-before-buffering-first-byte-over-maxBodyBytes",
            "enforceBefore": [
                "buffer-unbounded-body",
                "parse",
                "hmac",
                "deduplicate",
                "enqueue",
                "publish",
            ],
            "oversizeDisposition": "http-413-close-no-state-change",
            "oversizeBodyPersistence": "forbidden",
        },
        "webhook body limit is enforced while streaming before buffering or state",
    )
    oversized_body_policy = copy.deepcopy(policy)
    oversized_body_policy["github"]["webhooks"]["bodyLimitEnforcement"][
        "oversizeDisposition"
    ] = "http-413"
    try:
        validate(oversized_body_policy, schema)
    except ValueError:
        check(True, "closed policy rejects a weakened oversized-body disposition")
    else:
        raise AssertionError(
            "closed policy rejects a weakened oversized-body disposition"
        )
    check(
        webhooks["eventBinding"]
        == {
            "eventHeaderRequired": True,
            "eventTypeDerivedFromSignedPayloadShape": True,
            "headerMustEqualDerivedEventType": True,
            "actionField": "action",
            "payloadShapes": {
                "pull_request": {
                    "requiredTopLevelFields": [
                        "action",
                        "number",
                        "pull_request",
                        "repository",
                    ],
                    "forbiddenTopLevelFields": ["merge_group"],
                },
                "merge_group": {
                    "requiredTopLevelFields": [
                        "action",
                        "merge_group",
                        "repository",
                    ],
                    "forbiddenTopLevelFields": ["pull_request", "number"],
                },
            },
            "actionMustBeAcceptedForDerivedEventType": True,
            "validateBefore": ["deduplicate", "enqueue", "publish"],
            "unsupportedEventDisposition": "http-202-no-state-change",
            "shapeOrActionMismatchDisposition": "http-400-no-state-change",
        },
        "signed payload shape and action must match the event header before dispatch",
    )
    app_auth = policy["github"]["appAuthentication"]
    check(
        app_auth["jwtAlgorithm"] == "RS256"
        and app_auth["jwtRequiredClaims"] == ["iss", "iat", "exp"]
        and app_auth["jwtIssuerSource"]
        == "repository-enrollment-receipt.githubAppClientId"
        and app_auth["jwtIssuerMustEqualEnrollment"] is True
        and app_auth["jwtMaximumLifetimeSeconds"] == 600
        and app_auth["jwtIssuedAtBackdateSeconds"] == 60
        and app_auth["jwtClockSkewSeconds"] == 60
        and app_auth["jwtClaimsValidatedBeforeTokenRequest"] is True
        and app_auth["privateKeyCustody"]
        == "broker-kms-or-mounted-secret-file"
        and app_auth["privateKeyInRepositoryOrUserEnvironmentAllowed"] is False
        and app_auth["installationTokenTtlSeconds"] == 3600
        and app_auth["installationIdSource"]
        == "verified-webhook-payload-and-live-installation"
        and app_auth["installationIdRevalidatedBeforeTokenRequest"] is True
        and app_auth["installationTokenRepositoryScopeRequired"] is True,
        "GitHub App JWT and installation tokens are short-lived and enrollment-bound",
    )
    provenance = policy["provenance"]
    check(
        provenance["algorithm"] == "ed25519"
        and provenance["canonicalization"] == "rfc8785-json-canonicalization-scheme"
        and provenance["signedPayloadFields"]
        == [name for name in provenance["requiredFields"] if name != "signature"]
        and provenance["keyBindingFields"]
        == ["repository", "keyId", "makerVendor", "makerModel"]
        and provenance["keyRegistryRecordFields"]
        == [
            "repository",
            "keyId",
            "authorizedMakerVendor",
            "authorizedMakerModel",
            "publicKey",
            "issuerPrincipal",
            "status",
        ]
        and provenance["verificationKeyStore"] == "broker-public-key-registry"
        and provenance["issuerPrivateKeyCustody"]
        == "maker-principal-os-credential-store-or-kms"
        and provenance["brokerPrivateKeyAccessAllowed"] is False
        and provenance["acceptedKeyStatus"] == "active"
        and provenance["signatureEncoding"] == "base64url-without-padding"
        and provenance["issuedAtFormat"] == "rfc3339-utc-seconds-Z-no-fraction"
        and provenance["clockComparison"] == "absolute-parsed-utc-instant-skew"
        and provenance["makerFieldsMustEqualKeyAuthorization"] is True
        and provenance["crossRepositoryKeysAllowed"] is False,
        "provenance has deterministic signed bytes and repository-bound keys",
    )
    check(
        provenance["nonceDeduplication"]
        == {
            "keyFields": ["repository", "keyId", "nonce"],
            "store": "sqlite",
            "transaction": "begin-immediate-insert-unique",
            "retention": "permanent",
            "duplicateDisposition": "reject-no-enqueue-no-route",
        },
        "provenance nonces are durably and atomically replay-protected",
    )
    composition = provenance["mergeGroupComposition"]
    check(
        composition["associationSource"] == "github-api-associated-pulls"
        and composition["componentIdentity"]
        == "canonical-positive-pull-request-number-object-key"
        and composition["associatedPullRequestOrder"]
        == "numeric-ascending-component-keys"
        and composition["oneComponentPerAssociatedPullRequest"] is True
        and composition[
            "eachProvenanceMustVerifyAgainstCurrentPullRequestCoordinates"
        ]
        is True
        and composition["allComponentsBoundIntoCandidateManifest"] is True
        and composition[
            "mergeGroupHeadBaseAndPullRequestsRevalidatedBeforeReviewAndPublish"
        ]
        is True
        and composition["missingMixedOrUnknownDisposition"]
        == "manual-blocking-review",
        "merge groups bind current provenance for every constituent PR",
    )
    classification = policy["routing"]["classification"]
    check(
        classification["sourceFields"] == ["makerVendor", "makerModel"]
        and classification["inputTrust"]
        == "verified-provenance-with-key-authorized-maker-only"
        and classification["firstMatchOrder"][-1] == "unknownMaker"
        and classification["consumerOverrideAllowed"] is False
        and classification["rules"]["solMaker"]
        == {"vendorEquals": "openai", "modelEquals": "gpt-5.6-sol"},
        "maker provenance maps to routes deterministically",
    )
    reviewers = policy["routing"]["reviewers"]
    constraints = policy["routing"]["selectionConstraints"]
    check(
        reviewers["openai-responses"]["model"] == "gpt-5.6-sol"
        and reviewers["openai-responses-terra"]["model"] == "gpt-5.6-terra"
        and all(row["modelPin"] == "exact" for row in reviewers.values())
        and all(
            row["inputUsdPerMillion"] > 0
            and row["outputUsdPerMillion"] > 0
            and row["pricingObservedAt"].startswith("2026-")
            for row in reviewers.values()
        )
        and constraints["identityFields"] == ["vendor", "model"]
        and constraints["normalizedExactIdentityMustDiffer"] is True
        and constraints["noEligibleDifferentIdentity"] == "UNAVAILABLE"
        and constraints["consumerOverrideAllowed"] is False,
        "routes select immutable checker identities distinct from the maker",
    )
    budget = policy["budget"]
    check(
        budget["pricingSource"] == "frozen-selected-reviewer-definition"
        and budget["reservationAmountUsd"]
        == "direct-maxReviewUsd-or-planned-hierarchical-provider-call-count-times-reviewer-cap"
        and budget["hierarchicalCallReservationMicrousd"]
        == {
            "openai-responses": 750000,
            "openai-responses-terra": 500000,
        }
        and budget["maxHierarchicalProviderCalls"] == 16
        and budget["inputTokenUpperBound"] == "utf8-provider-request-bytes"
        and budget["requestMustSetOutputTokenCap"] is True
        and budget["rounding"] == "decimal-round-up-6-places"
        and budget["currencyUnit"] == "microusd"
        and budget["reservationMicrousd"] == 750000
        and budget["monthlyMicrousd"] == 10000000
        and budget["settlementSchema"]
        == "REVIEW_BROKER_RUNTIME.schema.json#/$defs/budgetSettlement"
        and budget["authoritativeSpendSource"] == "immutable-budget-settlements"
        and budget["settledCostFormula"]
        == "ceil(inputTokens*inputUsdPerMillion+outputTokens*outputUsdPerMillion)"
        and budget["totalTokensStored"] is False
        and budget["callerSuppliedCostAccepted"] is False
        and budget["admissionPredicate"]
        == "settled-month-spend-plus-active-reservations-plus-planned-reservation-lte-monthlyUsd"
        and budget["missingOrInvalidPricing"] == "UNAVAILABLE-no-dispatch"
        and budget["nonpositiveOutputTokenCap"] == "UNAVAILABLE-no-dispatch"
        and budget["actualCostAboveReservation"]
        == "broker-incident-action_required-no-success"
        and budget["hierarchicalUncertainCharge"]
        == "settled-observed-usage-plus-one-ambiguous-provider-call-cap",
        "budget is bounded conservatively before provider dispatch",
    )
    unknown = policy["routing"]["unknownOrMixedMakerDisposition"]
    check(
        unknown["makerRouteEligible"] is False
        and unknown["automaticProviderCallAllowed"] is False
        and unknown["status"] == "UNVERIFIED"
        and unknown["externalCheckConclusion"] == "action_required"
        and unknown["manualOutcomeCanPublishSuccess"] is False
        and unknown["resolution"]
        == "repair-provenance-and-run-fresh-exact-api-review",
        "unknown or mixed makers cannot satisfy the external gate",
    )
    receipt_fields = set(policy["evidence"]["receiptCommonFields"])
    receipt_subject_fields = policy["evidence"]["receiptSubjectFields"]
    check(
        policy["evidence"]["redactionManifestPersisted"] is True
        and policy["evidence"]["usageAndCostEvidencePersisted"] is True
        and policy["evidence"]["costEvidenceSource"]
        == "budget-settlement-derived-from-primary-usage-and-frozen-policy"
        and {
            "candidateManifestSha256",
            "budgetSettlementSha256",
            "externalIdPayloadSha256",
            "makerClass",
            "checkerReviewerId",
            "policySha256",
            "reviewDiffSha256",
            "reviewDiffBytes",
            "sanitizerVersion",
            "redactionManifest",
            "providerRequestSha256",
            "providerRequestBytes",
            "fileCount",
            "paginationComplete",
        }.issubset(receipt_fields),
        "receipt preserves candidate completeness evidence",
    )
    check(
        policy["evidence"]["candidateManifestPersisted"] is True
        and receipt_subject_fields["pull_request"]
        == ["pullRequest", "checkSha", "provenanceReceiptSha256"]
        and receipt_subject_fields["merge_group"] == [],
        "receipt subject fields are normalized through the candidate manifest",
    )
    check(
        policy["evidence"]["receiptInvariants"]
        == [
            "provider-evidence-binds-direct-exact-request-or-hierarchical-request-bundle",
            "candidateManifestSha256-equals-embedded-manifest-hash",
            "provider-request-sha256-equals-direct-request-or-hierarchical-evidence-bundle",
            "provider-request-bytes-equals-direct-request-or-hierarchical-evidence-bundle",
            "every-provider-request-bytes-lte-candidate-maxProviderRequestBytes",
            "hierarchical-provider-request-evidence-bundle-binds-every-exact-request-hash-byte-count-unit-and-output-cap",
            "hierarchical-review-plan-binds-the-complete-scrubbed-diff-and-every-deterministic-unit",
            "hierarchical-success-requires-all-unit-verdicts-and-one-integration-verdict",
            "validatedVerdictSha256-equals-persisted-validated-verdict",
            "redactionManifestSha256-equals-persisted-redactionManifest",
            "successful-receipt-requires-empty-redactionManifest",
            "externalIdPayloadSha256-equals-published-check-run-external-id",
            "budgetSettlementSha256-equals-immutable-settlement",
            "budgetSettlement-binds-policy-reviewer-candidate-and-primary-usage",
            "settled-cost-is-derived-not-caller-supplied",
        ],
        "receipt binds the non-self-referential provider request and verdict",
    )

    sha1 = "a" * 40
    sha256 = "b" * 64
    empty_redaction_manifest = {
        "version": 1,
        "sanitizerVersion": "itd-scrubber-v1",
        "status": "clean",
        "reviewDiffSha256": sha256,
        "redactions": [],
    }
    redaction_validator = runtime_validator(runtime, "redactionManifest")
    redaction_validator.validate(empty_redaction_manifest)
    check(True, "empty pinned redaction manifest validates")
    Draft202012Validator(runtime).validate(empty_redaction_manifest)
    check(True, "root runtime schema recognizes redaction manifests")
    arbitrary_sanitizer = copy.deepcopy(empty_redaction_manifest)
    arbitrary_sanitizer["sanitizerVersion"] = "custom-scrubber"
    expect_rejected(
        redaction_validator,
        arbitrary_sanitizer,
        "non-allowlisted sanitizer version is rejected",
    )
    contradictory_clean_manifest = copy.deepcopy(empty_redaction_manifest)
    contradictory_clean_manifest["rawDiffSha256"] = sha256
    contradictory_clean_manifest["sanitizedDiffSha256"] = "c" * 64
    expect_rejected(
        redaction_validator,
        contradictory_clean_manifest,
        "clean redaction manifest cannot carry divergent diff hashes",
    )
    nonempty_redaction_manifest = copy.deepcopy(empty_redaction_manifest)
    nonempty_redaction_manifest["status"] = "redacted"
    del nonempty_redaction_manifest["reviewDiffSha256"]
    nonempty_redaction_manifest["rawDiffSha256"] = sha256
    nonempty_redaction_manifest["sanitizedDiffSha256"] = "c" * 64
    nonempty_redaction_manifest["redactions"] = [{
        "ruleId": "github-token",
        "byteOffset": 10,
        "originalByteLength": 40,
        "replacement": "[REDACTED-GH-TOKEN]",
    }]
    redaction_validator.validate(nonempty_redaction_manifest)
    check(True, "redaction evidence remains valid for a blocked candidate")
    added_file = {
        "previousPath": None,
        "baseBlobSha": None,
        "headBlobSha": sha1,
        "baseBytes": 0,
        "headBytes": 12,
        "status": "added",
    }
    manifest_fixture = {
        "version": 1,
        "repository": "hihol-labs/example",
        "subjectType": "pull_request",
        "pullRequest": 7,
        "headSha": sha1,
        "baseSha": "c" * 40,
        "checkSha": "d" * 40,
        "provenanceReceiptSha256": sha256,
        "source": "github-api-complete-file-list-plus-full-blobs",
        "files": {"src/new.py": added_file},
        "pagination": {"pageCount": 1, "complete": True},
        "totalDecodedBlobBytes": 12,
        "reviewDiffSha256": sha256,
        "reviewDiffBytes": 120,
        "sanitizerVersion": "itd-scrubber-v1",
        "redactionManifestSha256": sha256,
    }
    manifest_validator = runtime_validator(runtime, "candidateManifest")
    manifest_validator.validate(manifest_fixture)
    check(True, "added-file candidate manifest validates")
    transparent_manifest = copy.deepcopy(manifest_fixture)
    transparent_manifest["files"] = {
        "evidence/transcript.jsonl.gz": {
            **added_file,
            "baseReview": None,
            "headReview": {
                "encoding": "gzip-jsonl-utf8-v1",
                "sha256": sha256,
                "bytes": 48,
            },
        }
    }
    transparent_manifest["totalReviewBytes"] = 48
    manifest_validator.validate(transparent_manifest)
    check(True, "declared transparent representation manifest validates")
    missing_transparent_total = copy.deepcopy(transparent_manifest)
    del missing_transparent_total["totalReviewBytes"]
    expect_rejected(
        manifest_validator,
        missing_transparent_total,
        "transparent candidate requires aggregate review-byte accounting",
    )
    text_with_transparent_total = copy.deepcopy(manifest_fixture)
    text_with_transparent_total["totalReviewBytes"] = 12
    expect_rejected(
        manifest_validator,
        text_with_transparent_total,
        "text-only candidate cannot claim transparent review-byte accounting",
    )
    missing_transparent_binding = copy.deepcopy(manifest_fixture)
    missing_transparent_binding["files"] = {
        "evidence/transcript.jsonl.gz": added_file
    }
    expect_rejected(
        manifest_validator,
        missing_transparent_binding,
        "declared transparent path requires logical side bindings",
    )
    generic_path_with_binding = copy.deepcopy(transparent_manifest)
    generic_path_with_binding["files"] = {
        "evidence/transcript.gz": generic_path_with_binding["files"].pop(
            "evidence/transcript.jsonl.gz"
        )
    }
    expect_rejected(
        manifest_validator,
        generic_path_with_binding,
        "generic paths cannot claim a transparent representation",
    )
    malformed_transparent = copy.deepcopy(transparent_manifest)
    malformed_transparent["files"][
        "evidence/transcript.jsonl.gz"
    ]["headReview"]["encoding"] = "generic-binary-v1"
    expect_rejected(
        manifest_validator,
        malformed_transparent,
        "candidate manifest rejects an undeclared review representation",
    )
    incomplete_transparent = copy.deepcopy(transparent_manifest)
    del incomplete_transparent["files"][
        "evidence/transcript.jsonl.gz"
    ]["baseReview"]
    expect_rejected(
        manifest_validator,
        incomplete_transparent,
        "candidate manifest requires both transparent side bindings",
    )
    oversized_transparent = copy.deepcopy(transparent_manifest)
    oversized_transparent["files"][
        "evidence/transcript.jsonl.gz"
    ]["headReview"]["bytes"] = 1048577
    expect_rejected(
        manifest_validator,
        oversized_transparent,
        "candidate manifest rejects an oversized logical representation",
    )
    check(
        empty_redaction_manifest["reviewDiffSha256"]
        == manifest_fixture["reviewDiffSha256"],
        "clean scan evidence binds the exact candidate review diff",
    )
    oversized_blob = copy.deepcopy(manifest_fixture)
    oversized_blob["files"]["src/new.py"]["headBytes"] = 1048577
    oversized_blob["totalDecodedBlobBytes"] = 1048577
    expect_rejected(
        manifest_validator,
        oversized_blob,
        "candidate manifest rejects a decoded blob over the per-side limit",
    )
    oversized_blob_total = copy.deepcopy(manifest_fixture)
    oversized_blob_total["totalDecodedBlobBytes"] = 16777217
    expect_rejected(
        manifest_validator,
        oversized_blob_total,
        "candidate manifest rejects aggregate decoded blobs over the total limit",
    )
    missing_manifest_version = copy.deepcopy(manifest_fixture)
    del missing_manifest_version["version"]
    expect_rejected(
        manifest_validator,
        missing_manifest_version,
        "candidate manifest without a version is rejected",
    )
    wrong_manifest_version = copy.deepcopy(manifest_fixture)
    wrong_manifest_version["version"] = 2
    expect_rejected(
        manifest_validator,
        wrong_manifest_version,
        "candidate manifest with a different format version is rejected",
    )
    wrong_sanitizer_manifest = copy.deepcopy(manifest_fixture)
    wrong_sanitizer_manifest["sanitizerVersion"] = "custom-scrubber"
    expect_rejected(
        manifest_validator,
        wrong_sanitizer_manifest,
        "candidate manifest cannot select an arbitrary sanitizer",
    )
    removed_manifest = copy.deepcopy(manifest_fixture)
    removed_manifest["files"] = {"src/old.py": {
        "previousPath": None,
        "baseBlobSha": sha1,
        "headBlobSha": None,
        "baseBytes": 12,
        "headBytes": 0,
        "status": "removed",
    }}
    manifest_validator.validate(removed_manifest)
    check(True, "removed-file candidate manifest validates")
    ambiguous_modified_manifest = copy.deepcopy(manifest_fixture)
    ambiguous_modified_manifest["files"] = {"src/new.py": {
        "previousPath": "src/old.py",
        "baseBlobSha": sha1,
        "headBlobSha": sha1,
        "baseBytes": 12,
        "headBytes": 12,
        "status": "modified",
    }}
    ambiguous_modified_manifest["totalDecodedBlobBytes"] = 24
    expect_rejected(
        manifest_validator,
        ambiguous_modified_manifest,
        "modified file cannot carry a rename previous path",
    )
    malformed_manifest = copy.deepcopy(manifest_fixture)
    malformed_manifest["files"]["src/new.py"]["baseBlobSha"] = sha1
    expect_rejected(
        manifest_validator,
        malformed_manifest,
        "added file with a base blob is rejected",
    )
    extra_manifest = copy.deepcopy(manifest_fixture)
    extra_manifest["unbound"] = True
    expect_rejected(
        manifest_validator,
        extra_manifest,
        "candidate manifest extra fields are rejected",
    )
    redundant_count = copy.deepcopy(manifest_fixture)
    redundant_count["fileCount"] = 1
    expect_rejected(
        manifest_validator,
        redundant_count,
        "candidate manifest cannot declare a contradictory file count",
    )
    redundant_pagination_count = copy.deepcopy(manifest_fixture)
    redundant_pagination_count["pagination"]["totalFiles"] = 1
    expect_rejected(
        manifest_validator,
        redundant_pagination_count,
        "pagination cannot declare a contradictory file count",
    )
    unsafe_path = copy.deepcopy(manifest_fixture)
    unsafe_path["files"] = {"../secret": added_file}
    expect_rejected(
        manifest_validator,
        unsafe_path,
        "unsafe file path key is rejected",
    )
    unsafe_windows_path = copy.deepcopy(manifest_fixture)
    unsafe_windows_path["files"] = {"dir\\secret": added_file}
    expect_rejected(
        manifest_validator,
        unsafe_windows_path,
        "backslash file path key is rejected",
    )
    drive_relative_path = copy.deepcopy(manifest_fixture)
    drive_relative_path["files"] = {"C:secret": added_file}
    expect_rejected(
        manifest_validator,
        drive_relative_path,
        "Windows drive-relative file path key is rejected",
    )
    trailing_slash_path = copy.deepcopy(manifest_fixture)
    trailing_slash_path["files"] = {"src/": added_file}
    expect_rejected(
        manifest_validator,
        trailing_slash_path,
        "file path key with an empty trailing segment is rejected",
    )
    dot_owner = copy.deepcopy(manifest_fixture)
    dot_owner["repository"] = "../target"
    expect_rejected(
        manifest_validator,
        dot_owner,
        "dot-only GitHub owner coordinate is rejected",
    )
    dot_repository = copy.deepcopy(manifest_fixture)
    dot_repository["repository"] = "owner/.."
    expect_rejected(
        manifest_validator,
        dot_repository,
        "dot-only GitHub repository coordinate is rejected",
    )
    single_dot_owner = copy.deepcopy(manifest_fixture)
    single_dot_owner["repository"] = "./target"
    expect_rejected(
        manifest_validator,
        single_dot_owner,
        "single-dot GitHub owner coordinate is rejected",
    )
    single_dot_repository = copy.deepcopy(manifest_fixture)
    single_dot_repository["repository"] = "owner/."
    expect_rejected(
        manifest_validator,
        single_dot_repository,
        "single-dot GitHub repository coordinate is rejected",
    )
    renamed_manifest = copy.deepcopy(manifest_fixture)
    renamed_manifest["files"] = {"src/new.py": {
        "previousPath": "src/old.py",
        "baseBlobSha": sha1,
        "headBlobSha": sha1,
        "baseBytes": 12,
        "headBytes": 12,
        "status": "renamed",
    }}
    renamed_manifest["totalDecodedBlobBytes"] = 24
    manifest_validator.validate(renamed_manifest)
    check(True, "safe renamed-file previous path validates")
    unsafe_previous_path = copy.deepcopy(renamed_manifest)
    unsafe_previous_path["files"]["src/new.py"]["previousPath"] = "../old.py"
    expect_rejected(
        manifest_validator,
        unsafe_previous_path,
        "unsafe renamed-file previous path is rejected",
    )
    drive_relative_previous_path = copy.deepcopy(renamed_manifest)
    drive_relative_previous_path["files"]["src/new.py"]["previousPath"] = (
        "C:old.py"
    )
    expect_rejected(
        manifest_validator,
        drive_relative_previous_path,
        "Windows drive-relative renamed-file previous path is rejected",
    )
    trailing_slash_previous_path = copy.deepcopy(renamed_manifest)
    trailing_slash_previous_path["files"]["src/new.py"]["previousPath"] = "src/"
    expect_rejected(
        manifest_validator,
        trailing_slash_previous_path,
        "renamed-file previous path with a trailing slash is rejected",
    )
    merge_manifest = copy.deepcopy(manifest_fixture)
    merge_manifest["subjectType"] = "merge_group"
    del merge_manifest["pullRequest"]
    del merge_manifest["checkSha"]
    del merge_manifest["provenanceReceiptSha256"]
    merge_manifest["components"] = {
        "8": {
            "pullRequestHeadSha": sha1,
            "pullRequestBaseSha": "c" * 40,
            "provenanceReceiptSha256": sha256,
        }
    }
    manifest_validator.validate(merge_manifest)
    check(True, "merge-group component map validates")
    noncanonical_merge = copy.deepcopy(merge_manifest)
    noncanonical_merge["components"] = {
        "08": merge_manifest["components"]["8"]
    }
    expect_rejected(
        manifest_validator,
        noncanonical_merge,
        "noncanonical merge-group pull request key is rejected",
    )
    contradictory_merge = copy.deepcopy(merge_manifest)
    contradictory_merge["checkSha"] = "d" * 40
    expect_rejected(
        manifest_validator,
        contradictory_merge,
        "merge-group manifest cannot declare a separate check SHA",
    )

    external_id_validator = runtime_validator(runtime, "externalIdPayload")
    pr_external_id = {
        "repository": manifest_fixture["repository"],
        "subjectType": "pull_request",
        "pullRequest": manifest_fixture["pullRequest"],
        "headSha": manifest_fixture["headSha"],
        "baseSha": manifest_fixture["baseSha"],
        "checkSha": manifest_fixture["checkSha"],
        "provenanceReceiptSha256":
            manifest_fixture["provenanceReceiptSha256"],
        "candidateManifestSha256": sha256,
        "verdictSha256": sha256,
    }
    external_id_validator.validate(pr_external_id)
    check(True, "pull-request external-id payload validates")
    merge_external_id = {
        "repository": merge_manifest["repository"],
        "subjectType": "merge_group",
        "pullRequests": {key: True for key in merge_manifest["components"]},
        "headSha": merge_manifest["headSha"],
        "baseSha": merge_manifest["baseSha"],
        "candidateManifestSha256": sha256,
        "verdictSha256": sha256,
    }
    external_id_validator.validate(merge_external_id)
    check(True, "derived merge-group external-id payload validates")
    contradictory_external_id = copy.deepcopy(merge_external_id)
    contradictory_external_id["pullRequest"] = 8
    expect_rejected(
        external_id_validator,
        contradictory_external_id,
        "merge-group external-id cannot mix pull-request coordinates",
    )
    contradictory_merge_check_sha = copy.deepcopy(merge_external_id)
    contradictory_merge_check_sha["checkSha"] = merge_manifest["headSha"]
    expect_rejected(
        external_id_validator,
        contradictory_merge_check_sha,
        "merge-group external-id cannot duplicate its authoritative head SHA",
    )
    malformed_pull_request_set = copy.deepcopy(merge_external_id)
    malformed_pull_request_set["pullRequests"] = {"08": True}
    expect_rejected(
        external_id_validator,
        malformed_pull_request_set,
        "merge-group external-id requires canonical pull-request keys",
    )
    malformed_pull_request_value = copy.deepcopy(merge_external_id)
    malformed_pull_request_value["pullRequests"] = {"8": False}
    expect_rejected(
        external_id_validator,
        malformed_pull_request_value,
        "merge-group external-id set values are canonical true constants",
    )
    Draft202012Validator(runtime).validate(merge_external_id)
    check(True, "root runtime schema recognizes external-id payloads")

    provenance_fixture = {
        "repository": "hihol-labs/example",
        "pullRequest": 7,
        "headSha": sha1,
        "baseSha": "c" * 40,
        "makerVendor": "openai",
        "makerModel": "gpt-5.6-sol",
        "makerSession": "session-1",
        "issuedAt": "2026-07-29T12:00:00Z",
        "nonce": "abcdefghijklmnop",
        "keyId": "maker-key-1",
        "signature": "A" * 86,
    }
    provenance_validator = runtime_validator(runtime, "provenanceRecord")
    provenance_validator.validate(provenance_fixture)
    check(True, "provenance record validates")
    bad_provenance = copy.deepcopy(provenance_fixture)
    bad_provenance["signature"] = "short"
    expect_rejected(
        provenance_validator,
        bad_provenance,
        "malformed provenance signature is rejected",
    )

    usage_fixture = {"inputTokens": 500, "outputTokens": 100}
    settlement_fixture = {
        "version": 1,
        "reservationId": "1" * 32,
        "period": "2026-07",
        "reviewerId": "openai-responses-terra",
        "policySha256": sha256,
        "candidateManifestSha256": sha256,
        "usage": usage_fixture,
        "reservationMicrousd": 750000,
        "status": "settled",
        "settledAt": "2026-07-29T12:00:30Z",
    }
    settlement_validator = runtime_validator(runtime, "budgetSettlement")
    settlement_validator.validate(settlement_fixture)
    check(True, "primary-usage budget settlement validates")
    Draft202012Validator(runtime).validate(settlement_fixture)
    check(True, "root runtime schema recognizes budget settlements")
    supplied_total = copy.deepcopy(settlement_fixture)
    supplied_total["usage"]["totalTokens"] = 600
    expect_rejected(
        settlement_validator,
        supplied_total,
        "caller-supplied total token count is rejected",
    )
    supplied_cost = copy.deepcopy(settlement_fixture)
    supplied_cost["costUsd"] = 0.000001
    expect_rejected(
        settlement_validator,
        supplied_cost,
        "caller-supplied settlement cost is rejected",
    )
    terra_pricing = policy["routing"]["reviewers"]["openai-responses-terra"]
    derived_microusd = (
        Decimal(usage_fixture["inputTokens"])
        * Decimal(str(terra_pricing["inputUsdPerMillion"]))
        + Decimal(usage_fixture["outputTokens"])
        * Decimal(str(terra_pricing["outputUsdPerMillion"]))
    ).to_integral_value(rounding=ROUND_CEILING)
    check(
        derived_microusd == Decimal("2750"),
        "settled cost is reproducible from primary usage and frozen pricing",
    )

    receipt_fixture = {
        "repository": "hihol-labs/example",
        "pullRequest": 7,
        "subjectType": "pull_request",
        "headSha": sha1,
        "baseSha": "c" * 40,
        "installationId": 73,
        "checkSha": "d" * 40,
        "provenanceReceiptSha256": sha256,
        "checkPublication": {
            "id": 101,
            "appIntegrationId": 2,
            "name": "ITD external review gate",
            "headSha": "d" * 40,
            "externalId": sha256,
            "status": "completed",
            "conclusion": "success",
        },
        "makerClass": "solMaker",
        "checkerReviewerId": "openai-responses-terra",
        "policySha256": sha256,
        "candidateManifestSha256": sha256,
        "budgetSettlementSha256": sha256,
        "externalIdPayloadSha256": sha256,
        "reviewDiffSha256": sha256,
        "reviewDiffBytes": 120,
        "sanitizerVersion": "itd-scrubber-v1",
        "redactionManifest": empty_redaction_manifest,
        "providerRequestSha256": sha256,
        "providerRequestBytes": 2000,
        "fileCount": 1,
        "paginationComplete": True,
        "verdictSha256": sha256,
        "usage": usage_fixture,
        "status": "PASSED",
        "observedAt": "2026-07-29T12:01:00Z",
    }
    receipt_validator = runtime_validator(runtime, "brokerReceipt")
    receipt_validator.validate(receipt_fixture)
    check(True, "broker receipt validates")
    check_publication_validator = runtime_validator(
        runtime, "checkPublication"
    )
    check_publication_validator.validate(receipt_fixture["checkPublication"])
    Draft202012Validator(runtime).validate(
        receipt_fixture["checkPublication"]
    )
    check(True, "root runtime schema recognizes observed check publication")
    wrong_passing_conclusion = copy.deepcopy(receipt_fixture)
    wrong_passing_conclusion["checkPublication"]["conclusion"] = "failure"
    expect_rejected(
        receipt_validator,
        wrong_passing_conclusion,
        "passing receipt requires a successful observed check conclusion",
    )
    forged_check_field = copy.deepcopy(receipt_fixture)
    forged_check_field["checkPublication"]["publisher"] = "lookalike"
    expect_rejected(
        receipt_validator,
        forged_check_field,
        "observed check publication fields are closed",
    )
    redacted_passing_receipt = copy.deepcopy(receipt_fixture)
    redacted_passing_receipt["redactionManifest"] = nonempty_redaction_manifest
    expect_rejected(
        receipt_validator,
        redacted_passing_receipt,
        "a passing broker receipt cannot contain any redaction",
    )
    redacted_blocked_receipt = copy.deepcopy(redacted_passing_receipt)
    redacted_blocked_receipt["status"] = "UNVERIFIED"
    expect_rejected(
        receipt_validator,
        redacted_blocked_receipt,
        "redacted candidates never produce provider-call broker receipts",
    )
    null_provenance_receipt = copy.deepcopy(receipt_fixture)
    null_provenance_receipt["provenanceReceiptSha256"] = None
    expect_rejected(
        receipt_validator,
        null_provenance_receipt,
        "a pull-request receipt cannot pass with null provenance",
    )
    null_pull_request_receipt = copy.deepcopy(receipt_fixture)
    null_pull_request_receipt["pullRequest"] = None
    expect_rejected(
        receipt_validator,
        null_pull_request_receipt,
        "a pull-request receipt cannot pass with a null PR number",
    )
    oversized_receipt = copy.deepcopy(receipt_fixture)
    oversized_receipt["providerRequestBytes"] = 100001
    expect_rejected(
        receipt_validator,
        oversized_receipt,
        "oversized provider request receipt is rejected",
    )
    same_model_route = copy.deepcopy(receipt_fixture)
    same_model_route["checkerReviewerId"] = "openai-responses"
    expect_rejected(
        receipt_validator,
        same_model_route,
        "same-model reviewer route cannot produce a passing receipt",
    )
    merge_receipt = copy.deepcopy(receipt_fixture)
    merge_receipt["subjectType"] = "merge_group"
    del merge_receipt["pullRequest"]
    del merge_receipt["checkSha"]
    del merge_receipt["provenanceReceiptSha256"]
    merge_receipt["checkPublication"]["headSha"] = merge_receipt["headSha"]
    receipt_validator.validate(merge_receipt)
    check(True, "normalized merge-group broker receipt validates")
    contradictory_merge_receipt = copy.deepcopy(merge_receipt)
    contradictory_merge_receipt["checkSha"] = "d" * 40
    expect_rejected(
        receipt_validator,
        contradictory_merge_receipt,
        "merge-group receipt cannot declare a separate check SHA",
    )

    enrollment_validator = runtime_validator(runtime, "enrollmentReceipt")
    enrollment_fixture = {
        "repository": "hihol-labs/example",
        "rulesetId": 1,
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
                "integrationId": 2,
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
        "githubAppClientId": "Iv1a2b3c4d5e6f7g8",
        "githubAppSlug": "itd-review-broker",
        "githubAppOwner": "hihol-labs",
        "githubAppNodeId": "MDM6QXBwMg",
        "blockDeletion": True,
        "blockForcePush": True,
        "mergeGroupEventsRequired": True,
        "bypassActors": [],
        "policyId": "itd-central-review-broker-v1",
        "observedAt": "2026-07-29T12:02:00Z",
    }
    enrollment_validator.validate(enrollment_fixture)
    check(True, "enrollment receipt validates")
    bad_enrollment = copy.deepcopy(enrollment_fixture)
    bad_enrollment["requiredStatusChecks"]["externalReview"]["integrationId"] = 0
    expect_rejected(
        enrollment_validator,
        bad_enrollment,
        "nonpositive GitHub App integration id is rejected",
    )
    wrong_external_check = copy.deepcopy(enrollment_fixture)
    wrong_external_check["requiredStatusChecks"]["externalReview"]["name"] = (
        "ITD external review gate spoof"
    )
    expect_rejected(
        enrollment_validator,
        wrong_external_check,
        "live ruleset receipt requires the exact external check name",
    )
    wrong_machine_publisher = copy.deepcopy(enrollment_fixture)
    wrong_machine_publisher["requiredStatusChecks"]["machineOracle"][
        "integrationId"
    ] = 2
    expect_rejected(
        enrollment_validator,
        wrong_machine_publisher,
        "live ruleset receipt requires the GitHub Actions integration",
    )
    bad_client_id = copy.deepcopy(enrollment_fixture)
    bad_client_id["githubAppClientId"] = "bad id"
    expect_rejected(
        enrollment_validator,
        bad_client_id,
        "malformed GitHub App JWT issuer client id is rejected",
    )
    wrong_policy_enrollment = copy.deepcopy(enrollment_fixture)
    wrong_policy_enrollment["policyId"] = "another-policy"
    expect_rejected(
        enrollment_validator,
        wrong_policy_enrollment,
        "enrollment under another policy revision is rejected",
    )
    bypassed_enrollment = copy.deepcopy(enrollment_fixture)
    bypassed_enrollment["bypassActors"] = [
        {"actorType": "Team", "actorId": 7, "bypassMode": "always"}
    ]
    expect_rejected(
        enrollment_validator,
        bypassed_enrollment,
        "an enrollment receipt with any bypass actor is rejected",
    )
    inactive_enrollment = copy.deepcopy(enrollment_fixture)
    inactive_enrollment["rulesetEnforcement"] = "evaluate"
    expect_rejected(
        enrollment_validator,
        inactive_enrollment,
        "a non-enforcing live ruleset snapshot is rejected",
    )
    uncovered_default_branch = copy.deepcopy(enrollment_fixture)
    del uncovered_default_branch["protectedRefPatterns"]["~DEFAULT_BRANCH"]
    expect_rejected(
        enrollment_validator,
        uncovered_default_branch,
        "an enrollment that omits the default-branch target is rejected",
    )
    excluded_default_branch = copy.deepcopy(enrollment_fixture)
    excluded_default_branch["excludedRefPatterns"] = {
        "refs/heads/main": True
    }
    expect_rejected(
        enrollment_validator,
        excluded_default_branch,
        "an enrollment with any ref exclusion is rejected",
    )

    verdict_validator = Draft202012Validator(verdict_schema)
    verdict_validator.validate(
        {"verdict": "PASSED", "findings": [], "unverified": []}
    )
    check(True, "closed reviewer verdict validates")
    expect_rejected(
        verdict_validator,
        {
            "verdict": "PASSED",
            "findings": [],
            "unverified": [],
            "extra": True,
        },
        "reviewer verdict extra fields are rejected",
    )

    invariants = [
        ("authority", "externalReview", "repository-workflow"),
        ("authority", "localHooks", "merge-authority"),
        ("candidate", "executeCandidateCode", True),
        ("candidate", "allowSilentTruncation", True),
        ("routing", "sameModelHighRiskAllowed", True),
        ("routing", "automatedCliFallbackAllowed", True),
        ("routing", "classification", {}),
        ("budget", "onExhaustion", "PASSED"),
        ("evidence", "rawDiffPersisted", True),
        ("service", "candidateProcessExecutionAllowed", True),
        ("repositoryEnrollment", "adminBypassAllowed", True),
        ("repositoryEnrollment", "anyBypassActorAllowed", True),
        ("repositoryEnrollment", "requirePublisherBinding", False),
    ]
    for section, name, replacement in invariants:
        changed = copy.deepcopy(policy)
        changed[section][name] = replacement
        try:
            validate(changed, schema)
        except ValueError:
            check(True, f"mutation rejected: {section}.{name}")
        else:
            raise AssertionError(f"mutation accepted: {section}.{name}")

    extra = copy.deepcopy(policy)
    extra["github"]["externalCheck"]["passOnQuota"] = True
    try:
        validate(extra, schema)
    except ValueError:
        check(True, "nested extra field rejected by frozen const")
    else:
        raise AssertionError("nested extra field accepted")

    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
