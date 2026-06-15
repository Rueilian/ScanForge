"""ITC'99 benchmark tiers — Python mirror of itc99_benchmark_scope.sh."""
from __future__ import annotations

import os

ITC_ACTIVE = ["b03", "b04", "b05", "b07", "b08", "b09", "b11", "b13"]
ITC_DEFERRED = ["b12", "b14", "b15"]
ITC_OUT_OF_SCOPE = ["b17", "b18", "b20", "b21", "b22"]
ITC_ALL = ITC_ACTIVE + ITC_DEFERRED

if os.environ.get("ITC_INCLUDE_DEFERRED") == "1":
    ITC_ATPG = list(ITC_ALL)
else:
    ITC_ATPG = list(ITC_ACTIVE)
