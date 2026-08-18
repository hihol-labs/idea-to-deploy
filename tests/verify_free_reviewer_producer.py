#!/usr/bin/env python3
"""Behavioral oracle for the free isolated two-phase reviewer producer."""
from __future__ import annotations

import base64
import contextlib
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "skills/_shared/itd_free_reviewer_producer.py"

# The governing review total must be read as an exact delimited number, never as
# a substring: an emitted 1411470 embeds the expected 141147 and would otherwise
# satisfy the regression while violating the contract.
GOVERNING_TOTAL_RE = re.compile(
    r"(?:exact total is|representation total of) (\d+) bytes(?![\d])"
)


def governing_totals(prompt_text: str) -> set[int]:
    """Every governing total the prompt states, parsed exactly."""
    return {int(match) for match in GOVERNING_TOTAL_RE.findall(prompt_text)}


def shell(argv: list[str], cwd: Path) -> str:
    result = subprocess.run(
        argv, cwd=cwd, text=True, capture_output=True, timeout=30
    )
    if result.returncode:
        raise AssertionError(
            f"{argv} rc={result.returncode}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def load_module():
    if not PRODUCER.is_file():
        raise AssertionError(
            "RED: free isolated reviewer producer is not implemented"
        )
    spec = importlib.util.spec_from_file_location("itd_free_reviewer", PRODUCER)
    if spec is None or spec.loader is None:
        raise AssertionError("free reviewer producer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_fixture(root: Path) -> tuple[str, str, str]:
    shell(["git", "init", "-q"], root)
    shell(["git", "config", "user.name", "ITD Review Test"], root)
    shell(["git", "config", "user.email", "review@invalid"], root)
    (root / "service.py").write_text(
        "def decision():\n    return 'old'\n", encoding="utf-8"
    )
    shell(["git", "add", "service.py"], root)
    shell(["git", "commit", "-qm", "base"], root)
    base = shell(["git", "rev-parse", "HEAD"], root)
    (root / "branch.py").write_text("BRANCH = True\n", encoding="utf-8")
    shell(["git", "add", "branch.py"], root)
    shell(["git", "commit", "-qm", "branch parent"], root)
    parent = shell(["git", "rev-parse", "HEAD"], root)
    (root / "service.py").write_text(
        "def decision():\n"
        "    marker = 'GIT binary patch / Binary files x differ'\n"
        "    return 'reviewed'\n",
        encoding="utf-8",
    )
    shell(["git", "add", "service.py"], root)
    tree = shell(["git", "write-tree"], root)
    return base, parent, tree


def write_inputs(
    root: Path, repo: Path, parent: str, tree: str
) -> tuple[Path, Path, Path]:
    scope = root / "scope.md"
    scope.write_text("# Frozen scope\nOnly service.py.\n", encoding="utf-8")
    acceptance = root / "acceptance.json"
    acceptance.write_text(
        json.dumps({"version": 1, "criteria": ["review exact candidate"]}),
        encoding="utf-8",
    )
    machine = root / "machine.json"
    diff = subprocess.run(
        ["git", "diff", "--cached", "--binary", "--full-index",
         "--no-ext-diff", parent, "--"], cwd=repo, capture_output=True,
        timeout=30, check=True,
    ).stdout
    machine.write_text(
        json.dumps({
            "version": 1,
            "kind": "machine-verification",
            "candidate": {
                "baseCommit": parent,
                "reviewedTree": tree,
                "diffHash": __import__("hashlib").sha256(diff).hexdigest(),
                "scopeContractHash": __import__("hashlib").sha256(
                    scope.read_bytes()
                ).hexdigest(),
                "acceptanceContractHash": __import__("hashlib").sha256(
                    acceptance.read_bytes()
                ).hexdigest(),
            },
            "verdict": "PASSED",
        }),
        encoding="utf-8",
    )
    return scope, acceptance, machine


def raw_private_key() -> bytes:
    return Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )


def public_key(private: bytes) -> str:
    raw = Ed25519PrivateKey.from_private_bytes(private).public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def clean_verdict() -> dict:
    return {"verdict": "PASSED", "findings": [], "unverified": []}


def main() -> int:
    producer = load_module()
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(message)

    # S7-U1: non-finite timeouts must be rejected before deadline arithmetic —
    # NaN slips through a `timeout <= 0` guard (both comparisons are False) and
    # +inf never expires, so either would silently disarm the process bound.
    for bad_timeout in (float("nan"), float("inf"), float("-inf")):
        try:
            producer.run_bounded_process(
                [sys.executable, "-c", "pass"], timeout=bad_timeout
            )
        except ValueError:
            checks += 1
        else:
            raise AssertionError(
                f"non-finite timeout {bad_timeout!r} was accepted"
            )
    completed = producer.run_bounded_process(
        [sys.executable, "-c", "print('ok')"], timeout=30.0
    )
    check(completed.returncode == 0 and b"ok" in completed.stdout,
          "finite float timeout no longer runs the bounded process")

    # S7-U2: the Windows wrapper starts from its own temp directory, so a
    # relative cwd in the plan would resolve against the wrong base. The plan
    # must anchor it at the caller's directory before handoff — without
    # collapsing symlinks (abspath semantics, not resolve).
    check(producer.wrapper_plan_cwd(None) == os.getcwd(),
          "plan cwd default is not the caller's directory")
    check(producer.wrapper_plan_cwd("sub/dir")
          == os.path.join(os.getcwd(), "sub", "dir"),
          "relative plan cwd is not anchored at the caller")
    absolute_probe = os.path.join(os.getcwd(), "already-absolute")
    check(producer.wrapper_plan_cwd(Path(absolute_probe)) == absolute_probe,
          "absolute plan cwd must pass through unchanged")

    # S7-U3: a descendant that re-calls setsid() leaves the process group, so
    # killpg alone never reaps it. The cleanup must snapshot descendants via a
    # PPID walk BEFORE the kill and finish off group escapees. This test
    # actually daemonizes: the grandchild detaches into its own session and
    # outlives the parent's timeout unless reaped. (Accepted residual: a
    # double-fork orphan reparented to init before cleanup stays invisible to
    # a PPID walk — BACKLOG containment item.)
    if os.name != "nt" and Path("/proc").is_dir():
        with tempfile.TemporaryDirectory(prefix="itd-reap-") as reap_raw:
            escapee_pid_path = Path(reap_raw) / "escapee.pid"
            daemonizing_child = (
                "import os, sys, time\n"
                "pid = os.fork()\n"
                "if pid == 0:\n"
                "    os.setsid()\n"
                f"    open({str(escapee_pid_path)!r}, 'w')"
                ".write(str(os.getpid()))\n"
                "    time.sleep(120)\n"
                "    raise SystemExit(0)\n"
                "time.sleep(120)\n"
            )
            try:
                producer.run_bounded_process(
                    [sys.executable, "-c", daemonizing_child], timeout=3.0
                )
            except subprocess.TimeoutExpired:
                pass
            else:
                raise AssertionError("daemonizing fixture did not time out")
            check(escapee_pid_path.is_file(),
                  "daemonized escapee never announced its pid")
            escapee_pid = int(escapee_pid_path.read_text())
            for _ in range(50):
                try:
                    os.kill(escapee_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                os.kill(escapee_pid, signal.SIGKILL)
                raise AssertionError(
                    "setsid escapee survived cleanup: killpg cannot reach "
                    "another session and no reap followed"
                )
            checks += 1

    with tempfile.TemporaryDirectory(prefix="itd-free-review-") as raw:
        fixture = Path(raw)
        repo = fixture / "repo"
        repo.mkdir()
        base, parent, tree = git_fixture(repo)
        scope, acceptance, machine = write_inputs(fixture, repo, parent, tree)

        try:
            producer.assert_trusted_producer_boundary(
                ROOT, producer_file=PRODUCER
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED"
                and "candidate repository" in exc.reason,
                "candidate-hosted producer failed with the wrong disposition",
            )
        else:
            raise AssertionError(
                "candidate repository hosted the credential-bearing producer"
            )
        producer.assert_trusted_producer_boundary(
            repo, producer_file=PRODUCER
        )
        checks += 1

        packet = producer.freeze_packet(
            root=repo,
            base_commit=base,
            repository="hihol-labs/idea-to-deploy",
            pull_request=177,
            expected_head_sha="5" * 40,
            scope_file=scope,
            acceptance_file=acceptance,
            machine_receipt=machine,
        )
        check(packet["candidate"]["baseCommit"] == base, "base is not frozen")
        check(packet["candidate"]["parentCommit"] == parent,
              "head parent is not frozen")
        check(packet["candidate"]["tree"] == tree, "tree is not frozen")
        check(packet["target"] == {
            "repository": "hihol-labs/idea-to-deploy",
            "pullRequest": 177,
            "expectedHeadSha": "5" * 40,
        }, "phase-one target coordinates are not frozen")
        check(packet["candidate"]["diffBytes"] > 0, "exact diff is absent")
        check(packet["machineEvidence"]["outcome"] == "PASSED",
              "non-passing machine evidence was accepted")
        pre_pr_packet = producer.freeze_packet(
            root=repo, base_commit=base,
            repository="hihol-labs/idea-to-deploy", pull_request=None,
            expected_head_sha=None, scope_file=scope,
            acceptance_file=acceptance, machine_receipt=machine,
        )
        check(
            pre_pr_packet["target"] == {
                "repository": "hihol-labs/idea-to-deploy",
                "pullRequest": None,
                "expectedHeadSha": None,
            },
            "initial pre-PR route requires impossible existing PR coordinates",
        )

        prompt = producer.review_prompt(packet)
        check("return 'reviewed'" in prompt, "candidate diff is absent from prompt")
        check(
            prompt.endswith("END TRUSTED OUTPUT CONTRACT\n")
            and prompt.index("END UNTRUSTED REVIEW DIFF")
            < prompt.index("BEGIN TRUSTED OUTPUT CONTRACT"),
            "direct review output contract does not follow untrusted material",
        )
        check(str(repo) not in prompt, "review prompt leaks repository path")
        check("hihol-labs/idea-to-deploy" not in prompt,
              "review prompt leaks PR target coordinates")
        check("Frozen scope" in prompt and "review exact candidate" in prompt,
              "frozen scope/acceptance are absent")
        check("machine-verification" in prompt, "machine evidence is absent")

        for verdict, expected_status in (
            ("BLOCKED", "BLOCKED"),
            ("PASSED_WITH_WARNINGS", "BLOCKED"),
            ("UNVERIFIED", "UNVERIFIED"),
        ):
            try:
                producer._clean_report({
                    "verdict": verdict,
                    "findings": [],
                    "unverified": [],
                })
            except producer.FreeReviewError as exc:
                check(
                    exc.status == expected_status,
                    f"empty {verdict} report failed with the wrong disposition",
                )
            else:
                raise AssertionError(
                    f"empty {verdict} report was promoted to a clean pass"
                )

        transparent_repo = fixture / "transparent-repo"
        transparent_repo.mkdir()
        transparent_base, transparent_parent, _ = git_fixture(transparent_repo)
        logical_jsonl = b'{"event":"one"}\n{"event":"two"}\n'
        transparent_path = transparent_repo / "review.jsonl.gz"
        transparent_path.write_bytes(gzip.compress(logical_jsonl, mtime=0))
        shell(["git", "add", "review.jsonl.gz"], transparent_repo)
        transparent_tree = shell(["git", "write-tree"], transparent_repo)
        transparent_inputs = fixture / "transparent-inputs"
        transparent_inputs.mkdir()
        transparent_scope, transparent_acceptance, transparent_machine = write_inputs(
            transparent_inputs, transparent_repo,
            transparent_parent, transparent_tree,
        )
        transparent_packet = producer.freeze_packet(
            root=transparent_repo, base_commit=transparent_base,
            repository="hihol-labs/idea-to-deploy", pull_request=None,
            expected_head_sha=None, scope_file=transparent_scope,
            acceptance_file=transparent_acceptance,
            machine_receipt=transparent_machine,
        )
        representation = transparent_packet["reviewRepresentation"]
        transparent_record = representation["files"]["review.jsonl.gz"]
        check(
            representation["algorithm"]
            == "itd-canonical-transparent-diff-v1"
            and representation["transparentFileCount"] == 1,
            "supported transparent binary did not select the logical review route",
        )
        check(
            transparent_record["headReview"] == {
                "encoding": "gzip-jsonl-utf8-v1",
                "sha256": hashlib.sha256(logical_jsonl).hexdigest(),
                "bytes": len(logical_jsonl),
            }
            and transparent_record["baseReview"] is None
            and transparent_record["newMode"] == "100644",
            "transparent logical bytes are not raw-blob/mode bound",
        )
        transparent_raw_diff = subprocess.run(
            ["git", "diff", "--cached", "--binary", "--full-index",
             "--no-ext-diff", transparent_base, "--"],
            cwd=transparent_repo, capture_output=True, check=True, timeout=30,
        ).stdout
        check(
            transparent_packet["candidate"]["diffSha256"]
            == hashlib.sha256(transparent_raw_diff).hexdigest()
            and transparent_packet["candidate"]["diffBytes"]
            == len(transparent_raw_diff),
            "logical review replaced the exact raw candidate binding",
        )
        check(
            '{"event":"one"}' in transparent_packet["diff"]
            and "\nGIT binary patch\n" not in transparent_packet["diff"]
            and representation["reviewDiffSha256"]
            == hashlib.sha256(
                transparent_packet["diff"].encode("utf-8")
            ).hexdigest(),
            "reviewer did not receive the exact hash-bound logical JSONL diff",
        )

        large_root = fixture / "large-transparent"
        large_repo = large_root / "repo"
        large_repo.mkdir(parents=True)
        large_base, large_parent, _ = git_fixture(large_repo)
        large_jsonl = b"".join(
            json.dumps({"event": index, "payload": "x" * 24}, separators=(",", ":"))
            .encode("utf-8") + b"\n"
            for index in range(5000)
        )
        (large_repo / "review.jsonl.gz").write_bytes(
            gzip.compress(large_jsonl, mtime=0)
        )
        shell(["git", "add", "review.jsonl.gz"], large_repo)
        large_tree = shell(["git", "write-tree"], large_repo)
        large_inputs = large_root / "inputs"
        large_inputs.mkdir()
        large_scope, large_acceptance, large_machine = write_inputs(
            large_inputs, large_repo, large_parent, large_tree,
        )
        large_packet = producer.freeze_packet(
            root=large_repo, base_commit=large_base,
            repository="hihol-labs/idea-to-deploy", pull_request=None,
            expected_head_sha=None, scope_file=large_scope,
            acceptance_file=large_acceptance, machine_receipt=large_machine,
        )
        large_representation = large_packet["reviewRepresentation"]
        plan = large_representation["reviewPlan"]
        check(
            large_representation["reviewMode"] == "hierarchical"
            and plan["mode"] == "hierarchical"
            and 1 < plan["unitCount"] <= 16,
            "oversized keyless packet did not select the bounded review plan",
        )
        observed_prompts = []

        def fake_packet_runner(prompt_text, report_schema, report_parser):
            observed_prompts.append(prompt_text)
            if report_schema == producer.UNIT_VERDICT_SCHEMA:
                report = {
                    "verdict": "PASSED",
                    "findings": [],
                    "unverified": [],
                    "summary": "Unit behavior and cross-unit interfaces are consistent.",
                }
            else:
                report = clean_verdict()
            return (
                report_parser(report),
                f"fresh-unit-{len(observed_prompts)}",
                "subscription-model",
            )

        final_report, aggregate_session, observed_model, prompt_artifact = (
            producer.run_packet_review(large_packet, fake_packet_runner)
        )
        check(
            final_report == clean_verdict()
            and observed_model == "subscription-model"
            and len(aggregate_session) == 64
            and len(observed_prompts) == plan["unitCount"] + 1,
            "hierarchical keyless review did not run every unit plus integration",
        )
        check(
            all(
                len(value.encode("utf-8")) < producer.MAX_INPUT_BYTES
                and large_packet["diff"] not in value
                for value in observed_prompts
            ),
            "hierarchical keyless review sent the full oversized packet to a model",
        )
        check(
            all(value.endswith("END TRUSTED OUTPUT CONTRACT\n")
                for value in observed_prompts)
            and all(
                value.index("END UNTRUSTED DIFF UNIT")
                < value.index("BEGIN TRUSTED OUTPUT CONTRACT")
                for value in observed_prompts[:-1]
            ),
            "hierarchical output contract is not the final trusted instruction",
        )
        unit_prompts = observed_prompts[:-1]
        serialized_representation = json.dumps(
            large_packet["reviewRepresentation"],
            ensure_ascii=False,
            sort_keys=True,
        )
        check(
            all(
                len(value.encode("utf-8"))
                <= producer.MAX_UNIT_PROMPT_BYTES
                for value in unit_prompts
            )
            and len(observed_prompts[-1].encode("utf-8"))
            <= producer.MAX_INTEGRATION_PROMPT_BYTES,
            "hierarchical reviewer prompts exceed their transport bounds",
        )
        check(
            all(serialized_representation not in value for value in unit_prompts)
            and all(
                '"reviewRepresentationSha256"' in value
                and "FROZEN_ACTIVE_ACCEPTANCE=" in value
                and "MACHINE_EVIDENCE_SUMMARY=" in value
                for value in unit_prompts
            ),
            "unit prompts repeat the full plan instead of its exact hash binding",
        )
        representation_total = plan["fullDiffBytes"]
        check(
            large_packet["candidate"]["diffBytes"] != representation_total
            and all(
                "never against candidate.diffBytes" in value
                and str(representation_total) in value
                for value in observed_prompts
            )
            and "never against candidate.diffBytes"
            in producer.review_prompt(large_packet),
            "reviewer prompts leave the candidate and review byte totals ambiguous",
        )
        check(
            transparent_packet["candidate"]["diffBytes"]
            != representation["reviewDiffBytes"]
            and str(representation["reviewDiffBytes"])
            in producer.review_prompt(transparent_packet)
            and "never against candidate.diffBytes"
            in producer.review_prompt(transparent_packet),
            "direct transparent prompt omits its exact review representation total",
        )
        check(
            all(
                governing_totals(value) == {representation_total}
                for value in observed_prompts
            )
            and governing_totals(producer.review_prompt(large_packet))
            == {representation_total}
            and governing_totals(producer.review_prompt(transparent_packet))
            == {representation["reviewDiffBytes"]}
            and not governing_totals(
                producer.review_prompt(large_packet).replace(
                    f"{representation_total} bytes",
                    f"{representation_total}0 bytes",
                )
            )
            == {representation_total},
            "governing review total is accepted as a substring instead of an "
            "exact delimited number",
        )
        producer.validate_review_prompt_artifact(
            large_packet, prompt_artifact, final_report,
        )

        # A bound unit is cut by a byte budget at line boundaries alone, so the
        # paired records of one JSONL entry land in adjacent units.  The unit
        # checker then truthfully reports its own slice as ending mid-record;
        # without a machine-derived boundary fact the integration stage cannot
        # tell that observation apart from a genuinely truncated artifact and
        # promotes it into the candidate verdict.
        split_root = fixture / "split-transcript"
        split_repo = split_root / "repo"
        split_repo.mkdir(parents=True)
        split_base, split_parent, _ = git_fixture(split_repo)
        (split_repo / "review.jsonl.gz").write_bytes(gzip.compress(
            b"".join(
                json.dumps({
                    "type": phase,
                    "item": {
                        "id": f"item_{index}",
                        "status": status,
                        "payload": "x" * 96,
                    },
                }, separators=(",", ":")).encode("utf-8") + b"\n"
                for index in range(1400)
                for phase, status in (
                    ("item.started", "in_progress"),
                    ("item.completed", "completed"),
                )
            ),
            mtime=0,
        ))
        shell(["git", "add", "review.jsonl.gz"], split_repo)
        split_tree = shell(["git", "write-tree"], split_repo)
        split_inputs = split_root / "inputs"
        split_inputs.mkdir()
        split_scope, split_acceptance, split_machine = write_inputs(
            split_inputs, split_repo, split_parent, split_tree,
        )
        split_packet = producer.freeze_packet(
            root=split_repo, base_commit=split_base,
            repository="hihol-labs/idea-to-deploy", pull_request=None,
            expected_head_sha=None, scope_file=split_scope,
            acceptance_file=split_acceptance, machine_receipt=split_machine,
        )
        split_plan = split_packet["reviewRepresentation"]["reviewPlan"]
        split_diff = split_packet["diff"].encode("utf-8")
        split_units = split_plan["units"]
        started_re = re.compile(
            r'"type":"item\.started","item":\{"id":"(item_\d+)"'
        )
        completed_re = re.compile(
            r'"type":"item\.completed","item":\{"id":"(item_\d+)"'
        )
        unit_texts = [
            split_diff[
                unit["reviewDiffStartByte"]:unit["reviewDiffEndByteExclusive"]
            ].decode("utf-8")
            for unit in split_units
        ]
        orphaned = [
            sorted(set(started_re.findall(text)) - set(completed_re.findall(text)))
            for text in unit_texts
        ]
        split_index = next(
            (index for index, ids in enumerate(orphaned) if ids), -1
        )
        check(
            split_plan["mode"] == "hierarchical"
            and split_plan["unitCount"] > 1
            and 0 <= split_index < len(unit_texts) - 1
            and any(
                item_id in completed_re.findall(unit_texts[split_index + 1])
                for item_id in orphaned[split_index]
            ),
            "transcript fixture does not split a paired record across units",
        )

        def bound_range_truth(plan_value, unit):
            segments = unit["pathSegments"]
            return {
                "unitIndex": unit["index"],
                "unitCount": plan_value["unitCount"],
                "reviewDiffStartByte": unit["reviewDiffStartByte"],
                "reviewDiffEndByteExclusive":
                    unit["reviewDiffEndByteExclusive"],
                "fullDiffBytes": plan_value["fullDiffBytes"],
                "continuesPreviousUnit": unit["reviewDiffStartByte"] > 0,
                "continuedByNextUnit":
                    unit["reviewDiffEndByteExclusive"]
                    < plan_value["fullDiffBytes"],
                "pathsContinuedFromPreviousUnit": sorted(
                    path for path, segment in segments.items()
                    if segment["index"] > 1
                ),
                "pathsContinuedInNextUnit": sorted(
                    path for path, segment in segments.items()
                    if segment["index"] < segment["count"]
                ),
            }

        def tagged_json(prompt_text, marker):
            start = prompt_text.find(marker)
            if start < 0:
                return None
            start += len(marker)
            end = prompt_text.find("\n", start)
            try:
                return json.loads(prompt_text[start:end])
            except json.JSONDecodeError:
                return None

        split_prompts = []

        def split_runner(prompt_text, report_schema, report_parser):
            split_prompts.append(prompt_text)
            if report_schema == producer.UNIT_VERDICT_SCHEMA:
                report = {
                    "verdict": "PASSED",
                    "findings": [],
                    "unverified": [],
                    "summary": "Bound range reviewed; no cross-unit risk.",
                }
            else:
                report = clean_verdict()
            return (
                report_parser(report),
                f"fresh-split-{len(split_prompts)}",
                "subscription-model",
            )

        producer.run_packet_review(split_packet, split_runner)
        split_unit_prompts = split_prompts[:-1]
        split_integration_prompt = split_prompts[-1]
        check(
            len(split_unit_prompts) == split_plan["unitCount"]
            and [
                tagged_json(value, "BOUND_RANGE_FACTS=")
                for value in split_unit_prompts
            ] == [
                bound_range_truth(split_plan, unit) for unit in split_units
            ],
            "unit prompts omit the exact machine-derived bound-range facts",
        )
        check(
            all(
                producer.BOUND_RANGE_DISCLAIMER in value
                for value in split_prompts
            )
            and all(
                term in producer.BOUND_RANGE_DISCLAIMER
                for term in ("bound range", "truncated", "incomplete",
                             "not a defect of the candidate")
            ),
            "reviewer prompts permit a candidate verdict about completeness "
            "drawn from an intentionally cut bound range",
        )
        integration_evidence = tagged_json(
            split_integration_prompt, "HIERARCHICAL_REVIEW_EVIDENCE="
        )
        check(
            isinstance(integration_evidence, dict)
            and integration_evidence.get("unitBoundaries")
            == [bound_range_truth(split_plan, unit) for unit in split_units],
            "the integration stage cannot resolve a boundary observation "
            "against the adjacent bound units",
        )

        boundary_unit = split_units[split_index]
        boundary_text = unit_texts[split_index]
        earlier_line = boundary_text[boundary_text.rindex(
            "\n", 0, len(boundary_text) - 1
        ) + 1:]
        later_line = unit_texts[split_index + 1].split("\n", 1)[0] + "\n"
        shifted_earlier = copy.deepcopy(boundary_unit)
        shifted_earlier["reviewDiffEndByteExclusive"] -= len(
            earlier_line.encode("utf-8")
        )
        shifted_later = copy.deepcopy(boundary_unit)
        shifted_later["reviewDiffEndByteExclusive"] += len(
            later_line.encode("utf-8")
        )
        whole_path = copy.deepcopy(boundary_unit)
        whole_path["reviewDiffStartByte"] = 0
        whole_path["reviewDiffEndByteExclusive"] = split_plan["fullDiffBytes"]
        whole_path["pathSegments"] = {
            path: {"index": 1, "count": 1}
            for path in whole_path["pathSegments"]
        }
        check(
            all(
                tagged_json(
                    producer._unit_review_prompt(
                        split_packet, split_plan, mutated, boundary_text,
                    ),
                    "BOUND_RANGE_FACTS=",
                ) == bound_range_truth(split_plan, mutated)
                for mutated in (shifted_earlier, shifted_later, whole_path)
            ),
            "bound-range facts do not follow the exact unit boundary",
        )

        # --- S11: model-visible means logged ---------------------------------
        # (c) A bound unit sees a byte range, never the candidate's file list.
        # A reviewer that misses a file in its own slice must be told, from the
        # frozen plan itself, that the file exists and which units carry it.
        def inventory_truth(plan_value, unit):
            carriers: dict = {}
            for row in plan_value["units"]:
                for path in row["paths"]:
                    carriers.setdefault(path, []).append(row["index"])
            segments = unit["pathSegments"]
            complete, partial, other = [], {}, {}
            for path in [*carriers, *[p for p in segments if p not in carriers]]:
                indices = carriers.get(path, [])
                segment = segments.get(path)
                if segment is None:
                    other[path] = indices
                elif segment["count"] == 1:
                    complete.append(path)
                else:
                    partial[path] = {
                        "segmentIndex": segment["index"],
                        "segmentCount": segment["count"],
                        "otherUnits": [
                            index for index in indices if index != unit["index"]
                        ],
                    }
            return {
                "candidateFileCount": len(carriers),
                "unitIndex": unit["index"],
                "unitCount": plan_value["unitCount"],
                "completeInThisUnit": complete,
                "partialInThisUnit": partial,
                "inOtherUnits": other,
            }

        split_inventories = [
            tagged_json(value, "FILE_INVENTORY=") for value in split_unit_prompts
        ]
        check(
            split_inventories
            == [inventory_truth(split_plan, unit) for unit in split_units],
            "unit prompts omit the plan-derived candidate file inventory",
        )
        service_units = [
            unit["index"] for unit in split_units
            if "service.py" in unit["paths"]
        ]
        transcript_units = [
            unit["index"] for unit in split_units
            if "review.jsonl.gz" in unit["paths"]
        ]
        candidate_paths = {
            path for unit in split_units for path in unit["paths"]
        }
        check(
            len(service_units) == 1
            and len(transcript_units) > 1
            and candidate_paths >= {"branch.py", "review.jsonl.gz", "service.py"}
            and all(
                isinstance(inventory, dict)
                and inventory["candidateFileCount"] == len(candidate_paths)
                and (
                    "service.py" in inventory["completeInThisUnit"]
                    if unit["index"] in service_units
                    else inventory["inOtherUnits"].get("service.py")
                    == service_units
                )
                and (
                    inventory["partialInThisUnit"].get("review.jsonl.gz")
                    == {
                        "segmentIndex": unit["pathSegments"]["review.jsonl.gz"]["index"],
                        "segmentCount": len(transcript_units),
                        "otherUnits": [
                            index for index in transcript_units
                            if index != unit["index"]
                        ],
                    }
                    if unit["index"] in transcript_units
                    else inventory["inOtherUnits"].get("review.jsonl.gz")
                    == transcript_units
                )
                for inventory, unit in zip(split_inventories, split_units)
            ),
            "a unit is not told which candidate files lie whole, split, or in "
            "other units",
        )
        check(
            all(
                producer.FILE_INVENTORY_DISCLAIMER in value
                for value in split_prompts
            )
            and all(
                term in producer.FILE_INVENTORY_DISCLAIMER
                for term in ("never infer", "absent", "named units")
            ),
            "reviewer prompts permit inferring a file's absence from one bound "
            "range",
        )
        check(
            isinstance(integration_evidence, dict)
            and integration_evidence.get("fileInventory") == {
                "candidateFileCount": len(candidate_paths),
                "files": {
                    path: [
                        unit["index"] for unit in split_units
                        if path in unit["paths"]
                    ]
                    for path in candidate_paths
                },
            }
            and integration_evidence["fileInventory"]["files"]["review.jsonl.gz"]
            == transcript_units
            and integration_evidence["fileInventory"]["files"]["service.py"]
            == service_units,
            "the integration stage lacks the candidate file inventory",
        )
        # The inventory is only as honest as the plan's path claims, so the
        # plan is checked against the diff headers inside the exact byte
        # ranges before any prompt is built.
        lying_owner = copy.deepcopy(split_packet)
        lying_units = lying_owner["reviewRepresentation"]["reviewPlan"]["units"]
        owner = next(u for u in lying_units if "service.py" in u["paths"])
        foreign = next(u for u in lying_units if "service.py" not in u["paths"])
        owner["paths"].remove("service.py")
        del owner["pathSegments"]["service.py"]
        foreign["paths"].append("service.py")
        foreign["pathSegments"]["service.py"] = {"index": 1, "count": 1}
        lying_whole = copy.deepcopy(split_packet)
        for row in lying_whole["reviewRepresentation"]["reviewPlan"]["units"]:
            if "review.jsonl.gz" in row["pathSegments"]:
                row["pathSegments"]["review.jsonl.gz"] = {"index": 1, "count": 1}
        for label, lying in (("owner", lying_owner), ("whole", lying_whole)):
            try:
                producer.run_packet_review(lying, split_runner)
            except producer.FreeReviewError as exc:
                check(
                    exc.status == "UNVERIFIED" and "diff headers" in exc.reason,
                    f"a plan lying about file ownership ({label}) failed for "
                    "the wrong reason",
                )
            else:
                raise AssertionError(
                    f"a plan lying about file ownership ({label}) was accepted"
                )

        # (a) Every prompt handed to a transport is appended to a byte ledger
        # BEFORE the send, with its own sha256, and (b) the ledger verifies
        # against the signed receipt as a pure function of the two files.
        ledger_path = fixture / "split-transcript" / "prompt.ledger.jsonl"
        ledger = producer.PromptLedger(ledger_path)
        ledger_prompts = []
        ledger_seen_before_send = []

        def ledger_runner(prompt_text, report_schema, report_parser):
            ledger_prompts.append(prompt_text)
            lines = ledger_path.read_bytes().split(b"\n")
            last = json.loads(lines[-2]) if len(lines) > 1 else {}
            ledger_seen_before_send.append(
                last.get("sha256")
                == hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
                and last.get("prompt") == prompt_text
            )
            return split_runner(prompt_text, report_schema, report_parser)

        ledger_report, _ledger_session, _ledger_model, ledger_bundle = (
            producer.run_packet_review(
                split_packet, ledger_runner, prompt_ledger=ledger,
            )
        )
        check(
            len(ledger_seen_before_send) == split_plan["unitCount"] + 1
            and all(ledger_seen_before_send),
            "a prompt reached the transport before its ledger entry was written",
        )
        ledger_rows = [
            json.loads(line)
            for line in ledger_path.read_bytes().decode("utf-8").split("\n")[:-1]
        ]
        check(
            [(row["kind"], row["unitIndex"]) for row in ledger_rows]
            == [("unit", index) for index in range(1, split_plan["unitCount"] + 1)]
            + [("integration", None)]
            and [row["prompt"] for row in ledger_rows] == ledger_prompts
            and all(
                row["sha256"]
                == hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest()
                and row["promptBytes"] == len(row["prompt"].encode("utf-8"))
                for row in ledger_rows
            ),
            "the prompt ledger does not recover every sent prompt byte-exactly",
        )
        ledger_binding = ledger.binding()
        ledger_bundle_value = json.loads(ledger_bundle)
        check(
            ledger_binding["sha256"]
            == hashlib.sha256(ledger_path.read_bytes()).hexdigest()
            and [entry["sha256"] for entry in ledger_binding["entries"]]
            == [
                hashlib.sha256(call["prompt"].encode("utf-8")).hexdigest()
                for call in ledger_bundle_value["unitCalls"]
            ] + [
                hashlib.sha256(
                    ledger_bundle_value["integrationPrompt"].encode("utf-8")
                ).hexdigest()
            ],
            "the ledger binding does not name every unit and integration "
            "prompt hash",
        )
        ledger_private = raw_private_key()
        ledger_keys = {"free-reviewer-2026-08": public_key(ledger_private)}
        ledger_maker = {"provider": "openai-codex", "model": "gpt-5.6-sol",
                        "session": "maker-session-ledger"}
        ledger_reviewer = {
            "provider": "openai-subscription", "model": "gpt-5.6-terra",
            "session": "fresh-thread-ledger",
            "transportExecutableSha256": "5" * 64,
        }
        ledger_attempts = [{"provider": "openai-subscription", "status": "PASSED"}]

        def mint(prompt_value, packet_value, binding):
            return producer.phase_one_receipt(
                packet=packet_value, prompt=prompt_value, report=clean_verdict(),
                maker=ledger_maker, reviewer=ledger_reviewer,
                attempts=ledger_attempts,
                isolation=producer.required_isolation(),
                key_id="free-reviewer-2026-08", private_key=ledger_private,
                issued_at="2026-08-18T09:00:00Z", prompt_ledger=binding,
            )

        ledger_receipt = mint(ledger_bundle, split_packet, ledger_binding)
        verified_ledger_receipt = producer.verify_phase_one(
            ledger_receipt, ledger_keys
        )
        check(
            verified_ledger_receipt["promptLedger"] == ledger_binding
            and producer.verify_prompt_ledger(
                ledger_path.read_bytes(), ledger_receipt
            )["status"] == "VERIFIED",
            "a signed receipt does not bind the prompt ledger it was minted with",
        )

        def ledger_why(ledger_bytes, receipt_value):
            try:
                producer.verify_prompt_ledger(ledger_bytes, receipt_value)
            except producer.FreeReviewError as exc:
                return exc.status + ":" + exc.reason
            return "VERIFIED"

        ledger_bytes = ledger_path.read_bytes()
        ledger_lines = ledger_bytes.split(b"\n")
        dropped = b"\n".join(ledger_lines[:-2] + [b""])
        extra = ledger_bytes + ledger_lines[-2] + b"\n"
        flipped_row = json.loads(ledger_lines[0])
        flipped_row["prompt"] = flipped_row["prompt"][:-1] + "!"
        flipped = b"\n".join([
            json.dumps(flipped_row, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8"),
            *ledger_lines[1:],
        ])
        foreign_receipt = copy.deepcopy(ledger_receipt)
        foreign_receipt["signed"]["promptLedger"]["entries"][0]["sha256"] = "0" * 64
        unbound_receipt = copy.deepcopy(ledger_receipt)
        del unbound_receipt["signed"]["promptLedger"]
        ledger_mutations = {
            "missing": ledger_why(dropped, ledger_receipt),
            "extra": ledger_why(extra, ledger_receipt),
            "flipped": ledger_why(flipped, ledger_receipt),
            "foreign": ledger_why(ledger_bytes, foreign_receipt),
            "unbound": ledger_why(ledger_bytes, unbound_receipt),
            "garbage": ledger_why(b"not json\n", ledger_receipt),
        }
        check(
            all(value.startswith("UNVERIFIED:")
                for value in ledger_mutations.values())
            and "missing" in ledger_mutations["missing"]
            and "extra" in ledger_mutations["extra"],
            "a tampered prompt ledger or receipt still verifies: "
            f"{ledger_mutations}",
        )
        ledger_receipt_path = fixture / "split-transcript" / "phase-one.json"
        ledger_receipt_path.write_text(json.dumps(ledger_receipt), encoding="utf-8")
        cli_ok = subprocess.run(
            [sys.executable, "-I", str(PRODUCER), "verify-prompt-log",
             "--prompt-log", str(ledger_path),
             "--receipt", str(ledger_receipt_path)],
            capture_output=True, text=True, timeout=120,
        )
        broken_ledger_path = fixture / "split-transcript" / "prompt.broken.jsonl"
        broken_ledger_path.write_bytes(dropped)
        cli_bad = subprocess.run(
            [sys.executable, "-I", str(PRODUCER), "verify-prompt-log",
             "--prompt-log", str(broken_ledger_path),
             "--receipt", str(ledger_receipt_path)],
            capture_output=True, text=True, timeout=120,
        )
        check(
            cli_ok.returncode == 0
            and json.loads(cli_ok.stdout)["status"] == "VERIFIED"
            and cli_bad.returncode != 0
            and json.loads(cli_bad.stdout)["status"] == "UNVERIFIED"
            and "missing" in json.loads(cli_bad.stdout)["why"],
            "verify-prompt-log does not report VERIFIED/UNVERIFIED as a pure "
            f"function of the two files ({cli_ok.stdout!r} {cli_bad.stdout!r} "
            f"{cli_bad.stderr!r})",
        )
        # direct mode: one entry whose hash is the receipt's promptSha256
        direct_ledger_path = fixture / "direct.ledger.jsonl"
        direct_ledger = producer.PromptLedger(direct_ledger_path)
        direct_prompts = []

        def direct_runner(prompt_text, report_schema, report_parser):
            direct_prompts.append(prompt_text)
            return report_parser(clean_verdict()), "fresh-direct-ledger", "gpt-5.6-terra"

        producer.run_packet_review(
            transparent_packet, direct_runner, prompt_ledger=direct_ledger,
        )
        direct_binding = direct_ledger.binding()
        direct_receipt = mint(
            producer.review_prompt(transparent_packet), transparent_packet,
            direct_binding,
        )
        check(
            [(entry["kind"], entry["unitIndex"]) for entry in direct_binding["entries"]]
            == [("direct", None)]
            and direct_binding["entries"][0]["sha256"]
            == direct_receipt["signed"]["promptSha256"]
            == hashlib.sha256(direct_prompts[0].encode("utf-8")).hexdigest()
            and producer.verify_prompt_ledger(
                direct_ledger_path.read_bytes(), direct_receipt
            )["status"] == "VERIFIED",
            "the direct route does not ledger its single prompt against "
            "promptSha256",
        )
        # A receipt whose ledger binding contradicts the prompt artifact
        # (a unit hash that no sent unit prompt has) must not be mintable.
        contradicting = copy.deepcopy(ledger_binding)
        contradicting["entries"][0]["sha256"] = "1" * 64
        try:
            mint(ledger_bundle, split_packet, contradicting)
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED",
                "a contradicting ledger binding failed with the wrong status",
            )
        else:
            raise AssertionError(
                "a ledger binding contradicting the prompt artifact was signed"
            )

        # End-to-end: the review command writes the ledger next to the prompt
        # artifact, binds it into the receipt, and refuses to emit a receipt
        # whose ledger no longer verifies (self-check before publication).
        e2e_root = fixture / "s11-e2e"
        e2e_root.mkdir()
        e2e_key = e2e_root / "producer.key"
        e2e_key.write_bytes(ledger_private)
        e2e_key.chmod(0o600)
        e2e_prompt = e2e_root / "prompt.md"
        e2e_report = e2e_root / "report.json"
        e2e_receipt = e2e_root / "phase-one.json"
        e2e_sessions = []

        def fake_codex_review(prompt_text, **kwargs):
            e2e_sessions.append(f"fresh-e2e-{len(e2e_sessions) + 1}")
            schema = kwargs["report_schema"]
            report = (
                {"verdict": "PASSED", "findings": [], "unverified": [],
                 "summary": "Bound range reviewed; no cross-unit risk."}
                if schema == producer.UNIT_VERDICT_SCHEMA else clean_verdict()
            )
            return kwargs["report_parser"](report), e2e_sessions[-1], "gpt-5.6-terra"

        def e2e_argv(root_dir):
            return [
                "review", "--root", str(split_repo), "--base", split_base,
                "--repository", "hihol-labs/idea-to-deploy",
                "--scope", str(split_scope), "--acceptance", str(split_acceptance),
                "--machine-receipt", str(split_machine),
                "--signing-key", str(e2e_key), "--key-id", "free-reviewer-2026-08",
                "--maker-provider", "openai-codex", "--maker-model", "gpt-5.6-sol",
                "--maker-session", "maker-session-e2e",
                "--codex-sha256", "5" * 64, "--proxy-sha256", "6" * 64,
                "--prompt-output", str(root_dir / "prompt.md"),
                "--report-output", str(root_dir / "report.json"),
                "--output", str(root_dir / "phase-one.json"),
            ]

        original_codex_review = producer.run_codex_review
        original_phase_one_receipt = producer.phase_one_receipt
        producer.run_codex_review = fake_codex_review
        try:
            e2e_out = io.StringIO()
            with contextlib.redirect_stdout(e2e_out):
                e2e_code = producer.main(e2e_argv(e2e_root))
            e2e_ledger = e2e_root / "prompt.md.ledger.jsonl"
            e2e_verify = subprocess.run(
                [sys.executable, "-I", str(PRODUCER), "verify-prompt-log",
                 "--prompt-log", str(e2e_ledger), "--receipt", str(e2e_receipt)],
                capture_output=True, text=True, timeout=120,
            )
            check(
                e2e_code == 0
                and json.loads(e2e_out.getvalue())["promptLedger"] == str(e2e_ledger)
                and e2e_ledger.is_file()
                and len(e2e_ledger.read_bytes().decode("utf-8").split("\n")[:-1])
                == split_plan["unitCount"] + 1
                and e2e_verify.returncode == 0
                and json.loads(e2e_verify.stdout)["status"] == "VERIFIED"
                and json.loads(e2e_receipt.read_text(encoding="utf-8"))["signed"]
                ["promptLedger"]["sha256"]
                == hashlib.sha256(e2e_ledger.read_bytes()).hexdigest(),
                "the review command does not publish a receipt-bound prompt "
                f"ledger (rc={e2e_code} {e2e_out.getvalue()!r} "
                f"{e2e_verify.stdout!r} {e2e_verify.stderr!r})",
            )

            def corrupting_phase_one_receipt(**kwargs):
                # Damage the ledger between the last send and the signature.
                with open(e2e_root2 / "prompt.md.ledger.jsonl", "ab") as handle:
                    handle.write(b'{"stray":true}\n')
                return original_phase_one_receipt(**kwargs)

            e2e_root2 = fixture / "s11-e2e-corrupt"
            e2e_root2.mkdir()
            e2e_sessions.clear()
            producer.phase_one_receipt = corrupting_phase_one_receipt
            e2e_err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(e2e_err):
                e2e_code2 = producer.main(e2e_argv(e2e_root2))
            check(
                e2e_code2 == 4
                and json.loads(e2e_err.getvalue())["status"] == "UNVERIFIED"
                and "prompt ledger" in json.loads(e2e_err.getvalue())["reason"]
                and not (e2e_root2 / "phase-one.json").exists(),
                "the review command emitted a receipt over a prompt ledger that "
                f"does not verify (rc={e2e_code2} {e2e_err.getvalue()!r})",
            )
        finally:
            producer.run_codex_review = original_codex_review
            producer.phase_one_receipt = original_phase_one_receipt

        unit_failure_calls = 0

        def unit_failure_runner(prompt_text, report_schema, report_parser):
            nonlocal unit_failure_calls
            unit_failure_calls += 1
            if (
                report_schema == producer.UNIT_VERDICT_SCHEMA
                and unit_failure_calls == 1
            ):
                report = {
                    "verdict": "BLOCKED",
                    "findings": [{
                        "severity": "high",
                        "confidence": "high",
                        "category": "correctness",
                        "file": "service.py",
                        "line": 1,
                        "summary": "A bound unit found a blocking defect.",
                    }],
                    "unverified": [],
                    "summary": "The first unit contains one blocking defect.",
                }
            elif report_schema == producer.UNIT_VERDICT_SCHEMA:
                report = {
                    "verdict": "PASSED", "findings": [], "unverified": [],
                    "summary": "Bound unit behavior and interfaces are consistent.",
                }
            else:
                # A clean integration response must never erase a unit failure.
                report = clean_verdict()
            return (
                report_parser(report),
                f"fresh-unit-failure-{unit_failure_calls}",
                "subscription-model",
            )

        blocked_report, _session, _model, blocked_artifact = (
            producer.run_packet_review(large_packet, unit_failure_runner)
        )
        check(
            blocked_report["verdict"] == "BLOCKED"
            and len(blocked_report["findings"]) == 1
            and blocked_report["findings"][0]["file"] == "service.py",
            "clean integration report erased a blocking unit finding",
        )
        producer.validate_review_prompt_artifact(
            large_packet, blocked_artifact, blocked_report,
        )
        checks += 1
        mutated_bundle = json.loads(prompt_artifact)
        mutated_bundle["unitCalls"][0]["report"]["summary"] += " changed"
        try:
            producer.validate_review_prompt_artifact(
                large_packet,
                producer.canonical_bytes(mutated_bundle).decode("utf-8"),
                final_report,
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("changed hierarchical unit evidence was accepted")
        checks += 1

        try:
            producer._unit_report({
                "verdict": "PASSED",
                "findings": [],
                "unverified": [],
                "summary": "x" * (producer.MAX_UNIT_SUMMARY_BYTES + 1),
            })
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED" and "summary" in exc.reason,
                "oversized unit summary failed with the wrong disposition",
            )
        else:
            raise AssertionError("oversized unit summary was accepted")

        def reused_session_runner(prompt_text, report_schema, report_parser):
            if report_schema == producer.UNIT_VERDICT_SCHEMA:
                report = {
                    "verdict": "PASSED", "findings": [], "unverified": [],
                    "summary": "Bound unit behavior and interfaces are consistent.",
                }
            else:
                report = clean_verdict()
            return report_parser(report), "reused-session", "subscription-model"

        try:
            producer.run_packet_review(large_packet, reused_session_runner)
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED" and "session was reused" in exc.reason,
                "hierarchical session reuse failed with the wrong disposition",
            )
        else:
            raise AssertionError("hierarchical reviewer session reuse was accepted")

        mixed_model_calls = 0
        def mixed_model_runner(prompt_text, report_schema, report_parser):
            nonlocal mixed_model_calls
            mixed_model_calls += 1
            if report_schema == producer.UNIT_VERDICT_SCHEMA:
                report = {
                    "verdict": "PASSED", "findings": [], "unverified": [],
                    "summary": "Bound unit behavior and interfaces are consistent.",
                }
            else:
                report = clean_verdict()
            model = "foreign-model" if mixed_model_calls == 2 else "subscription-model"
            return report_parser(report), f"fresh-mixed-{mixed_model_calls}", model

        try:
            producer.run_packet_review(large_packet, mixed_model_runner)
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED" and "model changed" in exc.reason,
                "hierarchical mixed-model evidence failed with the wrong disposition",
            )
        else:
            raise AssertionError("hierarchical mixed-model evidence was accepted")

        # --- U15: per-unit resumability of the hierarchical route.
        # A transient transport loss must cost only the failing unit, a unit
        # that already produced a verdict is never re-run, and any checkpoint
        # anomaly (tamper, staleness, foreign binding) discards the checkpoint
        # and restarts the route from zero instead of being trusted.
        route_key = raw_private_key()
        route_binding = {
            "provider": "openai-subscription",
            "requestedModel": "gpt-5.6-terra",
            "transportExecutableSha256": "a" * 64,
            "proxySha256": "b" * 64,
        }
        route_checkpoint = fixture / "route-checkpoint.json"
        unit_count = plan["unitCount"]

        def passed_unit_report() -> dict:
            return {
                "verdict": "PASSED", "findings": [], "unverified": [],
                "summary": "Bound unit behavior and interfaces are consistent.",
            }

        def make_interrupting_runner(fail_at: int, tag: str):
            state = {"calls": 0}

            def interrupting_runner(prompt_text, report_schema, report_parser):
                state["calls"] += 1
                if state["calls"] == fail_at:
                    raise producer.FreeReviewError(
                        "UNAVAILABLE", "simulated transport loss mid-route"
                    )
                report = (
                    passed_unit_report()
                    if report_schema == producer.UNIT_VERDICT_SCHEMA
                    else clean_verdict()
                )
                return (
                    report_parser(report),
                    f"resume-{tag}-{state['calls']}",
                    "subscription-model",
                )

            return interrupting_runner

        try:
            producer.run_packet_review(
                large_packet, make_interrupting_runner(3, "a"),
                checkpoint_path=route_checkpoint,
                checkpoint_binding=dict(route_binding),
                checkpoint_key_id="route-checkpoint-test",
                checkpoint_private_key=route_key,
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNAVAILABLE" and route_checkpoint.exists(),
                "interrupted hierarchical route left no resumable checkpoint",
            )
        else:
            raise AssertionError("simulated transport loss did not fail the attempt")

        resumed_prompts = []

        def resuming_runner(prompt_text, report_schema, report_parser):
            resumed_prompts.append(prompt_text)
            report = (
                passed_unit_report()
                if report_schema == producer.UNIT_VERDICT_SCHEMA
                else clean_verdict()
            )
            return (
                report_parser(report),
                f"resume-b-{len(resumed_prompts)}",
                "subscription-model",
            )

        resumed_report, _resumed_session, _resumed_model, resumed_artifact = (
            producer.run_packet_review(
                large_packet, resuming_runner,
                checkpoint_path=route_checkpoint,
                checkpoint_binding=dict(route_binding),
                checkpoint_key_id="route-checkpoint-test",
                checkpoint_private_key=route_key,
            )
        )
        check(
            resumed_report == clean_verdict()
            and len(resumed_prompts) == unit_count - 2 + 1
            and not route_checkpoint.exists(),
            "resumed hierarchical route re-ran completed units or kept its checkpoint",
        )
        producer.validate_review_prompt_artifact(
            large_packet, resumed_artifact, resumed_report,
        )
        resumed_bundle = json.loads(resumed_artifact)
        check(
            resumed_bundle["unitCalls"][0]["prompt"] not in resumed_prompts
            and resumed_bundle["unitCalls"][1]["prompt"] not in resumed_prompts
            and resumed_bundle["unitCalls"][2]["prompt"] in resumed_prompts,
            "resumed route did not bind stored verdicts to their original units",
        )

        def make_counting_runner(tag: str, counter: list):
            def counting_runner(prompt_text, report_schema, report_parser):
                counter.append(prompt_text)
                report = (
                    passed_unit_report()
                    if report_schema == producer.UNIT_VERDICT_SCHEMA
                    else clean_verdict()
                )
                return (
                    report_parser(report),
                    f"resume-{tag}-{len(counter)}",
                    "subscription-model",
                )
            return counting_runner

        def regenerate_checkpoint(tag: str) -> None:
            try:
                producer.run_packet_review(
                    large_packet, make_interrupting_runner(3, tag),
                    checkpoint_path=route_checkpoint,
                    checkpoint_binding=dict(route_binding),
                    checkpoint_key_id="route-checkpoint-test",
                    checkpoint_private_key=route_key,
                )
            except producer.FreeReviewError:
                pass

        regenerate_checkpoint("c")
        tampered = json.loads(route_checkpoint.read_text(encoding="utf-8"))
        tampered["signed"]["units"][0]["report"]["summary"] += " changed"
        route_checkpoint.write_text(
            json.dumps(tampered, ensure_ascii=False), encoding="utf-8"
        )
        tampered_calls: list = []
        tampered_report, _s1, _m1, _a1 = producer.run_packet_review(
            large_packet, make_counting_runner("d", tampered_calls),
            checkpoint_path=route_checkpoint,
            checkpoint_binding=dict(route_binding),
            checkpoint_key_id="route-checkpoint-test",
            checkpoint_private_key=route_key,
        )
        check(
            tampered_report == clean_verdict()
            and len(tampered_calls) == unit_count + 1,
            "tampered route checkpoint was trusted instead of forcing a restart",
        )

        regenerate_checkpoint("e")
        stale = json.loads(route_checkpoint.read_text(encoding="utf-8"))
        stale["signed"]["updatedAt"] = "2020-01-01T00:00:00Z"
        stale_signature = producer.Ed25519PrivateKey.from_private_bytes(
            route_key
        ).sign(producer.canonical_bytes(stale["signed"])).hex()
        stale["signatureHex"] = stale_signature
        route_checkpoint.write_text(
            json.dumps(stale, ensure_ascii=False), encoding="utf-8"
        )
        stale_calls: list = []
        stale_report, _s2, _m2, _a2 = producer.run_packet_review(
            large_packet, make_counting_runner("f", stale_calls),
            checkpoint_path=route_checkpoint,
            checkpoint_binding=dict(route_binding),
            checkpoint_key_id="route-checkpoint-test",
            checkpoint_private_key=route_key,
        )
        check(
            stale_report == clean_verdict()
            and len(stale_calls) == unit_count + 1,
            "stale route checkpoint was trusted instead of forcing a restart",
        )

        regenerate_checkpoint("g")
        foreign_binding = dict(route_binding)
        foreign_binding["provider"] = "gemini-user"
        foreign_calls: list = []
        foreign_report, _s3, _m3, _a3 = producer.run_packet_review(
            large_packet, make_counting_runner("h", foreign_calls),
            checkpoint_path=route_checkpoint,
            checkpoint_binding=foreign_binding,
            checkpoint_key_id="route-checkpoint-test",
            checkpoint_private_key=route_key,
        )
        check(
            foreign_report == clean_verdict()
            and len(foreign_calls) == unit_count + 1,
            "foreign-provider route checkpoint was trusted instead of discarded",
        )
        route_checkpoint.unlink(missing_ok=True)

        try:
            producer.run_packet_review(
                large_packet, make_counting_runner("i", []),
                checkpoint_path=route_checkpoint,
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED"
                and "checkpoint configuration" in exc.reason,
                "incomplete checkpoint configuration failed with the wrong disposition",
            )
        else:
            raise AssertionError(
                "checkpoint path without signing material was accepted"
            )

        # Every checkpoint guard is exercised from the outside: a checkpoint
        # carrying the anomaly must be discarded whole, so the route re-runs
        # every unit plus integration. Nothing unverified is ever reused.
        unit_ids = [call["unit"] for call in resumed_bundle["unitCalls"]]

        def signed_checkpoint(tag: str) -> dict:
            regenerate_checkpoint(tag)
            envelope = json.loads(route_checkpoint.read_text(encoding="utf-8"))
            route_checkpoint.unlink()
            return envelope

        def resign(envelope: dict) -> None:
            envelope["signatureHex"] = producer.Ed25519PrivateKey.from_private_bytes(
                route_key
            ).sign(producer.canonical_bytes(envelope["signed"])).hex()
            route_checkpoint.write_text(
                json.dumps(envelope, ensure_ascii=False), encoding="utf-8"
            )

        def check_full_restart(tag: str, message: str) -> None:
            calls: list = []
            report, _session, _model, _artifact = producer.run_packet_review(
                large_packet, make_counting_runner(tag, calls),
                checkpoint_path=route_checkpoint,
                checkpoint_binding=dict(route_binding),
                checkpoint_key_id="route-checkpoint-test",
                checkpoint_private_key=route_key,
            )
            check(
                report == clean_verdict() and len(calls) == unit_count + 1,
                message,
            )

        def full_prefix_rows() -> list[dict]:
            return [
                {
                    "unit": unit_id, "report": passed_unit_report(),
                    "session": f"synthetic-{index}",
                    "model": "subscription-model",
                }
                for index, unit_id in enumerate(unit_ids)
            ]

        envelope = signed_checkpoint("j")
        envelope["note"] = "smuggled envelope field"
        resign(envelope)
        check_full_restart(
            "k", "route checkpoint envelope accepted an undeclared field"
        )

        envelope = signed_checkpoint("l")
        envelope["signed"]["note"] = "smuggled signed field"
        resign(envelope)
        check_full_restart(
            "m", "route checkpoint signed payload accepted an undeclared field"
        )

        envelope = signed_checkpoint("n")
        envelope["signed"]["keyId"] = "route-checkpoint-other"
        resign(envelope)
        check_full_restart(
            "o", "route checkpoint signed by a foreign key id was trusted"
        )

        envelope = signed_checkpoint("p")
        envelope["signatureHex"] = envelope["signatureHex"].upper()
        route_checkpoint.write_text(
            json.dumps(envelope, ensure_ascii=False), encoding="utf-8"
        )
        check_full_restart(
            "q", "route checkpoint accepted a non-canonical signature encoding"
        )

        envelope = signed_checkpoint("r")
        rows = full_prefix_rows()
        envelope["signed"]["units"] = rows + [
            dict(rows[-1], session="synthetic-overflow")
        ]
        resign(envelope)
        check_full_restart(
            "s", "route checkpoint longer than the frozen plan was trusted"
        )

        envelope = signed_checkpoint("t")
        envelope["signed"]["units"][0]["note"] = "smuggled row field"
        resign(envelope)
        check_full_restart(
            "u", "route checkpoint row accepted an undeclared field"
        )

        envelope = signed_checkpoint("v")
        envelope["signed"]["units"][0]["unit"] = unit_ids[1]
        resign(envelope)
        check_full_restart(
            "w", "route checkpoint row bound to a foreign unit was trusted"
        )

        envelope = signed_checkpoint("x")
        envelope["signed"]["units"][0]["report"] = {"verdict": "PASSED"}
        resign(envelope)
        check_full_restart(
            "y", "route checkpoint row bypassed the unit report contract"
        )

        envelope = signed_checkpoint("z")
        envelope["signed"]["units"][0]["session"] = " resume-z-1 "
        resign(envelope)
        check_full_restart(
            "aa", "route checkpoint row accepted untrimmed provenance"
        )

        envelope = signed_checkpoint("ab")
        envelope["signed"]["units"][1]["session"] = (
            envelope["signed"]["units"][0]["session"]
        )
        resign(envelope)
        check_full_restart(
            "ac", "route checkpoint rows reusing one session were trusted"
        )

        envelope = signed_checkpoint("ad")
        envelope["signed"]["units"][1]["model"] = "other-subscription-model"
        resign(envelope)
        check_full_restart(
            "ae", "route checkpoint rows changing the reviewer model were trusted"
        )

        route_checkpoint.unlink(missing_ok=True)
        try:
            producer.run_packet_review(
                large_packet, make_counting_runner("af", []),
                checkpoint_path=route_checkpoint,
                checkpoint_binding=dict(route_binding, proxySha256=""),
                checkpoint_key_id="route-checkpoint-test",
                checkpoint_private_key=route_key,
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED"
                and "checkpoint binding is invalid" in exc.reason,
                "empty checkpoint binding failed with the wrong disposition",
            )
        else:
            raise AssertionError(
                "route checkpoint accepted an empty reviewer binding"
            )
        route_checkpoint.unlink(missing_ok=True)

        hostile_binary_cases = (
            ("generic.bin", b"\x00\x01\x02", "undeclared binary"),
            ("invalid.jsonl.gz", b"not-gzip", "invalid gzip"),
            (
                "multiple.jsonl.gz",
                gzip.compress(b'{"a":1}\n', mtime=0)
                + gzip.compress(b'{"b":2}\n', mtime=0),
                "multiple gzip members",
            ),
            (
                "invalid-json.jsonl.gz",
                gzip.compress(b"not-json\n", mtime=0),
                "invalid JSONL",
            ),
            (
                "duplicate.jsonl.gz",
                gzip.compress(b'{"a":1,"a":2}\n', mtime=0),
                "duplicate JSON keys",
            ),
            (
                "constant.jsonl.gz",
                gzip.compress(b'{"a":NaN}\n', mtime=0),
                "non-standard JSON constant",
            ),
            (
                "empty-record.jsonl.gz",
                gzip.compress(b'{"a":1}\n\n{"b":2}\n', mtime=0),
                "empty JSONL record",
            ),
            (
                "oversized.jsonl.gz",
                gzip.compress(
                    b'{"a":"' + b"x" * (1024 * 1024) + b'"}\n', mtime=0
                ),
                "decompression bound",
            ),
        )
        for index, (name, payload, label) in enumerate(hostile_binary_cases):
            hostile_root = fixture / f"hostile-{index}"
            hostile_repo = hostile_root / "repo"
            hostile_repo.mkdir(parents=True)
            hostile_base, hostile_parent, _ = git_fixture(hostile_repo)
            (hostile_repo / name).write_bytes(payload)
            shell(["git", "add", name], hostile_repo)
            hostile_tree = shell(["git", "write-tree"], hostile_repo)
            hostile_inputs = hostile_root / "inputs"
            hostile_inputs.mkdir()
            hostile_scope, hostile_acceptance, hostile_machine = write_inputs(
                hostile_inputs, hostile_repo, hostile_parent, hostile_tree
            )
            try:
                producer.freeze_packet(
                    root=hostile_repo, base_commit=hostile_base,
                    repository="hihol-labs/idea-to-deploy", pull_request=None,
                    expected_head_sha=None, scope_file=hostile_scope,
                    acceptance_file=hostile_acceptance,
                    machine_receipt=hostile_machine,
                )
            except producer.FreeReviewError as exc:
                check(
                    exc.status == "UNVERIFIED",
                    f"{label} failed with a non-terminal disposition",
                )
            else:
                raise AssertionError(f"{label} reached the independent reviewer")

        argv = producer.codex_command(
            executable="codex", model="gpt-5.6-terra",
            output_schema=fixture / "verdict.schema.json",
            report_file=fixture / "report.json",
        )
        disabled = {
            argv[index + 1]
            for index, value in enumerate(argv[:-1]) if value == "--disable"
        }
        check(disabled == set(producer.disabled_tool_features()),
              "Codex tool denylist is not exact")
        check({
            "shell_tool", "apps", "browser_use", "browser_use_external",
            "browser_use_full_cdp_access", "computer_use", "in_app_browser",
            "plugins", "remote_plugin", "image_generation", "multi_agent",
            "enable_fanout", "skill_mcp_dependency_install", "tool_suggest",
            "code_mode_host", "workspace_dependencies", "hooks", "goals",
        }.issubset(disabled), "Codex isolation omits an enabled tool surface")
        check(all(value in argv for value in (
            "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check",
        )) and "--ephemeral" not in argv,
              "Codex temporary-home provenance/sandbox flags are incomplete")
        check(
            "TemporaryDirectory-backed CODEX_HOME" in inspect.getsource(
                producer.codex_command
            ),
            "Codex non-persistence/model-provenance trade-off is undocumented",
        )
        source = inspect.getsource(producer)
        check(
            'review_broker = _LazyModule("itd_review_broker")' in source
            and "import itd_review_broker as review_broker" not in source,
            "direct keyless transports avoid an eager broker/jsonschema dependency",
        )
        check("resume" not in argv, "producer can inherit an old Codex session")
        check("api.openai.com" not in " ".join(argv), "paid API route is present")
        finding_schema = producer.VERDICT_SCHEMA["properties"]["findings"].get("items")
        check(
            isinstance(finding_schema, dict)
            and finding_schema.get("additionalProperties") is False
            and set(finding_schema.get("required", []))
            == {"severity", "confidence", "category", "file", "line", "summary"},
            "review finding output schema is not closed",
        )

        trusted_binary = Path(sys.executable).resolve()
        trusted_binary_sha = producer.sha256_bytes(trusted_binary.read_bytes())
        review_codex_home = fixture / "review-codex-home"
        review_codex_home.mkdir()
        auth_fields = producer.subscription_auth_field_names()
        api_key_field = auth_fields["apiKey"]
        token_fields = {
            auth_fields["access"]: "a",
            auth_fields["account"]: "b",
            auth_fields["identity"]: "c",
            auth_fields["refresh"]: "d",
        }
        subscription_auth = {
            "auth_mode": "chatgpt",
            api_key_field: None,
            "tokens": token_fields,
            "last_refresh": "2026-08-01T18:00:00Z",
        }
        (review_codex_home / "auth.json").write_text(
            json.dumps(subscription_auth), encoding="utf-8"
        )
        if os.name != "nt":
            (review_codex_home / "auth.json").chmod(0o600)
        transport_source = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(fixture / "transport-home"),
            "CODEX_HOME": str(review_codex_home),
            "HTTP_PROXY": "http://proxy.invalid:8080",
            "HTTPS_PROXY": "http://proxy.invalid:8080",
        }
        trusted_proxy_sha = producer.sha256_bytes(
            (transport_source["HTTP_PROXY"] + "\n"
             + transport_source["HTTPS_PROXY"]).encode("utf-8")
        )
        original_run = producer.run_bounded_process
        event_item_type = "agent_message"
        event_item_extra: dict[str, object] = {}
        observed_transport_env = {}
        rollout_padding_bytes = 0

        def fake_codex_run(command, **kwargs):
            observed_transport_env.update(kwargs["env"])
            report_path = Path(
                command[command.index("--output-last-message") + 1]
            )
            report_path.write_text(json.dumps(clean_verdict()), encoding="utf-8")
            rollout = (
                Path(kwargs["env"]["CODEX_HOME"])
                / "sessions" / "2026" / "08" / "03" / "rollout-fixture.jsonl"
            )
            rollout.parent.mkdir(parents=True)
            rollout_events = [{
                "type": "session_meta", "payload": {"id": "fresh-clean"},
            }]
            if event_model is not None:
                rollout_events.append({
                    "type": "turn_context", "payload": {"model": event_model},
                })
            if rollout_padding_bytes:
                rollout_events.append({
                    "type": "response_item",
                    "payload": {"text": "x" * rollout_padding_bytes},
                })
            rollout.write_bytes(b"\n".join(
                json.dumps(event).encode() for event in rollout_events
            ) + b"\n")
            events = b"\n".join((
                json.dumps({
                    "type": "thread.started", "thread_id": "fresh-clean",
                }).encode(),
                json.dumps({"type": "item.completed", "item": dict(
                    {"type": event_item_type, "text": "done"},
                    **event_item_extra,
                )}).encode(),
            )) + b"\n"
            return subprocess.CompletedProcess(command, 0, events, b"")

        producer.run_bounded_process = fake_codex_run
        event_model = "subscription-model"
        observed_report, observed_session, observed_model = producer.run_codex_review(
            "bounded prompt", executable=str(trusted_binary),
            model="subscription-model", source_env=transport_source,
            expected_executable_sha256=trusted_binary_sha,
            expected_proxy_sha256=trusted_proxy_sha,
        )
        check(observed_report == clean_verdict()
              and observed_session == "fresh-clean"
              and observed_model == "subscription-model",
              "zero-tool reviewer event stream was not accepted")
        check(
            observed_transport_env.get("HTTP_PROXY")
            == transport_source["HTTP_PROXY"]
            and observed_transport_env.get("HTTPS_PROXY")
            == transport_source["HTTPS_PROXY"],
            "content-pinned transport proxy was not applied",
        )
        rollout_padding_bytes = producer.MAX_INPUT_BYTES + 1
        padded_report, padded_session, padded_model = producer.run_codex_review(
            "bounded prompt", executable=str(trusted_binary),
            model="subscription-model", source_env=transport_source,
            expected_executable_sha256=trusted_binary_sha,
            expected_proxy_sha256=trusted_proxy_sha,
        )
        check(
            padded_report == clean_verdict()
            and padded_session == "fresh-clean"
            and padded_model == "subscription-model",
            "bounded Codex rollout larger than the prompt cap lost provenance",
        )
        rollout_padding_bytes = 0
        event_model = None
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model", source_env=transport_source,
                expected_executable_sha256=trusted_binary_sha,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNAVAILABLE",
                "missing OpenAI model telemetry was not unavailable",
            )
        else:
            raise AssertionError("missing OpenAI model telemetry was accepted")
        event_model = "maker-model"
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model", source_env=transport_source,
                expected_executable_sha256=trusted_binary_sha,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED",
                "mismatched OpenAI model telemetry was not terminal",
            )
        else:
            raise AssertionError("mismatched OpenAI model telemetry was accepted")
        event_model = "subscription-model"
        event_item_type = "command_execution"
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model",
                source_env=transport_source,
                expected_executable_sha256=trusted_binary_sha,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("observed reviewer tool call was accepted")
        checks += 1
        # A19. Newer Codex builds report a turn failure as an error ITEM
        # instead of a turn.failed EVENT. The two-name allowlist counted that
        # item as a tool call, so the transport's own failure was reported as
        # the reviewer breaking isolation - blaming the reviewer and hiding the
        # cause. An error item is a CLI failure, and it must say so.
        event_item_type = "error"
        event_item_extra = {"message": "stream disconnected before completion"}
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model", source_env=transport_source,
                expected_executable_sha256=trusted_binary_sha,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError as exc:
            check(
                "event stream" in str(exc)
                and "attempted to use a tool" not in str(exc),
                "codex error item was misreported as a reviewer tool call",
            )
        else:
            raise AssertionError("codex error item was accepted as a clean turn")

        # The build acknowledging our own --disable code_mode_host arrives as an
        # advisory error item while the turn still completes. That is the closed
        # denylist working: neither a failure nor a tool call.
        event_item_extra = {
            "message": producer.CODE_MODE_DISABLED_ADVISORY_PREFIX
            + " - install the code-mode host to enable it",
        }
        advisory_report, advisory_session, _ = producer.run_codex_review(
            "bounded prompt", executable=str(trusted_binary),
            model="subscription-model", source_env=transport_source,
            expected_executable_sha256=trusted_binary_sha,
            expected_proxy_sha256=trusted_proxy_sha,
        )
        check(
            advisory_report == clean_verdict()
            and advisory_session == "fresh-clean",
            "code-mode-disabled advisory was treated as a failure",
        )

        # A genuine advisory is one printable line. Anything that starts with
        # the prefix and then smuggles a control character plus text is not the
        # CLI acknowledging our flag. Two review rounds found two holes here -
        # CR past an LF-only test, then NUL past a line-splitting test - so the
        # cases below cover every C0/C1 control and Unicode separator, not a
        # hand-listed subset.
        for separator in ("\n", "\r", "\r\n", "\u2028", "\u2029", "\x0b",
                          "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\x00",
                          "\x07", "\x7f"):
            event_item_extra = {
                "message": producer.CODE_MODE_DISABLED_ADVISORY_PREFIX
                + separator + "and here is something else entirely",
            }
            try:
                producer.run_codex_review(
                    "bounded prompt", executable=str(trusted_binary),
                    model="subscription-model", source_env=transport_source,
                    expected_executable_sha256=trusted_binary_sha,
                    expected_proxy_sha256=trusted_proxy_sha,
                )
            except producer.FreeReviewError as exc:
                check(
                    "event stream" in str(exc),
                    "a broken-line advisory was not treated as a transport"
                    f" failure (separator {separator!r})",
                )
            else:
                raise AssertionError(
                    f"a broken-line advisory was accepted (separator {separator!r})"
                )

        # A separator BEFORE or AFTER the prefix must not be normalized away
        # first: stripping before validating accepted "\rPREFIX" outright.
        for wrapped in ("\r" + producer.CODE_MODE_DISABLED_ADVISORY_PREFIX,
                        producer.CODE_MODE_DISABLED_ADVISORY_PREFIX + "\n",
                        " " + producer.CODE_MODE_DISABLED_ADVISORY_PREFIX):
            event_item_extra = {"message": wrapped}
            try:
                producer.run_codex_review(
                    "bounded prompt", executable=str(trusted_binary),
                    model="subscription-model", source_env=transport_source,
                    expected_executable_sha256=trusted_binary_sha,
                    expected_proxy_sha256=trusted_proxy_sha,
                )
            except producer.FreeReviewError as exc:
                check("event stream" in str(exc),
                      f"a padded advisory was not treated as a transport failure ({wrapped!r})")
            else:
                raise AssertionError(f"a padded advisory was accepted ({wrapped!r})")

        # Anything else in an error item stays fail-closed - and stays a
        # TRANSPORT failure. A near-miss of the advisory wording must not be
        # accepted, and must not be reported as the reviewer using a tool
        # either; the pre-change producer refused it for the wrong reason.
        event_item_extra = {"message": "Code Mode is unavailable"}
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model", source_env=transport_source,
                expected_executable_sha256=trusted_binary_sha,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError as exc:
            check(
                "event stream" in str(exc)
                and "attempted to use a tool" not in str(exc),
                "a near-miss advisory was refused as a reviewer tool call",
            )
        else:
            raise AssertionError("a non-advisory error item was accepted")

        # A refusal must name what it saw: a newer CLI emitting an item type
        # this allowlist has never heard of cannot otherwise be told apart from
        # a real tool call, which is exactly the distinction an operator needs.
        event_item_extra = {}
        event_item_type = "web_search_call"
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model", source_env=transport_source,
                expected_executable_sha256=trusted_binary_sha,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError as exc:
            check(
                "attempted to use a tool" in str(exc)
                and "web_search_call" in str(exc),
                "tool-call refusal did not name the observed item type",
            )
        else:
            raise AssertionError("unknown reviewer item type was accepted")
        event_item_type = "agent_message"
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model", source_env=transport_source,
                expected_executable_sha256="f" * 64,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("untrusted Codex executable reached subscription auth")
        producer.run_bounded_process = original_run
        checks += 1
        hostile_proxy_source = dict(transport_source)
        hostile_proxy_source["HTTPS_PROXY"] = "http://hostile.invalid:8080"
        try:
            producer.run_codex_review(
                "bounded prompt", executable=str(trusted_binary),
                model="subscription-model", source_env=hostile_proxy_source,
                expected_executable_sha256=trusted_binary_sha,
                expected_proxy_sha256=trusted_proxy_sha,
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("caller-controlled proxy bypassed the content pin")
        checks += 1

        direct_source = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(fixture / "direct-home"),
            "CODEX_HOME": str(review_codex_home),
        }
        direct_pin = producer.sha256_bytes(b"\n")
        check(
            producer.trusted_proxy_environment(direct_source, direct_pin) == {},
            "pinned direct subscription transport was not accepted",
        )
        try:
            producer.trusted_proxy_environment(direct_source, "f" * 64)
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED",
                "changed direct-transport pin was not fail-closed",
            )
        else:
            raise AssertionError("unbound direct subscription transport was accepted")
        partial_proxy_source = dict(direct_source)
        partial_proxy_source["HTTP_PROXY"] = "http://proxy.invalid:8080"
        try:
            producer.trusted_proxy_environment(partial_proxy_source, direct_pin)
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED",
                "partial transport proxy was not fail-closed",
            )
        else:
            raise AssertionError("partial transport proxy was accepted")

        gemini_bundle_source = fixture / "gemini-bundle-source"
        gemini_bundle_source.mkdir()
        gemini_launcher = gemini_bundle_source / "cli.js"
        gemini_launcher_content = b"// pinned Gemini launcher\n"
        gemini_launcher.write_bytes(gemini_launcher_content)
        gemini_runtime_source = fixture / "gemini-runtime-source"
        gemini_runtime_content = b"pinned Gemini runtime\n"
        gemini_runtime_source.write_bytes(gemini_runtime_content)
        gemini_home = fixture / "gemini-review-home"
        gemini_home.mkdir()
        gemini_policy = gemini_home / "deny-all.toml"
        gemini_policy.write_text("# deny all\n", encoding="utf-8")
        exact_gemini_prompt = "exact review packet — bytes must survive\n"
        observed_gemini_calls = []

        @contextlib.contextmanager
        def fake_gemini_home(_source):
            yield gemini_home, gemini_policy

        def fake_gemini_run(command, **kwargs):
            if command[-1] == "--help":
                help_text = " ".join(producer.GEMINI_REQUIRED_CLI_FLAGS).encode()
                return subprocess.CompletedProcess(command, 0, help_text, b"")
            observed_gemini_calls.append((list(command), kwargs["input"]))
            session = command[command.index("--session-id") + 1]
            requested_model = command[command.index("--model") + 1]
            events = b"\n".join((
                json.dumps({
                    "type": "init", "session_id": session,
                    "model": requested_model,
                }).encode(),
                json.dumps({
                    "type": "result", "status": "success",
                    "content": json.dumps(clean_verdict()),
                }).encode(),
            )) + b"\n"
            return subprocess.CompletedProcess(command, 0, events, b"")

        original_bundle = producer.trusted_gemini_bundle
        original_runtime = producer.trusted_executable
        original_gemini_home = producer.gemini_transport_home
        original_run = producer.run_bounded_process
        try:
            producer.trusted_gemini_bundle = lambda *_args: (
                gemini_launcher, "a" * 64,
                [("cli.js", gemini_launcher_content)],
            )
            producer.trusted_executable = lambda *_args: (
                gemini_runtime_source, "b" * 64, gemini_runtime_content,
            )
            producer.gemini_transport_home = fake_gemini_home
            producer.run_bounded_process = fake_gemini_run
            gemini_report, gemini_session, gemini_model = (
                producer.run_gemini_review(
                    exact_gemini_prompt,
                    executable=str(gemini_launcher),
                    runtime=str(gemini_runtime_source),
                    model="gemini-2.5-pro",
                    source_env={
                        "PATH": os.environ.get("PATH", ""),
                        "HOME": str(gemini_home),
                    },
                    expected_executable_sha256="a" * 64,
                    expected_runtime_sha256="b" * 64,
                    expected_proxy_sha256=producer.sha256_bytes(b"\n"),
                )
            )
        finally:
            producer.trusted_gemini_bundle = original_bundle
            producer.trusted_executable = original_runtime
            producer.gemini_transport_home = original_gemini_home
            producer.run_bounded_process = original_run
        check(
            gemini_report == clean_verdict()
            and gemini_session
            and gemini_model == "gemini-2.5-pro",
            "Gemini stdin transport did not return the closed review report",
        )
        check(
            len(observed_gemini_calls) == 1
            and observed_gemini_calls[0][0][
                observed_gemini_calls[0][0].index("--prompt") + 1
            ] == ""
            and observed_gemini_calls[0][1]
            == exact_gemini_prompt.encode("utf-8")
            and producer.sha256_bytes(observed_gemini_calls[0][1])
            == producer.sha256_bytes(exact_gemini_prompt.encode("utf-8")),
            "Gemini did not receive the exact prompt bytes through stdin",
        )

        hostile_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(fixture / "home"),
            "CODEX_HOME": str(review_codex_home),
            "OPENAI_API_KEY": "[REDACTED]",
            "GITHUB_TOKEN": "[REDACTED]",
            "AWS_SECRET_ACCESS_KEY": "[REDACTED]",
            "ITD_PAID_REVIEW_CONSENT": "1",
            "HTTP_PROXY": "http://proxy.invalid:8080",
            "HTTPS_PROXY": "http://proxy.invalid:8080",
        }
        child_env = producer.reviewer_environment(hostile_env)
        check("PATH" in child_env and "CODEX_HOME" in child_env,
              "host transport environment is unusable")
        check(
            not any("PROXY" in key.upper() for key in child_env),
            "reviewer inherited a caller-controlled proxy",
        )
        check(not any(
            marker in key.upper()
            for key in child_env
            for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CONSENT")
        ), "reviewer environment contains credentials or paid consent")
        with producer.transport_home(hostile_env) as isolated_home:
            isolated_home_path = Path(isolated_home)
            check(
                sorted(path.name for path in isolated_home_path.iterdir())
                == ["auth.json"],
                "transport home inherited config, cache, or history",
            )
            check(
                isolated_home_path != review_codex_home
                and (isolated_home_path / "auth.json").read_text(encoding="utf-8")
                == json.dumps(subscription_auth),
                "transport auth was not copied into a fresh private home",
            )
        check(not isolated_home_path.exists(), "ephemeral transport home survived review")
        api_auth = dict(subscription_auth)
        api_auth.update({"auth_mode": "apikey", api_key_field: "x"})
        (review_codex_home / "auth.json").write_text(
            json.dumps(api_auth), encoding="utf-8"
        )
        try:
            with producer.transport_home(hostile_env):
                raise AssertionError("API auth entered free reviewer transport")
        except producer.FreeReviewError:
            pass
        checks += 1
        (review_codex_home / "auth.json").write_text(
            json.dumps(subscription_auth), encoding="utf-8"
        )

        machine_value = json.loads(machine.read_text(encoding="utf-8"))
        for field in (
            "baseCommit", "reviewedTree", "diffHash",
            "scopeContractHash", "acceptanceContractHash",
        ):
            altered = copy.deepcopy(machine_value)
            altered["candidate"][field] = (
                "f" * 40 if field in {"baseCommit", "reviewedTree"} else "f" * 64
            )
            altered_path = fixture / f"machine-{field}.json"
            altered_path.write_text(json.dumps(altered), encoding="utf-8")
            try:
                producer.freeze_packet(
                    root=repo, base_commit=base,
                    repository="hihol-labs/idea-to-deploy",
                    pull_request=177, expected_head_sha="5" * 40,
                    scope_file=scope,
                    acceptance_file=acceptance, machine_receipt=altered_path,
                )
            except producer.FreeReviewError:
                pass
            else:
                raise AssertionError(f"machine evidence with foreign {field} was accepted")
            checks += 1

        producer_private = raw_private_key()
        app_private = raw_private_key()
        issued = "2026-08-01T18:30:00Z"
        phase_one = producer.phase_one_receipt(
            packet=packet,
            prompt=prompt,
            report=clean_verdict(),
            maker={"provider": "openai-codex", "model": "gpt-5.6-sol",
                   "session": "maker-session-current"},
            reviewer={"provider": "openai-subscription", "model": "gpt-5.6-terra",
                      "session": "fresh-thread-123",
                      "transportExecutableSha256": "5" * 64},
            attempts=[{"provider": "openai-subscription", "status": "PASSED"}],
            isolation=producer.required_isolation(),
            key_id="free-reviewer-2026-08",
            private_key=producer_private,
            issued_at=issued,
        )
        verified_one = producer.verify_phase_one(
            phase_one, {"free-reviewer-2026-08": public_key(producer_private)}
        )
        check(verified_one["status"] == "PASSED", "phase-one receipt is invalid")
        check(verified_one["candidate"]["tree"] == tree,
              "phase-one receipt lost the exact candidate")
        check(verified_one["target"] == packet["target"],
              "phase-one receipt lost the exact PR target")
        check(verified_one["producerId"] == "itd-free-reviewer-producer-v1",
              "phase-one receipt lacks a scoped producer identity")
        check(
            verified_one["attempts"]
            == [{"provider": "openai-subscription", "status": "PASSED"}],
            "phase-one receipt lost the signed attempt ledger",
        )
        quorum_reviewers = [
            {"provider": "openai-subscription", "model": "gpt-5.6-terra",
             "session": "fresh-quorum-openai",
             "transportExecutableSha256": "5" * 64},
            {"provider": "anthropic-subscription", "model": "claude-opus",
             "session": "fresh-quorum-anthropic",
             "transportExecutableSha256": "6" * 64},
        ]
        quorum_reviews = [
            {"reviewer": reviewer, "report": clean_verdict()}
            for reviewer in quorum_reviewers
        ]
        quorum_prompt = producer.quorum_prompt_artifact(
            packet, quorum_reviews, {
                "openai-subscription": prompt,
                "anthropic-subscription": prompt,
            },
        )
        quorum_phase_one = producer.phase_one_receipt(
            packet=packet, prompt=quorum_prompt, report=clean_verdict(),
            maker={"provider": "openai-codex", "model": "gpt-5.6-sol",
                   "session": "maker-session-current"},
            reviewer=quorum_reviewers[0], reviewers=quorum_reviewers,
            attempts=[
                {"provider": "openai-subscription", "status": "PASSED"},
                {"provider": "anthropic-subscription", "status": "PASSED"},
            ],
            isolation=producer.required_isolation(),
            key_id="free-reviewer-2026-08", private_key=producer_private,
            issued_at=issued,
        )
        try:
            producer.verify_phase_one(
                quorum_phase_one,
                {"free-reviewer-2026-08": public_key(producer_private)},
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED"
                and "non-authoritative" in exc.reason,
                "legacy quorum remained authoritative on the current route",
            )
        else:
            raise AssertionError("legacy quorum was accepted by the current verifier")
        verified_quorum = producer.verify_legacy_quorum_phase_one(
            quorum_phase_one,
            {"free-reviewer-2026-08": public_key(producer_private)},
        )
        check(
            verified_quorum["version"] == 3
            and verified_quorum["reviewers"] == quorum_reviewers,
            "phase-one receipt lost the high-risk reviewer quorum",
        )
        mutated_quorum = copy.deepcopy(quorum_phase_one["signed"])
        mutated_quorum["reviewers"].pop()
        mutated_quorum_receipt = {
            "signed": mutated_quorum,
            "signature": producer.b64url(
                Ed25519PrivateKey.from_private_bytes(producer_private).sign(
                    producer.canonical_bytes(mutated_quorum)
                )
            ),
        }
        try:
            producer.verify_phase_one(
                mutated_quorum_receipt,
                {"free-reviewer-2026-08": public_key(producer_private)},
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("under-quorum phase one verified")
        checks += 1
        try:
            producer.phase_one_receipt(
                packet=packet, prompt=prompt, report=clean_verdict(),
                maker={"provider": "anthropic", "model": "opus",
                       "session": "maker-claude-alias"},
                reviewer={"provider": "anthropic-subscription",
                          "model": "claude-opus-4-6",
                          "session": "fresh-claude-alias",
                          "transportExecutableSha256": "6" * 64},
                attempts=[
                    {"provider": "openai-subscription", "status": "UNAVAILABLE"},
                    {"provider": "anthropic-subscription", "status": "PASSED"},
                ],
                isolation=producer.required_isolation(),
                key_id="free-reviewer-2026-08",
                private_key=producer_private, issued_at=issued,
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED",
                "phase-one Anthropic alias bypass had the wrong disposition",
            )
        else:
            raise AssertionError("phase one signed an Anthropic same-family alias")

        alias_signed = copy.deepcopy(phase_one["signed"])
        alias_signed["maker"] = {
            "provider": "anthropic", "model": "opus",
            "session": "maker-claude-alias",
        }
        alias_signed["reviewer"] = {
            "provider": "anthropic-subscription",
            "model": "claude-opus-4-6",
            "session": "fresh-claude-alias",
            "transportExecutableSha256": "6" * 64,
        }
        alias_signed["attempts"] = [
            {"provider": "openai-subscription", "status": "UNAVAILABLE"},
            {"provider": "anthropic-subscription", "status": "PASSED"},
        ]
        alias_receipt = {
            "signed": alias_signed,
            "signature": producer.b64url(
                Ed25519PrivateKey.from_private_bytes(producer_private).sign(
                    producer.canonical_bytes(alias_signed)
                )
            ),
        }
        try:
            producer.verify_phase_one(
                alias_receipt,
                {"free-reviewer-2026-08": public_key(producer_private)},
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED",
                "verified Anthropic alias bypass had the wrong disposition",
            )
        else:
            raise AssertionError("re-signed Anthropic alias verified as independent")
        try:
            producer.phase_one_receipt(
                packet=packet, prompt=prompt + "\ncaller mutation",
                report=clean_verdict(),
                maker={"provider": "openai-codex", "model": "gpt-5.6-sol",
                       "session": "maker-session-current"},
                reviewer={"provider": "openai-subscription",
                          "model": "gpt-5.6-terra",
                          "session": "fresh-thread-prompt-mutation",
                          "transportExecutableSha256": "5" * 64},
                attempts=[{
                    "provider": "openai-subscription", "status": "PASSED",
                }],
                isolation=producer.required_isolation(),
                key_id="free-reviewer-2026-08",
                private_key=producer_private, issued_at=issued,
            )
        except producer.FreeReviewError as exc:
            check(
                exc.status == "UNVERIFIED",
                "mutated review prompt failed with the wrong disposition",
            )
        else:
            raise AssertionError("caller-mutated prompt produced a signed receipt")

        ledger_mutations = (
            ("missing ledger", None),
            ("skipped provider", [
                {"provider": "openai-subscription", "status": "UNAVAILABLE"},
                {"provider": "github-copilot-user", "status": "PASSED"},
            ]),
            ("non-unavailable predecessor", [
                {"provider": "openai-subscription", "status": "PASSED"},
                {"provider": "anthropic-subscription", "status": "UNAVAILABLE"},
                {"provider": "github-copilot-user", "status": "PASSED"},
            ]),
            ("non-passing terminal", [
                {"provider": "openai-subscription", "status": "UNAVAILABLE"},
                {"provider": "anthropic-subscription", "status": "UNAVAILABLE"},
                {"provider": "github-copilot-user", "status": "UNAVAILABLE"},
            ]),
            ("foreign terminal", [
                {"provider": "github-copilot-user", "status": "PASSED"},
            ]),
        )
        for label, attempts in ledger_mutations:
            altered_signed = copy.deepcopy(phase_one["signed"])
            if attempts is None:
                altered_signed.pop("attempts")
            else:
                altered_signed["attempts"] = attempts
            altered_receipt = {
                "signed": altered_signed,
                "signature": producer.b64url(
                    Ed25519PrivateKey.from_private_bytes(producer_private).sign(
                        producer.canonical_bytes(altered_signed)
                    )
                ),
            }
            try:
                producer.verify_phase_one(
                    altered_receipt,
                    {"free-reviewer-2026-08": public_key(producer_private)},
                )
            except producer.FreeReviewError:
                pass
            else:
                raise AssertionError(f"{label} verified as a closed route")
            checks += 1

        legacy_signed = copy.deepcopy(phase_one["signed"])
        legacy_signed["version"] = 1
        legacy_receipt = {
            "signed": legacy_signed,
            "signature": producer.b64url(
                Ed25519PrivateKey.from_private_bytes(producer_private).sign(
                    producer.canonical_bytes(legacy_signed)
                )
            ),
        }
        try:
            producer.verify_phase_one(
                legacy_receipt,
                {"free-reviewer-2026-08": public_key(producer_private)},
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("legacy phase-one version verified as version 2")
        checks += 1

        live = {
            "source": "github-app-api-revalidation-v1",
            "repository": "hihol-labs/idea-to-deploy",
            "pullRequest": 177,
            "baseSha": base,
            "headSha": "5" * 40,
            "headTree": tree,
            "checkSha": "1" * 40,
            "checkRunId": 99177,
            "appIntegrationId": 4242,
            "observedAt": "2026-08-01T18:31:00Z",
        }
        phase_two = producer.github_app_phase_two_receipt(
            phase_one=phase_one,
            producer_keys={"free-reviewer-2026-08": public_key(producer_private)},
            repository=live["repository"], pull_request=live["pullRequest"],
            expected_head_sha=live["headSha"], check_run_id=live["checkRunId"],
            expected_app_id=live["appIntegrationId"],
            fetch_json=lambda path: {
                f"/repos/{live['repository']}/pulls/{live['pullRequest']}": {
                    "state": "open", "mergeable": True,
                    "head": {"sha": live["headSha"],
                             "repo": {"full_name": live["repository"]}},
                    "base": {"sha": live["baseSha"],
                             "repo": {"full_name": live["repository"]}},
                    "merge_commit_sha": live["checkSha"],
                },
                f"/repos/{live['repository']}/git/commits/{live['headSha']}": {
                    "sha": live["headSha"], "tree": {"sha": live["headTree"]},
                    "parents": [{"sha": parent}],
                },
                f"/repos/{live['repository']}/commits/{live['checkSha']}": {
                    "sha": live["checkSha"],
                    "parents": [{"sha": live["baseSha"]},
                                {"sha": live["headSha"]}],
                },
                f"/repos/{live['repository']}/check-runs/{live['checkRunId']}": {
                    "id": live["checkRunId"],
                    "app": {"id": live["appIntegrationId"]},
                    "name": "ITD external review gate",
                    "head_sha": live["checkSha"],
                    "external_id": producer.sha256_bytes(
                        producer.canonical_bytes(phase_one)
                    ),
                    "status": "in_progress", "conclusion": None,
                },
            }[path],
            key_id="github-app-broker-2026-08",
            private_key=app_private,
            observed_at=live["observedAt"],
            issued_at="2026-08-01T18:31:01Z",
        )
        verified_two = producer.verify_two_phase(
            phase_two,
            producer_keys={"free-reviewer-2026-08": public_key(producer_private)},
            app_keys={"github-app-broker-2026-08": public_key(app_private)},
            now=dt.datetime(2026, 8, 1, 18, 31, 2, tzinfo=dt.timezone.utc),
        )
        check(verified_two["status"] == "PASSED", "two-phase receipt is invalid")
        check(verified_two["live"] == live, "live coordinates are not exact")

        rejected_inputs = [
            ("inherited context", {
                **producer.required_isolation(), "inheritedContext": True,
            }, clean_verdict(), "fresh-thread-123"),
            ("same session", producer.required_isolation(), clean_verdict(),
             "maker-session-current"),
            ("review finding", producer.required_isolation(), {
            "verdict": "BLOCKED",
            "findings": [{
                "severity": "important", "confidence": "high",
                "category": "missing-guard", "file": "service.py", "line": 2,
                "summary": "A required guard is absent.",
            }],
            "unverified": [],
            }, "fresh-thread-123"),
            ("unverified review", producer.required_isolation(), {
                "verdict": "PASSED", "findings": [],
                "unverified": ["runtime behavior"],
            }, "fresh-thread-123"),
        ]
        for label, isolation, report, reviewer_session in rejected_inputs:
            try:
                producer.phase_one_receipt(
                    packet=packet, prompt=prompt, report=report,
                    maker={"provider": "openai-codex", "model": "gpt-5.6-sol",
                           "session": "maker-session-current"},
                    reviewer={"provider": "openai-subscription",
                              "model": "gpt-5.6-terra",
                              "session": reviewer_session,
                              "transportExecutableSha256": "5" * 64},
                    attempts=[{
                        "provider": "openai-subscription", "status": "PASSED",
                    }],
                    isolation=isolation, key_id="free-reviewer-2026-08",
                    private_key=producer_private, issued_at=issued,
                )
            except producer.FreeReviewError:
                pass
            else:
                raise AssertionError(f"{label} produced a signed phase one")
            checks += 1

        try:
            producer.phase_one_receipt(
                packet=packet, prompt=prompt, report=clean_verdict(),
                maker={"provider": "openai-codex", "model": "gpt-5.6-sol",
                       "session": "maker-session-current"},
                reviewer={"provider": "openai-subscription",
                          "model": " gpt-5.6-sol ",
                          "session": "fresh-padded-model",
                          "transportExecutableSha256": "5" * 64},
                attempts=[{
                    "provider": "openai-subscription", "status": "PASSED",
                }],
                isolation=producer.required_isolation(),
                key_id="free-reviewer-2026-08",
                private_key=producer_private, issued_at=issued,
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError(
                "whitespace-padded same reviewer model produced phase one"
            )
        checks += 1

        padded_signed = copy.deepcopy(phase_one["signed"])
        padded_signed["reviewer"]["model"] = " gpt-5.6-sol "
        padded_signed["reviewer"]["session"] = "fresh-padded-model"
        padded_receipt = {
            "signed": padded_signed,
            "signature": producer.b64url(
                Ed25519PrivateKey.from_private_bytes(producer_private).sign(
                    producer.canonical_bytes(padded_signed)
                )
            ),
        }
        try:
            producer.verify_phase_one(
                padded_receipt,
                {"free-reviewer-2026-08": public_key(producer_private)},
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError(
                "re-signed whitespace-padded same model verified as independent"
            )
        checks += 1

        forged = copy.deepcopy(phase_one)
        forged["signature"] = "A" * 86
        try:
            producer.verify_phase_one(
                forged, {"free-reviewer-2026-08": public_key(producer_private)}
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("forged signature reached a successful phase one")
        checks += 1

        base_responses = {
            f"/repos/{live['repository']}/pulls/{live['pullRequest']}": {
                "state": "open", "mergeable": True,
                "head": {"sha": live["headSha"],
                         "repo": {"full_name": live["repository"]}},
                "base": {"sha": live["baseSha"],
                         "repo": {"full_name": live["repository"]}},
                "merge_commit_sha": live["checkSha"],
            },
            f"/repos/{live['repository']}/git/commits/{live['headSha']}": {
                "sha": live["headSha"], "tree": {"sha": live["headTree"]},
                "parents": [{"sha": parent}],
            },
            f"/repos/{live['repository']}/commits/{live['checkSha']}": {
                "sha": live["checkSha"],
                "parents": [{"sha": live["baseSha"]}, {"sha": live["headSha"]}],
            },
            f"/repos/{live['repository']}/check-runs/{live['checkRunId']}": {
                "id": live["checkRunId"], "app": {"id": live["appIntegrationId"]},
                "name": "ITD external review gate", "head_sha": live["checkSha"],
                "external_id": producer.sha256_bytes(
                    producer.canonical_bytes(phase_one)
                ),
                "status": "in_progress", "conclusion": None,
            },
        }
        replay_fetches = 0

        def replay_fetch(_path):
            nonlocal replay_fetches
            replay_fetches += 1
            raise AssertionError("foreign target reached GitHub lookup")

        try:
            producer.github_app_phase_two_receipt(
                phase_one=phase_one,
                producer_keys={
                    "free-reviewer-2026-08": public_key(producer_private)
                },
                repository=live["repository"],
                pull_request=live["pullRequest"] + 1,
                expected_head_sha=live["headSha"],
                check_run_id=live["checkRunId"],
                expected_app_id=live["appIntegrationId"],
                fetch_json=replay_fetch,
                key_id="github-app-broker-2026-08",
                private_key=app_private,
                observed_at=live["observedAt"],
                issued_at="2026-08-01T18:31:01Z",
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("phase one replayed onto another pull request")
        check(replay_fetches == 0, "foreign PR target reached live revalidation")

        response_mutations = (
            ("foreign PR base", next(iter(base_responses)),
             ("base", "sha"), "2" * 40),
            ("foreign PR head", next(iter(base_responses)),
             ("head", "sha"), "3" * 40),
            ("foreign head tree", f"/repos/{live['repository']}/git/commits/{live['headSha']}",
             ("tree", "sha"), "4" * 40),
            ("wrong merge parent", f"/repos/{live['repository']}/commits/{live['checkSha']}",
             ("parents", 0, "sha"), "2" * 40),
            ("foreign App", f"/repos/{live['repository']}/check-runs/{live['checkRunId']}",
             ("app", "id"), 9999),
        )
        for label, path, key_path, bad_value in response_mutations:
            responses = copy.deepcopy(base_responses)
            target = responses[path]
            for key in key_path[:-1]:
                target = target[key]
            target[key_path[-1]] = bad_value
            try:
                producer.github_app_phase_two_receipt(
                    phase_one=phase_one,
                    producer_keys={
                        "free-reviewer-2026-08": public_key(producer_private)
                    },
                    repository=live["repository"],
                    pull_request=live["pullRequest"],
                    expected_head_sha=live["headSha"],
                    check_run_id=live["checkRunId"],
                    expected_app_id=live["appIntegrationId"],
                    fetch_json=lambda fetch_path, value=responses: value[fetch_path],
                    key_id="github-app-broker-2026-08",
                    private_key=app_private,
                    observed_at=live["observedAt"],
                    issued_at="2026-08-01T18:31:01Z",
                )
            except producer.FreeReviewError:
                pass
            else:
                raise AssertionError(f"{label} was countersigned")
            checks += 1

        stale_time = copy.deepcopy(phase_two)
        stale_time["signed"]["live"]["observedAt"] = "2026-08-01T17:00:00Z"
        try:
            producer.verify_two_phase(
                stale_time,
                producer_keys={"free-reviewer-2026-08": public_key(producer_private)},
                app_keys={"github-app-broker-2026-08": public_key(app_private)},
                now=dt.datetime(2026, 8, 1, 18, 31, 2, tzinfo=dt.timezone.utc),
            )
        except producer.FreeReviewError:
            pass
        else:
            raise AssertionError("stale live observation remained valid")
        checks += 1

    # --- redaction is not a finding (route findings r33-r35, retro R1) ----
    # The reviewer gets the SCRUBBED text; only a detector hit refuses.
    noreply = "maintainer@" + "users.noreply.github.com"
    manifest = '{"author": {"email": "' + noreply + '"}}\n'
    safe = producer._safe_review_text(manifest.encode("utf-8"), "manifest")
    check("[REDACTED-EMAIL]" in safe and "noreply" not in safe,
          "a contact address is redacted, not a reason to refuse the route")
    check('"author"' in safe,
          "the surrounding candidate text still reaches the reviewer")

    # Neutralised side (S6): a pattern-known credential is REDACTED by
    # scrub(), the reviewer receives the redacted text, and the route
    # proceeds — refusing on the raw form over-refuses (detection runs on
    # the scrubbed text, matching the broker and build_candidate routes).
    # Prefixes are assembled at runtime so this file does not read as a leak
    # to the very scrubber whose diff it passes through.
    assign = "tok" + "en" + ' = "'
    for label, payload, raw_marker in (
        ("openai-style key", assign + "s" + "k-" + "a" * 40 + '"\n',
         "k-" + "a" * 40),
        ("aws access key", assign + "AK" + "IA" + "B" * 16 + '"\n',
         "IA" + "B" * 16),
        ("high-entropy blob", assign + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3"
                                        "zA5bC7dE9fG1hJ3kL5mN7pQ9rS1tU3vW5x"
                                        '"\n',
         "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3"),
    ):
        safe = producer._safe_review_text(
            payload.encode("utf-8"), "candidate diff"
        )
        check(raw_marker not in safe and "[REDACTED" in safe,
              f"{label} was not neutralised before reaching the reviewer")

    # fail-closed side: a credential the scrubber cannot neutralise refuses.
    # The scrub() bare-value pattern stops at '#' ([^\s#;,]), the residual
    # detector does not ([^ \t\r\n"'&]) — a literal password containing '#'
    # is exactly the gap where only clean-text detection stands between the
    # credential and the reviewer.
    literal = "pass" + "word" + "=abcd#efgh2026\n"
    try:
        producer._safe_review_text(literal.encode("utf-8"), "candidate diff")
    except producer.FreeReviewError:
        checks += 1
    else:
        raise AssertionError(
            "unneutralisable literal credential did not block the route")

    # --- whitespace-split credential (independent route finding r2) --------
    # A credential split by intra-line spaces evades the contiguous patterns;
    # before R1 it escaped only when nothing else was redactable (any contact
    # in the same candidate blocked the whole text by accident). Detection
    # now collapses per-line whitespace, so the composite blocks directly.
    split_key = "AK" + "IA " + "IOSF " + "ODNN " + "7EXA " + "MPLE"
    composite = ('contact = "maintainer@' + 'users.noreply.github.com"\n'
                 'key = "' + split_key + '"\n')
    try:
        producer._safe_review_text(composite.encode("utf-8"), "candidate diff")
    except producer.FreeReviewError:
        checks += 1
    else:
        raise AssertionError(
            "whitespace-split credential + redactable contact passed")
    try:
        producer._safe_review_text(
            ('key = "' + split_key + '"\n').encode("utf-8"), "candidate diff")
    except producer.FreeReviewError:
        checks += 1
    else:
        raise AssertionError("whitespace-split credential alone passed")
    # negative control: ordinary spaced prose must not trip the collapsed
    # detection (collapse is line-scoped and detection-only)
    benign = ("# AKIA prefix mentioned in prose, then words\n"
              "value = compute(a, b)  # spaced call, no credential\n")
    check(producer._safe_review_text(benign.encode("utf-8"), "diff") == benign,
          "benign spaced text does not trip collapsed detection")

    # the smuggling shape that defeated the earlier safe-reference attempt:
    # a secret in front of a public no-reply suffix. The historical bug was
    # RESTORATION — an email-shaped safe reference returned the raw key to
    # the outgoing text. The invariant is that the key never reaches the
    # reviewer: scrub() must neutralise it before egress (S6: detection runs
    # on the scrubbed text, so an unneutralised key still refuses the route).
    smuggled = ('contact = "' + "s" + "k-ant-api03-" + "A" * 80
                + '@users.noreply.github.com"\n')
    safe = producer._safe_review_text(smuggled.encode("utf-8"), "candidate diff")
    check("k-ant-api03-" not in safe and "A" * 80 not in safe
          and "[REDACTED" in safe,
          "a secret hidden in a no-reply address reached the reviewer text")

    # --- full route in the redacted regime (review finding, 2026-08-10) ----
    # Before R1 the scrubber was fail-closed, so packet['diff'] was always
    # byte-identical to the raw candidate. R1 makes packet['diff'] scrubbed;
    # this proves the whole freeze_packet route stays coherent when the shown
    # text differs from the raw candidate identity. Contract the asserts pin:
    # `candidate.diffSha256` is the RAW candidate identity (the verification
    # loop reconstructs the exact git diff and compares against it — never a
    # scrubbed-text hash), while `packet['diff']` is the scrubbed text the
    # reviewer sees, carried verbatim inside the signed packet so the exact
    # shown bytes stay auditable without a separate hash.
    with tempfile.TemporaryDirectory(prefix="itd-free-review-redact-") as raw2:
        fx = Path(raw2)
        repo2 = fx / "repo"
        repo2.mkdir()
        shell(["git", "init", "-q"], repo2)
        shell(["git", "config", "user.name", "ITD Redact Test"], repo2)
        shell(["git", "config", "user.email", "review@invalid"], repo2)
        (repo2 / "service.py").write_text(
            "def decision():\n    return 'old'\n", encoding="utf-8")
        shell(["git", "add", "service.py"], repo2)
        shell(["git", "commit", "-qm", "base"], repo2)
        base2 = shell(["git", "rev-parse", "HEAD"], repo2)
        (repo2 / "branch.py").write_text("BRANCH = True\n", encoding="utf-8")
        shell(["git", "add", "branch.py"], repo2)
        shell(["git", "commit", "-qm", "branch parent"], repo2)
        parent2 = shell(["git", "rev-parse", "HEAD"], repo2)
        # a redactable public contact detail in the candidate diff
        contact = "owner" + "@" + "example.com"
        (repo2 / "service.py").write_text(
            "def decision():\n"
            f"    # maintainer: {contact}\n"
            "    return 'reviewed'\n",
            encoding="utf-8")
        shell(["git", "add", "service.py"], repo2)
        tree2 = shell(["git", "write-tree"], repo2)
        scope2, acceptance2, machine2 = write_inputs(fx, repo2, parent2, tree2)

        redacted_packet = producer.freeze_packet(
            root=repo2, base_commit=base2,
            repository="hihol-labs/idea-to-deploy", pull_request=None,
            expected_head_sha=None, scope_file=scope2,
            acceptance_file=acceptance2, machine_receipt=machine2,
        )
        # candidate.diffSha256 binds the base..cached diff (freeze_packet
        # uses base_commit, not the head parent, for the candidate identity)
        raw_diff = subprocess.run(
            ["git", "diff", "--cached", "--binary", "--full-index",
             "--no-ext-diff", base2, "--"], cwd=repo2,
            capture_output=True, timeout=30, check=True,
        ).stdout
        # identity hash stays the RAW candidate (what the verification loop
        # reconstructs and compares), untouched by scrubbing
        check(redacted_packet["candidate"]["diffSha256"]
              == __import__("hashlib").sha256(raw_diff).hexdigest(),
              "diffSha256 stays the raw candidate identity under redaction")
        # the reviewer sees the scrubbed text, not the raw contact
        check("[REDACTED-EMAIL]" in redacted_packet["diff"]
              and contact not in redacted_packet["diff"],
              "the shown diff is scrubbed while the route still completes")
        # the shown text is auditable: it is carried verbatim in the packet
        # and the prompt is deterministic from that packet
        check(producer.review_prompt(redacted_packet)
              == producer.review_prompt(redacted_packet)
              and redacted_packet["diff"]
              in producer.review_prompt(redacted_packet),
              "the scrubbed shown text is embedded verbatim in the prompt")

    # --- S9-U1: an already-committed candidate must be routable --------
    with tempfile.TemporaryDirectory() as raw:
        fixture = Path(raw)
        repo = fixture / "repo"
        repo.mkdir()
        base, parent, tree = git_fixture(repo)
        scope, acceptance, machine = write_inputs(fixture, repo, parent, tree)
        # Freeze the staged packet FIRST, then commit the very same index, so
        # the two modes can be compared on one repository rather than on two
        # look-alike fixtures.
        staged_before = producer.freeze_packet(
            root=repo, base_commit=base,
            repository="hihol-labs/idea-to-deploy", pull_request=None,
            expected_head_sha=None, scope_file=scope,
            acceptance_file=acceptance, machine_receipt=machine,
        )
        # Commit the exact staged candidate: index and HEAD tree now agree, and
        # `git diff --cached HEAD` is empty by construction.
        shell(["git", "commit", "-qm", "candidate"], repo)
        head = shell(["git", "rev-parse", "HEAD"], repo)
        head_tree = shell(["git", "rev-parse", "HEAD^{tree}"], repo)

        try:
            producer.freeze_packet(
                root=repo, base_commit=base,
                repository="hihol-labs/idea-to-deploy", pull_request=None,
                expected_head_sha=None, scope_file=scope,
                acceptance_file=acceptance, machine_receipt=machine,
            )
        except producer.FreeReviewError as exc:
            check("empty" in exc.reason,
                  "staged mode on a committed candidate failed for a new reason")
        else:
            raise AssertionError(
                "staged mode accepted a committed candidate with an empty "
                "machine diff"
            )

        committed = producer.freeze_packet(
            root=repo, base_commit=base,
            repository="hihol-labs/idea-to-deploy", pull_request=None,
            expected_head_sha=None, scope_file=scope,
            acceptance_file=acceptance, machine_receipt=machine,
            candidate_mode="committed-head",
        )
        check(committed["candidate"]["parentCommit"] == parent,
              "committed-head did not bind HEAD's own parent")
        check(committed["candidate"]["tree"] == head_tree == tree,
              "committed-head did not bind the committed HEAD tree")
        check(committed["candidate"]["baseCommit"] == base,
              "committed-head lost the PR base")
        check(committed["candidate"]["diffBytes"] > 0,
              "committed-head produced an empty exact diff")
        check(head != parent, "fixture did not actually commit the candidate")

        # The two modes must agree on the exact candidate they describe: the
        # committed packet has to equal what staged mode froze from the very
        # same index before the commit, otherwise routing after commit would
        # review something other than what was accepted.
        check(
            staged_before["candidate"]["tree"] == committed["candidate"]["tree"]
            and staged_before["candidate"]["diffSha256"]
            == committed["candidate"]["diffSha256"]
            and staged_before["candidate"]["parentCommit"]
            == committed["candidate"]["parentCommit"]
            and staged_before["candidate"]["baseCommit"]
            == committed["candidate"]["baseCommit"],
            "committing the candidate changed the exact candidate it describes",
        )

        # A dirty index over the committed HEAD is not the committed candidate.
        (repo / "extra.py").write_text("EXTRA = 1" + chr(10), encoding="utf-8")
        shell(["git", "add", "extra.py"], repo)
        try:
            producer.freeze_packet(
                root=repo, base_commit=base,
                repository="hihol-labs/idea-to-deploy", pull_request=None,
                expected_head_sha=None, scope_file=scope,
                acceptance_file=acceptance, machine_receipt=machine,
                candidate_mode="committed-head",
            )
        except producer.FreeReviewError as exc:
            check("committed HEAD tree" in exc.reason,
                  "a staged change over committed HEAD was not rejected exactly")
        else:
            raise AssertionError(
                "committed-head accepted an index that differs from HEAD"
            )
        shell(["git", "reset", "-q", "HEAD", "--", "extra.py"], repo)
        (repo / "extra.py").unlink()

        try:
            producer.freeze_packet(
                root=repo, base_commit=base,
                repository="hihol-labs/idea-to-deploy", pull_request=None,
                expected_head_sha=None, scope_file=scope,
                acceptance_file=acceptance, machine_receipt=machine,
                candidate_mode="staged-head",
            )
        except producer.FreeReviewError as exc:
            check("invalid candidate mode" in exc.reason,
                  "an unknown candidate mode was not rejected fail-closed")
        else:
            raise AssertionError("an unknown candidate mode was accepted")

    # A merge commit has no single exact parent to bind.
    with tempfile.TemporaryDirectory() as raw:
        fixture = Path(raw)
        repo = fixture / "repo"
        repo.mkdir()
        base, parent, tree = git_fixture(repo)
        shell(["git", "commit", "-qm", "candidate"], repo)
        scope, acceptance, machine = write_inputs(fixture, repo, parent, tree)
        shell(["git", "checkout", "-q", "-b", "side", base], repo)
        (repo / "side.py").write_text("SIDE = 1" + chr(10), encoding="utf-8")
        shell(["git", "add", "side.py"], repo)
        shell(["git", "commit", "-qm", "side"], repo)
        shell(["git", "checkout", "-q", "-"], repo)
        shell(["git", "merge", "-q", "--no-ff", "-m", "merge", "side"], repo)
        try:
            producer.freeze_packet(
                root=repo, base_commit=base,
                repository="hihol-labs/idea-to-deploy", pull_request=None,
                expected_head_sha=None, scope_file=scope,
                acceptance_file=acceptance, machine_receipt=machine,
                candidate_mode="committed-head",
            )
        except producer.FreeReviewError as exc:
            check("single-parent" in exc.reason,
                  "a merge commit was not rejected as a committed candidate")
        else:
            raise AssertionError("committed-head accepted a merge commit")

    source = PRODUCER.read_text(encoding="utf-8")
    check("api.openai.com" not in source and "OPENAI_API_KEY" not in source,
          "producer contains a paid API dispatch path")
    print(json.dumps({
        "status": "PASSED",
        "checks": checks,
        "liveExternalCalls": 0,
        "paidApiCalls": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
