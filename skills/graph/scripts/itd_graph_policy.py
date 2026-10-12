#!/usr/bin/env python3
"""Bounded owner-authorized conditional Graph Lite preparation; never invokes a model."""
from __future__ import annotations
import argparse,fnmatch,hashlib,json,os,re,sys,time,types
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
def module(name):
    p=HERE/(name+".py"); m=types.ModuleType(name);m.__file__=str(p)
    exec(compile(p.read_bytes(),str(p),"exec"),m.__dict__);return m
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def policy_digest(p): return hashlib.sha256(canonical(p)).hexdigest()
def fingerprint(): return hashlib.sha256(b"graph-v2-template\0"+(HERE/"itd_graph_v2.py").read_bytes()+b"\0"+(HERE/"itd_graph.py").read_bytes()+b"\0"+Path(__file__).read_bytes()).hexdigest()
def boot_id():
    p=Path("/proc/sys/kernel/random/boot_id")
    if p.is_file(): return p.read_text().strip()
    # Native host clock identity; persistent run cannot survive a reboot unnoticed.
    return "native-"+str(int(time.time()-time.monotonic())//60)
def read(p):
    p=Path(p)
    if p.is_symlink() or p.stat().st_size>256000: raise ValueError("metadata symlink/size refused")
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError("duplicate JSON key")
            d[k]=v
        return d
    return json.loads(p.read_text(encoding="utf-8"),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError("non-finite JSON")))
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    if p.is_symlink(): raise ValueError("metadata symlink refused")
    tmp=p.with_name(p.name+"."+str(os.getpid())+".tmp")
    with tmp.open("x",encoding="utf-8") as f: f.write(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    os.replace(tmp,p)
def path(project,value):
    if not module("itd_graph_v2").safe_relative(value): raise ValueError("unsafe relative path")
    root=Path(project).resolve();p=root/value
    current=root
    for part in Path(value).parts:
        current=current/part
        if current.is_symlink(): raise ValueError("symlink in scope")
    if not p.is_file() or root not in p.resolve().parents: raise ValueError("scope path is not a project file")
    return p
def matches(name,patterns): return any(fnmatch.fnmatchcase(name,p) for p in patterns)
def utc(value):
    if not isinstance(value,str): raise ValueError("UTC timestamp required")
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None or dt.utcoffset().total_seconds()!=0: raise ValueError("UTC timestamp required")
    return dt
def decide(project,request,policy,authorization,used=0):
    if policy is None: return {"route":"single","reason":"no-policy"}
    if not isinstance(policy,dict) or policy.get("version")!=1 or type(policy.get("enabled")) is not bool: raise ValueError("malformed graph policy")
    if not policy["enabled"]: return {"route":"single","reason":"disabled"}
    required={"version","enabled","project","template","templateSha256","allowedModules","sensitivePaths","boundaries","maxRuns","maxAgentNodes","maxSeconds","expiresAt"}
    if set(policy)!=required: raise ValueError("unknown/missing policy fields")
    root=Path(project).resolve()
    if Path(policy["project"]).resolve()!=root or Path(policy["project"]).is_symlink(): raise ValueError("foreign policy project")
    if policy["template"]!="contract-boundary-check" or policy["templateSha256"]!=fingerprint(): raise ValueError("stale template authorization")
    for field,lo,hi in (("maxRuns",1,32),("maxSeconds",1,3600),("maxAgentNodes",3,3)):
        if type(policy[field]) is not int or not lo<=policy[field]<=hi: raise ValueError("invalid policy limit")
    if utc(policy["expiresAt"])<=datetime.now(timezone.utc): raise ValueError("expired graph policy")
    for field in ("allowedModules","sensitivePaths"):
        if not isinstance(policy[field],list) or len(policy[field])>64 or any(not module("itd_graph_v2").safe_relative(p) for p in policy[field]): raise ValueError("unsafe scope pattern")
    bs=policy["boundaries"]
    if not isinstance(bs,list) or len(bs)>32 or any(not isinstance(b,dict) or set(b)!={"id","paths"} or not isinstance(b["id"],str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}",b["id"]) or not isinstance(b["paths"],list) or not b["paths"] or any(not module("itd_graph_v2").safe_relative(p) for p in b["paths"]) for b in bs) or len({b["id"] for b in bs})!=len(bs): raise ValueError("invalid boundary map")
    if authorization is None: return {"route":"single","reason":"owner-authorization-required"}
    if not isinstance(authorization,dict) or set(authorization)!={"version","policySha256","by","at"} or authorization["version"]!=1 or authorization["policySha256"]!=policy_digest(policy) or not isinstance(authorization["by"],str) or not authorization["by"].strip(): raise ValueError("owner authorization missing/stale")
    if utc(authorization["at"])>datetime.now(timezone.utc): raise ValueError("future owner authorization")
    fields={"version","unitId","module","task","functions","contracts","changedFiles"}
    if not isinstance(request,dict) or not fields<=set(request)<=fields|{"unresolved"} or request["version"]!=1 or not isinstance(request["unitId"],str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}",request["unitId"]): raise ValueError("invalid routing request")
    if not isinstance(request["task"],str) or not request["task"].strip() or len(request["task"].encode())>20000: raise ValueError("invalid task")
    v2=module("itd_graph_v2");v2.validate_contract(request["contracts"],request["functions"]);path(root,request["module"])
    if not isinstance(request["changedFiles"],list) or not request["changedFiles"] or len(request["changedFiles"])>128 or len(set(request["changedFiles"]))!=len(request["changedFiles"]): raise ValueError("invalid changed-file inventory")
    for p in request["changedFiles"]: path(root,p)
    if not matches(request["module"],policy["allowedModules"]): return {"route":"single","reason":"outside-module-policy"}
    hit=[b["id"] for b in bs if any(matches(p,b["paths"]) for p in request["changedFiles"])]
    sensitive=any(matches(p,policy["sensitivePaths"]) for p in request["changedFiles"])
    dispute=False
    if "unresolved" in request:
        u=request["unresolved"]
        if not isinstance(u,dict) or set(u)!={"findingId","reason","counterexample","evidence"} or any(not isinstance(u[k],str) or not u[k].strip() for k in ("findingId","reason","counterexample")) or not isinstance(u["evidence"],list) or len(u["evidence"])<2: raise ValueError("unresolved candidate needs concrete independent evidence")
        seen=[]
        for e in u["evidence"]:
            if not isinstance(e,dict) or set(e)!={"path","sha256"} or hashlib.sha256(path(root,e["path"]).read_bytes()).hexdigest()!=e["sha256"]: raise ValueError("unresolved evidence changed")
            seen.append(e["path"])
        if len(set(seen))!=len(seen): raise ValueError("independent evidence paths required")
        dispute=True
    eligible=dispute or (sensitive and len(hit)>=2)
    if type(used) is not int or used<0: raise ValueError("invalid usage ledger")
    if eligible and used>=policy["maxRuns"]: return {"route":"single","reason":"budget-exhausted","eligible":True}
    return {"route":"graph" if eligible else "single","reason":"evidence-dispute" if dispute else "cross-boundary-contract" if eligible else "single-check-sufficient","boundaries":hit,"eligible":eligible}

def validate_bound_approval(run_dir,graph,approval):
    b=approval["policy"];root=Path(run_dir).resolve().parents[2]
    if set(b)!={"policyPath","authorizationPath","requestPath","policySha256","authorizationSha256","requestSha256","session","startedNs","bootId","maxSeconds"}: raise ValueError("incomplete policy provenance")
    p=read(path(root,b["policyPath"]));a=read(path(root,b["authorizationPath"]));r=read(path(root,b["requestPath"]))
    if policy_digest(p)!=b["policySha256"] or policy_digest(a)!=b["authorizationSha256"] or policy_digest(r)!=b["requestSha256"]: raise ValueError("policy/request changed after approval")
    decision=decide(root,r,p,a)
    if decision["route"]!="graph": raise ValueError("policy no longer selects graph")
    expected=module("itd_graph_v2").build_graph(graph["runId"],str(root),r["module"],r["task"],r["contracts"],r["functions"])
    if canonical(expected)!=canonical(graph) or approval["by"]!=a["by"] or b["maxSeconds"]!=p["maxSeconds"]: raise ValueError("graph outside owner authorization envelope")
def check_deadline(approval):
    b=approval["policy"]
    if b["bootId"]!=boot_id() or type(b["startedNs"]) is not int or time.monotonic_ns()<b["startedNs"]: raise ValueError("execution clock/boot changed")
    if time.monotonic_ns()-b["startedNs"]>b["maxSeconds"]*1000000000: raise ValueError("graph execution budget exceeded")

def prepare(project,request_path,session):
    root=Path(project).resolve()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",session): raise ValueError("invalid host session")
    pp=root/".itd/GRAPH_POLICY.json";ap=root/".itd/GRAPH_AUTHORIZATION.json"
    if not pp.exists(): return {"route":"single","reason":"no-policy"}
    p=read(path(root,".itd/GRAPH_POLICY.json"))
    if p.get("enabled") is False: return {"route":"single","reason":"disabled"}
    rp=path(root,str(Path(request_path).relative_to(root)) if Path(request_path).is_absolute() else request_path)
    r=read(rp);a=read(path(root,".itd/GRAPH_AUTHORIZATION.json")) if ap.exists() else None
    state=root/".itd-memory/STATE.json"
    if state.exists():
        current=read(state).get("currentUnit",{})
        if current.get("id")!=r.get("unitId") or current.get("status") not in ("in_progress","verifying","recovery_required"): return {"route":"single","reason":"no-active-request"}
    # Recheck owner authorization and expiry BEFORE any existing-run reuse.
    first=decide(root,r,p,a)
    if first["route"]!="graph": return first
    gt=module("itd_graph");tree=gt.project_tree_state(root)
    if tree.get("git") is not True: raise ValueError("automatic graph requires tracked project")
    for f in r["changedFiles"]:
        import subprocess
        if subprocess.run(["git","-C",str(root),"ls-files","--error-unmatch","--",f],capture_output=True).returncode: raise ValueError("changed-file inventory contains untracked source")
    mem=root/".itd-memory";mem.mkdir(exist_ok=True)
    lock=mem/"graph-policy.lock"
    if lock.is_symlink(): raise ValueError("policy lock symlink")
    try: lock.mkdir()
    except FileExistsError: raise ValueError("graph policy busy; recover the existing lock before retrying")
    try:
        lp=mem/"graph-policy-ledger.json";ledger=read(lp) if lp.exists() else {"version":2,"entries":[]}
        if set(ledger)!={"version","entries"} or ledger["version"]!=2 or not isinstance(ledger["entries"],list): raise ValueError("malformed policy ledger")
        for entry in ledger["entries"]:
            fields={"key","session","unitId","runDir","graphDigest","policySha256","authorizationSha256"}
            if not isinstance(entry,dict) or set(entry)!=fields or any(not isinstance(entry[k],str) for k in fields): raise ValueError("invalid policy ledger entry")
            if any(not re.fullmatch(r"[0-9a-f]{64}",entry[field]) for field in ("key","graphDigest","policySha256","authorizationSha256")) or entry["runDir"]!=".itd-memory/graph-runs/auto-"+entry["key"][:24]: raise ValueError("foreign/unsafe policy ledger run")
            saved=gt.contained_run_dir(root/entry["runDir"])
            saved_graph,saved_digest=gt.load_valid_graph(saved)
            saved_approval=gt.read_json(saved/"approval.json","saved policy approval")
            bound=saved_approval.get("policy") if isinstance(saved_approval,dict) else None
            if saved_graph["runId"]!=saved.name or saved_digest!=entry["graphDigest"] or not isinstance(bound,dict) or saved_approval.get("graphDigest")!=saved_digest or saved_approval.get("runId")!=saved.name or any(bound.get(field)!=entry[field] for field in ("session","policySha256","authorizationSha256")):
                raise ValueError("policy ledger budget identity differs from saved approval")
        key=hashlib.sha256(canonical([session,r,tree,policy_digest(p),policy_digest(a)])).hexdigest()
        prior=next((e for e in ledger["entries"] if e.get("key")==key),None)
        if prior:
            rd=gt.contained_run_dir(root/prior["runDir"]);g,d=gt.load_valid_graph(rd)
            if rd.name!="auto-"+key[:24] or g["runId"]!=rd.name or d!=prior["graphDigest"]: raise ValueError("existing graph identity differs from ledger")
            approval=gt.load_matching_approval(rd,d,g)
            if "policy" not in approval or approval["policy"]["session"]!=session or approval["policy"]["requestSha256"]!=policy_digest(r) or canonical(approval["projectTree"])!=canonical(tree): raise ValueError("existing graph lacks current owner-policy provenance")
            recorded=(rd/"receipt.json").exists()
            if recorded:
                if gt.receipt_mismatches(rd,gt.read_json(rd/"receipt.json","receipt"),g) or gt.run_state(rd)["state"] not in ("recorded","closed"): raise ValueError("existing graph receipt is corrupted or partial")
            else: check_deadline(approval)
            return dict(first,route="recorded" if recorded else "graph",runDir=str(rd),graphDigest=d,reused=True)
        used=sum(e["policySha256"]==policy_digest(p) and e["authorizationSha256"]==policy_digest(a) for e in ledger["entries"])
        decision=decide(root,r,p,a,used)
        if decision["route"]!="graph": return decision
        run_id="auto-"+key[:24];rd=gt.contained_run_dir(mem/"graph-runs"/run_id)
        if rd.exists(): raise ValueError("unledgered graph directory exists")
        g=module("itd_graph_v2").build_graph(run_id,str(root),r["module"],r["task"],r["contracts"],r["functions"])
        if gt.validate_graph(g): raise ValueError("invalid generated graph")
        d=gt.graph_digest(g);gt.write_json(rd/"graph.json",g)
        bound={"policyPath":".itd/GRAPH_POLICY.json","authorizationPath":".itd/GRAPH_AUTHORIZATION.json","requestPath":rp.relative_to(root).as_posix(),"policySha256":policy_digest(p),"authorizationSha256":policy_digest(a),"requestSha256":policy_digest(r),"session":session,"startedNs":time.monotonic_ns(),"bootId":boot_id(),"maxSeconds":p["maxSeconds"]}
        gt.write_json(rd/"approval.json",{"graphDigest":d,"runId":run_id,"by":a["by"],"at":gt.now_iso(None),"projectTree":tree,"policy":bound})
        ledger["entries"].append({"key":key,"session":session,"unitId":r["unitId"],"runDir":rd.relative_to(root).as_posix(),"graphDigest":d,"policySha256":policy_digest(p),"authorizationSha256":policy_digest(a)});write(lp,ledger)
        return dict(decision,runDir=str(rd),graphDigest=d,reused=False)
    except gt.Refused as exc: raise ValueError(str(exc)) from exc
    finally: lock.rmdir()

def main(argv=None):
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest="command")
    for cmd in ("digest","authorize","prepare"):
        p=sub.add_parser(cmd);p.add_argument("--project",default=".")
        if cmd=="authorize": p.add_argument("--digest",required=True);p.add_argument("--by",required=True)
        if cmd=="prepare": p.add_argument("--request",default=".itd-memory/graph-request.json");p.add_argument("--session",required=True)
    sub.add_parser("hook");sub.add_parser("template-digest");a=parser.parse_args(argv)
    if not a.command: return 0
    if a.command=="template-digest": print(fingerprint());return 0
    try:
        if a.command=="hook":
            payload=json.load(sys.stdin);root=Path(payload.get("cwd") or ".").resolve()
            if not (root/".itd/GRAPH_POLICY.json").exists() or not (root/".itd-memory/graph-request.json").exists(): return 0
            result=prepare(root,".itd-memory/graph-request.json",str(payload.get("session_id") or ""))
            if result["route"]=="graph":
                context="Owner policy selected Graph Lite: "+result["reason"]+". Execute the authorized read-only graph with fresh native subagents, in layers, before treating the task as complete. Run: sh "+str(HERE.parents[1]/"_shared/itd_py.sh")+" "+str(HERE/"itd_graph.py")+" emit-serial "+result["runDir"]+". Resume saved node outputs; never duplicate a completed node. Human decision stays terminal; no gate is replaced."
                print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":context}}))
            return 0
        root=Path(a.project).resolve();p=read(path(root,".itd/GRAPH_POLICY.json"))
        if a.command=="digest": print(policy_digest(p));return 0
        if a.command=="authorize":
            if a.digest!=policy_digest(p) or not a.by.strip(): raise ValueError("owner must authorize the exact displayed policy digest")
            write(root/".itd/GRAPH_AUTHORIZATION.json",{"version":1,"policySha256":a.digest,"by":a.by.strip(),"at":datetime.now(timezone.utc).isoformat()});return 0
        print(json.dumps(prepare(root,a.request,a.session),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        if a.command=="hook":
            print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"Conditional Graph preparation refused: "+str(exc)+". Fix the explicit policy/request; do not infer an approval or weaken normal verification."}}));return 0
        print("REFUSED: "+str(exc)+"; FIX: restore the exact owner policy and bounded request.",file=sys.stderr);return 2
if __name__=="__main__": sys.exit(main())
