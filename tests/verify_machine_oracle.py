#!/usr/bin/env python3
"""Regression checks for the tracked verification-contract machine oracle."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "itd_machine_oracle.py"
spec = importlib.util.spec_from_file_location("itd_machine_oracle_test", MODULE)
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = oracle
spec.loader.exec_module(oracle)
CHECKS = 0


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def expect_oracle_error(fn, label: str) -> None:
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except oracle.OracleError:
        return
    raise AssertionError(label)


def initialize(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email",
         "fixture" + "@example.test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Fixture"],
        check=True,
    )


def contract(commands: list[dict], artifacts: list[str]) -> dict:
    return {
        "version": 2,
        "commands": commands,
        "requiredArtifacts": artifacts,
        "failClosed": "missing or ambiguous evidence is UNVERIFIED",
    }


def command(
    identifier: str,
    argv: list[str],
    parser: str,
    expected,
    trusted_paths: list[str] | None = None,
) -> dict:
    return {
        "id": identifier,
        "argv": argv,
        "trustedVerifierPaths": trusted_paths or ["verifiers"],
        "timeoutSeconds": 10,
        "expectedOutput": expected,
        "passFailParser": parser,
    }


def repository_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-machine-oracle-") as raw:
        root = Path(raw)
        initialize(root)
        itd = root / ".itd"
        itd.mkdir()
        artifact = root / "evidence.txt"
        artifact.write_text("ready\n", encoding="utf-8")
        (root / ".gitignore").write_text(
            "ignored-input.txt\n", encoding="utf-8"
        )
        (root / "ignored-input.txt").write_text(
            "must never enter the oracle\n", encoding="utf-8"
        )
        verifier = root / "verifiers" / "verifier.py"
        verifier.parent.mkdir()
        verifier.write_text(
            "import json\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            "mode = sys.argv[1]\n"
            "if mode == 'exit': raise SystemExit(0)\n"
            "if mode == 'contains': print('EXPECTED-SENTINEL')\n"
            "elif mode == 'json': "
            "print(json.dumps({'nested': {'ok': True}}))\n"
            "elif mode == 'no-credential': "
            "raise SystemExit(1 if os.getenv('OPENAI_API_KEY') else 0)\n"
            "elif mode == 'no-command-env': "
            "raise SystemExit(1 if any(os.getenv(name) for name in "
            "('GITHUB_ENV', 'GITHUB_PATH', 'GITHUB_OUTPUT', "
            "'GITHUB_STEP_SUMMARY', 'RUNNER_TEMP')) else 0)\n"
            "elif mode == 'no-overlay': "
            "raise SystemExit(1 if Path('ignored-input.txt').exists() else 0)\n",
            encoding="utf-8",
        )
        contract_path = itd / "VERIFICATION_CONTRACT.json"
        value = contract(
            [
                command(
                    "exit",
                    [sys.executable, "-I", "verifiers/verifier.py", "exit"],
                    "exit_code_zero",
                    "",
                ),
                command(
                    "contains",
                    [sys.executable, "-I", "verifiers/verifier.py", "contains"],
                    "stdout_contains",
                    "EXPECTED-SENTINEL",
                ),
                command(
                    "json",
                    [sys.executable, "-I", "verifiers/verifier.py", "json"],
                    "json_field_equals",
                    {"field": "nested.ok", "value": True},
                ),
                command(
                    "no-credential-env",
                    [sys.executable, "-I", "verifiers/verifier.py", "no-credential"],
                    "exit_code_zero",
                    "",
                ),
                command(
                    "no-github-command-env",
                    [
                        sys.executable,
                        "-I",
                        "verifiers/verifier.py",
                        "no-command-env",
                    ],
                    "exit_code_zero",
                    "",
                ),
                command(
                    "no-ignored-overlay",
                    [sys.executable, "-I", "verifiers/verifier.py", "no-overlay"],
                    "exit_code_zero",
                    "",
                ),
            ],
            ["evidence.txt"],
        )
        contract_path.write_text(json.dumps(value), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "fixture"],
            check=True,
        )
        head = git(root, "rev-parse", "HEAD")
        tree = git(root, "rev-parse", "HEAD^{tree}")
        with oracle.isolated_head(root, head, tree) as isolated:
            check(
                not (
                    isolated / ".git" / "objects" / "info" / "alternates"
                ).exists(),
                "isolated candidate must not share the caller object store",
            )
        with oracle_environment():
            receipt = oracle.execute(root, contract_path)
        check(receipt["status"] == "PASSED", "machine receipt passes")
        check(receipt["rawOutputPersisted"] is False, "raw output absent")
        check(
            all(
                set(row)
                >= {
                    "stdoutSha256",
                    "stderrSha256",
                    "argvSha256",
                    "trustedVerifierManifestSha256",
                    "status",
                }
                for row in receipt["commands"]
            ),
            "commands hash-bound",
        )
        check(
            receipt["verifierTrust"] == "LOCAL_ONLY",
            "local preflight does not claim independent trust",
        )
        check(receipt["headSha"] == git(root, "rev-parse", "HEAD"), "HEAD bound")
        check(receipt["tree"] == git(root, "rev-parse", "HEAD^{tree}"), "tree bound")
        expected = dict(receipt)
        digest = expected.pop("receiptSha256")
        check(
            digest == oracle.sha256_bytes(oracle.canonical_json(expected)),
            "receipt digest",
        )

        original_contract = contract_path.read_bytes()
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "update-index",
                "--assume-unchanged",
                ".itd/VERIFICATION_CONTRACT.json",
            ],
            check=True,
        )
        contract_path.write_bytes(original_contract + b"\n")
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "contract bytes must match HEAD despite assume-unchanged",
        )
        contract_path.write_bytes(original_contract)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "update-index",
                "--no-assume-unchanged",
                ".itd/VERIFICATION_CONTRACT.json",
            ],
            check=True,
        )

        overlay = root / "untracked-overlay.txt"
        overlay.write_text("must not affect oracle\n", encoding="utf-8")
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "untracked candidate overlay blocks",
        )
        overlay.unlink()

        artifact.unlink()
        subprocess.run(["git", "-C", str(root), "add", "-u"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "remove artifact"],
            check=True,
        )
        failed = oracle.execute(root, contract_path)
        check(
            failed["status"] == "UNVERIFIED"
            and failed["missingArtifacts"] == ["evidence.txt"],
            "missing artifact blocks",
        )

        with tempfile.TemporaryDirectory(
            prefix="itd-machine-host-artifact-"
        ) as outside_raw:
            outside = Path(outside_raw)
            (outside / "evidence.txt").write_text(
                "must stay outside the candidate\n", encoding="utf-8"
            )
            artifact_link = root / "artifact-link"
            artifact_link.symlink_to(outside, target_is_directory=True)
            linked = contract(
                [
                    command(
                        "linked-artifact",
                        [sys.executable, "-I", "verifiers/verifier.py", "exit"],
                        "exit_code_zero",
                        "",
                    )
                ],
                ["artifact-link/evidence.txt"],
            )
            contract_path.write_text(json.dumps(linked), encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", str(contract_path), str(artifact_link)],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "link artifact"],
                check=True,
            )
            linked_receipt = oracle.execute(root, contract_path)
            check(
                linked_receipt["status"] == "UNVERIFIED"
                and linked_receipt["missingArtifacts"]
                == ["artifact-link/evidence.txt"],
                "required artifact rejects a symlinked parent",
            )

        manual = contract(
            [
                command(
                    "manual",
                    [sys.executable, "-I", "verifiers/verifier.py", "exit"],
                    "manual_evidence",
                    "operator says pass",
                )
            ],
            [],
        )
        contract_path.write_text(json.dumps(manual), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", str(contract_path)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "manual contract"],
            check=True,
        )
        manual_receipt = oracle.execute(root, contract_path)
        check(manual_receipt["status"] == "UNVERIFIED", "manual evidence blocks")


def protected_base_contract_phase() -> None:
    with tempfile.TemporaryDirectory(
        prefix="itd-machine-protected-contract-"
    ) as raw:
        workspace = Path(raw)
        protected = workspace / "protected-base"
        candidate = workspace / "candidate"
        protected.mkdir()
        candidate.mkdir()
        initialize(protected)
        initialize(candidate)

        protected_contract = (
            protected / ".itd" / "VERIFICATION_CONTRACT.json"
        )
        protected_contract.parent.mkdir()
        protected_verifier = protected / "verifiers" / "verifier.py"
        protected_verifier.parent.mkdir()
        protected_verifier.write_text(
            "from pathlib import Path\n"
            "raise SystemExit(0 if "
            "Path('evidence.txt').read_text() == 'trusted\\n' else 1)\n",
            encoding="utf-8",
        )
        protected_contract.write_text(
            json.dumps(
                contract(
                    [
                        command(
                            "protected-command",
                            [sys.executable, "-I", "verifiers/verifier.py"],
                            "exit_code_zero",
                            "",
                            ["verifiers/verifier.py"],
                        )
                    ],
                    ["evidence.txt"],
                )
            ),
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(protected), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(protected), "commit", "-qm", "protected"],
            check=True,
        )

        candidate_contract = (
            candidate / ".itd" / "VERIFICATION_CONTRACT.json"
        )
        candidate_contract.parent.mkdir()
        candidate_verifier = candidate / "verifiers" / "verifier.py"
        candidate_verifier.parent.mkdir()
        candidate_verifier.write_text(
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        candidate_contract.write_text(
            json.dumps(
                contract(
                    [
                        command(
                            "candidate-noop",
                            [sys.executable, "-I", "verifiers/verifier.py"],
                            "exit_code_zero",
                            "",
                        )
                    ],
                    [],
                )
            ),
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(candidate), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(candidate), "commit", "-qm", "candidate"],
            check=True,
        )

        failed = oracle.execute(
            candidate, protected_contract, protected
        )
        check(
            failed["status"] == "UNVERIFIED"
            and failed["missingArtifacts"] == ["evidence.txt"]
            and failed["trustedVerifierFailures"]
            == ["verifiers/verifier.py"]
            and failed["commands"][0]["status"]
            == "NOT_RUN_TRUST_FAILURE",
            "candidate no-op verifier cannot self-attest",
        )
        (candidate / "evidence.txt").write_text(
            "trusted\n", encoding="utf-8"
        )
        candidate_verifier.write_bytes(protected_verifier.read_bytes())
        subprocess.run(
            ["git", "-C", str(candidate), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(candidate), "commit", "-qm", "evidence"],
            check=True,
        )
        passed = oracle.execute(
            candidate, protected_contract, protected
        )
        check(
            passed["status"] == "PASSED"
            and passed["contractSource"] == "protected-base-head"
            and passed["verifierTrust"]
            == "PROTECTED_BASE_CONTENT_BOUND"
            and passed["contractHeadSha"]
            == git(protected, "rev-parse", "HEAD"),
            "receipt binds protected contract, verifier, and commit",
        )
        startup_hook = candidate / "verifiers" / "sitecustomize.py"
        startup_hook.write_text(
            "import os\nos._exit(0)\n",
            encoding="utf-8",
        )
        (candidate / "evidence.txt").write_text(
            "untrusted\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(candidate), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(candidate), "commit", "-qm", "startup-hook"],
            check=True,
        )
        startup_tampered = oracle.execute(
            candidate, protected_contract, protected
        )
        check(
            startup_tampered["status"] == "UNVERIFIED"
            and startup_tampered["trustedVerifierFailures"] == []
            and startup_tampered["commands"][0]["status"] == "FAILED",
            "isolated exact-file verifier ignores adjacent sitecustomize",
        )
        startup_hook.unlink()
        (candidate / "evidence.txt").write_text(
            "trusted\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(candidate), "add", "-A"], check=True
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(candidate),
                "commit",
                "-qm",
                "remove-startup-hook",
            ],
            check=True,
        )
        candidate_verifier.write_text(
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(candidate), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(candidate), "commit", "-qm", "tamper"],
            check=True,
        )
        tampered = oracle.execute(
            candidate, protected_contract, protected
        )
        check(
            tampered["status"] == "UNVERIFIED"
            and tampered["trustedVerifierFailures"]
            == ["verifiers/verifier.py"],
            "protected verifier content mutation blocks",
        )
        expect_oracle_error(
            lambda: oracle.execute(candidate, protected_contract),
            "external contract requires an explicit trusted root",
        )
        (protected / "dirty.txt").write_text(
            "drift\n", encoding="utf-8"
        )
        expect_oracle_error(
            lambda: oracle.execute(
                candidate, protected_contract, protected
            ),
            "dirty protected contract checkout blocks",
        )


def contract_trust_schema_phase() -> None:
    with tempfile.TemporaryDirectory(
        prefix="itd-machine-contract-schema-"
    ) as raw:
        root = Path(raw)
        initialize(root)
        contract_path = root / ".itd" / "VERIFICATION_CONTRACT.json"
        contract_path.parent.mkdir()
        verifier = root / "verifiers" / "verifier.py"
        verifier.parent.mkdir()
        verifier.write_text(
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        launcher = root / "verifiers" / "itd_py.sh"
        launcher.write_text("#!/bin/sh\nexec python3 -I \"$@\"\n",
                            encoding="utf-8")
        (root / "other.py").write_text(
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        legacy = {
            "version": 1,
            "commands": [
                {
                    "id": "legacy",
                    "command": "true",
                    "timeoutSeconds": 10,
                    "expectedOutput": "",
                    "passFailParser": "exit_code_zero",
                }
            ],
            "requiredArtifacts": [],
        }
        contract_path.write_text(json.dumps(legacy), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "legacy"],
            check=True,
        )
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "legacy shell-string contract is rejected",
        )

        nonisolated = contract(
            [
                command(
                    "nonisolated-python",
                    [sys.executable, "verifiers/verifier.py"],
                    "exit_code_zero",
                    "",
                )
            ],
            [],
        )
        contract_path.write_text(
            json.dumps(nonisolated),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "nonisolated"],
            check=True,
        )
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "Python verifier without isolated mode is rejected",
        )

        pypy_nonisolated = contract(
            [
                command(
                    "nonisolated-pypy",
                    ["pypy3", "verifiers/verifier.py"],
                    "exit_code_zero",
                    "",
                )
            ],
            [],
        )
        contract_path.write_text(
            json.dumps(pypy_nonisolated),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "nonisolated-pypy"],
            check=True,
        )
        try:
            oracle.execute(root, contract_path)
        except oracle.OracleError as exc:
            check(
                "not isolated with -I" in str(exc),
                "PyPy verifier requires the same isolated-script boundary",
            )
        else:
            raise AssertionError("non-isolated PyPy verifier was accepted")

        misplaced_isolation = contract(
            [
                command(
                    "misplaced-python-isolation",
                    [sys.executable, "verifiers/verifier.py", "-I"],
                    "exit_code_zero",
                    "",
                )
            ],
            [],
        )
        contract_path.write_text(
            json.dumps(misplaced_isolation),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "misplaced-isolation"],
            check=True,
        )
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "Python -I after the verifier does not enable isolated mode",
        )

        option_operand = contract(
            [
                command(
                    "python-option-operand",
                    [
                        sys.executable,
                        "-I",
                        "-X",
                        "verifiers/verifier.py",
                        "other.py",
                    ],
                    "exit_code_zero",
                    "",
                )
            ],
            [],
        )
        contract_path.write_text(json.dumps(option_operand), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "option-operand"],
            check=True,
        )
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "Python option operands cannot masquerade as trusted scripts",
        )

        unrelated = contract(
            [
                command(
                    "unrelated-binding",
                    [sys.executable, "-I", "-c", "raise SystemExit(0)"],
                    "exit_code_zero",
                    "",
                )
            ],
            [],
        )
        contract_path.write_text(
            json.dumps(unrelated),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "unrelated"],
            check=True,
        )
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "unrelated trusted file cannot authorize a no-op argv",
        )

        undeclared = contract(
            [
                command(
                    "undeclared-input",
                    [
                        sys.executable,
                        "-I",
                        "other.py",
                        "verifiers/verifier.py",
                    ],
                    "exit_code_zero",
                    "",
                )
            ],
            [],
        )
        contract_path.write_text(
            json.dumps(undeclared),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "undeclared"],
            check=True,
        )
        expect_oracle_error(
            lambda: oracle.execute(root, contract_path),
            "tracked argv verifier input must be declared and bound",
        )

        inert_shell = contract(
            [
                command(
                    "inert-shell-binding",
                    [
                        "bash", "-c", "printf EXPECTED-SENTINEL",
                        "verifiers/verifier.py",
                    ],
                    "stdout_contains",
                    "EXPECTED-SENTINEL",
                )
            ],
            [],
        )
        expect_oracle_error(
            lambda: oracle.verifier_bindings(inert_shell, root, root),
            "shell -c cannot use a trusted path as an inert argument",
        )

        launcher_only = contract(
            [command(
                "launcher-only-binding",
                ["sh", "verifiers/itd_py.sh", "--itd-isolated", "other.py"],
                "exit_code_zero",
                "",
                ["verifiers/itd_py.sh"],
            )],
            [],
        )
        expect_oracle_error(
            lambda: oracle.verifier_bindings(launcher_only, root, root),
            "isolated launcher cannot authorize an unbound verifier",
        )

        for parser, expected in (
            ("stdout_contains", ""),
            ("unknown_parser", "pass"),
        ):
            invalid_expected = contract(
                [command(
                    "invalid-expected",
                    [sys.executable, "-I", "verifiers/verifier.py"],
                    parser,
                    expected,
                )],
                [],
            )
            contract_path.write_text(
                json.dumps(invalid_expected),
                encoding="utf-8",
            )
            expect_oracle_error(
                lambda: oracle.load_contract(contract_path),
                "ambiguous or unknown parser expectation is rejected",
            )

        expect_oracle_error(
            lambda: oracle.verifier_bindings(
                contract(
                    [command(
                        "exact-file-shell",
                        ["sh", "verifiers/verifier.py"],
                        "exit_code_zero",
                        "",
                        ["verifiers/verifier.py"],
                    )],
                    [],
                ),
                root,
                root,
            ),
            "non-isolated exact-file verifier binding is rejected",
        )


class oracle_environment:
    def __enter__(self):
        provider_credential_name = "OPENAI" + "_API_KEY"
        self.values = {
            provider_credential_name: "must-not-reach-child",
            "GITHUB_ENV": "/tmp/must-not-reach-child",
            "GITHUB_PATH": "/tmp/must-not-reach-child",
            "GITHUB_OUTPUT": "/tmp/must-not-reach-child",
            "GITHUB_STEP_SUMMARY": "/tmp/must-not-reach-child",
            "RUNNER_TEMP": "/tmp/must-not-reach-child",
        }
        self.previous = {
            name: os.environ.get(name) for name in self.values
        }
        os.environ.update(self.values)

    def __exit__(self, exc_type, exc, traceback):
        for name, value in self.previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def bounded_output_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-machine-output-") as raw:
        with mock.patch.dict(
            oracle.os.environ,
            {"PATH": str(Path(raw))},
        ):
            trusted = oracle.run_argv(
                ["python3", "-c", "print('trusted-runtime')"],
                cwd=Path(raw),
                timeout=10,
                max_output_bytes=1024,
            )
        check(
            trusted["stdout"].strip() == b"trusted-runtime"
            and Path(trusted["runtimePath"]).resolve()
            == Path(sys.executable).resolve()
            and len(trusted["runtimeSha256"]) == 64,
            "poisoned PATH cannot substitute the bound runtime",
        )
        result = oracle.run_argv(
            [sys.executable, "-c", "print('x' * 100000)"],
            cwd=Path(raw),
            timeout=10,
            max_output_bytes=1024,
        )
        check(result["outputOverflow"] is True, "output overflow detected")
        check(len(result["stdout"]) <= 1024, "captured output bounded")
        argv = oracle.run_argv(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.write('x' * 100000)",
            ],
            cwd=Path(raw),
            timeout=10,
            max_output_bytes=1024,
        )
        check(argv["outputOverflow"] is True, "argv output overflow detected")
        check(
            len(argv["stdout"]) + len(argv["stderr"]) <= 1024,
            "combined argv capture bounded",
        )


def windows_process_tree_phase() -> None:
    class Process:
        pid = 9123

        def __init__(self) -> None:
            self.killed = False

        def poll(self):
            return None

        def kill(self) -> None:
            self.killed = True

    process = Process()
    with (
        mock.patch.object(oracle.os, "name", "nt"),
        mock.patch.object(oracle.subprocess, "run") as taskkill,
    ):
        oracle._terminate(process)
    arguments = taskkill.call_args.args[0]
    check(
        arguments == ["taskkill", "/PID", "9123", "/T", "/F"],
        "Windows process tree terminated",
    )
    check(process.killed, "Windows parent kill is enforced")


def receipt_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-machine-receipt-") as raw:
        path = Path(raw) / "receipt.json"
        oracle.write_receipt(path, {"status": "PASSED"})
        if oracle.os.name != "nt":
            mode = stat.S_IMODE(path.stat().st_mode)
            check(mode == 0o600, "receipt permissions")
        check(json.loads(path.read_text())["status"] == "PASSED", "receipt written")


def required_workflow_phase() -> None:
    workflow = (
        ROOT / "docs/templates/github/itd-machine-oracle.yml"
    ).read_text(encoding="utf-8")
    check(
        "repository: hihol-labs/idea-to-deploy" in workflow
        and "ref: ${{ github.workflow_sha }}" in workflow
        and "WORKFLOW_REF: ${{ github.workflow_ref }}" in workflow
        and "hihol-labs/idea-to-deploy/.github/workflows/"
        "itd-machine-oracle.yml@*" in workflow,
        "required workflow loads its pinned central control plane",
    )
    check(
        "path: protected-base" in workflow
        and "github.event.pull_request.base.sha" in workflow,
        "required workflow materializes the protected target base",
    )
    check(
        "python3 -I control/scripts/itd_machine_oracle.py" in workflow
        and "--trusted-contract-root protected-base" in workflow,
        "candidate cannot substitute the oracle runner or contract source",
    )
    check(
        "python3 scripts/itd_machine_oracle.py" not in workflow,
        "required workflow never executes a candidate-owned oracle runner",
    )
    quick = (ROOT / "tests/verify_quick_regression.py").read_text(
        encoding="utf-8"
    )
    check(
        "oracle.run_argv(" in quick
        and "max_output_bytes=oracle.MAX_OUTPUT_BYTES" in quick,
        "quick verifier delegates every child to bounded oracle capture",
    )


def main() -> int:
    expect_oracle_error(
        lambda: oracle.safe_relative("C:/outside", "required artifact"),
        "Windows drive-absolute paths are unsafe",
    )
    repository_phase()
    protected_base_contract_phase()
    contract_trust_schema_phase()
    bounded_output_phase()
    windows_process_tree_phase()
    receipt_phase()
    required_workflow_phase()
    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
