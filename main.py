import pygame
import sys
import random
import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# Constants for colors
BGCOLOR = (0, 0, 0)           # Black background
COLOR = [
    (125, 249, 255),     # DEFAULT, Blue eyes
    (50, 249, 50),       # TIRED, yellow eyes
    (255, 0, 0),         # ANGRY, Red eyes
    (0, 249, 255)        # HAPPY, GREEN eyes
]
MAINCOLOR = (125, 249, 255)   # Blue eyes

# Mood Types
DEFAULT = 0
TIRED = 1
ANGRY = 2
HAPPY = 3

# Predefined Positions
N = 1   # North, top center
NE = 2  # North-east, top right
E = 3   # East, middle right
SE = 4  # South-east, bottom right
S = 5   # South, bottom center
SW = 6  # South-west, bottom left
W = 7   # West, middle left
NW = 8  # North-west, top left

REMINDER_DUE = pygame.USEREVENT + 1
REMINDER_COMPLETED = pygame.USEREVENT + 2
TOAST_BAND_HEIGHT = 140


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
        if urlparse(self.path).path == "/reminders":
            self._send_json(200, self.store.list())
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        print('* Received new Reminder: {}'.format(self))
        try:
            payload = self._read_json()
            if path == "/reminders":
                title = str(payload.get("title", "")).strip()
                if not title:
                    raise ValueError("title is required")
                if payload.get("delay_seconds") is not None:
                    due_at = (utc_now() + timedelta(seconds=float(payload["delay_seconds"]))).isoformat()
                else:
                    due_at = parse_due_at(payload.get("due_at"))
                self._send_json(201, self.store.create(title, due_at))
                return

            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "reminders" and parts[2] == "complete":
                reminder = self.store.complete(int(parts[1]))
                if reminder is None:
                    self._send_json(404, {"error": "reminder not found"})
                else:
                    pygame.event.post(pygame.event.Event(REMINDER_COMPLETED, reminder_id=reminder["id"]))
                    self._send_json(200, reminder)
                return
            self._send_json(404, {"error": "not found"})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})

    def log_message(self, format_string, *args):
        return


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

class RoboEyes:
    def __init__(self, draw_surface, width=320, height=240, frame_rate=50):
        """
        Initialize the RoboEyes class.

        :param draw_surface: Pygame surface to draw on.
        :param width: Screen width in pixels (unrotated).
        :param height: Screen height in pixels (unrotated).
        :param frame_rate: Maximum frames per second.
        """
        self.surface = draw_surface
        self.screen_width = width
        self.screen_height = height
        self.frame_interval = 1000 / frame_rate  # in milliseconds
        self.fps_timer = pygame.time.get_ticks()

        # Mood and expressions
        self.tired = False
        self.angry = False
        self.happy = False
        self.curious = False
        self.cyclops = False
        self.eyeL_open = False
        self.eyeR_open = False
        self.eye_color = COLOR[DEFAULT]

        # Eye Geometry
        self.space_between_default = 10  # Reduced space for larger eyes
        self.space_between_current = self.space_between_default
        self.space_between_next = self.space_between_default

        # Left Eye
        self.eyeLwidth_default = 100   # Increased size proportionally
        self.eyeLheight_default = 100
        self.eyeLwidth_current = self.eyeLwidth_default
        self.eyeLheight_current = 1  # start with closed eye
        self.eyeLwidth_next = self.eyeLwidth_default
        self.eyeLheight_next = self.eyeLheight_default
        self.eyeLheight_offset = 0

        self.eyeLborder_radius_default = 20  # Increased radius for larger eyes
        self.eyeLborder_radius_current = self.eyeLborder_radius_default
        self.eyeLborder_radius_next = self.eyeLborder_radius_default

        # Right Eye
        self.eyeRwidth_default = self.eyeLwidth_default
        self.eyeRheight_default = self.eyeLheight_default
        self.eyeRwidth_current = self.eyeRwidth_default
        self.eyeRheight_current = 1  # start with closed eye
        self.eyeRwidth_next = self.eyeRwidth_default
        self.eyeRheight_next = self.eyeRheight_default
        self.eyeRheight_offset = 0

        self.eyeRborder_radius_default = 20
        self.eyeRborder_radius_current = self.eyeRborder_radius_default
        self.eyeRborder_radius_next = self.eyeRborder_radius_default

        # Coordinates
        self.eyeLx_default = (self.screen_width - (self.eyeLwidth_default + self.space_between_default + self.eyeRwidth_default)) // 2
        self.eyeLy_default = (self.screen_height - self.eyeLheight_default) // 2
        self.eyeLx = self.eyeLx_default
        self.eyeLy = self.eyeLy_default
        self.eyeLx_next = self.eyeLx
        self.eyeLy_next = self.eyeLy

        self.eyeRx_default = self.eyeLx + self.eyeLwidth_current + self.space_between_default
        self.eyeRy_default = self.eyeLy
        self.eyeRx = self.eyeRx_default
        self.eyeRy = self.eyeRy_default
        self.eyeRx_next = self.eyeRx
        self.eyeRy_next = self.eyeRy

        # Both Eyes
        self.eyelids_height_max = self.eyeLheight_default // 2
        self.eyelids_tired_height = 0
        self.eyelids_tired_height_next = self.eyelids_tired_height
        self.eyelids_angry_height = 0
        self.eyelids_angry_height_next = self.eyelids_angry_height
        self.eyelids_happy_bottom_offset_max = (self.eyeLheight_default // 2) + 6  # Adjusted for larger eyes
        self.eyelids_happy_bottom_offset = 0
        self.eyelids_happy_bottom_offset_next = 0

        # Macro Animations
        self.hFlicker = False
        self.hFlicker_alternate = False
        self.hFlicker_amplitude = 4  # Increased amplitude for larger screen

        self.vFlicker = False
        self.vFlicker_alternate = False
        self.vFlicker_amplitude = 20  # Increased amplitude for larger screen

        self.autoblinker = False
        self.blink_interval = 2000  # in milliseconds (2 seconds)
        self.blink_interval_variation = 4000  # in milliseconds
        self.blink_timer = pygame.time.get_ticks()

        self.idle = False
        self.idle_interval = 5000  # in milliseconds (5 seconds)
        self.idle_interval_variation = 5000  # in milliseconds
        self.idle_animation_timer = pygame.time.get_ticks()

        self.confused = False
        self.confused_animation_timer = 0
        self.confused_animation_duration = 500  # in milliseconds
        self.confused_toggle = True

        self.laugh = False
        self.laugh_animation_timer = 0
        self.laugh_animation_duration = 500  # in milliseconds
        self.laugh_toggle = True

    # General Setup
    def begin(self):
        self.clear_display()
        self.eyeLheight_current = 1
        self.eyeRheight_current = 1

    def update(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.fps_timer >= self.frame_interval:
            self.drawEyes()
            self.fps_timer = current_time

    # Setter Methods
    def setFramerate(self, fps):
        self.frame_interval = 1000 / fps

    def setWidth(self, leftEye, rightEye):
        self.eyeLwidth_next = leftEye
        self.eyeRwidth_next = rightEye
        self.eyeLwidth_default = leftEye
        self.eyeRwidth_default = rightEye

    def setHeight(self, leftEye, rightEye):
        self.eyeLheight_next = leftEye
        self.eyeRheight_next = rightEye
        self.eyeLheight_default = leftEye
        self.eyeRheight_default = rightEye

    def setBorderradius(self, leftEye, rightEye):
        self.eyeLborder_radius_next = leftEye
        self.eyeRborder_radius_next = rightEye
        self.eyeLborder_radius_default = leftEye
        self.eyeRborder_radius_default = rightEye

    def setSpacebetween(self, space):
        self.space_between_next = space
        self.space_between_default = space

    def setMood(self, mood):
        self.angry = False
        self.happy = False
        self.tired = False

        if mood == TIRED:
            self.tired = True
        elif mood == ANGRY:
            self.angry = True
        elif mood == HAPPY:
            self.happy = True
        
        self.eye_color = COLOR[mood]

    def setPosition(self, position):
        if position == N:
            self.eyeLx_next = self.getScreenConstraint_X() // 2
            self.eyeLy_next = 0
        elif position == NE:
            self.eyeLx_next = self.getScreenConstraint_X()
            self.eyeLy_next = 0
        elif position == E:
            self.eyeLx_next = self.getScreenConstraint_X()
            self.eyeLy_next = self.getScreenConstraint_Y() // 2
        elif position == SE:
            self.eyeLx_next = self.getScreenConstraint_X()
            self.eyeLy_next = self.getScreenConstraint_Y()
        elif position == S:
            self.eyeLx_next = self.getScreenConstraint_X() // 2
            self.eyeLy_next = self.getScreenConstraint_Y()
        elif position == SW:
            self.eyeLx_next = 0
            self.eyeLy_next = self.getScreenConstraint_Y()
        elif position == W:
            self.eyeLx_next = 0
            self.eyeLy_next = self.getScreenConstraint_Y() // 2
        elif position == NW:
            self.eyeLx_next = 0
            self.eyeLy_next = 0
        else:
            # Default: Middle center
            self.eyeLx_next = self.getScreenConstraint_X() // 2
            self.eyeLy_next = self.getScreenConstraint_Y() // 2

    def setAutoblinker(self, active, interval=2, variation=4):
        """
        Set automated eye blinking.

        :param active: Boolean to activate/deactivate autoblinker.
        :param interval: Basic interval between each blink in seconds.
        :param variation: Interval variation range in seconds.
        """
        self.autoblinker = active
        self.blink_interval = interval * 1000  # convert to milliseconds
        self.blink_interval_variation = variation * 1000  # convert to milliseconds

    def setIdleMode(self, active, interval=5, variation=5):
        """
        Set idle mode for automated eye repositioning.

        :param active: Boolean to activate/deactivate idle mode.
        :param interval: Basic interval between each repositioning in seconds.
        :param variation: Interval variation range in seconds.
        """
        self.idle = active
        self.idle_interval = interval * 1000  # convert to milliseconds
        self.idle_interval_variation = variation * 1000  # convert to milliseconds

    def setCuriosity(self, curious_bit):
        self.curious = curious_bit

    def setCyclops(self, cyclops_bit):
        self.cyclops = cyclops_bit

    def setHFlicker(self, flicker_bit, amplitude=4):
        self.hFlicker = flicker_bit
        self.hFlicker_amplitude = amplitude

    def setVFlicker(self, flicker_bit, amplitude=20):
        self.vFlicker = flicker_bit
        self.vFlicker_amplitude = amplitude

    # Getter Methods
    def getScreenConstraint_X(self):
        return self.screen_width - self.eyeLwidth_current - self.space_between_current - self.eyeRwidth_current

    def getScreenConstraint_Y(self):
        return self.screen_height - self.eyeLheight_default - TOAST_BAND_HEIGHT

    # Blinking Methods
    def close(self, left=True, right=True):
        if left:
            self.eyeLheight_next = 1
            self.eyeL_open = False
        if right:
            self.eyeRheight_next = 1
            self.eyeR_open = False

    def open_eyes(self, left=True, right=True):
        if left:
            self.eyeL_open = True
        if right:
            self.eyeR_open = True

    def blink(self, left=True, right=True):
        self.close(left, right)
        self.open_eyes(left, right)

    # Macro Animation Methods
    def anim_confused(self):
        self.confused = True

    def anim_laugh(self):
        self.laugh = True

    # Drawing Methods
    def drawEyes(self):
        current_time = pygame.time.get_ticks()

        # Pre-Calculations
        if self.curious:
            if self.eyeLx_next <= 20:  # Adjusted threshold for larger screen
                self.eyeLheight_offset = 16
            elif self.eyeLx_next >= (self.getScreenConstraint_X() - 20) and self.cyclops:
                self.eyeLheight_offset = 16
            else:
                self.eyeLheight_offset = 0  # left eye

            if self.eyeRx_next >= self.screen_width - self.eyeRwidth_current - 20:
                self.eyeRheight_offset = 16
            else:
                self.eyeRheight_offset = 0  # right eye
        else:
            self.eyeLheight_offset = 0
            self.eyeRheight_offset = 0

        # Left eye height
        self.eyeLheight_current = (self.eyeLheight_current + self.eyeLheight_next + self.eyeLheight_offset) // 2
        self.eyeLy += ((self.eyeLheight_default - self.eyeLheight_current) // 2)
        self.eyeLy -= self.eyeLheight_offset // 2

        # Right eye height
        self.eyeRheight_current = (self.eyeRheight_current + self.eyeRheight_next + self.eyeRheight_offset) // 2
        self.eyeRy += ((self.eyeRheight_default - self.eyeRheight_current) // 2)
        self.eyeRy -= self.eyeRheight_offset // 2

        # Open eyes again after closing them
        if self.eyeL_open:
            if self.eyeLheight_current <= 1 + self.eyeLheight_offset:
                self.eyeLheight_next = self.eyeLheight_default

        if self.eyeR_open:
            if self.eyeRheight_current <= 1 + self.eyeRheight_offset:
                self.eyeRheight_next = self.eyeRheight_default

        # Left eye width
        self.eyeLwidth_current = (self.eyeLwidth_current + self.eyeLwidth_next) // 2

        # Right eye width
        self.eyeRwidth_current = (self.eyeRwidth_current + self.eyeRwidth_next) // 2

        # Space between eyes
        self.space_between_current = (self.space_between_current + self.space_between_next) // 2

        # Left eye coordinates
        self.eyeLx = (self.eyeLx + self.eyeLx_next) // 2
        self.eyeLy = (self.eyeLy + self.eyeLy_next) // 2

        # Right eye coordinates
        self.eyeRx_next = self.eyeLx_next + self.eyeLwidth_current + self.space_between_current
        self.eyeRy_next = self.eyeLy_next
        self.eyeRx = (self.eyeRx + self.eyeRx_next) // 2
        self.eyeRy = (self.eyeRy + self.eyeRy_next) // 2

        # Left eye border radius
        self.eyeLborder_radius_current = (self.eyeLborder_radius_current + self.eyeLborder_radius_next) // 2

        # Right eye border radius
        self.eyeRborder_radius_current = (self.eyeRborder_radius_current + self.eyeRborder_radius_next) // 2

        # Apply Macro Animations
        if self.autoblinker and (current_time >= self.blink_timer):
            self.blink()
            variation = random.randint(0, self.blink_interval_variation)
            self.blink_timer = current_time + self.blink_interval + variation

        # Laugh Animation
        if self.laugh:
            if self.laugh_toggle:
                self.setVFlicker(True, 10)  # Increased amplitude for larger screen
                self.laugh_animation_timer = current_time
                self.laugh_toggle = False
            elif current_time >= self.laugh_animation_timer + self.laugh_animation_duration:
                self.setVFlicker(False, 0)
                self.laugh_toggle = True
                self.laugh = False

        # Confused Animation
        if self.confused:
            if self.confused_toggle:
                self.setHFlicker(True, 40)  # Increased amplitude for larger screen
                self.confused_animation_timer = current_time
                self.confused_toggle = False
            elif current_time >= self.confused_animation_timer + self.confused_animation_duration:
                self.setHFlicker(False, 0)
                self.confused_toggle = True
                self.confused = False

        # Idle Animation
        if self.idle and (current_time >= self.idle_animation_timer):
            self.eyeLx_next = random.randint(0, self.getScreenConstraint_X())
            self.eyeLy_next = random.randint(0, self.getScreenConstraint_Y())
            variation = random.randint(0, self.idle_interval_variation)
            self.idle_animation_timer = current_time + self.idle_interval + variation

        # Horizontal Flicker
        if self.hFlicker:
            if self.hFlicker_alternate:
                self.eyeLx += self.hFlicker_amplitude
                self.eyeRx += self.hFlicker_amplitude
            else:
                self.eyeLx -= self.hFlicker_amplitude
                self.eyeRx -= self.hFlicker_amplitude
            self.hFlicker_alternate = not self.hFlicker_alternate

        # Vertical Flicker
        if self.vFlicker:
            if self.vFlicker_alternate:
                self.eyeLy += self.vFlicker_amplitude
                self.eyeRy += self.vFlicker_amplitude
            else:
                self.eyeLy -= self.vFlicker_amplitude
                self.eyeRy -= self.vFlicker_amplitude
            self.vFlicker_alternate = not self.vFlicker_alternate

        # Cyclops Mode
        if self.cyclops:
            self.eyeRwidth_current = 0
            self.eyeRheight_current = 0
            self.space_between_current = 0

        # Clear Display
        self.clear_display()

        # Draw Eyes
        self.draw_eye(self.eyeLx, self.eyeLy, self.eyeLwidth_current, self.eyeLheight_current,
                     self.eyeLborder_radius_current, self.eye_color)
        if not self.cyclops:
            self.draw_eye(self.eyeRx, self.eyeRy, self.eyeRwidth_current, self.eyeRheight_current,
                         self.eyeRborder_radius_current, self.eye_color)

        # Mood Transitions
        if self.tired:
            self.eyelids_tired_height_next = self.eyeLheight_current // 2
            self.eyelids_angry_height_next = 0
        else:
            self.eyelids_tired_height_next = 0

        if self.angry:
            self.eyelids_angry_height_next = self.eyeLheight_current // 2
            self.eyelids_tired_height_next = 0
        else:
            self.eyelids_angry_height_next = 0

        if self.happy:
            self.eyelids_happy_bottom_offset_next = self.eyeLheight_current // 2
        else:
            self.eyelids_happy_bottom_offset_next = 0

        # Draw Tired Eyelids
        self.eyelids_tired_height = (self.eyelids_tired_height + self.eyelids_tired_height_next) // 2
        if not self.cyclops:
            # Left Eye
            points_left = [
                (self.eyeLx, self.eyeLy - 1),
                (self.eyeLx + self.eyeLwidth_current, self.eyeLy - 1),
                (self.eyeLx, self.eyeLy + self.eyelids_tired_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_left)

            # Right Eye
            points_right = [
                (self.eyeRx, self.eyeRy - 1),
                (self.eyeRx + self.eyeRwidth_current, self.eyeRy - 1),
                (self.eyeRx + self.eyeRwidth_current, self.eyeRy + self.eyelids_tired_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_right)
        else:
            # Cyclops Tired Eyelids
            half_width = self.eyeLwidth_current // 2
            points_left = [
                (self.eyeLx, self.eyeLy - 1),
                (self.eyeLx + half_width, self.eyeLy - 1),
                (self.eyeLx, self.eyeLy + self.eyelids_tired_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_left)

            points_right = [
                (self.eyeLx + half_width, self.eyeLy - 1),
                (self.eyeLx + self.eyeLwidth_current, self.eyeLy - 1),
                (self.eyeLx + self.eyeLwidth_current, self.eyeLy + self.eyelids_tired_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_right) 

        # Draw Angry Eyelids
        self.eyelids_angry_height = (self.eyelids_angry_height + self.eyelids_angry_height_next) // 2
        if not self.cyclops:
            # Left Eye
            points_left = [
                (self.eyeLx, self.eyeLy - 1),
                (self.eyeLx + self.eyeLwidth_current, self.eyeLy - 1),
                (self.eyeLx + self.eyeLwidth_current, self.eyeLy + self.eyelids_angry_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_left)

            # Right Eye
            points_right = [
                (self.eyeRx, self.eyeRy - 1),
                (self.eyeRx + self.eyeRwidth_current, self.eyeRy - 1),
                (self.eyeRx, self.eyeRy + self.eyelids_angry_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_right)
        else:
            # Cyclops Angry Eyelids
            half_width = self.eyeLwidth_current // 2
            points_left = [
                (self.eyeLx, self.eyeLy - 1),
                (self.eyeLx + half_width, self.eyeLy - 1),
                (self.eyeLx + half_width, self.eyeLy + self.eyelids_angry_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_left)

            points_right = [
                (self.eyeLx + half_width, self.eyeLy - 1),
                (self.eyeLx + self.eyeLwidth_current, self.eyeLy - 1),
                (self.eyeLx + half_width, self.eyeLy + self.eyelids_angry_height - 1)
            ]
            pygame.draw.polygon(self.surface, BGCOLOR, points_right)

        # Draw Happy Eyelids
        self.eyelids_happy_bottom_offset = (self.eyelids_happy_bottom_offset + self.eyelids_happy_bottom_offset_next) // 2
        pygame.draw.rect(self.surface, BGCOLOR,
                         (self.eyeLx - 2, (self.eyeLy + self.eyeLheight_current) - self.eyelids_happy_bottom_offset + 2,
                          self.eyeLwidth_current + 4, self.eyeLheight_default))
        if not self.cyclops:
            pygame.draw.rect(self.surface, BGCOLOR,
                             (self.eyeRx - 2, (self.eyeRy + self.eyeRheight_current) - self.eyelids_happy_bottom_offset + 2,
                              self.eyeRwidth_current + 4, self.eyeRheight_default))

        # Update Display (Handled externally)
        # pygame.display.flip()  # Removed to handle rotation externally

    def draw_eye(self, x, y, width, height, border_radius, color):
        # Draw a rounded rectangle representing an eye
        eye_rect = pygame.Rect(x, y, width, height)
        if border_radius > 0:
            pygame.draw.rect(self.surface, color, eye_rect, border_radius=border_radius)
        else:
            pygame.draw.rect(self.surface, color, eye_rect)

    def clear_display(self):
        self.surface.fill(BGCOLOR)

# Example usage within a Pygame application
def main():
    pygame.init()

    # Screen settings
    screen_width = 1024   # Rotated width
    screen_height = 600  # Rotated height
    window = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("RoboEyes Simulation")

    # Create a separate surface for drawing (unrotated)
    draw_width = 1024
    draw_height = 600
    draw_surface = pygame.Surface((draw_width, draw_height))
    draw_surface.fill(BGCOLOR)  # Ensure it's cleared initially

    # Create RoboEyes instance
    robo_eyes = RoboEyes(draw_surface, width=draw_width, height=draw_height, frame_rate=60)
    robo_eyes.begin()

    # Example configurations
    robo_eyes.setMood(DEFAULT)
    robo_eyes.setAutoblinker(True, interval=6, variation=7)
    robo_eyes.setIdleMode(True, interval=5, variation=5)
    robo_eyes.setCuriosity(True)
    robo_eyes.setWidth(250,250)
    robo_eyes.setHeight(300,300)
    robo_eyes.setSpacebetween(40)
    robo_eyes.setBorderradius(40, 40)
    # robo_eyes.setCyclops(False)
    # robo_eyes.setHFlicker(True, amplitude=1)
    # robo_eyes.setVFlicker(True, amplitude=1)

    clock = pygame.time.Clock()
    store = ReminderStore()
    api_server = run_reminder_api(store)
    stop_scheduler = threading.Event()
    threading.Thread(
        target=run_reminder_scheduler,
        args=(store, stop_scheduler),
        daemon=True,
    ).start()
    toast_font = pygame.font.Font(None, 30)
    toast_small_font = pygame.font.Font(None, 22)
    active_reminder = None
    pending_reminders = []
    toast_started = 0
    toast_completed = False
    happy_until = 0

    def complete_reminder(reminder_id):
        nonlocal toast_completed, happy_until
        store.complete(reminder_id)
        toast_completed = True
        happy_until = pygame.time.get_ticks() + 2500
        robo_eyes.setMood(HAPPY)

    def draw_toast(reminder, started, completed):
        elapsed = pygame.time.get_ticks() - started
        progress = min(1.0, elapsed / 350.0)
        toast_width, toast_height = 440, 100
        target_x = screen_width - toast_width - 24
        target_y = screen_height - toast_height - 24
        toast_y = screen_height + 8 - int((toast_height + 32) * progress)
        toast = pygame.Surface((toast_width, toast_height), pygame.SRCALPHA)
        pygame.draw.rect(toast, (18, 24, 28, 245), toast.get_rect(), border_radius=14)
        pygame.draw.rect(toast, (70, 214, 137), (0, 0, 6, toast_height), border_radius=3)
        title = toast_font.render(reminder["title"], True, (245, 250, 248))
        toast.blit(title, (24, 18))
        status = "Completed" if completed else "Tap the checkmark when done"
        status_color = (120, 232, 160) if completed else (174, 190, 194)
        toast.blit(toast_small_font.render(status, True, status_color), (24, 55))
        button_rect = pygame.Rect(toast_width - 76, 22, 52, 52)
        pygame.draw.rect(toast, (57, 190, 116) if completed else (38, 62, 58), button_rect, border_radius=12)
        pygame.draw.line(toast, (235, 255, 240), (button_rect.x + 14, button_rect.y + 27),
                         (button_rect.x + 23, button_rect.y + 36), 4)
        pygame.draw.line(toast, (235, 255, 240), (button_rect.x + 23, button_rect.y + 36),
                         (button_rect.x + 39, button_rect.y + 17), 4)
        window.blit(toast, (target_x, target_y if progress >= 1 else toast_y))
        return pygame.Rect(target_x + button_rect.x, target_y + button_rect.y, button_rect.width, button_rect.height)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_scheduler.set()
                api_server.shutdown()
                pygame.quit()
                sys.exit()

            if event.type == REMINDER_DUE:
                if active_reminder is None:
                    active_reminder = event.reminder
                    toast_started = pygame.time.get_ticks()
                    toast_completed = False
                    robo_eyes.setMood(ANGRY)
                else:
                    pending_reminders.append(event.reminder)

            if event.type == REMINDER_COMPLETED and active_reminder and event.reminder_id == active_reminder["id"]:
                toast_completed = True
                happy_until = pygame.time.get_ticks() + 2500
                robo_eyes.setMood(HAPPY)

            # Example: Change mood with key presses
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    robo_eyes.setMood(TIRED)
                elif event.key == pygame.K_2:
                    robo_eyes.setMood(ANGRY)
                elif event.key == pygame.K_3:
                    robo_eyes.setMood(HAPPY)
                elif event.key == pygame.K_0:
                    robo_eyes.setMood(DEFAULT)
                elif event.key == pygame.K_c:
                    robo_eyes.anim_confused()
                elif event.key == pygame.K_5:
                    robo_eyes.anim_laugh()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and active_reminder and not toast_completed:
                checkmark_rect = draw_toast(active_reminder, toast_started, toast_completed)
                if checkmark_rect.collidepoint(event.pos):
                    complete_reminder(active_reminder["id"])

        # Update RoboEyes
        robo_eyes.update()

        # Rotate the draw_surface by 90 degrees clockwise
        rotated_surface = pygame.transform.rotate(draw_surface, 0)
        rotated_rect = rotated_surface.get_rect(center=window.get_rect().center)

        # Clear the window before blitting
        window.fill(BGCOLOR)

        # Blit the rotated surface onto the main window
        window.blit(rotated_surface, rotated_rect)

        if active_reminder:
            checkmark_rect = draw_toast(active_reminder, toast_started, toast_completed)
            if toast_completed and pygame.time.get_ticks() >= happy_until:
                robo_eyes.setMood(DEFAULT)
                active_reminder = pending_reminders.pop(0) if pending_reminders else None
                if active_reminder:
                    toast_started = pygame.time.get_ticks()
                    toast_completed = False

        # Optional Debug Drawings
        # Uncomment the following lines to add debug shapes
        # pygame.draw.rect(draw_surface, (255, 0, 0), (10, 10, 50, 50))  # Red square for debugging
        # pygame.draw.circle(draw_surface, (0, 255, 0), (160, 120), 10)  # Green circle at center

        # Update the display
        pygame.display.flip()

        # Limit to 60 FPS
        clock.tick(60)

if __name__ == "__main__":
    main()
