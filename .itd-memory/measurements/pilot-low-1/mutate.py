"""Mutation check for one pilot unit: apply each mutation, run one test file, restore via git."""
import json
import subprocess
import sys

root, target, test_file, spec = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
mutations = json.load(open(spec, encoding="utf-8"))
path = f"{root}/{target}"
original = open(path, encoding="utf-8").read()
for name, old, new in mutations:
    assert old in original, f"{name}: pattern not found"
    open(path, "w", encoding="utf-8").write(original.replace(old, new, 1))
    run = subprocess.run(
        [f"{root}/.venv/bin/python", "-m", "pytest", "-q", test_file],
        cwd=f"{root}/backend", capture_output=True, text=True,
    )
    last = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr[-200:]
    print(f"{name}: {'CAUGHT' if run.returncode else 'SURVIVED'} ({last})")
    open(path, "w", encoding="utf-8").write(original)
subprocess.run(["git", "-C", root, "checkout", "-q", "--", target], check=True)
clean = subprocess.run(["git", "-C", root, "diff", "--quiet", "--", target]).returncode == 0
print("product file restored:", clean)
