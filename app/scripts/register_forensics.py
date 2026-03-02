#!/usr/bin/env python3
"""
Generate deterministic register-access forensics and critical sequence diffs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from modules.validation.register_parity_guard import (
        default_critical_registers,
        run_parity_guard,
    )

    parser = argparse.ArgumentParser(description="Register forensics and parity comparison")
    parser.add_argument("--candidate", required=True, help="Candidate output directory")
    parser.add_argument("--baseline", required=True, help="Baseline output directory")
    parser.add_argument(
        "--mode",
        default="critical_only",
        choices=["critical_only", "strict", "off"],
        help="Comparison mode",
    )
    parser.add_argument(
        "--critical",
        nargs="*",
        default=None,
        help="Override critical register list",
    )
    args = parser.parse_args()

    candidate = Path(args.candidate).resolve()
    baseline = Path(args.baseline).resolve()
    critical = args.critical if args.critical else default_critical_registers()

    result = run_parity_guard(
        candidate,
        baseline,
        mode=args.mode,
        critical_registers=critical,
    )
    print(json.dumps(result, indent=2))
    return 0 if bool(result.get("passes", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
