#!/usr/bin/env python3
"""Backward-compatibility shim.
Use scraper.py as the single source of truth.
"""

from scraper import *  # noqa: F401,F403


if __name__ == "__main__":
    from scraper import main
    main()
