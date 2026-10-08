#!/usr/bin/env python3
"""verify_graph_skill.py - Graph Lite (ADR-013): the deterministic half of /graph.

The skill /graph designs ONE explicit agent graph per task, the owner approves its exact
digest, the host runs it (Workflow tool or serial plan), every node output lands as a file
and a human closes the run. This oracle drives skills/graph/scripts/itd_graph.py through
temporary run directories only (never a live `.itd-memory/`) and pins the contract:

  1. init is deterministic (same inputs -> byte-identical graph.json) and the printed digest
     is the canonical digest of the file; validate accepts the shipped template.
  2. The pure validator rejects every forbidden shape by a stable rule id (cycle, no or two
     human terminals, a non-terminal human, a node that never reaches the human, a mutating
     or non-agent node, a prompt without the read-only clause, empty inputs, an unknown
     schema, no checker / self-checking checker / checker without an edge, dangling and
     self edges, duplicate ids, unknown roles, bad runId, empty task, wrong schemaVersion);
     `init --from` an invalid graph writes nothing.
  3. approve binds the EXACT digest: a wrong or malformed digest is refused and writes
     nothing; a change to graph.json after approval makes the approval stale and
     emit-workflow / record refuse.
  4. emit-workflow refuses without approval; with it the script starts with a pure-literal
     `export const meta`, embeds the digest, every agent node and its schema, fans each layer
     out with parallel()/agent(), never uses Date.now/Math.random/new Date, throws on a null
     node output, and (when node is installed) parses as JavaScript.
  5. emit-serial lists the layers in topological order (hunters, skeptic, synth, human).
  6. record refuses a missing node output, a foreign node, a digest mismatch and a second
     record; a good result writes nodes/<id>.md for every agent node and a receipt whose
     per-node sha256 equals the file bytes and whose digest is the approved one.
  7. close refuses before record and twice; after record it writes the human decision.
  8. Containment and integrity (independent review GRAPH-LITE-1 p3): every command refuses a run
     directory outside `.itd-memory/graph-runs/<run-id>` or behind a symbolic link; node ids with
     path separators or traversal are invalid; record refuses node outputs that break their schema
     (required field, enum, type) and a partial run, writing nothing; close and status re-verify
     the approval and every node file against the receipt (tampered, deleted, extra file).
  9. Read-only nodes are enforced (independent review GRAPH-LITE-1 p6): both emitters name the
     Explore agent type (no Edit/Write tools); approve stores the project's git state and record
     refuses a changed, new or deleted project file and a moved HEAD, while harness telemetry and
     .itd-memory/ stay outside the check; a project outside git cannot be approved.
 10. Provenance (independent review p8): emit and record refuse an approval without its human, run,
     time or tree state; status and close refuse a receipt with a foreign run, an unknown runtime,
     no timestamp or a malformed entry; NaN and Infinity are refused at parse time.
 11. SKILL.md declares the default-off contract (disable-model-invocation, explicit
     invocation, memory-write, the run directory, ADR-013, both emit modes, no Edit).

Run: sh skills/_shared/itd_py.sh tests/verify_graph_skill.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "graph" / "scripts" / "itd_graph.py"
SKILL_MD = ROOT / "skills" / "graph" / "SKILL.md"
PY = sys.executable

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  - " + detail[:600]) if detail else ""))


def run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return subprocess.run([PY, str(SCRIPT), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def rd(tmp: Path, name: str, project: str = "proj") -> Path:
    """A run directory where the run tool accepts it: <project>/.itd-memory/graph-runs/<run-id>."""
    return tmp / project / ".itd-memory" / "graph-runs" / name


def canonical_digest(obj) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def git_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})
    return env


def ensure_git(project: Path) -> None:
    """The run tool approves only inside a git work tree: give each test project one commit."""
    if (project / ".git").exists():
        return
    project.mkdir(parents=True, exist_ok=True)
    (project / "src.txt").write_text("tracked source\n", encoding="utf-8")
    for args in (["init", "-q"], ["add", "src.txt"], ["commit", "-q", "-m", "seed"]):
        subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True, env=git_env())


def init_run(tmp: Path, name: str = "run-a", project: str = "proj") -> tuple[Path, str]:
    run_dir = rd(tmp, name, project)
    ensure_git(run_dir.parent.parent.parent)
    r = run("init", str(run_dir), "--template", "module-neighbour-check",
            "--module", "packages/shared/src/billing/limits.ts", "--project", "/proj", "--task", "R-10 тарифы")
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.search(r"graphDigest: ([0-9a-f]{64})", r.stdout)
    assert m, r.stdout
    return run_dir, m.group(1)


def load(run_dir: Path) -> dict:
    return json.loads((run_dir / "graph.json").read_text(encoding="utf-8"))


def save(run_dir: Path, graph: dict) -> None:
    (run_dir / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def good_result(graph: dict, digest: str) -> dict:
    finding = {"file": "limits.ts", "line": 41, "class": "money", "severity": "high",
               "claim": "пустая валюта проходит", "evidence": "if (!amount) return", "origin": "pre-existing"}
    nodes = {}
    for n in graph["nodes"]:
        if n["kind"] != "agent":
            continue
        if n["schema"] == "findings":
            nodes[n["id"]] = {"findings": [finding], "scopeRead": ["limits.ts"]}
        elif n["schema"] == "verdicts":
            nodes[n["id"]] = {"verdicts": [{"file": "limits.ts", "line": 41, "class": "money",
                                            "claim": "пустая валюта проходит", "verdict": "confirmed",
                                            "reason": "нет проверки выше"}]}
        else:
            nodes[n["id"]] = {"findings": [dict(finding, status="confirmed")], "dropped": [],
                              "journalLine": "| {дата} | проверка по классам (/graph) | `limits.ts` | money | было до | /graph run-a | 1 |",
                              "summary": "одна подтверждённая находка"}
    return {"graphDigest": digest, "nodes": nodes}


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. init + validate
# ---------------------------------------------------------------------------

def test_init_and_validate(tmp: Path) -> tuple[Path, str]:
    run_dir, digest = init_run(tmp, "run-a")
    graph = load(run_dir)
    check("init writes graph.json for the shipped template", (run_dir / "graph.json").is_file())
    check("printed digest is the canonical digest of graph.json", canonical_digest(graph) == digest)
    r = run("digest", str(run_dir))
    check("digest command agrees", r.returncode == 0 and r.stdout.strip() == digest, r.stdout)
    r = run("validate", str(run_dir))
    check("validate accepts the template", r.returncode == 0 and f"VALID graphDigest {digest}" in r.stdout, r.stdout)
    ids = [n["id"] for n in graph["nodes"]]
    check("template has four hunters, one checker, one synthesizer and one human",
          ids == ["hunt-owner", "hunt-money", "hunt-dedup", "hunt-time", "skeptic", "synth", "human"], str(ids))
    check("every agent prompt carries the read-only clause",
          all("read-only" in n["prompt"].lower() for n in graph["nodes"] if n["kind"] == "agent"))
    other_dir = rd(tmp, "run-a", project="proj2")
    r = run("init", str(other_dir), "--template", "module-neighbour-check",
            "--module", "packages/shared/src/billing/limits.ts", "--project", "/proj", "--task", "R-10 тарифы")
    check("init is deterministic: same inputs give byte-identical graph.json",
          r.returncode == 0 and (other_dir / "graph.json").read_bytes() == (run_dir / "graph.json").read_bytes())
    r = run("init", str(run_dir), "--template", "module-neighbour-check", "--module", "x.ts")
    check("init refuses to overwrite an existing graph.json", r.returncode == 2 and "already exists" in r.stdout, r.stdout)
    r = run("init", str(rd(tmp, "run-c")), "--template", "module-neighbour-check")
    check("init without --module is refused", r.returncode == 2 and "--module" in r.stdout and not rd(tmp, "run-c").exists(), r.stdout)
    r = run("init", str(rd(tmp, "run-d")), "--template", "no-such-template", "--module", "x.ts")
    check("unknown template is refused", r.returncode == 2 and "unknown template" in r.stdout, r.stdout)
    r = run("status", str(run_dir))
    check("status after init is designed", r.returncode == 0 and '"state": "designed"' in r.stdout, r.stdout)
    return run_dir, digest


# ---------------------------------------------------------------------------
# 2. validator mutations
# ---------------------------------------------------------------------------

def mutations(base: dict) -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []

    def m(name: str, rule: str, fn) -> None:
        g = copy.deepcopy(base)
        fn(g)
        out.append((name, rule, g))

    def node(g, nid):
        return next(n for n in g["nodes"] if n["id"] == nid)

    m("cycle synth->hunt-owner", "G04", lambda g: g["edges"].append(["synth", "hunt-owner"]))
    m("no human terminal", "G05", lambda g: (g["nodes"].pop(), g.__setitem__("edges", [e for e in g["edges"] if "human" not in e])))
    m("two human terminals", "G05", lambda g: (g["nodes"].append(dict(node(g, "human"), id="human2")), g["edges"].append(["synth", "human2"])))
    m("human with an outgoing edge", "G05", lambda g: g["edges"].append(["human", "synth"]))

    def orphan(g):
        g["nodes"].append(dict(node(g, "hunt-owner"), id="orphan"))
        g["nodes"].append(dict(node(g, "hunt-owner"), id="orphan2"))
        g["edges"].append(["orphan", "orphan2"])
    m("agent branch that never reaches the human", "G05", orphan)
    m("mutating node", "G06", lambda g: node(g, "hunt-owner").__setitem__("purity", "mutating"))
    m("non-agent kind", "G06", lambda g: node(g, "hunt-owner").__setitem__("kind", "tool"))
    m("prompt without the read-only clause", "G07", lambda g: node(g, "hunt-money").__setitem__("prompt", "ищи валюту"))
    m("empty inputs", "G07", lambda g: node(g, "synth").__setitem__("inputs", []))
    m("unknown schema", "G08", lambda g: node(g, "skeptic").__setitem__("schema", "nope"))
    m("no checker node", "G09", lambda g: (node(g, "skeptic").__setitem__("role", "researcher"), node(g, "skeptic").pop("checks")))
    m("checker checks itself", "G09", lambda g: node(g, "skeptic").__setitem__("checks", ["skeptic"]))
    m("checker checks a node without an edge", "G09", lambda g: node(g, "skeptic").__setitem__("checks", ["synth"]))
    m("agent node without an outgoing edge", "G10", lambda g: g.__setitem__("edges", [e for e in g["edges"] if e[0] != "hunt-time"]))
    m("dangling edge", "G03", lambda g: g["edges"].append(["hunt-owner", "ghost"]))
    m("self edge", "G03", lambda g: g["edges"].append(["synth", "synth"]))
    m("duplicate node id", "G02", lambda g: g["nodes"].append(dict(node(g, "hunt-owner"))))
    m("unknown role", "G11", lambda g: node(g, "synth").__setitem__("role", "wizard"))
    m("human node declared mutating", "G06", lambda g: node(g, "human").__setitem__("purity", "mutating"))
    m("bad runId", "G12", lambda g: g.__setitem__("runId", "../escape"))
    m("empty task", "G12", lambda g: g.__setitem__("task", "  "))
    m("wrong schemaVersion", "G01", lambda g: g.__setitem__("schemaVersion", 2))
    m("node id with path traversal", "G02", lambda g: node(g, "hunt-owner").__setitem__("id", "../../outside"))
    m("node id with a path separator", "G02", lambda g: node(g, "hunt-money").__setitem__("id", "a/b"))
    m("missing template", "G12", lambda g: g.pop("template"))
    m("human node without a prompt", "G07", lambda g: node(g, "human").__setitem__("prompt", ""))
    m("unsupported schema keyword", "G08", lambda g: g["schemas"]["findings"].__setitem__("additionalProperties", False))
    m("schema property of an unknown type", "G08",
      lambda g: g["schemas"]["verdicts"]["properties"]["verdicts"].__setitem__("type", "list"))
    return out


def test_validator(tmp: Path, run_dir: Path) -> None:
    base = load(run_dir)
    muts = mutations(base)
    check("at least 27 negative mutations are exercised", len(muts) >= 27, str(len(muts)))
    for k, (name, rule, graph) in enumerate(muts):
        d = rd(tmp, f"mut-{k}")
        d.mkdir(parents=True)
        save(d, graph)
        r = run("validate", str(d))
        check(f"validator rejects: {name} ({rule})", r.returncode == 1 and "INVALID" in r.stdout and rule in r.stdout,
              r.stdout.strip().replace("\n", " | "))
    # init --from an invalid graph writes nothing
    bad = tmp / "bad-from.json"
    write_json(bad, muts[0][2])
    target = rd(tmp, "from-invalid")
    r = run("init", str(target), "--from", str(bad))
    check("init --from an invalid graph is refused and writes nothing",
          r.returncode == 2 and "invalid" in r.stdout and not target.exists(), r.stdout)
    good = tmp / "good-from.json"
    write_json(good, base)
    target = rd(tmp, "from-valid")
    r = run("init", str(target), "--from", str(good))
    check("init --from a valid graph takes the run-id from the directory",
          r.returncode == 0 and load(target)["runId"] == "from-valid", r.stdout)


# ---------------------------------------------------------------------------
# 3-4. approve + emit-workflow + emit-serial
# ---------------------------------------------------------------------------

def test_approve_and_emit(tmp: Path, run_dir: Path, digest: str) -> str:
    r = run("emit-workflow", str(run_dir))
    check("emit-workflow refuses without approval", r.returncode == 2 and "approve" in r.stdout, r.stdout)
    r = run("approve", str(run_dir), "--digest", "0" * 64, "--by", "owner")
    check("approve refuses a wrong digest and writes nothing",
          r.returncode == 2 and "digest mismatch" in r.stdout and not (run_dir / "approval.json").exists(), r.stdout)
    r = run("approve", str(run_dir), "--digest", "zz", "--by", "owner")
    check("approve refuses a malformed digest", r.returncode == 2 and "64-hex" in r.stdout, r.stdout)
    r = run("approve", str(run_dir), "--digest", digest, "--by", "owner", "--at", "2026-10-07T00:00:00Z")
    approval = json.loads((run_dir / "approval.json").read_text(encoding="utf-8")) if (run_dir / "approval.json").exists() else {}
    check("approve binds the exact digest and names the human",
          r.returncode == 0 and approval.get("graphDigest") == digest and approval.get("by") == "owner"
          and approval.get("at") == "2026-10-07T00:00:00Z", r.stdout)
    r = run("status", str(run_dir))
    check("status after approve is approved", '"state": "approved"' in r.stdout, r.stdout)

    r = run("emit-workflow", str(run_dir))
    js = r.stdout
    check("emit-workflow succeeds after approval", r.returncode == 0 and js.strip(), r.stdout[:300])
    check("workflow script starts with export const meta", js.startswith("export const meta = {"))
    meta_block = js[: js.index("\n}\n") + 3]
    check("meta is a pure literal (no template strings, no interpolation, no identifiers in values)",
          "`" not in meta_block and "${" not in meta_block
          and re.search(r"name: \"itd-graph-run-a\"", meta_block) is not None
          and "phases: [{ title: \"Hunt\" }, { title: \"Check\" }, { title: \"Synthesize\" }]" in meta_block, meta_block)
    check("workflow script embeds the approved digest", f'const GRAPH_DIGEST = "{digest}"' in js)
    graph = load(run_dir)
    agent_ids = [n["id"] for n in graph["nodes"] if n["kind"] == "agent"]
    check("every agent node and its prompt is embedded",
          all(f'"{i}": {{' in js and json.dumps(n["prompt"], ensure_ascii=False) in js
              for n in graph["nodes"] for i in [n["id"]] if n["kind"] == "agent"))
    check("the human node is not an agent call", '"human": {' not in js)
    nodes_m = re.search(r"const NODES = (\{.*?\n\})\nconst outputs", js, re.S)
    emitted = json.loads(nodes_m.group(1)) if nodes_m else {}
    by_id = {n["id"]: n for n in graph["nodes"]}
    check("each emitted node carries exactly its own prompt, schema, role and upstream nodes",
          sorted(emitted) == sorted(agent_ids)
          and all(emitted[i]["prompt"] == by_id[i]["prompt"]
                  and emitted[i]["schema"] == graph["schemas"][by_id[i]["schema"]]
                  and emitted[i]["role"] == by_id[i]["role"]
                  and emitted[i]["upstream"] == [s for s, d in graph["edges"] if d == i]
                  for i in agent_ids), str(sorted(emitted)))
    check("the three node schemas differ (no generic schema for every node)",
          len({json.dumps(graph["schemas"][by_id[i]["schema"]], sort_keys=True) for i in agent_ids}) == 3)
    layers_m = re.search(r"const LAYERS = (\[.*?\n\])\n", js, re.S)
    layers = json.loads(layers_m.group(1)) if layers_m else None
    check("layers are topological: hunters, then skeptic, then synth",
          layers == [["hunt-owner", "hunt-money", "hunt-dedup", "hunt-time"], ["skeptic"], ["synth"]], str(layers))
    check("fan-out uses parallel() and agent() with the node schema",
          "await parallel(layer.map(id => () =>" in js and 'agent(promptFor(id), { label: id, phase: NODES[id].phase, schema: NODES[id].schema, agentType: "Explore" })' in js)
    check("every node runs as the Explore agent type (no Edit/Write tools)", js.count('agentType: "Explore"') == 1)
    check("a null node output throws instead of passing", "returned no output" in js and "throw new Error" in js)
    check("an empty string, array or object node output throws too",
          "out === ''" in js and "Array.isArray(out) && out.length === 0" in js
          and "Object.keys(out).length === 0" in js)
    check("no wall-clock or randomness in the script",
          not re.search(r"Date\.now|Math\.random|new Date\(", js))
    check("every node schema is embedded", all(json.dumps(graph["schemas"][n["schema"]], ensure_ascii=False, indent=2).splitlines()[1] in js
                                               for n in graph["nodes"] if n["kind"] == "agent"))
    node_bin = shutil.which("node")
    if node_bin:
        wrapped = "async function __wf() {\n" + js.replace("export const meta", "const meta", 1) + "\n}\n"
        wf = tmp / "wf.check.js"
        wf.write_text(wrapped, encoding="utf-8")
        rc = subprocess.run([node_bin, "--check", str(wf)], capture_output=True, text=True)
        check("workflow script parses as JavaScript (node --check, wrapped in an async function)",
              rc.returncode == 0, rc.stderr[:400])
    else:
        check("workflow script parses as JavaScript (SKIP: node not installed)", True)

    r = run("emit-serial", str(run_dir))
    s = r.stdout
    check("emit-serial succeeds after approval", r.returncode == 0 and s.startswith("# Serial plan for graph run run-a"))
    pos = [s.find(f"### node `{i}`") for i in agent_ids]
    check("serial plan lists every agent node once and in layer order",
          all(p >= 0 for p in pos) and pos == sorted(pos) and s.count("### node `") == len(agent_ids)
          and s.find("## Terminal: `human`") > max(pos), str(pos))
    check("serial plan carries every prompt verbatim", all(n["prompt"] in s for n in graph["nodes"] if n["kind"] == "agent"))
    check("serial plan tells the operator not to skip a node", "not skipped" in s and "not recorded" in s)
    check("serial plan names the Explore agent type for every node", "subagent_type Explore" in s and "general-purpose" not in s)
    check("serial plan warns that record compares the project's git state", "refuses on any difference" in s)
    return js


# ---------------------------------------------------------------------------
# 5-6. record + close + stale approval
# ---------------------------------------------------------------------------

def test_record_and_close(tmp: Path, run_dir: Path, digest: str) -> None:
    graph = load(run_dir)
    result = good_result(graph, digest)
    agent_ids = [n["id"] for n in graph["nodes"] if n["kind"] == "agent"]

    r = run("close", str(run_dir), "--decision", "ok", "--by", "owner")
    check("close refuses before record", r.returncode == 2 and "record the run first" in r.stdout, r.stdout)

    missing = copy.deepcopy(result)
    missing["nodes"].pop("synth")
    p = tmp / "missing.json"
    write_json(p, missing)
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "workflow")
    check("record refuses a missing node output and writes nothing",
          r.returncode == 2 and "synth" in r.stdout and not (run_dir / "receipt.json").exists()
          and not (run_dir / "nodes").exists(), r.stdout)
    empty = copy.deepcopy(result)
    empty["nodes"]["skeptic"] = {}
    write_json(p, empty)
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "workflow")
    check("record treats an empty node output as missing", r.returncode == 2 and "skeptic" in r.stdout, r.stdout)
    foreign = copy.deepcopy(result)
    foreign["nodes"]["extra"] = {"x": 1}
    write_json(p, foreign)
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "workflow")
    check("record refuses a node outside the approved graph", r.returncode == 2 and "extra" in r.stdout, r.stdout)
    wrong = copy.deepcopy(result)
    wrong["graphDigest"] = "1" * 64
    write_json(p, wrong)
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "workflow")
    check("record refuses a result for another digest", r.returncode == 2 and "not the approved graph" in r.stdout, r.stdout)
    write_json(p, result)
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "sideways")
    check("record refuses an unknown runtime", r.returncode == 2 and "--runtime" in r.stdout, r.stdout)

    r = run("record", str(run_dir), "--result", str(p), "--runtime", "workflow", "--at", "2026-10-07T00:01:00Z")
    receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8")) if (run_dir / "receipt.json").exists() else {}
    check("record writes receipt.json for the approved digest and runtime",
          r.returncode == 0 and receipt.get("graphDigest") == digest and receipt.get("runtime") == "workflow"
          and receipt.get("at") == "2026-10-07T00:01:00Z", r.stdout)
    files = sorted(q.name for q in (run_dir / "nodes").glob("*.md")) if (run_dir / "nodes").is_dir() else []
    check("one markdown file per agent node", files == sorted(f"{i}.md" for i in agent_ids), str(files))
    ok = True
    for i in agent_ids:
        data = (run_dir / "nodes" / f"{i}.md").read_bytes()
        entry = receipt.get("nodes", {}).get(i, {})
        ok = ok and entry.get("sha256") == hashlib.sha256(data).hexdigest() and entry.get("bytes") == len(data)
        ok = ok and data.decode("utf-8").startswith(f"# node {i} (role ")
    check("receipt per-node sha256 and size match the node files", ok)
    check("result digest is pinned in the receipt", receipt.get("resultSha256") == canonical_digest(result))
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "workflow")
    check("a second record is refused (rerun = new directory)", r.returncode == 2 and "already exists" in r.stdout, r.stdout)
    r = run("status", str(run_dir))
    check("status after record is recorded", '"state": "recorded"' in r.stdout, r.stdout)

    r = run("close", str(run_dir), "--decision", "", "--by", "owner")
    check("close refuses an empty decision", r.returncode == 2 and not (run_dir / "decision.json").exists(), r.stdout)
    r = run("close", str(run_dir), "--decision", "первую в журнал", "--by", "owner", "--at", "2026-10-07T00:02:00Z")
    decision = json.loads((run_dir / "decision.json").read_text(encoding="utf-8")) if (run_dir / "decision.json").exists() else {}
    check("close writes the human decision bound to the digest",
          r.returncode == 0 and decision.get("decision") == "первую в журнал" and decision.get("by") == "owner"
          and decision.get("graphDigest") == digest, r.stdout)
    r = run("close", str(run_dir), "--decision", "again", "--by", "owner")
    check("a closed run is immutable", r.returncode == 2 and "immutable" in r.stdout, r.stdout)
    r = run("status", str(run_dir))
    check("status after close is closed", '"state": "closed"' in r.stdout, r.stdout)


def test_stale_approval(tmp: Path) -> None:
    run_dir, digest = init_run(tmp, "stale")
    r = run("approve", str(run_dir), "--digest", digest, "--by", "owner", "--at", "2026-10-07T00:00:00Z")
    assert r.returncode == 0, r.stdout
    graph = load(run_dir)
    graph["task"] = "изменено после утверждения"
    save(run_dir, graph)
    r = run("status", str(run_dir))
    check("a graph edit after approval shows approval-stale", '"state": "approval-stale"' in r.stdout, r.stdout)
    r = run("emit-workflow", str(run_dir))
    check("emit-workflow refuses a stale approval", r.returncode == 2 and "stale" in r.stdout, r.stdout)
    r = run("emit-serial", str(run_dir))
    check("emit-serial refuses a stale approval", r.returncode == 2 and "stale" in r.stdout, r.stdout)
    p = tmp / "stale-result.json"
    write_json(p, good_result(graph, canonical_digest(graph)))
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "serial")
    check("record refuses a stale approval even when the result matches the new graph",
          r.returncode == 2 and "stale" in r.stdout and not (run_dir / "receipt.json").exists(), r.stdout)
    r = run("approve", str(run_dir), "--digest", canonical_digest(graph), "--by", "owner", "--at", "2026-10-07T00:03:00Z")
    r2 = run("record", str(run_dir), "--result", str(p), "--runtime", "serial", "--at", "2026-10-07T00:04:00Z")
    check("re-approving the new digest unblocks record with the serial runtime",
          r.returncode == 0 and r2.returncode == 0
          and json.loads((run_dir / "receipt.json").read_text(encoding="utf-8")).get("runtime") == "serial", r.stdout + r2.stdout)
    r = run("validate", str(rd(tmp, "does-not-exist")))
    check("validate on a missing run directory is a refusal, not a crash", r.returncode == 2 and "missing" in r.stdout, r.stdout)


# ---------------------------------------------------------------------------
# 7. SKILL.md contract
# ---------------------------------------------------------------------------

def test_skill_md() -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    fm = text.split("\n---\n", 1)[0]
    check("SKILL.md is default-off: disable-model-invocation: true", "disable-model-invocation: true" in fm)
    check("SKILL.md declares explicit_invocation: true", re.search(r"^\s+explicit_invocation:\s*true", fm, re.M) is not None)
    check("SKILL.md declares side_effect: memory-write", re.search(r"^\s+side_effect:\s*memory-write", fm, re.M) is not None)
    tools = re.search(r"^allowed-tools:\s*(.+)$", fm, re.M)
    check("SKILL.md allowed-tools has no Edit (nodes never edit sources)",
          tools is not None and "Edit" not in tools.group(1).split(), tools.group(0) if tools else "no allowed-tools")
    for anchor in (".itd-memory/graph-runs/", "ADR-013", "emit-workflow", "emit-serial", "receipt.json",
                   "decision.json", "approval-stale", "itd_py.sh", "skills/graph/scripts/itd_graph.py"):
        check(f"SKILL.md mentions {anchor}", anchor in text)
    check("SKILL.md says the Workflow script is passed verbatim", "дословно" in text)
    check("SKILL.md keeps the human as the terminal node", "терминал" in text.lower() and "MUST keep the human as the terminal node" in text)


# ---------------------------------------------------------------------------
# 7. containment, schema-checked record, integrity of close/status (Sol p3 findings)
# ---------------------------------------------------------------------------

def approved_run(tmp: Path, name: str) -> tuple[Path, str, dict]:
    run_dir, digest = init_run(tmp, name)
    r = run("approve", str(run_dir), "--digest", digest, "--by", "owner", "--at", "2026-10-07T00:00:00Z")
    assert r.returncode == 0, r.stdout
    return run_dir, digest, load(run_dir)


def test_containment_and_integrity(tmp: Path) -> None:
    outside = tmp / "plain" / "run-x"
    r = run("init", str(outside), "--template", "module-neighbour-check", "--module", "x.ts")
    check("init refuses a run directory outside .itd-memory/graph-runs/",
          r.returncode == 2 and "graph-runs" in r.stdout and not outside.exists(), r.stdout)
    for cmd in ("validate", "digest", "status", "emit-workflow", "emit-serial"):
        r = run(cmd, str(outside))
        check(f"{cmd} refuses a run directory outside .itd-memory/graph-runs/", r.returncode == 2 and "graph-runs" in r.stdout, r.stdout)
    r = run("record", str(outside), "--result", str(tmp / "x.json"), "--runtime", "serial")
    check("record refuses a run directory outside .itd-memory/graph-runs/", r.returncode == 2 and "graph-runs" in r.stdout, r.stdout)
    r = run("close", str(outside), "--decision", "x", "--by", "owner")
    check("close refuses a run directory outside .itd-memory/graph-runs/", r.returncode == 2 and "graph-runs" in r.stdout, r.stdout)
    bad_name = rd(tmp, ".hidden")
    r = run("init", str(bad_name), "--template", "module-neighbour-check", "--module", "x.ts")
    check("init refuses a run directory whose name is not a run id", r.returncode == 2 and "run id" in r.stdout, r.stdout)

    real_dir, _ = init_run(tmp, "real")
    link = rd(tmp, "link")
    try:
        os.symlink(real_dir, link, target_is_directory=True)
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    if linked:
        res = tmp / "link-result.json"
        write_json(res, {"graphDigest": "0" * 64, "nodes": {}})
        commands = {
            "validate": [], "digest": [], "status": [], "emit-workflow": [], "emit-serial": [],
            "approve": ["--digest", "0" * 64, "--by", "owner"],
            "record": ["--result", str(res), "--runtime", "serial"],
            "close": ["--decision", "x", "--by", "owner"],
        }
        for cmd, extra in commands.items():
            r = run(cmd, str(link), *extra)
            check(f"{cmd} refuses a symlinked run directory", r.returncode == 2 and "symbolic link" in r.stdout, r.stdout)
        linked_runs = rd(tmp, "x", project="proj-linked").parent
        linked_runs.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(real_dir.parent, linked_runs, target_is_directory=True)
        r = run("init", str(linked_runs / "new-run"), "--module", "x.ts")
        check("init refuses a run directory under a symlinked graph-runs", r.returncode == 2 and "symbolic link" in r.stdout
              and not (real_dir.parent / "new-run").exists(), r.stdout)
        os.symlink(tmp, real_dir / "nodes", target_is_directory=True)
        r = run("status", str(real_dir))
        check("a symlinked nodes/ artifact is refused", r.returncode == 2 and "symbolic link" in r.stdout, r.stdout)
        os.unlink(real_dir / "nodes")
    else:
        check("a symlinked run directory is refused (SKIP: no symlink privilege)", True)

    run_dir, digest, graph = approved_run(tmp, "schema")
    good = good_result(graph, digest)
    p = tmp / "schema-result.json"
    cases = {
        "a missing required field": lambda res: res["nodes"]["hunt-owner"].__setitem__("findings", [{"file": "a.ts"}]),
        "a value outside the enum": lambda res: res["nodes"]["hunt-money"]["findings"][0].__setitem__("severity", "critical"),
        "a wrong type": lambda res: res["nodes"]["skeptic"].__setitem__("verdicts", "none"),
        "a string instead of an object": lambda res: res["nodes"].__setitem__("synth", "всё хорошо"),
        "a boolean where an integer is required": lambda res: res["nodes"]["hunt-time"]["findings"][0].__setitem__("line", True),
    }
    for label, mutate in cases.items():
        bad = copy.deepcopy(good)
        mutate(bad)
        write_json(p, bad)
        r = run("record", str(run_dir), "--result", str(p), "--runtime", "serial")
        check(f"record refuses a node output with {label} and writes nothing",
              r.returncode == 2 and "does not match its schema" in r.stdout
              and not (run_dir / "nodes").exists() and not (run_dir / "receipt.json").exists(), r.stdout)

    run_dir, digest, graph = approved_run(tmp, "partial")
    (run_dir / "nodes").mkdir()
    (run_dir / "nodes" / "hunt-owner.md").write_text("stale partial output\n", encoding="utf-8")
    r = run("status", str(run_dir))
    check("status reports a partial run (nodes/ without a receipt)", '"state": "partial"' in r.stdout, r.stdout)
    write_json(p, good_result(graph, digest))
    r = run("record", str(run_dir), "--result", str(p), "--runtime", "serial")
    check("record refuses to overwrite a partial run and keeps its files",
          r.returncode == 2 and "partial run" in r.stdout
          and (run_dir / "nodes" / "hunt-owner.md").read_text(encoding="utf-8") == "stale partial output\n"
          and not (run_dir / "receipt.json").exists(), r.stdout)
    leftovers = [q.name for q in run_dir.iterdir() if q.name.startswith(".")]
    check("a refused record leaves no staging directory behind", leftovers == [], str(leftovers))

    def recorded(name: str) -> tuple[Path, dict]:
        rdir, dg, gr = approved_run(tmp, name)
        write_json(p, good_result(gr, dg))
        rr = run("record", str(rdir), "--result", str(p), "--runtime", "workflow")
        assert rr.returncode == 0, rr.stdout
        return rdir, gr

    run_dir, graph = recorded("tamper")
    (run_dir / "nodes" / "skeptic.md").write_text("rewritten after the run\n", encoding="utf-8")
    r = run("status", str(run_dir))
    check("status reports a node file that differs from the receipt", '"state": "receipt-mismatch"' in r.stdout, r.stdout)
    r = run("close", str(run_dir), "--decision", "ok", "--by", "owner")
    check("close refuses a tampered node file", r.returncode == 2 and "differs from the receipt" in r.stdout
          and not (run_dir / "decision.json").exists(), r.stdout)

    run_dir, graph = recorded("deleted")
    (run_dir / "nodes" / "synth.md").unlink()
    r = run("status", str(run_dir))
    check("status reports a deleted node file", '"state": "receipt-mismatch"' in r.stdout and "synth.md is missing" in r.stdout, r.stdout)
    r = run("close", str(run_dir), "--decision", "ok", "--by", "owner")
    check("close refuses a deleted node file", r.returncode == 2 and "synth.md is missing" in r.stdout, r.stdout)

    run_dir, graph = recorded("extra")
    (run_dir / "nodes" / "injected.md").write_text("not a node of the graph\n", encoding="utf-8")
    r = run("status", str(run_dir))
    check("status reports an extra file in nodes/", '"state": "receipt-mismatch"' in r.stdout and "injected.md" in r.stdout, r.stdout)
    r = run("close", str(run_dir), "--decision", "ok", "--by", "owner")
    check("close refuses an extra file in nodes/", r.returncode == 2 and "injected.md" in r.stdout, r.stdout)

    run_dir, graph = recorded("no-approval")
    (run_dir / "approval.json").unlink()
    r = run("close", str(run_dir), "--decision", "ok", "--by", "owner")
    check("close refuses a run whose approval is gone", r.returncode == 2 and "approval" in r.stdout
          and not (run_dir / "decision.json").exists(), r.stdout)

    run_dir, graph = recorded("clean")
    digest_clean = canonical_digest(graph)
    r = run("approve", str(run_dir), "--digest", digest_clean, "--by", "someone-else")
    check("a recorded run cannot be re-approved", r.returncode == 2 and "cannot be re-approved" in r.stdout
          and json.loads((run_dir / "approval.json").read_text(encoding="utf-8"))["by"] == "owner", r.stdout)
    r = run("close", str(run_dir), "--decision", "принято", "--by", "owner", "--at", "2026-10-07T00:05:00Z")
    check("an intact recorded run still closes", r.returncode == 0 and (run_dir / "decision.json").is_file(), r.stdout)
    r = run("approve", str(run_dir), "--digest", digest_clean, "--by", "someone-else")
    check("a closed run cannot be re-approved", r.returncode == 2 and "cannot be re-approved" in r.stdout, r.stdout)
    decision_path = run_dir / "decision.json"
    good_decision = decision_path.read_text(encoding="utf-8")
    for label, text in (("unreadable", "{not json"),
                        ("for another digest", good_decision.replace(digest_clean, "1" * 64)),
                        ("without the human", json.dumps(dict(json.loads(good_decision), by="")))):
        decision_path.write_text(text, encoding="utf-8")
        r = run("status", str(run_dir))
        check(f"status does not report a {label} decision as closed", '"state": "decision-invalid"' in r.stdout, r.stdout)
    decision_path.write_text(good_decision, encoding="utf-8")
    r = run("status", str(run_dir))
    check("status reports the intact decision as closed", '"state": "closed"' in r.stdout, r.stdout)

    alias = tmp / "alias-of-proj"
    try:
        os.symlink(tmp / "proj", alias, target_is_directory=True)
        aliased = True
    except (OSError, NotImplementedError):
        aliased = False
    if aliased:
        r = run("status", str(alias / ".itd-memory" / "graph-runs" / "clean"))
        check("a symbolic link above the project on the run path is refused",
              r.returncode == 2 and "symbolic link" in r.stdout and "alias-of-proj" in r.stdout, r.stdout)
    else:
        check("a symbolic link above the project on the run path is refused (SKIP: no symlink privilege)", True)


# ---------------------------------------------------------------------------
# 8. read-only nodes, enforced by the project's git state (independent review p6)
# ---------------------------------------------------------------------------

def test_project_tree_check(tmp: Path) -> None:
    def attempt(name: str, mutate) -> tuple[subprocess.CompletedProcess, Path]:
        run_dir, digest = init_run(tmp, name, project=f"tree-{name}")
        r = run("approve", str(run_dir), "--digest", digest, "--by", "owner", "--at", "2026-10-07T00:00:00Z")
        assert r.returncode == 0, r.stdout
        project = run_dir.parent.parent.parent
        mutate(project)
        res = tmp / f"tree-{name}.json"
        write_json(res, good_result(load(run_dir), digest))
        return run("record", str(run_dir), "--result", str(res), "--runtime", "workflow"), run_dir

    run_dir, digest = init_run(tmp, "approval-tree", project="tree-approval")
    run("approve", str(run_dir), "--digest", digest, "--by", "owner")
    approval = json.loads((run_dir / "approval.json").read_text(encoding="utf-8"))
    tree = approval.get("projectTree") or {}
    check("approve stores the project's git state (HEAD and changed paths)",
          tree.get("git") is True and re.fullmatch(r"[0-9a-f]{40}", tree.get("head", "")) is not None
          and isinstance(tree.get("changes"), dict), json.dumps(tree)[:300])

    r, rdir = attempt("tracked", lambda pr: (pr / "src.txt").write_text("edited by a node\n", encoding="utf-8"))
    check("record refuses when a tracked project file changed during the run",
          r.returncode == 2 and "did not stay read-only" in r.stdout and "src.txt" in r.stdout
          and not (rdir / "receipt.json").exists() and not (rdir / "nodes").exists(), r.stdout)
    r, rdir = attempt("untracked", lambda pr: (pr / "new-file.py").write_text("print(1)\n", encoding="utf-8"))
    check("record refuses when a new file appeared in the project", r.returncode == 2 and "new-file.py" in r.stdout, r.stdout)
    r, rdir = attempt("deleted", lambda pr: (pr / "src.txt").unlink())
    check("record refuses when a project file was deleted", r.returncode == 2 and "src.txt" in r.stdout, r.stdout)

    def commit(pr: Path) -> None:
        (pr / "src.txt").write_text("committed by a node\n", encoding="utf-8")
        for args in (["add", "src.txt"], ["commit", "-q", "-m", "node commit"]):
            subprocess.run(["git", "-C", str(pr), *args], check=True, capture_output=True, env=git_env())
    r, rdir = attempt("commit", commit)
    check("record refuses when HEAD moved during the run", r.returncode == 2 and "HEAD" in r.stdout, r.stdout)

    def telemetry(pr: Path) -> None:
        for rel in (".claude/completion/signals.jsonl", ".claude/traces/t.jsonl", ".itd-memory/events.jsonl"):
            f = pr / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("{}\n", encoding="utf-8")
    r, rdir = attempt("telemetry", telemetry)
    check("harness telemetry and .itd-memory/ do not count as a project change",
          r.returncode == 0 and (rdir / "receipt.json").is_file(), r.stdout)

    def ignored(pr: Path) -> None:
        (pr / ".gitignore").write_text("build/\n", encoding="utf-8")
    r, rdir = attempt("gitignore", ignored)
    check("a new .gitignore is itself a project change", r.returncode == 2 and ".gitignore" in r.stdout, r.stdout)

    run_dir, digest = init_run(tmp, "legacy", project="tree-legacy")
    run("approve", str(run_dir), "--digest", digest, "--by", "owner")
    legacy = json.loads((run_dir / "approval.json").read_text(encoding="utf-8"))
    legacy.pop("projectTree")
    (run_dir / "approval.json").write_text(json.dumps(legacy), encoding="utf-8")
    res = tmp / "legacy.json"
    write_json(res, good_result(load(run_dir), digest))
    r = run("record", str(run_dir), "--result", str(res), "--runtime", "serial")
    check("record refuses an approval without the project tree state", r.returncode == 2 and "approve the graph again" in r.stdout, r.stdout)

    plain_run = rd(tmp, "no-git", project="not-a-repo")
    r = run("init", str(plain_run), "--module", "x.ts")
    digest_m = re.search(r"graphDigest: ([0-9a-f]{64})", r.stdout)
    r = run("approve", str(plain_run), "--digest", digest_m.group(1) if digest_m else "0" * 64, "--by", "owner")
    check("approve refuses a project that is not a git work tree",
          r.returncode == 2 and "not a git work tree" in r.stdout and not (plain_run / "approval.json").exists(), r.stdout)

    # a project that is a subdirectory of its git work tree (monorepo): paths resolve from the repository root
    mono = tmp / "mono"
    ensure_git(mono)
    app = mono / "apps" / "web"
    app.mkdir(parents=True)
    (app / "limits.ts").write_text("export const a = 1\n", encoding="utf-8")
    for args in (["add", "apps/web/limits.ts"], ["commit", "-q", "-m", "app"]):
        subprocess.run(["git", "-C", str(mono), *args], check=True, capture_output=True, env=git_env())
    (app / "limits.ts").write_text("export const a = 2 // owner's work in progress\n", encoding="utf-8")
    (app / "draft.ts").write_text("export const draft = 1\n", encoding="utf-8")
    sub_run = app / ".itd-memory" / "graph-runs" / "sub"
    r = run("init", str(sub_run), "--module", "limits.ts")
    sub_digest = re.search(r"graphDigest: ([0-9a-f]{64})", r.stdout).group(1)
    run("approve", str(sub_run), "--digest", sub_digest, "--by", "owner")
    tree = json.loads((sub_run / "approval.json").read_text(encoding="utf-8"))["projectTree"]["changes"]
    check("a subdirectory project hashes its changed files (not 'deleted')",
          tree.get("apps/web/limits.ts", "").startswith(" M:") and "deleted" not in tree.get("apps/web/limits.ts", "")
          and tree.get("apps/web/draft.ts", "").startswith("??:") and "deleted" not in tree.get("apps/web/draft.ts", ""),
          json.dumps(tree)[:300])
    (app / "limits.ts").write_text("export const a = 3 // changed by a node\n", encoding="utf-8")
    res = tmp / "sub.json"
    write_json(res, good_result(load(sub_run), sub_digest))
    r = run("record", str(sub_run), "--result", str(res), "--runtime", "serial")
    check("record catches a second change to an already modified file of a subdirectory project",
          r.returncode == 2 and "apps/web/limits.ts" in r.stdout and not (sub_run / "receipt.json").exists(), r.stdout)


# ---------------------------------------------------------------------------
# 9. approval and receipt provenance, RFC 8259 numbers (independent review p8)
# ---------------------------------------------------------------------------

def test_provenance_and_json(tmp: Path) -> None:
    run_dir, digest = init_run(tmp, "forged", project="prov-forged")
    (run_dir / "approval.json").write_text(json.dumps({"graphDigest": digest}), encoding="utf-8")
    for cmd in ("emit-workflow", "emit-serial"):
        r = run(cmd, str(run_dir))
        check(f"{cmd} refuses a digest-only approval nobody signed", r.returncode == 2 and "incomplete" in r.stdout, r.stdout)
    r = run("status", str(run_dir))
    check("status reports a digest-only approval as invalid", '"state": "approval-invalid"' in r.stdout, r.stdout)
    r = run("approve", str(run_dir), "--digest", digest, "--by", "owner")
    good = json.loads((run_dir / "approval.json").read_text(encoding="utf-8"))
    for label, mutate in (("without the human", lambda a: a.__setitem__("by", " ")),
                          ("for another run", lambda a: a.__setitem__("runId", "other-run")),
                          ("without a timestamp", lambda a: a.pop("at")),
                          ("with a malformed tree state", lambda a: a.__setitem__("projectTree", {"git": True, "head": "x", "changes": []}))):
        bad = json.loads(json.dumps(good))
        mutate(bad)
        (run_dir / "approval.json").write_text(json.dumps(bad), encoding="utf-8")
        r = run("emit-workflow", str(run_dir))
        check(f"emit-workflow refuses an approval {label}", r.returncode == 2 and "incomplete" in r.stdout, r.stdout)
    (run_dir / "approval.json").write_text(json.dumps(good), encoding="utf-8")
    r = run("emit-workflow", str(run_dir))
    check("the intact approval still emits", r.returncode == 0 and r.stdout.startswith("export const meta"), r.stdout[:200])

    res = tmp / "prov-result.json"
    write_json(res, good_result(load(run_dir), digest))
    r = run("record", str(run_dir), "--result", str(res), "--runtime", "workflow", "--at", "2026-10-07T00:01:00Z")
    assert r.returncode == 0, r.stdout
    receipt_path = run_dir / "receipt.json"
    intact = receipt_path.read_text(encoding="utf-8")
    base = json.loads(intact)
    for label, mutate, needle in (
            ("an unsupported runtime", lambda x: x.__setitem__("runtime", "teleport"), "runtime"),
            ("a foreign run id", lambda x: x.__setitem__("runId", "other-run"), "runId"),
            ("no timestamp", lambda x: x.pop("at"), "timestamp"),
            ("a malformed result hash", lambda x: x.__setitem__("resultSha256", "abc"), "resultSha256"),
            ("a malformed node entry", lambda x: x["nodes"]["synth"].__setitem__("bytes", "12"), "synth is malformed")):
        bad = json.loads(intact)
        mutate(bad)
        receipt_path.write_text(json.dumps(bad), encoding="utf-8")
        r = run("status", str(run_dir))
        check(f"status reports a receipt with {label}", '"state": "receipt-mismatch"' in r.stdout and needle in r.stdout, r.stdout)
        r = run("close", str(run_dir), "--decision", "ok", "--by", "owner")
        check(f"close refuses a receipt with {label}", r.returncode == 2 and needle in r.stdout
              and not (run_dir / "decision.json").exists(), r.stdout)
    receipt_path.write_text(intact, encoding="utf-8")
    r = run("status", str(run_dir))
    check("the intact receipt is recorded again", '"state": "recorded"' in r.stdout, r.stdout)

    nan_graph = tmp / "nan-graph.json"
    nan_graph.write_text(json.dumps(load(run_dir)).replace('"schemaVersion": 1', '"schemaVersion": NaN'), encoding="utf-8")
    target = rd(tmp, "nan", project="prov-forged")
    r = run("init", str(target), "--from", str(nan_graph))
    check("init refuses a graph with a non-finite number (NaN is not JSON)",
          r.returncode == 2 and "non-finite" in r.stdout and not target.exists(), r.stdout)
    run2, digest2 = init_run(tmp, "inf", project="prov-forged")
    run("approve", str(run2), "--digest", digest2, "--by", "owner")
    inf_res = tmp / "inf-result.json"
    text = json.dumps(good_result(load(run2), digest2)).replace('"line": 41', '"line": Infinity', 1)
    inf_res.write_text(text, encoding="utf-8")
    r = run("record", str(run2), "--result", str(inf_res), "--runtime", "serial")
    check("record refuses a result with Infinity", r.returncode == 2 and "non-finite" in r.stdout
          and not (run2 / "receipt.json").exists(), r.stdout)


def main() -> int:
    # resolved: the run tool refuses a symbolic link anywhere on the run directory path
    tmp = Path(tempfile.mkdtemp(prefix="itd-graph-")).resolve()
    try:
        run_dir, digest = test_init_and_validate(tmp)
        test_validator(tmp, run_dir)
        test_approve_and_emit(tmp, run_dir, digest)
        test_record_and_close(tmp, run_dir, digest)
        test_stale_approval(tmp)
        test_containment_and_integrity(tmp)
        test_project_tree_check(tmp)
        test_provenance_and_json(tmp)
        test_skill_md()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'PASSED' if FAIL == 0 else 'FAILED'}: {FAIL} failed ({PASS} passed)")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
