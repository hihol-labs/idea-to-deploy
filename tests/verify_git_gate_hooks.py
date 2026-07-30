#!/usr/bin/env python3
"""Mutation checks for host-global Git hooks and the machine workflow."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load("itd_pre_push_test", ROOT / "scripts" / "itd_pre_push.py")
installer = load(
    "itd_install_git_hooks_test",
    ROOT / "scripts" / "itd_install_git_hooks.py",
)
cli_installer = load(
    "itd_install_cli_test",
    ROOT / "scripts" / "itd_install_cli.py",
)
CHECKS = 0
HEAD = "a" * 40
BASE = "b" * 40
REPOSITORY = "hihol-labs/example"


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
    except hook.PushBlocked:
        return
    raise AssertionError(label)


def updates(remote_ref: str, local_sha: str = HEAD) -> bytes:
    return (
        f"refs/heads/topic {local_sha} {remote_ref} {BASE}\n"
    ).encode("utf-8")


def registry(checkout: Path) -> dict:
    return {
        "version": 1,
        "repositories": [
            {
                "repository": REPOSITORY,
                "checkout": str(checkout),
                "brokerUrl": "https://broker.example.test",
                "appId": 424242,
                "rulesetScope": "organization",
                "rulesetId": 91,
                "machineWorkflowRepositoryId": 515151,
                "machineWorkflowSha": "1" * 40,
                "provenanceKeyId": "current",
                "provenanceKeyFile": str(checkout / "signing.key"),
            }
        ],
    }


def receipt(path: Path, head: str = HEAD) -> None:
    value = {
        "version": 2,
        "kind": "itd-machine-oracle",
        "repository": str(path.parent),
        "headSha": head,
        "tree": "c" * 40,
        "contractPath": ".itd/VERIFICATION_CONTRACT.json",
        "contractSha256": "d" * 64,
        "verifierTrust": "LOCAL_ONLY",
        "trustedVerifierBindings": [
            {
                "path": "tests",
                "objectKind": "tree",
                "protectedManifestSha256": "e" * 64,
                "candidateManifestSha256": "e" * 64,
                "entryCount": 1,
                "status": "LOCAL_ONLY",
            }
        ],
        "trustedVerifierFailures": [],
        "commands": [{"id": "tests", "status": "PASSED"}],
        "missingArtifacts": [],
        "requiredArtifactSha256": {},
        "executionCheckout": "isolated-exact-head-tree",
        "credentialEnvironment": "removed-by-name",
        "rawOutputPersisted": False,
        "observedAt": "2026-07-30T00:00:00Z",
        "status": "PASSED",
    }
    value["receiptSha256"] = hashlib.sha256(
        hook.gate.canonical_json(value)
    ).hexdigest()
    path.write_text(json.dumps(value), encoding="utf-8")


def hook_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-pre-push-") as raw:
        root = Path(raw).resolve()
        receipt_path = root / "receipt.json"
        receipt(receipt_path)
        managed = registry(root)
        remote = "https://github.com/hihol-labs/example.git"
        guarded = {
            "ITD_GUARDED_PR_PUSH": "1",
            "ITD_MACHINE_RECEIPT": str(receipt_path),
            "ITD_MAKER_VENDOR": "openai",
            "ITD_MAKER_MODEL": "gpt-5.6-sol",
            "ITD_MAKER_SESSION": "session-1",
        }

        rejects(
            lambda: hook.enforce(
                remote,
                updates("refs/heads/main"),
                registry=managed,
                root=root,
            ),
            "direct main push blocked",
        )
        rejects(
            lambda: hook.enforce(
                remote,
                updates("refs/heads/release/1.95"),
                registry=managed,
                root=root,
            ),
            "direct release push blocked",
        )
        hook.enforce(
            "https://git.example.test/team/repo.git",
            updates("refs/heads/topic"),
            registry=managed,
            root=root,
        )
        check(True, "non-GitHub feature push is outside ITD registry")
        rejects(
            lambda: hook.enforce(
                "https://github.com/other/repo.git",
                updates("refs/heads/topic"),
                registry=managed,
                root=root,
            ),
            "unregistered GitHub push is fail-closed",
        )
        rejects(
            lambda: hook.enforce(
                remote,
                updates("refs/heads/topic"),
                registry=managed,
                root=root,
            ),
            "registered direct feature push routes through itd pr create",
        )
        hook.enforce(
            remote,
            updates("refs/heads/topic"),
            environment=guarded,
            registry=managed,
            root=root,
        )
        check(True, "guarded exact-head feature push allowed")
        missing_maker = dict(guarded)
        del missing_maker["ITD_MAKER_MODEL"]
        rejects(
            lambda: hook.enforce(
                remote,
                updates("refs/heads/topic"),
                environment=missing_maker,
                registry=managed,
                root=root,
            ),
            "missing maker provenance blocks the guarded push",
        )
        rejects(
            lambda: hook.enforce(
                remote,
                updates("refs/heads/topic", "e" * 40),
                environment=guarded,
                registry=managed,
                root=root,
            ),
            "receipt/head mismatch blocked",
        )
        legacy = json.loads(receipt_path.read_text())
        legacy["version"] = 1
        legacy.pop("receiptSha256")
        legacy["receiptSha256"] = hashlib.sha256(
            hook.gate.canonical_json(legacy)
        ).hexdigest()
        receipt_path.write_text(json.dumps(legacy), encoding="utf-8")
        rejects(
            lambda: hook.enforce(
                remote,
                updates("refs/heads/topic"),
                environment=guarded,
                registry=managed,
                root=root,
            ),
            "legacy self-attestable machine receipt blocked",
        )
        receipt(receipt_path)
        value = json.loads(receipt_path.read_text())
        value["status"] = "UNVERIFIED"
        receipt_path.write_text(json.dumps(value), encoding="utf-8")
        rejects(
            lambda: hook.enforce(
                remote,
                updates("refs/heads/topic"),
                environment=guarded,
                registry=managed,
                root=root,
            ),
            "forged receipt blocked",
        )


def installer_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-hook-install-") as raw:
        root = Path(raw)
        script = root / "itd_pre_push.py"
        python = root / "python"
        script.write_text("# fixture\n", encoding="utf-8")
        python.write_text("", encoding="utf-8")
        target = root / "hooks"
        selected_runtime = (python.resolve(), "test-version", "explicit")
        with (
            mock.patch.object(installer, "git_config", return_value=""),
            mock.patch.object(
                installer,
                "select_runtime",
                return_value=selected_runtime,
            ),
        ):
            preview = installer.install(
                target,
                apply=False,
                replace_existing=False,
                python=python,
                script=script,
            )
        check(
            preview["status"] == "PREVIEW"
            and preview["pythonSource"] == "explicit"
            and preview["cryptographyVersion"] == "test-version"
            and not target.exists(),
            "installer preview is read-only",
        )
        configured: list[tuple[str, ...]] = []

        def config(*arguments: str, check: bool = True) -> str:
            del check
            configured.append(arguments)
            if arguments == ("--get", "core.hooksPath"):
                return target.as_posix() if len(configured) > 1 else ""
            return ""

        with (
            mock.patch.object(installer, "git_config", side_effect=config),
            mock.patch.object(
                installer,
                "select_runtime",
                return_value=selected_runtime,
            ),
        ):
            result = installer.install(
                target,
                apply=True,
                replace_existing=False,
                python=python,
                script=script,
            )
        wrapper = (target / "pre-push").read_text(encoding="utf-8")
        check(result["status"] == "INSTALLED", "installer applies")
        check(
            wrapper.startswith("#!/bin/sh\nset -eu\nexec ")
            and "\"$@\"" in wrapper,
            "installed wrapper is bounded and forwards hook arguments",
        )
        incompatible = root / "python-without-cryptography"
        incompatible.write_text("", encoding="utf-8")
        incompatible_target = root / "broken-hooks"
        with mock.patch.object(installer, "git_config", return_value=""):
            try:
                installer.install(
                    incompatible_target,
                    apply=True,
                    replace_existing=False,
                    python=incompatible,
                    script=script,
                )
            except installer.InstallError:
                check(
                    not incompatible_target.exists(),
                    "hook installer rejects an incompatible Python before writing",
                )
            else:
                raise AssertionError(
                    "hook installer accepted Python without cryptography"
                )
        with (
            mock.patch.object(
                installer,
                "git_config",
                return_value=str(root / "other-hooks"),
            ),
            mock.patch.object(
                installer,
                "select_runtime",
                return_value=selected_runtime,
            ),
        ):
            try:
                installer.install(
                    target,
                    apply=False,
                    replace_existing=False,
                    python=python,
                    script=script,
                )
            except installer.InstallError:
                check(True, "existing global hooksPath is preserved")
            else:
                raise AssertionError("existing hooksPath was overwritten")


def cli_installer_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-cli-install-") as raw:
        root = Path(raw)
        script = root / "itd.py"
        python = Path(sys.executable)
        target = root / "bin" / (
            "itd.cmd" if cli_installer.os.name == "nt" else "itd"
        )
        script.write_text("# fixture\n", encoding="utf-8")
        preview = cli_installer.install(
            target,
            apply=False,
            replace_existing=False,
            update_path=False,
            python=python,
            script=script,
        )
        check(
            preview["status"] == "PREVIEW" and not target.exists(),
            "CLI installer preview is read-only",
        )
        applied = cli_installer.install(
            target,
            apply=True,
            replace_existing=False,
            update_path=False,
            python=python,
            script=script,
        )
        check(
            applied["status"] == "INSTALLED" and target.is_file(),
            "CLI installer applies exact runtime wrapper",
        )
        expected = cli_installer.wrapper(
            python.resolve(), script.resolve()
        )
        check(target.read_bytes() == expected, "CLI wrapper bytes are exact")
        target.write_text("foreign command\n", encoding="utf-8")
        try:
            cli_installer.install(
                target,
                apply=False,
                replace_existing=False,
                update_path=False,
                python=python,
                script=script,
            )
        except cli_installer.InstallError:
            check(True, "CLI installer preserves a foreign command")
        else:
            raise AssertionError("foreign ITD command was overwritten")

        incompatible = root / "python-without-cryptography"
        incompatible.write_text("", encoding="utf-8")
        incompatible_target = root / "broken" / "itd"
        try:
            cli_installer.install(
                incompatible_target,
                apply=True,
                replace_existing=False,
                update_path=False,
                python=incompatible,
                script=script,
            )
        except cli_installer.InstallError:
            check(
                not incompatible_target.exists(),
                "CLI installer rejects an incompatible Python before writing",
            )
        else:
            raise AssertionError(
                "CLI installer accepted Python without cryptography"
            )

        probe_cases = [
            (
                "import sys;"
                "sys.stdout.buffer.write("
                f"b'x'*{cli_installer.MAX_RUNTIME_PROBE_OUTPUT + 1});"
                "sys.stdout.flush()",
                "CLI runtime probe rejects output beyond its byte bound",
            ),
            (
                "import sys;"
                "sys.stdout.buffer.write(bytes([255]));"
                "sys.stdout.flush()",
                "CLI runtime probe rejects non-UTF-8 output",
            ),
        ]
        for probe, label in probe_cases:
            with mock.patch.object(
                cli_installer, "RUNTIME_PROBE", probe
            ):
                try:
                    cli_installer.probe_runtime(python)
                except cli_installer.InstallError:
                    check(True, label)
                else:
                    raise AssertionError(label)


def workflow_phase() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "itd-machine-oracle.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    required = [
        "pull_request:",
        "merge_group:",
        "name: ITD machine oracle",
        "persist-credentials: false",
        "scripts/itd_machine_oracle.py",
        "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ]
    check(all(item in workflow for item in required), "machine workflow exact assets")
    forbidden = [
        "pull_request_target:",
        "repository_dispatch:",
        "OPENAI_API_KEY: ${{",
        "ANTHROPIC_API_KEY: ${{",
        "ITD_PROVENANCE_HMAC_KEY",
        "actions/checkout@v",
        "actions/upload-artifact@v",
    ]
    check(
        all(item not in workflow for item in forbidden),
        "machine workflow has no reviewer secret or mutable action",
    )
    check(
        not (
            ROOT / ".github" / "workflows" / "external-review-gate.yml"
        ).exists(),
        "obsolete repository API reviewer workflow removed",
    )


def main() -> int:
    hook_phase()
    installer_phase()
    cli_installer_phase()
    workflow_phase()
    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
