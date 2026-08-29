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


def rejects_naming(fn, needles: tuple[str, ...], label: str) -> None:
    """Refusal must name the offending path and a FIX, not just say 'drifted'."""
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except runtime.RuntimeInstallError as exc:
        message = str(exc)
        if all(needle in message for needle in needles):
            return
        raise AssertionError(f"{label}: {message}") from None
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


HOOKS_LOADING_INSTALLED_MODULES = (
    ("check-review-before-commit.sh", "load_cache_module"),
    ("check-dod-before-commit.sh", "security_review_was_done"),
    ("pii-egress-guard.sh", "load_external_gate"),
)

# A hook runs from its own shebang, so the interpreter writes bytecode unless the
# hook forbids it. When the loaded module lives in the installed runtime, that
# .pyc lands INSIDE the content-addressed directory and the next reinstall dies
# on "installed runtime directory inventory drifted" (measured 2026-08-29:
# skills/review/scripts/__pycache__/itd_review_cache.cpython-312.pyc, 39 files
# against 38 in the manifest). The guarantee is behavioural: loading a module
# out of a runtime-shaped directory must leave that directory byte-identical.
BYTECODE_PROBE = """
import importlib.machinery, importlib.util, sys
target = sys.argv[1]
loader = importlib.machinery.SourceFileLoader("itd_bytecode_probe", target)
spec = importlib.util.spec_from_loader("itd_bytecode_probe", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
"""


def bytecode_written_by(source: str, module_path: Path, directory: Path) -> bool:
    """Run `source` in a child WITHOUT -B and report whether it left bytecode."""
    for stale in directory.rglob("__pycache__"):
        for item in stale.iterdir():
            item.unlink()
        stale.rmdir()
    subprocess.run(
        [sys.executable, "-I", "-c", source, str(module_path)],
        capture_output=True, text=True, timeout=30, check=False,
        cwd=str(directory),
    )
    return bool(list(directory.rglob("__pycache__")))


def main() -> int:
    for hook_name, symbol in HOOKS_LOADING_INSTALLED_MODULES:
        hook_source = (ROOT / "hooks" / hook_name).read_text(encoding="utf-8")
        check(
            symbol in hook_source,
            f"{hook_name} still loads an installed module through {symbol}",
        )
        check(
            "sys.dont_write_bytecode" in hook_source,
            f"{hook_name} forbids bytecode writes around the installed module load",
        )

    with tempfile.TemporaryDirectory(prefix="itd-bytecode-") as raw:
        probe_root = Path(raw).resolve()
        module_path = probe_root / "skills" / "review" / "scripts" / "probe_mod.py"
        module_path.parent.mkdir(parents=True)
        module_path.write_text("VALUE = 1\n", encoding="utf-8")
        # The unguarded loader is the defect: it proves the probe detects the
        # failure mode, so the guarded assertion below cannot pass vacuously.
        check(
            bytecode_written_by(BYTECODE_PROBE, module_path, probe_root),
            "the probe detects bytecode written by an unguarded module load",
        )
        check(
            not bytecode_written_by(
                "import sys\nsys.dont_write_bytecode = True\n" + BYTECODE_PROBE,
                module_path, probe_root,
            ),
            "forbidding bytecode keeps the runtime-shaped directory unchanged",
        )

    actual_shared = {
        path.name for path in (ROOT / "skills" / "_shared").iterdir()
        if path.is_file() and path.suffix in {".py", ".json"}
    }
    check(
        actual_shared == set(runtime.RUNTIME_SHARED_FILES),
        "runtime declares every shared Python/policy file exactly",
    )
    check(
        runtime.RUNTIME_SKILL_FILES
        == (
            "skills/review/scripts/itd_review_cache.py",
            "skills/review/SKILL.md",
            "skills/review/references/review-checklist.md",
            "skills/review/references/meta-review-checklist.md",
        ),
        "runtime declares the complete exact-context review dependency set",
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
        named = runtime_root / "foreign-named.py"
        named.write_text("foreign\n", encoding="utf-8")
        rejects_naming(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=True
            ),
            ("foreign-named.py", "FIX"),
            "extra-file refusal names the offending path and a FIX",
        )
        named.unlink()
        extra_dir = runtime_root / "empty-extra-directory"
        extra_dir.mkdir()
        rejects(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=False
            ),
            "extra runtime directory is refused",
        )
        extra_dir.rmdir()
        # The real 2026-08-29 failure: bytecode written by a hook that loaded a
        # module out of the installed runtime. The directory check must fire and
        # must say WHICH directory, otherwise the operator hunts it by hand.
        cache_dir = runtime_root / "skills" / "review" / "scripts" / "__pycache__"
        cache_dir.mkdir(parents=True)
        (cache_dir / "itd_review_cache.cpython-312.pyc").write_bytes(b"\x00")
        rejects_naming(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=True
            ),
            ("__pycache__", "FIX"),
            "stray bytecode refusal names the __pycache__ directory and a FIX",
        )
        (cache_dir / "itd_review_cache.cpython-312.pyc").unlink()
        cache_dir.rmdir()
        missing_probe = runtime_root / "skills" / "review" / "SKILL.md"
        missing_bytes = missing_probe.read_bytes()
        missing_probe.chmod(0o600)
        missing_probe.unlink()
        rejects_naming(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=True
            ),
            ("missing:", "skills/review/SKILL.md"),
            "missing-file refusal names what disappeared",
        )
        missing_probe.write_bytes(missing_bytes)
        missing_probe.chmod(0o400)
        # Reviewer finding r4: the diagnostic contract must cover EVERY strict
        # refusal branch, not the two that were easy to reach. A symlink and a
        # special file are refused just as hard, so they must name the path and
        # a FIX too — otherwise the operator is back to hunting by hand.
        link = runtime_root / "stray-link"
        link.symlink_to(runtime_root / "scripts" / "itd.py")
        rejects_naming(
            lambda: runtime.install_runtime(
                source_root=source, runtime_parent=parent, apply=True
            ),
            ("stray-link", "FIX"),
            "symlink refusal names the offending path and a FIX",
        )
        link.unlink()
        # Reviewer finding r8: os.mkfifo is Unix-only, and this suite also runs
        # on native Windows. Name the platform boundary instead of crashing on
        # it — the guarantee is exercised wherever a real special file can be
        # created, and the skip is printed, never silent.
        if hasattr(os, "mkfifo"):
            fifo = runtime_root / "stray-fifo"
            os.mkfifo(fifo)
            rejects_naming(
                lambda: runtime.install_runtime(
                    source_root=source, runtime_parent=parent, apply=True
                ),
                ("stray-fifo", "FIX"),
                "special-file refusal names the offending path and a FIX",
            )
            fifo.unlink()
        else:
            print(
                "SKIP  special-file refusal: os.mkfifo is unavailable on this "
                "platform; the symlink branch above still covers the "
                "path+FIX contract"
            )
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
        load_probe = (
            "import importlib.util, pathlib, sys; "
            "p=pathlib.Path(sys.argv[1]); "
            "s=importlib.util.spec_from_file_location('runtime_loop', p); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "m.candidate_context(sys.argv[2], 'high')"
        )
        dependency_result = subprocess.run(
            [
                sys.executable, "-I", "-B", "-c", load_probe,
                str(
                    Path(real_cli["runtimeRoot"])
                    / "skills" / "_shared" / "itd_verification_loop.py"
                ),
                str(ROOT),
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        check(
            dependency_result.returncode == 0,
            "installed verification loop computes an exact candidate context",
        )
        check(
            not list(Path(real_cli["runtimeRoot"]).rglob("__pycache__")),
            "isolated runtime execution writes no bytecode cache",
        )

    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
