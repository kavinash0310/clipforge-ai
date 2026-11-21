from __future__ import annotations

import math
import os


def cpu_thread_budget(percent: int, logical_processors: int | None = None) -> int:
    """Translate the CPU target into a conservative per-job thread budget.

    This limits parallel worker threads rather than enforcing a hard OS CPU cap.
    """
    if percent < 25 or percent > 95:
        raise ValueError("CPU thread budget must be between 25 and 95 percent.")
    processor_count = max(1, logical_processors or os.cpu_count() or 1)
    return max(1, min(processor_count, math.floor(processor_count * percent / 100)))
