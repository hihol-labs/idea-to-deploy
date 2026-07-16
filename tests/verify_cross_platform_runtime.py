#!/usr/bin/env python3
"""Behavioural runtime matrix across native, PowerShell, Git Bash and WSL/Linux."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "helpers" / "platform_runtime_probe.py"
CORPUS = ROOT / "benchmarks" / "cross-platform" / "CORPUS.json"
CORPUS_SHA = ROOT / "benchmarks" / "cross-platform" / "CORPUS.sha256"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(args: list[str], cwd: Path = ROOT, timeout: int = 120) -> tuple[int, str]:
    result = subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def last_json(output: str) -> dict | None:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def probe_passes(report: dict | None, contract: dict) -> bool:
    if not isinstance(report, dict) or report.get("status") != contract["requiredStatus"]:
        return False
    if report.get("manualRepairs") != contract["maxManualRepairs"]:
        return False
    return all(field in report for field in contract["requiredParityFields"])


def is_wsl() -> bool:
    # A native Windows process may run with a \\wsl.localhost UNC cwd.  In that
    # case Path('/proc/...') can resolve into the WSL share even though this
    # process is not running on the Linux kernel.  OS identity wins over an
    # accidentally reachable foreign procfs path.
    if os.name != "posix":
        return False
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def windows_path(path: Path) -> str | None:
    if os.name == "nt":
        return str(path)
    if not is_wsl() or not shutil.which("wslpath"):
        return None
    rc, out = run(["wslpath", "-w", str(path)], timeout=20)
    return out.strip() if rc == 0 and out.strip() else None


def powershell_executable() -> str | None:
    candidates = ("powershell.exe", "pwsh.exe") if os.name != "nt" else ("powershell", "pwsh")
    return next((path for name in candidates if (path := shutil.which(name))), None)


def run_powershell_probe() -> tuple[bool, str]:
    shell = powershell_executable()
    probe = windows_path(PROBE)
    if not shell or not probe:
        return False, "PowerShell or Windows path bridge unavailable"
    if os.name == "nt":
        python = str(Path(sys.executable))
        command = f"& '{python.replace(chr(39), chr(39) * 2)}' '{probe.replace(chr(39), chr(39) * 2)}'"
    else:
        command = (
            "$py=(Get-Command py.exe -ErrorAction SilentlyContinue); "
            "if (-not $py) { exit 127 }; "
            f"& $py.Source -3 '{probe.replace(chr(39), chr(39) * 2)}'"
        )
    rc, out = run([shell, "-NoProfile", "-NonInteractive", "-Command", command], timeout=180)
    report = last_json(out)
    return rc == 0 and report is not None, out


def git_bash_executable() -> str | None:
    if os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "usr" / "bin" / "bash.exe",
        ]
    elif is_wsl():
        candidates = [
            Path("/mnt/c/Program Files/Git/bin/bash.exe"),
            Path("/mnt/c/Program Files/Git/usr/bin/bash.exe"),
        ]
    else:
        candidates = []
    return next((str(path) for path in candidates if path.is_file()), None)


def run_git_bash_probe() -> tuple[bool, str]:
    bash = git_bash_executable()
    probe = windows_path(PROBE)
    if not bash or not probe:
        return False, "Git Bash or Windows path bridge unavailable"
    if os.name == "nt":
        python = str(Path(sys.executable))
    else:
        ps = powershell_executable()
        if not ps:
            return False, "Windows Python discovery requires PowerShell"
        rc, python = run([ps, "-NoProfile", "-NonInteractive", "-Command",
                          "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
                          "$p=(Get-Command py.exe -ErrorAction SilentlyContinue); if ($p) {$p.Source}"], timeout=30)
        python = python.strip()
        if rc != 0 or not python:
            return False, "Windows py.exe unavailable"
    script = 'py=$(cygpath -u "$1"); probe=$(cygpath -u "$2"); "$py" -3 "$probe"'
    # python.exe ignores -3, while py.exe accepts it. Use the launcher in both
    # native Windows and WSL discovery for one stable Git Bash path.
    if Path(python).name.lower() != "py.exe":
        script = 'py=$(cygpath -u "$1"); probe=$(cygpath -u "$2"); "$py" "$probe"'
    rc, out = run([bash, "-lc", script, "_", python, probe], timeout=180)
    report = last_json(out)
    return rc == 0 and report is not None, out


def workflow_contract(text: str, runner: str) -> bool:
    return runner in text and "verify_cross_platform_runtime.py" in text


def main() -> int:
    raw = CORPUS.read_bytes()
    expected = CORPUS_SHA.read_text(encoding="utf-8").strip().split()[0]
    actual = hashlib.sha256(raw).hexdigest()
    check("cross-platform corpus seal matches", actual == expected,
          f"expected={expected} actual={actual}")
    corpus = json.loads(raw)
    contract = corpus["probeContract"]

    rc, native_out = run([sys.executable, str(PROBE)], timeout=180)
    native_report = last_json(native_out)
    check("native runtime probe passes", rc == 0 and probe_passes(native_report, contract),
          native_out[-1200:])
    if os.name == "posix":
        check("POSIX native path is required and executed", native_report is not None)
    if is_wsl():
        check("WSL/Linux path is identified from the kernel", "microsoft" in platform.release().lower())

    ps_available = powershell_executable() is not None and windows_path(PROBE) is not None
    ps_ok, ps_out = run_powershell_probe()
    if os.name == "nt" or ps_available:
        check("Windows PowerShell launch path passes", ps_ok and probe_passes(last_json(ps_out), contract),
              ps_out[-1200:])
    else:
        print("  SKIP Windows PowerShell — executable/path bridge unavailable in this environment")

    bash_binary_available = git_bash_executable() is not None and windows_path(PROBE) is not None
    bash_ok, bash_out = run_git_bash_probe()
    bash_runtime_available = bash_binary_available and not any(
        marker in bash_out for marker in (
            "Windows Python discovery requires PowerShell",
            "Windows py.exe unavailable",
        )
    )
    if os.name == "nt" or bash_runtime_available:
        check("Windows Git Bash launch path passes", bash_ok and probe_passes(last_json(bash_out), contract),
              bash_out[-1200:])
    else:
        print("  SKIP Windows Git Bash — complete bash+Windows-Python bridge unavailable")

    linux_workflow = (ROOT / ".github" / "workflows" / "meta-review.yml").read_text(encoding="utf-8")
    windows_workflow = (ROOT / ".github" / "workflows" / "windows-verify.yml").read_text(encoding="utf-8")
    check("Linux CI enforces the runtime matrix", workflow_contract(linux_workflow, "ubuntu-latest"))
    check("Windows CI enforces the runtime matrix", workflow_contract(windows_workflow, "windows-latest"))

    # Refute pass: each broken behavior must turn the oracle red.
    good = native_report or {}
    mutations = [
        dict(good, status="fail"),
        dict(good, manualRepairs=1),
        {key: value for key, value in good.items() if key != "codex"},
    ]
    check("probe-contract mutations are rejected",
          all(not probe_passes(value, contract) for value in mutations))
    check("missing Windows CI registration is rejected",
          not workflow_contract(windows_workflow.replace("verify_cross_platform_runtime.py", "removed.py"),
                                "windows-latest"))
    check("missing Linux CI registration is rejected",
          not workflow_contract(linux_workflow.replace("verify_cross_platform_runtime.py", "removed.py"),
                                "ubuntu-latest"))

    executed = ["native"]
    if os.name == "nt" or ps_available:
        executed.append("powershell")
    if os.name == "nt" or bash_runtime_available:
        executed.append("git-bash")
    if is_wsl():
        executed.append("wsl")
    print("METRICS " + json.dumps({
        "executedLaunchPaths": sorted(set(executed)),
        "manualRepairs": 0,
        "mutationGuards": len(corpus["mutationGuards"]),
        "ciRunners": ["ubuntu-latest", "windows-latest"],
    }, sort_keys=True))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS — available launch paths and CI matrix preserve one behavioural core")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
