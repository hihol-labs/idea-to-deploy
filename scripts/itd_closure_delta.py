#!/usr/bin/env python3
"""Closure delta — prove that only closure records changed after a unit was verified.

Why this exists
---------------
A unit is verified on an exact tree: the adjudication receipt binds
`candidate.reviewedTree`. What gets committed or merged later is a different
tree - the goal harness writes the unit transition, the ledger-close appends
decisions and backlog entries, the acceptance contract moves the followup.
Until now "nothing else changed" was a claim checked by eye in every
ledger-close (REL-1.106.0 route). This tool turns it into an exit code.

The etalon comes from the harness, not from a list of allowed shapes
----------------------------------------------------------------------
Three pre-PR review rounds blocked a rule-list design on one mechanism: a
closure record of a shape the goal harness never writes was accepted (owner
decision 2026-09-29, .itd/DECISIONS.md). So the ledger delta is judged against
the harness itself: the verified tree is extracted into a temporary
repository, the goal harness of THAT tree (`skills/goal/scripts/
itd_goal_verify.py`) performs the verify transition of the receipt's unit
there (tier `low`, command `exit 0`, so no oracle and no receipt run inside
the copy), and the candidate's GOAL.json, STATE.json and appended events must
equal what the harness wrote, after normalizing only the fields the harness
cannot reproduce deterministically:

* timestamps (`updatedAt`, `verifiedAt`, `completedAt`, event `at`) -
  ISO-8601 UTC, not before the reviewed tree's `updatedAt` minus a 60-second
  clock-skew allowance (WSL2 steps its clock backwards; the review broker
  tolerates the same `MAX_CLOCK_SKEW_SECONDS`), not in the future;
* event `id` and `transaction` - the shape the harness event has;
* `evidence` - the harness `exit 0` record, identical in the unit and in its
  event;
* `riskTier` and `verificationCommand` of the unit - the reviewed tree's
  values (substituted inside the copy only);
* `verificationReceipt` - present for a medium/high unit and equal, key for
  key, to the record the harness derives from THIS receipt file (path
  relative to the project root, sha256 of its bytes, receiptSha256, outcome,
  machinePath, machineSha256).

The harness takes the transition times from separate clock reads in the order
verifiedAt, updatedAt, event `at`, so they are not required to be equal:
`verifiedAt <= updatedAt <= at`, the event `at` equals
`currentUnit.completedAt` (the projection copies it), and all of them lie
within one minute of verifiedAt (a longer lock wait inside the harness would
read as a violation - a deliberate bound, not a harness invariant). Everything else is a byte-for-byte harness invariant.
The appended journal lines are exactly the transition events the harness
wrote, in order - nothing else. Hook lines and harness attempts between the
review and the closure are not replayed by the etalon and therefore not
accepted: a closure receipt is minted on the tree right before the final
verify (the recorded ledger-close deltas carry only the transition events).
`handoffState` is never a transition field here: the harness writes it only
for working-deadline units, which the tool refuses, so a pre-existing handoff
stays byte-identical and an acknowledgement after the review is not accepted.

Other closure records keep their own rules: the move of the unit's
`activeFollowup` to the end of `closedFollowups` in
`.itd/ACCEPTANCE_CONTRACT.json`; whole UTF-8 lines appended at the end of
`.itd/DECISIONS.md`; whole UTF-8 lines inserted into `BACKLOG.md` (owner
decision 2026-09-28). Ledger records change only for a unit verified in the
later GOAL.json; the later GOAL.json and STATE.json also pass
`scripts/validate_state.py` of the reviewed tree. Any other path, any added or
deleted file and any mode change is rejected. Receipt integrity is not
re-checked here - that is `itd_verification_loop.py check`. A working-deadline
unit (host clock, live policy) and a bounded (sealed) unit (command sealed by
fingerprint) cannot be replayed with a substituted command: the tool refuses
them itself with exit 2 before touching the copy. A harness or validator run
in the copy is bounded by `ITD_CLOSURE_DELTA_TIMEOUT` seconds (default 600);
a run that does not finish, or cannot start, is an input error, not a traceback.

Usage:
  itd_closure_delta.py --receipt <adjudication.json> --tree <tree-ish> [--repo DIR]

Exit: 0 silent - the delta is closure records only; 1 - violations, one
`path: WHY` + `FIX:` per finding on stderr; 2 - input error (receipt, tree,
repository, harness etalon). No arguments - a quiet no-op.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

GOAL = ".itd-memory/GOAL.json"
STATE = ".itd-memory/STATE.json"
EVENTS = ".itd-memory/events.jsonl"
ACCEPTANCE = ".itd/ACCEPTANCE_CONTRACT.json"
DECISIONS = ".itd/DECISIONS.md"
BACKLOG = "BACKLOG.md"
HARNESS = "skills/goal/scripts/itd_goal_verify.py"
VALIDATOR = "scripts/validate_state.py"
LEDGER_RECORDS = (GOAL, STATE, EVENTS, ACCEPTANCE)
TRANSITION_RECORDS = (GOAL, STATE, EVENTS)
REGULAR_FILE = "100644"
HEX_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
ISO_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
RECEIPT_TIERS = {"medium", "high"}
FOLLOWUP_EMPTY_KEYS = {"unitId", "status", "note"}
MISSING = object()


HARNESS_TIMEOUT = 600  # seconds for one harness or validator run in the copy
WORKING_DEADLINE_PROFILE = "working_deadline"  # boundaries, spelled as in the goal harness
BOUNDED_MODE = "bounded_autonomous"


def harness_timeout() -> int:
    """`ITD_CLOSURE_DELTA_TIMEOUT` (positive seconds) overrides the default; anything else is ignored."""
    raw = os.environ.get("ITD_CLOSURE_DELTA_TIMEOUT", "")
    return int(raw) if raw.isascii() and raw.isdigit() and int(raw) > 0 else HARNESS_TIMEOUT


class InputError(Exception):
    """The inputs cannot be evaluated (exit 2)."""


@dataclass
class Closure:
    """What the receipt says was verified, plus the unit as the later GOAL records it."""
    unit_id: str
    receipt_sha256: str
    receipt_path: Path
    receipt: dict
    receipt_bytes: bytes
    unit: dict | None = None
    state: dict | None = None  # the later STATE.json, for the completedAt/at invariant
    updated_at: object = None  # the later GOAL updatedAt, for the clock order
    receipt_record: dict | None = None  # what the harness writes as unit.verificationReceipt


@dataclass
class Etalon:
    """What the harness of the reviewed tree wrote for the verify transition."""
    goal: dict
    state: dict | None
    events: list[dict]
    tier: str
    base_updated_at: str
    event_prefix: str = ""
    event_keys: list[str] = field(default_factory=list)
    segments: list[str] | None = None  # top-level `&&` segments of the unit command, per the harness


class Finding:
    def __init__(self, path: str, why: str, fix: str) -> None:
        self.path, self.why, self.fix = path, why, fix

    def render(self) -> str:
        return f"{self.path}: {self.why}\n  FIX: {self.fix}"


FIXES = {
    GOAL: "Leave the unit transition to the goal harness; any other ledger edit is its own reviewed unit.",
    STATE: "Leave STATE.json to the goal harness projection of the same unit.",
    EVENTS: "Only append the events the harness writes; never rewrite the journal.",
    ACCEPTANCE: "Move the unit's activeFollowup to the end of closedFollowups and nothing else.",
    DECISIONS: "Append the new entry at the end of the journal; history is never edited.",
    BACKLOG: "Insert new lines; changing or removing an entry is a reviewed change, not a closure.",
}


# --- git and parsing ---------------------------------------------------------

def git(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if proc.returncode != 0:
        raise InputError(f"git {' '.join(args)}: "
                         f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def resolve_tree(repo: Path, treeish: str, label: str) -> str:
    try:
        return git(repo, "rev-parse", "--verify", "--quiet",
                   treeish + "^{tree}").decode().strip()
    except InputError:
        raise InputError(f"{label} {treeish!r} is not a tree in {repo}") from None


def load_receipt(path: Path) -> tuple[Closure, str]:
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"receipt {path}: cannot read JSON ({exc})") from None
    if not isinstance(data, dict):
        raise InputError(f"receipt {path}: not a JSON object")
    if data.get("kind") != "adjudication":
        raise InputError(f"receipt {path}: kind is {data.get('kind')!r}, "
                         "expected 'adjudication'")
    if data.get("outcome") != "PASSED":
        raise InputError(f"receipt {path}: outcome is {data.get('outcome')!r}, "
                         "a verified tree comes only from a PASSED receipt")
    unit_id = data.get("unitId")
    digest = data.get("receiptSha256")
    candidate = data.get("candidate")
    tree = candidate.get("reviewedTree") if isinstance(candidate, dict) else None
    if not isinstance(unit_id, str) or not unit_id:
        raise InputError(f"receipt {path}: unitId is missing")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise InputError(f"receipt {path}: receiptSha256 is missing")
    if not isinstance(tree, str) or not HEX_ID.fullmatch(tree):
        raise InputError(f"receipt {path}: candidate.reviewedTree is not a tree id")
    return Closure(unit_id, digest, path, data, raw), tree


def receipt_record(ctx: Closure, repo: Path) -> dict:
    """The verificationReceipt the harness writes for this receipt: every field is derived."""
    try:
        relative = ctx.receipt_path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        raise InputError(f"receipt {ctx.receipt_path} lies outside {repo}; the harness records it "
                         "relative to the project root") from None
    deps = ctx.receipt.get("dependencies")
    machine = deps.get("machine") if isinstance(deps, dict) else None
    if not isinstance(machine, dict):
        raise InputError(f"receipt {ctx.receipt_path}: dependencies.machine is missing")
    return {
        "path": relative,
        "sha256": hashlib.sha256(ctx.receipt_bytes).hexdigest(),
        "receiptSha256": ctx.receipt_sha256,
        "outcome": str(ctx.receipt.get("outcome") or ""),
        "machinePath": str(machine.get("path") or ""),
        "machineSha256": str(machine.get("sha256") or ""),
    }


def changed_paths(repo: Path, old: str, new: str) -> list[tuple[str, str, str, str]]:
    raw = git(repo, "diff-tree", "-r", "--no-renames", "-z", old, new)
    fields = raw.split(b"\0")
    out = []
    i = 0
    while i + 1 < len(fields) and fields[i]:
        meta = fields[i].decode().lstrip(":").split()
        path = fields[i + 1].decode("utf-8", "surrogateescape")
        out.append((path, meta[0], meta[1], meta[4]))
        i += 2
    return out


def blob(repo: Path, tree: str, path: str) -> bytes:
    return git(repo, "cat-file", "blob", f"{tree}:{path}")


def no_duplicates(pairs: list) -> dict:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate key {sorted(k for k in keys if keys.count(k) > 1)[0]!r}")
    return dict(pairs)


def parse_json(data: bytes) -> object:
    return json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates)


def json_at(repo: Path, tree: str, path: str) -> dict | None:
    try:
        value = parse_json(blob(repo, tree, path))
    except (InputError, UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def unit_in(goal: dict | None, unit_id: str) -> dict:
    units = goal.get("units") if goal else None
    return next((u for u in units or [] if isinstance(u, dict) and u.get("id") == unit_id), {})


def lines(data: bytes) -> list[bytes]:
    return re.findall(rb"[^\n]*\n|[^\n]+$", data)


def differs(old: dict, new: dict, key: str) -> bool:
    return old.get(key, MISSING) != new.get(key, MISSING)


def unit_verified(ctx: Closure) -> bool:
    return (ctx.unit or {}).get("status") == "verified"


# --- the harness etalon -------------------------------------------------------

class Workspace:
    """The reviewed tree extracted into a temporary repository."""

    def __init__(self, repo: Path, tree: str) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="itd-closure-delta-"))
        self.repo = self.root / "reviewed"
        self.repo.mkdir()
        archive = git(repo, "archive", "--format=tar", tree)
        try:
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(self.repo, filter="data")  # no links or paths outside the copy
                else:
                    tar.extractall(self.repo)
        except (tarfile.TarError, OSError) as exc:
            self.close()
            raise InputError(f"the reviewed tree {tree} could not be extracted into a copy: {exc}") from None
        # The copy is its own repository: no GIT_* of the caller, no live project pointer.
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_") and k != "CLAUDE_PROJECT_DIR"}
        self.env["PYTHONUTF8"] = "1"
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], capture_output=True, env=self.env)
        self._harness = None

    def harness(self):
        """The harness module of the reviewed tree, for its own command splitter."""
        if self._harness is None:
            path = self.repo / HARNESS
            if not path.is_file():
                raise InputError(f"the reviewed tree has no {HARNESS}")
            spec = importlib.util.spec_from_file_location("itd_closure_delta_harness", path)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as exc:  # noqa: BLE001 - any import failure is an input error
                raise InputError(f"the harness of the reviewed tree does not import: {exc}") from None
            self._harness = module
        return self._harness

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def run(self, script: str, *args: str) -> subprocess.CompletedProcess:
        path = self.repo / script
        if not path.is_file():
            raise InputError(f"the reviewed tree has no {script}; the etalon needs the harness "
                             "of the tree that verified the unit")
        timeout = harness_timeout()
        try:
            return subprocess.run([sys.executable, str(path), *args], cwd=str(self.repo),
                                  capture_output=True, encoding="utf-8", errors="replace",
                                  env=self.env, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise InputError(f"{script} of the reviewed tree did not finish within {timeout}s "
                             "in the copy") from None
        except OSError as exc:
            raise InputError(f"{script} of the reviewed tree could not run in the copy: {exc}") from None

    def write_json(self, rel: str, value: object) -> None:
        (self.repo / rel).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")

    def read_json(self, rel: str) -> dict | None:
        path = self.repo / rel
        if not path.is_file():
            return None
        try:
            value = parse_json(path.read_bytes())
        except (UnicodeDecodeError, ValueError):
            return None
        return value if isinstance(value, dict) else None


def last_line(proc: subprocess.CompletedProcess) -> str:
    rows = [r for r in (proc.stdout + proc.stderr).splitlines() if r.strip()]
    return rows[-1][:200] if rows else f"rc {proc.returncode}"


def build_etalon(ws: Workspace, ctx: Closure) -> Etalon:
    goal = ws.read_json(GOAL)
    if goal is None:
        raise InputError(f"the reviewed tree has no readable {GOAL}")
    unit = unit_in(goal, ctx.unit_id)
    if not unit:
        raise InputError(f"the reviewed tree's {GOAL} has no unit {ctx.unit_id!r}")
    tier = str(unit.get("riskTier") or "unknown")
    receipt_tier = (ctx.receipt.get("candidate") or {}).get("riskTier")
    if not isinstance(receipt_tier, str) or not receipt_tier:
        raise InputError(f"receipt {ctx.receipt_path}: candidate.riskTier is missing")
    if receipt_tier != tier:
        raise InputError(f"receipt {ctx.receipt_path}: candidate.riskTier {receipt_tier!r} is not the "
                         f"reviewed unit's riskTier {tier!r}; the receipt did not verify this unit")
    had_tier, had_command = "riskTier" in unit, "verificationCommand" in unit
    command = unit.get("verificationCommand")
    base_updated_at = str(goal.get("updatedAt") or "")
    if ws.read_json(STATE) is None:
        raise InputError(f"the reviewed tree has no readable {STATE}; a goal ledger without a STATE "
                         "mirror is outside this tool")
    # The boundaries are decided here, not left to the harness of the copy: a deadline unit
    # needs the host clock and the live policy, a bounded unit seals its command by fingerprint.
    deadline = unit.get("deadlineState")
    if isinstance(deadline, dict) and deadline.get("profile") == WORKING_DEADLINE_PROFILE:
        raise InputError(f"the etalon cannot replay a working-deadline unit ({ctx.unit_id!r}: "
                         f"deadlineState.profile {WORKING_DEADLINE_PROFILE!r})")
    policy = goal.get("runPolicy") if isinstance(goal.get("runPolicy"), dict) else {}
    run_state = unit.get("runState") if isinstance(unit.get("runState"), dict) else {}
    if (policy.get("mode") == BOUNDED_MODE or policy.get("sealedFingerprint")
            or run_state.get("verificationFingerprint")):
        raise InputError(f"the etalon cannot replay a sealed (bounded) unit ({ctx.unit_id!r}: the "
                         "verification command is sealed by fingerprint and cannot be substituted)")
    # The copy verifies without the oracle and without a receipt: the shape of
    # the transition does not depend on either, both are restored below.
    unit["riskTier"] = "low"
    unit["verificationCommand"] = "exit 0"
    ws.write_json(GOAL, goal)
    before = (ws.repo / EVENTS).read_bytes() if (ws.repo / EVENTS).is_file() else b""
    proc = ws.run(HARNESS, ctx.unit_id)
    if proc.returncode != 0:
        raise InputError(f"the harness of the reviewed tree could not verify {ctx.unit_id!r} "
                         f"in the copy: {last_line(proc)}")
    after_goal = ws.read_json(GOAL)
    if after_goal is None:
        raise InputError(f"the harness left no readable {GOAL} in the copy")
    etalon_unit = unit_in(after_goal, ctx.unit_id)
    for key, had, value in (("riskTier", had_tier, tier), ("verificationCommand", had_command, command)):
        if had:
            etalon_unit[key] = value
        else:
            etalon_unit.pop(key, None)
    state = ws.read_json(STATE)
    if state is not None:
        current = state.get("currentUnit")
        if isinstance(current, dict) and current.get("id") == ctx.unit_id:
            current["riskTier"] = tier
    after = (ws.repo / EVENTS).read_bytes() if (ws.repo / EVENTS).is_file() else b""
    if not after.startswith(before):
        raise InputError("the harness rewrote the journal in the copy")
    events = [json.loads(row) for row in after[len(before):].decode("utf-8").splitlines() if row]
    verified = next((e for e in events if isinstance(e, dict) and e.get("decision") == "verified"), None)
    if verified is None:
        raise InputError("the harness wrote no verified event in the copy")
    event_id = str(verified.get("id") or "")
    transaction = str(verified.get("transaction") or "")
    prefix = event_id[: len(event_id) - len(transaction)] if event_id.endswith(transaction) else ""
    prefix = re.sub(r"\d+-$", "", prefix)  # `evt-goal-<seconds>-` -> `evt-goal-`
    segments = ws.harness().split_top_level_and(command) if isinstance(command, str) else None
    return Etalon(after_goal, state, events, tier, base_updated_at, prefix, list(verified), segments)


# --- normalization against the etalon ----------------------------------------

CLOCK_SKEW = dt.timedelta(minutes=5)
PAST_SKEW = dt.timedelta(seconds=60)  # a backwards clock step between the review and the verify


def check_time(value: object, label: str, base: str, errs: list[str]) -> None:
    if not isinstance(value, str) or not ISO_UTC.fullmatch(value):
        errs.append(f"{label} is not an ISO-8601 UTC timestamp: {value!r}")
        return
    try:
        moment = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        errs.append(f"{label} is not a real UTC moment: {value!r}")
        return
    base_moment = parse_time(base) if base else None
    if base_moment is not None and moment < base_moment - PAST_SKEW:
        errs.append(f"{label} {value} is earlier than the reviewed tree's updatedAt {base}")
    elif moment > dt.datetime.now(dt.timezone.utc) + CLOCK_SKEW:
        errs.append(f"{label} {value} lies in the future")


TRANSITION_WINDOW = dt.timedelta(minutes=1)


def parse_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not ISO_UTC.fullmatch(value):
        return None
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def transition_window(first: object, second: object, first_label: str, second_label: str) -> list[str]:
    """Two clock reads of one harness transition: ordered and within the window."""
    a, b = parse_time(first), parse_time(second)
    if a is None or b is None:
        return []  # the shape errors are reported by check_time
    if b < a:
        return [f"{second_label} {second} is earlier than {first_label} {first}"]
    if b - a > TRANSITION_WINDOW:
        return [f"{second_label} {second} is more than {TRANSITION_WINDOW} after {first_label} {first}"]
    return []


def evidence_errors(evidence: object, segments: list[str] | None, label: str) -> list[str]:
    """The green record the harness writes for THIS command: one row per top-level `&&`
    segment (`<segment>: exit 0, stdout sha256 <16 hex>, <last line>`), else `exit 0: <line>`."""
    if not isinstance(evidence, str) or not evidence.strip():
        return [f"{label} evidence is empty"]
    rows = evidence.split("\n")
    if segments and len(segments) > 1:
        if len(rows) != len(segments):
            return [f"{label} evidence has {len(rows)} rows for {len(segments)} command segments"]
        return [f"{label} evidence row {n} is not the harness record of segment {seg!r}"
                for n, (row, seg) in enumerate(zip(rows, segments), 1)
                if not re.fullmatch(re.escape(seg) + r": exit 0, stdout sha256 [0-9a-f]{16}, .+", row)]
    if len(rows) != 1 or not re.fullmatch(r"exit 0: .+", rows[0]):
        return [f"{label} evidence is not the harness `exit 0: <line>` record of a single command"]
    return []


def diff_paths(a: object, b: object, where: str = "") -> list[str]:
    """Where two JSON values differ, as dotted paths (key order matters)."""
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b):
            extra = [k for k in a if k not in b]
            missing = [k for k in b if k not in a]
            if extra or missing:
                return [f"{where or '$'} keys: extra {extra}, missing {missing}"]
            return [f"{where or '$'} key order {list(a)} != {list(b)}"]
        out: list[str] = []
        for key in a:
            out.extend(diff_paths(a[key], b[key], f"{where}.{key}" if where else key))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{where or '$'} length {len(a)} != {len(b)}"]
        out = []
        for n, (x, y) in enumerate(zip(a, b)):
            out.extend(diff_paths(x, y, f"{where}[{n}]"))
        return out
    if a != b or type(a) is not type(b):
        return [f"{where or '$'}: candidate {a!r} != harness {b!r}"]
    return []


def normalize_goal(goal: dict, ctx: Closure, et: Etalon, candidate: bool) -> tuple[dict, list[str]]:
    errs: list[str] = []
    goal = json.loads(json.dumps(goal))
    unit = unit_in(goal, ctx.unit_id)
    if candidate:
        check_time(goal.get("updatedAt"), "updatedAt", et.base_updated_at, errs)
        check_time(unit.get("verifiedAt"), f"unit {ctx.unit_id!r} verifiedAt", et.base_updated_at, errs)
        errs.extend(transition_window(unit.get("verifiedAt"), goal.get("updatedAt"),
                                      "the unit verifiedAt", "updatedAt"))
        errs.extend(evidence_errors(unit.get("evidence"), et.segments, f"unit {ctx.unit_id!r}"))
        receipt = unit.get("verificationReceipt", MISSING)
        if receipt is MISSING:
            if et.tier in RECEIPT_TIERS:
                errs.append(f"unit {ctx.unit_id!r}: a {et.tier} unit is verified without a "
                            "verificationReceipt")
        elif receipt != ctx.receipt_record or list(receipt) != list(ctx.receipt_record or {}):
            errs.append(f"unit {ctx.unit_id!r}: verificationReceipt is not the record the harness "
                        f"writes for this receipt (path, sha256, receiptSha256, outcome, machinePath, "
                        "machineSha256)")
    # The receipt binding is checked above for the candidate; the copy verified without a
    # receipt and may carry a stale one from before a recheck, so the key leaves both sides.
    unit.pop("verificationReceipt", None)
    if "updatedAt" in goal:
        goal["updatedAt"] = "<time>"
    units = goal.get("units")
    if (candidate and goal.get("status") == "done" and isinstance(units, list)
            and all(isinstance(u, dict) and u.get("status") in ("verified", "skipped") for u in units)):
        # /goal Step 3 closes the ledger by hand once every unit is verified or skipped.
        goal["status"] = "active"
    if unit:
        if "verifiedAt" in unit:
            unit["verifiedAt"] = "<time>"
        if "evidence" in unit:
            unit["evidence"] = "<evidence>"
    # handoffState is not normalized: the harness writes it only for working-deadline units
    # (refused above), so whatever the reviewed tree carried must survive byte for byte.
    return goal, errs


def normalize_state(state: dict, ctx: Closure, et: Etalon, candidate: bool) -> tuple[dict, list[str]]:
    errs: list[str] = []
    state = json.loads(json.dumps(state))
    current = state.get("currentUnit")
    if isinstance(current, dict) and current.get("id") == ctx.unit_id and "completedAt" in current:
        if candidate:
            check_time(current.get("completedAt"), "currentUnit.completedAt", et.base_updated_at, errs)
            errs.extend(transition_window((ctx.unit or {}).get("verifiedAt"), current.get("completedAt"),
                                          "the unit verifiedAt", "currentUnit.completedAt"))
        current["completedAt"] = "<time>"
    return state, errs


def compare_json(path: str, candidate: dict, etalon: dict, ctx: Closure, et: Etalon) -> list[str]:
    normalize = normalize_goal if path == GOAL else normalize_state
    cand, errs = normalize(candidate, ctx, et, True)
    ref, _ = normalize(etalon, ctx, et, False)
    for where in diff_paths(cand, ref)[:6]:
        errs.append(f"differs from the harness transition at {where}")
    return errs


# --- events ------------------------------------------------------------------

def event_shape_errors(event: dict, ctx: Closure, et: Etalon, label: str) -> list[str]:
    errs: list[str] = []
    if list(event) != et.event_keys:
        return [f"{label} does not have the harness event fields {et.event_keys} "
                f"(got {list(event)})"]
    if event.get("actor") != "harness" or event.get("type") != "unit" or event.get("name") != ctx.unit_id:
        errs.append(f"{label} is not a harness unit event of {ctx.unit_id!r} (actor "
                    f"{event.get('actor')!r}, type {event.get('type')!r}, name {event.get('name')!r})")
    transaction = event.get("transaction")
    if not isinstance(transaction, str) or not re.fullmatch(r"[0-9a-f]{32}", transaction):
        errs.append(f"{label} transaction is not a harness transaction id: {transaction!r}")
    event_id = event.get("id")
    if (not isinstance(event_id, str) or not event_id.startswith(et.event_prefix)
            or not re.fullmatch(r"\d+-" + re.escape(str(transaction)), event_id[len(et.event_prefix):])):
        errs.append(f"{label} id {event_id!r} is not the harness shape "
                    f"{et.event_prefix}<seconds>-<transaction>")
    check_time(event.get("at"), f"{label} at", et.base_updated_at, errs)
    if event.get("ledger") != et.events[0].get("ledger"):
        errs.append(f"{label} ledger {event.get('ledger')!r} != {et.events[0].get('ledger')!r}")
    return errs


def split_events(old: bytes, new: bytes) -> tuple[list[tuple[int, dict]], list[str]]:
    """The appended journal lines as parsed objects, or why the append is not an append."""
    if old and not old.endswith(b"\n"):
        return [], ["the old content does not end with a newline, an append would edit its last line"]
    if not new.startswith(old):
        return [], ["the old content is not a prefix of the new one - an existing line was edited or removed"]
    tail = new[len(old):]
    if tail and not tail.endswith(b"\n"):
        return [], ["the appended part does not end with a newline - a partial line"]
    errs: list[str] = []
    appended: list[tuple[int, dict]] = []
    for n, raw in enumerate(tail.split(b"\n")[:-1], 1):
        try:
            event = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
        except (UnicodeDecodeError, ValueError) as exc:
            errs.append(f"appended line {n} is not UTF-8 JSON ({exc})")
            continue
        if not isinstance(event, dict):
            errs.append(f"appended line {n} is not a JSON object")
            continue
        if not isinstance(event.get("type"), str) or not event["type"]:
            errs.append(f"appended line {n} has no type")
            continue
        appended.append((n, event))
    return appended, errs


def check_events(appended: list[tuple[int, dict]], ctx: Closure, et: Etalon | None) -> list[str]:
    """The appended journal lines are the harness transition events, in order, and nothing else.

    Hook lines and harness attempts between the review and the closure are not replayed by the
    etalon, so they are not accepted either: a closure receipt is minted on the tree right before
    the final verify, and the recorded ledger-close deltas carry exactly the transition events.
    """
    errs: list[str] = []
    if et is None:
        return [f"appended line {n} was appended but the unit {ctx.unit_id!r} was not verified by "
                "the harness in this delta" for n, _event in appended]
    expected = list(et.events)
    unit_evidence = (ctx.unit or {}).get("evidence")
    for n, event in appended:
        label = f"appended line {n}"
        if not expected:
            errs.append(f"{label} is not part of the harness transition (decision "
                        f"{event.get('decision')!r}); the transition ended one line earlier")
            continue
        ref = expected.pop(0)
        if event.get("decision") != ref.get("decision"):
            errs.append(f"{label} decision {event.get('decision')!r} is not the harness "
                        f"{ref.get('decision')!r} event of the transition")
            continue
        shape = event_shape_errors(event, ctx, et, label)
        if shape:
            errs.extend(shape)
            continue
        if ref.get("decision") == "verified":
            if event.get("evidence") != unit_evidence:
                errs.append(f"{label} evidence differs from the unit evidence in GOAL.json")
            errs.extend(transition_window((ctx.unit or {}).get("verifiedAt"), event.get("at"),
                                          "the unit verifiedAt", f"{label} at"))
            # The harness reads the clock in this order: verifiedAt, updatedAt, event at.
            errs.extend(transition_window(ctx.updated_at, event.get("at"), "updatedAt", f"{label} at"))
            # The STATE comparison already rejects a currentUnit that is not this unit.
            current = (ctx.state or {}).get("currentUnit")
            completed = current.get("completedAt") if isinstance(current, dict) else None
            if completed is not None and event.get("at") != completed:
                errs.append(f"{label} at differs from currentUnit.completedAt, which the "
                            "harness copies from this event")
        elif event.get("evidence") in ("", None):
            errs.append(f"{label} has no evidence")
    for ref in expected:
        errs.append(f"the harness {ref.get('decision')} event of {ctx.unit_id!r} was not appended")
    return errs


# --- other closure records ----------------------------------------------------

def check_acceptance(old: dict, new: dict, ctx: Closure) -> list[str]:
    errs = []
    for key in sorted(set(old) | set(new)):
        if key not in ("activeFollowup", "closedFollowups") and differs(old, new, key):
            errs.append(f"key {key!r} changed")
    active, closed_old = old.get("activeFollowup"), old.get("closedFollowups")
    empty, closed_new = new.get("activeFollowup"), new.get("closedFollowups")
    if active == empty and closed_old == closed_new:
        return errs
    if not isinstance(active, dict) or active.get("unitId") != ctx.unit_id:
        owner = active.get("unitId") if isinstance(active, dict) else active
        return errs + [f"followups changed but activeFollowup belongs to {owner!r}, "
                       f"not to {ctx.unit_id!r}"]
    if (not isinstance(empty, dict) or not set(empty) <= FOLLOWUP_EMPTY_KEYS
            or empty.get("unitId") != "" or empty.get("status") != "none"):
        errs.append("new activeFollowup is not the empty record {unitId: '', status: 'none', note?}")
    if (not isinstance(closed_old, list) or not isinstance(closed_new, list)
            or len(closed_new) != len(closed_old) + 1 or closed_new[:-1] != closed_old):
        return errs + ["closedFollowups is not the old list plus one record at the end"]
    moved = closed_new[-1]
    if not isinstance(moved, dict):
        return errs + ["the moved followup is not an object"]
    if moved.get("status") != "closed":
        errs.append(f"moved followup status is {moved.get('status')!r}, expected 'closed'")
    for key in ("closedAt", "closureEvidence"):
        value = moved.get(key)
        if key in active:
            errs.append(f"the active followup already had {key}")
        elif not isinstance(value, str) or not value.strip():
            errs.append(f"moved followup {key} is missing or empty")
    for key in sorted(set(active) | set(moved)):
        if key not in ("status", "closedAt", "closureEvidence") and differs(active, moved, key):
            errs.append(f"moved followup key {key!r} differs from the active followup")
    return errs


def whole_utf8_lines(part: bytes, label: str) -> list[str]:
    """Appended or inserted text is complete UTF-8 lines, never a fragment."""
    if not part:
        return []
    try:
        part.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{label} is not UTF-8 ({exc})"]
    if not part.endswith(b"\n"):
        return [f"{label} does not end with a newline - a partial line"]
    return []


def check_appended_text(old: bytes, new: bytes) -> list[str]:
    if old and not old.endswith(b"\n"):
        return ["the old content does not end with a newline, an append would edit its last line"]
    if not new.startswith(old):
        return ["the old content is not a prefix of the new one - an entry was edited, removed "
                "or inserted before the end"]
    return whole_utf8_lines(new[len(old):], "the appended part")


def check_inserted_lines(old: bytes, new: bytes) -> list[str]:
    old_lines, new_lines = lines(old), lines(new)
    j = 0
    inserted: list[tuple[int, bytes]] = []
    for n, line in enumerate(new_lines, 1):
        if j < len(old_lines) and line == old_lines[j]:
            j += 1
        else:
            inserted.append((n, line))
    if j != len(old_lines):
        return [f"old line {j + 1} ({old_lines[j][:60].decode('utf-8', 'replace').rstrip()!r}) "
                "was removed or changed; only inserted lines are a closure"]
    errs: list[str] = []
    for n, line in inserted:
        errs.extend(whole_utf8_lines(line, f"inserted line {n}"))
    return errs


# --- evaluation ----------------------------------------------------------------

def evaluate(repo: Path, old: str, new: str, ctx: Closure) -> list[Finding]:
    ctx.receipt_record = receipt_record(ctx, repo)
    later_goal = json_at(repo, new, GOAL)
    ctx.state = json_at(repo, new, STATE)
    ctx.updated_at = (later_goal or {}).get("updatedAt")
    ctx.unit = unit_in(later_goal, ctx.unit_id) or None
    changed = changed_paths(repo, old, new)
    findings: list[Finding] = []
    modified: dict[str, tuple[bytes, bytes]] = {}
    for path, old_mode, new_mode, status in changed:
        if path not in FIXES:
            findings.append(Finding(path, f"not a closure record (status {status}) - the verified "
                                    "tree did not contain this change",
                                    "Re-verify the unit on the tree that carries it, or drop the change."))
            continue
        if old_mode != REGULAR_FILE or new_mode != REGULAR_FILE:  # A, D and T all change a mode
            findings.append(Finding(path, f"status {status}, mode {old_mode} -> {new_mode}; a closure "
                                    "only modifies an existing regular file", FIXES[path]))
            continue
        modified[path] = (blob(repo, old, path), blob(repo, new, path))
    if not unit_verified(ctx):
        # One rule for every ledger file: a closure record exists only for a verified unit.
        findings.extend(Finding(path, f"a closure record changed while the unit {ctx.unit_id!r} is "
                                "not verified in the later GOAL.json", FIXES[path])
                        for path in modified if path in LEDGER_RECORDS)
    parsed: dict[str, tuple[dict, dict]] = {}
    for path in (GOAL, STATE, ACCEPTANCE):
        if path not in modified:
            continue
        before, after = modified[path]
        try:
            a, b = parse_json(before), parse_json(after)
        except (UnicodeDecodeError, ValueError) as exc:
            findings.append(Finding(path, f"not valid JSON ({exc})", FIXES[path]))
            continue
        if not isinstance(a, dict) or not isinstance(b, dict):
            findings.append(Finding(path, "not a JSON object", FIXES[path]))
            continue
        parsed[path] = (a, b)
    if ACCEPTANCE in parsed:
        findings.extend(Finding(ACCEPTANCE, err, FIXES[ACCEPTANCE])
                        for err in check_acceptance(*parsed[ACCEPTANCE], ctx))
    if DECISIONS in modified:
        findings.extend(Finding(DECISIONS, err, FIXES[DECISIONS])
                        for err in check_appended_text(*modified[DECISIONS]))
    if BACKLOG in modified:
        findings.extend(Finding(BACKLOG, err, FIXES[BACKLOG])
                        for err in check_inserted_lines(*modified[BACKLOG]))
    transition = any(path in modified for path in TRANSITION_RECORDS)
    if not transition:
        return findings
    try:
        old_events, new_events = modified.get(EVENTS) or (blob(repo, old, EVENTS),) * 2
    except InputError:
        old_events = new_events = b""
    appended, journal_errs = split_events(old_events, new_events)
    findings.extend(Finding(EVENTS, err, FIXES[EVENTS]) for err in journal_errs)
    if (journal_errs or not unit_verified(ctx)
            or any(path in modified and path not in parsed for path in (GOAL, STATE))):
        # Already reported: no etalon against a broken journal or an unreadable, unverified ledger.
        findings.extend(Finding(EVENTS, err, FIXES[EVENTS]) for err in check_events(appended, ctx, None))
        return findings
    ws = Workspace(repo, old)
    try:
        candidate_goal = parsed[GOAL][1] if GOAL in parsed else later_goal
        et = build_etalon(ws, ctx)
        findings.extend(Finding(GOAL, err, FIXES[GOAL])
                        for err in compare_json(GOAL, candidate_goal or {}, et.goal, ctx, et))
        if et.state is not None:
            later_state = parsed[STATE][1] if STATE in parsed else json_at(repo, new, STATE)
            if later_state is None:
                findings.append(Finding(STATE, "the harness projected the transition into STATE.json "
                                        "but the later tree has no readable STATE.json", FIXES[STATE]))
            else:
                findings.extend(Finding(STATE, err, FIXES[STATE])
                                for err in compare_json(STATE, later_state, et.state, ctx, et))
        elif STATE in modified:
            findings.append(Finding(STATE, "changed although the harness wrote no STATE projection "
                                    "for this transition", FIXES[STATE]))
        findings.extend(Finding(EVENTS, err, FIXES[EVENTS]) for err in check_events(appended, ctx, et))
        findings.extend(validate_ledger(ws, repo, new))
    finally:
        ws.close()
    return findings


def validate_ledger(ws: Workspace, repo: Path, new: str) -> list[Finding]:
    """The later GOAL.json and STATE.json pass the schema validator of the reviewed tree."""
    out = ws.root / "later"
    out.mkdir()
    args = []
    for path in (GOAL, STATE, EVENTS):
        try:
            data = blob(repo, new, path)
        except InputError:
            continue
        target = out / Path(path).name
        target.write_bytes(data)
        if path != EVENTS:  # the journal lies beside the ledger for the reconciliation check
            args.append(str(target))
    if not args:
        return []
    if not (ws.repo / VALIDATOR).is_file():
        return []  # the reviewed tree ships no validator; the etalon comparison stands alone
    proc = ws.run(VALIDATOR, *args)  # a timeout or a start failure is an input error, not a pass
    if proc.returncode != 0:
        return [Finding(GOAL, f"the later ledger fails {VALIDATOR} of the reviewed tree: "
                        f"{last_line(proc)}", FIXES[GOAL])]
    return []


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--receipt", type=Path, help="PASSED adjudication receipt of the unit")
    p.add_argument("--tree", help="later tree-ish: HEAD, a commit, or `git write-tree` output")
    p.add_argument("--repo", type=Path, default=Path("."), help="repository (default: .)")
    args = p.parse_args(argv)
    if args.receipt is None and args.tree is None:
        return 0
    try:
        if args.receipt is None or args.tree is None:
            raise InputError("--receipt and --tree go together")
        ctx, verified = load_receipt(args.receipt)
        try:
            git(args.repo, "cat-file", "-e", verified + "^{tree}")
        except InputError:
            raise InputError(f"verified tree {verified} of {args.receipt} is not in "
                             f"{args.repo}") from None
        later = resolve_tree(args.repo, args.tree, "--tree")
        findings = evaluate(args.repo, verified, later, ctx)
    except InputError as exc:
        print(f"itd_closure_delta: {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
