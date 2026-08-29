import threading
import sqlite3
from helper import utc_now
from dataclasses import dataclass, field
import roboeyes as r

import roboeyes as r

class MoodState:
    """Thread-safe mood state, shared between the API thread and the main loop.

    .get() is safe to call from either thread.
    .set() mutates the bound RoboEyes instance directly, so it must only ever
    be called from the main/pygame thread (i.e. from main.py's event loop,
    never from inside an API route handler).
    """

    MOOD_MAP = {
        "default": r.DEFAULT,
        "tired": r.TIRED,
        "angry": r.ANGRY,
        "happy": r.HAPPY,
    }
    MOOD_NAMES = {const: name for name, const in MOOD_MAP.items()} # reverse lookup to get the mood name from the RoboEyes constant

    def __init__(self, robo_eyes=None, initial="default"):
        if initial not in self.MOOD_MAP:
            raise ValueError(f"mood must be one of {sorted(self.MOOD_MAP)}")
        self.lock = threading.Lock()
        self.robo_eyes = robo_eyes
        self._mood = initial
        if robo_eyes is not None:
            robo_eyes.setMood(self.MOOD_MAP[initial])

    def get(self):
        with self.lock:
            return self._mood

    def set(self, mood):
        print('> [MoodState] Setting mood to {}'.format(mood))
        if mood not in self.MOOD_MAP:
            raise ValueError(f"mood must be one of {sorted(self.MOOD_MAP)}")
        with self.lock:
            self._mood = mood
            if self.robo_eyes is not None:
                self.robo_eyes.setMood(self.MOOD_MAP[mood])

    def set_const(self, mood_const):
        """Convenience for callers that already have a roboeyes constant (r.ANGRY, etc.)."""
        self.set(self.MOOD_NAMES[mood_const])


class ReminderStore:
    def __init__(self, path="reminders.db"):
        self.path = path
        self.lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    triggered INTEGER NOT NULL DEFAULT 0
                )"""
            )

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def create(self, title, due_at):
        with self.lock, self._connect() as connection:
            print('+ Adding Reminder {} - due at {}'.format(title, due_at))
            cursor = connection.execute(
                "INSERT INTO reminders (title, due_at) VALUES (?, ?)",
                (title, due_at),
            )
            reminder_id = cursor.lastrowid
        return self.get(reminder_id)

    def get(self, reminder_id):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, title, due_at, completed FROM reminders WHERE id = ?",
                (reminder_id,),
            ).fetchone()
        return self._as_dict(row) if row else None

    def list(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, title, due_at, completed FROM reminders "
                "WHERE completed = 0 ORDER BY due_at"
            ).fetchall()
        return [self._as_dict(row) for row in rows]

    def complete(self, reminder_id):
        with self.lock, self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET completed = 1 WHERE id = ?",
                (reminder_id,),
            )
        return self.get(reminder_id)

    def due(self):
        now = utc_now().isoformat()
        with self.lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT id, title, due_at FROM reminders "
                "WHERE completed = 0 AND triggered = 0 AND due_at <= ?",
                (now,),
            ).fetchall()
            connection.executemany(
                "UPDATE reminders SET triggered = 1 WHERE id = ?",
                [(row[0],) for row in rows],
            )
        return [{"id": row[0], "title": row[1], "due_at": row[2]} for row in rows]

    @staticmethod
    def _as_dict(row):
        return {
            "id": row[0],
            "title": row[1],
            "due_at": row[2],
            "completed": bool(row[3]),
        }



@dataclass
class ToastState:
    active_reminder: dict | None = None
    pending_reminders: list = field(default_factory=list)
    toast_started: int = 0
    toast_completed: bool = False
    happy_until: int = 0
    flash_toast: dict | None = None
    flash_started: int = 0