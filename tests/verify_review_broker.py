#!/usr/bin/env python3
"""Executable broker regressions for exact GitHub/API review evidence."""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "_shared" / "itd_review_broker.py"
POLICY_PATH = ROOT / "skills" / "_shared" / "REVIEW_BROKER_POLICY.json"
SCHEMA_PATH = ROOT / "skills" / "_shared" / "REVIEW_BROKER_POLICY.schema.json"

spec = importlib.util.spec_from_file_location("itd_review_broker_test", MODULE_PATH)
assert spec and spec.loader
broker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = broker
spec.loader.exec_module(broker)

CHECKS = 0
REPOSITORY = "hihol-labs/example"
HEAD = "a" * 40
BASE = "b" * 40
CHECK_SHA = "c" * 40
MERGE_HEAD = "d" * 40
APP_ID = 424242
INSTALLATION_ID = 991
CLIENT_ID = "Iv1_fixture-client"
PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_KEY = PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def expect_error(status: str, fn, label: str) -> str:
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except broker.BrokerError as exc:
        if exc.status != status:
            raise AssertionError(
                f"{label}: expected {status}, got {exc.status}: {exc.reason}"
            ) from exc
        return exc.reason
    raise AssertionError(f"{label}: expected {status}")


def load() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def policy_phase() -> None:
    policy = broker.validate_policy(load())
    check(
        policy["authority"]["externalReview"] == "github-app-check-run",
        "App authority",
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    check(schema["additionalProperties"] is False, "schema closes top level")
    for name in (
        "authority",
        "github",
        "candidate",
        "provenance",
        "routing",
        "budget",
        "evidence",
        "service",
        "repositoryEnrollment",
    ):
        check(
            schema["properties"][name]["const"] == policy[name],
            f"schema freezes {name}",
        )
    for label, path, value in (
        (
            "neutral unavailable",
            ("github", "externalCheck", "unavailableConclusion"),
            "neutral",
        ),
        (
            "candidate execution",
            ("candidate", "executeCandidateCode"),
            True,
        ),
        (
            "silent truncation",
            ("candidate", "allowSilentTruncation"),
            True,
        ),
        (
            "CLI fallback",
            ("routing", "automatedCliFallbackAllowed"),
            True,
        ),
    ):
        changed = copy.deepcopy(policy)
        cursor = changed
        for part in path[:-1]:
            cursor = cursor[part]
        cursor[path[-1]] = value
        expect_error(
            "UNVERIFIED",
            lambda changed=changed: broker.validate_policy(changed),
            label,
        )


def enrollment_receipt() -> dict[str, Any]:
    return {
        "repository": REPOSITORY,
        "rulesetId": 101,
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
                "integrationId": APP_ID,
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
        "observedAt": broker.now_iso(),
    }


def key_record() -> dict[str, Any]:
    return {
        "repository": REPOSITORY,
        "keyId": "maker-key",
        "authorizedMakerVendor": "openai",
        "authorizedMakerModel": "gpt-5.6-sol",
        "publicKey": broker.b64url(PUBLIC_KEY),
        "issuerPrincipal": "windows-user-dmitry",
        "status": "active",
    }


def signed_provenance() -> dict[str, Any]:
    return broker.sign_provenance(
        {
            "repository": REPOSITORY,
            "pullRequest": 7,
            "headSha": HEAD,
            "baseSha": BASE,
            "makerVendor": "openai",
            "makerModel": "gpt-5.6-sol",
            "makerSession": "maker-session",
            "issuedAt": broker.now_iso(),
            "nonce": "n" * 24,
            "keyId": "maker-key",
        },
        PRIVATE_KEY,
    )


def coordinates() -> broker.Coordinates:
    return broker.Coordinates(
        REPOSITORY, 7, HEAD, BASE, INSTALLATION_ID
    ).validate()


OLD = b'print("old")\n'
NEW = b'print("new")\n'


class FakeGitHub(broker.GitHubApi):
    def __init__(self) -> None:
        self.old = OLD
        self.new = NEW
        self.old_sha = broker._git_blob_sha(self.old)
        self.new_sha = broker._git_blob_sha(self.new)
        self.compare_head = HEAD
        self.merge_base_sha = BASE
        self.live_head = HEAD
        self.live_base = BASE
        self.check_sha = CHECK_SHA
        self.mergeable: bool | None = True
        self.file_row: dict[str, Any] = {
            "filename": "app.py",
            "status": "modified",
            "sha": self.new_sha,
            "patch": "THIS FIELD MUST NEVER BE TRUSTED",
        }
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.checks: dict[int, dict[str, Any]] = {}
        self.next_check = 100
        self.observed_app_id = APP_ID
        self.merge_pull_pages: dict[int, list[dict[str, Any]]] | None = None

    def request_json(
        self,
        method: str,
        path: str,
        token: str,
        data: dict[str, Any] | None = None,
        limit: int = 4 * 1024 * 1024,
    ) -> Any:
        del limit
        check(token == "installation-token", "repository-scoped token used")
        self.calls.append((method, path, copy.deepcopy(data)))
        if method == "GET" and "/compare/" in path:
            return {
                "base_commit": {"sha": BASE},
                "merge_base_commit": {"sha": self.merge_base_sha},
                "ahead_by": 1,
                "commits": [{"sha": self.compare_head}],
                "files": [copy.deepcopy(self.file_row)],
            }
        if method == "GET" and path.endswith("/pulls/7"):
            return {
                "state": "open",
                "mergeable": self.mergeable,
                "merge_commit_sha": self.check_sha,
                "head": {
                    "sha": self.live_head,
                    "repo": {"full_name": REPOSITORY},
                },
                "base": {
                    "sha": self.live_base,
                    "repo": {"full_name": REPOSITORY},
                },
            }
        if method == "GET" and path.endswith(f"/commits/{self.check_sha}"):
            return {
                "sha": self.check_sha,
                "parents": [{"sha": self.live_base}, {"sha": self.live_head}],
            }
        if (
            method == "GET"
            and f"/commits/{MERGE_HEAD}/pulls?" in path
        ):
            default = [
                {
                    "number": 7,
                    "state": "open",
                    "head": {
                        "sha": HEAD,
                        "repo": {"full_name": REPOSITORY},
                    },
                    "base": {
                        "sha": BASE,
                        "repo": {"full_name": REPOSITORY},
                    },
                }
            ]
            page = int(
                urllib.parse.parse_qs(
                    urllib.parse.urlsplit(path).query
                )["page"][0]
            )
            return copy.deepcopy(
                (self.merge_pull_pages or {1: default}).get(page, [])
            )
        if method == "GET" and "/contents/app.py?ref=" in path:
            raw = self.old if path.endswith(BASE) else self.new
            sha = self.old_sha if path.endswith(BASE) else self.new_sha
            return {"type": "file", "sha": sha, "size": len(raw)}
        if method == "GET" and "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[1]
            raw = self.old if sha == self.old_sha else self.new
            return {
                "sha": sha,
                "size": len(raw),
                "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii"),
            }
        if method == "POST" and path.endswith("/check-runs"):
            self.next_check += 1
            self.checks[self.next_check] = {
                "id": self.next_check,
                "appIntegrationId": self.observed_app_id,
                "name": data["name"],
                "headSha": data["head_sha"],
                "externalId": data["external_id"],
                "status": data["status"],
                "conclusion": None,
            }
            return {"id": self.next_check}
        if method == "PATCH" and "/check-runs/" in path:
            check_id = int(path.rsplit("/", 1)[1])
            current = self.checks[check_id]
            current.update(
                {
                    "name": data["name"],
                    "externalId": data["external_id"],
                    "status": data["status"],
                    "conclusion": data["conclusion"],
                }
            )
            return {"id": check_id}
        if method == "GET" and "/check-runs/" in path:
            current = self.checks[int(path.rsplit("/", 1)[1])]
            return {
                "id": current["id"],
                "app": {"id": current["appIntegrationId"]},
                "name": current["name"],
                "head_sha": current["headSha"],
                "external_id": current["externalId"],
                "status": current["status"],
                "conclusion": current["conclusion"],
            }
        raise AssertionError(f"unexpected GitHub call: {method} {path}")


class FakeAuth:
    def __init__(self) -> None:
        self.api = None

    def installation_token(
        self, installation_id: int, repository: str, expected_app_id: int
    ) -> str:
        check(installation_id == INSTALLATION_ID, "exact installation id")
        check(repository == REPOSITORY, "exact installation repository")
        check(expected_app_id == APP_ID, "enrollment App id used")
        return "installation-token"


class PendingOnceGitHub(FakeGitHub):
    def __init__(self) -> None:
        super().__init__()
        self.pull_reads = 0

    def request_json(
        self,
        method: str,
        path: str,
        token: str,
        data: dict[str, Any] | None = None,
        limit: int = 4 * 1024 * 1024,
    ) -> Any:
        if method == "GET" and path.endswith("/pulls/7"):
            self.pull_reads += 1
            if self.pull_reads == 1:
                original = self.mergeable
                self.mergeable = None
                try:
                    return super().request_json(
                        method, path, token, data, limit
                    )
                finally:
                    self.mergeable = original
        return super().request_json(method, path, token, data, limit)


class EvidenceOrderGitHub(FakeGitHub):
    def __init__(self, store: broker.BrokerStore) -> None:
        super().__init__()
        self.store = store
        self.success_saw_preparation = False
        self.terminal_patch_evidence: list[bool] = []

    def request_json(
        self,
        method: str,
        path: str,
        token: str,
        data: dict[str, Any] | None = None,
        limit: int = 4 * 1024 * 1024,
    ) -> Any:
        if method == "PATCH" and "/check-runs/" in path and isinstance(data, dict):
            check_id = int(path.rsplit("/", 1)[1])
            review_rows = self.store.db.execute(
                """
                SELECT receipt_template_json FROM review_preparations
                WHERE check_run_id=? AND state='prepared'
                """,
                (check_id,),
            ).fetchall()
            failure_rows = self.store.db.execute(
                """
                SELECT payload_json FROM failure_preparations
                WHERE check_run_id=? AND state='prepared'
                """,
                (check_id,),
            ).fetchall()
            prepared_conclusions = {
                json.loads(row["receipt_template_json"])[
                    "checkPublication"
                ]["conclusion"]
                for row in review_rows
            } | {
                json.loads(row["payload_json"])[
                    "checkPublication"
                ]["conclusion"]
                for row in failure_rows
            }
            self.terminal_patch_evidence.append(
                data.get("conclusion") in prepared_conclusions
            )
        if (
            method == "PATCH"
            and "/check-runs/" in path
            and isinstance(data, dict)
            and data.get("conclusion") == "success"
        ):
            prepared = self.store.db.execute(
                """
                SELECT COUNT(*) FROM review_preparations
                WHERE state='prepared'
                """
            ).fetchone()[0]
            finalized = self.store.db.execute(
                "SELECT COUNT(*) FROM reviews_v3"
            ).fetchone()[0]
            self.success_saw_preparation = prepared == 1 and finalized == 0
        return super().request_json(method, path, token, data, limit)


class LostSuccessResponseGitHub(EvidenceOrderGitHub):
    def __init__(self, store: broker.BrokerStore) -> None:
        super().__init__(store)
        self.lose_success_response = True

    def request_json(
        self,
        method: str,
        path: str,
        token: str,
        data: dict[str, Any] | None = None,
        limit: int = 4 * 1024 * 1024,
    ) -> Any:
        value = super().request_json(method, path, token, data, limit)
        if (
            self.lose_success_response
            and method == "PATCH"
            and "/check-runs/" in path
            and isinstance(data, dict)
            and data.get("conclusion") == "success"
        ):
            self.lose_success_response = False
            raise broker.BrokerError(
                "UNAVAILABLE", "synthetic lost GitHub success response"
            )
        return value


class LostFailureResponseGitHub(EvidenceOrderGitHub):
    def __init__(self, store: broker.BrokerStore) -> None:
        super().__init__(store)
        self.lose_failure_response = True

    def request_json(
        self,
        method: str,
        path: str,
        token: str,
        data: dict[str, Any] | None = None,
        limit: int = 4 * 1024 * 1024,
    ) -> Any:
        value = super().request_json(method, path, token, data, limit)
        if (
            self.lose_failure_response
            and method == "PATCH"
            and "/check-runs/" in path
            and isinstance(data, dict)
            and data.get("conclusion") == "failure"
        ):
            self.lose_failure_response = False
            raise broker.BrokerError(
                "UNAVAILABLE", "synthetic lost GitHub failure response"
            )
        return value


class FakeReviewer:
    def __init__(
        self,
        verdict: dict[str, Any] | None = None,
        failure: str | None = None,
    ) -> None:
        self.failure = failure
        self.calls = 0
        self.verdict = verdict or {
            "verdict": "PASSED",
            "findings": [],
            "unverified": [],
        }

    def planned_provider_calls(
        self,
        candidate: broker.Candidate,
        reviewer_id: str,
        policy: dict[str, Any],
    ) -> int:
        del candidate, reviewer_id, policy
        return 1

    def reservation_microusd(
        self,
        candidate: broker.Candidate,
        reviewer_id: str,
        policy: dict[str, Any],
    ) -> int:
        del candidate, reviewer_id
        return int(policy["budget"]["reservationMicrousd"])

    def review(
        self,
        candidate: broker.Candidate,
        reviewer_id: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        del policy
        self.calls += 1
        check(reviewer_id == "openai-responses-terra", "Sol routes to Terra")
        check("THIS FIELD" not in candidate.review_diff, "patch field ignored")
        if self.failure:
            raise broker.BrokerError(self.failure, "synthetic provider outage")
        request = broker.canonical_json(
            {
                "candidateManifest": candidate.manifest,
                "reviewDiff": candidate.review_diff,
            }
        )
        return {
            "provider": {
                "id": reviewer_id,
                "model": "gpt-5.6-terra",
            },
            "providerRequest": request,
            "sanitizedPrompt": request.decode("utf-8"),
            "verdict": copy.deepcopy(self.verdict),
            "usage": {"inputTokens": 1000, "outputTokens": 100},
            "session": "resp-fixture",
            "latencyMs": 1,
        }


def running_store() -> tuple[broker.BrokerStore, int]:
    store = broker.BrokerStore(
        ":memory:",
        provenance_keyring={"maker-key": key_record()},
    )
    store.enroll(enrollment_receipt())
    coord = coordinates()
    check(
        store.record_delivery_candidate(
            "delivery-0001",
            "pull_request",
            "synchronize",
            "d" * 64,
            coord,
        ),
        "signed webhook candidate inserted",
    )
    check(
        store.put_provenance_and_queue(signed_provenance(), coord),
        "verified provenance queues exact candidate",
    )
    claimed = store.claim()
    check(claimed is not None, "candidate claimed")
    return store, int(claimed[0])


def candidate_phase() -> None:
    policy = broker.load_policy()
    github = FakeGitHub()
    provenance_sha = broker.sha256_bytes(
        broker.canonical_json(signed_provenance())
    )
    candidate = broker.build_candidate(
        github,
        "installation-token",
        coordinates(),
        policy,
        check_sha=CHECK_SHA,
        provenance_receipt_sha256=provenance_sha,
    )
    check(candidate.manifest["pagination"]["complete"] is True, "complete compare")
    check(candidate.manifest["pagination"]["pageCount"] == 1, "page count bound")
    check(candidate.manifest["files"]["app.py"]["baseBlobSha"] == github.old_sha, "base blob")
    check(candidate.manifest["files"]["app.py"]["headBlobSha"] == github.new_sha, "head blob")
    check(candidate.redaction_manifest["redactions"] == [], "clean redaction manifest")
    check('print("old")' in candidate.review_diff, "full base content diffed")
    check('print("new")' in candidate.review_diff, "full head content diffed")
    check("THIS FIELD" not in candidate.review_diff, "GitHub patch ignored")
    broker.validate_runtime_record("candidateManifest", candidate.manifest)

    github.merge_base_sha = "e" * 40
    behind_base = broker.build_candidate(
        github,
        "installation-token",
        coordinates(),
        policy,
        check_sha=CHECK_SHA,
        provenance_receipt_sha256=provenance_sha,
    )
    check(
        behind_base.manifest["baseSha"] == BASE,
        "valid PR merge base may precede the current base commit",
    )

    github.compare_head = "e" * 40
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            github,
            "installation-token",
            coordinates(),
            policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "incomplete comparison rejected",
    )
    github = FakeGitHub()
    github.file_row["sha"] = "e" * 40
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            github,
            "installation-token",
            coordinates(),
            policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "compare/blob mismatch rejected",
    )
    github = FakeGitHub()
    credential_name = "OPENAI" + "_API_KEY"
    synthetic_value = "sk-" + "proj-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
    github.new = f'{credential_name}="{synthetic_value}"\n'.encode("ascii")
    github.new_sha = broker._git_blob_sha(github.new)
    github.file_row["sha"] = github.new_sha
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            github,
            "installation-token",
            coordinates(),
            policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "redaction blocks provider candidate",
    )
    github = FakeGitHub()
    github.new = b"\x00binary"
    github.new_sha = broker._git_blob_sha(github.new)
    github.file_row["sha"] = github.new_sha
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            github,
            "installation-token",
            coordinates(),
            policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "binary blob rejected",
    )

    class TransparentGzipGitHub(FakeGitHub):
        def request_json(
            self,
            method: str,
            path: str,
            token: str,
            data: dict[str, Any] | None = None,
            limit: int = 4 * 1024 * 1024,
        ) -> Any:
            if method == "GET" and "/contents/" in path:
                check(
                    token == "installation-token",
                    "transparent container uses repository-scoped token",
                )
                self.calls.append((method, path, copy.deepcopy(data)))
                return {
                    "type": "file",
                    "sha": self.new_sha,
                    "size": len(self.new),
                }
            return super().request_json(
                method, path, token, data=data, limit=limit
            )

    transparent = TransparentGzipGitHub()
    transparent.file_row = {
        "filename": "evidence/transcript.jsonl.gz",
        "status": "added",
        "sha": "",
    }
    transparent_jsonl = (
        b'{"event":"started","ok":true}\n'
        b'{"event":"completed","ok":true}\n'
    )
    transparent.new = gzip.compress(transparent_jsonl, mtime=0)
    transparent.new_sha = broker._git_blob_sha(transparent.new)
    transparent.file_row["sha"] = transparent.new_sha
    transparent_candidate = broker.build_candidate(
        transparent,
        "installation-token",
        coordinates(),
        policy,
        check_sha=CHECK_SHA,
        provenance_receipt_sha256=provenance_sha,
    )
    transparent_record = transparent_candidate.manifest["files"][
        "evidence/transcript.jsonl.gz"
    ]
    check(
        transparent_record["baseReview"] is None
        and transparent_record["headReview"]
        == {
            "encoding": "gzip-jsonl-utf8-v1",
            "sha256": broker.sha256_bytes(transparent_jsonl),
            "bytes": len(transparent_jsonl),
        }
        and transparent_candidate.manifest["totalReviewBytes"]
        == len(transparent_jsonl)
        and "".join(
            f"+{line}\n"
            for line in transparent_jsonl.decode("utf-8").splitlines()
        )
        in "".join(
            unit.review_diff
            for unit in transparent_candidate.review_units
        ),
        "bounded transparent JSONL gzip is reviewable and hash-bound",
    )

    class MixedTransparentGitHub(FakeGitHub):
        def __init__(self) -> None:
            super().__init__()
            self.logical = b'{"event":"mixed","ok":true}\n'
            self.container = gzip.compress(self.logical, mtime=0)
            self.container_sha = broker._git_blob_sha(self.container)
            self.file_rows = [
                copy.deepcopy(self.file_row),
                {
                    "filename": "evidence/transcript.jsonl.gz",
                    "status": "added",
                    "sha": self.container_sha,
                },
            ]
            self.blobs = {
                self.old_sha: self.old,
                self.new_sha: self.new,
                self.container_sha: self.container,
            }

        def request_json(
            self,
            method: str,
            path: str,
            token: str,
            data: dict[str, Any] | None = None,
            limit: int = 4 * 1024 * 1024,
        ) -> Any:
            if method == "GET" and "/compare/" in path:
                return {
                    "base_commit": {"sha": BASE},
                    "merge_base_commit": {"sha": self.merge_base_sha},
                    "ahead_by": 1,
                    "commits": [{"sha": self.compare_head}],
                    "files": copy.deepcopy(self.file_rows),
                }
            if method == "GET" and "/contents/" in path:
                encoded_path = path.split("/contents/", 1)[1].split("?", 1)[0]
                candidate_path = urllib.parse.unquote(encoded_path)
                ref = urllib.parse.parse_qs(
                    urllib.parse.urlsplit(path).query
                )["ref"][0]
                if candidate_path == "app.py":
                    raw = self.old if ref == BASE else self.new
                else:
                    raw = self.container
                return {
                    "type": "file",
                    "sha": broker._git_blob_sha(raw),
                    "size": len(raw),
                }
            if method == "GET" and "/git/blobs/" in path:
                sha = path.rsplit("/", 1)[1]
                raw = self.blobs[sha]
                return {
                    "sha": sha,
                    "size": len(raw),
                    "encoding": "base64",
                    "content": base64.b64encode(raw).decode("ascii"),
                }
            return super().request_json(
                method, path, token, data=data, limit=limit
            )

    mixed = MixedTransparentGitHub()
    mixed_candidate = broker.build_candidate(
        mixed,
        "installation-token",
        coordinates(),
        policy,
        check_sha=CHECK_SHA,
        provenance_receipt_sha256=provenance_sha,
    )
    check(
        mixed_candidate.manifest["totalReviewBytes"]
        == len(mixed.old) + len(mixed.new) + len(mixed.logical),
        "mixed candidate review bound includes raw text and logical gzip bytes",
    )

    def reject_transparent(raw: bytes, label: str) -> None:
        rejected = TransparentGzipGitHub()
        rejected.file_row = {
            "filename": "evidence/transcript.jsonl.gz",
            "status": "added",
            "sha": "",
        }
        rejected.new = raw
        rejected.new_sha = broker._git_blob_sha(raw)
        rejected.file_row["sha"] = rejected.new_sha
        expect_error(
            "UNVERIFIED",
            lambda: broker.build_candidate(
                rejected,
                "installation-token",
                coordinates(),
                policy,
                check_sha=CHECK_SHA,
                provenance_receipt_sha256=provenance_sha,
            ),
            label,
        )

    reject_transparent(b"not-gzip", "invalid transparent gzip rejected")
    reject_transparent(
        gzip.compress(b'{"member":1}\n', mtime=0)
        + gzip.compress(b'{"member":2}\n', mtime=0),
        "multiple transparent gzip members rejected",
    )
    logical_limit = int(policy["candidate"]["maxDecodedBlobBytes"])
    reject_transparent(
        gzip.compress(
            b'{"payload":"'
            + (b"x" * logical_limit)
            + b'"}\n',
            mtime=0,
        ),
        "transparent gzip expansion overflow rejected",
    )
    reject_transparent(
        gzip.compress(b'{"event":"bad-utf8","value":"\xff"}\n', mtime=0),
        "non-UTF-8 transparent JSONL rejected",
    )
    reject_transparent(
        gzip.compress(b'{"event":}\n', mtime=0),
        "invalid transparent JSONL rejected",
    )
    reject_transparent(
        gzip.compress(
            (
                '{"'
                + credential_name
                + '":"'
                + synthetic_value
                + '"}\n'
            ).encode("ascii"),
            mtime=0,
        ),
        "secret-bearing transparent JSONL rejected",
    )
    undeclared = TransparentGzipGitHub()
    undeclared.file_row = {
        "filename": "evidence/transcript.gz",
        "status": "added",
        "sha": "",
    }
    undeclared.new = gzip.compress(transparent_jsonl, mtime=0)
    undeclared.new_sha = broker._git_blob_sha(undeclared.new)
    undeclared.file_row["sha"] = undeclared.new_sha
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            undeclared,
            "installation-token",
            coordinates(),
            policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "undeclared gzip binary remains rejected",
    )

    github = FakeGitHub()
    github.new = "".join(
        f"value_{index:05d} = {index}\n" for index in range(7000)
    ).encode("utf-8")
    github.new_sha = broker._git_blob_sha(github.new)
    github.file_row["sha"] = github.new_sha
    hierarchical = broker.build_candidate(
        github,
        "installation-token",
        coordinates(),
        policy,
        check_sha=CHECK_SHA,
        provenance_receipt_sha256=provenance_sha,
    )
    plan = broker.decode_strict_json(
        hierarchical.review_diff.encode("utf-8"),
        "hierarchical review plan fixture",
    )
    reconstructed = "".join(
        unit.review_diff for unit in hierarchical.review_units
    )
    check(
        len(hierarchical.review_units) > 1
        and plan["mode"] == "hierarchical"
        and plan["unitCount"] == len(hierarchical.review_units),
        "oversized clean diff becomes a bounded hierarchical plan",
    )
    check(
        broker.sha256_bytes(reconstructed.encode("utf-8"))
        == plan["fullDiffSha256"]
        and len(reconstructed.encode("utf-8"))
        == plan["fullDiffBytes"],
        "hierarchical units reconstruct the complete canonical diff",
    )
    check(
        all(
            broker.sha256_bytes(unit.review_diff.encode("utf-8"))
            == unit.manifest["reviewDiffSha256"]
            and len(unit.review_diff.encode("utf-8"))
            == unit.manifest["reviewDiffBytes"]
            <= policy["candidate"]["maxRawDiffBytes"]
            for unit in hierarchical.review_units
        ),
        "every hierarchical unit is exact and within the single-call bound",
    )
    check(
        hierarchical.manifest["reviewDiffSha256"]
        == broker.sha256_bytes(hierarchical.review_diff.encode("utf-8")),
        "candidate manifest binds the hierarchical review plan",
    )
    broker.validate_runtime_record(
        "candidateManifest", hierarchical.manifest
    )

    first_complete_file = "a" * 60000 + "\n"
    second_complete_file = "b" * 30000 + "\n"
    complete_plan, complete_units = broker._review_units(
        first_complete_file + second_complete_file,
        [
            ("first.txt", first_complete_file),
            ("second.txt", second_complete_file),
        ],
        policy,
    )
    decoded_complete_plan = broker.decode_strict_json(
        complete_plan.encode("utf-8"),
        "complete-file-first plan fixture",
    )
    check(
        len(complete_units) == 2
        and complete_units[0].manifest["paths"] == ["first.txt"]
        and complete_units[1].manifest["paths"] == ["second.txt"]
        and decoded_complete_plan["units"][1]["paths"] == ["second.txt"],
        "a file that fits an empty unit is never split by prior-unit fill",
    )

    too_large = FakeGitHub()
    too_large.new = b"bounded_line = 1\n" * 6000
    too_large.new_sha = broker._git_blob_sha(too_large.new)
    too_large.file_row["sha"] = too_large.new_sha
    too_large_policy = copy.deepcopy(policy)
    too_large_policy["candidate"]["maxHierarchicalRawDiffBytes"] = 90000
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            too_large,
            "installation-token",
            coordinates(),
            too_large_policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "diff beyond the hierarchical bound is rejected without truncation",
    )

    hidden_secret = FakeGitHub()
    hidden_secret.new = github.new + (
        b'OPENAI_API_KEY="sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"\n'
    )
    hidden_secret.new_sha = broker._git_blob_sha(hidden_secret.new)
    hidden_secret.file_row["sha"] = hidden_secret.new_sha
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            hidden_secret,
            "installation-token",
            coordinates(),
            policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "secret in a later hierarchical unit blocks every provider call",
    )

    unsplittable = FakeGitHub()
    unsplittable.new = b"x" * 90000 + b"\n"
    unsplittable.new_sha = broker._git_blob_sha(unsplittable.new)
    unsplittable.file_row["sha"] = unsplittable.new_sha
    expect_error(
        "UNVERIFIED",
        lambda: broker.build_candidate(
            unsplittable,
            "installation-token",
            coordinates(),
            policy,
            check_sha=CHECK_SHA,
            provenance_receipt_sha256=provenance_sha,
        ),
        "a single over-bound diff line is never sliced or truncated",
    )


class StaticResponse:
    def __init__(self, value: dict[str, Any]) -> None:
        self.raw = broker.canonical_json(value)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, limit: int) -> bytes:
        return self.raw[:limit]


def adapter_phase() -> None:
    github = FakeGitHub()
    policy = broker.load_policy()
    provenance_sha = broker.sha256_bytes(
        broker.canonical_json(signed_provenance())
    )
    candidate = broker.build_candidate(
        github,
        "installation-token",
        coordinates(),
        policy,
        check_sha=CHECK_SHA,
        provenance_receipt_sha256=provenance_sha,
    )
    response = {
        "id": "resp-fixture",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"findings":[],"unverified":[],"verdict":"PASSED"}',
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 2000, "output_tokens": 100},
    }
    captured: dict[str, Any] = {}

    def opener(request, timeout: int):
        captured["request"] = request
        captured["timeout"] = timeout
        return StaticResponse(response)

    adapter = broker.ReviewerAdapter("x" * 30, opener=opener)
    result = adapter.review(
        candidate, "openai-responses-terra", policy
    )
    sent = broker.decode_strict_json(
        result["providerRequest"], "captured provider request"
    )
    check(sent["model"] == "gpt-5.6-terra", "exact Terra model selected")
    check(sent["store"] is False, "provider storage disabled")
    check(sent["max_output_tokens"] > 0, "budget-derived output cap")
    check(
        len(result["providerRequest"])
        <= policy["candidate"]["maxProviderRequestBytes"],
        "provider request bound",
    )
    check(result["usage"] == {"inputTokens": 2000, "outputTokens": 100}, "primary usage")
    check(captured["timeout"] == 120, "bounded provider timeout")
    bad = copy.deepcopy(response)
    bad["usage"] = {"input_tokens": 1}
    adapter_bad = broker.ReviewerAdapter(
        "x" * 30, opener=lambda *_args, **_kwargs: StaticResponse(bad)
    )
    expect_error(
        "UNVERIFIED",
        lambda: adapter_bad.review(
            candidate, "openai-responses-terra", policy
        ),
        "missing primary usage rejected",
    )

    large_github = FakeGitHub()
    large_github.new = "".join(
        f"value_{index:05d} = {index}\n" for index in range(7000)
    ).encode("utf-8")
    large_github.new_sha = broker._git_blob_sha(large_github.new)
    large_github.file_row["sha"] = large_github.new_sha
    large_candidate = broker.build_candidate(
        large_github,
        "installation-token",
        coordinates(),
        policy,
        check_sha=CHECK_SHA,
        provenance_receipt_sha256=provenance_sha,
    )
    hierarchical_calls: list[str] = []

    def hierarchical_opener(request, timeout: int):
        check(timeout == 120, "hierarchical provider timeout bounded")
        body = broker.decode_strict_json(
            request.data, "hierarchical request fixture"
        )
        name = body["text"]["format"]["name"]
        hierarchical_calls.append(name)
        if name == "itd_hierarchical_unit_review":
            unit_prompt = body["input"][1]["content"]
            check(
                "are not an unverified contour merely because they are "
                "absent from this unit" in unit_prompt
                and "Put cross-unit dependencies in the summary" in unit_prompt,
                "unit prompt reserves unverified for an incomplete current unit",
            )
            check(
                "PASSED_WITH_WARNINGS requires an important finding or "
                "unverified contour" in unit_prompt
                and "PASSED permits only minor findings" in unit_prompt,
                "unit prompt states canonical verdict semantics",
            )
        else:
            integration_prompt = body["input"][1]["content"]
            check(
                "Candidate success requires complete unit coverage and a "
                "PASSED verdict with no finding or unverified contour"
                in integration_prompt
                and "PASSED permits only minor findings" in integration_prompt,
                "integration prompt separates verdict validity from success",
            )
        verdict_value = (
            {
                "verdict": "PASSED",
                "findings": [],
                "unverified": [],
                "summary": (
                    "This unit changes generated value assignments; no "
                    "cross-unit interface or dependency risk was found."
                ),
            }
            if name == "itd_hierarchical_unit_review"
            else {
                "verdict": "PASSED",
                "findings": [],
                "unverified": [],
            }
        )
        return StaticResponse(
            {
                "id": f"resp-hierarchical-{len(hierarchical_calls)}",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(verdict_value),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 10},
            }
        )

    hierarchical_adapter = broker.ReviewerAdapter(
        "x" * 30, opener=hierarchical_opener
    )
    hierarchical_result = hierarchical_adapter.review(
        large_candidate, "openai-responses-terra", policy
    )
    request_bundle = broker.decode_strict_json(
        hierarchical_result["providerRequest"],
        "hierarchical provider evidence fixture",
    )
    expected_calls = len(large_candidate.review_units) + 1
    check(
        request_bundle["plannedCalls"] == expected_calls
        and len(request_bundle["requests"]) == expected_calls
        and request_bundle["requests"][-1]["kind"] == "integration",
        "hierarchical evidence covers every unit and integration call",
    )
    check(
        hierarchical_calls
        == [
            *(
                "itd_hierarchical_unit_review"
                for _ in large_candidate.review_units
            ),
            "itd_external_review",
        ],
        "integration runs only after every unit review",
    )
    check(
        hierarchical_result["usage"]
        == {
            "inputTokens": 100 * expected_calls,
            "outputTokens": 10 * expected_calls,
        }
        and hierarchical_result["verdict"]
        == {"verdict": "PASSED", "findings": [], "unverified": []},
        "hierarchical usage and final verdict are complete aggregates",
    )
    check(
        hierarchical_adapter.reservation_microusd(
            large_candidate, "openai-responses-terra", policy
        )
        == expected_calls * 500000,
        "hierarchical reservation is bound to planned Terra calls",
    )

    finding_calls = 0

    def finding_opener(_request, **_kwargs):
        nonlocal finding_calls
        finding_calls += 1
        return StaticResponse(
            {
                "id": "resp-unit-finding",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "verdict": "PASSED_WITH_WARNINGS",
                                        "findings": [
                                            {
                                                "severity": "important",
                                                "confidence": "high",
                                                "category": "correctness",
                                                "file": "app.py",
                                                "line": 1,
                                                "summary":
                                                    "synthetic unit finding",
                                            }
                                        ],
                                        "unverified": [],
                                        "summary":
                                            "The first unit has a blocking issue.",
                                    }
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 10},
            }
        )

    finding_adapter = broker.ReviewerAdapter(
        "x" * 30, opener=finding_opener
    )
    finding_result = finding_adapter.review(
        large_candidate, "openai-responses-terra", policy
    )
    finding_bundle = broker.decode_strict_json(
        finding_result["providerRequest"],
        "hierarchical finding evidence fixture",
    )
    check(
        finding_calls == 1
        and len(finding_bundle["requests"]) == 1
        and finding_result["verdict"]["findings"],
        "first blocking unit stops paid calls without claiming full coverage",
    )


def process_phase() -> None:
    orphan_store, orphan_job = running_store()
    reconciliation = orphan_store.reconcile_interrupted_jobs()
    check(
        reconciliation == {
            "requeued": 1,
            "completed": 0,
            "failed": 0,
            "pending": 0,
        },
        "startup requeues running job without publication evidence",
    )
    reclaimed = orphan_store.claim()
    check(
        reclaimed is not None and reclaimed[0] == orphan_job,
        "requeued interrupted job is claimable",
    )
    orphan_store.close()

    store, job_id = running_store()
    github = EvidenceOrderGitHub(store)
    reviewer = FakeReviewer()
    runtime = broker.ReviewBroker(
        broker.load_policy(), store, github, FakeAuth(), reviewer
    )
    result = runtime.process(coordinates())
    check(result["status"] == "PASSED", "clean end-to-end review passes")
    check(result["conclusion"] == "success", "success conclusion")
    check(result["receiptId"] is not None, "durable broker receipt returned")
    publication = github.checks[result["checkRunId"]]
    check(publication["headSha"] == CHECK_SHA, "check bound to test merge SHA")
    check(publication["appIntegrationId"] == APP_ID, "App-owned check observed")
    review = store.db.execute("SELECT * FROM reviews_v3").fetchone()
    check(review is not None, "closed review evidence persisted")
    check(review["check_run_external_id"] == publication["externalId"], "external id cross-bound")
    check("sk-proj-" not in review["sanitized_prompt"], "no secret persisted")
    check(
        github.success_saw_preparation,
        "success PATCH observes durable preparation before publication",
    )
    check(
        github.terminal_patch_evidence == [True],
        "every successful terminal PATCH has exact prior evidence",
    )
    preparation = store.db.execute(
        "SELECT state FROM review_preparations"
    ).fetchone()
    check(
        preparation is not None and preparation["state"] == "finalized",
        "pre-publication evidence atomically finalizes",
    )
    store.finish_job(job_id, True, result)
    store.close()

    hierarchical_store, hierarchical_job = running_store()
    hierarchical_github = EvidenceOrderGitHub(hierarchical_store)
    hierarchical_github.new = "".join(
        f"value_{index:05d} = {index}\n" for index in range(7000)
    ).encode("utf-8")
    hierarchical_github.new_sha = broker._git_blob_sha(
        hierarchical_github.new
    )
    hierarchical_github.file_row["sha"] = hierarchical_github.new_sha
    hierarchical_api_calls = 0

    def passing_hierarchical_opener(request, timeout: int):
        nonlocal hierarchical_api_calls
        hierarchical_api_calls += 1
        check(timeout == 120, "end-to-end hierarchical timeout bounded")
        body = broker.decode_strict_json(
            request.data, "end-to-end hierarchical request"
        )
        unit = (
            body["text"]["format"]["name"]
            == "itd_hierarchical_unit_review"
        )
        verdict = {
            "verdict": "PASSED",
            "findings": [],
            "unverified": [],
        }
        if unit:
            verdict["summary"] = (
                "This unit changes generated assignments and exposes no "
                "cross-unit interface or dependency risk."
            )
        return StaticResponse(
            {
                "id": f"resp-e2e-hier-{hierarchical_api_calls}",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(verdict),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 10},
            }
        )

    hierarchical_runtime = broker.ReviewBroker(
        broker.load_policy(),
        hierarchical_store,
        hierarchical_github,
        FakeAuth(),
        broker.ReviewerAdapter(
            "x" * 30, opener=passing_hierarchical_opener
        ),
    )
    hierarchical_result = hierarchical_runtime.process(coordinates())
    check(
        hierarchical_result["status"] == "PASSED"
        and hierarchical_result["conclusion"] == "success",
        "hierarchical exact-candidate review passes end to end",
    )
    hierarchical_reservation = hierarchical_store.db.execute(
        """
        SELECT amount_microusd,status,usage_json
        FROM reservations_v2
        """
    ).fetchone()
    check(
        hierarchical_reservation is not None
        and hierarchical_reservation["status"] == "settled"
        and hierarchical_reservation["amount_microusd"]
        == hierarchical_api_calls * 500000,
        "hierarchical budget reservation binds the planned Terra call count",
    )
    hierarchical_preparation = hierarchical_store.db.execute(
        """
        SELECT provider_request_sha256,provider_request_bytes,state
        FROM review_preparations
        """
    ).fetchone()
    check(
        hierarchical_preparation is not None
        and hierarchical_preparation["state"] == "finalized"
        and hierarchical_preparation["provider_request_bytes"] > 0,
        "hierarchical provider evidence is durable before success",
    )
    hierarchical_store.finish_job(
        hierarchical_job, True, hierarchical_result
    )
    hierarchical_store.close()

    class SwappedPromptAdapter(broker.ReviewerAdapter):
        def review(self, candidate, reviewer_id, broker_policy):
            result = super().review(
                candidate, reviewer_id, broker_policy
            )
            evidence = broker.decode_strict_json(
                result["sanitizedPrompt"].encode("utf-8"),
                "swapped hierarchical prompt fixture",
            )
            evidence["prompts"][0], evidence["prompts"][1] = (
                evidence["prompts"][1],
                evidence["prompts"][0],
            )
            result["sanitizedPrompt"] = broker.canonical_json(
                evidence
            ).decode("utf-8")
            return result

    swapped_store, _ = running_store()
    swapped_github = EvidenceOrderGitHub(swapped_store)
    swapped_github.new = "".join(
        f"value_{index:05d} = {index}\n" for index in range(7000)
    ).encode("utf-8")
    swapped_github.new_sha = broker._git_blob_sha(swapped_github.new)
    swapped_github.file_row["sha"] = swapped_github.new_sha
    swapped_result = broker.ReviewBroker(
        broker.load_policy(),
        swapped_store,
        swapped_github,
        FakeAuth(),
        SwappedPromptAdapter(
            "x" * 30, opener=passing_hierarchical_opener
        ),
    ).process(coordinates())
    check(
        swapped_result["status"] == "UNVERIFIED"
        and swapped_result["conclusion"] == "action_required",
        "swapped unit prompts cannot satisfy durable provider evidence",
    )
    swapped_store.close()

    outage_store, _ = running_store()
    outage_github = EvidenceOrderGitHub(outage_store)
    outage_github.new = "".join(
        f"value_{index:05d} = {index}\n" for index in range(7000)
    ).encode("utf-8")
    outage_github.new_sha = broker._git_blob_sha(outage_github.new)
    outage_github.file_row["sha"] = outage_github.new_sha
    outage_calls = 0

    def partial_outage_opener(_request, **_kwargs):
        nonlocal outage_calls
        outage_calls += 1
        if outage_calls == 2:
            raise OSError("synthetic hierarchical outage")
        return StaticResponse(
            {
                "id": "resp-before-outage",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "verdict": "PASSED",
                                        "findings": [],
                                        "unverified": [],
                                        "summary":
                                            "First unit completed cleanly.",
                                    }
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 10},
            }
        )

    outage_result = broker.ReviewBroker(
        broker.load_policy(),
        outage_store,
        outage_github,
        FakeAuth(),
        broker.ReviewerAdapter(
            "x" * 30, opener=partial_outage_opener
        ),
    ).process(coordinates())
    check(
        outage_result["status"] == "UNAVAILABLE"
        and outage_result["conclusion"] == "failure",
        "hierarchical API outage blocks merge",
    )
    uncertain = outage_store.db.execute(
        """
        SELECT amount_microusd,status,observed_microusd,usage_json
        FROM reservations_v2
        """
    ).fetchone()
    check(
        uncertain is not None
        and uncertain["status"] == "uncertain"
        and uncertain["amount_microusd"] > uncertain["observed_microusd"]
        and uncertain["observed_microusd"] == 500400,
        "partial outage charges observed usage plus one ambiguous call cap",
    )
    check(
        outage_store.budget_status()["reservedMicrousd"] == 0,
        "hierarchical outage releases the unused reservation remainder",
    )
    outage_store.close()

    recovery_store, recovery_job = running_store()
    recovery_github = LostSuccessResponseGitHub(recovery_store)
    recovery_reviewer = FakeReviewer()
    recovery_runtime = broker.ReviewBroker(
        broker.load_policy(),
        recovery_store,
        recovery_github,
        FakeAuth(),
        recovery_reviewer,
    )
    interrupted = recovery_runtime.process(coordinates())
    check(
        interrupted["status"] == "UNAVAILABLE",
        "ambiguous success publication remains recovery-pending",
    )
    check(
        recovery_github.success_saw_preparation,
        "ambiguous success still has prior durable preparation",
    )
    check(
        recovery_store.db.execute(
            """
            SELECT state FROM review_preparations
            """
        ).fetchone()["state"]
        == "prepared",
        "lost success response preserves recovery record",
    )
    check(
        recovery_store.reconcile_interrupted_jobs()["pending"] == 1,
        "startup preserves job with durable pending publication",
    )
    check(
        recovery_runtime.recover_pending_publications() == 1,
        "recovery observes and finalizes already-published success",
    )
    check(
        recovery_reviewer.calls == 1,
        "publication recovery never repeats provider review",
    )
    recovered_job = recovery_store.db.execute(
        "SELECT status FROM jobs WHERE job_id=?", (recovery_job,)
    ).fetchone()
    check(
        recovered_job["status"] == "completed",
        "recovery completes interrupted job",
    )
    check(
        recovery_store.db.execute(
            "SELECT COUNT(*) FROM reviews_v3"
        ).fetchone()[0]
        == 1,
        "recovery creates the observed final receipt",
    )
    recovery_store.close()

    store, _ = running_store()
    pending_github = PendingOnceGitHub()
    sleeps: list[float] = []
    pending = broker.ReviewBroker(
        broker.load_policy(),
        store,
        pending_github,
        FakeAuth(),
        FakeReviewer(),
        sleeper=sleeps.append,
    ).process(coordinates())
    check(pending["status"] == "PASSED", "transient mergeability is retried")
    check(
        pending_github.pull_reads >= 3 and sleeps == [1.0],
        "mergeability retry is bounded and revalidated",
    )
    store.close()

    merge_store = broker.BrokerStore(
        ":memory:",
        provenance_keyring={"maker-key": key_record()},
    )
    merge_store.enroll(enrollment_receipt())
    component = coordinates()
    merge_store.record_delivery_candidate(
        "delivery-component",
        "pull_request",
        "synchronize",
        "1" * 64,
        component,
    )
    merge_store.put_provenance_and_queue(
        signed_provenance(), component
    )
    component_job = merge_store.claim()
    check(component_job is not None, "merge component job exists")
    merge_store.finish_job(
        component_job[0], False, {"status": "superseded-by-merge-fixture"}
    )
    merge_coordinates = broker.Coordinates(
        REPOSITORY, 0, MERGE_HEAD, BASE, INSTALLATION_ID
    ).validate()
    def merge_pull_row(number: int) -> dict[str, Any]:
        return {
            "number": number,
            "state": "open",
            "head": {
                "sha": HEAD,
                "repo": {"full_name": REPOSITORY},
            },
            "base": {
                "sha": BASE,
                "repo": {"full_name": REPOSITORY},
            },
        }

    paged_github = FakeGitHub()
    first_page = [merge_pull_row(number) for number in range(1, 101)]
    paged_github.merge_pull_pages = {1: first_page, 2: []}
    paged_runtime = broker.ReviewBroker(
        broker.load_policy(),
        merge_store,
        paged_github,
        FakeAuth(),
        FakeReviewer(),
    )
    paged_components = paged_runtime._merge_components(
        merge_coordinates, "installation-token"
    )
    check(
        len(paged_components) == 100,
        "full merge-group page requires and accepts empty terminator page",
    )
    check(
        len(
            [
                path
                for method, path, _data in paged_github.calls
                if method == "GET" and "/pulls?" in path
            ]
        )
        == 2,
        "merge-group composition traverses explicit pagination",
    )
    paged_github.merge_pull_pages = {
        1: first_page,
        2: [merge_pull_row(101)],
    }
    expect_error(
        "UNVERIFIED",
        lambda: paged_runtime._merge_components(
            merge_coordinates, "installation-token"
        ),
        "merge-group component beyond bound is never silently omitted",
    )

    merge_store.record_delivery_candidate(
        "delivery-merge",
        "merge_group",
        "checks_requested",
        "2" * 64,
        merge_coordinates,
    )
    merge_github = FakeGitHub()
    merge_github.compare_head = MERGE_HEAD
    merge_runtime = broker.ReviewBroker(
        broker.load_policy(),
        merge_store,
        merge_github,
        FakeAuth(),
        FakeReviewer(),
    )
    check(
        merge_runtime.prepare_merge_group(merge_coordinates),
        "merge group queues only after live component provenance",
    )
    merge_job = merge_store.claim()
    check(
        merge_job is not None and merge_job[1] == merge_coordinates,
        "exact merge-group job claimed",
    )
    merge_result = merge_runtime.process(merge_coordinates)
    check(merge_result["status"] == "PASSED", "merge-group review passes")
    merge_row = merge_store.db.execute(
        "SELECT subject_type,pull_request FROM reviews_v3"
    ).fetchone()
    check(
        merge_row["subject_type"] == "merge_group"
        and merge_row["pull_request"] == 0,
        "merge receipt binds synthetic subject",
    )
    check(
        merge_github.checks[merge_result["checkRunId"]]["headSha"]
        == MERGE_HEAD,
        "merge check binds merge-group SHA",
    )
    merge_store.close()

    late_store = broker.BrokerStore(
        ":memory:",
        provenance_keyring={"maker-key": key_record()},
    )
    late_store.enroll(enrollment_receipt())
    late_store.record_delivery_candidate(
        "delivery-merge-late",
        "merge_group",
        "checks_requested",
        "3" * 64,
        merge_coordinates,
    )
    late_github = FakeGitHub()
    late_github.compare_head = MERGE_HEAD
    late_runtime = broker.ReviewBroker(
        broker.load_policy(),
        late_store,
        late_github,
        FakeAuth(),
        FakeReviewer(),
    )
    check(
        late_runtime.prepare_waiting_merge_groups(REPOSITORY) == 0,
        "merge group remains waiting when component provenance is absent",
    )
    late_store.record_delivery_candidate(
        "delivery-component-late",
        "pull_request",
        "synchronize",
        "4" * 64,
        component,
    )
    late_store.put_provenance_and_queue(signed_provenance(), component)
    late_component_job = late_store.claim()
    check(
        late_component_job is not None
        and late_component_job[1] == component,
        "late component provenance queues its PR",
    )
    late_store.finish_job(
        late_component_job[0], True, {"status": "component-ready"}
    )
    check(
        late_runtime.prepare_waiting_merge_groups(REPOSITORY) == 1,
        "late provenance automatically releases waiting merge group",
    )
    late_merge_job = late_store.claim()
    check(
        late_merge_job is not None
        and late_merge_job[1] == merge_coordinates,
        "released merge group is exact",
    )
    late_store.close()

    store, _ = running_store()
    github = EvidenceOrderGitHub(store)
    github.live_base = "e" * 40
    reviewer = FakeReviewer()
    stale = broker.ReviewBroker(
        broker.load_policy(), store, github, FakeAuth(), reviewer
    ).process(coordinates())
    check(stale["status"] == "UNVERIFIED", "stale live base blocks")
    check(reviewer.calls == 0, "stale coordinates never reach provider")
    check(
        github.checks[stale["checkRunId"]]["conclusion"] == "action_required",
        "stale coordinate publishes blocking check",
    )
    check(
        github.terminal_patch_evidence == [True],
        "stale-coordinate action_required has exact prior evidence",
    )
    check(
        store.db.execute(
            "SELECT state FROM failure_preparations"
        ).fetchone()["state"]
        == "finalized",
        "stale-coordinate terminal failure has durable evidence",
    )
    store.close()

    store, _ = running_store()
    github = EvidenceOrderGitHub(store)
    reviewer = FakeReviewer(failure="UNAVAILABLE")
    outage = broker.ReviewBroker(
        broker.load_policy(), store, github, FakeAuth(), reviewer
    ).process(coordinates())
    check(outage["status"] == "UNAVAILABLE", "provider outage typed")
    check(
        github.checks[outage["checkRunId"]]["conclusion"] == "failure",
        "provider outage is fail-closed",
    )
    check(
        github.terminal_patch_evidence == [True],
        "provider-outage failure has exact prior evidence",
    )
    check(
        store.db.execute(
            "SELECT state FROM failure_preparations"
        ).fetchone()["state"]
        == "finalized",
        "provider outage terminal failure has durable evidence",
    )
    budget = store.budget_status()
    check(budget["reservedMicrousd"] == 0, "outage reservation closed")
    check(budget["spentMicrousd"] == 750000, "uncertain outage charged cap")
    store.close()

    failure_store, failure_job = running_store()
    failure_github = LostFailureResponseGitHub(failure_store)
    failure_runtime = broker.ReviewBroker(
        broker.load_policy(),
        failure_store,
        failure_github,
        FakeAuth(),
        FakeReviewer(failure="UNAVAILABLE"),
    )
    expect_error(
        "UNAVAILABLE",
        lambda: failure_runtime.process(coordinates()),
        "lost terminal failure response leaves recovery work",
    )
    check(
        failure_store.db.execute(
            "SELECT state FROM failure_preparations"
        ).fetchone()["state"]
        == "prepared",
        "ambiguous failure publication keeps durable preparation",
    )
    check(
        failure_runtime.recover_pending_publications() == 1,
        "failure publication recovery observes terminal Check",
    )
    check(
        failure_store.db.execute(
            "SELECT state FROM failure_preparations"
        ).fetchone()["state"]
        == "finalized",
        "failure recovery finalizes immutable evidence",
    )
    check(
        failure_store.db.execute(
            "SELECT status FROM jobs WHERE job_id=?", (failure_job,)
        ).fetchone()["status"]
        == "failed",
        "recovered failure keeps job fail-closed",
    )
    failure_store.close()

    warning = {
        "verdict": "PASSED_WITH_WARNINGS",
        "findings": [
            {
                "severity": "important",
                "confidence": "high",
                "category": "correctness",
                "file": "app.py",
                "line": 1,
                "summary": "synthetic merge-relevant finding",
            }
        ],
        "unverified": [],
    }
    store, _ = running_store()
    github = EvidenceOrderGitHub(store)
    blocked = broker.ReviewBroker(
        broker.load_policy(),
        store,
        github,
        FakeAuth(),
        FakeReviewer(verdict=warning),
    ).process(coordinates())
    check(blocked["status"] == "BLOCKED", "important finding blocks")
    check(blocked["conclusion"] == "action_required", "blocked conclusion")
    check(blocked["receiptId"] is not None, "blocked evidence persisted")
    check(
        github.terminal_patch_evidence == [True],
        "review-blocking action_required has exact prior evidence",
    )
    store.close()

    store, _ = running_store()
    github = FakeGitHub()
    github.observed_app_id = APP_ID + 1
    forged = broker.ReviewBroker(
        broker.load_policy(), store, github, FakeAuth(), FakeReviewer()
    ).process(coordinates())
    check(forged["status"] == "UNVERIFIED", "forged publisher cannot pass")
    final = github.checks[forged["checkRunId"]]
    check(
        final["status"] == "in_progress" and final["conclusion"] is None,
        "unverifiable publisher remains non-terminal and fail-closed",
    )
    check(
        not any(
            method == "PATCH"
            and isinstance(data, dict)
            for method, _path, data in github.calls
        ),
        "preparation failure never publishes a terminal Check Run",
    )
    check(
        store.db.execute(
            "SELECT COUNT(*) FROM review_preparations"
        ).fetchone()[0]
        == 0,
        "invalid publisher creates no preparation",
    )
    check(store.db.execute("SELECT COUNT(*) FROM reviews_v3").fetchone()[0] == 0, "forged check not persisted")
    store.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=["all", "policy", "candidate", "adapter", "process"],
        default="all",
    )
    args = parser.parse_args()
    if args.phase in {"all", "policy"}:
        policy_phase()
    if args.phase in {"all", "candidate"}:
        candidate_phase()
    if args.phase in {"all", "adapter"}:
        adapter_phase()
    if args.phase in {"all", "process"}:
        process_phase()
    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
