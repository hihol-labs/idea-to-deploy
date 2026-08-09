#!/usr/bin/env python3
"""Oracle for live gate-registry write isolation (GPG-004-PB3).

RED-first target: on 2026-08-09 the live registry ``~/.config/itd/gates.json``
was overwritten by a test-fixture row (``checkout:
/tmp/itd_gate_local_review_commit``) because a rehearsal write went to the
un-overridden default registry path. This oracle requires the writer guard:
a registry write whose row checkout lies under the system temp directory must
refuse to target the un-overridden live default path, while explicit
``ITD_GATE_REGISTRY`` / explicit-path targets and non-fixture rows keep
working. The real live registry must stay byte-identical across this suite.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "itd.py"

checks = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(f"{name}: {detail}"[:400])


# Pin the real live registry before any patching: the suite itself must never
# touch it (the exact leak this oracle exists to prevent).
def live_registry_bytes() -> bytes | None:
    if os.name == "nt":
        base = Path(os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        target = base / "ITD" / "gates.json"
    else:
        target = Path.home() / ".config" / "itd" / "gates.json"
    try:
        return target.read_bytes()
    except OSError:
        return None


LIVE_BEFORE = live_registry_bytes()

spec = importlib.util.spec_from_file_location("itd_cli_isolation_test", MODULE)
assert spec and spec.loader
cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cli
spec.loader.exec_module(cli)
gate = cli.gate

SANDBOX = Path(tempfile.mkdtemp(prefix="gate-registry-isolation-"))
FIXTURE_CHECKOUT = Path(tempfile.mkdtemp(prefix="itd_gate_fixture_checkout-"))


def profile_value(checkout: Path) -> dict:
    """A valid v2 local-review row mirroring the incident registry state."""
    return {
        "version": 2,
        "repositories": [{
            "repository": "hihol-labs/idea-to-deploy",
            "checkout": str(checkout),
            "repositoryOwnerType": "organization",
            "deploymentProfile": "local-submission",
            "protectionProfile": "local-review",
            "localReviewReceiptFile": str(
                checkout / ".itd-memory" / "verification-loop" / "receipts"
                / "fixture" / "adjudication.json"),
            "localReviewUnitId": "GPG-004:local-review-commit",
            "localReviewRiskTier": "high",
            "localReviewProducerKeyringSha256": "a" * 64,
            "brokerUrl": None,
            "appId": None,
            "appOwner": None,
            "appOwnerType": None,
            "appVisibility": None,
            "rulesetScope": None,
            "rulesetId": None,
            "machineWorkflowRepositoryId": None,
            "machineWorkflowSha": None,
            "provenanceKeyId": None,
            "provenanceKeyFile": None,
            "enrollmentReceiptSha256": None,
        }],
    }


@contextlib.contextmanager
def sandbox_home(home: Path):
    with mock.patch("pathlib.Path.home", return_value=home):
        with mock.patch.dict("os.environ"):
            os.environ.pop("ITD_GATE_REGISTRY", None)
            yield


@contextlib.contextmanager
def fake_tempdir(value: Path):
    """Patch gettempdir wherever the writer guard may consult it."""
    targets = [mock.patch("tempfile.gettempdir", return_value=str(value))]
    for module in (cli, gate):
        if hasattr(module, "tempfile"):
            targets.append(mock.patch.object(
                module.tempfile, "gettempdir", return_value=str(value)))
    with contextlib.ExitStack() as stack:
        for target in targets:
            stack.enter_context(target)
        yield


# --- Scenario A: the incident write must refuse ----------------------------
# A fixture row (checkout under the system temp directory) written with no
# explicit path and no ITD_GATE_REGISTRY targets the un-overridden default
# registry. RED on pre-unit code: the write silently succeeds.
home_a = SANDBOX / "home-a"
home_a.mkdir()
default_a = home_a / ".config" / "itd" / "gates.json"
with sandbox_home(home_a):
    try:
        cli.save_registry(profile_value(FIXTURE_CHECKOUT))
        refused = ""
    except gate.GateError as exc:
        refused = f"{exc.status}: {exc.reason}"
check("fixture write into the un-overridden default registry refuses",
      bool(refused), "write succeeded silently")
check("refused fixture write leaves no default registry file",
      not default_a.exists(), str(default_a))

# --- Scenario B: explicit ITD_GATE_REGISTRY target keeps working -----------
home_b = SANDBOX / "home-b"
home_b.mkdir()
isolated_b = SANDBOX / "isolated-b" / "gates.json"
with sandbox_home(home_b):
    os.environ["ITD_GATE_REGISTRY"] = str(isolated_b)
    try:
        written_b = cli.save_registry(profile_value(FIXTURE_CHECKOUT))
        error_b = ""
    except gate.GateError as exc:
        written_b, error_b = None, f"{exc.status}: {exc.reason}"
check("fixture write through explicit ITD_GATE_REGISTRY succeeds",
      written_b == isolated_b.resolve() and isolated_b.is_file(), error_b)
if isolated_b.is_file():
    loaded = gate.load_registry(isolated_b)
    check("isolated registry loads and validates as v2",
          loaded.get("version") == 2
          and loaded["repositories"][0]["checkout"] == str(FIXTURE_CHECKOUT),
          json.dumps(loaded)[:200])
check("default registry stays absent next to the isolated write",
      not (home_b / ".config" / "itd" / "gates.json").exists(), "leak")

# --- Scenario C: explicit path argument keeps working ----------------------
explicit_c = SANDBOX / "explicit-c" / "gates.json"
home_c = SANDBOX / "home-c"
home_c.mkdir()
with sandbox_home(home_c):
    try:
        written_c = cli.save_registry(
            profile_value(FIXTURE_CHECKOUT), explicit_c)
        error_c = ""
    except gate.GateError as exc:
        written_c, error_c = None, f"{exc.status}: {exc.reason}"
check("fixture write to an explicit non-default path succeeds",
      written_c == explicit_c.resolve() and explicit_c.is_file(), error_c)
check("explicit-path write leaves the default registry absent",
      not (home_c / ".config" / "itd" / "gates.json").exists(), "leak")

# --- Scenario D: a non-fixture row may register into the default path ------
# Real registration (checkout outside the system temp directory) must keep
# working against the default registry; gettempdir is repointed so the
# sandbox checkout counts as a normal project path.
home_d = SANDBOX / "home-d"
home_d.mkdir()
real_checkout = SANDBOX / "projects" / "real-repo"
real_checkout.mkdir(parents=True)
with sandbox_home(home_d), fake_tempdir(SANDBOX / "faketmp"):
    try:
        written_d = cli.save_registry(profile_value(real_checkout))
        error_d = ""
    except gate.GateError as exc:
        written_d, error_d = None, f"{exc.status}: {exc.reason}"
default_d = home_d / ".config" / "itd" / "gates.json"
check("non-fixture registration into the default registry keeps working",
      written_d == default_d.resolve() and default_d.is_file(), error_d)

# --- The live registry never moved -----------------------------------------
live_after = live_registry_bytes()


def digest(value: bytes | None) -> str:
    return hashlib.sha256(value).hexdigest() if value is not None else "absent"


check("real live registry is byte-identical across the suite",
      LIVE_BEFORE == live_after,
      f"before={digest(LIVE_BEFORE)} after={digest(live_after)}")

print(json.dumps({
    "checks": checks, "failures": failures,
    "status": "PASSED" if not failures else "FAILED",
}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
