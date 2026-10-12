#!/usr/bin/env python3
"""Native Codex study transport. No provider CLI."""
from __future__ import annotations
import collections,hashlib,json,os,re,types
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CTX=types.ModuleType("study_context");exec(compile((ROOT/"scripts/graph_v2_context.py").read_bytes(),str(ROOT/"scripts/graph_v2_context.py"),"exec"),CTX.__dict__)
CONTEXT=CTX.context(ROOT)
SESSION_ROOT=Path("/mnt/c/Users/Дмитрий/.codex/sessions")
def config(): return strict(CONTEXT["protocol"].read_text())
def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
class GT:
 canonical=staticmethod(canonical)
class OLD:
 LEAK_CATEGORIES={"sealed","study","bases","otherClone","hostTranscripts","otherOutside","otherMetadata","forbiddenCommand"}
 @staticmethod
 def paths_in(text):
  text=text.replace("~/","/home/hihol/").replace("$HOME/","/home/hihol/").replace("${HOME}/","/home/hihol/")
  return re.findall(r"(?<![\w.~-])(/(?:home|tmp|root|etc|usr|opt|var|mnt|proc|srv|bin|lib|snap|dev|run)(?:/[^\s\"'`<>|;&(){}\[\],:*?$=]*)?)",text)
 @staticmethod
 def classify(path,clone):
  p=path.rstrip("/");clone=clone.rstrip("/")
  if "/sealed" in p or p.endswith("/manifest.json"): return "sealed"
  if "/.codex/sessions" in p or "/.codex/log" in p: return "hostTranscripts"
  if p==clone or p.startswith(clone+"/"):
   if "/.itd-memory/" in p and not p.startswith(clone+"/.itd-memory/tasks/"): return "otherMetadata"
   return None
  if p=="/dev/null": return None
  if "/graph-v2-study" in p or "/itd-graph-exp" in p: return "study"
  roots={str(CONTEXT["runs"]),"/home/hihol/itd-graph-v2-runs"}
  if any(p==r+"/bases" or p.startswith(r+"/bases/") for r in roots): return "bases"
  if any(p==r or p.startswith(r+"/") for r in roots): return "otherClone"
  return "otherOutside"
def strict(text):
    def pairs(items):
        d = {}
        for k,v in items:
            if k in d: raise ValueError("duplicate JSON key: " + k)
            d[k] = v
        return d
    def bad(x): raise ValueError("non-finite JSON: " + x)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)

def terminal_status(rows):
    starts=[i for i,r in enumerate(rows) if r.get("type")=="event_msg" and r.get("payload",{}).get("type")=="task_started"]
    if not starts: return None
    last=starts[-1]
    ends=[(i,r) for i,r in enumerate(rows) if i>last and r.get("type")=="event_msg" and (r.get("payload",{}).get("type")=="task_complete" or (r.get("payload",{}).get("type")=="turn_aborted" and r["payload"].get("reason") in ("interrupted","cancelled")))]
    if not ends: return None
    index,row=ends[-1]
    if any(r.get("type")=="response_item" and r.get("payload",{}).get("type") in ("function_call","custom_tool_call") for r in rows[index+1:]): return None
    return {"type":row["payload"]["type"],"sha256":hashlib.sha256(GT.canonical(row)).hexdigest()}

def parent_rows():
    path=Path(config()["parentTranscript"])
    lines=path.read_text(encoding="utf-8").splitlines(keepends=True)
    rows=[]
    for i,line in enumerate(lines):
        try: rows.append(strict(line))
        except ValueError:
            if i==len(lines)-1 and not line.endswith("\n"): break
            raise
    if rows[0]["payload"]["id"]!=config()["parentThreadId"]: raise ValueError("parent provenance mismatch")
    return rows

def dispatch_args_match(actual,expected):
    if actual==expected: return True
    # Desktop encrypts free-text messages in native caller logs. No decryption
    # key is accessed. Lineage and task content remain honest-host assertions.
    if not isinstance(actual,dict) or set(actual)!=set(expected): return False
    if any(actual[k]!=expected[k] for k in expected if k!="message"): return False
    message=actual.get("message")
    return isinstance(message,str) and re.fullmatch(r"gAAAA[A-Za-z0-9_=-]{120,}",message) is not None


def native_rows(agent):
    cfg=config(); found=[]
    dates={cfg["sessionDate"],datetime.now().strftime("%Y/%m/%d"),datetime.now(ZoneInfo("Europe/Helsinki")).strftime("%Y/%m/%d")}
    for date in dates:
        for p in (SESSION_ROOT/date).glob("*.jsonl"):
            with p.open(encoding="utf-8") as f:
                line=f.readline()
                if not line.endswith("\n"): continue
                try: first=strict(line)
                except ValueError: continue
            meta=first.get("payload",{}); src=meta.get("source",{})
            if isinstance(src,dict) and src.get("subagent",{}).get("thread_spawn",{}).get("agent_path")==agent and src.get("subagent",{}).get("thread_spawn",{}).get("parent_thread_id")==cfg["parentThreadId"]:
                found.append(p)
    if len(found)!=1: raise ValueError("expected one native transcript for "+agent)
    p=found[0]; return p,NativeSnapshot(p.read_bytes())

def final_from(rows):
    final=[r for r in rows if r.get("type")=="response_item" and r.get("payload",{}).get("type")=="message" and r["payload"].get("role")=="assistant" and r["payload"].get("phase")=="final_answer"]
    if len(final)!=1: raise ValueError("one final JSON response required")
    raw="".join(p.get("text","") for p in final[0]["payload"].get("content",[]) if p.get("type")=="output_text")
    return raw,strict(raw),final[0]["timestamp"]

def audit(rows,clone,assigned=None):
    tools=collections.Counter(); nested=collections.Counter(); outside=collections.Counter(); relative=collections.Counter(); ctx=0
    for r in rows:
        p=r.get("payload",{})
        if r.get("type")!="response_item" or p.get("type") not in ("function_call","custom_tool_call"): continue
        name=p.get("name","unknown"); tools[name]+=1
        inp=p.get("input",p.get("arguments","")); text=inp if isinstance(inp,str) else json.dumps(inp)
        for n in re.findall(r"tools\.(\w+)\s*\(",text): nested[n]+=1
        ctx+=int("ctx_" in name or "context-mode" in name or "ctx_" in text or "context-mode" in text)
        text=re.sub(r"\\+(?=[\"'])","",text)
        text=re.sub(r"/+","/",text.replace("\\","/"))
        text=re.sub(r"/wsl(?:\.localhost|\$)/Ubuntu-24\.04/","/",text,flags=re.I)
        if re.search(r"\.codex/(?:sessions|logs?)(?:/|$)",text,re.I): outside["hostTranscripts"]+=1
        if re.search(r"(?:^|[/ .])sealed(?:/|$)|manifest\.json",text,re.I): outside["sealed"]+=1
        if re.search(r"(?:^|[\s;|\"'])(?:curl|wget|claude|npm|pnpm|yarn|pip|pytest|uv|ssh|scp)\b|python[0-9.]*[^\n]* -m (?:unittest|pytest)|git[^\n;]*\b(?:add|commit|checkout|switch|reset|clean|restore|apply|merge|rebase|push|fetch|pull|clone)\b|python[0-9.]*[^\n;]*\btests/",text,re.I): outside["forbiddenCommand"]+=1
        for metadata in re.findall(r"\.itd(?:-memory)?/[^\s\"';|&()]*",text):
            if assigned is None or metadata!=".itd-memory/tasks/"+assigned+".json": outside["otherMetadata"]+=1
        for path in OLD.paths_in(text):
            path=os.path.normpath(path); cat=OLD.classify(path,str(clone))
            if "/.codex/sessions" in path or "/.codex/log" in path: cat="hostTranscripts"
            if cat: outside[cat]+=1
        for tok in re.findall(r"[^\s\"';|&()]*\.\.(?:/[^\s\"';|&()]*)?",text):
            if tok.startswith("http") or "..." in tok: continue
            resolved=os.path.normpath(os.path.join(str(clone),tok)); cat=OLD.classify(resolved,str(clone))
            relative[cat or "insideClone"]+=1
    calls=[r.get("payload",{}) for r in rows if r.get("type")=="response_item" and r.get("payload",{}).get("type") in ("function_call","custom_tool_call")]
    exact=CTX.read_code(Path(clone)/".itd-memory/tasks"/(str(assigned)+".json"))
    approved=(assigned is not None and len(calls)==1 and calls[0].get("type")=="custom_tool_call" and calls[0].get("name")=="exec" and isinstance(calls[0].get("input"),str) and calls[0]["input"].strip()==exact)
    # Exact literal transport includes its fixed /usr/bin/cat binary; its only data read is the assigned capsule.
    if approved: outside=collections.Counter();relative=collections.Counter()
    voiding=sorted((set(outside)|set(relative))&OLD.LEAK_CATEGORIES)
    if not approved: voiding.append("taskCapsuleIsolation")
    if set(nested)-{"exec_command","write_stdin"} or set(tools)-{"exec","wait"}: voiding.append("forbiddenTool")
    return {"toolCalls":dict(tools),"nestedTools":dict(nested),"ctxCalls":ctx,"outside":dict(outside),"relative":dict(relative),"voiding":voiding,"invalid":"sealed" in outside or "sealed" in relative or (bool(calls) and not approved)}


class NativeSnapshot(list):
    def __init__(self,raw):
        self.digest=hashlib.sha256(raw).hexdigest(); self.complete=raw.endswith(b"\n")
        try: text=raw.decode("utf-8")
        except UnicodeDecodeError: text=raw.decode("utf-8",errors="replace"); self.complete=False
        parsed=[]
        for line in text.splitlines(keepends=True):
            if not line.endswith("\n"): self.complete=False
            try: parsed.append(strict(line))
            except ValueError: self.complete=False
        super().__init__(parsed)
