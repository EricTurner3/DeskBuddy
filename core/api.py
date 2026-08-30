import pygame
import json
import re

import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from core.events import REMINDER_DUE, REMINDER_COMPLETED, MOOD_CHANGED, REMINDER_CREATED
import core.actions as actions

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
        self.routes = {"GET": [], "POST": [], "DELETE": []}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)
    
    def delete(self, path):
        return self._register("DELETE", path)

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


class APIHandler(BaseHTTPRequestHandler):
    store = None        # Reminder State
    mood_state = None   # RoboEyes Mood State

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

    def do_DELETE(self):
        self._dispatch("DELETE")

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
    handler._send_json(200, actions.list_reminders(handler.store))


'''
    expects a JSON payload with either "delay_seconds" or "due_at" (ISO 8601 format).
    optional "recurrence_seconds": if set, a new reminder is auto-created at
    (this reminder's due_at + recurrence_seconds) each time this one is completed.
    {"title": "Drink water", "delay_seconds": 3600, "recurrence_seconds": 3600}
'''
@router.post("/reminders")
def create_reminder(handler):
    payload = handler._read_json()
    reminder = actions.create_reminder(
        handler.store,
        title=payload.get("title"),
        due_at=payload.get("due_at"),
        delay_seconds=payload.get("delay_seconds"),
        recurrence_seconds=payload.get("recurrence_seconds"),
    )
    handler._send_json(201, reminder)


@router.delete("/reminders/{reminder_id}")
def delete_reminder(handler, reminder_id):
    deleted = actions.delete_reminder(handler.store, int(reminder_id))
    if deleted:
        handler._send_json(200, {"deleted": True, "id": int(reminder_id)})
    else:
        handler._send_json(404, {"error": "reminder not found or already completed"})


@router.post("/reminders/{reminder_id}/complete")
def complete_reminder(handler, reminder_id):
    reminder = actions.complete_reminder(handler.store, int(reminder_id))
    if reminder is None:
        handler._send_json(404, {"error": "reminder not found"})
    else:
        handler._send_json(200, reminder)

'''
    expects a JSON payload like {"mood": "happy"}
    valid moods: default, tired, angry, happy
'''
@router.post("/mood")
def set_mood(handler):
    payload = handler._read_json()
    mood = actions.set_mood(payload.get("mood"), handler.mood_state.MOOD_MAP)
    handler._send_json(200, {"mood": mood})

@router.get("/mood")
def get_mood(handler):
    handler._send_json(200, {"mood": handler.mood_state.get()})

def run_api(store, mood_state, host="0.0.0.0", port=8765):
    APIHandler.store = store # load the ReminderStore state so it can be referenced by other calls
    APIHandler.mood_state = mood_state # load the MoodState so it can be referenced by other calls
    server = ThreadingHTTPServer((host, port), APIHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print('* API Started on {}:{}'.format(host, port))
    return server
