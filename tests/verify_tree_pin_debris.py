#!/usr/bin/env python3
"""The methodology tree pin digests the methodology, not harness debris.

A stray Git-ignored file under a tree root once entered the pin silently and
only surfaced later, in an isolated staged candidate, as three failing checks.
The pin now excludes exactly what Git ignores - and says so loudly when Git
cannot answer, rather than quietly widening back.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PROBE_IGNORED = ROOT / "skills" / "_shared" / ".claude" / "traces" / "tree-pin-probe.json"
PROBE_TRACKED_SHAPE = ROOT / "skills" / "_shared" / "tree-pin-probe.tmp"
CHECKS = 0


def check(condition: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(label)


def load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plant(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def unplant(path: Path) -> None:
    path.unlink(missing_ok=True)
    for parent in path.parents:
        if parent == ROOT:
            break
        try:
            parent.rmdir()
        except OSError:
            break


def main() -> int:
    verifier = load("tests/verify_live_model_benchmark.py", "itd_tree_pin_verifier")
    producer = load("tests/run-live-model-benchmark.py", "itd_tree_pin_producer")

    baseline = verifier.methodology_tree_sha256()
    check(baseline.startswith("sha256:"), "tree pin is a sha256 digest")
    check(
        baseline == producer.methodology_tree_sha256(),
        "producer and verifier compute the same tree pin",
    )

    # Ignored debris must not move the pin. This is the H4 reproduction: the
    # incident file lived under skills/_shared/.claude/traces/.
    try:
        plant(PROBE_IGNORED, b'{"trace": "harness debris, not methodology"}\n')
        check(
            verifier.methodology_tree_sha256() == baseline,
            "git-ignored debris does not enter the verifier tree pin",
        )
        check(
            producer.methodology_tree_sha256() == baseline,
            "git-ignored debris does not enter the producer tree pin",
        )
    finally:
        unplant(PROBE_IGNORED)
    check(
        verifier.methodology_tree_sha256() == baseline,
        "removing the debris restores the baseline pin",
    )

    # Non-vacuity: a file Git does NOT ignore must still move the pin, or the
    # filter above would be indistinguishable from pinning nothing at all.
    try:
        plant(PROBE_TRACKED_SHAPE, b"probe\n")
        check(
            verifier.methodology_tree_sha256() != baseline,
            "a non-ignored file still moves the verifier tree pin",
        )
        check(
            producer.methodology_tree_sha256() != baseline,
            "a non-ignored file still moves the producer tree pin",
        )
    finally:
        unplant(PROBE_TRACKED_SHAPE)
    check(
        verifier.methodology_tree_sha256() == baseline,
        "removing the probe restores the baseline pin",
    )

    # An unanswerable Git is a loud failure, never a silently wider pin.
    for module, label in ((verifier, "verifier"), (producer, "producer")):
        original = module.subprocess.run

        def unavailable(*args, **kwargs):
            raise FileNotFoundError("git")

        module.subprocess.run = unavailable
        try:
            try:
                module.methodology_tree_sha256()
            except Exception:
                raised = True
            else:
                raised = False
        finally:
            module.subprocess.run = original
        check(raised, f"{label} tree pin fails loudly when git is unavailable")

    # ... and the two other ways Git can fail to answer: a fatal exit code and
    # a timeout. Both must raise for the same reason as a missing executable -
    # a pin that widens whenever Git stumbles is the defect being removed.
    fatal = subprocess.CompletedProcess(["git"], 128, stdout=b"", stderr=b"fatal: not a git repository")
    for module, label in ((verifier, "verifier"), (producer, "producer")):
        original = module.subprocess.run
        for behaviour, case in (
            (lambda *a, **k: fatal, "a fatal git exit code"),
            (lambda *a, **k: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(["git"], 60)), "a git timeout"),
        ):
            module.subprocess.run = behaviour
            try:
                try:
                    module.methodology_tree_sha256()
                except Exception:
                    raised = True
                else:
                    raised = False
            finally:
                module.subprocess.run = original
            check(raised, f"{label} tree pin fails loudly on {case}")

    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
