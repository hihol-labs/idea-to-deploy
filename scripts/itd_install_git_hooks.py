#!/usr/bin/env python3
"""Install the ITD pre-push UX guard as a host-global Git hooksPath."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRE_PUSH = ROOT / "scripts" / "itd_pre_push.py"
MAX_GIT_OUTPUT = 32768
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import itd_install_cli as cli_runtime  # noqa: E402
import itd_install_runtime as runtime_install  # noqa: E402


class InstallError(RuntimeError):
    pass


def run_bounded_process(
    command: list[str],
    *,
    output_limit: int,
    timeout: float,
) -> subprocess.CompletedProcess[bytes]:
    """Run a child while bounding each captured output stream in memory."""
    if output_limit <= 0 or timeout <= 0:
        raise InstallError("bounded child process limits are invalid")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise InstallError("global Git configuration is unavailable") from exc

    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()
    reader_errors: list[OSError] = []

    def read_stream(name: str, stream) -> None:
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                destination = outputs[name]
                allowance = output_limit + 1 - len(destination)
                if allowance > 0:
                    destination.extend(chunk[:allowance])
                if len(destination) > output_limit:
                    overflow.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    return
        except OSError as exc:
            reader_errors.append(exc)
            try:
                process.kill()
            except OSError:
                pass

    assert process.stdout is not None and process.stderr is not None
    readers = [
        threading.Thread(
            target=read_stream,
            args=(name, stream),
            name=f"itd-git-{name}",
            daemon=True,
        )
        for name, stream in (
            ("stdout", process.stdout),
            ("stderr", process.stderr),
        )
    ]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    for reader in readers:
        reader.join()

    if timed_out:
        raise InstallError("global Git configuration timed out")
    if overflow.is_set():
        raise InstallError("global Git configuration output is too large")
    if reader_errors:
        raise InstallError("global Git configuration output is unavailable")
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        bytes(outputs["stdout"]),
        bytes(outputs["stderr"]),
    )


def select_runtime(
    requested: Path | None,
) -> tuple[Path, str, str]:
    try:
        return cli_runtime.select_runtime(requested)
    except cli_runtime.InstallError as exc:
        raise InstallError(str(exc)) from exc


def default_target() -> Path:
    if os.name == "nt":
        base = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
        )
        return (base / "ITD" / "git-hooks").resolve()
    return (Path.home() / ".config" / "itd" / "git-hooks").resolve()


def git_config(*arguments: str, check: bool = True) -> str:
    completed = run_bounded_process(
        ["git", "config", "--global", *arguments],
        output_limit=MAX_GIT_OUTPUT,
        timeout=20,
    )
    if check and completed.returncode != 0:
        reason = completed.stderr.decode("utf-8", errors="replace").strip()
        raise InstallError(
            "global Git configuration failed"
            + (f": {reason[:1000]}" if reason else "")
        )
    if completed.returncode != 0:
        return ""
    return completed.stdout.decode("utf-8", errors="strict").strip()


def wrapper(python: Path, script: Path) -> bytes:
    python_value = shlex.quote(python.as_posix())
    script_value = shlex.quote(script.as_posix())
    return (
        "#!/bin/sh\n"
        "set -eu\n"
        "git_dir=$(git rev-parse --git-dir)\n"
        "local_hook=$git_dir/hooks/pre-push\n"
        "if [ -x \"$local_hook\" ] && [ \"$local_hook\" != \"$0\" ]; then\n"
        "  \"$local_hook\" \"$@\"\n"
        "fi\n"
        f"exec {python_value} -I -B {script_value} \"$@\"\n"
    ).encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o700,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o700)
    finally:
        temporary.unlink(missing_ok=True)


def install(
    target: Path,
    *,
    apply: bool,
    replace_existing: bool,
    python: Path | None = None,
    script: Path | None = None,
    source_root: Path = ROOT,
    runtime_parent: Path | None = None,
) -> dict[str, object]:
    target = target.resolve()
    source_root = source_root.expanduser()
    source_script = (source_root / "scripts" / "itd_pre_push.py").resolve()
    if script is not None and script.resolve() != source_script:
        raise InstallError("ITD hook script is outside the declared runtime")
    python, cryptography_version, runtime_source = select_runtime(python)
    try:
        runtime = runtime_install.install_runtime(
            source_root=source_root, runtime_parent=runtime_parent, apply=False
        )
    except runtime_install.RuntimeInstallError as exc:
        raise InstallError(str(exc)) from exc
    runtime_script = (
        Path(str(runtime["runtimeRoot"])) / "scripts" / "itd_pre_push.py"
    )
    current = git_config("--get", "core.hooksPath", check=False)
    current_path = Path(current).expanduser().resolve() if current else None
    if (
        current_path is not None
        and current_path != target
        and not replace_existing
    ):
        raise InstallError(
            "a different global core.hooksPath is already configured; "
            "rerun with --replace-existing after preserving its hooks"
        )
    hook = target / "pre-push"
    expected = wrapper(python, runtime_script)
    if hook.exists():
        try:
            existing = hook.read_bytes()
        except OSError as exc:
            raise InstallError("existing pre-push hook is unreadable") from exc
        if existing != expected and not replace_existing:
            raise InstallError(
                "target pre-push hook differs; use --replace-existing only "
                "after reviewing the existing hook"
            )
    result: dict[str, object] = {
        "status": "PREVIEW",
        "target": str(target),
        "prePush": str(hook),
        "previousHooksPath": current,
        "python": str(python),
        "pythonSource": runtime_source,
        "cryptographyVersion": cryptography_version,
        "sourceScript": str(source_script),
        "script": str(runtime_script),
        "runtimeRoot": runtime["runtimeRoot"],
        "runtimeManifest": runtime["runtimeManifest"],
        "runtimeSha256": runtime["runtimeSha256"],
        "release": runtime["release"],
    }
    if not apply:
        return result
    try:
        deployed = runtime_install.install_runtime(
            source_root=source_root, runtime_parent=runtime_parent, apply=True
        )
    except runtime_install.RuntimeInstallError as exc:
        raise InstallError(str(exc)) from exc
    if deployed["runtimeRoot"] != result["runtimeRoot"]:
        raise InstallError("runtime identity changed during hook installation")
    atomic_write(hook, expected)
    git_config("core.hooksPath", target.as_posix())
    observed = git_config("--get", "core.hooksPath")
    if Path(observed).expanduser().resolve() != target:
        raise InstallError("global core.hooksPath did not persist exactly")
    result["status"] = "INSTALLED"
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Install the host-global ITD Git pre-push guard"
    )
    result.add_argument("--target", type=Path, default=default_target())
    result.add_argument("--python", type=Path)
    result.add_argument("--apply", action="store_true")
    result.add_argument("--replace-existing", action="store_true")
    result.add_argument("--runtime-parent", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value = install(
            args.target,
            apply=args.apply,
            replace_existing=args.replace_existing,
            python=args.python,
            runtime_parent=args.runtime_parent,
        )
    except (InstallError, OSError, UnicodeError) as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "reason": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
