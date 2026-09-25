"""Mutation check for one pilot unit: apply each mutation, run one test file, restore the original bytes.

The original bytes of the target are captured once and written back in a finally
block, so an exception or an interrupt leaves no mutation behind and uncommitted
changes of the target survive (no git checkout). Each pytest run gets a fresh
PYTHONPYCACHEPREFIX: a mutant written within the same second as the previous one
and of the same size would otherwise be imported from the previous mutant's .pyc
and inherit its verdict. The pilot ran an earlier version without both guards;
its mutation results were re-run with this version (RETRO-PILOT-LOW-1.md).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root, target, test_file, spec = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
mutations = json.load(open(spec, encoding="utf-8"))
path = Path(root) / target
original = path.read_bytes()
try:
    for name, old, new in mutations:
        assert old.encode("utf-8") in original, f"{name}: pattern not found"
        path.write_bytes(original.replace(old.encode("utf-8"), new.encode("utf-8"), 1))
        with tempfile.TemporaryDirectory() as pycache:
            run = subprocess.run(
                [f"{root}/.venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", test_file],
                cwd=f"{root}/backend", capture_output=True, text=True,
                env={**os.environ, "PYTHONPYCACHEPREFIX": pycache},
            )
        last = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr[-200:]
        print(f"{name}: {'CAUGHT' if run.returncode else 'SURVIVED'} ({last})")
        path.write_bytes(original)
finally:
    path.write_bytes(original)
print("product file restored:", path.read_bytes() == original)
