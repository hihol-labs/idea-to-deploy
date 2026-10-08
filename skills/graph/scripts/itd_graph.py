#!/usr/bin/env python3
"""itd_graph.py - Graph Lite (ADR-013): one explicit agent graph per task, as files.

The skill /graph turns ONE task into an explicit agent graph (jobs, arrows, shared
state, a checker separate from the writer, a human terminal) and keeps every step
as a file under the run directory `.itd-memory/graph-runs/<run-id>/`:

  graph.json     the designed graph (nodes, edges, state, prompts, output schemas)
  approval.json  the owner's approval of the EXACT graph digest
  nodes/<id>.md  one file per executed node (what the node returned)
  receipt.json   graph digest, runtime (workflow|serial), per-node sha256
  decision.json  the human terminal decision

This script is the deterministic half of the skill. It never runs a model, never
edits project sources and never talks to the network. Invariants (ADR-009 §Decision,
kept here on purpose): a proposal is not an authorization - only the human approves,
and approves an exact digest; a changed graph invalidates the approval; every
non-human node is read-only in this version; the human is the only terminal node;
no graph mechanism mints `verified`.

Containment: RUN_DIR must be `<project>/.itd-memory/graph-runs/<run-id>` with no symbolic
link anywhere on its absolute path; the run id is the directory name. Node
ids are single safe path components ([a-z0-9-]), so `nodes/<id>.md` cannot leave the
run directory. `record` checks every node output against the node's declared schema
(a closed JSON-schema subset: type, properties, required, items, enum), refuses a run
directory that already holds node artifacts, and writes the node files and the
receipt atomically; `close` and `status` re-verify the approval and every recorded
node file against the receipt.

Read-only nodes are a contract, backed by two mechanisms; Graph Lite is NOT a sandbox.
emit-workflow runs every node as the `Explore` subagent type (no Edit, Write or
NotebookEdit tools; shell and network access stay with the host and its hooks) and the
serial plan names the same agent type; and `approve` records the git state of the project
(the directory that holds `.itd-memory/`) - HEAD plus every changed or untracked path with
a content hash - so `record` refuses when a git-visible project file changed between
approval and recording. Not detected: git-ignored files, `.itd-memory/` (methodology
state), harness telemetry under `.claude/completion/` and `.claude/traces/`, and anything
outside the project, network use included. A project that is not a git work tree cannot
be approved.

Commands (exit 0 ok, 1 invalid graph, 2 refused):

  init RUN_DIR --template module-neighbour-check --module PATH [--task TEXT]
               [--project ROOT]
  init RUN_DIR --from GRAPH_JSON
  validate RUN_DIR
  digest RUN_DIR
  approve RUN_DIR --digest SHA --by NAME [--at ISO]
  emit-workflow RUN_DIR            # JS for the host Workflow tool (stdout)
  emit-serial RUN_DIR              # the same graph as an ordered serial plan (stdout)
  record RUN_DIR --result FILE --runtime workflow|serial [--at ISO]
  close RUN_DIR --decision TEXT --by NAME [--at ISO]
  status RUN_DIR

Run: sh skills/_shared/itd_py.sh skills/graph/scripts/itd_graph.py <command> ...
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = 1
ROLES = {"hunter", "checker", "synthesizer", "planner", "researcher", "human"}
TEMPLATES = ("module-neighbour-check",)
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA_KEYS = {"type", "properties", "required", "items", "enum"}
NODE_AGENT_TYPE = "Explore"
TREE_EXCLUDES = (".itd-memory", ".claude/completion", ".claude/traces")
SCHEMA_TYPES = {"object", "array", "string", "integer", "number", "boolean"}


class Refused(Exception):
    """A precondition failed; nothing was written."""


# --------------------------------------------------------------------------
# canonical digest
# --------------------------------------------------------------------------


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name} is not JSON (RFC 8259)")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def graph_digest(graph: dict) -> str:
    return sha256_bytes(canonical(graph))


def now_iso(at: str | None) -> str:
    if at:
        return at
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path, what: str):
    if not path.is_file():
        raise Refused(f"{what} is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except (OSError, ValueError) as exc:
        raise Refused(f"{what} is unreadable: {path}: {exc}") from exc


# --------------------------------------------------------------------------
# the shipped template: module neighbour check (ADR-012 item 6, four classes)
# --------------------------------------------------------------------------

CLASSES = [
    {
        "id": "owner",
        "title": "владелец или пустой id",
        "definition": (
            "операция над объектом без проверки, что он принадлежит текущему пользователю или "
            "организации; пустой, null, нулевой или не-UUID идентификатор, который проходит дальше по "
            "коду; доступ по id без проверки роли"
        ),
    },
    {
        "id": "money",
        "title": "валюта и сумма",
        "definition": (
            "пустая, отсутствующая или несовпадающая валюта; сумма без проверки знака, нуля и лимита; "
            "округление и порядок операций; сравнение суммы платежа с тарифом; единицы (копейки/рубли)"
        ),
    },
    {
        "id": "dedup",
        "title": "дедупликация и идемпотентность",
        "definition": (
            "повторный webhook, запрос или событие создают второй эффект; окно дедупликации и его ключ; "
            "ключ идемпотентности не проверяется или не сохраняется; гонка двух одинаковых запросов"
        ),
    },
    {
        "id": "time",
        "title": "границы времени",
        "definition": (
            "включительно/исключительно на границе окна (24 часа, сутки, месяц); часовой пояс; скользящее "
            "против календарного окна; истечение подписки или лимита; сравнение с now() в разных местах"
        ),
    },
]

READ_ONLY_CLAUSE = (
    "READ-ONLY: ничего не правь - без Edit/Write в исходники, без git-мутаций (add/commit/checkout/stash), "
    "без установки пакетов, без сети и без деплоя. Только читай код, тесты и `git diff`/`git log`."
)

FINDING_ITEM = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "line": {"type": "integer"},
        "class": {"type": "string", "enum": ["owner", "money", "dedup", "time", "other"]},
        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
        "claim": {"type": "string"},
        "evidence": {"type": "string"},
        "origin": {"type": "string", "enum": ["introduced", "pre-existing", "unknown"]},
    },
    "required": ["file", "line", "class", "severity", "claim", "evidence", "origin"],
}

SCHEMAS = {
    "findings": {
        "type": "object",
        "properties": {
            "findings": {"type": "array", "items": FINDING_ITEM},
            "scopeRead": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["findings", "scopeRead"],
    },
    "verdicts": {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "class": {"type": "string"},
                        "claim": {"type": "string"},
                        "verdict": {"type": "string", "enum": ["confirmed", "refuted", "unverifiable"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["file", "line", "class", "claim", "verdict", "reason"],
                },
            }
        },
        "required": ["verdicts"],
    },
    "synthesis": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "class": {"type": "string"},
                        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                        "origin": {"type": "string", "enum": ["introduced", "pre-existing", "unknown"]},
                        "status": {"type": "string", "enum": ["confirmed", "unverifiable"]},
                        "claim": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["file", "line", "class", "severity", "origin", "status", "claim", "evidence"],
                },
            },
            "dropped": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"claim": {"type": "string"}, "reason": {"type": "string"}},
                    "required": ["claim", "reason"],
                },
            },
            "journalLine": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["findings", "dropped", "journalLine", "summary"],
    },
}


def hunter_prompt(project: str, module: str, task: str, cls: dict) -> str:
    return (
        f"{READ_ONLY_CLAUSE}\n"
        f"Роль: охотник за одним классом дефектов в целом модуле (не только в диффе).\n"
        f"Проект: {project}\nМодуль: {module}\nЗадача, к которой относится проверка: {task}\n"
        f"Класс: {cls['id']} - {cls['title']}. Что искать: {cls['definition']}.\n"
        "Порядок: 1) прочитай ВЕСЬ модуль - каждую функцию, а не только изменённые; 2) найди вызывающий код "
        "и тесты модуля (grep по импортам и именам экспортов); 3) посмотри `git diff` модуля, чтобы отличить "
        "introduced (появилось в текущем изменении) от pre-existing (было до); 4) перечисли каждое место, где "
        "класс нарушен или не проверен. Каждая находка: file:line, что именно не так (claim), цитата кода "
        "(evidence), severity, origin. Находка без цитаты кода не считается. Если класса в модуле нет "
        "(например, валюта не используется) - верни пустой findings и перечисли в scopeRead, что прочитал."
    )


def skeptic_prompt(module: str) -> str:
    return (
        f"{READ_ONLY_CLAUSE}\n"
        "Роль: скептик - проверяешь ЧУЖИЕ находки, сам ничего не ищешь. Ниже, в разделе UPSTREAM OUTPUTS, "
        f"приходят находки охотников по модулю {module}. Для КАЖДОЙ находки открой указанный file:line и "
        "попробуй её ОПРОВЕРГНУТЬ: есть ли проверка выше по стеку, тест, инвариант БД, типизация или "
        "вызывающий код, который делает дефект невозможным. verdict = refuted, если опроверг (с цитатой в "
        "reason); confirmed, если код подтверждает дефект (цитата); unverifiable, если из кода установить "
        "нельзя. При сомнении - refuted. Дубликаты (тот же file:line и класс) объедини и скажи об этом в reason."
    )


def synthesizer_prompt(module: str, run_id: str) -> str:
    return (
        f"{READ_ONLY_CLAUSE}\n"
        "Роль: синтезатор. На входе (UPSTREAM OUTPUTS): находки охотников и вердикты скептика по модулю "
        f"{module}. Оставь только confirmed и unverifiable, сними дубликаты по file:line+class (в dropped - "
        "с причиной, туда же refuted), отсортируй по severity (high > medium > low), затем по origin "
        "(introduced раньше pre-existing). summary - 3-5 предложений для владельца: что найдено, что "
        "опровергнуто, что не удалось проверить. journalLine - одна строка таблицы журнала утечек проекта "
        "(docs/LEAK_JOURNAL.md) в формате `| {дата} | проверка по классам (/graph) | `"
        f"{module}` | классы через запятую | было до / внес сам | /graph {run_id} | итог |`. "
        "Решение, вносить ли строку, принимает человек - ты только готовишь текст."
    )


def build_template(run_id: str, project: str, module: str, task: str) -> dict:
    nodes = []
    edges = []
    for cls in CLASSES:
        nid = f"hunt-{cls['id']}"
        nodes.append({
            "id": nid, "role": "hunter", "kind": "agent", "purity": "read-only",
            "inputs": ["state.module", "state.task"], "outputs": ["findings"],
            "schema": "findings", "prompt": hunter_prompt(project, module, task, cls),
        })
        edges.append([nid, "skeptic"])
    nodes.append({
        "id": "skeptic", "role": "checker", "kind": "agent", "purity": "read-only",
        "inputs": [f"hunt-{c['id']}.findings" for c in CLASSES], "outputs": ["verdicts"],
        "checks": [f"hunt-{c['id']}" for c in CLASSES],
        "schema": "verdicts", "prompt": skeptic_prompt(module),
    })
    nodes.append({
        "id": "synth", "role": "synthesizer", "kind": "agent", "purity": "read-only",
        "inputs": ["skeptic.verdicts"] + [f"hunt-{c['id']}.findings" for c in CLASSES],
        "outputs": ["synthesis"], "schema": "synthesis", "prompt": synthesizer_prompt(module, run_id),
    })
    nodes.append({
        "id": "human", "role": "human", "kind": "human", "purity": "read-only",
        "inputs": ["synth.synthesis"], "outputs": ["decision"],
        "prompt": "Владелец читает synth.synthesis, решает по каждой находке и сам вносит строку в журнал утечек.",
    })
    edges += [["skeptic", "synth"], ["synth", "human"]]
    for cls in CLASSES:
        edges.append([f"hunt-{cls['id']}", "synth"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runId": run_id,
        "template": "module-neighbour-check",
        "task": task,
        "state": {
            "project": project, "module": module,
            "classes": [c["id"] for c in CLASSES],
            "sharedRecord": "findings -> verdicts -> synthesis -> decision; every node output is a file under nodes/",
        },
        "nodes": nodes,
        "edges": edges,
        "schemas": SCHEMAS,
    }


# --------------------------------------------------------------------------
# closed JSON-schema subset (the only keywords node schemas may use)
# --------------------------------------------------------------------------


def schema_errors(schema, path: str) -> list[str]:
    """Violations of the closed subset: type, properties, required, items, enum."""
    if not isinstance(schema, dict):
        return [f"{path} must be an object"]
    errs: list[str] = []
    unknown = sorted(set(schema) - SCHEMA_KEYS)
    if unknown:
        errs.append(f"{path} uses unsupported keyword(s) {', '.join(unknown)}")
    typ = schema.get("type")
    if typ not in SCHEMA_TYPES:
        errs.append(f"{path}.type must be one of {', '.join(sorted(SCHEMA_TYPES))}")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        errs.append(f"{path}.enum must be a non-empty list")
    if typ == "object":
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            errs.append(f"{path}.properties must be an object")
            props = {}
        for key, sub in props.items():
            errs += schema_errors(sub, f"{path}.properties.{key}")
        req = schema.get("required", [])
        if not isinstance(req, list) or not all(isinstance(r, str) and r in props for r in req):
            errs.append(f"{path}.required must list declared properties")
    elif "properties" in schema or "required" in schema:
        errs.append(f"{path}: properties/required need type object")
    if typ == "array":
        if "items" in schema:
            errs += schema_errors(schema["items"], f"{path}.items")
    elif "items" in schema:
        errs.append(f"{path}: items needs type array")
    return errs


def instance_errors(schema: dict, value, path: str = "$") -> list[str]:
    """Check a node output against a schema that passed schema_errors()."""
    typ = schema["type"]
    ok = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
        "boolean": isinstance(value, bool),
    }[typ]
    if not ok:
        return [f"{path} must be {typ}"]
    errs: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path} must be one of {schema['enum']}")
    if typ == "object":
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errs.append(f"{path}.{key} is required")
        for key, sub in props.items():
            if key in value:
                errs += instance_errors(sub, value[key], f"{path}.{key}")
    if typ == "array" and "items" in schema:
        for k, item in enumerate(value):
            errs += instance_errors(schema["items"], item, f"{path}[{k}]")
    return errs


# --------------------------------------------------------------------------
# pure validator
# --------------------------------------------------------------------------


def validate_graph(graph) -> list[str]:
    """Return the list of violations (empty = valid). Rule ids are stable: tests pin them."""
    errs: list[str] = []
    if not isinstance(graph, dict):
        return ["G01: graph must be a JSON object"]
    if graph.get("schemaVersion") != SCHEMA_VERSION:
        errs.append(f"G01: schemaVersion must be {SCHEMA_VERSION}")
    run_id = graph.get("runId")
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        errs.append("G12: runId must match [A-Za-z0-9][A-Za-z0-9._-]*")
    if not isinstance(graph.get("task"), str) or not graph.get("task", "").strip():
        errs.append("G12: task must be a non-empty string")
    if not isinstance(graph.get("template"), str) or not graph.get("template", "").strip():
        errs.append("G12: template must be a non-empty string (use \"custom\" for a hand-written graph)")
    if not isinstance(graph.get("state"), dict):
        errs.append("G12: state must be an object")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    schemas = graph.get("schemas")
    if not isinstance(nodes, list) or not nodes:
        errs.append("G01: nodes must be a non-empty list")
        return errs
    if not isinstance(edges, list):
        errs.append("G01: edges must be a list")
        return errs
    if not isinstance(schemas, dict):
        errs.append("G08: schemas must be an object")
        schemas = {}
    for name, sch in schemas.items():
        for e in schema_errors(sch, f"schemas.{name}"):
            errs.append("G08: " + e)
        if isinstance(sch, dict) and sch.get("type") != "object":
            errs.append(f"G08: schemas.{name} must have type object (a node returns a JSON object)")

    ids: list[str] = []
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not NODE_ID_RE.match(n.get("id", "")):
            errs.append("G02: every node needs an id matching [a-z0-9][a-z0-9-]*")
            continue
        if n["id"] in ids:
            errs.append(f"G02: duplicate node id {n['id']}")
        ids.append(n["id"])
    idset = set(ids)

    pairs: list[tuple[str, str]] = []
    for e in edges:
        if not (isinstance(e, list) and len(e) == 2 and all(isinstance(x, str) for x in e)):
            errs.append("G03: every edge must be a [from, to] pair of node ids")
            continue
        src, dst = e
        if src not in idset or dst not in idset:
            errs.append(f"G03: edge {src}->{dst} names an unknown node")
            continue
        if src == dst:
            errs.append(f"G03: self-edge on {src}")
            continue
        pairs.append((src, dst))

    out: dict[str, list[str]] = {i: [] for i in ids}
    inc: dict[str, list[str]] = {i: [] for i in ids}
    for src, dst in pairs:
        out[src].append(dst)
        inc[dst].append(src)

    # G04 DAG (Kahn)
    indeg = {i: len(inc[i]) for i in ids}
    queue = [i for i in ids if indeg[i] == 0]
    seen = 0
    while queue:
        cur = queue.pop(0)
        seen += 1
        for nxt in out[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if seen != len(ids):
        errs.append("G04: the graph has a cycle")

    by_id = {n["id"]: n for n in nodes if isinstance(n, dict) and n.get("id") in idset}
    humans = [i for i in ids if by_id[i].get("kind") == "human"]
    if len(humans) != 1:
        errs.append(f"G05: exactly one human terminal node is required (found {len(humans)})")
    else:
        h = humans[0]
        if out[h]:
            errs.append(f"G05: human node {h} must be terminal (no outgoing edges)")
        if not inc[h]:
            errs.append(f"G05: human node {h} must receive at least one edge")
        if seen == len(ids):
            # every node must reach the human
            reach: set[str] = set()
            stack = [h]
            while stack:
                cur = stack.pop()
                if cur in reach:
                    continue
                reach.add(cur)
                stack.extend(inc[cur])
            for i in ids:
                if i not in reach:
                    errs.append(f"G05: node {i} does not reach the human terminal")

    for i in ids:
        n = by_id[i]
        role = n.get("role")
        if role not in ROLES:
            errs.append(f"G11: node {i} has unknown role {role!r}")
        if n.get("kind") == "human":
            if role != "human":
                errs.append(f"G11: human node {i} must have role human")
            if n.get("purity") != "read-only":
                errs.append(f"G06: human node {i} must be read-only too (purity={n.get('purity')!r})")
            if not isinstance(n.get("prompt"), str) or not n.get("prompt", "").strip():
                errs.append(f"G07: human node {i} needs a non-empty prompt (what the owner decides)")
            continue
        if n.get("kind") != "agent":
            errs.append(f"G06: node {i} kind must be agent or human")
        if n.get("purity") != "read-only":
            errs.append(f"G06: node {i} must be read-only in this version (purity={n.get('purity')!r})")
        if role == "human":
            errs.append(f"G11: node {i} has role human but kind {n.get('kind')!r}")
        prompt = n.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errs.append(f"G07: node {i} needs a non-empty prompt")
        elif "read-only" not in prompt.lower():
            errs.append(f"G07: node {i} prompt must state that the node is read-only")
        for key in ("inputs", "outputs"):
            v = n.get(key)
            if not isinstance(v, list) or not v or not all(isinstance(x, str) and x for x in v):
                errs.append(f"G07: node {i} needs a non-empty {key} list")
        if n.get("schema") not in schemas:
            errs.append(f"G08: node {i} references unknown schema {n.get('schema')!r}")
        if not out[i]:
            errs.append(f"G10: agent node {i} has no outgoing edge")

    checkers = [i for i in ids if by_id[i].get("role") == "checker"]
    if not checkers:
        errs.append("G09: at least one checker node (role checker) is required - writer and checker stay separate")
    for c in checkers:
        checks = by_id[c].get("checks")
        if not isinstance(checks, list) or not checks:
            errs.append(f"G09: checker {c} must list the node ids it checks")
            continue
        for t in checks:
            if t == c:
                errs.append(f"G09: checker {c} checks itself")
            elif t not in inc[c]:
                errs.append(f"G09: checker {c} checks {t} without an edge {t}->{c}")
            elif by_id.get(t, {}).get("role") == "checker":
                errs.append(f"G09: checker {c} must check a non-checker node, not {t}")
    return errs


def topological_layers(graph: dict) -> list[list[str]]:
    """Agent nodes grouped by longest-path depth (human excluded); stable order inside a layer."""
    ids = [n["id"] for n in graph["nodes"]]
    inc = {i: [] for i in ids}
    for src, dst in graph["edges"]:
        inc[dst].append(src)
    depth: dict[str, int] = {}

    def d(i: str) -> int:
        if i not in depth:
            depth[i] = 0 if not inc[i] else 1 + max(d(p) for p in inc[i])
        return depth[i]

    for i in ids:
        d(i)
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    layers: dict[int, list[str]] = {}
    for i in ids:
        if kinds[i] == "human":
            continue
        layers.setdefault(depth[i], []).append(i)
    return [layers[k] for k in sorted(layers)]


# --------------------------------------------------------------------------
# run directory state
# --------------------------------------------------------------------------


def paths(run_dir: Path) -> dict[str, Path]:
    return {
        "graph": run_dir / "graph.json",
        "approval": run_dir / "approval.json",
        "receipt": run_dir / "receipt.json",
        "decision": run_dir / "decision.json",
        "nodes": run_dir / "nodes",
    }


def contained_run_dir(raw: str) -> Path:
    """RUN_DIR must be <anything>/.itd-memory/graph-runs/<run-id>, no symlink among the three.

    The run tool writes only under this directory; refusing anything else keeps a graph
    and its approval from pointing `record`/`close` at an arbitrary writable location.
    """
    run_dir = Path(os.path.abspath(raw))
    runs, memory = run_dir.parent, run_dir.parent.parent
    if run_dir.name in ("", ".", "..") or not RUN_ID_RE.match(run_dir.name):
        raise Refused(f"run directory name {run_dir.name!r} is not a valid run id ([A-Za-z0-9][A-Za-z0-9._-]*)")
    if runs.name != "graph-runs" or memory.name != ".itd-memory":
        raise Refused(f"run directory must be <project>/.itd-memory/graph-runs/<run-id>, got {run_dir}")
    for component in (run_dir, *run_dir.parents):
        if os.path.islink(component):
            raise Refused(f"run directory path holds a symbolic link: {component}")
    for name in ("graph.json", "approval.json", "receipt.json", "decision.json", "nodes"):
        if os.path.islink(run_dir / name):
            raise Refused(f"run artifact is a symbolic link: {run_dir / name}")
    return run_dir


def project_root(run_dir: Path) -> Path:
    return run_dir.parent.parent.parent


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=env, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused(f"git is not usable for the project tree check: {exc}") from exc


def project_tree_state(root: Path) -> dict:
    """HEAD plus every changed/untracked path (outside TREE_EXCLUDES) with a content hash."""
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != b"true":
        raise Refused(f"the project {root} is not a git work tree: /graph verifies that nodes stayed "
                      "read-only by the project's git state and cannot run without it")
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise Refused("git rev-parse --show-toplevel failed: " + top.stderr.decode("utf-8", "replace")[:200])
    toplevel = Path(top.stdout.decode("utf-8").strip())
    head = _git(root, "rev-parse", "--verify", "-q", "HEAD")
    head_oid = head.stdout.decode("utf-8").strip() if head.returncode == 0 else ""
    spec = ["--", "."] + [f":(exclude){x}" for x in TREE_EXCLUDES]
    status = _git(root, "-c", "status.renames=false", "status", "--porcelain=v1", "-z",
                  "--untracked-files=all", *spec)
    if status.returncode != 0:
        raise Refused("git status failed: " + status.stderr.decode("utf-8", "replace")[:200])
    changes: dict[str, str] = {}
    for entry in status.stdout.split(b"\0"):
        if len(entry) < 4:
            continue
        code, rel = entry[:2].decode("ascii", "replace"), entry[3:].decode("utf-8", "surrogateescape")
        full = toplevel / rel
        if os.path.islink(full):
            digest = "link:" + os.readlink(full)
        elif full.is_file():
            digest = sha256_bytes(full.read_bytes())
        elif full.exists():
            digest = "dir"
        else:
            digest = "deleted"
        changes[rel] = f"{code}:{digest}"
    return {"git": True, "head": head_oid, "changes": changes}


def tree_differences(before: dict, after: dict) -> list[str]:
    diffs: list[str] = []
    if before.get("head") != after.get("head"):
        diffs.append(f"HEAD {str(before.get('head'))[:12]} -> {str(after.get('head'))[:12]}")
    b, a = before.get("changes") or {}, after.get("changes") or {}
    for path in sorted(set(b) | set(a)):
        if b.get(path) != a.get(path):
            diffs.append(path)
    return diffs


def receipt_mismatches(run_dir: Path, receipt: dict, graph: dict) -> list[str]:
    """Node files that are missing, extra or differ from the receipt's sha256/size."""
    nodes_dir = paths(run_dir)["nodes"]
    agent_ids = sorted(n["id"] for n in graph["nodes"] if n["kind"] == "agent")
    problems: list[str] = []
    if receipt.get("runId") != graph.get("runId"):
        problems.append("receipt runId does not name this run")
    if receipt.get("runtime") not in ("workflow", "serial"):
        problems.append(f"receipt runtime {receipt.get('runtime')!r} is not workflow or serial")
    if not isinstance(receipt.get("at"), str) or not receipt["at"].strip():
        problems.append("receipt has no timestamp")
    if not (isinstance(receipt.get("resultSha256"), str) and SHA_RE.match(receipt["resultSha256"])):
        problems.append("receipt resultSha256 is not a sha256")
    recorded = receipt.get("nodes")
    if not isinstance(recorded, dict) or sorted(recorded) != agent_ids:
        return problems + ["receipt does not list exactly the agent nodes of the graph"]
    for i, entry in recorded.items():
        if not (isinstance(entry, dict) and set(entry) == {"sha256", "bytes"}
                and isinstance(entry["sha256"], str) and SHA_RE.match(entry["sha256"])
                and type(entry["bytes"]) is int and entry["bytes"] >= 0):
            problems.append(f"receipt entry of {i} is malformed")
    present = sorted(p.name for p in nodes_dir.iterdir()) if nodes_dir.is_dir() else []
    expected = sorted(f"{i}.md" for i in agent_ids)
    if present != expected:
        problems.append(f"nodes/ holds {present}, receipt expects {expected}")
    for i in agent_ids:
        f = nodes_dir / f"{i}.md"
        if not f.is_file() or os.path.islink(f):
            problems.append(f"nodes/{i}.md is missing")
            continue
        data = f.read_bytes()
        entry = recorded.get(i) or {}
        if entry.get("sha256") != sha256_bytes(data) or entry.get("bytes") != len(data):
            problems.append(f"nodes/{i}.md differs from the receipt")
    return problems


def load_valid_graph(run_dir: Path) -> tuple[dict, str]:
    graph = read_json(paths(run_dir)["graph"], "graph.json")
    errs = validate_graph(graph)
    if errs:
        raise Refused("graph.json is invalid: " + "; ".join(errs))
    return graph, graph_digest(graph)


def approval_problems(approval, graph: dict) -> list[str]:
    """Everything `approve` writes must be there: who, when, which run and the project tree."""
    if not isinstance(approval, dict):
        return ["approval.json is not an object"]
    problems = []
    if approval.get("runId") != graph.get("runId"):
        problems.append("runId does not name this run")
    for key in ("by", "at"):
        if not isinstance(approval.get(key), str) or not approval[key].strip():
            problems.append(f"no {key}")
    tree = approval.get("projectTree")
    if not (isinstance(tree, dict) and tree.get("git") is True and isinstance(tree.get("head"), str)
            and isinstance(tree.get("changes"), dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in tree["changes"].items())):
        problems.append("no project tree state")
    return problems


def load_matching_approval(run_dir: Path, digest: str, graph: dict) -> dict:
    approval = read_json(paths(run_dir)["approval"], "approval.json (approve the digest first)")
    if not isinstance(approval, dict) or approval.get("graphDigest") != digest:
        got = approval.get("graphDigest") if isinstance(approval, dict) else None
        raise Refused(
            f"approval is stale: approved {str(got)[:12]} but the graph is now "
            f"{digest[:12]} - the graph changed after approval, approve it again"
        )
    problems = approval_problems(approval, graph)
    if problems:
        raise Refused("approval.json is incomplete (" + "; ".join(problems) + ") - approve the graph again with `approve`")
    return approval


def run_state(run_dir: Path) -> dict:
    p = paths(run_dir)
    state = {"state": "missing", "graphDigest": None, "valid": False}
    if not p["graph"].is_file():
        return state
    try:
        graph = read_json(p["graph"], "graph.json")
    except Refused as exc:
        state["state"] = "unreadable"
        state["reason"] = str(exc)
        return state
    errs = validate_graph(graph)
    digest = graph_digest(graph)
    state.update({"graphDigest": digest, "valid": not errs, "state": "designed"})
    if errs:
        state["state"] = "invalid"
        state["reasons"] = errs
        return state
    if p["approval"].is_file():
        approval = read_json(p["approval"], "approval.json")
        state["state"] = "approved" if isinstance(approval, dict) and approval.get("graphDigest") == digest else "approval-stale"
        if state["state"] == "approval-stale":
            return state
        problems = approval_problems(approval, graph)
        if problems:
            state["state"] = "approval-invalid"
            state["reasons"] = problems
            return state
    else:
        if p["nodes"].exists() or p["receipt"].exists():
            state["state"] = "partial"
        return state
    if p["receipt"].is_file():
        receipt = read_json(p["receipt"], "receipt.json")
        state["state"] = "recorded" if receipt.get("graphDigest") == digest else "receipt-stale"
        if state["state"] == "receipt-stale":
            return state
        problems = receipt_mismatches(run_dir, receipt, graph)
        if problems:
            state["state"] = "receipt-mismatch"
            state["reasons"] = problems
            return state
    else:
        if p["nodes"].exists():
            state["state"] = "partial"
        return state
    if p["decision"].exists():
        problems = decision_problems(p["decision"], digest, graph)
        if problems:
            state["state"] = "decision-invalid"
            state["reasons"] = problems
        else:
            state["state"] = "closed"
    return state


def decision_problems(path: Path, digest: str, graph: dict) -> list[str]:
    try:
        decision = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"decision.json is unreadable: {exc}"]
    if not isinstance(decision, dict):
        return ["decision.json is not an object"]
    problems = []
    if decision.get("graphDigest") != digest:
        problems.append("decision.json names another graph digest")
    if decision.get("runId") != graph.get("runId"):
        problems.append("decision.json names another run id")
    for key in ("by", "decision", "at"):
        if not isinstance(decision.get(key), str) or not decision[key].strip():
            problems.append(f"decision.json has no {key}")
    return problems


# --------------------------------------------------------------------------
# emitters
# --------------------------------------------------------------------------


def js_literal(obj) -> str:
    # JSON is a valid JS literal for objects/arrays/strings/numbers; keep non-ASCII readable.
    return json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)


def phase_title(role: str) -> str:
    return {"hunter": "Hunt", "planner": "Plan", "researcher": "Research",
            "checker": "Check", "synthesizer": "Synthesize"}.get(role, role.capitalize())


def emit_workflow(graph: dict, digest: str) -> str:
    layers = topological_layers(graph)
    by_id = {n["id"]: n for n in graph["nodes"]}
    phases: list[str] = []
    for layer in layers:
        for i in layer:
            t = phase_title(by_id[i]["role"])
            if t not in phases:
                phases.append(t)
    nodes_lit = {
        i: {
            "prompt": by_id[i]["prompt"],
            "phase": phase_title(by_id[i]["role"]),
            "role": by_id[i]["role"],
            "upstream": [src for src, dst in graph["edges"] if dst == i],
            "schema": graph["schemas"][by_id[i]["schema"]],
        }
        for layer in layers for i in layer
    }
    meta_phases = ", ".join("{ title: " + json.dumps(p) + " }" for p in phases)
    run_id = graph["runId"]
    return (
        "export const meta = {\n"
        f"  name: {json.dumps('itd-graph-' + run_id)},\n"
        f"  description: {json.dumps('Graph Lite run ' + run_id + ' (' + graph['template'] + '): read-only nodes, approved digest ' + digest[:12])},\n"
        f"  phases: [{meta_phases}],\n"
        "}\n"
        "// Generated by skills/graph/scripts/itd_graph.py emit-workflow - do not edit by hand:\n"
        "// the owner approved exactly this graph digest; a hand edit is an unapproved graph.\n"
        f"const GRAPH_DIGEST = {json.dumps(digest)}\n"
        f"const LAYERS = {js_literal(layers)}\n"
        f"const NODES = {js_literal(nodes_lit)}\n"
        "const outputs = {}\n"
        "function promptFor(id) {\n"
        "  const node = NODES[id]\n"
        "  const upstream = {}\n"
        "  for (const u of node.upstream) upstream[u] = outputs[u]\n"
        "  if (node.upstream.length === 0) return node.prompt\n"
        "  return node.prompt + '\\n\\nUPSTREAM OUTPUTS (JSON):\\n' + JSON.stringify(upstream, null, 2)\n"
        "}\n"
        "for (const layer of LAYERS) {\n"
        "  // a barrier between layers is the graph itself: every downstream node consumes ALL upstream outputs\n"
        "  const results = await parallel(layer.map(id => () =>\n"
        f"    agent(promptFor(id), {{ label: id, phase: NODES[id].phase, schema: NODES[id].schema, agentType: {json.dumps(NODE_AGENT_TYPE)} }})))\n"
        "  layer.forEach((id, k) => {\n"
        "    const out = results[k]\n"
        "    if (out === null || out === undefined || out === '' || (Array.isArray(out) && out.length === 0)\n"
        "        || (typeof out === 'object' && !Array.isArray(out) && Object.keys(out).length === 0)) {\n"
        "      throw new Error('node ' + id + ' returned no output - the run is not green, record is refused')\n"
        "    }\n"
        "    outputs[id] = out\n"
        "  })\n"
        "  log('layer done: ' + layer.join(', '))\n"
        "}\n"
        "return { graphDigest: GRAPH_DIGEST, nodes: outputs }\n"
    )


def emit_serial(graph: dict, digest: str) -> str:
    layers = topological_layers(graph)
    by_id = {n["id"]: n for n in graph["nodes"]}
    lines = [
        f"# Serial plan for graph run {graph['runId']} (digest {digest})",
        "",
        "The host has no workflow runtime (or the workflow run failed): run the same graph node by node,",
        f"in this order, each node as ONE fresh read-only subagent (Agent tool, subagent_type {NODE_AGENT_TYPE}:",
        "no Edit, Write or NotebookEdit; on a host without it, the most restricted read-only agent). Paste the",
        "JSON the node returns into result.json under `nodes.<id>`; a node without output is not skipped",
        "and the run is not recorded. Nodes inside one layer are independent and may run in any order.",
        "",
    ]
    for k, layer in enumerate(layers, 1):
        lines.append(f"## Layer {k}: {', '.join(layer)}")
        for i in layer:
            n = by_id[i]
            ups = [src for src, dst in graph["edges"] if dst == i]
            lines += [
                "",
                f"### node `{i}` (role {n['role']}, schema `{n['schema']}`)",
                "",
                "Prompt (append the upstream outputs as `UPSTREAM OUTPUTS (JSON): {...}` "
                + (f"from nodes {', '.join(ups)}" if ups else "- none, this is a source node") + "):",
                "",
                "```text",
                n["prompt"],
                "```",
                "",
                "Expected output - JSON matching this schema:",
                "",
                "```json",
                json.dumps(graph["schemas"][n["schema"]], ensure_ascii=False, indent=2),
                "```",
            ]
        lines.append("")
    human = [n for n in graph["nodes"] if n["kind"] == "human"][0]
    lines += [f"## Terminal: `{human['id']}` (human)", "", human["prompt"], "",
              "Do not change the project while the run is open: `record` compares the project's git state with",
              "the state stored at approval and refuses on any difference.",
              "Then: `record --result result.json --runtime serial`, show the synthesis to the owner, `close --decision ...`."]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_init(a) -> int:
    run_dir = contained_run_dir(a.run_dir)
    p = paths(run_dir)
    if p["graph"].exists():
        raise Refused(f"graph.json already exists: {p['graph']} - a new run takes a new directory")
    run_id = run_dir.name
    if a.from_graph:
        graph = read_json(Path(a.from_graph), "--from graph")
        if isinstance(graph, dict):
            graph["runId"] = run_id
    else:
        if a.template not in TEMPLATES:
            raise Refused(f"unknown template {a.template!r}; known: {', '.join(TEMPLATES)}")
        if not a.module:
            raise Refused("--module PATH is required for the module-neighbour-check template")
        project = a.project or str(Path.cwd())
        task = a.task or f"проверка модуля {a.module} по четырём классам (владелец, валюта и сумма, дедуп, время)"
        graph = build_template(run_id, project, a.module, task)
    errs = validate_graph(graph)
    if errs:
        raise Refused("refusing to write an invalid graph: " + "; ".join(errs))
    write_json(p["graph"], graph)
    digest = graph_digest(graph)
    print(f"graph: {p['graph']}")
    print(f"graphDigest: {digest}")
    print("state: designed")
    print("next: show the graph to the owner; `approve --digest " + digest + " --by <owner>` only on an explicit yes")
    return 0


def cmd_validate(a) -> int:
    graph = read_json(paths(contained_run_dir(a.run_dir))["graph"], "graph.json")
    errs = validate_graph(graph)
    if errs:
        print("INVALID")
        for e in errs:
            print("  " + e)
        return 1
    print(f"VALID graphDigest {graph_digest(graph)}")
    return 0


def cmd_digest(a) -> int:
    graph = read_json(paths(contained_run_dir(a.run_dir))["graph"], "graph.json")
    print(graph_digest(graph))
    return 0


def cmd_approve(a) -> int:
    run_dir = contained_run_dir(a.run_dir)
    p = paths(run_dir)
    for key in ("nodes", "receipt", "decision"):
        if p[key].exists():
            raise Refused(f"{p[key].name} already exists: a recorded or closed run cannot be re-approved - "
                          "a new graph takes a new run directory")
    graph, digest = load_valid_graph(run_dir)
    if not SHA_RE.match(a.digest or ""):
        raise Refused("--digest must be the 64-hex graph digest printed by init/validate")
    if a.digest != digest:
        raise Refused(f"digest mismatch: the graph is {digest[:12]}, you approved {a.digest[:12]} - approve what the validator printed")
    if not (a.by or "").strip():
        raise Refused("--by NAME is required: the approval names the human")
    tree = project_tree_state(project_root(run_dir))
    approval = {"graphDigest": digest, "runId": graph["runId"], "by": a.by.strip(), "at": now_iso(a.at),
                "projectTree": tree}
    write_json(paths(run_dir)["approval"], approval)
    print(f"approved graphDigest {digest} by {approval['by']} at {approval['at']}")
    print("state: approved")
    return 0


def cmd_emit(a, kind: str) -> int:
    run_dir = contained_run_dir(a.run_dir)
    graph, digest = load_valid_graph(run_dir)
    load_matching_approval(run_dir, digest, graph)
    sys.stdout.write(emit_workflow(graph, digest) if kind == "workflow" else emit_serial(graph, digest))
    return 0


def node_markdown(node_id: str, role: str, output) -> str:
    body = json.dumps(output, ensure_ascii=False, indent=2)
    return f"# node {node_id} (role {role})\n\n```json\n{body}\n```\n"


def atomic_write_json(path: Path, obj) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_record(a) -> int:
    run_dir = contained_run_dir(a.run_dir)
    p = paths(run_dir)
    graph, digest = load_valid_graph(run_dir)
    approval = load_matching_approval(run_dir, digest, graph)
    if p["receipt"].exists():
        raise Refused(f"receipt.json already exists: {p['receipt']} - a rerun takes a new run directory")
    before = approval.get("projectTree")
    if not isinstance(before, dict) or before.get("git") is not True:
        raise Refused("approval.json carries no project tree state - approve the graph again")
    changed = tree_differences(before, project_tree_state(project_root(run_dir)))
    if changed:
        raise Refused("the project changed between approve and record, so a node did not stay read-only "
                      "(or someone edited the project during the run): " + ", ".join(changed[:12])
                      + (f" (+{len(changed) - 12} more)" if len(changed) > 12 else ""))
    if p["nodes"].exists():
        raise Refused(f"nodes/ already exists without a receipt (a partial run): {p['nodes']} - a rerun takes a new run directory")
    if a.runtime not in ("workflow", "serial"):
        raise Refused("--runtime must be workflow or serial")
    result = read_json(Path(a.result), "--result file")
    if not isinstance(result, dict):
        raise Refused("--result must be a JSON object {graphDigest, nodes}")
    if result.get("graphDigest") != digest:
        raise Refused(f"result graphDigest {str(result.get('graphDigest'))[:12]} is not the approved graph {digest[:12]}")
    outputs = result.get("nodes")
    if not isinstance(outputs, dict):
        raise Refused("result.nodes must be an object node id -> output")
    agent_nodes = [n for n in graph["nodes"] if n["kind"] == "agent"]
    agent_ids = [n["id"] for n in agent_nodes]
    missing = [i for i in agent_ids if i not in outputs or outputs[i] in (None, "", {}, [])]
    if missing:
        raise Refused("result has no output for node(s): " + ", ".join(missing) + " - a run with a missing node is not recorded")
    unknown = [i for i in outputs if i not in agent_ids]
    if unknown:
        raise Refused("result names node(s) outside the approved graph: " + ", ".join(unknown))
    bad: list[str] = []
    for n in agent_nodes:
        for e in instance_errors(graph["schemas"][n["schema"]], outputs[n["id"]], n["id"]):
            bad.append(e)
    if bad:
        raise Refused("node output does not match its schema: " + "; ".join(bad[:12])
                      + (f" (+{len(bad) - 12} more)" if len(bad) > 12 else ""))
    receipt_nodes = {}
    staging = Path(tempfile.mkdtemp(prefix=".nodes.", dir=str(run_dir)))
    try:
        for n in agent_nodes:
            md = node_markdown(n["id"], n["role"], outputs[n["id"]])
            data = md.encode("utf-8")
            (staging / f"{n['id']}.md").write_bytes(data)
            receipt_nodes[n["id"]] = {"sha256": sha256_bytes(data), "bytes": len(data)}
        os.rename(staging, p["nodes"])
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    receipt = {
        "graphDigest": digest,
        "runId": graph["runId"],
        "runtime": a.runtime,
        "at": now_iso(a.at),
        "resultSha256": sha256_bytes(canonical(result)),
        "nodes": receipt_nodes,
    }
    atomic_write_json(p["receipt"], receipt)
    print(f"recorded {len(agent_ids)} node(s) under {p['nodes']} runtime {a.runtime}")
    print(f"receipt: {p['receipt']}")
    print("state: recorded")
    return 0


def cmd_close(a) -> int:
    run_dir = contained_run_dir(a.run_dir)
    p = paths(run_dir)
    graph, digest = load_valid_graph(run_dir)
    load_matching_approval(run_dir, digest, graph)
    receipt = read_json(p["receipt"], "receipt.json (record the run first)")
    if receipt.get("graphDigest") != digest:
        raise Refused("receipt.json belongs to another graph digest")
    problems = receipt_mismatches(run_dir, receipt, graph)
    if problems:
        raise Refused("recorded evidence does not match receipt.json: " + "; ".join(problems))
    if p["decision"].exists():
        raise Refused(f"decision.json already exists: {p['decision']} - a closed run is immutable")
    if not (a.decision or "").strip() or not (a.by or "").strip():
        raise Refused("--decision TEXT and --by NAME are required: the human closes the run")
    decision = {"graphDigest": digest, "runId": graph["runId"], "by": a.by.strip(),
                "at": now_iso(a.at), "decision": a.decision.strip()}
    atomic_write_json(p["decision"], decision)
    print(f"closed by {decision['by']} at {decision['at']}")
    print("state: closed")
    return 0


def cmd_status(a) -> int:
    st = run_state(contained_run_dir(a.run_dir))
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Graph Lite run tool (ADR-013)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("run_dir")
    s.add_argument("--template", default="module-neighbour-check")
    s.add_argument("--module")
    s.add_argument("--task")
    s.add_argument("--project")
    s.add_argument("--from", dest="from_graph")
    s.set_defaults(fn=cmd_init)

    for name, fn in (("validate", cmd_validate), ("digest", cmd_digest), ("status", cmd_status)):
        s = sub.add_parser(name)
        s.add_argument("run_dir")
        s.set_defaults(fn=fn)

    s = sub.add_parser("approve")
    s.add_argument("run_dir")
    s.add_argument("--digest", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--at")
    s.set_defaults(fn=cmd_approve)

    for name, kind in (("emit-workflow", "workflow"), ("emit-serial", "serial")):
        s = sub.add_parser(name)
        s.add_argument("run_dir")
        s.set_defaults(fn=lambda a, k=kind: cmd_emit(a, k))

    s = sub.add_parser("record")
    s.add_argument("run_dir")
    s.add_argument("--result", required=True)
    s.add_argument("--runtime", required=True)
    s.add_argument("--at")
    s.set_defaults(fn=cmd_record)

    s = sub.add_parser("close")
    s.add_argument("run_dir")
    s.add_argument("--decision", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--at")
    s.set_defaults(fn=cmd_close)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except Refused as exc:
        print(f"REFUSED: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
