"""Shared ATPG timeout defaults for Python runners."""
from __future__ import annotations

import os

WALL_TIMEOUT_S = int(os.environ.get("ATPG_WALL_TIMEOUT", "3600"))
# 0 = off (Tier A default). Use 30 for Tier B deferred circuits.
PER_TARGET_TIMEOUT_S = float(os.environ.get("ATPG_PER_TARGET_TIMEOUT", "0"))
# 0 = all CPU cores; resolved to os.cpu_count() in runners.
ATPG_THREADS = int(os.environ.get("ATPG_THREADS", "0"))


def resolved_atpg_threads() -> int:
    n = ATPG_THREADS
    if n <= 0:
        n = os.cpu_count() or 1
    return n
