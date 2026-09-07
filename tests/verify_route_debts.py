#!/usr/bin/env python3
"""ROUTE-DEBTS aggregate oracle and replay of declared native rollout evidence.

Default: focused source regressions. --host-metadata: portable metadata gates.
--installed-proof: additionally require real host-observed deployment artifacts.
Fixtures and native canaries establish engineering behavior, not empirical RSI gains.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import io
import platform
import hashlib
import importlib.util
import json
import os
import re
import stat
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
REGRESSIONS = (
    "tests/verify_review_evidence.py",
    "tests/verify_review_cache.py",
    "tests/verify_free_reviewer_producer.py",
    "tests/verify_stop_rule.py",
    "tests/verify_adjudication_channel.py",
    "tests/verify_verification_loop.py",
    "tests/verify_gate_control.py",
    "tests/verify_itd_cli.py",
    "tests/verify_risk_score.py",
    "tests/verify_itd_runtime_install.py",
    "tests/verify_unit_log.py",
    "tests/verify_goal_tools.py",
    "tests/verify_goal_bounded_autonomy.py",
    "tests/verify_blind_protocol.py",
)
HOST_METADATA = (
    "tests/verify_host_adapters.py",
    "tests/meta_review.py",
    "tests/verify_runall_drift.py",
    "tests/verify_verification_profiles.py",
)
ADAPTER_SOURCES = (
    "hooks/risk-score.sh",
    "skills/goal/scripts/itd_goal_verify.py",
    "skills/goal/SKILL.md",
    "skills/task/scripts/itd_unit_log.py",
    "skills/_shared/itd_safe_atomic.py",
    "skills/_shared/itd_safe_atomic_windows.py",
    "skills/_shared/itd_verification_loop.py",
    "skills/_shared/itd_free_reviewer_producer.py",
    "skills/_shared/itd_review_evidence.py",
    "skills/_shared/itd_gate_control.py",
)


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_file(path: Path) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{path}: duplicate key {key}")
            value[key] = item
        return value
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def local_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("native evidence path is missing")
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", raw):
        raw = "/mnt/" + raw[0].lower() + "/" + raw[3:].replace("\\", "/")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def referenced(proof_dir: Path, ref: object) -> Path:
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("evidence reference requires path and sha256")
    raw = Path(ref["path"])
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("evidence reference must stay under the proof directory")
    path = proof_dir / raw
    cursor = proof_dir
    for part in raw.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("linked evidence is forbidden")
    if not path.is_file() or sha(path) != ref["sha256"]:
        raise ValueError(f"evidence bytes missing or changed: {path}")
    return path


def load_proof(path: Path) -> tuple[dict, dict]:
    proof = object_file(path)
    if (set(proof) != {"version", "release", "runtimeSha256", "hosts"}
            or type(proof["version"]) is not int or proof["version"] != 2):
        raise ValueError("installed proof requires native-validation schema v2")
    installer = module("route_runtime_install", ROOT / "scripts/itd_install_runtime.py")
    _, _, expected = installer.runtime_plan(source_root=ROOT)
    if proof["release"] != expected["release"] or proof["runtimeSha256"] != expected["runtimeSha256"]:
        raise ValueError("installed proof does not bind the current source runtime")
    hosts = proof["hosts"]
    if (not isinstance(hosts, list) or len(hosts) != 2
            or {h.get("platform") for h in hosts if isinstance(h, dict)} != {"Linux", "Windows"}):
        raise ValueError("real Linux and Windows records are both required")
    return proof, expected


def native_test_command(log: Path) -> str:
    # Same native interpreter used by the installed wrappers; closed argv.
    if os.name == "nt":
        # WSL can preserve the input spelling ``C:\\WINDOWS`` while Windows
        # resolves it as ``C:\\Windows``. Bind a normalized spelling so a
        # native producer and native replay compare the exact same argv bytes.
        native_log = os.path.normcase(os.path.normpath(str(log.resolve())))
        return f'"{sys.executable}" -I -B tests/verify_route_debts.py --native-test-log "{native_log}"'
    import shlex
    return " ".join(shlex.quote(v) for v in
                    (sys.executable, "-I", "-B", "tests/verify_route_debts.py", "--native-test-log", str(log)))


def validate_wrapper(target: Path, ref: object, content: bytes) -> None:
    # The declared path must lexically equal the expected namespace entry and
    # the entry itself must be a plain regular file: resolving first would let
    # a symlink or junction to a foreign target satisfy the byte/hash checks
    # and leave the "active wrapper" mutable through that target (Sol-a9).
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("active native wrapper bytes/target differ")
    declared = os.path.normcase(os.path.normpath(str(ref["path"])))
    if declared != os.path.normcase(os.path.normpath(str(target))):
        raise ValueError("active native wrapper path is not the expected namespace entry")
    try:
        info = target.lstat()
    except OSError as exc:
        raise ValueError("active native wrapper is missing") from exc
    reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
    if stat.S_ISLNK(info.st_mode) or reparse or not stat.S_ISREG(info.st_mode):
        raise ValueError("active native wrapper is a link or not a regular file")
    atomic = module("route_wrapper_safe_atomic", ROOT / "skills/_shared/itd_safe_atomic.py")
    actual = atomic.read_regular_snapshot(target.absolute(), 1024 * 1024)
    if hashlib.sha256(actual).hexdigest() != ref["sha256"] or actual != content:
        raise ValueError("active native wrapper bytes/target differ")


def validate_adapter_row(row: object, base: Path) -> None:
    if not isinstance(row, dict) or set(row) != {"source", "installed", "sha256"}:
        raise ValueError("malformed adapter row")
    target = base / row["source"]
    if (target.is_symlink() or ROOT.resolve() in target.resolve().parents
            or Path(row["installed"]).resolve() != target.resolve()
            or row["sha256"] != sha(ROOT / row["source"]) or sha(target) != row["sha256"]):
        raise ValueError("active adapter path/source drift")


def validate_adapter_activation(release: str) -> None:
    settings = object_file(Path.home() / ".claude/settings.json")
    risk_command = "~/.claude/hooks/risk-score.sh"
    if os.name == "nt":
        risk_command = (f'"{Path(sys.executable).as_posix()}" -X utf8 '
                        f'"{(Path.home() / ".claude/hooks/risk-score.sh").as_posix()}"')
    expected_hook = {"type": "command", "command": risk_command, "timeout": 5}
    enabled = [hook for row in settings.get("hooks", {}).get("PostToolUse", [])
               if isinstance(row, dict) and row.get("matcher") == "*"
               for hook in row.get("hooks", []) if hook == expected_hook]
    if settings.get("disableAllHooks") is True or len(enabled) != 1:
        raise ValueError("Claude risk hook is not enabled with its native command")
    codex = (str(Path.home() / ".codex/plugins/.plugin-appserver/codex.exe") if os.name == "nt"
             else shutil.which("codex"))
    if not codex:
        raise ValueError("native Codex installation metadata CLI unavailable")
    result = subprocess.run([codex, "plugin", "list", "--marketplace", "personal", "--json"],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    if result.returncode:
        raise ValueError("cannot read native Codex plugin activation")
    selected = [r for r in json.loads(result.stdout).get("installed", [])
                if isinstance(r, dict) and r.get("pluginId") == "idea-to-deploy@personal"]
    if (len(selected) != 1 or selected[0].get("installed") is not True
            or selected[0].get("enabled") is not True or selected[0].get("version") != release):
        raise ValueError("Codex does not select the installed release")


def validate_selected_hooks(source_repo: Path, expected_target: Path) -> None:
    selected = subprocess.run(["git", "config", "--path", "--get", "core.hooksPath"],
                              cwd=source_repo, capture_output=True, text=True,
                              encoding="utf-8", errors="strict", timeout=10)
    if selected.returncode or Path(selected.stdout.strip()).resolve() != expected_target.resolve():
        raise ValueError("Git does not select the installed pre-push directory")


def validate_native_record(path: Path, host: dict, expected: dict) -> dict:
    """Full receipt replay must execute on the host whose shell/candidate it binds."""
    fields = {"platform", "runtimeRoot", "runtimeManifestSha256", "machine", "adjudication",
              "revalidationLog", "nativeTestsLog", "revalidationExitCode", "nativeTestsExitCode",
              "cliWrapper", "prePushWrapper", "adapters", "sourceRepository"}
    if set(host) != fields or host["platform"] != platform.system():
        raise ValueError("native record shape or executing host differs")
    if not isinstance(host["sourceRepository"], str) or not host["sourceRepository"].strip():
        raise ValueError("native source repository is missing")
    source_repo = Path(host["sourceRepository"])
    if not source_repo.is_absolute() or source_repo.is_symlink() or not source_repo.is_dir():
        raise ValueError("native source repository is not an absolute real directory")
    source_repo = source_repo.resolve()
    for field in ("revalidationExitCode", "nativeTestsExitCode"):
        if type(host[field]) is not int or host[field] != 0:
            raise ValueError(f"native {field} was not a success")
    runtime = Path(host["runtimeRoot"])
    installer = module("route_runtime_install", ROOT / "scripts/itd_install_runtime.py")
    if (not runtime.is_absolute() or runtime.parent.resolve() != installer.default_runtime_parent()
            or runtime.name != f"{expected['release']}-{expected['runtimeSha256'][:16]}"):
        raise ValueError("runtime is not the native content-addressed installation")
    installer.validate_runtime(runtime, expected)
    if sha(runtime / installer.RUNTIME_MANIFEST) != host["runtimeManifestSha256"]:
        raise ValueError("native runtime manifest binding differs")
    # Import the installed code after confirming every runtime byte against source.
    cli = module("route_native_cli", ROOT / "scripts/itd_install_cli.py")
    hooks = module("route_native_hooks", ROOT / "scripts/itd_install_git_hooks.py")
    for key, target, content in (
        ("cliWrapper", cli.default_target(), cli.wrapper(Path(sys.executable), runtime / "scripts/itd.py")),
        ("prePushWrapper", hooks.default_target() / "pre-push",
         hooks.wrapper(Path(sys.executable), runtime / "scripts/itd_pre_push.py")),
    ):
        validate_wrapper(target, host[key], content)
    validate_selected_hooks(source_repo, hooks.default_target())
    adapters = host["adapters"]
    if not isinstance(adapters, dict) or set(adapters) != {"claude", "codex"}:
        raise ValueError("Claude and Codex adapter inventories required")
    for adapter, rows in adapters.items():
        base = (Path.home() / ".claude" if adapter == "claude" else
                Path.home() / ".codex/plugins/cache/personal/idea-to-deploy" / expected["release"])
        if (not isinstance(rows, list) or len(rows) != len(ADAPTER_SOURCES)
                or {r.get("source") for r in rows if isinstance(r, dict)} != set(ADAPTER_SOURCES)):
            raise ValueError("incomplete adapter inventory")
        for row in rows:
            validate_adapter_row(row, base)
    validate_adapter_activation(expected["release"])
    loop = module("route_native_loop", runtime / "skills/_shared/itd_verification_loop.py")
    return validate_native_canary(
        path, host, expected, loop,
        native_source_candidate_repo(str(source_repo), loop),
    )


def native_source_candidate_repo(value: object, loop) -> Path:
    """Bind a host checkout to the isolated aggregate candidate by content."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("native source repository is missing")
    source_repo = Path(value)
    if not source_repo.is_absolute() or source_repo.is_symlink() or not source_repo.is_dir():
        raise ValueError("native source repository is not an absolute real directory")
    source_repo = source_repo.resolve()
    try:
        live = loop.candidate_context(source_repo, "low")
        isolated = loop.candidate_context(ROOT, "low")
    except Exception as exc:
        raise ValueError(f"native source candidate is unavailable: {exc}") from exc
    # The aggregate oracle runs from an isolated staged checkout, whereas a
    # native canary observes the active host checkout. Locations may differ,
    # but every content-bearing candidate fact must still match exactly.
    if ({k: v for k, v in live.items() if k != "repository"}
            != {k: v for k, v in isolated.items() if k != "repository"}):
        raise ValueError("native source candidate differs from the isolated staged candidate")
    return source_repo


def validate_native_canary(path: Path, host: dict, expected: dict, loop,
                           candidate_repo: Path | None = None) -> dict:
    unit = "ROUTE-DEBTS:deployment-canary"
    policy, policy_sha = loop.load_policy()
    candidate_repo = ROOT if candidate_repo is None else candidate_repo
    receipt_dir = loop.receipt_root(candidate_repo, policy)
    # Host inputs retain copied snapshots for the aggregate's declared input
    # boundary. The complete receipts must also still exist at their canonical
    # append-only Verification Loop locations, byte-for-byte identical.
    mp_snapshot = referenced(path.parent, host["machine"])
    ap_snapshot = referenced(path.parent, host["adjudication"])
    mp = referenced(receipt_dir, host["machine"])
    ap = referenced(receipt_dir, host["adjudication"])
    if sha(mp_snapshot) != sha(mp) or sha(ap_snapshot) != sha(ap):
        raise ValueError("native receipt snapshot differs from canonical receipt")
    machine = object_file(mp)
    loop.validate_machine(machine, repo=candidate_repo, risk="low", unit_id=unit,
                          policy=policy, policy_sha=policy_sha)
    adjudication = loop.validate_adjudication(candidate_repo, ap, "low", unit)
    if (machine["verdict"] != "PASSED" or machine["producer"]["host"] != platform.system()
            or machine["candidate"]["methodologyVersion"] != expected["release"]
            or adjudication["outcome"] != "PASSED"
            or adjudication["dependencies"]["machine"]["sha256"] != sha(mp)):
        raise ValueError("native canary identity/outcome/dependency differs")
    test_log = referenced(path.parent, host["nativeTestsLog"])
    try:
        native_log = candidate_repo / test_log.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("native test log is outside the aggregate input root") from exc
    if not native_log.is_file() or native_log.is_symlink() or sha(native_log) != sha(test_log):
        raise ValueError("native test-log snapshot differs from the host log")
    runs = machine["runs"]
    if (len(runs) != 1 or runs[0]["command"] != native_test_command(native_log.resolve())
            or runs[0]["stdoutSha256"] != sha(test_log)):
        raise ValueError("native tests are not the exact aggregate command and captured output")
    log_text = test_log.read_text(encoding="utf-8")
    if not all(f"PASS {suite}\n" in log_text for suite in REGRESSIONS):
        raise ValueError("native log lacks actual focused suite completions")
    return {"status": "PASSED", "platform": platform.system(), "validatorSha256": sha(Path(__file__)),
            "runtimeSha256": expected["runtimeSha256"], "machineSha256": sha(mp),
            "adjudicationSha256": sha(ap), "nativeTestsSha256": sha(test_log),
            "candidateDigest": machine["candidateDigest"]}


def installed_proof(path: Path) -> None:
    """Replay each complete chain using its native installed interpreter."""
    proof, _ = load_proof(path)
    if os.name == "nt":
        raise ValueError("Run the dual-host aggregate from WSL; --native-proof validates Windows locally")
    for host in proof["hosts"]:
        if host["platform"] == "Linux":
            import shlex
            cli = module("route_cli_transport", ROOT / "scripts/itd_install_cli.py")
            wrapper_bytes = cli.default_target().read_bytes()
            lines = wrapper_bytes.decode("utf-8").splitlines()
            if len(lines) != 3 or lines[:2] != ["#!/bin/sh", "set -eu"]:
                raise ValueError("active Linux ITD wrapper is malformed")
            args = shlex.split(lines[2])
            if (len(args) != 6 or args[0] != "exec" or args[2:4] != ["-I", "-B"] or args[-1] != "$@"
                    or wrapper_bytes != cli.wrapper(Path(args[1]), Path(args[4]))):
                raise ValueError("active Linux ITD wrapper argv differs")
            argv = [args[1], "-I", "-B", str(Path(__file__).resolve()), "--native-proof", str(path.resolve())]
        else:
            # Fixed OS transport and interpreter from the user's active installed
            # wrapper, never an executable nominated by untrusted proof fields.
            def winpath(p: Path) -> str:
                return subprocess.run(["wslpath", "-w", str(p.resolve())], check=True,
                                      capture_output=True, text=True, timeout=10).stdout.strip()
            def psquote(value: str) -> str:
                return "'" + value.replace("'", "''") + "'"
            script = ("$ErrorActionPreference='Stop'; "
                      "$wrapper=Join-Path $env:LOCALAPPDATA 'ITD/bin/itd.cmd'; "
                      "$text=[IO.File]::ReadAllText($wrapper); "
                      r"""$match=[regex]::Match($text, '^@echo off\r?\n"([^"]+)" -I -B "[^"]+" %\*\r?\n$'); """
                      "if (!$match.Success) { throw 'Active ITD wrapper is malformed' }; "
                      "& $match.Groups[1].Value -I -B " + psquote(winpath(Path(__file__)))
                      + " --native-proof " + psquote(winpath(path)) + "; exit $LASTEXITCODE")
            encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
            argv = ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
                    "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
        result = subprocess.run(argv, capture_output=True, timeout=180)
        if result.returncode:
            raise ValueError("native replay failed: " + result.stderr.decode("utf-8", errors="replace"))
        expected_log = referenced(path.parent, host["revalidationLog"])
        if result.stdout.strip() != expected_log.read_bytes().strip():
            raise ValueError("native revalidation differs from captured structured result")
        replay = json.loads(result.stdout)
        if replay.get("status") != "PASSED" or replay.get("platform") != host["platform"]:
            raise ValueError("native replay returned wrong host/outcome")


def installed_canary_regressions() -> None:
    """Synthetic fixture: real producers/validators, never deployment evidence."""
    global ROOT
    source = ROOT
    loop_path = source / "skills/_shared/itd_verification_loop.py"
    loop = module("route_fixture_loop", loop_path)
    with tempfile.TemporaryDirectory(prefix="route-canary-fixture-") as td:
        # Keep the fixture's trusted root in the same canonical spelling that
        # native Git returns through the UTF-8 review-cache transport.
        repo = Path(td).resolve()
        def git(*args):
            return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        git("init", "-q")
        git("config", "user.name", "Synthetic route fixture")
        git("config", "user.email", "route@example.invalid")
        git("config", "core.hooksPath", str(repo / "no-hooks"))
        (repo / ".gitignore").write_text(".itd-memory/\n")
        (repo / ".itd").mkdir()
        (repo / ".itd/SCOPE_LOCK.md").write_text("Synthetic receipt-validator fixture only")
        (repo / ".itd/ACCEPTANCE_CONTRACT.json").write_text('{"criteria":[{"id":"fixture","status":"pending"}]}')
        (repo / "tests").mkdir()
        (repo / "tests/verify_route_debts.py").write_text(
            "import pathlib,sys\n"
            + "raw=" + repr("".join("PASS " + suite + "\n" for suite in REGRESSIONS).encode()) + "\n"
            + "pathlib.Path(sys.argv[2]).write_bytes(raw)\nsys.stdout.buffer.write(raw)\n")
        git("add", ".")
        git("commit", "-qm", "synthetic baseline")
        (repo / "change.txt").write_text("candidate")
        git("add", "change.txt")
        receipt_root = repo / ".itd-memory/verification-loop"
        proofdir = receipt_root / "route-fixture"
        proofdir.mkdir(parents=True)
        snapshotdir = repo / ".itd-memory/host-inputs/ROUTE-DEBTS"
        snapshotdir.mkdir(parents=True)
        log = snapshotdir / "route-fixture/native-tests.log"
        log.parent.mkdir()
        mp, ap = proofdir / "machine.json", proofdir / "adjudication.json"
        common = ["--root", str(repo), "--unit-id", "ROUTE-DEBTS:deployment-canary", "--risk-tier", "low"]
        def produce(verb, *args):
            result = subprocess.run([sys.executable, "-I", "-B", str(loop_path), verb, *common, *args],
                                    cwd=repo, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, result.stdout + result.stderr
        produce("machine", "--command", "native=" + native_test_command(log), "--output", str(mp))
        produce("adjudicate", "--machine", str(mp), "--output", str(ap))
        def receipt_ref(p):
            return {"path": str(p.relative_to(receipt_root)), "sha256": sha(p)}
        def input_ref(p):
            return {"path": str(p.relative_to(snapshotdir)), "sha256": sha(p)}
        def snapshots(*paths):
            for item in paths:
                target = snapshotdir / item.relative_to(receipt_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(item, target)
        snapshots(mp, ap)
        host = {"machine": receipt_ref(mp), "adjudication": receipt_ref(ap),
                "nativeTestsLog": input_ref(log)}
        original = mp.read_bytes()
        machine = object_file(mp)
        expected = {"release": machine["candidate"]["methodologyVersion"], "runtimeSha256": "a" * 64}
        ROOT = repo
        try:
            assert validate_native_canary(snapshotdir / "INSTALLED.json", host, expected, loop)["status"] == "PASSED"
            # The final aggregate executes in an isolated staged checkout but
            # must replay a canary captured in the real native checkout.
            context = loop.candidate_context(repo, "low")
            with loop.isolated_candidate(repo, context) as isolated:
                ROOT = isolated
                copied_inputs = isolated / snapshotdir.relative_to(repo)
                copied_inputs.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(snapshotdir, copied_inputs)
                assert native_source_candidate_repo(str(repo), loop) == repo.resolve()
                assert validate_native_canary(
                    copied_inputs / "INSTALLED.json", host, expected, loop, repo,
                )["status"] == "PASSED"
            ROOT = repo
            def refused(needle):
                try:
                    validate_native_canary(snapshotdir / "INSTALLED.json", host, expected, loop)
                except Exception as exc:
                    assert needle in str(exc), (needle, str(exc))
                else:
                    raise AssertionError("malformed native canary accepted: " + needle)
            for field, value, message in (
                ("runs", [], "no command runs"),
                ("unitId", "FOREIGN", "unit"),
                ("policySha256", "0" * 64, "policy"),
            ):
                changed = copy.deepcopy(machine)
                changed[field] = value
                mp.write_text(json.dumps(loop.seal_receipt(changed)))
                snapshots(mp)
                host["machine"] = receipt_ref(mp)
                refused(message)
                mp.write_bytes(original)
                snapshots(mp)
                host["machine"] = receipt_ref(mp)
            original_log = log.read_bytes()
            log.write_bytes(b"")
            host["nativeTestsLog"] = input_ref(log)
            refused("exact aggregate command and captured output")
            log.write_bytes(original_log)
            host["nativeTestsLog"] = input_ref(log)
            # A valid chain for another command cannot establish native test coverage.
            alternate_mp, alternate_ap = proofdir / "alternate-machine.json", proofdir / "alternate-adjudication.json"
            produce("machine", "--command", "other=echo unrelated", "--output", str(alternate_mp))
            produce("adjudicate", "--machine", str(alternate_mp), "--output", str(alternate_ap))
            snapshots(alternate_mp, alternate_ap)
            host["machine"], host["adjudication"] = receipt_ref(alternate_mp), receipt_ref(alternate_ap)
            refused("exact aggregate command and captured output")
        finally:
            ROOT = source
    print("PASS A2 native canary real-chain malformed-evidence regressions", flush=True)


def repair_regressions() -> None:
    """Exercise the actual transition and diagnostic writers with temp ledgers."""
    goal_module = module("route_goal", ROOT / "skills/goal/scripts/itd_goal_verify.py")
    producer = module("route_producer", ROOT / "skills/_shared/itd_free_reviewer_producer.py")
    atomic = module("route_safe_atomic", ROOT / "skills/_shared/itd_safe_atomic.py")
    with tempfile.TemporaryDirectory(prefix="route-atomic-writer-") as td_atomic:
        root = Path(td_atomic)
        victim = root / "victim.txt"
        victim.write_bytes(b"victim-before")
        goal_path = root / "GOAL.json"
        goal_path.write_bytes(b"goal-before")
        recovery_path = goal_module.transition_recovery_path(goal_path)
        state_path = root / "STATE.json"
        state_path.write_bytes(b"state-before")
        legacy = [
            goal_path.with_name(f".{goal_path.name}.{os.getpid()}.tmp"),
            recovery_path.with_name(f".{recovery_path.name}.{os.getpid()}.tmp"),
            state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp"),
        ]
        try:
            for path in legacy:
                path.symlink_to(victim)
        except OSError as exc:
            for path in legacy:
                path.unlink(missing_ok=True)
            print(f"SKIP native legacy-temp symlink regression: {exc}", flush=True)
        else:
            goal_module.save_goal_bytes(goal_path, b"goal-after")
            goal_module.save_transition_recovery(goal_path, {"fixture": "recovery"})
            goal_module.unit_log_module().save_state(root, {"fixture": "state"})
            assert victim.read_bytes() == b"victim-before"
            assert goal_path.read_bytes() == b"goal-after"
            assert json.loads(recovery_path.read_text(encoding="utf-8")) == {"fixture": "recovery"}
            assert json.loads(state_path.read_text(encoding="utf-8")) == {"fixture": "state"}
        destination = root / "destination.txt"
        destination.write_bytes(b"old-destination")
        if os.name != "nt":
            original_replace = atomic.os.replace
            atomic.os.replace = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected replace failure"))
            try:
                try:
                    atomic.atomic_replace_bytes(destination, b"new-destination")
                except OSError:
                    pass
                else:
                    raise AssertionError("atomic replacement accepted injected replace failure")
            finally:
                atomic.os.replace = original_replace
            assert destination.read_bytes() == b"old-destination"
            assert not list(root.glob(".destination.txt.*.tmp"))
        immutable = Path("archive") / "slot.json"
        calls = 0
        original_write = atomic.os.write
        def partial_write(fd, value):
            nonlocal calls
            calls += 1
            if calls == 1:
                return 1
            raise OSError("injected partial immutable write")
        atomic.os.write = partial_write
        try:
            try:
                atomic.write_immutable_bytes(immutable, b"immutable-payload", root=root)
            except OSError:
                pass
            else:
                raise AssertionError("immutable writer accepted partial write failure")
        finally:
            atomic.os.write = original_write
        assert not (root / immutable).exists()
        assert not list((root / "archive").glob(".slot.json.*.tmp"))
        assert atomic.write_immutable_bytes(immutable, b"immutable-payload", root=root) == "created"
        assert atomic.write_immutable_bytes(immutable, b"immutable-payload", root=root) == "existing-same"
        assert atomic.write_immutable_bytes(immutable, b"different", root=root) == "collision"
        if os.name != "nt":
            # Hold the original parent descriptor, then replace its pathname
            # with a symlink to a victim directory. Descriptor-relative leaf
            # writes must stay in the renamed original directory.
            original = root / "swap-original"
            victim_dir = root / "swap-victim"
            original.mkdir(); victim_dir.mkdir()
            victim = victim_dir / "entry"
            victim.write_bytes(b"victim")
            moved = root / "swap-moved"
            target = original / "entry"
            with atomic._posix_parent(target) as (parent_fd, leaf):
                original.rename(moved)
                original.symlink_to(victim_dir, target_is_directory=True)
                fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600, dir_fd=parent_fd)
                try:
                    os.write(fd, b"anchored")
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.fsync(parent_fd)
            assert victim.read_bytes() == b"victim"
            assert (moved / "entry").read_bytes() == b"anchored"
        else:
            print("SKIP POSIX parent-swap regression on Windows", flush=True)
        if os.name == "nt":
            backend = atomic._win()
            base = Path(tempfile.gettempdir())
            swap_root = base / ("route-anchor-swap-" + uuid.uuid4().hex)
            swap_root.mkdir()
            try:
                for operation in ("replace", "append", "read", "immutable", "unlink"):
                    work = swap_root / operation; work.mkdir()
                    original = work / "parent"; original.mkdir()
                    outside = work / "outside"; outside.mkdir()
                    target = original / "record"
                    target.write_bytes(b"original"); (outside / "record").write_bytes(b"victim")
                    moved = work / "retained"; real_open = backend._open; triggered = [False]
                    def switch(parent, name, **kwargs):
                        if parent is not None and (name == "record" or name.startswith(".record.")) and not triggered[0]:
                            triggered[0] = True; original.rename(moved)
                            script = ("New-Item -ItemType Junction -Path '" + str(original).replace("'", "''") +
                                      "' -Target '" + str(outside).replace("'", "''") + "' | Out-Null")
                            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], check=True, capture_output=True)
                        return real_open(parent, name, **kwargs)
                    backend._open = switch
                    try:
                        if operation == "replace": backend.atomic_replace_bytes(target, b"changed"); assert (moved / "record").read_bytes() == b"changed"
                        elif operation == "append": backend.durable_append_bytes(target, b"+"); assert (moved / "record").read_bytes() == b"original+"
                        elif operation == "read": assert backend.read_regular_snapshot(target, 4 * 1024 * 1024) == b"original"
                        elif operation == "immutable": assert backend.write_immutable_bytes(Path("record"), b"new", root=original) == "collision"
                        else: backend.durable_unlink(target); assert not (moved / "record").exists()
                        assert triggered[0] and (outside / "record").read_bytes() == b"victim"
                    finally:
                        backend._open = real_open
                        if original.is_junction(): original.rmdir()
            finally:
                if swap_root.exists(): shutil.rmtree(swap_root)
        original_write = atomic.os.write
        atomic.os.write = lambda *_args: 0
        try:
            try:
                atomic.atomic_replace_bytes(destination, b"new-destination")
            except OSError as exc:
                assert "no progress" in str(exc)
            else:
                raise AssertionError("atomic replacement accepted a zero-progress write")
        finally:
            atomic.os.write = original_write
        assert destination.read_bytes() == b"old-destination"
        assert not list(root.glob(".destination.txt.*.tmp"))
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td)
        hooks_repo = mem / "hooks-repo"
        hooks_repo.mkdir()
        native_hooks = mem / "hooks-\u0414\u043c\u0438\u0442\u0440\u0438\u0439"
        native_hooks.mkdir()
        subprocess.run(["git", "init", str(hooks_repo)], check=True, capture_output=True)
        subprocess.run(["git", "config", "core.hooksPath", str(native_hooks)],
                       cwd=hooks_repo, check=True, capture_output=True)
        validate_selected_hooks(hooks_repo, native_hooks)
        try:
            validate_selected_hooks(hooks_repo, mem / "other-hooks")
        except ValueError as exc:
            assert "installed pre-push directory" in str(exc)
        else:
            raise AssertionError("foreign active hooks path accepted")
        cli = module("route_fixture_cli", ROOT / "scripts/itd_install_cli.py")
        wrapper_path = mem / "itd"
        wrapper_bytes = cli.wrapper(Path(sys.executable), mem / "runtime/scripts/itd.py")
        wrapper_path.write_bytes(wrapper_bytes)
        validate_wrapper(wrapper_path, {"path": str(wrapper_path), "sha256": sha(wrapper_path)}, wrapper_bytes)
        wrapper_path.write_text("# " + str(mem / "runtime") + "\n")
        try:
            validate_wrapper(wrapper_path, {"path": str(wrapper_path), "sha256": sha(wrapper_path)}, wrapper_bytes)
        except ValueError as exc:
            assert "wrapper bytes" in str(exc)
        else:
            raise AssertionError("comment-only wrapper accepted")
        rel = ADAPTER_SOURCES[0]
        target = mem / "adapter" / rel
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT / rel).read_bytes())
        row = {"source": rel, "installed": str(target), "sha256": sha(target)}
        validate_adapter_row(row, mem / "adapter")
        row["installed"] = str(ROOT / rel)
        try:
            validate_adapter_row(row, mem / "adapter")
        except ValueError as exc:
            assert "adapter path" in str(exc)
        else:
            raise AssertionError("source-only adapter inventory accepted")
        path = mem / "GOAL.json"
        event_path = mem / "events.jsonl"
        unit = {"id": "U", "status": "verified", "riskTier": "low", "criterion": "test"}
        goal = {"units": [unit], "currentUnitId": "U"}
        goal_module.save_goal(path, goal)
        baseline = [{"type": "unit", "actor": "harness", "name": "U", "ledger": "GOAL.json",
                     "decision": decision, "at": str(i)}
                    for i, decision in enumerate(("activated", "verified"))]
        for successor in ("regressed", "blocked", "budget_exhausted", "recovery_required", "activated"):
            event_path.write_text("".join(json.dumps(e) + "\n" for e in
                baseline + [{**baseline[-1], "decision": successor, "at": "2"}]))
            assert goal_module.current_canonical_event(path, "U", "verified") is None, successor
            try:
                goal_module.cmd_reconcile(goal, path, unit, "unused-receipt")
            except SystemExit:
                pass
            else:
                raise AssertionError("reconcile accepted superseded verified event")
        event_path.write_text("".join(json.dumps(e) + "\n" for e in baseline))
        assert goal_module.current_canonical_event(path, "U", "verified")["at"] == "1"
        for initial in ("verified", "in_progress"):
            unit["status"] = initial
            goal["currentUnitId"] = "U"
            state_path = mem / "STATE.json"
            state_path.write_text(json.dumps({"currentUnit": {
                "id": "U", "ledger": "GOAL.json", "status": initial}}))
            count = len(event_path.read_text().splitlines())
            assert goal_module.bounded_stop(goal, path, unit, "blocked", "test policy stop") == 3
            assert object_file(state_path)["currentUnit"]["status"] == "blocked"
            assert object_file(path)["units"][0]["status"] == "blocked"
            assert len(event_path.read_text().splitlines()) == count + 1
        foreign = {"currentUnit": {"id": "OTHER", "ledger": "GOAL.json", "status": "in_progress"}}
        state_path.write_text(json.dumps(foreign))
        before = (path.read_bytes(), event_path.read_bytes(), state_path.read_bytes())
        try:
            goal_module.bounded_stop(goal, path, unit, "blocked", "foreign stop")
        except SystemExit:
            pass
        else:
            raise AssertionError("bounded stop accepted foreign WIP")
        assert before == (path.read_bytes(), event_path.read_bytes(), state_path.read_bytes())

        # The Goal/event/STATE transition is a three-write boundary.  Inject
        # each interruption at the writer seam: no event rolls Goal back,
        # a partial event preserves the log untouched, and a landed event is the
        # sole authority for completing STATE without a duplicate event.
        def transition_fixture(label: str):
            root = mem / label
            root.mkdir()
            goal_path = root / "GOAL.json"
            events_path = root / "events.jsonl"
            state_path = root / "STATE.json"
            fixture_unit = {"id": "T", "status": "in_progress", "riskTier": "low",
                            "criterion": "transition fixture", "verificationCommand": "fixture-cmd"}
            fixture_goal = {"units": [fixture_unit], "currentUnitId": "T"}
            goal_module.save_goal(goal_path, fixture_goal)
            events_path.write_text(
                json.dumps({"type": "unit", "actor": "harness", "name": "T",
                            "ledger": "GOAL.json", "decision": "activated", "at": "0"}) + "\n"
                + json.dumps({"type": "unit", "actor": "harness", "name": "T",
                              "ledger": "GOAL.json", "decision": "verification_failed",
                              "evidence": "negative evidence", "at": "1"}) + "\n",
                encoding="utf-8")
            state_path.write_text(json.dumps({"currentUnit": {
                "id": "T", "ledger": "GOAL.json", "status": "in_progress"}}), encoding="utf-8")
            projection = goal_module.state_projection(goal_path, fixture_unit, "verified")
            fixture_unit["status"] = "verified"
            fixture_goal["currentUnitId"] = ""
            return fixture_goal, fixture_unit, goal_path, events_path, state_path, projection

        original_append = goal_module.append_event
        original_projection = goal_module.write_state_projection
        original_validate = goal_module.validate_verification_receipt
        original_unit_log_module = goal_module.unit_log_module

        goal, unit, goal_path, events_path, state_path, projection = transition_fixture("append-before")
        before = (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes())
        def fail_before(*args, **kwargs):
            raise OSError("injected before append")
        goal_module.append_event = fail_before
        assert not goal_module.commit_goal_transition(goal, goal_path, unit, "verified", "evidence", projection)
        assert (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes()) == before
        assert not goal_module.transition_recovery_path(goal_path).exists()

        goal, unit, goal_path, events_path, state_path, projection = transition_fixture("append-partial")
        before = (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes())
        def fail_partial(*args, **kwargs):
            events_path.open("ab").write(goal_module.event_line(kwargs["event"])[:4])
            raise OSError("injected partial append")
        goal_module.append_event = fail_partial
        assert not goal_module.commit_goal_transition(goal, goal_path, unit, "verified", "evidence", projection)
        partial = events_path.read_bytes()
        assert goal_path.read_bytes() != before[0] and state_path.read_bytes() == before[2]
        assert b"negative evidence" in events_path.read_bytes()
        assert goal_module.transition_recovery_path(goal_path).exists()
        events_path.open("ab").write(b"\n" + json.dumps({"type": "unit", "actor": "harness",
            "name": "OTHER", "ledger": "GOAL.json", "decision": "activated", "at": "2"}).encode("utf-8") + b"\n")
        after_other = events_path.read_bytes()
        try:
            goal_module.recover_goal_transition(goal_path)
        except RuntimeError:
            pass
        else:
            raise AssertionError("ambiguous partial append was silently recovered")
        assert events_path.read_bytes() == after_other and events_path.read_bytes().startswith(partial)

        goal, unit, goal_path, events_path, state_path, projection = transition_fixture("append-landed")
        def fail_after(*args, **kwargs):
            original_append(*args, **kwargs)
            raise OSError("injected after complete append")
        goal_module.append_event = fail_after
        assert goal_module.commit_goal_transition(goal, goal_path, unit, "verified", "evidence", projection,
                                                  verified_context=True)
        landed = [event for event in (json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines())
                  if event.get("decision") == "verified"]
        assert len(landed) == 1 and object_file(state_path)["currentUnit"]["status"] == "verified"
        assert not goal_module.transition_recovery_path(goal_path).exists()
        assert not goal_module.recover_goal_transition(goal_path)

        goal, unit, goal_path, events_path, state_path, projection = transition_fixture("state-failure")
        state_writer = projection[0]
        original_save_locked = state_writer.save_state_locked
        def fail_state(*args, **kwargs):
            raise OSError("injected STATE failure")
        goal_module.append_event = original_append
        goal_module.unit_log_module = lambda: state_writer
        state_writer.save_state_locked = fail_state
        assert not goal_module.commit_goal_transition(goal, goal_path, unit, "verified", "evidence", projection,
                                                       verified_context=True)
        assert object_file(goal_path)["units"][0]["status"] == "verified"
        assert object_file(state_path)["currentUnit"]["status"] == "in_progress"
        assert goal_module.transition_recovery_path(goal_path).exists()
        state_writer.save_state_locked = original_save_locked
        goal_module.unit_log_module = original_unit_log_module
        journal_path = goal_module.transition_recovery_path(goal_path)
        journal_bytes = journal_path.read_bytes()
        malformed = json.loads(journal_bytes)
        malformed["decision"] = "activated"
        malformed["event"]["decision"] = "activated"
        journal_path.write_text(json.dumps(malformed), encoding="utf-8")
        protected = (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes())
        try:
            goal_module.recover_goal_transition(goal_path, "current-receipt")
        except RuntimeError:
            pass
        else:
            raise AssertionError("mismatched event/state journal completed a projection")
        assert protected == (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes())
        journal_path.write_bytes(journal_bytes)
        protected = (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes(),
                     journal_path.read_bytes())
        wrong_unit = dict(unit)
        wrong_unit["id"] = "OTHER"
        try:
            goal_module.cmd_reconcile(goal, goal_path, wrong_unit, "current-receipt")
        except SystemExit as exc:
            assert exc.code == 1
        else:
            raise AssertionError("reconcile accepted a journal for a different unit")
        assert protected == (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes(),
                             journal_path.read_bytes())
        original_argv = sys.argv
        try:
            sys.argv = ["itd_goal_verify.py", "--goal", str(goal_path), "--reconcile", "T"]
            try:
                goal_module.main()
            except SystemExit as exc:
                assert exc.code == 1
            else:
                raise AssertionError("reconcile accepted journal recovery without receipt")
            saved_events = events_path.read_bytes()
            events_path.open("ab").write(json.dumps({"type": "unit", "actor": "harness", "name": "T",
                "ledger": "GOAL.json", "decision": "regressed", "at": "9"}).encode("utf-8") + b"\n")
            goal_module.validate_verification_receipt = lambda *args: {
                "machine": {"runs": [{"command": "fixture-cmd"}]}}
            sys.argv = ["itd_goal_verify.py", "--goal", str(goal_path), "--reconcile", "T",
                        "--verification-receipt", "current-receipt"]
            try:
                goal_module.main()
            except SystemExit as exc:
                assert exc.code == 1
            else:
                raise AssertionError("reconcile accepted a superseded verified event")
            events_path.write_bytes(saved_events)
            assert goal_module.main() == 0
        finally:
            sys.argv = original_argv
            goal_module.validate_verification_receipt = original_validate
        landed = [event for event in (json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines())
                  if event.get("decision") == "verified"]
        assert len(landed) == 1 and object_file(state_path)["currentUnit"]["status"] == "verified"
        assert not goal_module.transition_recovery_path(goal_path).exists()
        assert not goal_module.recover_goal_transition(goal_path)
        goal_module.append_event = original_append
        goal_module.write_state_projection = original_projection

        # A Goal preflight must never overwrite a normal task-writer update
        # which landed before the final STATE projection.  The shared writer
        # CAS leaves the foreign update intact and the Goal journal recoverable.
        goal, unit, goal_path, events_path, state_path, projection = transition_fixture("state-concurrent")
        foreign = {"currentUnit": {"id": "FOREIGN", "ledger": "STATE.json",
                                     "status": "in_progress"}}
        projection[0].save_state(goal_path.parent, foreign)
        before_goal_events = (goal_path.read_bytes(), events_path.read_bytes())
        try:
            goal_module.commit_goal_transition(goal, goal_path, unit, "verified", "evidence", projection,
                                               verified_context=True)
        except SystemExit as exc:
            assert exc.code == 1
        else:
            raise AssertionError("Goal transition accepted a concurrent foreign STATE")
        assert object_file(state_path) == foreign
        assert (goal_path.read_bytes(), events_path.read_bytes()) == before_goal_events
        assert not goal_module.transition_recovery_path(goal_path).exists()

        # A real task-lifecycle terminal for the same unit also invalidates the
        # preflight generation. Goal must reject before creating its journal or
        # event rather than reviving that terminal STATE snapshot.
        goal, unit, goal_path, events_path, state_path, projection = transition_fixture("state-same-unit")
        task_close = subprocess.run(
            [sys.executable, "-I", "-B", str(goal_module.UNIT_LOG_PATH), "close", "T",
             "--note", "concurrent task terminal", "--ledger", "GOAL.json",
             "--dir", str(goal_path.parent)], capture_output=True, text=True, timeout=20)
        assert task_close.returncode == 0, task_close.stdout + task_close.stderr
        before_goal_events = (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes())
        assert not goal_module.commit_goal_transition(goal, goal_path, unit, "verified", "evidence", projection,
                                                       verified_context=True)
        assert (goal_path.read_bytes(), events_path.read_bytes(), state_path.read_bytes()) == before_goal_events
        assert not goal_module.transition_recovery_path(goal_path).exists()

        # The shared lock is bounded under contention and released by the OS
        # after a writer process exits while holding it.  This exercises the
        # actual task-writer lock backend, not a Goal-local substitute.
        lock_module = str(goal_module.UNIT_LOG_PATH)
        lock_code = (
            "import importlib.util,sys\nfrom pathlib import Path\n"
            f"s=importlib.util.spec_from_file_location('lock_probe',{lock_module!r})\n"
            "m=importlib.util.module_from_spec(s)\ns.loader.exec_module(m)\n"
            "with m.state_write_lock(Path(sys.argv[1])):\n    pass\n"
        )
        with projection[0].state_write_lock(goal_path.parent):
            blocked = subprocess.run([sys.executable, "-I", "-B", "-c", lock_code,
                                      str(goal_path.parent)], capture_output=True, timeout=10)
        assert blocked.returncode != 0
        released = subprocess.run([sys.executable, "-I", "-B", "-c", lock_code,
                                   str(goal_path.parent)], capture_output=True, timeout=10)
        assert released.returncode == 0
        crash_code = lock_code.replace("    pass\n", "    __import__('os')._exit(0)\n")
        crashed = subprocess.run([sys.executable, "-I", "-B", "-c", crash_code,
                                  str(goal_path.parent)], capture_output=True, timeout=10)
        assert crashed.returncode == 0
        with projection[0].state_write_lock(goal_path.parent):
            pass

        # The checker-error recheck transition has the same recovery envelope:
        # its canonical event projects the verified unit back to in_progress.
        goal, unit, goal_path, events_path, state_path, projection = transition_fixture("checker-unverified")
        unit["status"] = "in_progress"
        goal["currentUnitId"] = unit["id"]
        projection = goal_module.state_projection(goal_path, unit, "regressed")
        state_writer = projection[0]
        original_save_locked = state_writer.save_state_locked
        goal_module.unit_log_module = lambda: state_writer
        state_writer.save_state_locked = fail_state
        assert not goal_module.commit_goal_transition(
            goal, goal_path, unit, "verification_unverified", "checker missing", projection,
            state_decision="regressed")
        state_writer.save_state_locked = original_save_locked
        goal_module.unit_log_module = original_unit_log_module
        assert object_file(goal_path)["units"][0]["status"] == "in_progress"
        assert object_file(state_path)["currentUnit"]["status"] == "in_progress"
        assert goal_module.transition_recovery_path(goal_path).exists()
        assert goal_module.recover_goal_transition(goal_path) == "projected"
        assert object_file(state_path)["currentUnit"]["status"] == "in_progress"
        assert not goal_module.transition_recovery_path(goal_path).exists()

        # STATE-present normal reconciliation and already-active repair use
        # the three-field projection returned by state_projection.
        goal, unit, goal_path, events_path, state_path, _projection = transition_fixture("state-present-reconcile")
        unit["status"] = "verified"
        goal["currentUnitId"] = ""
        goal_module.save_goal(goal_path, goal)
        events_path.write_text(json.dumps({"type": "unit", "actor": "harness", "name": "T",
            "ledger": "GOAL.json", "decision": "activated", "at": "0"}) + "\n" +
            json.dumps({"type": "unit", "actor": "harness", "name": "T",
                "ledger": "GOAL.json", "decision": "verified", "at": "1"}) + "\n", encoding="utf-8")
        goal_module.validate_verification_receipt = lambda *_args: {"machine": {"runs": [{"command": "fixture-cmd"}]}}
        assert goal_module.cmd_reconcile(goal, goal_path, unit, "current-receipt") == 0
        assert object_file(state_path)["currentUnit"]["status"] == "verified"
        goal_module.validate_verification_receipt = original_validate

        goal, unit, goal_path, events_path, state_path, _projection = transition_fixture("state-present-active")
        unit["status"] = "in_progress"
        goal["currentUnitId"] = unit["id"]
        goal_module.save_goal(goal_path, goal)
        state_path.write_text(json.dumps({"currentUnit": {"id": "T", "ledger": "GOAL.json",
                                                     "status": "blocked"}}), encoding="utf-8")
        assert goal_module.cmd_activate(goal, goal_path, unit) == 0
        assert object_file(state_path)["currentUnit"]["status"] == "in_progress"

        # The machine bytes consumed for Goal command binding must be the same
        # machine dependency bytes the adjudication validator approved.
        fake_loop = mem / "swap-loop.py"
        machine = mem / "machine.json"
        machine.write_text('{"runs":[{"command":"fixture-cmd"}]}', encoding="utf-8")
        machine_sha = hashlib.sha256(b'{"runs":[{"command":"fixture-cmd"}]}').hexdigest()
        receipt_value = {"version": 1, "dependencies": {"machine": {"path": "machine.json", "sha256": machine_sha}}}
        (mem / "ignored.json").write_text(json.dumps(receipt_value), encoding="utf-8")
        fake_loop.write_text(
            "from pathlib import Path\n"
            "class LoopError(Exception):\n    why=''; fix=''\n"
            "def validate_adjudication(root,path,risk,unit):\n"
            " Path(root,'machine.json').write_text('{\\\"runs\\\":[{\\\"command\\\":\\\"swapped\\\"}]}',encoding='utf-8')\n"
            " return {'version':1,'dependencies':{'machine':{'path':'machine.json','sha256':'" + machine_sha + "'}}}\n",
            encoding="utf-8")
        old_loop = goal_module.VERIFICATION_LOOP_PATH
        goal_module.VERIFICATION_LOOP_PATH = fake_loop
        try:
            try:
                goal_module.validate_verification_receipt(goal_path, "ignored.json", "high", "T")
            except goal_module.VerificationReceiptError as exc:
                assert "changed after adjudication" in str(exc)
            else:
                raise AssertionError("Goal accepted machine bytes swapped after adjudication")
        finally:
            goal_module.VERIFICATION_LOOP_PATH = old_loop
        fake_loop.write_text(
            "from pathlib import Path\n"
            "class LoopError(Exception):\n    why=''; fix=''\n"
            "def validate_adjudication(root,path,risk,unit):\n"
            " Path(path).write_text('{\\\"changed\\\":true}',encoding='utf-8')\n"
            " return {'version':1,'dependencies':{'machine':{'path':'machine.json','sha256':'" + machine_sha + "'}}}\n",
            encoding="utf-8")
        machine.write_text('{"runs":[{"command":"fixture-cmd"}]}', encoding="utf-8")
        (mem / "ignored.json").write_text(json.dumps(receipt_value), encoding="utf-8")
        goal_module.VERIFICATION_LOOP_PATH = fake_loop
        try:
            try:
                goal_module.validate_verification_receipt(goal_path, "ignored.json", "high", "T")
            except goal_module.VerificationReceiptError as exc:
                assert "adjudication receipt changed after validation" in str(exc)
            else:
                raise AssertionError("Goal accepted adjudication bytes swapped after validation")
        finally:
            goal_module.VERIFICATION_LOOP_PATH = old_loop
        for replacement in ("true", "1.0"):
            fake_loop.write_text(
                "class LoopError(Exception):\n    why=''; fix=''\n"
                "def validate_adjudication(root,path,risk,unit):\n"
                " return {'version':1,'dependencies':{'machine':{'path':'machine.json','sha256':'" + machine_sha + "'}}}\n",
                encoding="utf-8")
            machine.write_text('{"runs":[{"command":"fixture-cmd"}]}', encoding="utf-8")
            (mem / "ignored.json").write_text(
                '{"version":' + replacement + ',"dependencies":{"machine":{"path":"machine.json","sha256":"' + machine_sha + '"}}}',
                encoding="utf-8")
            goal_module.VERIFICATION_LOOP_PATH = fake_loop
            try:
                try:
                    goal_module.validate_verification_receipt(goal_path, "ignored.json", "high", "T")
                except goal_module.VerificationReceiptError as exc:
                    assert "adjudication receipt changed after validation" in str(exc)
                else:
                    raise AssertionError("Goal accepted type-coerced adjudication replacement")
            finally:
                goal_module.VERIFICATION_LOOP_PATH = old_loop

        oversized = mem / "oversized-receipt.json"
        oversized.write_bytes(b"{" + b" " * (goal_module.JSON_SNAPSHOT_MAX_BYTES + 1) + b"}")
        try:
            goal_module.stable_json_snapshot(oversized, "oversized fixture")
        except goal_module.VerificationReceiptError as exc:
            assert "size limit" in str(exc)
        else:
            raise AssertionError("Goal accepted an oversized post-validation snapshot")
        fifo = mem / "receipt.fifo"
        if hasattr(os, "mkfifo"):
            os.mkfifo(fifo)
            try:
                try:
                    goal_module.stable_json_snapshot(fifo, "FIFO fixture")
                except goal_module.VerificationReceiptError as exc:
                    assert "regular" in str(exc)
                else:
                    raise AssertionError("Goal opened a FIFO snapshot")
            finally:
                fifo.unlink()
        else:
            print("SKIP native FIFO snapshot regression: os.mkfifo unavailable", flush=True)

        reviewer = {"provider": "openai-subscription", "model": "gpt-5.6-sol",
                    "session": "negative-1", "transportExecutableSha256": "a" * 64}
        error = producer.FreeReviewError("BLOCKED", "negative", evidence={
            "report": {"verdict": "BLOCKED", "findings": ["first"], "unverified": []},
            "reviewer": reviewer, "attempts": [{"provider": "openai-subscription", "status": "PASSED"}]})
        first = producer.persist_review_diagnostic(prompt="first", prompt_output=mem / "prompt.txt",
                                                   report_output=mem / "report.json", error=error)
        saved = {k: Path(first[k]).read_bytes() for k in ("prompt", "report", "observation")}
        error.evidence["report"]["findings"] = ["second"]
        second = producer.persist_review_diagnostic(prompt="second", prompt_output=mem / "prompt.txt",
                                                    report_output=mem / "report.json", error=error)
        assert first["observation"] != second["observation"]
        for key, value in saved.items():
            assert Path(first[key]).read_bytes() == value, "negative history replaced: " + key
        assert object_file(Path(second["report"]))["findings"] == ["second"]
    print("PASS A2 Goal event/state and immutable negative diagnostic regressions", flush=True)
    sol_a7_regressions(goal_module, producer, atomic)
    installed_canary_regressions()


def sol_a7_regressions(goal_module, producer, atomic) -> None:
    """Sol-a7: multi-link append destinations, scrubbed criterion IDs (rebuttal), link-swapped receipts."""
    with tempfile.TemporaryDirectory(prefix="route-sol-a7-") as td:
        root = Path(td)

        # 1. A trusted append must refuse a ledger path that is a hard link to
        # another file; the victim keeps its bytes and a plain ledger still works.
        ledger = root / "events.jsonl"
        victim = root / "victim.jsonl"
        victim.write_bytes(b"victim")
        # Both hosts support hard links in the temporary directory; a failure to
        # build this security fixture is a failed proof, never a skip (Sol-a8).
        try:
            os.link(victim, ledger)
        except OSError as exc:
            raise AssertionError(f"hard-link append fixture could not be built: {exc}") from exc
        try:
            atomic.durable_append_bytes(ledger, b"+")
        except RuntimeError as exc:
            assert "private" in str(exc) or "safe" in str(exc), str(exc)
        else:
            raise AssertionError("durable append wrote through a hard-linked ledger")
        assert victim.read_bytes() == b"victim", "hard-linked victim was modified"
        ledger.unlink()
        atomic.durable_append_bytes(ledger, b"ok\n")
        assert ledger.read_bytes() == b"ok\n"

        # 2. Rebuttal of Sol-a7 F2 on the unchanged producer bytes: the
        # criterion-ID check inspects the SCRUBBED representation the reviewer
        # receives (freeze_packet parses acceptance_text, not acceptance_raw).
        # A secret-shaped identifier the real scrubber rewrites is refused, and
        # every substitution the scrubber can make carries the [REDACTED
        # marker, so no identifier rewrite escapes the marker check.
        helpers = module("route_producer_fixture", ROOT / "tests/verify_free_reviewer_producer.py")
        repo = root / "repo"
        repo.mkdir()
        base, parent, tree = helpers.git_fixture(repo)
        scope, acceptance, machine = helpers.write_inputs(root, repo, parent, tree)
        freeze = dict(root=repo, base_commit=base, repository="hihol-labs/idea-to-deploy",
                      pull_request=None, expected_head_sha=None, scope_file=scope,
                      acceptance_file=acceptance, machine_receipt=machine)

        def bind_acceptance(criterion_id: str) -> None:
            acceptance.write_text(json.dumps({"version": 1, "criteria": [
                {"id": criterion_id, "text": "review exact candidate"}]}), encoding="utf-8")
            machine_value = json.loads(machine.read_text(encoding="utf-8"))
            machine_value["candidate"]["acceptanceContractHash"] = hashlib.sha256(acceptance.read_bytes()).hexdigest()
            machine.write_text(json.dumps(machine_value), encoding="utf-8")

        bind_acceptance("ghp_" + "A1b2C3d4" * 4)
        try:
            producer.freeze_packet(**freeze)
        except producer.FreeReviewError as exc:
            assert exc.status == "UNVERIFIED" and "criterion ID was scrubbed" in exc.reason, exc.reason
        else:
            raise AssertionError("producer froze a packet whose criterion ID the scrubber rewrote")
        for _pattern, replacement in producer.scrubber.SECRET_PATTERNS:
            assert "[REDACTED" in replacement, "scrubber substitution without the marker: " + replacement
        assert "[REDACTED-EMAIL]" in producer.scrubber.scrub("owner@example.com")[0]
        bind_acceptance("ROUTE-OWNER-1")
        packet = producer.freeze_packet(**freeze)
        assert packet["acceptance"]["value"]["criteria"][0]["id"] == "ROUTE-OWNER-1"

        # 3. A receipt swapped for a link after external validation is refused
        # without resolving the path first: a link to an identical receipt
        # elsewhere in the project (which resolve() would accept and record
        # under the original path), a directory link, and lexical escapes.
        project = root / "project"
        mem = project / ".itd-memory"
        mem.mkdir(parents=True)
        goal_path = mem / "GOAL.json"
        goal_path.write_text("{}", encoding="utf-8")
        outside = root / "outside"
        outside.mkdir()
        elsewhere = project / "elsewhere"
        (elsewhere / "receipts").mkdir(parents=True)
        machine_bytes = b'{"runs":[{"command":"fixture-cmd"}]}'
        (project / "machine.json").write_bytes(machine_bytes)
        machine_sha = hashlib.sha256(machine_bytes).hexdigest()
        receipt_bytes = json.dumps({"version": 1, "dependencies": {
            "machine": {"path": "machine.json", "sha256": machine_sha}}}).encode("utf-8")
        for target in (outside / "receipt.json", elsewhere / "receipt.json",
                       elsewhere / "receipts" / "receipt.json", project / "receipt.json"):
            target.write_bytes(receipt_bytes)
        (project / "receipts").mkdir()
        (project / "receipts" / "receipt.json").write_bytes(receipt_bytes)
        fake_loop = root / "swap-loop.py"
        fake_loop.write_text(
            "import os\nfrom pathlib import Path\n"
            "class LoopError(Exception):\n    why=''; fix=''\n"
            "def validate_adjudication(root,path,risk,unit):\n"
            " path=Path(path); outside=Path(root)/'elsewhere'\n"
            " if path.parent.name=='receipts':\n"
            "  path.parent.rename(path.parent.with_name('receipts-real'))\n"
            "  if os.name=='nt':\n"
            "   import subprocess; subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',"
            "\"New-Item -ItemType Junction -Path '\"+str(path.parent)+\"' -Target '\"+str(outside/'receipts')+\"' | Out-Null\"],check=True,capture_output=True)\n"
            "  else:\n"
            "   os.symlink(outside/'receipts', path.parent, target_is_directory=True)\n"
            " else:\n"
            "  path.unlink(); os.symlink(outside/'receipt.json', path)\n"
            " return {'version':1,'dependencies':{'machine':{'path':'machine.json','sha256':'" + machine_sha + "'}}}\n",
            encoding="utf-8")
        old_loop = goal_module.VERIFICATION_LOOP_PATH
        goal_module.VERIFICATION_LOOP_PATH = fake_loop
        try:
            probe = root / "probe-link"
            try:
                os.symlink(elsewhere / "receipt.json", probe)
            except OSError as exc:
                print(f"SKIP leaf-link receipt regression: {exc}", flush=True)
                leaf_cases = ()
            else:
                leaf_cases = ("receipt.json",)
            for relative in leaf_cases + ("receipts/receipt.json",):
                try:
                    goal_module.validate_verification_receipt(goal_path, relative, "high", "T")
                except goal_module.VerificationReceiptError as exc:
                    assert "no-link" in str(exc) or "unreadable" in str(exc), str(exc)
                else:
                    raise AssertionError("Goal read a link-swapped receipt as validated: " + relative)
            for escape in ("../outside/receipt.json", str(outside / "receipt.json")):
                try:
                    goal_module.validate_verification_receipt(goal_path, escape, "high", "T")
                except goal_module.VerificationReceiptError as exc:
                    assert "inside the project" in str(exc), str(exc)
                else:
                    raise AssertionError("Goal accepted a receipt outside the project: " + escape)
        finally:
            goal_module.VERIFICATION_LOOP_PATH = old_loop
            if (project / "receipts").is_symlink() or (os.name == "nt" and (project / "receipts").is_junction()):
                (project / "receipts").unlink() if (project / "receipts").is_symlink() else (project / "receipts").rmdir()
    print("PASS Sol-a7 hard-link append, scrubbed criterion rebuttal and link-swapped receipt regressions", flush=True)
    sol_a8_regressions(goal_module)


def sol_a8_regressions(goal_module) -> None:
    """Sol-a8: partial events.jsonl tail refuses a Goal append; inventories do not follow links."""
    with tempfile.TemporaryDirectory(prefix="route-sol-a8-") as td:
        root = Path(td)
        mem = root / ".itd-memory"
        mem.mkdir()
        goal_path = mem / "GOAL.json"
        goal_path.write_text("{}", encoding="utf-8")
        events = mem / "events.jsonl"
        fragment = b'{"type":"unit","name":"T","decision":"activated"'
        events.write_bytes(fragment)
        try:
            goal_module.append_event(goal_path, "T", "verified", "fixture")
        except RuntimeError as exc:
            assert "partial final record" in str(exc), str(exc)
        else:
            raise AssertionError("Goal appended an event after a partial final record")
        assert events.read_bytes() == fragment, "partial tail was mutated"
        events.write_bytes(fragment + b"}\n")
        goal_module.append_event(goal_path, "T", "verified", "fixture")
        lines = events.read_bytes().split(b"\n")
        assert len(lines) == 3 and lines[2] == b"" and json.loads(lines[1])["decision"] == "verified"

        runtime_tests = module("route_runtime_install_tests", ROOT / "tests/verify_itd_runtime_install.py")
        real = root / "real"
        (real / "dir").mkdir(parents=True)
        (real / "dir" / "inner.txt").write_bytes(b"inner")
        (real / "file.txt").write_bytes(b"same-bytes")
        linked = root / "linked"
        linked.mkdir()
        (linked / "target-dir").mkdir()
        (linked / "target-dir" / "inner.txt").write_bytes(b"inner")
        (linked / "target.txt").write_bytes(b"same-bytes")
        try:
            os.symlink(linked / "target.txt", linked / "file.txt")
            os.symlink(linked / "target-dir", linked / "dir", target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                raise
            # Symlinks need a privilege natively; junctions do not, so the
            # directory case is proved with a real junction instead of skipped.
            script = ("New-Item -ItemType Junction -Path '" + str(linked / "dir").replace("'", "''") +
                      "' -Target '" + str(linked / "target-dir").replace("'", "''") + "' | Out-Null")
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                           check=True, capture_output=True)
            try:
                junction_inventory = runtime_tests.runtime_inventory(linked)
                assert "dir/" not in junction_inventory and junction_inventory["dir"].startswith("link:"), \
                    "directory junction reported as a directory"
            finally:
                (linked / "dir").rmdir()
            print(f"SKIP native file-symlink inventory case (privilege unavailable: {exc}); directory junction case proved", flush=True)
        else:
            real_inventory = runtime_tests.runtime_inventory(real)
            linked_inventory = runtime_tests.runtime_inventory(linked)
            assert real_inventory["file.txt"] != linked_inventory["file.txt"], "file symlink hashed as its target"
            assert "dir/" in real_inventory and "dir/" not in linked_inventory, "directory symlink reported as a directory"
            assert linked_inventory["dir"].startswith("link:") and linked_inventory["file.txt"].startswith("link:")
    print("PASS Sol-a8 partial-tail Goal append and link-aware runtime inventory regressions", flush=True)
    sol_a9_regressions(goal_module)


def sol_a9_regressions(goal_module) -> None:
    """Sol-a9: no projection over a newline-less landed event; wrapper proof never follows links."""
    with tempfile.TemporaryDirectory(prefix="route-sol-a9-") as td:
        root = Path(td)
        # 1. A durable append that wrote the whole event object but not its
        # newline must not be recovered as landed: recovery evidence stays,
        # STATE is not projected, and the log is not rewritten.
        mem = root / ".itd-memory"
        mem.mkdir()
        goal_path = mem / "GOAL.json"
        unit = {"id": "T", "criterion": "c", "verificationCommand": "true", "status": "in_progress",
                "riskTier": "low"}
        goal = {"version": 1, "goal": "g", "status": "active", "createdAt": "0", "updatedAt": "0",
                "currentUnitId": "T", "units": [unit]}
        goal_module.save_goal(goal_path, goal)
        events_path = mem / "events.jsonl"
        events_path.write_text(json.dumps({"type": "unit", "actor": "harness", "name": "T",
            "ledger": "GOAL.json", "decision": "activated", "at": "0"}) + "\n", encoding="utf-8")
        state_path = mem / "STATE.json"
        state_path.write_text(json.dumps({"currentUnit": {"id": "T", "ledger": "GOAL.json",
                                                          "status": "in_progress"}}), encoding="utf-8")
        original_append = goal_module.append_event
        original_validate = goal_module.validate_verification_receipt
        goal_module.validate_verification_receipt = lambda *_args: {"machine": {"runs": [{"command": "true"}]}}

        def fail_without_newline(*args, **kwargs):
            events_path.open("ab").write(goal_module.event_line(kwargs["event"])[:-1])
            raise OSError("injected append without newline")

        goal_module.append_event = fail_without_newline
        try:
            projection = goal_module.state_projection(goal_path, unit, "verified")
            unit["status"] = "verified"
            goal["currentUnitId"] = ""
            committed = goal_module.commit_goal_transition(goal, goal_path, unit, "verified", "evidence",
                                                           projection, verified_context=True)
        finally:
            goal_module.append_event = original_append
            goal_module.validate_verification_receipt = original_validate
        assert committed is False, "a newline-less landed event was projected as recovered"
        log_after = events_path.read_bytes()
        assert not log_after.endswith(b"\n") and goal_module.transition_recovery_path(goal_path).exists()
        assert object_file(state_path)["currentUnit"]["status"] == "in_progress"
        try:
            goal_module.recover_goal_transition(goal_path)
        except RuntimeError as exc:
            assert "partial final record" in str(exc), str(exc)
        else:
            raise AssertionError("recovery projected over a newline-less final record")
        assert events_path.read_bytes() == log_after and goal_module.transition_recovery_path(goal_path).exists()

        # 2. The active wrapper proof binds the declared namespace entry itself.
        wrapper_dir = root / "bin"
        wrapper_dir.mkdir()
        target = wrapper_dir / "itd"
        content = b"#!/bin/sh\nexec true\n"
        target.write_bytes(content)
        ref = {"path": str(target), "sha256": hashlib.sha256(content).hexdigest()}
        validate_wrapper(target, ref, content)
        elsewhere = root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "itd").write_bytes(content)
        try:
            os.symlink(root / "bin", root / "bin-link", target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                raise
            script = ("New-Item -ItemType Junction -Path '" + str(root / "bin-link").replace("'", "''") +
                      "' -Target '" + str(root / "bin").replace("'", "''") + "' | Out-Null")
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                           check=True, capture_output=True)
            print(f"SKIP native wrapper file-symlink case (privilege unavailable: {exc}); junction path case proved", flush=True)
            file_link = False
        else:
            file_link = True
        try:
            validate_wrapper(target, {"path": str(root / "bin-link" / "itd"), "sha256": ref["sha256"]}, content)
        except ValueError as exc:
            assert "namespace entry" in str(exc), str(exc)
        else:
            raise AssertionError("wrapper proof accepted a declared path that only resolves to the target")
        if file_link:
            target.unlink()
            os.symlink(elsewhere / "itd", target)
            try:
                validate_wrapper(target, ref, content)
            except ValueError as exc:
                assert "link" in str(exc), str(exc)
            else:
                raise AssertionError("wrapper proof followed a symlinked wrapper with identical bytes")
    print("PASS Sol-a9 newline-less landed-event recovery and link-free wrapper proof regressions", flush=True)
    sol_a10_regressions(goal_module)


def sol_a10_regressions(goal_module) -> None:
    """Sol-a10: STATE mirror never read through a link; inventory survives interpreters without is_junction."""
    with tempfile.TemporaryDirectory(prefix="route-sol-a10-") as td:
        root = Path(td)
        mem = root / ".itd-memory"
        mem.mkdir()
        goal_path = mem / "GOAL.json"
        unit = {"id": "T", "status": "in_progress", "riskTier": "low",
                "criterion": "c", "verificationCommand": "true"}
        goal_module.save_goal(goal_path, {"units": [unit], "currentUnitId": "T"})
        outside = root / "outside-STATE.json"
        outside.write_text(json.dumps({"currentUnit": {"id": "T", "ledger": "GOAL.json",
                                                       "status": "in_progress"}}), encoding="utf-8")
        try:
            os.symlink(outside, mem / "STATE.json")
        except OSError as exc:
            if os.name != "nt":
                raise
            print(f"SKIP native linked-STATE regression: symlink privilege unavailable: {exc}", flush=True)
        else:
            sink = io.StringIO()
            try:
                with contextlib.redirect_stdout(sink):
                    goal_module.state_projection(goal_path, unit, "verified")
            except SystemExit:
                assert "STATE mirror" in sink.getvalue(), sink.getvalue()
            else:
                raise AssertionError("Goal read a linked STATE mirror as the project's own")
            (mem / "STATE.json").unlink()
        (mem / "STATE.json").write_text(json.dumps({"currentUnit": {"id": "T", "ledger": "GOAL.json",
                                                                    "status": "in_progress"}}), encoding="utf-8")
        assert goal_module.state_projection(goal_path, unit, "verified") is not None

        runtime_tests = module("route_runtime_install_tests_a10", ROOT / "tests/verify_itd_runtime_install.py")
        plain = root / "plain"
        (plain / "dir").mkdir(parents=True)
        (plain / "dir" / "f.txt").write_bytes(b"f")
        owner = next((klass for klass in Path.__mro__ if "is_junction" in vars(klass)), None)
        if owner is None:
            print("SKIP is_junction removal regression: interpreter has no Path.is_junction", flush=True)
        else:
            saved = vars(owner)["is_junction"]
            delattr(owner, "is_junction")
            try:
                inventory = runtime_tests.runtime_inventory(plain)
            finally:
                setattr(owner, "is_junction", saved)
            assert inventory == {"dir/": "directory", "dir/f.txt": hashlib.sha256(b"f").hexdigest()}
    print("PASS Sol-a10 no-follow STATE mirror and is_junction-free inventory regressions", flush=True)
    sol_a11_regressions(goal_module)


def sol_a11_regressions(goal_module) -> None:
    """Sol-a11: STATE re-read, recovery record and events tail are never read through links."""
    with tempfile.TemporaryDirectory(prefix="route-sol-a11-") as td:
        root = Path(td)
        mem = root / ".itd-memory"
        mem.mkdir()
        goal_path = mem / "GOAL.json"
        unit = {"id": "T", "status": "in_progress", "riskTier": "low",
                "criterion": "c", "verificationCommand": "true"}
        goal_module.save_goal(goal_path, {"units": [unit], "currentUnitId": "T"})
        state_bytes = json.dumps({"currentUnit": {"id": "T", "ledger": "GOAL.json",
                                                  "status": "in_progress"}}).encode("utf-8")
        state_path = mem / "STATE.json"
        state_path.write_bytes(state_bytes)
        outside = root / "outside"
        outside.mkdir()
        try:
            os.symlink(outside / "probe", root / "probe-link")
        except OSError as exc:
            if os.name != "nt":
                raise
            privilege = str(exc)
            # Without the symlink privilege the three sites are proved through
            # a junction on the ledger directory: every read is anchored, so a
            # reparse point on the way refuses instead of being followed.
            real_mem = root / "real-mem"
            real_mem.mkdir()
            (real_mem / "STATE.json").write_bytes(state_bytes)
            (real_mem / "events.jsonl").write_bytes(b'{"decision":"activated"}\n')
            (real_mem / ".goal-transition-recovery.json").write_text('{"version": 1}', encoding="utf-8")
            goal_module.save_goal(real_mem / "GOAL.json", {"units": [unit], "currentUnitId": "T"})
            jmem = root / "jmem"
            script = ("New-Item -ItemType Junction -Path '" + str(jmem).replace("'", "''") +
                      "' -Target '" + str(real_mem).replace("'", "''") + "' | Out-Null")
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                           check=True, capture_output=True)
            try:
                jgoal = jmem / "GOAL.json"
                sink = io.StringIO()
                try:
                    with contextlib.redirect_stdout(sink):
                        goal_module.state_projection(jgoal, unit, "verified")
                except SystemExit:
                    assert "STATE mirror" in sink.getvalue(), sink.getvalue()
                else:
                    raise AssertionError("STATE was read through a junctioned ledger directory")
                assert goal_module.transition_recovery_path(jgoal).name == ".goal-transition-recovery.json"
                try:
                    goal_module.load_transition_recovery(jgoal)
                except RuntimeError as exc:
                    assert "unreadable" in str(exc), str(exc)
                else:
                    raise AssertionError("recovery record was loaded through a junction")
                try:
                    goal_module.refuse_partial_tail(jmem / "events.jsonl")
                except RuntimeError as exc:
                    assert "cannot be safely read" in str(exc), str(exc)
                else:
                    raise AssertionError("events tail preflight read through a junction")
            finally:
                jmem.rmdir()
            print(f"SKIP native file-symlink cases (privilege unavailable: {privilege}); junctioned ledger cases proved", flush=True)
            print("PASS Sol-a11 no-link STATE re-read, recovery record and events tail regressions", flush=True)
            sol_a12_regressions(goal_module)
            return
        # 1. Same-preimage STATE swapped for a link after the preflight read.
        projection = goal_module.state_projection(goal_path, unit, "verified")
        (outside / "STATE.json").write_bytes(state_bytes)
        state_path.unlink()
        os.symlink(outside / "STATE.json", state_path)
        try:
            goal_module.write_state_projection(projection, goal_path, unit, "verified", "1")
        except RuntimeError as exc:
            assert "STATE mirror" in str(exc), str(exc)
        else:
            raise AssertionError("projection re-read STATE through a swapped link")
        assert (outside / "STATE.json").read_bytes() == state_bytes, "linked STATE target was written"
        state_path.unlink()
        state_path.write_bytes(state_bytes)
        # 2. Recovery instructions behind a link are refused before any parsing.
        recovery_path = goal_module.transition_recovery_path(goal_path)
        (outside / "recovery.json").write_text('{"version": 1}', encoding="utf-8")
        os.symlink(outside / "recovery.json", recovery_path)
        try:
            goal_module.load_transition_recovery(goal_path)
        except RuntimeError as exc:
            assert "no-link" in str(exc), str(exc)
        else:
            raise AssertionError("recovery record was loaded through a link")
        recovery_path.unlink()
        assert goal_module.load_transition_recovery(goal_path) is None
        # 3. The events tail preflight refuses a linked log instead of following it.
        events_path = mem / "events.jsonl"
        (outside / "events.jsonl").write_bytes(b'{"decision":"activated"}\n')
        os.symlink(outside / "events.jsonl", events_path)
        try:
            goal_module.refuse_partial_tail(events_path)
        except RuntimeError as exc:
            assert "no-link" in str(exc) or "cannot be safely read" in str(exc), str(exc)
        else:
            raise AssertionError("events tail preflight followed a linked log")
        events_path.unlink()
        events_path.write_bytes(b'{"decision":"activated"}\n')
        goal_module.refuse_partial_tail(events_path)
        events_path.write_bytes(b'{"decision":"activated"}')
        try:
            goal_module.refuse_partial_tail(events_path)
        except RuntimeError as exc:
            assert "partial final record" in str(exc), str(exc)
        else:
            raise AssertionError("partial tail was accepted")
    print("PASS Sol-a11 no-link STATE re-read, recovery record and events tail regressions", flush=True)
    sol_a12_regressions(goal_module)


def sol_a12_regressions(goal_module) -> None:
    """Sol-a12: every Goal and task ledger read is anchored no-follow and fail-closed."""
    unit_log = module("route_unit_log", ROOT / "skills/task/scripts/itd_unit_log.py")
    with tempfile.TemporaryDirectory(prefix="route-sol-a12-") as td:
        root = Path(td)
        mem = root / ".itd-memory"
        mem.mkdir()
        goal_path = mem / "GOAL.json"
        unit = {"id": "T", "status": "in_progress", "riskTier": "low",
                "criterion": "c", "verificationCommand": "true"}
        goal_module.save_goal(goal_path, {"units": [unit], "currentUnitId": "T"})
        activated = json.dumps({"type": "unit", "actor": "harness", "name": "T", "ledger": "GOAL.json",
                                "decision": "activated", "at": "2026-01-01T00:00:00+00:00",
                                "evidence": "x", "transaction": "a" * 32}).encode("utf-8") + b"\n"
        events_path = mem / "events.jsonl"
        state_bytes = json.dumps({"currentUnit": {"id": "T", "ledger": "GOAL.json",
                                                  "status": "in_progress"}}).encode("utf-8")
        state_path = mem / "STATE.json"
        outside = root / "outside"
        outside.mkdir()
        (outside / "events.jsonl").write_bytes(activated)
        (outside / "STATE.json").write_bytes(state_bytes)

        # 1. A malformed record makes the ledger ambiguous: transition and
        # recovery readers refuse instead of skipping to an earlier state.
        events_path.write_bytes(activated + b'{"type": "unit", "name": "T"\n')
        for label, call in (
            ("current_canonical_event", lambda: goal_module.current_canonical_event(goal_path, "T", "activated")),
            ("event_with_transaction", lambda: goal_module.event_with_transaction(goal_path, "a" * 32)),
            ("has_activation_event", lambda: goal_module.has_activation_event(goal_path, "T")),
            ("task has_event", lambda: unit_log.has_event(mem, "T", "activated")),
            ("task landed_terminal_event", lambda: unit_log.landed_terminal_event(
                mem, {}, "T", "GOAL.json", "activated", "x", "harness")),
        ):
            try:
                call()
            except RuntimeError as exc:
                assert "malformed" in str(exc), f"{label}: {exc}"
            else:
                raise AssertionError(f"{label} skipped a malformed ledger record")
        events_path.write_bytes(activated)
        assert goal_module.current_canonical_event(goal_path, "T", "activated") is not None
        assert goal_module.event_with_transaction(goal_path, "a" * 32) is not None
        assert unit_log.has_event(mem, "T", "activated")

        # 2. Links at the ledger paths are refused by every read site.
        try:
            os.symlink(outside / "events.jsonl", root / "probe-link")
        except OSError as exc:
            if os.name != "nt":
                raise
            privilege = str(exc)
            real_mem = root / "real-mem"
            real_mem.mkdir()
            (real_mem / "events.jsonl").write_bytes(activated)
            (real_mem / "STATE.json").write_bytes(state_bytes)
            goal_module.save_goal(real_mem / "GOAL.json", {"units": [unit], "currentUnitId": "T"})
            jmem = root / "jmem"
            script = ("New-Item -ItemType Junction -Path '" + str(jmem).replace("'", "''") +
                      "' -Target '" + str(real_mem).replace("'", "''") + "' | Out-Null")
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                           check=True, capture_output=True)
            try:
                jgoal = jmem / "GOAL.json"
                for label, call in (
                    ("current_canonical_event", lambda: goal_module.current_canonical_event(jgoal, "T", "activated")),
                    ("event_with_transaction", lambda: goal_module.event_with_transaction(jgoal, "a" * 32)),
                    ("task landed_terminal_event", lambda: unit_log.landed_terminal_event(
                        jmem, {}, "T", "GOAL.json", "activated", "x", "harness")),
                    ("task load_state_snapshot", lambda: unit_log.load_state_snapshot(jmem)),
                    ("task append_event", lambda: unit_log.append_event(jmem, "T", "verified", "x", "GOAL.json")),
                ):
                    try:
                        call()
                    except RuntimeError:
                        continue
                    raise AssertionError(f"{label} read through a junctioned ledger directory")
            finally:
                jmem.rmdir()
            print(f"SKIP native file-symlink ledger cases (privilege unavailable: {privilege}); junctioned cases proved", flush=True)
            print("PASS Sol-a12 anchored fail-closed Goal and task ledger reader regressions", flush=True)
            sol_a13_regressions()
            return
        events_path.unlink()
        os.symlink(outside / "events.jsonl", events_path)
        os.symlink(outside / "STATE.json", state_path)
        for label, call in (
            ("current_canonical_event", lambda: goal_module.current_canonical_event(goal_path, "T", "activated")),
            ("event_with_transaction", lambda: goal_module.event_with_transaction(goal_path, "a" * 32)),
            ("task landed_terminal_event", lambda: unit_log.landed_terminal_event(
                mem, {}, "T", "GOAL.json", "activated", "x", "harness")),
            ("task load_state_snapshot", lambda: unit_log.load_state_snapshot(mem)),
            ("task load_state", lambda: unit_log.load_state(mem)),
            ("task append_event", lambda: unit_log.append_event(mem, "T", "verified", "x", "GOAL.json")),
        ):
            try:
                call()
            except RuntimeError as exc:
                assert "no-link" in str(exc), f"{label}: {exc}"
            else:
                raise AssertionError(f"{label} read through a linked ledger file")
        assert (outside / "events.jsonl").read_bytes() == activated, "linked events target was appended"
        events_path.unlink()
        state_path.unlink()
        events_path.write_bytes(activated)
        state_path.write_bytes(state_bytes)
        assert unit_log.load_state_snapshot(mem)[0]["currentUnit"]["id"] == "T"
        unit_log.append_event(mem, "T", "verified", "x", "GOAL.json")
        assert unit_log.has_event(mem, "T", "verified")
    print("PASS Sol-a12 anchored fail-closed Goal and task ledger reader regressions", flush=True)
    sol_a13_regressions()


def sol_a13_regressions() -> None:
    """Sol-a13: the bounded STATE lock, the efficacy current view, Windows
    private ownership and explicit criterion ownership are all fail-closed."""
    unit_log = module("route_a13_unit_log", ROOT / "skills/task/scripts/itd_unit_log.py")
    evidence = module("route_a13_review_evidence", ROOT / "skills/_shared/itd_review_evidence.py")
    efficacy = module("route_a13_efficacy", ROOT / "tests/verify_independent_review_efficacy.py")

    # 1. A criterion row that claims this unit but carries no usable id used to
    # be dropped silently, so the selector fell back to legacy prefix matching
    # and the prompt projection could review a different set from the evidence
    # validator for the same unit.  Malformed explicit ownership fails closed.
    legacy = {"id": "U-1-AC1", "criterion": "legacy"}
    foreign = {"id": 7, "unitId": "U-2"}
    for malformed in ({"id": 1, "unitId": "U-1"}, {"id": "", "unitId": "U-1"}, {"unitId": "U-1"}):
        try:
            evidence.active_criteria({"criteria": [malformed, legacy]}, "U-1")
        except evidence.ReviewEvidenceError as exc:
            assert "ownership" in str(exc), str(exc)
        else:
            raise AssertionError("malformed explicit criterion ownership fell back to prefix matching")
    # A malformed row owned by ANOTHER unit stays that unit's problem.
    assert evidence.active_criteria({"criteria": [foreign, legacy]}, "U-1") == [legacy]
    explicit = {"id": "X", "unitId": "U-1"}
    assert evidence.active_criteria({"criteria": [explicit, legacy]}, "U-1") == [explicit]

    # 2. The bounded STATE writer lock is opened anchored and no-follow: a link
    # or a second hard link at .STATE.write.lock would move the lock (and its
    # initialising byte) into a foreign file while every writer still believed
    # the STATE write was serialised.  Each backend names its own reason, so
    # the refusal is required by name and never by bare failure.
    named_refusal = ("no-link", "private", "not a safe directory/regular file", "foreign owner")
    with tempfile.TemporaryDirectory(prefix="route-sol-a13-lock-") as td:
        root = Path(td)
        mem = root / ".itd-memory"
        mem.mkdir()
        lock = mem / ".STATE.write.lock"
        outside = root / "outside-lock"
        outside.write_bytes(b"")
        try:
            os.symlink(outside, lock)
        except OSError as exc:
            print(f"SKIP native lock-symlink case (privilege unavailable: {exc})", flush=True)
        else:
            try:
                with unit_log.state_write_lock(mem):
                    pass
            except (RuntimeError, OSError) as exc:
                assert any(reason in str(exc) for reason in named_refusal), str(exc)
            else:
                raise AssertionError("bounded STATE lock was taken through a linked lock file")
            assert outside.read_bytes() == b"", "linked lock target was initialised through the lock"
            lock.unlink()
        lock.write_bytes(b"\0")
        hard = root / "lock-hardlink"
        try:
            os.link(lock, hard)
        except OSError as exc:
            print(f"SKIP native lock hard-link case: {exc}", flush=True)
        else:
            try:
                with unit_log.state_write_lock(mem):
                    pass
            except (RuntimeError, OSError) as exc:
                assert any(reason in str(exc) for reason in named_refusal), str(exc)
            else:
                raise AssertionError("bounded STATE lock accepted a multi-link lock file")
            hard.unlink()
        # The ordinary file still serialises, including the reentrant path.
        with unit_log.state_write_lock(mem):
            with unit_log.state_write_lock(mem):
                pass

    # 3. The current efficacy view is read through the anchored no-follow
    # reader: a link planted at results/<name>.json would otherwise bind
    # foreign bytes to a current-producer diagnostic entry of the archive.
    with tempfile.TemporaryDirectory(prefix="route-sol-a13-efficacy-") as td:
        root = Path(td)
        results = root / "results"
        results.mkdir()
        payload = b'{"observation": "current"}'
        (root / "outside.json").write_bytes(payload)
        current = results / "semantic.json"
        producer_sha = "b" * 64
        history = {Path("history/semantic.json"): {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "classification": "diagnostic",
            "sourceProducerSha256": producer_sha,
        }}
        try:
            os.symlink(root / "outside.json", current)
        except OSError as exc:
            print(f"SKIP native efficacy current-view symlink case (privilege unavailable: {exc})", flush=True)
        else:
            try:
                efficacy.validate_current_result_archive_binding(current, history, producer_sha)
            except (RuntimeError, OSError) as exc:
                assert "no-link" in str(exc) or "regular" in str(exc), str(exc)
            else:
                raise AssertionError("efficacy current view was read through a link")
            current.unlink()
        current.write_bytes(payload)
        efficacy.validate_current_result_archive_binding(current, history, producer_sha)

    # 4. A private Windows open must also prove ownership, mirroring the POSIX
    # st_uid rule: the link count alone leaves a foreign-owned file planted at
    # a ledger path acceptable as the destination of a trusted append.
    if os.name != "nt":
        print("SKIP Windows private-ownership case: the native adapter only loads on Windows; "
              "the POSIX st_uid rule is enforced by _private_fd and exercised by the append cases",
              flush=True)
    else:
        backend = module("route_a13_windows", ROOT / "skills/_shared/itd_safe_atomic_windows.py").backend()
        with tempfile.TemporaryDirectory(prefix="route-sol-a13-owner-") as td:
            target = Path(td) / "events.jsonl"
            backend.durable_append_bytes(target, b"{}\n")
            original = backend.owner_identities()
            # SID of LocalSystem: a real, well-formed identity this process is not.
            backend._owner_identities = (b"\x01\x01\x00\x00\x00\x00\x00\x05\x12\x00\x00\x00",)
            try:
                backend.durable_append_bytes(target, b"{}\n")
            except RuntimeError as exc:
                assert "owner" in str(exc), str(exc)
            else:
                raise AssertionError("Windows private append accepted a foreign-owned destination")
            finally:
                backend._owner_identities = original
            backend.durable_append_bytes(target, b"{}\n")
            assert target.read_bytes() == b"{}\n{}\n"
    print("PASS Sol-a13 anchored STATE lock, efficacy current view, Windows ownership and "
          "explicit criterion ownership regressions", flush=True)


def run_suites(suites: tuple[str, ...]) -> bool:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    for suite in suites:
        try:
            result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / suite)], cwd=ROOT,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=600, env=env)
        except subprocess.TimeoutExpired:
            print(f"FAIL {suite}: exceeded600s; inspect the owned test process and its log", file=sys.stderr)
            return False
        print(f"{'PASS' if result.returncode == 0 else 'FAIL'} {suite}", flush=True)
        if result.returncode:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            return False
    return True


def main() -> int:
    # The aggregate forwards decoded child diagnostics. Native ``-I`` starts
    # with the Windows ANSI stdout codec, which cannot represent all valid
    # UTF-8 diagnostic text; configure only this transport, never child argv.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-metadata", action="store_true")
    parser.add_argument("--installed-proof", type=Path)
    parser.add_argument("--native-proof", type=Path)
    parser.add_argument("--native-test-log", type=Path)
    args = parser.parse_args()
    if args.native_proof:
        proof, expected = load_proof(args.native_proof)
        host = next(h for h in proof["hosts"] if h["platform"] == platform.system())
        print(json.dumps(validate_native_record(args.native_proof, host, expected), sort_keys=True))
        return 0
    if args.native_test_log:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            repair_regressions()
            passed = run_suites(REGRESSIONS)
        raw = output.getvalue().encode("utf-8")
        with args.native_test_log.open("xb") as handle:
            handle.write(raw)
        sys.stdout.buffer.write(raw)
        return 0 if passed else 1
    repair_regressions()
    if not run_suites(HOST_METADATA if args.host_metadata else REGRESSIONS):
        return 1
    if args.installed_proof:
        try:
            installed_proof(args.installed_proof)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"FAIL {args.installed_proof}: {exc}; obtain valid native rollout evidence", file=sys.stderr)
            return 1
        print("PASS installed WSL/Windows runtime and Claude/Codex adapter evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
