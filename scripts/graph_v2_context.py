#!/usr/bin/env python3
"""Pinned local study namespaces; no provider or model transport."""
from pathlib import Path
import json,re

def context(root):
    root=Path(root)
    protocol=root/'docs/measurements/graph-v2/PROTOCOL.json'
    def pairs(rows):
        out={}
        for key,value in rows:
            if key in out: raise ValueError('duplicate protocol key')
            out[key]=value
        return out
    cfg=json.loads(protocol.read_text(encoding='utf-8'),object_pairs_hook=pairs)
    namespace=cfg.get('namespace','gv2b')
    directory=cfg.get('studyDirectory','.itd-memory/graph-v2-study')
    if not isinstance(namespace,str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,39}',namespace): raise ValueError('unsafe study namespace')
    if not isinstance(directory,str) or not re.fullmatch(r'[.]itd-memory/graph-v2-study(?:-[a-z0-9][a-z0-9-]*)?',directory): raise ValueError('unsafe study directory')
    runs=Path(cfg.get('runsRoot','/home/hihol/itd-graph-v2-runs'))
    if not runs.is_absolute() or '..' in runs.parts or runs.is_symlink(): raise ValueError('unsafe clone root')
    grader='gv2_grade' if namespace=='gv2b' else namespace+'_grade'
    return {'protocol':protocol,'study':root/directory,'runs':runs,'namespace':namespace,'grader':grader}

def read_code(p):
    command="wsl.exe -d Ubuntu-24.04 --exec /usr/bin/cat '"+str(p).replace("'","''")+"'"
    return '// @exec: {"yield_time_ms":120000,"max_output_tokens":60000}\n'+"text(await tools.exec_command("+json.dumps({"cmd":command,"max_output_tokens":60000,"yield_time_ms":30000},ensure_ascii=False,separators=(",",":"))+"));"
