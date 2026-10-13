#!/usr/bin/env python3
"""Contract-first Graph Lite template and deterministic finding adjudication."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path

TEMPLATE="contract-boundary-check"
ID=re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
READ_ONLY="READ-ONLY: no source edits, Git mutations, package installation, network or external actions. Read only tracked source/tests in the assigned project and assigned metadata. Pure inline standard-library counterexamples without file writes are permitted."
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def string(): return {"type":"string"}
FINDING={"type":"object","properties":{k:string() for k in ("findingId","file","function","contractId","precondition","input","expected","actual","claim","evidence","class","severity","origin")},"required":["findingId","file","line","function","contractId","precondition","input","expected","actual","claim","evidence","class","severity","origin"]}
FINDING["properties"]["line"]={"type":"integer"}
FINDING["properties"]["severity"]={"type":"string","enum":["high","medium","low"]}
FINDING["properties"]["origin"]={"type":"string","enum":["introduced","pre-existing","unknown"]}
COVERAGE={"type":"object","properties":{"function":string(),"contractIds":{"type":"array","items":string()},"status":{"type":"string","enum":["checked","not-applicable"]},"evidence":string()},"required":["function","contractIds","status","evidence"]}
HUNTER={"type":"object","properties":{"findings":{"type":"array","items":FINDING},"coverage":{"type":"array","items":COVERAGE}},"required":["findings","coverage"]}
ASSESSMENT={"type":"object","properties":{k:string() for k in ("findingId","contract","reachability","reason","evidence")},"required":["findingId","contract","reachability","reason","evidence"]}
ASSESSMENT["properties"]["contract"]={"type":"string","enum":["violated","satisfied","unknown"]}
ASSESSMENT["properties"]["reachability"]={"type":"string","enum":["reachable","blocked","unknown"]}
CHECKER={"type":"object","properties":{"assessments":{"type":"array","items":ASSESSMENT}},"required":["assessments"]}

def safe_relative(value):
    return isinstance(value,str) and bool(value) and "\\" not in value and ":" not in value and not value.startswith("/") and all(p not in ("",".","..") for p in value.split("/"))

def validate_contract(contracts,functions):
    if not isinstance(contracts,list) or not contracts or not isinstance(functions,list) or not functions: raise ValueError("explicit contracts and function inventory required")
    ids=[]
    for c in contracts:
        if not isinstance(c,dict) or set(c)!={"id","requirement"} or not isinstance(c["id"],str) or not ID.fullmatch(c["id"]) or not isinstance(c["requirement"],str) or not c["requirement"].strip(): raise ValueError("malformed contract")
        ids.append(c["id"])
    if len(ids)!=len(set(ids)) or any(not isinstance(f,str) or not ID.fullmatch(f) for f in functions) or len(functions)!=len(set(functions)): raise ValueError("duplicate/invalid contract or function")

def build_graph(run_id,project,module,task,contracts,functions):
    validate_contract(contracts,functions)
    if not safe_relative(module) or not isinstance(task,str) or not task.strip(): raise ValueError("module/task invalid")
    shared=READ_ONLY+"\nProject: "+str(project)+"\nModule: "+module+"\nOriginal task: "+task+"\nCONTRACTS: "+canonical(contracts).decode()+"\nFUNCTION INVENTORY: "+canonical(functions).decode()+"\n"
    common="For every named function return one coverage row, with concrete source evidence. Its contractIds must enumerate every declared contract exactly once, including contracts deemed not applicable with an explanation in evidence. Check all declared contracts, including helpers and boundary inputs. Report only demonstrated behavior conflicts; a future unimplemented feature is not a defect of the current contract. Do not restrict discoveries to a defect class. Split independent claims, even at one source line. Every finding needs a minimal input, expected/actual behavior and exact code evidence. Use code-relative paths in evidence; put proposal IDs only in findingId, never in input, expected, actual or evidence. Do not include arm/run/role attribution in semantic fields. Keep finding IDs immutable. "
    prompts={
      "contracts":shared+"Role: local contract and boundary-input explorer. "+common+"Inspect empty/invalid/edge inputs, transformations, conservation rules and all public functions. IDs contracts-1, contracts-2, etc.",
      "integration":shared+"Role: caller, state and integration explorer. "+common+"Trace caller guarantees, persistence invariants, transitions and independent boundaries. Explain when there is no integration obligation. IDs integration-1, integration-2, etc.",
      "checker":shared+"Role: independent checker of supplied proposals. Do not invent or merge finding IDs. Return exactly one assessment per proposal. Separate local contract truth from operational reachability: a caller guard may block exploitation without repairing a helper-contract violation. contract violated requires code/counterexample evidence; satisfied requires a real refutation of the stated contract; unknown preserves uncertainty. reachability reachable/blocked/unknown is separate. Never turn doubt into satisfied or silently delete a proposal. Type annotations alone do not validate runtime inputs."
    }
    nodes=[]
    for name in ("contracts","integration","checker"):
        nodes.append({"id":name,"role":"checker" if name=="checker" else "hunter","kind":"agent","purity":"read-only","inputs":["state.task","state.contracts","state.functions"]+(["contracts.findings","integration.findings"] if name=="checker" else []),"outputs":["assessments" if name=="checker" else "findings"],"schema":"assessments" if name=="checker" else "findings","prompt":prompts[name]})
    nodes[2]["checks"]=["contracts","integration"]
    nodes.append({"id":"human","role":"human","kind":"human","purity":"read-only","inputs":["contracts.findings","integration.findings","checker.assessments"],"outputs":["decision"],"prompt":"The owner reads the deterministic synthesis and decides. This graph cannot verify a unit or authorize external actions."})
    return {"schemaVersion":1,"runId":run_id,"template":TEMPLATE,"task":task,"state":{"project":str(project),"module":module,"task":task,"contracts":contracts,"functions":functions,"sharedRecord":"immutable proposal IDs -> orthogonal assessments -> deterministic synthesis -> human"},"nodes":nodes,"edges":[["contracts","checker"],["integration","checker"],["contracts","human"],["integration","human"],["checker","human"]],"schemas":{"findings":HUNTER,"assessments":CHECKER}}

def validate_hunter(contracts,functions,value,node):
    validate_contract(contracts,functions)
    if node not in ("contracts","integration","check"): raise ValueError("unknown hunter role")
    contract_ids={x["id"] for x in contracts};ids=[]
    if not isinstance(value,dict) or set(value)!={"findings","coverage"} or not isinstance(value["findings"],list) or not isinstance(value["coverage"],list): raise ValueError("invalid hunter output")
    coverage=[]
    for row in value["coverage"]:
        if not isinstance(row,dict) or set(row)!={"function","contractIds","status","evidence"}: raise ValueError("invalid coverage")
        if row["status"] not in ("checked","not-applicable") or not isinstance(row["evidence"],str) or not row["evidence"].strip(): raise ValueError("coverage needs evidence")
        if not isinstance(row["contractIds"],list) or any(not isinstance(c,str) or c not in contract_ids for c in row["contractIds"]): raise ValueError("unknown coverage contract")
        if len(row["contractIds"])!=len(contract_ids) or set(row["contractIds"])!=contract_ids: raise ValueError("coverage must account for every contract exactly once")
        coverage.append(row["function"])
    if sorted(coverage)!=sorted(functions): raise ValueError("coverage must name every function exactly once")
    for f in value["findings"]:
        if not isinstance(f,dict) or set(f)!=set(FINDING["required"]): raise ValueError("finding schema mismatch")
        if any(not isinstance(f[k],str) or not f[k].strip() for k in FINDING["required"] if k!="line"): raise ValueError("finding fields must be nonempty")
        if not re.fullmatch(re.escape(node)+r"-[A-Za-z0-9][A-Za-z0-9_.-]{0,79}",f["findingId"]): raise ValueError("finding ID must belong to its node")
        if not safe_relative(f["file"]) or type(f["line"]) is not int or f["line"]<1 or f["function"] not in functions or f["contractId"] not in contract_ids: raise ValueError("finding reference invalid")
        if f["severity"] not in ("high","medium","low") or f["origin"] not in ("introduced","pre-existing","unknown"): raise ValueError("finding enums invalid")
        ids.append(f["findingId"])
    return ids

def validate_outputs(graph,outputs):
    if not isinstance(outputs,dict) or set(outputs)!={"contracts","integration","checker"}: raise ValueError("exact three node outputs required")
    contracts=graph["state"]["contracts"]; functions=graph["state"]["functions"]
    validate_contract(contracts,functions); contract_ids={x["id"] for x in contracts}; ids=[]
    for node in ("contracts","integration"):
        ids.extend(validate_hunter(contracts,functions,outputs[node],node))
    if len(ids)!=len(set(ids)): raise ValueError("duplicate finding ID")
    checker=outputs["checker"]
    if not isinstance(checker,dict) or set(checker)!={"assessments"} or not isinstance(checker["assessments"],list): raise ValueError("checker schema mismatch")
    assessed=[]
    for a in checker["assessments"]:
        if not isinstance(a,dict) or set(a)!=set(ASSESSMENT["required"]) or a["contract"] not in ("violated","satisfied","unknown") or a["reachability"] not in ("reachable","blocked","unknown"): raise ValueError("assessment schema mismatch")
        if any(not isinstance(a[k],str) or not a[k].strip() for k in ASSESSMENT["required"]): raise ValueError("assessment evidence missing")
        assessed.append(a["findingId"])
    if sorted(assessed)!=sorted(ids): raise ValueError("every finding needs exactly one assessment; no foreign/merged ID")

def synthesize(graph,outputs):
    validate_outputs(graph,outputs)
    assessments={a["findingId"]:a for a in outputs["checker"]["assessments"]}
    findings=[]; dropped=[]
    for node in ("contracts","integration"):
        for f in outputs[node]["findings"]:
            a=assessments[f["findingId"]]
            if a["contract"]=="satisfied": dropped.append({"findingId":f["findingId"],"reason":a["reason"],"evidence":a["evidence"]}); continue
            findings.append(dict(f,status="confirmed" if a["contract"]=="violated" else "unverifiable",reachability=a["reachability"],assessmentEvidence=a["evidence"],assessmentReason=a["reason"],sourceIds=[f["findingId"]]))
    findings.sort(key=lambda f: ({"high":0,"medium":1,"low":2}[f["severity"]],f["file"],f["line"],f["findingId"]))
    return {"findings":findings,"dropped":dropped,"coverage":{n:outputs[n]["coverage"] for n in ("contracts","integration")},"counts":{"proposed":sum(len(outputs[n]["findings"]) for n in ("contracts","integration")),"retained":len(findings),"dropped":len(dropped)}}
