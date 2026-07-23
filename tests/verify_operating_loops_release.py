#!/usr/bin/env python3
"""Fail-closed publication and active-install proof for operating loops v1.93.0."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.93.0"
DEFAULT_BRANCH = "codex/operating-loops-v1"
RECIPES = (
    "state freshness",
    "test regression",
    "dependency health",
    "security posture",
    "review drift",
    "documentation drift",
)
EXPECTED_CHANGED = {
    ".github/workflows/meta-review.yml",
    ".github/workflows/windows-verify.yml",
    ".claude-plugin/marketplace.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "CHANGELOG.md",
    "AGENTS.md",
    "LAUNCH_PLAN.md",
    "README.md",
    "README.ru.md",
    "agents/code-reviewer.md",
    "benchmarks/working-deadline/CORPUS.json",
    "benchmarks/working-deadline/CORPUS.sha256",
    "docs/CODEX_ADAPTER.md",
    "docs/CONTRACTS.md",
    "docs/HARNESS_CONFORMANCE_REPORT.md",
    "docs/HARNESS_DOCS_STATE.json",
    "docs/HARNESS_ENGINEERING_MAP.md",
    "docs/HOST_ADAPTER_CONTRACT.md",
    "docs/OPERATING_LOOPS.md",
    "docs/QUALITY.json",
    "docs/VERIFICATION_LOOP.md",
    "docs/adr/ADR-003-proof-carrying-verification-loop.md",
    "docs/external-validation/OPERATING_LOOP_STORIES.md",
    "docs/external-validation/PROTOCOL.md",
    "docs/host-adapters.json",
    "docs/templates/global-claude-md.md",
    "docs/templates/itd/OPERATING_LOOP_CONTRACT.json",
    "docs/templates/itd/OPERATING_LOOP_CONTRACT.schema.json",
    "docs/templates/itd/OPERATING_LOOP_FAILURE_STORY.json",
    "docs/templates/itd/OPERATING_LOOP_RUN.schema.json",
    "docs/templates/itd/OPERATING_LOOP_STORY.schema.json",
    "docs/templates/itd/OPERATING_LOOP_SUCCESS_STORY.json",
    "docs/templates/global-codex-agents.md",
    "docs/templates/itd-memory/goal.schema.json",
    "docs/templates/itd/VERIFICATION_CONTRACT.json",
    "docs/templates/itd/VERIFICATION_LOOP_CONTRACT.json",
    "hooks/check-dod-before-commit.sh",
    "hooks/validate_state_core.py",
    "scripts/itd_external_outcomes.py",
    "skills/_shared/VERIFICATION_LOOP_POLICY.json",
    "skills/_shared/WORKING_DEADLINE_POLICY.json",
    "skills/_shared/itd_verification_loop.py",
    "skills/_shared/OPERATING_LOOP_POLICY.json",
    "skills/_shared/OPERATING_LOOP_RECIPES.json",
    "skills/_shared/itd_operating_loops.py",
    "skills/goal/SKILL.md",
    "skills/goal/scripts/itd_goal_verify.py",
    "skills/kickstart/SKILL.md",
    "skills/review/SKILL.md",
    "skills/review/scripts/itd_review_cache.py",
    "skills/security-audit/SKILL.md",
    "skills/task/SKILL.md",
    "tests/run-all.sh",
    "tests/verification_loop_fixture.py",
    "tests/verify_all_hard_gate_host_parity.py",
    "tests/verify_dod_gate.py",
    "tests/verify_goal_bounded_autonomy.py",
    "tests/verify_operating_loops.py",
    "tests/verify_operating_loops_release.py",
    "tests/verify_review_cache.py",
    "tests/verify_review_sentinel_diffbind.py",
    "tests/verify_risk_score.py",
    "tests/verify_verification_loop.py",
    "tests/verify_work_deadline_contract.py",
}


class ReleaseError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def run(*args: str, cwd: Path = ROOT, timeout: int = 60) -> str:
    proc = subprocess.run(
        args, cwd=cwd, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=timeout,
    )
    if proc.returncode:
        raise ReleaseError(
            f"command failed ({proc.returncode}): {' '.join(args)}\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_file(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def candidate_checks() -> dict:
    manifests = (
        json_file(".claude-plugin/plugin.json"),
        json_file(".codex-plugin/plugin.json"),
    )
    marketplace = json_file(".claude-plugin/marketplace.json")
    require(all(item.get("version") == VERSION for item in manifests),
            "plugin manifests are not synchronized at v1.93.0")
    plugins = marketplace.get("plugins", [])
    require(len(plugins) == 1 and plugins[0].get("version") == VERSION,
            "marketplace version is not synchronized at v1.93.0")
    require(f"## [{VERSION}]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            "dated v1.93.0 changelog entry is missing")
    for relative in ("README.md", "README.ru.md", "docs/OPERATING_LOOPS.md", "CHANGELOG.md"):
        text = " ".join((ROOT / relative).read_text(encoding="utf-8").lower().split())
        missing = [recipe for recipe in RECIPES if recipe not in text]
        require(not missing, f"{relative} omits registry recipes: {missing}")
    run_all = (ROOT / "tests/run-all.sh").read_text(encoding="utf-8")
    require("verify_operating_loops_release" in run_all,
            "release verifier is not registered in tests/run-all.sh")
    missing_files = [relative for relative in sorted(EXPECTED_CHANGED)
                     if not (ROOT / relative).is_file()]
    require(not missing_files,
            f"release candidate is missing declared files: {missing_files}")
    return {"version": VERSION, "declaredFiles": len(EXPECTED_CHANGED)}


def publication_checks(branch: str) -> dict:
    result = candidate_checks()
    current = run("git", "branch", "--show-current")
    require(current == branch, f"wrong publication branch: {current!r}")
    require(not run("git", "status", "--porcelain"),
            "publication checkout has tracked or untracked drift")
    head = run("git", "rev-parse", "HEAD")
    tree = run("git", "rev-parse", "HEAD^{tree}")
    remote_rows = run("git", "ls-remote", "--heads", "origin", branch).splitlines()
    require(len(remote_rows) == 1 and remote_rows[0].split()[0] == head,
            "origin branch does not resolve to local HEAD")
    gh = shutil.which("gh") or shutil.which("gh.exe")
    require(bool(gh), "GitHub CLI is required to verify the pull request")
    raw = run(str(gh), "pr", "view", branch, "--repo", "hihol-labs/idea-to-deploy",
              "--json", "state,headRefName,headRefOid,baseRefName,baseRefOid,changedFiles,url,title,body")
    pr = json.loads(raw)
    require(pr.get("state") == "OPEN", "release pull request is not open")
    require(pr.get("headRefName") == branch and pr.get("headRefOid") == head,
            "pull request is not bound to the published HEAD")
    require(pr.get("baseRefName") == "main", "pull request base is not main")
    base = str(pr.get("baseRefOid") or "")
    remote_main = run("git", "ls-remote", "--heads", "origin", "main").splitlines()
    require(len(remote_main) == 1 and remote_main[0].split()[0] == base,
            "pull request base OID is not the current origin/main OID")
    run("git", "cat-file", "-e", f"{base}^{{commit}}")
    changed = set(filter(None, run("git", "diff", "--name-only", base, head).splitlines()))
    require(changed == EXPECTED_CHANGED and pr.get("changedFiles") == len(EXPECTED_CHANGED),
            f"published/PR scope differs: missing={sorted(EXPECTED_CHANGED - changed)} "
            f"extra={sorted(changed - EXPECTED_CHANGED)}")
    body = str(pr.get("body") or "")
    matches = re.findall(r"<!-- ITD_RELEASE_EVIDENCE\s*(\{.*?\})\s*-->", body, re.DOTALL)
    require(len(matches) == 1, "pull request lacks one structured ITD release evidence block")
    evidence = json.loads(matches[0])
    expected_evidence = {
        "schemaVersion": 1,
        "candidateTree": tree,
        "unit": "PE5-022",
        "adjudication": "PASSED",
        "checks": {
            "operatingLoops": "PASSED",
            "hostAdapters": "PASSED",
            "metaReview": "PASSED",
            "quickRegression": "PASSED",
            "fullRegression": "PASSED",
        },
    }
    require(evidence == expected_evidence,
            "pull request structured evidence is not exact or candidate-bound")
    result.update({"branch": branch, "head": head, "tree": tree, "pr": pr.get("url")})
    return result


def windows_home() -> Path:
    explicit = os.environ.get("ITD_WINDOWS_HOME")
    if explicit:
        return Path(explicit)
    require(os.name != "nt", "set ITD_WINDOWS_HOME when running deployment proof on Windows")
    profile = run("cmd.exe", "/d", "/c", "echo", "%USERPROFILE%", cwd=ROOT).splitlines()[-1].strip()
    mounted = run("wslpath", "-u", profile, cwd=ROOT)
    return Path(mounted)


def tracked_hashes(root: Path) -> dict[str, str]:
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
        cwd=root, capture_output=True, timeout=60,
    )
    require(proc.returncode == 0, "cannot enumerate published Git tree")
    result: dict[str, str] = {}
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, encoded = raw.split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split()
        require(mode in {"100644", "100755"} and object_type == "blob",
                f"unsupported published object for deployment: {encoded!r} mode={mode} type={object_type}")
        name = encoded.decode("utf-8", "surrogateescape")
        blob = subprocess.run(
            ["git", "cat-file", "blob", oid], cwd=root, capture_output=True, timeout=60,
        )
        require(blob.returncode == 0, f"cannot read Git blob for {name}")
        result[name] = sha256_bytes(blob.stdout)
    return result


def reject_link_escape(path: Path, windows: bool, recursive: bool = True) -> None:
    require(path.exists(), f"install path is missing: {path}")
    require(path.is_absolute() and ".." not in path.parts,
            f"install path must be literal and absolute: {path}")
    cursor = path
    while True:
        require(not cursor.is_symlink(), f"symlink ancestor is forbidden: {cursor}")
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    if recursive and path.is_dir():
        for current, directories, files in os.walk(path, followlinks=False):
            current_path = Path(current)
            for name in directories:
                child = current_path / name
                mode = child.stat(follow_symlinks=False).st_mode
                require(stat.S_ISDIR(mode) and not child.is_symlink(),
                        f"linked/special directory is forbidden in install: {child}")
            for name in files:
                child = current_path / name
                mode = child.stat(follow_symlinks=False).st_mode
                require(stat.S_ISREG(mode) and not child.is_symlink(),
                        f"linked/special file is forbidden in install: {child}")
    if not windows:
        return
    win_path = run("wslpath", "-w", str(path), cwd=ROOT)
    escaped = win_path.replace("'", "''")
    recurse = (
        "$items += @(Get-ChildItem -LiteralPath $root.FullName -Force -Recurse -ErrorAction Stop);"
        if recursive and path.is_dir() else ""
    )
    script = (
        f"$root=Get-Item -LiteralPath '{escaped}' -Force -ErrorAction Stop;"
        "$items=@($root);$p=$root.Parent;while($null -ne $p){$items+=@($p);$p=$p.Parent};"
        f"{recurse}"
        "$bad=@($items|Where-Object{($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0});"
        "if($bad.Count -ne 0){$bad|ForEach-Object{$_.FullName};exit 3}"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, timeout=120,
    )
    require(proc.returncode == 0,
            f"Windows reparse-point escape detected at {path}: "
            f"{proc.stdout.decode('utf-8', errors='replace').strip()}")


def actual_hashes(root: Path, windows: bool) -> dict[str, str]:
    require(root.is_dir(), f"install directory is missing: {root}")
    reject_link_escape(root, windows)
    result: dict[str, str] = {}
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            path = current_path / name
            require(not path.is_symlink(), f"symlink directory is forbidden in install: {path}")
        for name in files:
            path = current_path / name
            mode = path.stat(follow_symlinks=False).st_mode
            require(stat.S_ISREG(mode) and not path.is_symlink(),
                    f"special/symlink file is forbidden in install: {path}")
            result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def verify_codex_cache(home: Path, expected: dict[str, str], windows: bool) -> str:
    target = home / ".codex" / "plugins" / "cache" / "personal" / "idea-to-deploy" / VERSION
    actual = actual_hashes(target, windows)
    require(actual == expected,
            f"Codex cache hash drift at {target}: missing={sorted(set(expected) - set(actual))[:5]} "
            f"extra={sorted(set(actual) - set(expected))[:5]}")
    return str(target)


def claude_expected(tracked: dict[str, str]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for name, digest in tracked.items():
        rel = Path(name)
        if rel.parts[0] == "skills":
            target = name
        elif rel.parts[0] == "agents" and rel.suffix == ".md":
            target = name
        elif rel.parts[0] == "hooks" and rel.suffix in {".sh", ".py"}:
            target = name
        elif len(rel.parts) == 4 and rel.parts[:2] == ("docs", "templates") and rel.parts[2] in {"itd", "itd-memory"}:
            target = Path("templates", *rel.parts[2:]).as_posix()
        elif name == "scripts/itd_otel_export.py":
            target = name
        else:
            continue
        expected[target] = digest
    return expected


def desired_hooks() -> dict:
    source = (ROOT / "scripts" / "sync-to-active.sh").read_text(encoding="utf-8")
    match = re.search(r"DESIRED_HOOKS=\$\(cat <<'JSON'\n(.+?)\nJSON\n\)", source, re.DOTALL)
    require(bool(match), "cannot locate managed Claude hooks in sync-to-active.sh")
    return json.loads(match.group(1))


def normalized_windows_hooks(desired: dict, home: Path, actual: dict) -> dict:
    normalized = json.loads(json.dumps(desired))
    win_home = run("wslpath", "-w", str(home), cwd=ROOT).replace("\\", "/")
    expected_root = f"{win_home}/.claude/hooks/"
    interpreter = os.environ.get("ITD_WIN_PYTHON", "").strip().replace("\\", "/")
    require(bool(interpreter),
            "ITD_WIN_PYTHON must bind deployment proof to the sync interpreter override")
    mounted_interpreter = Path(run("wslpath", "-u", interpreter, cwd=ROOT))
    reject_link_escape(mounted_interpreter, True, recursive=False)
    require(mounted_interpreter.is_file(), "ITD_WIN_PYTHON does not name a regular file")
    for event, groups in normalized.items():
        actual_groups = actual.get(event)
        require(isinstance(actual_groups, list) and len(actual_groups) == len(groups),
                f"Windows Claude settings group drift for {event}")
        for group, actual_group in zip(groups, actual_groups):
            require(group.get("matcher") == actual_group.get("matcher"),
                    f"Windows Claude matcher drift for {event}")
            hooks = group.get("hooks", [])
            actual_hooks = actual_group.get("hooks", [])
            require(len(hooks) == len(actual_hooks), f"Windows Claude hook count drift for {event}")
            for hook, actual_hook in zip(hooks, actual_hooks):
                script_match = re.search(r"([a-z0-9-]+\.sh)$", hook["command"])
                require(bool(script_match), "unexpected canonical Claude hook command")
                command = str(actual_hook.get("command") or "").replace("\\", "/")
                suffix = expected_root + script_match.group(1)
                expected_command = f'"{interpreter}" -X utf8 "{suffix}"'
                require(command == expected_command,
                        f"Windows Claude wrapper drift for {script_match.group(1)}")
                hook["command"] = command
    return normalized


def verify_claude(home: Path, expected: dict[str, str], windows: bool) -> str:
    target = home / ".claude"
    require(target.is_dir(), f"Claude home is missing: {target}")
    for relative in ("skills", "agents", "hooks", "templates", "scripts"):
        reject_link_escape(target / relative, windows)
    reject_link_escape(target / "settings.json", windows, recursive=False)
    reject_link_escape(target / "CLAUDE.md", windows, recursive=False)
    drift = [name for name, digest in expected.items()
             if not (target / name).is_file()
             or (target / name).is_symlink()
             or not stat.S_ISREG((target / name).stat(follow_symlinks=False).st_mode)
             or sha256(target / name) != digest]
    require(not drift, f"Claude active install hash drift at {target}: {drift[:8]}")
    settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
    managed = {key: settings.get("hooks", {}).get(key) for key in desired_hooks()}
    canonical = desired_hooks()
    if windows:
        canonical = normalized_windows_hooks(canonical, home, managed)
    require(managed == canonical, f"Claude managed settings drift at {target / 'settings.json'}")
    return str(target)


def verify_router(path: Path, host: str, windows: bool) -> None:
    reject_link_escape(path, windows, recursive=False)
    require(path.is_file(), f"global {host} router is missing: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if "Codex" in host:
        expected = (ROOT / "docs" / "templates" / "global-codex-agents.md").read_text(encoding="utf-8")
        require(text == expected, f"global {host} router differs from the canonical policy: {path}")
        return
    template = (ROOT / "docs" / "templates" / "global-claude-md.md").read_text(encoding="utf-8")
    begin = "<!-- ITD:BEGIN"
    end = "<!-- ITD:END methodology -->"
    require(text.count(begin) == 1 and text.count(end) == 1,
            f"global {host} must contain exactly one managed ITD block: {path}")
    require(template.count(begin) == 1 and template.count(end) == 1,
            "canonical Claude template must contain exactly one managed ITD block")
    tb, te = template.find(begin), template.find(end)
    ab, ae = text.find(begin), text.find(end)
    require(min(tb, te, ab, ae) >= 0, f"managed ITD block is missing in {path}")
    require(text[ab:ae + len(end)] == template[tb:te + len(end)],
            f"global {host} managed policy differs from the canonical block: {path}")
    lowered = text.lower()
    require("product factory" not in lowered and "pfo_global" not in lowered,
            f"global {host} contains legacy PFO policy outside the canonical block")


def deployment_checks(branch: str, wsl: Path | None, windows: Path | None) -> dict:
    result = publication_checks(branch)
    wsl_home = (wsl or Path.home()).absolute()
    win_home = (windows or windows_home()).absolute()
    source = tracked_hashes(ROOT)
    claude = claude_expected(source)
    result["codexInstalls"] = [
        verify_codex_cache(wsl_home, source, False),
        verify_codex_cache(win_home, source, True),
    ]
    result["claudeInstalls"] = [verify_claude(wsl_home, claude, False), verify_claude(win_home, claude, True)]
    verify_router(wsl_home / ".codex" / "AGENTS.md", "WSL Codex", False)
    verify_router(win_home / ".codex" / "AGENTS.md", "Windows Codex", True)
    verify_router(wsl_home / ".claude" / "CLAUDE.md", "WSL Claude", False)
    verify_router(win_home / ".claude" / "CLAUDE.md", "Windows Claude", True)
    result["routers"] = 4
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("candidate", "publication", "deployment"), default="candidate")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--wsl-home", type=Path)
    parser.add_argument("--windows-home", type=Path)
    args = parser.parse_args()
    try:
        if args.phase == "candidate":
            details = candidate_checks()
        elif args.phase == "publication":
            details = publication_checks(args.branch)
        else:
            details = deployment_checks(args.branch, args.wsl_home, args.windows_home)
    except (ReleaseError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"phase": args.phase, "status": "PASSED", **details}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
