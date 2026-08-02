#!/usr/bin/env python3
"""Run local regressions only; this candidate-side aggregator is not gate authority."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import itd_machine_oracle as oracle  # noqa: E402

RUN_ALL = ROOT / "tests" / "run-all.sh"
NAME_RE = re.compile(r"^[a-z0-9_]+$")


def main() -> int:
    match = re.search(
        r'^CORE="([^"\r\n]+)"$',
        RUN_ALL.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    names = match.group(1).split() if match else []
    if not names or len(names) != len(set(names)):
        print("DONE fails:quick-profile")
        return 1
    failures: list[str] = []
    for name in names:
        verifier = ROOT / "tests" / f"{name}.py"
        if not NAME_RE.fullmatch(name) or not verifier.is_file():
            failures.append(name)
            continue
        try:
            result = oracle.run_argv(
                [sys.executable, "-I", str(verifier)],
                cwd=ROOT,
                timeout=300,
                max_output_bytes=oracle.MAX_OUTPUT_BYTES,
            )
        except (oracle.OracleError, OSError) as exc:
            print(f"ERROR {name}: {exc}", file=sys.stderr)
            result = None
        failed = (
            result is None
            or bool(result.get("timedOut"))
            or bool(result.get("outputOverflow"))
            or result.get("exitCode") != 0
        )
        if failed:
            failures.append(name)
            if result is not None:
                diagnostic = (result["stdout"] + result["stderr"])[
                    -4096:
                ].decode("utf-8", errors="replace")
                diagnostic = "".join(
                    character
                    if character in "\n\t" or ord(character) >= 32
                    else "\uFFFD"
                    for character in diagnostic
                )
                print(
                    f"FAIL {name} exit={result['exitCode']}\n{diagnostic}",
                    file=sys.stderr,
                )
    print("DONE fails:" + (" ".join(failures) if failures else "none"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
