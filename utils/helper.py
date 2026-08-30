from datetime import datetime, timezone, timedelta

def utc_now():
    return datetime.now(timezone.utc)


def parse_due_at(value):
    if not value:
        raise ValueError("due_at is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()

def next_due_at(previous_due_at, recurrence_seconds):
    prev = datetime.fromisoformat(previous_due_at)
    nxt = prev + timedelta(seconds=recurrence_seconds) # change prev to utc_now() to ensure consistent timing
    return nxt.astimezone(timezone.utc).isoformat()

def format_relative_due(due_at_iso):
    due = datetime.fromisoformat(due_at_iso)
    delta = (due - utc_now()).total_seconds()
    if delta <= 0:
        return "Due now"
    minutes = int(delta // 60)
    if minutes < 1:
        return "In under a minute"
    if minutes < 60:
        return f"In {minutes}m"
    hours, remaining_minutes = divmod(minutes, 60)
    if hours < 24:
        return f"In {hours}h {remaining_minutes}m" if remaining_minutes else f"In {hours}h"
    return f"In {hours // 24}d"