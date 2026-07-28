#!/usr/bin/env python3
"""Behavioral and tamper oracle for captured-run schema/replay."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "_shared" / "itd_captured_run.py"
SCHEMA = ROOT / "docs" / "examples" / "brownfield-piv" / "manifest.schema.json"
CANONICAL_MANIFEST = ROOT / "docs" / "examples" / "brownfield-piv" / "manifest.json"


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(manifest: pathlib.Path, action: str = "validate",
            extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(RUNNER), action, "--manifest", str(manifest)],
        capture_output=True, text=True, timeout=120, env=environment)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(args: list[str], cwd: pathlib.Path) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                            text=True, timeout=30)
    require(result.returncode == 0, result.stdout + result.stderr)
    return result.stdout.strip()


def write_json(path: pathlib.Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
                    + "\n", encoding="utf-8")


def expected_tree(before: pathlib.Path, patch: pathlib.Path,
                  paths: list[str]) -> str:
    with tempfile.TemporaryDirectory(prefix="itd-capture-tree-") as raw:
        fixture = pathlib.Path(raw) / "project"
        shutil.copytree(before, fixture)
        git(["init", "-q"], fixture)
        git(["config", "user.email", "fixture@example.invalid"], fixture)
        git(["config", "user.name", "ITD Capture"], fixture)
        git(["add", "--", *paths], fixture)
        git(["commit", "-qm", "base"], fixture)
        git(["apply", str(patch)], fixture)
        git(["add", "--", *paths], fixture)
        return git(["write-tree"], fixture)


def main() -> int:
    require(RUNNER.is_file() and SCHEMA.is_file(),
            "captured-run runner or schema is missing")
    with tempfile.TemporaryDirectory(prefix="itd-capture-schema-") as raw:
        example = pathlib.Path(raw) / "example"
        example.mkdir()
        shutil.copy2(SCHEMA, example / "manifest.schema.json")
        before = example / "before"
        (before / "tests").mkdir(parents=True)
        (before / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        (before / "calc.py").write_text(
            "def total(values):\n    return sum(values) + 1\n", encoding="utf-8")
        (before / "tests" / "test_calc.py").write_text(
            "import unittest\nfrom calc import total\n\n"
            "class TotalTest(unittest.TestCase):\n"
            "    def test_total(self):\n        self.assertEqual(total([1, 2]), 3)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
        patch = example / "patch.diff"
        patch.write_text(
            "diff --git a/calc.py b/calc.py\n"
            "--- a/calc.py\n+++ b/calc.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def total(values):\n"
            "-    return sum(values) + 1\n"
            "+    return sum(values)\n", encoding="utf-8")

        artifacts_dir = example / "artifacts"
        artifacts_dir.mkdir()
        artifact_content = {
            "ticket.md": "# Ticket\nFix total off-by-one.\n",
            "context.json": '{"authority":"derived-non-normative"}\n',
            "task-contract.md": "# Task\nRepair total and preserve API.\n",
            "machine.json": '{"kind":"machine-verification"}\n',
            "checker.json": '{"kind":"checker"}\n',
            "adjudication.json": '{"kind":"adjudication"}\n',
            "review.md": "# Review\nSchema fixture only.\n",
            "metrics.json": '{"replay":1}\n',
        }
        for name, content in artifact_content.items():
            (artifacts_dir / name).write_text(content, encoding="utf-8")
        tracked = [".gitignore", "calc.py", "tests/test_calc.py"]
        tree = expected_tree(before, patch, tracked)
        artifact_paths = {
            "ticketSha256": "artifacts/ticket.md",
            "contextSha256": "artifacts/context.json",
            "taskContractSha256": "artifacts/task-contract.md",
            "patchSha256": "patch.diff",
            "machineReceiptSha256": "artifacts/machine.json",
            "checkerReceiptSha256": "artifacts/checker.json",
            "adjudicationReceiptSha256": "artifacts/adjudication.json",
            "reviewReportSha256": "artifacts/review.md",
            "metricsSha256": "artifacts/metrics.json",
        }
        artifacts = {
            relative: sha(example / relative)
            for relative in artifact_paths.values()
        }
        manifest = {
            "version": 1,
            "externalAdoptionEvidence": False,
            "schema": {
                "path": "manifest.schema.json",
                "sha256": sha(example / "manifest.schema.json"),
            },
            "bindings": {
                "candidateTree": tree,
                **{binding: artifacts[relative]
                   for binding, relative in artifact_paths.items()},
            },
            "bindingArtifacts": artifact_paths,
            "artifacts": artifacts,
            "replay": {
                "beforeDir": "before",
                "patch": "patch.diff",
                "baseTrackedPaths": tracked,
                "trackedPaths": tracked,
                "commands": [[
                    "{python}", "-B", "-m", "unittest", "discover",
                    "-s", "tests", "-v"
                ]],
            },
            "normalization": {
                "volatileFields": ["createdAt", "producerRunId", "receiptSha256"],
                "receiptSemantics": "canonical",
            },
        }
        manifest_path = example / "manifest.json"
        write_json(manifest_path, manifest)
        valid = execute(manifest_path)
        require(valid.returncode == 0, valid.stdout + valid.stderr)
        replayed = execute(CANONICAL_MANIFEST, "replay")
        require(replayed.returncode == 0, replayed.stdout + replayed.stderr)

        mutations: list[tuple[str, object]] = []
        missing = copy.deepcopy(manifest)
        missing["bindings"].pop("metricsSha256")
        mutations.append(("missing binding", missing))
        tampered = copy.deepcopy(manifest)
        tampered["artifacts"]["artifacts/ticket.md"] = "0" * 64
        mutations.append(("artifact tamper", tampered))
        escaped = copy.deepcopy(manifest)
        escaped["bindingArtifacts"]["ticketSha256"] = "../ticket.md"
        mutations.append(("path escape", escaped))
        shell_string = copy.deepcopy(manifest)
        shell_string["replay"]["commands"] = ["python -m unittest"]
        mutations.append(("shell string", shell_string))
        unbound_executable = copy.deepcopy(manifest)
        unbound_executable["replay"]["commands"] = [["python3", "-V"]]
        mutations.append(("unbound executable", unbound_executable))
        arbitrary_module = copy.deepcopy(manifest)
        arbitrary_module["replay"]["commands"] = [["{python}", "-m", "http.server"]]
        mutations.append(("arbitrary Python module", arbitrary_module))
        arbitrary_file = copy.deepcopy(manifest)
        arbitrary_file["replay"]["commands"] = [["{python}", "/tmp/payload.py"]]
        mutations.append(("arbitrary Python file", arbitrary_file))
        windows_escape = copy.deepcopy(manifest)
        windows_escape["replay"]["trackedPaths"] = ["..\\outside.txt"]
        mutations.append(("Windows path escape", windows_escape))
        drive_escape = copy.deepcopy(manifest)
        drive_escape["replay"]["beforeDir"] = "C:outside"
        mutations.append(("drive-relative path escape", drive_escape))
        overclaim = copy.deepcopy(manifest)
        overclaim["externalAdoptionEvidence"] = True
        mutations.append(("external overclaim", overclaim))
        wrong_mapping = copy.deepcopy(manifest)
        wrong_mapping["bindingArtifacts"]["ticketSha256"] = "artifacts/context.json"
        mutations.append(("binding substitution", wrong_mapping))
        duplicate_mapping = copy.deepcopy(manifest)
        duplicate_mapping["bindingArtifacts"]["ticketSha256"] = \
            duplicate_mapping["bindingArtifacts"]["contextSha256"]
        duplicate_mapping["bindings"]["ticketSha256"] = \
            duplicate_mapping["bindings"]["contextSha256"]
        mutations.append(("duplicate semantic artifact", duplicate_mapping))
        for index, (label, mutant) in enumerate(mutations):
            mutant_path = example / f"mutant-{index}.json"
            write_json(mutant_path, mutant)
            result = execute(mutant_path)
            require(result.returncode != 0, f"{label} mutation passed")

        ignored_extra = before / "ignored.pyc"
        ignored_extra.write_text("undeclared", encoding="utf-8")
        result = execute(manifest_path, "replay")
        require(result.returncode != 0, "ignored undeclared input passed replay")
        ignored_extra.unlink()

        side_effect = copy.deepcopy(manifest)
        side_effect["replay"]["commands"] = [[
            "{python}", "-c",
            "import calc,pathlib; ok=calc.total([1,2])==3; "
            "pathlib.Path('side-effect').write_text('x') if ok else None; "
            "raise SystemExit(0 if ok else 1)",
        ]]
        side_effect_path = example / "side-effect.json"
        write_json(side_effect_path, side_effect)
        result = execute(side_effect_path, "replay")
        require(result.returncode != 0, "post-check side effect passed replay")

        secret_probe = copy.deepcopy(manifest)
        secret_probe["replay"]["commands"] = [[
            "{python}", "-c",
            "import calc,os; ok=calc.total([1,2])==3 and "
            "'ITD_CAPTURE_TEST_SECRET' not in os.environ; "
            "raise SystemExit(0 if ok else 1)",
        ]]
        secret_probe_path = example / "secret-probe.json"
        write_json(secret_probe_path, secret_probe)
        result = execute(
            secret_probe_path, "replay",
            {"ITD_CAPTURE_TEST_SECRET": "must-not-cross-boundary"})
        require(result.returncode != 0,
                "caller-authored Python probe escaped the trusted replay boundary")

        symlink_case_count = 0
        symlink_path = before / "linked-outside"
        try:
            symlink_path.symlink_to(example, target_is_directory=True)
        except (NotImplementedError, OSError):
            pass
        else:
            symlink_case_count = 1
            result = execute(manifest_path, "replay")
            require(result.returncode != 0, "symlinked before tree passed replay")
            symlink_path.unlink()

        wrong_tree = copy.deepcopy(manifest)
        wrong_tree["bindings"]["candidateTree"] = "0" * 40
        wrong_tree_path = example / "wrong-tree.json"
        write_json(wrong_tree_path, wrong_tree)
        result = execute(wrong_tree_path, "replay")
        require(result.returncode != 0, "wrong replay tree passed")

    print(json.dumps({"negativeCases": 16 + symlink_case_count, "replays": 1,
                      "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
