#!/usr/bin/env python3
"""
Compatibility launcher for BSP Generator.

This shim preserves existing behavior by delegating to app/main.py.
"""

import asyncio
import sys

from main import main


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
        if isinstance(rc, int):
            sys.exit(rc)
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)
