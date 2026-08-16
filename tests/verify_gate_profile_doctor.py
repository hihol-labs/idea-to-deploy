#!/usr/bin/env python3
"""Negative canaries for portable profile claims and doctor routing."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(SHARED))
import itd_gate_control as gate  # noqa: E402

SCRIPT = ROOT / "scripts" / "itd_gate_profile_doctor.py"
spec = importlib.util.spec_from_file_location("profile_doctor_test", SCRIPT)
assert spec and spec.loader
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)

APP_ID = 424242
REPOSITORY = "owner/example"
CHECKS = 0
PRIVATE_KEY = bytes(range(32))


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def rejects(fn, label: str) -> None:
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except gate.GateError as exc:
        if exc.status != "UNVERIFIED":
            raise AssertionError(f"{label}: {exc.status}") from exc
    else:
        raise AssertionError(f"{label}: mutation passed")


def row(root: Path, protection: str) -> dict[str, Any]:
    local = protection == "local-review"
    app_check = protection == "app-check"
    return {
        "repository": REPOSITORY,
        "checkout": str(root),
        "repositoryOwnerType": "user" if app_check or local else "organization",
        "deploymentProfile": "local-submission" if local else "self-hosted-app",
        "protectionProfile": protection,
        "localReviewReceiptFile": str(root / "review.json") if local else None,
        "localReviewUnitId": "GPG-001:general-review" if local else None,
        "localReviewRiskTier": "high" if local else None,
        "localReviewProducerKeyringSha256": "a" * 64 if local else None,
        "brokerUrl": None if local else "https://broker.example.test",
        "appId": None if local else APP_ID,
        "appOwner": None if local else "app-owner",
        "appOwnerType": None if local else "user",
        "appVisibility": None if local else "public",
        "rulesetScope": None if local else "repository" if app_check else "organization",
        "rulesetId": None if local else 91,
        "machineWorkflowRepositoryId": None if local or app_check else 515151,
        "machineWorkflowSha": None if local or app_check else "1" * 40,
        "provenanceKeyId": None if local else "current",
        "provenanceKeyFile": None if local else str(root / "signing.key"),
        "enrollmentReceiptSha256": None if local else "e" * 64,
    }


def registry(root: Path, protection: str) -> dict[str, Any]:
    return {"version": 2, "repositories": [row(root, protection)]}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-profile-doctor-") as raw:
        root = Path(raw)
        gate.write_provenance_private_key(root / "signing.key", PRIVATE_KEY)

        local_registry = gate.validate_profile_registry(
            registry(root, "local-review")
        )
        check(
            local_registry["repositories"][0]["appId"] is None,
            "local profile has no App authority",
        )
        overclaim = copy.deepcopy(local_registry)
        overclaim["repositories"][0]["protectionProfile"] = (
            "organization-workflow"
        )
        rejects(
            lambda: gate.validate_profile_registry(overclaim),
            "local evidence cannot overclaim PROTECTED",
        )
        private_managed = registry(root, "app-check")
        private_managed["repositories"][0]["deploymentProfile"] = "managed-app"
        private_managed["repositories"][0]["appVisibility"] = "private"
        rejects(
            lambda: gate.validate_profile_registry(private_managed),
            "managed App profile is public-only",
        )
        borrowed = registry(root, "app-check")
        borrowed["repositories"][0]["machineWorkflowRepositoryId"] = 515151
        borrowed["repositories"][0]["machineWorkflowSha"] = "1" * 40
        rejects(
            lambda: gate.validate_profile_registry(borrowed),
            "App-check cannot borrow machine authority",
        )

        app_rule = gate.app_check_ruleset_payload(
            APP_ID, scope="repository", repository_name="example"
        )
        by_type = {item["type"]: item for item in app_rule["rules"]}
        check("workflows" not in by_type, "App-check ruleset has no workflow")
        check(
            by_type["required_status_checks"]["parameters"][
                "required_status_checks"
            ] == [{"context": gate.EXTERNAL_CHECK, "integration_id": APP_ID}],
            "App-check is bound to the exact App integration",
        )
        forged = copy.deepcopy(app_rule)
        next(
            item for item in forged["rules"]
            if item["type"] == "required_status_checks"
        )["parameters"]["required_status_checks"][0]["integration_id"] += 1
        check(
            bool(gate.validate_live_app_check_ruleset(
                forged, APP_ID, scope="repository", repository_name="example"
            )),
            "same-name foreign App check is rejected",
        )

        local_calls: list[tuple[Any, ...]] = []
        local_entry = local_registry["repositories"][0]
        local_result = gate.profile_doctor_entry(
            local_entry,
            gh=lambda _args: (_ for _ in ()).throw(
                AssertionError("local doctor called GitHub")
            ),
            readiness=lambda *_args: (_ for _ in ()).throw(
                AssertionError("local doctor called broker")
            ),
            local_review=lambda *args: local_calls.append(args),
            adoption=lambda _root: [], version_probe=lambda: "1.95.0",
        )
        check(
            local_result["status"] == "LOCAL_REVIEWED" and local_calls,
            "local doctor reports only local review authority",
        )
        # GPG-004-PB2: the doctor surfaces which authority backed the review
        # without elevating the LOCAL_REVIEWED claim.
        adjudicated_result = gate.profile_doctor_entry(
            local_entry,
            gh=lambda _args: (_ for _ in ()).throw(
                AssertionError("local doctor called GitHub")
            ),
            readiness=lambda *_args: (_ for _ in ()).throw(
                AssertionError("local doctor called broker")
            ),
            local_review=lambda *_args: {"routeEvidence": "human-adjudication"},
            adoption=lambda _root: [], version_probe=lambda: "1.95.0",
        )
        check(
            adjudicated_result["status"] == "LOCAL_REVIEWED"
            and adjudicated_result.get("routeEvidence") == "human-adjudication",
            "adjudicated route evidence is labelled honestly without a claim lift",
        )
        # S9-U2: a route with no signed independence level reports null rather
        # than inventing one.
        check(
            adjudicated_result.get("routeIndependence") is None,
            "route without a signed independence level reports no level",
        )
        signed_result = gate.profile_doctor_entry(
            local_entry,
            gh=lambda _args: (_ for _ in ()).throw(
                AssertionError("local doctor called GitHub")
            ),
            readiness=lambda *_args: (_ for _ in ()).throw(
                AssertionError("local doctor called broker")
            ),
            local_review=lambda *_args: {
                "routeEvidence": "signed-keyless-route",
                "routeIndependence": "cross-vendor",
            },
            adoption=lambda _root: [], version_probe=lambda: "1.95.0",
        )
        check(
            signed_result["status"] == "LOCAL_REVIEWED"
            and signed_result.get("routeEvidence") == "signed-keyless-route",
            "signed keyless route evidence keeps its own honest label",
        )
        # S9-U2: the doctor entry surfaces the independence level the validated
        # route reported, and surfacing it does not lift the claim.
        check(
            signed_result.get("routeIndependence") == "cross-vendor"
            and signed_result["status"] == "LOCAL_REVIEWED",
            "signed route independence level reaches the doctor entry",
        )
        foreign_result = gate.profile_doctor_entry(
            local_entry,
            gh=lambda _args: (_ for _ in ()).throw(
                AssertionError("local doctor called GitHub")
            ),
            readiness=lambda *_args: (_ for _ in ()).throw(
                AssertionError("local doctor called broker")
            ),
            local_review=lambda *_args: {
                "routeEvidence": "signed-keyless-route",
                "routeIndependence": "",
            },
            adoption=lambda _root: [], version_probe=lambda: "1.95.0",
        )
        check(
            foreign_result.get("routeIndependence") is None
            and foreign_result.get("routeEvidence") == "signed-keyless-route",
            "empty independence label is dropped, evidence label survives",
        )

        def outcome_runner(payload: bytes):
            def runner(command, **_kwargs):
                return subprocess.CompletedProcess(command, 0, payload, b"")
            return runner

        check(
            gate.validate_local_adjudication(
                root, root / "review.json", "GPG-004:local-review-commit",
                "high", REPOSITORY, "a" * 64,
                runner=outcome_runner(b'{"outcome": "ADJUDICATED"}'),
            ) == {"routeEvidence": "human-adjudication"},
            "validated ADJUDICATED outcome maps to the human-adjudication label",
        )
        check(
            gate.validate_local_adjudication(
                root, root / "review.json", "GPG-004:local-review-commit",
                "high", REPOSITORY, "a" * 64,
                runner=outcome_runner(b'{"outcome": "PASSED"}'),
            ) == {"routeEvidence": "signed-keyless-route"},
            "validated PASSED outcome maps to the signed-keyless-route label",
        )
        # S9-U2: the validator carries the independence level the check
        # printed, but only when it is inside the closed independence class.
        check(
            gate.validate_local_adjudication(
                root, root / "review.json", "GPG-004:local-review-commit",
                "high", REPOSITORY, "a" * 64,
                runner=outcome_runner(
                    b'{"outcome": "PASSED", '
                    b'"routeIndependence": "cross-vendor"}'
                ),
            ) == {"routeEvidence": "signed-keyless-route",
                  "routeIndependence": "cross-vendor"},
            "validated signed route carries its closed-class independence level",
        )
        check(
            gate.validate_local_adjudication(
                root, root / "review.json", "GPG-004:local-review-commit",
                "high", REPOSITORY, "a" * 64,
                runner=outcome_runner(
                    b'{"outcome": "PASSED", '
                    b'"routeIndependence": "same-vendor-different-model"}'
                ),
            ) == {"routeEvidence": "signed-keyless-route",
                  "routeIndependence": "same-vendor-different-model"},
            "the weaker closed-class level is reported as itself, not upgraded",
        )
        for forged in (
            b'{"outcome": "PASSED", "routeIndependence": "fully-independent"}',
            b'{"outcome": "PASSED", "routeIndependence": ""}',
            b'{"outcome": "PASSED", "routeIndependence": true}',
            b'{"outcome": "PASSED", "routeIndependence": ["cross-vendor"]}',
            b'{"outcome": "PASSED", "routeIndependence": null}',
        ):
            check(
                gate.validate_local_adjudication(
                    root, root / "review.json", "GPG-004:local-review-commit",
                    "high", REPOSITORY, "a" * 64,
                    runner=outcome_runner(forged),
                ) == {"routeEvidence": "signed-keyless-route"},
                "independence level outside the closed class is dropped: "
                + forged.decode("utf-8"),
            )
        check(
            gate.validate_local_adjudication(
                root, root / "review.json", "GPG-004:local-review-commit",
                "high", REPOSITORY, "a" * 64,
                runner=outcome_runner(b'["PASSED"]'),
            ) is None,
            "a non-object route payload yields no label at all",
        )
        check(
            gate.validate_local_adjudication(
                root, root / "review.json", "GPG-004:local-review-commit",
                "high", REPOSITORY, "a" * 64,
                runner=outcome_runner(
                    b'{"outcome": "UNVERIFIED", '
                    b'"routeIndependence": "cross-vendor"}'
                ),
            ) is None,
            "an independence level cannot survive a non-passing outcome",
        )
        commands: list[list[str]] = []

        def committed_runner(command, **_kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, b"", b"")

        gate.validate_local_adjudication(
            root, root / "review.json", "GPG-001:general-review", "high",
            REPOSITORY, "a" * 64,
            runner=committed_runner,
        )
        check(
            commands
            and "--candidate-mode" in commands[0]
            and commands[0][commands[0].index("--candidate-mode") + 1]
            == "committed-head",
            "local doctor bridges only the exact committed HEAD candidate",
        )
        check(
            "--require-mandatory-route" in commands[0],
            "local doctor rejects generic checker/adjudication publication evidence",
        )
        check(
            commands[0][commands[0].index("--expected-repository") + 1]
            == REPOSITORY,
            "local doctor binds mandatory route evidence to the selected repository",
        )
        check(
            commands[0][
                commands[0].index("--expected-producer-keyring-sha256") + 1
            ] == "a" * 64,
            "local doctor does not bind the host-authorized producer keyring",
        )
        unc_timeouts: list[int] = []

        def unc_runner(command, **kwargs):
            unc_timeouts.append(kwargs["timeout"])
            return subprocess.CompletedProcess(command, 0, b"", b"")

        for unc_checkout in (
            PureWindowsPath(r"\\wsl.localhost\Ubuntu-24.04\home\user\project"),
            PureWindowsPath(
                r"\\?\UNC\wsl.localhost\Ubuntu-24.04\home\user\project"
            ),
        ):
            unc_timeouts.clear()
            gate.validate_local_adjudication(
                unc_checkout, unc_checkout / "review.json",
                "GPG-001:general-review", "high", REPOSITORY,
                "a" * 64,
                runner=unc_runner,
                platform_name="nt",
            )
            check(
                unc_timeouts == [180],
                "native Windows UNC doctor receives a bounded cold-start budget",
            )
        check(
            gate.local_adjudication_timeout(
                Path("/home/user/project"), platform_name="posix"
            ) == 30,
            "local checkout adjudication retains the strict default timeout",
        )
        for local_windows_path in (
            PureWindowsPath(r"C:\repo"),
            PureWindowsPath(r"\\?\C:\repo"),
            PureWindowsPath(r"\\.\C:\repo"),
            PureWindowsPath(r"\\server-only"),
            PureWindowsPath(r"\\?\UNC\server-only"),
        ):
            check(
                gate.local_adjudication_timeout(
                    local_windows_path, platform_name="nt"
                ) == 30,
                "native Windows local/device paths retain the strict timeout",
            )

        def stale(*_args):
            raise gate.GateError("UNVERIFIED", "local adjudication is stale")

        stale_result = gate.profile_doctor_entry(
            local_entry, local_review=stale, adoption=lambda _root: [],
            version_probe=lambda: "1.95.0",
        )
        check(
            stale_result["status"] == "UNVERIFIED"
            and any("stale" in item for item in stale_result["drift"]),
            "stale local receipt fails closed",
        )

        app_entry = gate.validate_profile_registry(
            registry(root, "app-check")
        )["repositories"][0]
        ready = {
            "status": "ready",
            "enrollment": {"receiptSha256": "e" * 64},
        }
        app_result = gate.profile_doctor_entry(
            app_entry, gh=lambda _args: app_rule,
            readiness=lambda *_args: ready,
            local_review=lambda *_args: (_ for _ in ()).throw(
                AssertionError("App doctor used local receipt")
            ),
            adoption=lambda _root: [], version_probe=lambda: "1.95.0",
        )
        check(
            app_result["status"] == "APP_CHECK_ENFORCED",
            "App doctor does not overclaim PROTECTED",
        )
        wrong_enrollment = gate.profile_doctor_entry(
            app_entry, gh=lambda _args: app_rule,
            readiness=lambda *_args: {
                "status": "ready",
                "enrollment": {"receiptSha256": "f" * 64},
            },
            adoption=lambda _root: [], version_probe=lambda: "1.95.0",
        )
        check(
            wrong_enrollment["status"] == "UNVERIFIED",
            "foreign broker enrollment fails closed",
        )

        strongest_entry = gate.validate_profile_registry(
            registry(root, "organization-workflow")
        )["repositories"][0]
        strongest = gate.profile_doctor_entry(
            strongest_entry,
            strongest_doctor=lambda _entry, **_kwargs: {
                "repository": REPOSITORY, "status": "PROTECTED", "drift": [],
                "itdVersion": "1.95.0", "broker": ready,
            },
        )
        check(strongest["status"] == "PROTECTED", "strict doctor may claim PROTECTED")
        check(
            gate.aggregate_claim([strongest, app_result])
            == "APP_CHECK_ENFORCED",
            "mixed fleet reports the weakest verified claim",
        )
        check(
            gate.aggregate_claim([strongest, wrong_enrollment]) == "UNVERIFIED",
            "any fleet drift fails closed",
        )

        quiet = io.StringIO()
        with redirect_stdout(quiet):
            no_op = doctor.main([])
        check(no_op == 0 and quiet.getvalue() == "", "no-argument doctor is quiet")
        input_file = root / "profiles.json"
        input_file.write_text(json.dumps(local_registry), encoding="utf-8")
        check(
            doctor.load_profile_registry(input_file) == local_registry,
            "profile doctor loads a bounded closed registry",
        )

    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
