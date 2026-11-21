from __future__ import annotations

from datetime import datetime, time
from typing import Any


def schedule_window_is_open(settings: dict[str, Any], now: datetime | None = None) -> bool:
    """Return whether queued work may start in the configured local-time window."""
    if not settings.get("processing_schedule_enabled", False):
        return True

    current = now or datetime.now().astimezone()
    current_time = current.replace(tzinfo=None).time()
    try:
        start = time.fromisoformat(str(settings["processing_schedule_start"]))
        end = time.fromisoformat(str(settings["processing_schedule_end"]))
        selected_days = {int(day) for day in settings["processing_schedule_days"]}
    except (KeyError, TypeError, ValueError):
        return False

    if not selected_days or any(day < 0 or day > 6 for day in selected_days):
        return False

    weekday = current.weekday()
    if start == end:
        return weekday in selected_days
    if start < end:
        return weekday in selected_days and start <= current_time < end

    # For an overnight window, the selected day is the day on which it starts.
    return (weekday in selected_days and current_time >= start) or (
        (weekday - 1) % 7 in selected_days and current_time < end
    )
