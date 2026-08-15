#!/usr/bin/env python3
import argparse, importlib, json, sys, tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLI = importlib.import_module("scripts.itd")

def rejects(fn):
    try:
        fn()
    except CLI.gate.GateError as e:
        assert e.status == "UNVERIFIED"
    else:
        raise AssertionError

with tempfile.TemporaryDirectory() as raw:
    p = Path(raw)/"r"
    row = {"repository": "owner/repo", "checkout": str(p)}
    reg = {"repositories": [row]}
    assert CLI.repository_entry(reg, p, "owner/repo") is row
    rejects(lambda: CLI.repository_entry(reg, Path(raw)/"x", "owner/repo"))

for fn in (
    lambda: CLI.apply_ruleset(argparse.Namespace(repository="malformed",
        scope="repository", ruleset_id=None)),
    lambda: CLI.observe_enrollment(argparse.Namespace(repository="malformed")),
):
    rejects(fn)
with mock.patch.object(CLI.subprocess, "run", side_effect=AssertionError):
    assert CLI.run([sys.executable, "-c", "print('ok')"]).stdout == b"ok\n"
with mock.patch.object(CLI, "MAX_COMMAND_OUTPUT", 128):
    rejects(lambda: CLI.run([sys.executable, "-c",
                             "print('x'*129,end='')"]))
rows = json.loads((ROOT/".itd/VERIFICATION_CONTRACT.json").read_text())["commands"]
rows = {x["id"]: x for x in rows}
for n in ("external-reviewer-release-regression", "host-adapter-regression"):
    assert rows[n]["passFailParser"] == "exit_code_zero" and not rows[n]["expectedOutput"]
# The efficacy verifier's host pin is a REQUIRED argparse input: an entry that
# omits it exits 2 before any check runs, so every contract-driven gate
# (itd_hygiene.py close) reads red for a reason that has nothing to do with the
# candidate. The pin file itself is a host input under git-ignored
# .itd-memory/, so it must NOT be declared as a trusted verifier path -
# trustedVerifierPaths entries are required to be tracked clean blobs.
efficacy = rows["independent-review-efficacy"]
argv = efficacy["argv"]
flag = "--expected-keyring-sha256-file"
assert flag in argv, "efficacy entry lost its required host pin flag"
pin = argv[argv.index(flag) + 1]
assert pin and not pin.startswith("-"), "host pin flag has no path argument"
assert pin not in efficacy["trustedVerifierPaths"], (
    "host pin is a git-ignored host input, not a trusted verifier path")

print(json.dumps({"status": "PASSED"}))
