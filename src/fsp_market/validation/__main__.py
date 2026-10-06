"""python -m fsp_market.validation [--out artifacts/validation] [--check]

Runs the fixed dataset through the three matching methods and the assessment reference
validation, writes latest.json / latest.md and prints the summary. --check regenerates the
results and fails if they differ from the stored artifacts (reproducibility check).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fsp_market.validation.report import markdown
from fsp_market.validation.runner import run_validation, write_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(prog="fsp_market.validation")
    parser.add_argument("--out", default="artifacts/validation")
    parser.add_argument(
        "--check", action="store_true", help="compare with stored artifacts instead of writing"
    )
    args = parser.parse_args()
    res = run_validation()
    text = json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        stored = Path(args.out) / "latest.json"
        same = stored.exists() and stored.read_text(encoding="utf-8") == text
        print(
            "reproducible: artifacts match"
            if same
            else "MISMATCH: artifacts differ from a fresh run"
        )
        return 0 if same else 1
    js, md = write_artifacts(res, Path(args.out))
    print(markdown(res))
    print(f"written: {js}  {md}")
    ev = res["matching"]["summary"]["evidence_matching"]
    if ev["constraint_violations@10"] != 0:
        print("FAIL: evidence matching returned hard-constraint violations", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
