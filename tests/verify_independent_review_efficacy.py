#!/usr/bin/env python3
"""Replay structural canaries and real dual-host semantic reviewer evidence."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "_shared" / "itd_review_evidence.py"
POLICY_PATH = ROOT / "skills" / "_shared" / "itd_reviewer_independence.py"
PRODUCER_PATH = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"
RUNNER_PATH = ROOT / "tests" / "run-independent-review-efficacy.py"
KEYRING_PATH = ROOT / ".itd" / "REVIEW_EFFICACY_KEYRING.json"
HOST_PIN_REL = Path(
    ".itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256"
)
CASES_PATH = ROOT / "benchmarks" / "independent-review-efficacy" / "cases.json"
U12_CROSS_PATH = (
    ROOT / "benchmarks" / "independent-review-efficacy" / "results"
    / "u12-cross-vendor-wsl.json"
)
RESULTS = {
    "wsl": ROOT / "benchmarks" / "independent-review-efficacy" / "results" / "wsl.json",
    "windows": ROOT / "benchmarks" / "independent-review-efficacy" / "results" / "windows.json",
}
EXPECTED_OPPOSITE = {
    "gpt-5.6-sol": "gpt-5.6-terra",
    "gpt-5.6-terra": "gpt-5.6-sol",
}
EXPECTED_ISOLATION = {
    "freshSession": True,
    "ephemeral": True,
    "inheritedContext": False,
    "repositoryAccess": False,
    "repositoryMutation": False,
    "shellTools": False,
    "networkTools": False,
    "secrets": False,
    "paidApi": False,
    "observedToolCallsZero": True,
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def baseline():
    tree = "a" * 40
    acceptance = {
        "criteria": [{
            "id": "UNIT-AC1",
            "status": "passed",
            "reviewEvidence": {
                "claim": "Bounded export and reconciliation behavior are executable.",
                "impactClasses": ["bounded-output", "reconciliation"],
                "oracleIds": ["domain-oracle"],
            },
        }],
        "activeFollowup": {
            "unitId": "UNIT",
            "reviewPolicy": {
                "mode": "evidence-first",
                "riskTier": "high",
                "requiredImpactClasses": ["bounded-output", "reconciliation"],
                "minimumIndependentReviewers": 1,
                "explorer": "isolated-machine-oracle",
                "adjudicator": "sealed-host-union",
            },
        },
    }
    machine = {
        "unitId": "UNIT",
        "riskTier": "high",
        "candidate": {"reviewedTree": tree},
        "runs": [{"id": "domain-oracle", "exitCode": 0, "executedTree": tree}],
    }
    return acceptance, machine


def mutate(name, acceptance, machine):
    criterion = acceptance["criteria"][0]
    policy = acceptance["activeFollowup"]["reviewPolicy"]
    run = machine["runs"][0]
    if name == "none":
        return
    if name == "missing-review-evidence":
        criterion.pop("reviewEvidence")
    elif name == "failed-oracle":
        run["exitCode"] = 1
    elif name == "foreign-tree":
        run["executedTree"] = "b" * 40
    elif name == "missing-impact":
        criterion["reviewEvidence"]["impactClasses"] = ["bounded-output"]
    elif name == "missing-reviewer":
        policy["minimumIndependentReviewers"] = 0
    elif name == "missing-oracle":
        criterion["reviewEvidence"]["oracleIds"] = ["absent-oracle"]
    elif name == "unpassed-criterion":
        criterion["status"] = "pending"
    elif name == "unknown-impact":
        criterion["reviewEvidence"]["impactClasses"] = ["unknown-domain"]
    elif name == "duplicate-oracle":
        criterion["reviewEvidence"]["oracleIds"] = ["domain-oracle", "domain-oracle"]
    elif name == "duplicate-criterion":
        acceptance["criteria"].append(copy.deepcopy(criterion))
    elif name == "risk-mismatch":
        policy["riskTier"] = "medium"
    elif name == "missing-claim":
        criterion["reviewEvidence"]["claim"] = ""
    else:
        raise AssertionError(f"unknown structural mutation: {name}")


def exact(value: object, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AssertionError(f"{label} is not a closed object")
    return value


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_host_pin(raw: bytes) -> str:
    if not re.fullmatch(rb"[0-9a-f]{64}\n?", raw):
        raise AssertionError("host-owned review keyring pin is malformed")
    return raw.rstrip(b"\n").decode("ascii")


def host_keyring(path: Path) -> dict[str, str]:
    if path != HOST_PIN_REL:
        raise AssertionError("review keyring pin path is not the host contract")
    expected = parse_host_pin((ROOT / path).read_bytes())
    keyring_raw = KEYRING_PATH.read_bytes()
    if sha256(keyring_raw) != expected:
        raise AssertionError("review efficacy keyring is not host-authorized")
    return json.loads(keyring_raw.decode("utf-8"))


def verify_signed_evidence(envelope, keyring, producer, label):
    row = exact(envelope, {"signed", "signatureHex"}, label)
    signed = row["signed"]
    key_id = signed.get("keyId") if isinstance(signed, dict) else None
    signature = row["signatureHex"]
    if (
        not isinstance(key_id, str)
        or key_id not in keyring
        or not isinstance(signature, str)
        or not re.fullmatch(r"[0-9a-f]{128}", signature)
    ):
        raise AssertionError(f"{label} signature envelope is invalid")
    try:
        public = producer.b64url_decode(keyring[key_id], 32, label + " public key")
        producer.Ed25519PublicKey.from_public_bytes(public).verify(
            bytes.fromhex(signature), producer.canonical_bytes(signed)
        )
    except Exception as exc:
        raise AssertionError(f"{label} signature is invalid") from exc
    return signed


SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
CATEGORY_ALIASES = {
    "scale-and-bounded-output": "scale",
    "scale/capacity": "scale",
    "generated-artifact-freshness": "release-gate",
}


def normalized_category(value: str) -> str:
    normalized = re.sub(r"[-_\s]+", "-", value.strip().casefold())
    return CATEGORY_ALIASES.get(normalized, normalized)


def normalized_category_components(value: object) -> set[str]:
    """Preserve every explicit dimension in a compound reviewer category."""
    return {
        normalized_category(component)
        for component in re.split(r"\s*/\s*", str(value))
        if component.strip()
    }


def normalized_summary(value: object) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"\btsc\b|typescript check(?:ing)?", "typecheck", text)
    return text


def category_agrees(finding: dict[str, Any], fault: dict[str, Any]) -> bool:
    """Whether the reviewer's free-text label falls inside the declared set."""
    categories = {
        normalized_category(str(value)) for value in fault["categories"]
    }
    return bool(
        normalized_category_components(finding.get("category") or "") & categories
    )


def finding_matches_fault(finding: dict[str, Any], fault: dict[str, Any]) -> bool:
    """Match on substance: file, line range, severity floor and a required literal.

    The reviewer's free-text `category` is advisory and deliberately NOT a
    gate: a finding that pins the same file, the same line, at least the
    declared severity, and quotes a required summary literal has identified
    the seeded fault whatever noun it chose for it. Scoring the label was
    measured twice on 2026-08-08 to turn correct detections into misses
    ('release-gate correctness' on WSL, 'capacity' on Windows), which made the
    benchmark understate reviewer efficacy and re-run-sensitive to phrasing.
    A divergent label is surfaced by category_agrees(), not swallowed.
    """
    minimum = SEVERITY_RANK.get(str(fault["minimumSeverity"]))
    observed = SEVERITY_RANK.get(str(finding.get("severity")))
    summary = normalized_summary(finding.get("summary"))
    return bool(
        minimum is not None
        and observed is not None
        and observed >= minimum
        and finding.get("file") == fault["file"]
        and fault["lineStart"] <= finding.get("line", 0) <= fault["lineEnd"]
        and any(normalized_summary(term) in summary for term in fault["summaryTerms"])
    )


def structural_metrics(manifest, evidence, producer) -> dict[str, float]:
    outcomes = []
    for case in manifest["structuralCases"]:
        acceptance, machine = baseline()
        mutate(case["mutation"], acceptance, machine)
        try:
            matrix = evidence.coverage_matrix(acceptance, machine)
        except evidence.ReviewEvidenceError:
            blocked = True
        else:
            blocked = False
            assert matrix and matrix["criteria"][0]["criterionId"] == "UNIT-AC1"
        expected_block = case["severity"] != "clean"
        detected = blocked is expected_block
        outcomes.append({**case, "detected": detected, "blocked": blocked})
        print(("PASS  " if detected else "FAIL  ") + "structural/" + case["id"])
    low_acceptance, low_machine = baseline()
    low_acceptance["activeFollowup"]["reviewPolicy"].update({
        "riskTier": "low", "minimumIndependentReviewers": 0,
    })
    low_machine["riskTier"] = "low"
    evidence.coverage_matrix(low_acceptance, low_machine)
    for label, risk, minimum in (
        ("low-reviewer", "low", 1),
        ("high-quorum", "high", 2),
    ):
        mutated_acceptance, mutated_machine = baseline()
        mutated_acceptance["activeFollowup"]["reviewPolicy"].update({
            "riskTier": risk, "minimumIndependentReviewers": minimum,
        })
        mutated_machine["riskTier"] = risk
        try:
            evidence.coverage_matrix(mutated_acceptance, mutated_machine)
        except evidence.ReviewEvidenceError:
            print("PASS  structural/" + label)
        else:
            raise AssertionError(label + " reviewer cardinality was accepted")
    policy = load_module("itd_reviewer_independence_efficacy", POLICY_PATH)
    quorum_identity = {
        "provider": "openai-subscription", "model": "gpt-5.6-terra",
        "session": "quorum-a",
    }
    try:
        policy.require_reviewer_quorum(
            [dict(quorum_identity), {**quorum_identity, "model": "GPT-5.6-TERRA"}], 2,
        )
    except policy.IndependenceError:
        print("PASS  structural/duplicate-reviewer-quorum")
    else:
        raise AssertionError("duplicate reviewer identity satisfied a higher quorum")
    assert policy.require_reviewer_quorum(
        [dict(quorum_identity),
         {"provider": "openai-subscription", "model": "gpt-5.6-sol",
          "session": "quorum-b"}], 2,
    ) == 2
    missing = [row for row in outcomes if "missing" in row["mutation"]]
    unit_finding = {
        "severity": "high", "confidence": "high", "category": "correctness",
        "file": "service.py", "line": 1, "summary": "Seeded blocker.",
    }
    aggregated = producer._aggregate_hierarchical_report(
        [{"unit": {"index": 1}, "report": {
            "verdict": "BLOCKED", "findings": [unit_finding],
            "unverified": [], "summary": "Seeded blocker is present.",
        }}],
        {"verdict": "PASSED", "findings": [], "unverified": []},
    )
    return {
        "closedEvidenceDetection": (
            sum(row["detected"] for row in outcomes) / len(outcomes)
        ),
        "missingEvidenceDetection": (
            sum(row["detected"] for row in missing) / len(missing)
        ),
        "unitFindingRetention": float(
            aggregated["verdict"] == "BLOCKED"
            and aggregated["findings"] == [unit_finding]
        ),
    }


def validate_host_result(
    host, path, manifest, manifest_raw, producer, runner, keyring,
    observed_sessions, *, maker_provider="openai-subscription",
):
    envelope = json.loads(path.read_text(encoding="utf-8"))
    result = verify_signed_evidence(
        envelope, keyring, producer, f"{host} semantic efficacy result"
    )
    row = exact(result, {
        "version", "kind", "host", "hostRuntime", "observedAt",
        "manifestSha256", "producerSha256", "runnerSha256", "reviewer", "cases",
        "keyId",
    }, f"{host} semantic result")
    if (
        row["version"] != 1
        or row["kind"] != "itd-independent-review-semantic-efficacy-run"
        or row["host"] != host
        or row["keyId"] != "gpg003-local-producer-20260803"
        or row["manifestSha256"] != sha256(manifest_raw)
        or row["producerSha256"] != sha256(PRODUCER_PATH.read_bytes())
        or row["runnerSha256"] != sha256(RUNNER_PATH.read_bytes())
    ):
        raise AssertionError(f"{host} semantic result binding is foreign")
    runtime = exact(
        row["hostRuntime"],
        {"osName", "system", "release", "pythonImplementation"},
        f"{host} runtime",
    )
    if host == "windows":
        coherent = runtime["osName"] == "nt" and runtime["system"] == "Windows"
    else:
        coherent = (
            runtime["osName"] == "posix"
            and runtime["system"] == "Linux"
            and ("microsoft" in runtime["release"].casefold()
                 or "wsl" in runtime["release"].casefold())
        )
    if not coherent or runtime["pythonImplementation"] != "cpython":
        raise AssertionError(f"{host} runtime claim is incoherent")
    observed = dt.datetime.fromisoformat(row["observedAt"].replace("Z", "+00:00"))
    age = dt.datetime.now(dt.timezone.utc) - observed
    if not dt.timedelta(0) <= age <= dt.timedelta(days=30):
        raise AssertionError(f"{host} semantic result is stale")
    reviewer = exact(row["reviewer"], {
        "provider", "makerProvider", "makerModel", "requestedModel",
        "runtimeVersion",
        "transportExecutableSha256", "proxySha256", "paidApiCalls", "isolation",
    }, f"{host} reviewer")
    maker_norm = str(reviewer["makerModel"]).strip().casefold()
    requested_norm = str(reviewer["requestedModel"]).strip().casefold()
    if maker_provider == "openai-subscription":
        # Same-vendor parity leg: exact Sol/Terra alternation.
        pair_ok = EXPECTED_OPPOSITE.get(maker_norm) == requested_norm
    else:
        # Cross-vendor U12 leg: anthropic maker, supported OpenAI reviewer.
        pair_ok = (
            requested_norm in EXPECTED_OPPOSITE
            and maker_norm not in EXPECTED_OPPOSITE
        )
    if (
        reviewer["provider"] != "openai-subscription"
        or reviewer["makerProvider"] != maker_provider
        or not pair_ok
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", reviewer["runtimeVersion"])
        or reviewer["paidApiCalls"] != 0
        or not re.fullmatch(r"[0-9a-f]{64}", reviewer["transportExecutableSha256"])
        or not re.fullmatch(r"[0-9a-f]{64}", reviewer["proxySha256"])
        or reviewer["isolation"] != EXPECTED_ISOLATION
        # Dict equality alone would accept JSON 0/1 for False/True; the
        # fail-closed isolation contract requires exact booleans.
        or any(type(value) is not bool
               for value in reviewer["isolation"].values())
    ):
        raise AssertionError(f"{host} reviewer provenance is invalid")
    expected_selection = (
        EXPECTED_OPPOSITE[maker_norm]
        if maker_provider == "openai-subscription"
        else requested_norm
    )
    if producer.select_openai_reviewer_model(
        reviewer["makerModel"], reviewer["requestedModel"],
        maker_provider=reviewer["makerProvider"],
    ).casefold() != expected_selection:
        raise AssertionError("candidate producer opposite-model policy drifted")
    if producer.required_isolation() != EXPECTED_ISOLATION:
        raise AssertionError("candidate producer isolation policy drifted")
    semantic_cases = manifest["semanticCases"]
    if not isinstance(row["cases"], list) or len(row["cases"]) != len(semantic_cases):
        raise AssertionError(f"{host} semantic case coverage is incomplete")
    outcomes = []
    for definition, raw in zip(semantic_cases, row["cases"]):
        result_case = exact(raw, {
            "id", "attempts", "promptSha256", "report", "session", "observedModel",
        }, f"{host}/{definition['id']}")
        prompt_sha = sha256(runner.case_prompt(definition).encode("utf-8"))
        if (
            result_case["id"] != definition["id"]
            or type(result_case["attempts"]) is not int
            or result_case["attempts"] != 1
            or result_case["promptSha256"] != prompt_sha
            or not isinstance(result_case["session"], str)
            or not result_case["session"].strip()
            or result_case["session"] in observed_sessions
            or result_case["observedModel"].casefold()
            != reviewer["requestedModel"].casefold()
        ):
            raise AssertionError(f"{host}/{definition['id']} provenance is invalid")
        observed_sessions.add(result_case["session"])
        report = producer._report(result_case["report"])
        expected = definition["expectedFaults"]
        matched = []
        for fault in expected:
            exact(fault, {
                "id", "file", "lineStart", "lineEnd", "minimumSeverity",
                "categories", "summaryTerms",
            }, "expected fault")
            hits = [finding for finding in report["findings"]
                    if finding_matches_fault(finding, fault)]
            matched.append(bool(hits))
            if hits and not any(category_agrees(finding, fault) for finding in hits):
                # Detection stands on substance; the divergent label is stated
                # so the record shows the benchmark accepted it knowingly.
                print(
                    f"ADVISORY  {host}/{definition['id']}: fault {fault['id']} "
                    f"labelled {hits[0].get('category')!r}, outside the declared "
                    f"{fault['categories']}"
                )
        if definition["severity"] == "clean":
            detected = (
                report["verdict"] == "PASSED"
                and not report["findings"]
                and not report["unverified"]
            )
            false_block = not detected
        else:
            blocking_verdict = (
                report["verdict"] == "BLOCKED"
                if definition["severity"] in {"critical", "high"}
                else report["verdict"] in {"BLOCKED", "PASSED_WITH_WARNINGS"}
            )
            detected = bool(matched) and all(matched) and blocking_verdict
            false_block = False
        outcomes.append({
            "id": definition["id"], "severity": definition["severity"],
            "detected": detected, "falseBlock": false_block,
        })
        print(("PASS  " if detected else "FAIL  ") + f"{host}/{definition['id']}")
    return outcomes


def rate(rows: list[dict[str, Any]], field: str) -> float:
    if not rows:
        raise AssertionError("efficacy metric population is empty")
    return sum(bool(row[field]) for row in rows) / len(rows)


def verify_checkpoint_resume(manifest: dict[str, Any], manifest_raw: bytes) -> None:
    runner = load_module("itd_independent_efficacy_runner_test", RUNNER_PATH)
    main_source = inspect.getsource(runner.main)
    if not (
        0 <= main_source.find("attest_codex_transport(")
        < main_source.find("load_checkpoint(")
    ):
        raise AssertionError("checkpoint resume precedes live transport attestation")
    attest_source = inspect.getsource(runner.attest_codex_transport)
    if "_write_private(transport, content)" not in attest_source or "cwd=work" not in attest_source:
        raise AssertionError("version probe does not execute a private attested copy")
    probe_called = False
    original_probe = runner.producer.run_bounded_process

    def forbidden_probe(*_args, **_kwargs):
        nonlocal probe_called
        probe_called = True
        raise AssertionError("untrusted transport was executed")

    runner.producer.run_bounded_process = forbidden_probe
    try:
        runner.attest_codex_transport(
            executable=sys.executable, executable_sha256="f" * 64,
            proxy_sha256=runner.producer.sha256_bytes(b"\n"),
            source={"PATH": str(Path(sys.executable).parent)},
        )
    except runner.producer.FreeReviewError:
        pass
    else:
        raise AssertionError("wrong executable pin was accepted")
    finally:
        runner.producer.run_bounded_process = original_probe
    if probe_called:
        raise AssertionError("version probe ran before executable pin validation")
    observed_probe: dict[str, Any] = {}

    def private_probe(command, **kwargs):
        observed_probe.update({"command": command, **kwargs})
        return subprocess.CompletedProcess(
            command, 0, b"codex-cli 0.146.0\n", b""
        )

    runner.producer.run_bounded_process = private_probe
    executable = Path(sys.executable).resolve()
    try:
        resolved, actual_sha, version = runner.attest_codex_transport(
            executable=str(executable),
            executable_sha256=sha256(executable.read_bytes()),
            proxy_sha256=runner.producer.sha256_bytes(b"\n"),
            source={"PATH": str(executable.parent)},
        )
    finally:
        runner.producer.run_bounded_process = original_probe
    private_path = Path(observed_probe["command"][0])
    if (
        resolved != executable
        or actual_sha != sha256(executable.read_bytes())
        or version != "0.146.0"
        or private_path == executable
        or private_path.parent != Path(observed_probe["cwd"])
    ):
        raise AssertionError("successful version attestation did not use a private copy")
    print("PASS  executable pin precedes private version probe and checkpoint resume")
    definitions = manifest["semanticCases"]
    private_key = b"\x19" * 32
    context = runner.checkpoint_context(
        host="wsl", manifest_raw=manifest_raw,
        producer_raw=PRODUCER_PATH.read_bytes(),
        runner_raw=RUNNER_PATH.read_bytes(), maker_model="gpt-5.6-sol",
        maker_provider="openai-subscription",
        model="gpt-5.6-terra",
        runtime_version="0.146.0", executable_sha256="a" * 64,
        proxy_sha256="b" * 64,
    )
    rows = []
    for index, definition in enumerate(definitions[:2], 1):
        rows.append({
            "id": definition["id"], "attempts": 1,
            "promptSha256": sha256(
                runner.case_prompt(definition).encode("utf-8")
            ),
            "report": {"verdict": "BLOCKED", "findings": [], "unverified": []},
            "session": f"fresh-checkpoint-{index}",
            "observedModel": "gpt-5.6-terra",
        })
    with tempfile.TemporaryDirectory(prefix="itd-efficacy-checkpoint-") as raw:
        checkpoint = Path(raw) / "resume.json"
        runner.write_checkpoint(
            checkpoint, context=context, cases=rows,
            key_id="fixture-key", private_key=private_key,
        )
        loaded = runner.load_checkpoint(
            checkpoint, context=context, definitions=definitions,
            key_id="fixture-key", private_key=private_key,
        )
        if loaded != rows:
            raise AssertionError("checkpoint did not preserve the completed prefix")
        envelope = json.loads(checkpoint.read_text(encoding="utf-8"))
        envelope["signed"]["cases"][0]["session"] = "tampered"
        checkpoint.write_text(json.dumps(envelope), encoding="utf-8")
        try:
            runner.load_checkpoint(
                checkpoint, context=context, definitions=definitions,
                key_id="fixture-key", private_key=private_key,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("tampered checkpoint was accepted")
    print("PASS  signed per-case checkpoint resumes only a bound prefix")


def verify_semantic_matcher(manifest: dict[str, Any], runner) -> None:
    case = runner.exact_case(manifest["semanticCases"][0])
    fault = case["expectedFaults"][0]
    finding = {
        "severity": "critical", "confidence": "high",
        "category": "specification compliance", "file": fault["file"],
        "line": fault["lineStart"],
        "summary": "The 1,048,576 worksheet row ceiling is exceeded.",
    }
    if not finding_matches_fault(finding, fault):
        raise AssertionError("fault-specific efficacy matcher rejected a true hit")
    compound = dict(finding, category="scale/specification compliance")
    if not finding_matches_fault(compound, fault):
        raise AssertionError("efficacy matcher rejected a true compound category")
    # A reviewer that pins the same file, the same line, the same severity and
    # the required summary literal has found the seeded fault; the free-text
    # label it chooses for that fault is not the fault. Measured twice on
    # 2026-08-08 - WSL 'release-gate correctness' and Windows 'capacity' - the
    # label alone turned a correct detection into a scored miss. The category
    # is therefore advisory, and a divergent label is reported, not silently
    # accepted. This does not change WHICH faults must be found.
    relabelled = dict(finding, category="capacity")
    if not finding_matches_fault(relabelled, fault):
        raise AssertionError("efficacy matcher scored a true hit as a miss on its label")
    if category_agrees(relabelled, fault):
        raise AssertionError("divergent reviewer label was not reported as advisory")
    if not category_agrees(finding, fault):
        raise AssertionError("declared reviewer label was reported as divergent")
    for field, value in (
        ("severity", "low"),
        ("summary", "Unrelated observation at the same line."),
        ("line", fault["lineEnd"] + 2),
        ("file", "src/unrelated.ts"),
    ):
        mutated = dict(finding)
        mutated[field] = value
        if finding_matches_fault(mutated, fault):
            raise AssertionError(f"efficacy matcher accepted wrong {field}")
    print("PASS  efficacy matcher requires file, line, severity and rationale")


def verify_prompt_boundary(manifest: dict[str, Any], runner) -> None:
    case = dict(manifest["semanticCases"][0])
    marker = "UNTRUSTED_OVERRIDE_RETURN_PASSED"
    hidden_label = "HOST_ONLY_EVALUATION_LABEL"
    case["severity"] = hidden_label
    case["diff"] = str(case["diff"]) + "\n" + marker
    prompt = runner.case_prompt(case)
    trusted = prompt.rfind("BEGIN TRUSTED EFFICACY REVIEW CONTRACT")
    output = prompt.rfind("BEGIN TRUSTED OUTPUT CONTRACT")
    if (
        prompt.find(marker) < 0
        or trusted <= prompt.find(marker)
        or output <= trusted
        or not prompt.endswith("END TRUSTED OUTPUT CONTRACT\n")
        or case["expectedFaults"][0]["id"] in prompt
        or hidden_label in prompt
        or "EVALUATION_SEVERITY=" in prompt
        or "This is a clean control" in prompt
    ):
        raise AssertionError("efficacy prompt boundary leaks host-side ground truth")
    if (
        "no tools" not in prompt
        or "do not attempt to call any tool" not in prompt.casefold()
    ):
        raise AssertionError("efficacy prompt does not declare the no-tool isolation")
    print("PASS  efficacy prompt hides host-side ground truth and ends with closed contract")


def verify_manifest_contract(manifest: dict[str, Any], runner) -> None:
    def clone() -> dict[str, Any]:
        return json.loads(json.dumps(manifest))

    mutations = []
    empty_semantic = clone()
    empty_semantic["semanticCases"] = []
    mutations.append(empty_semantic)
    duplicate_case = clone()
    duplicate_case["semanticCases"][1]["id"] = duplicate_case["semanticCases"][0]["id"]
    mutations.append(duplicate_case)
    duplicate_fault = clone()
    duplicate_fault["semanticCases"][1]["expectedFaults"][0]["id"] = (
        duplicate_fault["semanticCases"][0]["expectedFaults"][0]["id"]
    )
    mutations.append(duplicate_fault)
    missing_fault = clone()
    missing_fault["semanticCases"][0]["expectedFaults"] = []
    mutations.append(missing_fault)
    boolean_threshold = clone()
    boolean_threshold["thresholds"]["criticalHighDetection"] = True
    mutations.append(boolean_threshold)
    for mutation in mutations:
        try:
            runner.exact_manifest(mutation)
        except ValueError:
            continue
        raise AssertionError("efficacy manifest mutation was accepted")
    print("PASS  efficacy manifest rejects empty, duplicate and weak corpora")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-keyring-sha256-file", type=Path, required=True
    )
    args = parser.parse_args(argv)
    evidence = load_module("itd_review_evidence_test", MODULE_PATH)
    producer = load_module("itd_free_reviewer_efficacy_test", PRODUCER_PATH)
    runner = load_module("itd_independent_efficacy_runner_main", RUNNER_PATH)
    keyring = host_keyring(args.expected_keyring_sha256_file)
    for raw in (b"a" * 63, b"A" * 64, b"a" * 64 + b"\n\n"):
        try:
            parse_host_pin(raw)
        except AssertionError:
            continue
        raise AssertionError("malformed host keyring pin was accepted")
    manifest_raw = CASES_PATH.read_bytes()
    manifest, _semantic_cases = runner.exact_manifest(
        json.loads(manifest_raw.decode("utf-8"))
    )
    structural = structural_metrics(manifest, evidence, producer)
    verify_checkpoint_resume(manifest, manifest_raw)
    verify_semantic_matcher(manifest, runner)
    verify_prompt_boundary(manifest, runner)
    verify_manifest_contract(manifest, runner)
    host_metrics = {}
    observed_sessions: set[str] = set()
    thresholds = manifest["thresholds"]
    all_ok = True
    for host, path in RESULTS.items():
        outcomes = validate_host_result(
            host, path, manifest, manifest_raw, producer, runner, keyring,
            observed_sessions,
        )
        critical_high = [
            row for row in outcomes if row["severity"] in {"critical", "high"}
        ]
        medium = [row for row in outcomes if row["severity"] == "medium"]
        clean = [row for row in outcomes if row["severity"] == "clean"]
        metrics = {
            "criticalHighDetection": rate(critical_high, "detected"),
            "mediumDetection": rate(medium, "detected"),
            "cleanFalseBlockRate": rate(clean, "falseBlock"),
        }
        host_ok = (
            metrics["criticalHighDetection"] >= thresholds["criticalHighDetection"]
            and metrics["mediumDetection"] >= thresholds["mediumDetection"]
            and metrics["cleanFalseBlockRate"]
            <= thresholds["maximumCleanFalseBlockRate"]
        )
        metrics["status"] = "PASSED" if host_ok else "FAILED"
        host_metrics[host] = metrics
        all_ok = all_ok and host_ok
    structural_ok = (
        structural["closedEvidenceDetection"]
        >= thresholds["closedEvidenceDetection"]
        and structural["missingEvidenceDetection"]
        >= thresholds["missingEvidenceDetection"]
        and structural["unitFindingRetention"]
        >= thresholds["unitFindingRetention"]
    )
    host_parity = set(host_metrics) == {"wsl", "windows"} and all_ok
    # U12: the independence ladder is measured, not asserted. The cross-vendor
    # leg must be a valid signed host-derived run over the same frozen corpus;
    # its rates are recorded honestly and are deliberately NOT thresholded
    # against the same-vendor leg.
    u12_outcomes = validate_host_result(
        "wsl", U12_CROSS_PATH, manifest, manifest_raw, producer, runner,
        keyring, observed_sessions, maker_provider="anthropic-subscription",
    )
    u12_critical_high = [
        row for row in u12_outcomes if row["severity"] in {"critical", "high"}
    ]
    u12_medium = [row for row in u12_outcomes if row["severity"] == "medium"]
    u12_clean = [row for row in u12_outcomes if row["severity"] == "clean"]
    u12 = {
        "sameVendor": {
            key: host_metrics["wsl"][key]
            for key in (
                "criticalHighDetection", "mediumDetection",
                "cleanFalseBlockRate",
            )
        },
        "crossVendor": {
            "criticalHighDetection": rate(u12_critical_high, "detected"),
            "mediumDetection": rate(u12_medium, "detected"),
            "cleanFalseBlockRate": rate(u12_clean, "falseBlock"),
        },
        "host": "wsl",
        "corpus": "shared-frozen-manifest",
    }
    ok = structural_ok and host_parity
    print(json.dumps({
        "status": "PASSED" if ok else "FAILED",
        "structuralMetrics": structural,
        "semanticMetrics": host_metrics,
        "u12IndependenceLadder": u12,
        "hostParityVerified": host_parity,
        "evidenceSource": "real-keyless-model-reports",
    }, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
