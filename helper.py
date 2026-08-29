from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)


def parse_due_at(value):
    if not value:
        raise ValueError("due_at is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()