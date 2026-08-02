#!/usr/bin/env python3
"""Mutation checks for the canonical profile-aware gates.json consumers."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(SHARED))
import itd_gate_control as gate  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = load("itd_profile_registry_cli_test", ROOT / "scripts" / "itd.py")
hook = load(
    "itd_profile_registry_hook_test", ROOT / "scripts" / "itd_pre_push.py"
)
CHECKS = 0
REPOSITORY = "owner/example"
HEAD = "a" * 40
BASE = "b" * 40


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
    except gate.GateError as exc:
        if exc.status != status:
            raise AssertionError(f"{label}: {exc.status}") from exc
    else:
        raise AssertionError(label)


def legacy(root: Path) -> dict:
    return {
        "version": 1,
        "repositories": [{
            "repository": REPOSITORY,
            "checkout": str(root),
            "brokerUrl": "https://broker.example.test",
            "appId": 424242,
            "rulesetScope": "organization",
            "rulesetId": 91,
            "machineWorkflowRepositoryId": 515151,
            "machineWorkflowSha": "1" * 40,
            "provenanceKeyId": "current",
            "provenanceKeyFile": str(root / "signing.key"),
        }],
    }


def local_profile(root: Path) -> dict:
    return {
        "version": 2,
        "repositories": [{
            "repository": REPOSITORY,
            "checkout": str(root),
            "repositoryOwnerType": "user",
            "deploymentProfile": "local-submission",
            "protectionProfile": "local-review",
            "localReviewReceiptFile": str(root / "review.json"),
            "localReviewUnitId": "GPG-001:general-review",
            "localReviewRiskTier": "high",
            "brokerUrl": None,
            "appId": None,
            "appOwner": None,
            "appOwnerType": None,
            "appVisibility": None,
            "rulesetScope": None,
            "rulesetId": None,
            "machineWorkflowRepositoryId": None,
            "machineWorkflowSha": None,
            "provenanceKeyId": None,
            "provenanceKeyFile": None,
            "enrollmentReceiptSha256": None,
        }],
    }


def result(status: str) -> dict:
    return {
        "repository": REPOSITORY,
        "status": status,
        "drift": [] if status != "UNVERIFIED" else ["local review stale"],
        "itdVersion": "1.95.0",
        "broker": None,
        "deploymentProfile": "local-submission",
        "protectionProfile": "local-review",
    }


def push_updates() -> bytes:
    return f"refs/heads/topic {HEAD} refs/heads/topic {BASE}\n".encode("utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-registry-profiles-") as raw:
        root = Path(raw).resolve()
        (root / "signing.key").write_bytes(bytes(range(32)))
        (root / "review.json").write_text("{}", encoding="utf-8")
        check(gate.validate_registry(legacy(root))["version"] == 1,
              "legacy v1 stays readable")
        profile = gate.validate_registry(local_profile(root))
        check(profile["version"] == 2, "canonical registry accepts profile v2")
        extra = json.loads(json.dumps(profile))
        extra["repositories"][0]["mergeAuthority"] = True
        rejects("UNVERIFIED", lambda: gate.validate_registry(extra),
                "v2 registry is closed schema")

        target = root / "gates.json"
        cli.save_registry(profile, target)
        check(gate.load_registry(target) == profile,
              "canonical loader round-trips v2")

        registered = root / "registered.json"
        args = cli.parser().parse_args([
            "gate", "register-profile", "--repository", REPOSITORY,
            "--checkout", str(root), "--repository-owner-type", "user",
            "--deployment-profile", "local-submission",
            "--protection-profile", "local-review",
            "--local-review-receipt-file", str(root / "review.json"),
            "--local-review-unit-id", "GPG-001:general-review",
            "--local-review-risk-tier", "high", "--registry", str(registered),
        ])
        registered_result = args.handler(args)
        check(
            registered_result["status"] == "REGISTERED"
            and gate.load_registry(registered)["version"] == 2,
            "CLI writes canonical local profile",
        )
        legacy_path = root / "legacy.json"
        cli.save_registry(legacy(root), legacy_path)
        rejects(
            "BLOCKED",
            lambda: cli.persist_profile_registry_row(
                profile["repositories"][0], legacy_path
            ),
            "v1 registry is never silently migrated",
        )

        doctor_args = SimpleNamespace(
            registry=target, all=True, repository=None
        )
        with mock.patch.object(
            cli.gate, "profile_doctor_entry", return_value=result("LOCAL_REVIEWED")
        ):
            inspected = cli.doctor(doctor_args)
        check(
            inspected["status"] == "LOCAL_REVIEWED"
            and inspected["protected"] == 0
            and inspected["total"] == 1,
            "canonical doctor reports the bounded local claim",
        )
        with mock.patch.object(
            cli.gate, "profile_doctor_entry", return_value=result("UNVERIFIED")
        ):
            stale = cli.doctor(doctor_args)
        check(stale["status"] == "UNVERIFIED", "doctor fails stale local review")

        other_root = root / "other-checkout"
        other_root.mkdir()
        rejects(
            "UNVERIFIED",
            lambda: cli.repository_entry(profile, other_root, REPOSITORY),
            "PR root cannot borrow another checkout registration",
        )

        entry = profile["repositories"][0]
        with mock.patch.object(
            hook.gate, "profile_doctor_entry", return_value=result("LOCAL_REVIEWED")
        ):
            hook.require_profile_review(profile, entry, root)
        check(True, "pre-push accepts exact local adjudication")
        with mock.patch.object(
            hook.gate, "profile_doctor_entry", return_value=result("UNVERIFIED")
        ):
            try:
                hook.require_profile_review(profile, entry, root)
            except hook.PushBlocked:
                check(True, "pre-push blocks stale local adjudication")
            else:
                check(False, "pre-push accepted stale local adjudication")

        machine = {
            "headSha": HEAD, "tree": "c" * 40, "repository": str(root),
        }
        guarded = {
            "ITD_GUARDED_PR_PUSH": "1",
            "ITD_MACHINE_RECEIPT": str(root / "machine.json"),
            "ITD_MAKER_VENDOR": "openai",
            "ITD_MAKER_MODEL": "gpt-5.6-sol",
            "ITD_MAKER_SESSION": "maker-session",
        }
        with (
            mock.patch.object(hook, "load_machine_receipt", return_value=machine),
            mock.patch.object(
                hook, "execute_fresh_machine_oracle", return_value=machine
            ),
            mock.patch.object(hook, "machine_evidence_binding", return_value=()),
            mock.patch.object(
                hook.gate, "profile_doctor_entry",
                return_value=result("LOCAL_REVIEWED"),
            ),
        ):
            hook.enforce(
                "https://github.com/owner/example.git", push_updates(),
                environment=guarded, registry=profile, root=root,
            )
        check(True, "guarded enforce consumes the local-review profile")
        with (
            mock.patch.object(hook, "load_machine_receipt", return_value=machine),
            mock.patch.object(
                hook.gate, "profile_doctor_entry", return_value=result("UNVERIFIED")
            ),
        ):
            try:
                hook.enforce(
                    "https://github.com/owner/example.git", push_updates(),
                    environment=guarded, registry=profile, root=root,
                )
            except hook.PushBlocked:
                check(True, "guarded enforce blocks stale local review")
            else:
                check(False, "guarded enforce bypassed stale local review")

        pr_args = SimpleNamespace(
            root=root, registry=target, repository=REPOSITORY,
            maker_vendor="openai", maker_model="gpt-5.6-sol",
            maker_session="maker-session", timeout=120, no_wait=False,
        )
        with (
            mock.patch.object(cli.gate, "adopted_checkout", return_value=[]),
            mock.patch.object(cli.gate, "profile_doctor_entry",
                              return_value=result("LOCAL_REVIEWED")),
            mock.patch.object(cli, "require_registered_origin"),
            mock.patch.object(cli, "ensure_clean_branch", return_value=("topic", HEAD)),
            mock.patch.object(cli, "machine_preflight", return_value=root / "machine.json"),
            mock.patch.object(cli, "create_draft_pr", return_value={
                "number": 177, "url": "https://github.test/pull/177",
                "headRefOid": HEAD, "baseRefOid": BASE,
            }),
            mock.patch.object(cli, "current_pull_request",
                              side_effect=AssertionError("local route called GitHub REST")),
            mock.patch.object(cli, "check_runs",
                              side_effect=AssertionError("local route read App checks")),
            mock.patch.object(cli, "submit_provenance",
                              side_effect=AssertionError("local route called broker")),
        ):
            local_pr = cli.pr_create(pr_args)
        check(
            local_pr["status"] == "LOCAL_REVIEWED"
            and local_pr["provenance"] == "NOT_REQUIRED",
            "local Draft PR route uses no App or broker authority",
        )

        api_docs = (ROOT / "docs" / "API_REVIEWER.md").read_text("utf-8")
        ci_docs = (ROOT / "docs" / "CI.md").read_text("utf-8")
        adopt_docs = (ROOT / "skills" / "adopt" / "SKILL.md").read_text("utf-8")
        check(
            all("itd gate register-profile" in text for text in
                (api_docs, ci_docs, adopt_docs)),
            "operator and adoption docs expose profile registration",
        )
        check(
            "LOCAL_REVIEWED" in api_docs and "never `PROTECTED`" in ci_docs,
            "docs do not overclaim the local profile",
        )
        check(
            all("--candidate-mode committed-head" in text for text in
                (api_docs, ci_docs, adopt_docs)),
            "local profile docs preserve review across exactly one commit",
        )

    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
