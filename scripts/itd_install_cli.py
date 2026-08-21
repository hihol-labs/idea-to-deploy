#!/usr/bin/env python3
"""Install the host-global `itd` command without editing plugin caches."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "itd.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import itd_install_runtime as runtime_install  # noqa: E402


class InstallError(RuntimeError):
    pass


RUNTIME_PROBE = (
    "import cryptography;"
    "from cryptography.hazmat.primitives.asymmetric.ed25519 "
    "import Ed25519PrivateKey;"
    "Ed25519PrivateKey.generate();"
    "print(cryptography.__version__)"
)
MAX_RUNTIME_PROBE_OUTPUT = 4096
RUNTIME_PROBE_TIMEOUT_SECONDS = 15


def default_target() -> Path:
    if os.name == "nt":
        base = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
        )
        return (base / "ITD" / "bin" / "itd.cmd").resolve()
    return (Path.home() / ".local" / "bin" / "itd").resolve()


def codex_bundled_python() -> Path:
    return (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "python"
        / "python.exe"
    ).resolve()


def probe_runtime(python: Path) -> str:
    if not python.is_file():
        raise InstallError("ITD CLI Python runtime is missing")
    process: subprocess.Popen[bytes] | None = None
    output = bytearray()
    overflow = threading.Event()
    read_error: list[BaseException] = []
    try:
        process = subprocess.Popen(
            [str(python), "-I", "-c", RUNTIME_PROBE],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None

        def drain() -> None:
            try:
                while True:
                    chunk = process.stdout.read(512)
                    if not chunk:
                        return
                    remaining = MAX_RUNTIME_PROBE_OUTPUT - len(output)
                    output.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        overflow.set()
                        process.kill()
                        return
            except (OSError, ValueError) as exc:
                read_error.append(exc)
                process.kill()

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            process.wait(timeout=RUNTIME_PROBE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise InstallError("ITD CLI Python runtime probe timed out") from exc
        reader.join(timeout=1)
        if reader.is_alive():
            process.stdout.close()
            reader.join(timeout=1)
            raise InstallError("ITD CLI Python runtime probe pipe did not close")
        process.stdout.close()
    except (OSError, subprocess.SubprocessError) as exc:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        raise InstallError(
            "ITD CLI Python runtime cannot execute the cryptography probe"
        ) from exc
    if read_error:
        raise InstallError("ITD CLI Python runtime probe output failed")
    if overflow.is_set():
        raise InstallError("ITD CLI Python runtime probe output exceeds its bound")
    try:
        version = bytes(output).decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise InstallError(
            "ITD CLI Python runtime probe output is not UTF-8"
        ) from exc
    if (
        process is None
        or process.returncode != 0
        or not re.fullmatch(r"[0-9A-Za-z.+-]{1,64}", version)
    ):
        raise InstallError(
            "ITD CLI Python runtime lacks a working cryptography dependency"
        )
    return version


def select_runtime(requested: Path | None) -> tuple[Path, str, str]:
    if requested is not None:
        candidate = requested.resolve()
        return candidate, probe_runtime(candidate), "explicit"

    candidates: list[tuple[Path, str]] = [
        (Path(sys.executable).resolve(), "current"),
    ]
    if os.name == "nt":
        candidates.append((codex_bundled_python(), "codex-bundled"))
    seen: set[Path] = set()
    for candidate, source in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return candidate, probe_runtime(candidate), source
        except InstallError:
            continue
    raise InstallError(
        "no compatible ITD CLI Python runtime found; pass --python PATH "
        "to a runtime with cryptography installed"
    )


def wrapper(python: Path, script: Path) -> bytes:
    if os.name == "nt":
        return (
            "@echo off\r\n"
            f'"{python}" -I -B "{script}" %*\r\n'
        ).encode("utf-8")
    return (
        "#!/bin/sh\n"
        "set -eu\n"
        f"exec {shlex.quote(python.as_posix())} -I -B "
        f"{shlex.quote(script.as_posix())} \"$@\"\n"
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


def ensure_windows_user_path(directory: Path) -> bool:
    if os.name != "nt":
        return False
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        try:
            current, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, kind = "", winreg.REG_EXPAND_SZ
        if not isinstance(current, str):
            raise InstallError("Windows user Path registry value is invalid")
        parts = [item for item in current.split(";") if item]
        normalized = {os.path.normcase(os.path.normpath(item)) for item in parts}
        target = os.path.normcase(os.path.normpath(str(directory)))
        if target in normalized:
            return False
        parts.append(str(directory))
        winreg.SetValueEx(
            key,
            "Path",
            0,
            kind if kind in {winreg.REG_SZ, winreg.REG_EXPAND_SZ}
            else winreg.REG_EXPAND_SZ,
            ";".join(parts),
        )
    return True


def install(
    target: Path,
    *,
    apply: bool,
    replace_existing: bool,
    update_path: bool,
    python: Path | None = None,
    script: Path | None = None,
    source_root: Path = ROOT,
    runtime_parent: Path | None = None,
) -> dict[str, object]:
    target = target.resolve()
    source_root = source_root.expanduser()
    source_script = (source_root / "scripts" / "itd.py").resolve()
    if script is not None and script.resolve() != source_script:
        raise InstallError("ITD CLI script is outside the declared runtime")
    python, cryptography_version, runtime_source = select_runtime(python)
    try:
        runtime = runtime_install.install_runtime(
            source_root=source_root, runtime_parent=runtime_parent, apply=False
        )
    except runtime_install.RuntimeInstallError as exc:
        raise InstallError(str(exc)) from exc
    runtime_script = Path(str(runtime["runtimeRoot"])) / "scripts" / "itd.py"
    expected = wrapper(python, runtime_script)
    if target.exists():
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise InstallError("existing ITD command is unreadable") from exc
        if existing != expected and not replace_existing:
            raise InstallError(
                "existing ITD command differs; use --replace-existing only "
                "after reviewing it"
            )
    result: dict[str, object] = {
        "status": "PREVIEW",
        "command": str(target),
        "python": str(python),
        "pythonSource": runtime_source,
        "cryptographyVersion": cryptography_version,
        "sourceScript": str(source_script),
        "script": str(runtime_script),
        "runtimeRoot": runtime["runtimeRoot"],
        "runtimeManifest": runtime["runtimeManifest"],
        "runtimeSha256": runtime["runtimeSha256"],
        "release": runtime["release"],
        "pathUpdateRequired": os.name == "nt",
        "pathUpdated": False,
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
        raise InstallError("runtime identity changed during CLI installation")
    atomic_write(target, expected)
    if update_path:
        result["pathUpdated"] = ensure_windows_user_path(target.parent)
    result["status"] = "INSTALLED"
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Install the host-global ITD command"
    )
    result.add_argument("--target", type=Path, default=default_target())
    result.add_argument(
        "--python",
        type=Path,
        help=(
            "override automatic selection with a Python runtime carrying "
            "the ITD cryptography dependency"
        ),
    )
    result.add_argument("--apply", action="store_true")
    result.add_argument("--replace-existing", action="store_true")
    result.add_argument("--no-path-update", action="store_true")
    result.add_argument("--runtime-parent", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value = install(
            args.target,
            apply=args.apply,
            replace_existing=args.replace_existing,
            update_path=not args.no_path_update,
            python=args.python,
            runtime_parent=args.runtime_parent,
        )
    except (InstallError, OSError) as exc:
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
