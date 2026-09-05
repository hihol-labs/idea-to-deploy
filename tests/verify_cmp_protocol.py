#!/usr/bin/env python3
"""Synthetic producer-shaped regression tests; never empirical Q6 evidence."""
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmarks/cmp/cmp_protocol.py"
PROTOCOL = SCRIPT.with_name("PROTOCOL.json")

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value

cmp = module("q6_instrument_test", SCRIPT)
producer = module("q6_real_producer", ROOT / "skills/_shared/itd_verification_loop.py")

def digest(value):
    return hashlib.sha256(value).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))
    return path

def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True, encoding="utf-8", timeout=20).stdout.strip()

def cli(script, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    return subprocess.run([sys.executable, "-I", "-B", str(script), *map(str, args)],
                          env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)

CONTEXT = {"vendor": "openai", "model": "gpt-6-astra", "harnessMajor": "1",
           "promptPolicyDigest": digest(b"synthetic fixed policy")}
ALIAS = "/home/hihol/projects/idea-to-deploy"
T0 = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=100)

def stamp(days):
    return (T0 + timedelta(days=days)).isoformat().replace("+00:00", "Z")

def identity(unit):
    return ["idea-to-deploy", "GOAL.json", unit, "activate-" + unit]

def machine(unit, when, verdict, inputs, tree="a" * 40):
    # Field layout follows machine() and uses actual producer seal helpers.
    candidate = {
        "repository": ALIAS, "baseCommit": "b" * 40, "reviewedTree": tree,
        "diffHash": digest(b"diff"), "scopeContractHash": digest(b"scope"),
        "acceptanceContractHash": digest(b"acceptance"), "rubricHash": digest(b"rubric"),
        "methodologyVersion": "1.103.0", "riskTier": "medium",
    }
    command = "exit 0" if verdict == "PASSED" else "exit 1"
    return producer.seal_receipt({
        "version": 1, "kind": "machine-verification", "createdAt": stamp(when),
        "unitId": unit, "riskTier": "medium", "candidate": candidate,
        "candidateDigest": producer.candidate_digest(candidate), "policySha256": digest(b"policy"),
        "producer": {"id": "itd-verification-loop", "role": "machine-verifier", "host": "fixture"},
        "producerRunId": digest((unit + stamp(when)).encode())[:32],
        "assurance": {"class": "integrity-and-process", "trustRoot": "honest-host-orchestrator",
                      "samePrincipalByzantineResistance": False},
        "declaredInputs": inputs,
        "runs": [{"id": "unit-oracle", "command": command,
                  "commandSha256": digest(command.encode()), "shell": "/bin/sh",
                  "shellSha256": digest(b"shell"), "startedAt": stamp(when), "completedAt": stamp(when),
                  "timeoutSeconds": 30, "executionMode": "isolated-staged-tree", "executedTree": tree,
                  "exitCode": 0 if verdict == "PASSED" else 1,
                  "stdoutSha256": digest(b""), "stderrSha256": digest(b"")}],
        "verdict": verdict,
    })

class ReceiptTests(unittest.TestCase):
    def test_real_producer_shape(self):
        value = machine("U1", 3, "FAILED", [])
        self.assertTrue(producer.receipt_digest_valid(value))
        cmp.receipt(value, {ALIAS})
        value["verdict"] = "PASSED"
        with self.assertRaises(cmp.ProtocolError): cmp.receipt(value, {ALIAS})

    def test_semantic_corruption_despite_valid_seal(self):
        mutations = [lambda r: r.update(runs=[]), lambda r: r.update(verdict="PASSED"),
                     lambda r: r["runs"][0].update(exitCode=True),
                     lambda r: r["runs"][0].update(executedTree="c" * 40),
                     lambda r: r.update(candidateDigest="sha256:" + "0" * 64),
                     lambda r: r["candidate"].update(reviewedTree="tree"),
                     lambda r: r.update(version=999), lambda r: r.update(createdAt="2026-01-01"),
                     lambda r: r["candidate"].update(repository="foreign")]
        for index, mutate in enumerate(mutations):
            value = machine("U1", 3, "FAILED", [])
            mutate(value)
            with self.subTest(mutation=index), self.assertRaises(cmp.ProtocolError):
                cmp.receipt(producer.seal_receipt(value), {ALIAS})

    def test_receipt_provenance_and_absent_executor(self):
        original = machine("U1", 3, "FAILED", [])
        for key in ("producer", "policySha256", "assurance"):
            value = copy.deepcopy(original)
            value.pop(key)
            with self.subTest(missing=key), self.assertRaises(cmp.ProtocolError):
                cmp.receipt(producer.seal_receipt(value), {ALIAS})
        value = copy.deepcopy(original)
        value["producerRunId"] = "invalid"
        with self.assertRaises(cmp.ProtocolError): cmp.receipt(producer.seal_receipt(value), {ALIAS})
        unavailable = copy.deepcopy(original)
        unavailable["runs"][0].update(shell="unavailable", shellSha256=digest(b""), exitCode=127)
        with self.assertRaisesRegex(cmp.ProtocolError, "missing|unavailable"):
            cmp.receipt(producer.seal_receipt(unavailable), {ALIAS})
        ordinary = copy.deepcopy(original)
        ordinary["runs"][0]["exitCode"] = 127
        cmp.receipt(producer.seal_receipt(ordinary), {ALIAS})

    def test_strict_json(self):
        for raw in [b'{"key":1,"key":2}', b'{"value":NaN}', b'{"value":Infinity}']:
            with self.subTest(raw=raw), self.assertRaises(cmp.ProtocolError):
                cmp.parse_json_bytes(raw, "fixture")

class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Q6 fixture")
        git(self.repo, "config", "user.email", "q6@example.test")
        self.script = self.repo / "benchmarks/cmp/cmp_protocol.py"
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.script)
        shutil.copyfile(PROTOCOL, self.script.with_name("PROTOCOL.json"))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "synthetic merged source")
        self.head = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.head)
        self.output = self.base / "campaign"
        self.context = write(self.output / "CONTEXT.json", CONTEXT)

    def freeze(self):
        return cli(self.script, "freeze", "--root", self.repo, "--context", self.context, "--output", self.output)

    def validate(self):
        return cli(self.script, "validate", "--campaign", self.output / "CAMPAIGN.json", "--current-context", self.context)

    def test_clock_clean_merged_source_exclusive_output(self):
        before = datetime.now(timezone.utc) - timedelta(seconds=1)
        result = self.freeze()
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.output / "CAMPAIGN.json"
        frozen = path.read_bytes()
        campaign = json.loads(frozen)
        self.assertEqual(campaign["sourceHead"], self.head)
        self.assertLessEqual(before, cmp.utc(campaign["createdAt"], "createdAt"))
        self.assertLessEqual(cmp.utc(campaign["createdAt"], "createdAt"), datetime.now(timezone.utc))
        self.assertEqual(self.validate().returncode, 0)
        self.assertNotEqual(self.freeze().returncode, 0)
        self.assertEqual(path.read_bytes(), frozen)

    def test_dirty_and_unmerged_rejected(self):
        self.script.write_bytes(self.script.read_bytes() + b"\n# dirty fixture\n")
        self.assertNotEqual(self.freeze().returncode, 0)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "unmerged fixture")
        self.assertNotEqual(self.freeze().returncode, 0)
        self.assertFalse((self.output / "CAMPAIGN.json").exists())

    def test_campaign_and_context_tamper(self):
        result = self.freeze()
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.output / "CAMPAIGN.json"
        original = json.loads(path.read_bytes())
        for key, value in [("createdAt", stamp(0)), ("sourceHead", "f" * 40), ("windowDays", 1), ("schemaVersion", 99)]:
            changed = copy.deepcopy(original)
            changed[key] = value
            write(path, changed)
            with self.subTest(key=key): self.assertNotEqual(self.validate().returncode, 0)
        write(path, original)
        for key in CONTEXT:
            changed = dict(CONTEXT)
            changed[key] = "changed"
            write(self.context, changed)
            with self.subTest(key=key): self.assertNotEqual(self.validate().returncode, 0)
        write(self.context, CONTEXT)
        self.script.write_bytes(self.script.read_bytes() + b"\n# changed instrument\n")
        self.assertNotEqual(self.validate().returncode, 0)

    def test_sha256_git_campaign_roundtrip(self):
        repo = self.base / "sha256-repo"
        repo.mkdir()
        init = subprocess.run(["git", "init", "-q", "--object-format=sha256"], cwd=repo,
                              capture_output=True, text=True, encoding="utf-8")
        if init.returncode and ("unknown hash algorithm" in init.stderr or "unknown option" in init.stderr):
            self.skipTest("Git does not support SHA-256 repositories")
        self.assertEqual(init.returncode, 0, init.stderr)
        git(repo, "config", "user.name", "Q6 fixture")
        git(repo, "config", "user.email", "q6@example.test")
        git(repo, "config", "core.autocrlf", "false")
        script = repo / "benchmarks/cmp/cmp_protocol.py"
        script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, script)
        shutil.copyfile(PROTOCOL, script.with_name("PROTOCOL.json"))
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "SHA-256 fixture")
        head = git(repo, "rev-parse", "HEAD")
        self.assertEqual(len(head), 64)
        git(repo, "update-ref", "refs/remotes/origin/main", head)
        self.repo, self.script = repo, script
        result = self.freeze()
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_noargs_quiet(self):
        result = cli(self.script)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


class EvidenceFixture:
    def __init__(self, base):
        self.base = base
        self.source = base / "source"
        self.source.mkdir()
        self.context = write(base / "CONTEXT.json", CONTEXT)
        self.protocol = PROTOCOL
        self.instrument = SCRIPT
        self.campaign = base / "CAMPAIGN.json"
        self.snapshot = base / "SNAPSHOT.json"
        self.events, self.rows = [], []
        self.snapshot_extra = {}
        self.refresh_campaign()

    def refresh_campaign(self):
        value = {"schemaVersion": 1, "protocolVersion": "q6-cmp-v1", "createdAt": stamp(0),
                 "sourceHead": "b" * 40, "windowDays": 90, "protocolSha256": digest(self.protocol.read_bytes()),
                 "instrumentSha256": digest(self.instrument.read_bytes()), "context": CONTEXT,
                 "protocolPath": "benchmarks/cmp/PROTOCOL.json", "instrumentPath": "benchmarks/cmp/cmp_protocol.py",
                 "status": "UNVALIDATED"}
        value["campaignSha256"] = digest(cmp.canonical(value))
        write(self.campaign, value)
        return value

    def unit(self, name, activation, first_at, closed, parents=(), verdict="FAILED", terminal="verified", directory=False):
        key = identity(name)
        lineage_path = f"inputs/{name}/lineage.json" if directory else f"inputs/{name}.cmp-lineage.json"
        descriptor = {"schemaVersion": 1, "identity": key, "parents": list(parents)}
        write(self.source / lineage_path, descriptor)
        input_path = f"inputs/{name}" if directory else lineage_path
        declared = producer.input_snapshot(self.source / input_path, input_path)
        if directory:
            write(self.source / input_path / "other.json", {"fixture": True})
            declared = producer.input_snapshot(self.source / input_path, input_path)
        record = machine(name, first_at, verdict, [declared])
        write(self.source / f"{name}.receipt", record)
        self.events.append({"id": key[3], "at": stamp(activation), "actor": "harness", "type": "unit",
                            "name": name, "decision": "activated", "evidence": "fixture", "ledger": key[1]})
        if closed is not None:
            self.events.append({"id": "close-" + name, "at": stamp(closed), "actor": "harness", "type": "unit",
                                "name": name, "decision": terminal, "evidence": "fixture", "ledger": key[1]})
        self.rows.append(dict(zip(("project", "ledger", "unitId", "activationEventId"), key),
                              eventsPath="events.jsonl", lineagePath=lineage_path))
        return record

    def sync(self):
        (self.source / "events.jsonl").write_bytes(b"\n".join(cmp.canonical(x) for x in self.events) + b"\n")
        inventory = [{"path": p.relative_to(self.source).as_posix(), "sha256": digest(p.read_bytes())}
                     for p in sorted(self.source.rglob("*")) if p.is_file()]
        write(self.snapshot, {"sourceInventory": inventory, "units": self.rows, **self.snapshot_extra})

    def reconcile(self):
        return cmp.reconcile(self.snapshot, self.source, self.campaign, self.protocol, self.instrument, self.context)

    def cohort(self):
        for index in range(20):
            root = f"R{index:02}"
            child = f"D{index:02}"
            self.unit(root, 1, 2, 3, verdict="PASSED")
            original = self.unit(child, 4, 5, 7, parents=[identity(root)])
            retry = copy.deepcopy(original)
            retry.update(createdAt=stamp(6), producerRunId=digest(child.encode())[:32], verdict="PASSED")
            retry["runs"][0].update(exitCode=0)
            write(self.source / f"{child}-retry.json", producer.seal_receipt(retry))
        self.sync()


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fx = EvidenceFixture(Path(self.temp.name))

    def test_first_failed_by_content_and_read_only_scoring(self):
        f = self.fx
        f.cohort()
        before = {p: p.read_bytes() for p in f.source.rglob("*") if p.is_file()}
        rows, campaign = f.reconcile()
        scores = cmp.score(rows, campaign)
        self.assertEqual(scores["status"], "UNVALIDATED")
        self.assertEqual(len(scores["scores"]), 20)
        self.assertEqual([r["cmp"] for r in scores["scores"]], [0.0] * 20)
        self.assertFalse(scores["operationalSignal"])
        self.assertEqual(scores["d3Verdict"], "NOT_RUN")
        self.assertEqual(before, {p: p.read_bytes() for p in f.source.rglob("*") if p.is_file()})

    def test_population_reports_excluded_and_later_roots(self):
        f = self.fx
        f.cohort()
        f.unit("R21", 8, 9, 10)
        f.unit("Q6-SETUP", 1, 2, 3)
        f.rows.pop()  # Preregistered exclusion still appears in the source event census.
        f.sync()
        rows, campaign = f.reconcile()
        result = cmp.score(rows, campaign)
        population = result["population"]
        self.assertEqual(population["lifecycleCycles"], 42)
        self.assertEqual(population["primaryMachineReceipts"], 62)
        self.assertEqual(population["includedCycles"], 41)
        self.assertEqual(population["cohortSize"], 20)
        self.assertEqual(population["excludedCycles"][0]["identity"][2], "Q6-SETUP")
        later = next(row for row in population["classifications"] if row["identity"][2] == "R21")
        self.assertEqual(later["reason"], "later verified root, outside fixed first20")

    def test_inventory_omission_duplicate_hash_and_unlisted_unit(self):
        f = self.fx
        f.unit("R", 1, 2, 3)
        f.sync()
        original = json.loads(f.snapshot.read_bytes())
        mutations = [lambda x: x["sourceInventory"].pop(),
                     lambda x: x["sourceInventory"].append(copy.deepcopy(x["sourceInventory"][0])),
                     lambda x: x["sourceInventory"][0].update(sha256="0" * 64),
                     lambda x: x.update(units=[]),
                     lambda x: x["units"][0].update(project="foreign"),
                     lambda x: x["units"][0].update(eventsPath="../events.jsonl")]
        for index, mutation in enumerate(mutations):
            value = copy.deepcopy(original)
            mutation(value)
            write(f.snapshot, value)
            with self.subTest(mutation=index), self.assertRaises(cmp.ProtocolError): f.reconcile()
        # Caller kind labels cannot suppress actual receipt content.
        original["sourceInventory"][0]["kind"] = "cmp-lineage-descriptor"
        write(f.snapshot, original)
        self.assertEqual(len(f.reconcile()[0]), 1)

    def test_declared_directory_and_changed_lineage(self):
        f = self.fx
        f.unit("R", 1, 2, 3, directory=True)
        f.sync()
        self.assertEqual(len(f.reconcile()[0]), 1)
        write(f.source / "inputs/R/other.json", {"changed": True})
        f.sync()  # Even a new truthful inventory cannot change the first receipt input seal.
        with self.assertRaises(cmp.ProtocolError): f.reconcile()

    def test_git_blob_is_bound_to_real_candidate(self):
        f = self.fx
        original = f.unit("R", 1, 2, 3)
        repo = f.base / "gitrepo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.name", "Q6 fixture")
        git(repo, "config", "user.email", "q6@example.test")
        path = f.rows[0]["lineagePath"]
        (repo / path).parent.mkdir(parents=True)
        shutil.copyfile(f.source / path, repo / path)
        git(repo, "add", ".")
        tree = git(repo, "write-tree")
        original["candidate"].update(reviewedTree=tree, repository=str(repo))
        original["runs"][0]["executedTree"] = tree
        original["candidateDigest"] = producer.candidate_digest(original["candidate"])
        original["declaredInputs"] = []
        write(f.source / "R.receipt", producer.seal_receipt(original))
        (f.source / path).unlink()  # Proves reading the Git blob, not live descriptor bytes.
        definition = json.loads(PROTOCOL.read_bytes())
        definition["repository"]["aliases"].append(str(repo))
        f.protocol = write(f.base / "PROTOCOL.json", definition)
        f.snapshot_extra["repositoryPath"] = str(repo)
        f.refresh_campaign()
        f.sync()
        self.assertEqual(len(f.reconcile()[0]), 1)
        f.rows[0]["lineagePath"] = "missing.json"
        f.sync()
        with self.assertRaises(cmp.ProtocolError): f.reconcile()

    def test_cycles_chronology_and_foreign_parent(self):
        f = self.fx
        f.unit("R", 1, 2, 3, parents=[identity("R")])
        f.sync()
        with self.assertRaises(cmp.ProtocolError): f.reconcile()
        descriptor = f.source / f.rows[0]["lineagePath"]
        for parents in [[identity("missing")], []]:
            write(descriptor, {"schemaVersion": 1, "identity": identity("R"), "parents": parents})
            record = machine("R", 2, "FAILED", [producer.input_snapshot(descriptor, f.rows[0]["lineagePath"])])
            write(f.source / "R.receipt", record)
            if not parents:
                f.events[-1]["at"] = stamp(.5)
            f.sync()
            with self.assertRaises(cmp.ProtocolError): f.reconcile()

    def test_first_cohort_not_replaced_and_overlap_rejected(self):
        f = self.fx
        f.cohort()
        rows, campaign = f.reconcile()
        rows_without = [r for r in rows if r["identity"] != tuple(identity("D00"))]
        later = copy.deepcopy(next(r for r in rows if r["identity"] == tuple(identity("R00"))))
        later.update(identity=tuple(identity("R21")), closed=T0 + timedelta(days=8))
        self.assertEqual(cmp.score(rows_without + [later], campaign)["status"], "INSUFFICIENT_DATA")
        next(r for r in rows if r["identity"] == tuple(identity("D00")))["parents"].append(tuple(identity("R01")))
        with self.assertRaises(cmp.ProtocolError): cmp.score(rows, campaign)

    def test_prefreeze_and_censored_exposure(self):
        f = self.fx
        f.unit("R", -1, 2, 3)
        f.sync()
        with self.assertRaises(cmp.ProtocolError): f.reconcile()
        with tempfile.TemporaryDirectory() as tmp:
            f = EvidenceFixture(Path(tmp))
            f.cohort()
            rows, campaign = f.reconcile()
            next(r for r in rows if r["identity"] == tuple(identity("D00")))["closed"] = None
            self.assertEqual(cmp.score(rows, campaign)["status"], "INSUFFICIENT_DATA")

    def test_symlink_and_path_escape_rejected(self):
        f = self.fx
        f.unit("R", 1, 2, 3)
        f.sync()
        for path in ["../escape", "/absolute", "a/../b", "C:/escape"]:
            with self.subTest(path=path), self.assertRaises(cmp.ProtocolError): cmp.source_path(f.source, path)
        link = f.source / "link.receipt"
        try:
            link.symlink_to(f.source / "R.receipt")
        except OSError:
            self.skipTest("host does not permit symlink fixtures")
        with self.assertRaises(cmp.ProtocolError): f.reconcile()


class LabelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fx = EvidenceFixture(Path(self.temp.name))
        self.fx.cohort()
        self.rows, self.campaign = self.fx.reconcile()
        self.labels = self.fx.base / "LABELS.json"
        self.owner = write(self.fx.base / "owner.json", {"ratings": [
            {"root": list(row["identity"]), "rating": index % 5}
            for index, row in enumerate(cmp.fixed_cohort(self.rows, self.campaign))]})

    def test_labels_seal_and_reveal_preserve_inputs(self):
        f = self.fx
        cmp.seal_labels(self.rows, self.campaign, f.snapshot, self.owner, self.labels)
        frozen = self.labels.read_bytes()
        result = cmp.guarded_score(self.rows, self.campaign, self.labels, f.snapshot)
        self.assertEqual(len(result["scores"]), 20)
        with self.assertRaises(cmp.ProtocolError):
            cmp.seal_labels(self.rows, self.campaign, f.snapshot, self.owner, self.labels)
        self.assertEqual(self.labels.read_bytes(), frozen)
        write(f.snapshot, {"changed": True})
        with self.assertRaises(cmp.ProtocolError): cmp.guarded_score(self.rows, self.campaign, self.labels, f.snapshot)

    def test_no_owner_labels_bool_out_of_range_duplicate_or_missing(self):
        original = json.loads(self.owner.read_bytes())
        mutations = [lambda x: x.pop("ratings"), lambda x: x["ratings"][0].update(rating=True),
                     lambda x: x["ratings"][0].update(rating=5), lambda x: x["ratings"].pop(),
                     lambda x: x["ratings"].append(x["ratings"][0])]
        for index, mutation in enumerate(mutations):
            value = copy.deepcopy(original)
            mutation(value)
            write(self.owner, value)
            with self.subTest(mutation=index), self.assertRaises(cmp.ProtocolError):
                cmp.seal_labels(self.rows, self.campaign, self.fx.snapshot, self.owner, self.labels)
            self.assertFalse(self.labels.exists())

    def test_maturity_guard_cannot_be_skipped_by_cli(self):
        self.campaign["createdAt"] = datetime.now(timezone.utc).isoformat()
        self.campaign.pop("campaignSha256")
        self.campaign["campaignSha256"] = digest(cmp.canonical(self.campaign))
        write(self.fx.campaign, self.campaign)
        with self.assertRaises(cmp.ProtocolError):
            cmp.guarded_score(self.rows, self.campaign, self.labels, self.fx.snapshot)
        result = cli(SCRIPT, "score", "--campaign", self.fx.campaign, "--current-context", self.fx.context,
                     "--snapshot", self.fx.snapshot, "--source-root", self.fx.source)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_complete_cli_seal_then_score(self):
        common = ["--campaign", self.fx.campaign, "--current-context", self.fx.context,
                  "--snapshot", self.fx.snapshot, "--source-root", self.fx.source]
        sealed = cli(SCRIPT, "seal-labels", *common, "--labels", self.owner)
        self.assertEqual(sealed.returncode, 0, sealed.stderr)
        result = cli(SCRIPT, "score", *common)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["scores"]), 20)
        write(self.fx.source / "unlisted.json", {"extra": True})
        rejected = cli(SCRIPT, "score", *common)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, "")

    def test_roots_only_forged_seal_is_rejected(self):
        roots = [list(row["identity"]) for row in cmp.fixed_cohort(self.rows, self.campaign)]
        value = {"schemaVersion": 1, "roots": roots, "campaignSha256": self.campaign["campaignSha256"],
                 "snapshotSha256": digest(self.fx.snapshot.read_bytes()),
                 "sealedAt": datetime.now(timezone.utc).isoformat()}
        value["labelsSha256"] = digest(cmp.canonical(value))
        write(self.labels, value)
        with self.assertRaises(cmp.ProtocolError):
            cmp.guarded_score(self.rows, self.campaign, self.labels, self.fx.snapshot)

if __name__ == "__main__":
    unittest.main(verbosity=1)
