#!/usr/bin/env python3
"""Regression oracle for the content-bound installed ITD runtime."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
CHECKS = 0


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime = load(
    "itd_install_runtime_test", SCRIPTS / "itd_install_runtime.py"
)
cli = load("itd_install_cli_runtime_test", SCRIPTS / "itd_install_cli.py")
hooks = load(
    "itd_install_git_hooks_runtime_test",
    SCRIPTS / "itd_install_git_hooks.py",
)


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
    except runtime.RuntimeInstallError:
        return
    raise AssertionError(label)


def source_fixture(root: Path) -> Path:
    source = root / "source"
    for relative in runtime.RUNTIME_FILES:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative in {
            ".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
        }:
            target.write_text(json.dumps({
                "name": "idea-to-deploy", "version": "1.100.0",
            }) + "\n", encoding="utf-8")
        else:
            target.write_text(f"fixture:{relative}\n", encoding="utf-8")
    return source


def main() -> int:
    actual_shared = {
        path.name for path in (ROOT / "skills" / "_shared").iterdir()
        if path.is_file() and path.suffix in {".py", ".json"}
    }
    check(
        actual_shared == set(runtime.RUNTIME_SHARED_FILES),
        "runtime declares every shared Python/policy file exactly",
    )
    with tempfile.TemporaryDirectory(prefix="itd-runtime-install-") as raw:
        root = Path(raw).resolve()
        source = source_fixture(root)
        parent = root / "runtime"

        preview = runtime.install_runtime(
            source_root=source, runtime_parent=parent, apply=False
        )
        runtime_root = Path(preview["runtimeRoot"])
        check(preview["status"] == "PREVIEW", "runtime preview is typed")
        check(not parent.exists(), "runtime preview writes nothing")
        check(
            runtime_root.name.startswith("1.100.0-")
            and preview["release"] == "1.100.0",
            "runtime path binds canonical release identity",
        )
        check(
            len(preview["runtimeSha256"]) == 64,
            "runtime preview exposes the aggregate digest",
        )

        installed = runtime.install_runtime(
            source_root=source, runtime_parent=parent, apply=True
        )
        check(installed["status"] == "INSTALLED", "runtime installs")
        check(runtime_root.is_dir(), "runtime target exists")
        manifest = json.loads(
            (runtime_root / runtime.RUNTIME_MANIFEST).read_text(encoding="utf-8")
        )
        check(
            manifest["runtimeSha256"] == preview["runtimeSha256"]
            and {row["path"] for row in manifest["files"]}
            == set(runtime.RUNTIME_FILES),
            "runtime manifest binds the exact closed inventory",
        )
        check(
            runtime.validate_runtime(runtime_root, manifest) == manifest,
            "installed runtime validates byte-for-byte",
        )
        reused = runtime.install_runtime(
            source_root=source, runtime_parent=parent, apply=True
        )
        check(reused["status"] == "REUSED", "exact reinstall is idempotent")

        entry = runtime_root / "scripts" / "itd.py"
        original = entry.read_bytes()
        entry.chmod(0o600)
        entry.write_bytes(b"tampered\n")
        rejects(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=False
            ),
            "preview also refuses a tampered existing runtime",
        )
        rejects(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=True
            ),
            "tampered existing runtime is refused",
        )
        check(entry.read_bytes() == b"tampered\n", "tamper is not overwritten")
        entry.write_bytes(original)
        entry.chmod(0o400)
        extra = runtime_root / "foreign.py"
        extra.write_text("foreign\n", encoding="utf-8")
        rejects(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=True
            ),
            "extra runtime file is refused",
        )
        extra.unlink()
        extra_dir = runtime_root / "empty-extra-directory"
        extra_dir.mkdir()
        rejects(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=False
            ),
            "extra runtime directory is refused",
        )
        extra_dir.rmdir()
        real_is_symlink = Path.is_symlink
        with mock.patch.object(
            Path,
            "is_symlink",
            lambda path: path == runtime_root or real_is_symlink(path),
        ):
            rejects(
                lambda: runtime.validate_runtime(runtime_root, manifest),
                "a symlinked runtime root is refused before resolution",
            )
        with mock.patch.object(
            Path,
            "is_symlink",
            lambda path: path == parent or real_is_symlink(path),
        ):
            rejects(
                lambda: runtime.install_runtime(
                    source_root=source, runtime_parent=parent, apply=False
                ),
                "a symlinked runtime parent is refused before planning",
            )

        changed = source_fixture(root / "changed")
        (changed / "scripts" / "itd.py").write_text(
            "changed runtime\n", encoding="utf-8"
        )
        changed_preview = runtime.install_runtime(
            source_root=changed, runtime_parent=parent, apply=False
        )
        check(
            changed_preview["runtimeRoot"] != preview["runtimeRoot"],
            "one runtime byte changes the content address",
        )
        missing = source_fixture(root / "missing")
        (missing / runtime.RUNTIME_FILES[-1]).unlink()
        rejects(
            lambda: runtime.install_runtime(
                source_root=missing, runtime_parent=parent, apply=False
            ),
            "missing declared source file is refused",
        )

        selected = (Path(sys.executable).resolve(), "test", "explicit")
        cli_target = root / "bin" / "itd"
        with mock.patch.object(cli, "select_runtime", return_value=selected):
            cli_result = cli.install(
                cli_target, apply=True, replace_existing=False,
                update_path=False, python=selected[0], source_root=source,
                runtime_parent=parent,
            )
        hook_target = root / "hooks"
        configured: list[tuple[str, ...]] = []

        def git_config(*arguments: str, check: bool = True) -> str:
            del check
            configured.append(arguments)
            if arguments == ("--get", "core.hooksPath"):
                return hook_target.as_posix() if len(configured) > 1 else ""
            return ""

        with (
            mock.patch.object(hooks, "select_runtime", return_value=selected),
            mock.patch.object(hooks, "git_config", side_effect=git_config),
        ):
            hook_result = hooks.install(
                hook_target, apply=True, replace_existing=False,
                python=selected[0], source_root=source,
                runtime_parent=parent,
            )
        cli_bytes = cli_target.read_text(encoding="utf-8")
        hook_bytes = (hook_target / "pre-push").read_text(encoding="utf-8")
        check(
            cli_result["runtimeRoot"] == hook_result["runtimeRoot"]
            == str(runtime_root),
            "CLI and pre-push use one runtime identity",
        )
        check(
            str(source) not in cli_bytes + hook_bytes,
            "wrappers do not retain the mutable source checkout",
        )
        check(
            (runtime_root / "scripts" / "itd.py").as_posix()
            in cli_bytes.replace("\\", "/")
            and (runtime_root / "scripts" / "itd_pre_push.py").as_posix()
            in hook_bytes.replace("\\", "/"),
            "wrappers name only deployed runtime entry points",
        )
        check(
            " -I -B " in cli_bytes and " -I -B " in hook_bytes,
            "runtime entry points disable ambient imports and bytecode writes",
        )

        real_parent = root / "real-runtime"
        real_target = root / "real-bin" / (
            "itd.cmd" if os.name == "nt" else "itd"
        )
        real_cli = cli.install(
            real_target, apply=True, replace_existing=False,
            update_path=False, python=Path(sys.executable), source_root=ROOT,
            runtime_parent=real_parent,
        )
        help_command = (
            ["cmd.exe", "/d", "/c", str(real_target), "--help"]
            if os.name == "nt" else [str(real_target), "--help"]
        )
        help_result = subprocess.run(
            help_command, capture_output=True, text=True,
            timeout=30, check=False,
        )
        check(
            help_result.returncode == 0
            and "{gate,pr}" in help_result.stdout,
            "installed real CLI runs from the isolated runtime",
        )
        push_result = subprocess.run(
            [
                sys.executable, "-I", "-B",
                str(Path(real_cli["runtimeRoot"]) / "scripts" / "itd_pre_push.py"),
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        check(
            push_result.returncode == 1 and "BLOCKED:" in push_result.stderr,
            "installed real pre-push entrypoint runs and fails closed",
        )
        check(
            not list(Path(real_cli["runtimeRoot"]).rglob("__pycache__")),
            "isolated runtime execution writes no bytecode cache",
        )

    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
