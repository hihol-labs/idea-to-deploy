#!/usr/bin/env python3
import copy, importlib, json, os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
H = importlib.import_module("verify_session_hygiene_quality")
init_repo = H.init_repo
runner = H.runner
write_json = H.write_json
git = H.git


def main():
    failures = []
    with tempfile.TemporaryDirectory() as td:
        repo = init_repo(Path(td))
        path = repo / ".itd" / "VERIFICATION_CONTRACT.json"
        valid = json.loads(path.read_text(encoding="utf-8"))
        valid["version"] = 2
        for v in ("2", 3):
            contract = copy.deepcopy(valid)
            contract["version"] = v
            write_json(path, contract)
            result = runner(repo, "close")
            if result.returncode != 1 or (
                "verification contract version is unsupported"
                not in result.stdout
            ):
                failures.append(f"version-{v}")
        protected_v1 = copy.deepcopy(valid)
        protected_v1["version"] = 1
        write_json(path, protected_v1)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "seed protected v1")
        env = os.environ.copy()
        env["ITD_PROTECTED_BASE_SHA"] = git(
            repo, "rev-parse", "HEAD").stdout.strip()
        result = runner(repo, "close", env=env)
        if (result.returncode != 1
                or "protected execution requires verification contract "
                "version 2" not in result.stdout):
            failures.append("protected-v1")
        cases = (
            ("missing", None, "commands[] is empty"),
            ("empty", [], "commands[] is empty"),
            ("non-object", ["skip"], "command is not an object"),
        )
        for label, commands, expected in cases:
            contract = copy.deepcopy(valid)
            if commands is None:
                contract.pop("commands")
            else:
                contract["commands"] = commands
            write_json(path, contract)
            result = runner(repo, "close")
            if result.returncode != 1 or expected not in result.stdout:
                failures.append(label)
        checks = (
            ("python-isolation", ["python3", "src/app.py"], ["src/app.py"],
             "not isolated with -I"),
            ("python-isolation-order", ["python3", "src/app.py", "-I"],
             ["src/app.py"], "not isolated with -I"),
            ("pypy-isolation", ["pypy3", "src/app.py"], ["src/app.py"],
             "not isolated with -I"),
            ("python-option-operand",
             ["python3", "-I", "-X", "src/app.py", "untrusted.py"],
             ["src/app.py"], "Python interpreter options are unsupported"),
            ("absolute-path", [sys.executable, "-I", "/src/app.py"],
             ["src/app.py"], "dispatcher does not directly invoke"),
            ("traversal", [sys.executable, "-I", "src/../untrusted.py"],
             ["src"], "dispatcher does not directly invoke"),
            ("launcher-only",
             ["sh", "src/itd_py.sh", "--itd-isolated", "untrusted.py"],
             ["src"], "dispatcher does not directly invoke"),
        )
        for label, argv, paths, expected in checks:
            contract = copy.deepcopy(valid)
            command = contract["commands"][0]
            command["argv"] = argv
            command["trustedVerifierPaths"] = paths
            if label == "traversal":
                (repo / "untrusted.py").write_text(
                    "raise SystemExit(0)\n", encoding="utf-8")
            write_json(path, contract)
            git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
            git(repo, "commit", "-qm", f"seed {label}")
            env["ITD_PROTECTED_BASE_SHA"] = git(
                repo, "rev-parse", "HEAD").stdout.strip()
            result = runner(repo, "close", env=env)
            if result.returncode != 1 or expected not in result.stdout:
                failures.append(label)
        for label, parser, expected_output in (
            ("empty-sentinel", "stdout_contains", ""),
            ("unknown-parser", "unknown_parser", "pass"),
        ):
            contract = copy.deepcopy(valid)
            command = contract["commands"][0]
            command["argv"] = [sys.executable, "-I", "src/app.py"]
            command["trustedVerifierPaths"] = ["src/app.py"]
            command["passFailParser"] = parser
            command["expectedOutput"] = expected_output
            write_json(path, contract)
            git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
            git(repo, "commit", "-qm", f"seed {label}")
            env["ITD_PROTECTED_BASE_SHA"] = git(
                repo, "rev-parse", "HEAD").stdout.strip()
            result = runner(repo, "close", env=env)
            if (result.returncode != 1
                    or "passFailParser or expectedOutput is invalid"
                    not in result.stdout):
                failures.append(label)
    if failures:
        print(json.dumps({"failures": failures, "status": "FAILED"}))
        return 1
    print(json.dumps({"cases": 15, "status": "PASSED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
