#!/usr/bin/env python3
"""UserPromptSubmit hook — bounded owner-authorized conditional Graph Lite.

No configuration/request means no-op. Python prepares a plan; only the native
host executes agents. The hook never calls a provider, Claude CLI or a model.
"""
from pathlib import Path
import sys,types

def main():
    source=Path(__file__).resolve().parents[1]/"skills/graph/scripts/itd_graph_policy.py"
    mod=types.ModuleType("graph_policy_hook");mod.__file__=str(source)
    exec(compile(source.read_bytes(),str(source),"exec"),mod.__dict__)
    return mod.main(["hook"])

if __name__=="__main__": sys.exit(main())
