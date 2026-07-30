#!/usr/bin/env python3
"""Install the host-global `itd` command without editing plugin caches."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "itd.py"


class InstallError(RuntimeError):
    pass


def default_target() -> Path:
    if os.name == "nt":
        base = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
        )
        return (base / "ITD" / "bin" / "itd.cmd").resolve()
    return (Path.home() / ".local" / "bin" / "itd").resolve()


def wrapper(python: Path, script: Path) -> bytes:
    if os.name == "nt":
        return (
            "@echo off\r\n"
            f'"{python}" "{script}" %*\r\n'
        ).encode("utf-8")
    return (
        "#!/bin/sh\n"
        "set -eu\n"
        f"exec {shlex.quote(python.as_posix())} "
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
    script: Path = CLI,
) -> dict[str, object]:
    target = target.resolve()
    python = (python or Path(sys.executable)).resolve()
    script = script.resolve()
    if not python.is_file() or not script.is_file():
        raise InstallError("ITD CLI runtime or Python executable is missing")
    expected = wrapper(python, script)
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
        "script": str(script),
        "pathUpdateRequired": os.name == "nt",
        "pathUpdated": False,
    }
    if not apply:
        return result
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
        help="Python runtime that carries the ITD cryptography dependency",
    )
    result.add_argument("--apply", action="store_true")
    result.add_argument("--replace-existing", action="store_true")
    result.add_argument("--no-path-update", action="store_true")
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
