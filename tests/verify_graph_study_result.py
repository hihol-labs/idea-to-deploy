#!/usr/bin/env python3
"""Replay the exact fresh study and every blind native answer from declared inputs."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):
 import types
 m=types.ModuleType("subject");m.__file__=str(p);exec(compile(p.read_bytes(),str(p),"exec"),m.__dict__);return m
def native_proof(a,raw,n,parent,expected_agent):
 if hashlib.sha256(raw).hexdigest()!=a["nativeSha256"]: raise ValueError("native snapshot hash")
 rows=n.NativeSnapshot(raw);meta=rows[0]["payload"];spawn=meta.get("source",{}).get("subagent",{}).get("thread_spawn",{})
 if meta["id"]!=a["sessionId"] or spawn.get("parent_thread_id")!=parent or spawn.get("agent_path")!=expected_agent: raise ValueError("native lineage")
 bind=a["binding"];call=bind["call"]["payload"];ret=bind["return"]["payload"]
 if call["call_id"]!=ret["call_id"] or ret.get("type")!="function_call_output": raise ValueError("native call return link")
 return rows
def self_test():
 import copy
 n=load(ROOT/"scripts/graph_v2_native.py")
 meta={"id":"synthetic","source":{"subagent":{"thread_spawn":{"parent_thread_id":"parent","agent_path":"/root/synthetic"}}}}
 raw=(json.dumps({"type":"session_meta","payload":meta})+"\n").encode()
 a={"nativeSha256":hashlib.sha256(raw).hexdigest(),"sessionId":"synthetic","binding":{"call":{"payload":{"call_id":"c"}},"return":{"payload":{"type":"function_call_output","call_id":"c"}}}}
 native_proof(a,raw,n,"parent","/root/synthetic")
 cases=[]
 for key,value in (("nativeSha256","0"*64),("sessionId","foreign")):
  bad=copy.deepcopy(a);bad[key]=value;cases.append((bad,raw,"parent","/root/synthetic"))
 bad=copy.deepcopy(a);bad["binding"]["return"]["payload"]["call_id"]="other";cases.append((bad,raw,"parent","/root/synthetic"))
 bad=copy.deepcopy(a);bad["binding"]["return"]["payload"]["type"]="message";cases.append((bad,raw,"parent","/root/synthetic"))
 cases.extend([(a,raw+b" ","parent","/root/synthetic"),(a,raw,"foreign","/root/synthetic"),(a,raw,"parent","/root/foreign")])
 for args in cases:
  try: native_proof(*args[:2],n,*args[2:])
  except (ValueError,KeyError,IndexError): continue
  raise ValueError("negative native provenance accepted")
 g=load(ROOT/"scripts/graph_v2_grade.py")
 batch={"kind":"semantic","items":[]};p=Path("/tmp/assigned.json")
 for cmd in ("cat /tmp/foreign.json","cat ../foreign.json","claude --version","curl https://example.invalid"):
  rows=[{"type":"response_item","payload":{"type":"custom_tool_call","name":"exec","input":"text(await tools.exec_command({cmd:"+json.dumps(cmd)+"}));"}}]
  if not g.audit(n,rows,batch,p): raise ValueError("negative grader isolation accepted")
 print(json.dumps({"status":"PASSED","negativeCases":len(cases)+4}));return 0

def main():
 context=load(ROOT/"scripts/graph_v2_context.py").context(ROOT)
 d=context["study"];history=d/"source-snapshot"
 st=load(history/"scripts/graph_v2_study.py");st.STUDY=d
 g=load(ROOT/"scripts/graph_v2_grade.py");n=load(ROOT/"scripts/graph_v2_native.py");sc=load(ROOT/"skills/graph/scripts/itd_graph_score.py")
 freeze=st.read(d/"freeze.json");origin=Path(freeze["projectRoot"])
 for recorded,digest in freeze["files"].items():
  rel=Path(recorded).relative_to(origin)
  if st.sha(ROOT/rel)!=digest or st.sha(history/rel)!=digest: raise ValueError("current measured engine or frozen snapshot differs from study freeze")
 collection=st.replay();grading=g.combine(False);read=st.read;parent=read(st.PROTO)["parentThreadId"]
 for i in range(g.frozen()["batches"]):
  audit=read(d/"grading/audits"/(str(i)+".json"));raw=(d/"grading/native"/(audit["nativeSha256"]+".jsonl")).read_bytes()
  native_proof(audit,raw,n,parent,"/root/"+g.launch(i)["task_name"])
 for key in read(d/"grading/attempts.json"):
  audit=g.rejected_proof(int(key));raw=(d/"grading/native"/(audit["nativeSha256"]+".jsonl")).read_bytes()
  native_proof(audit,raw,n,parent,"/root/"+g._launch(int(key),0)["task_name"])
 results=read(d/"results.json");manifest=read(d/"sealed/manifest.json");verdicts=read(d/"verdicts.json")
 if sc.build_queue(manifest,results)!=read(d/"queue.json"): raise ValueError("queue changed")
 score=sc.score(manifest,results,verdicts)
 frozen_sc=load(history/"skills/graph/scripts/itd_graph_score.py")
 if frozen_sc.score(manifest,results,verdicts)!=score or score!=read(d/"score.json"): raise ValueError("frozen/current score or registered arithmetic differs")
 print(json.dumps({"status":"PASSED","collection":collection,"grading":grading,"outcome":score["outcome"]}))
 return 0

if __name__=="__main__":
 try: sys.exit(self_test() if "--self-test" in sys.argv else main())
 except Exception as e: print("FAILED: "+str(e),file=sys.stderr);sys.exit(1)
