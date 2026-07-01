#!/usr/bin/env python3
"""Convenience entry point: `python main.py <command> ...`"""

import sys

from log_analyzer.cli import main

if __name__ == "__main__":
    sys.exit(main())
