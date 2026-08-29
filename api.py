import pygame
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse



REMINDER_DUE = pygame.USEREVENT + 1
REMINDER_COMPLETED = pygame.USEREVENT + 2
TOAST_BAND_HEIGHT = 140


class Router:
    """Minimal FastAPI-style router for BaseHTTPRequestHandler.

    Usage:
        router = Router()

        @router.get("/reminders")
        def list_reminders(handler):
            ...

        @router.post("/reminders/{reminder_id}/complete")
        def complete_reminder(handler, reminder_id):
            ...
    """

    def __init__(self):
        self.routes = {"GET": [], "POST": []}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def _register(self, method, path):
        pattern = self._compile(path)

        def decorator(func):
            self.routes[method].append((pattern, func))
            return func

        return decorator

    @staticmethod
    def _compile(path):
        # "/reminders/{reminder_id}/complete" -> regex with named groups
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        return re.compile(f"^{pattern}$")

    def match(self, method, path):
        for pattern, func in self.routes.get(method, []):
            m = pattern.match(path)
            if m:
                return func, m.groupdict()
        return None, None


router = Router()


def utc_now():
    return datetime.now(timezone.utc)


def parse_due_at(value):
    if not value:
        raise ValueError("due_at is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


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


class ReminderHandler(BaseHTTPRequestHandler):
    store = None

    def __str__(self):
        return f"{self.command} {self.path}"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        data = self.rfile.read(length).decode('utf-8')
        # print(data)
        return json.loads(data)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        print('* Received request: {}'.format(self))
        self._dispatch("POST")

    def _dispatch(self, method):
        path = urlparse(self.path).path
        func, params = router.match(method, path)
        if func is None:
            self._send_json(404, {"error": "not found"})
            return
        try:
            func(self, **params)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})

    def log_message(self, format_string, *args):
        return


@router.get("/reminders")
def list_reminders(handler):
    handler._send_json(200, handler.store.list())


'''
    expects a JSON payload with either "delay_seconds" or "due_at" (ISO 8601 format) to create a new reminder.
    {"title": "Example Reminder", "delay_seconds": 3600}
    {"title": "Example Reminder", "due_at": "2024-06-01T12:00:00Z"}
'''
@router.post("/reminders")
def create_reminder(handler):
    payload = handler._read_json()
    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValueError("title is required")
    if payload.get("delay_seconds") is not None:
        due_at = (utc_now() + timedelta(seconds=float(payload["delay_seconds"]))).isoformat()
    else:
        due_at = parse_due_at(payload.get("due_at"))
    handler._send_json(201, handler.store.create(title, due_at))


@router.post("/reminders/{reminder_id}/complete")
def complete_reminder(handler, reminder_id):
    reminder = handler.store.complete(int(reminder_id))
    if reminder is None:
        handler._send_json(404, {"error": "reminder not found"})
    else:
        pygame.event.post(pygame.event.Event(REMINDER_COMPLETED, reminder_id=reminder["id"]))
        handler._send_json(200, reminder)


def run_reminder_api(store, host="0.0.0.0", port=8765):
    ReminderHandler.store = store
    server = ThreadingHTTPServer((host, port), ReminderHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print('* API Started on {}:{}'.format(host, port))
    return server


def run_reminder_scheduler(store, stop_event):
    while not stop_event.wait(1):
        for reminder in store.due():
            print('* Reminder Due: {}'.format(reminder))
            pygame.event.post(pygame.event.Event(REMINDER_DUE, reminder=reminder))