"""Shared business-logic layer.

Single source of truth for "what happens" when a reminder is completed,
created, or deleted, or the mood changes — regardless of whether the
trigger was an HTTP request (API thread) or a direct call from the main
loop (e.g. tapping the checkmark).

Thread-safety contract: every function here may be called from either the
API thread or the main/pygame thread. They only touch thread-safe state
(ReminderStore) and post pygame events — never mood_state.set() or
robo_eyes directly, since those are main-thread-only.
"""
import pygame
from datetime import timedelta
from utils.helper import utc_now, parse_due_at
import core.events as ev

def list_reminders(store):
    """Returns a list of all reminders, sorted by due_at ascending."""
    return store.list()

def complete_reminder(store, reminder_id):
    """Marks a reminder complete (and, if recurring, spawns the next
    occurrence), posting REMINDER_COMPLETED and REMINDER_CREATED as needed.
    Returns the completed reminder dict, or None if it didn't exist."""
    reminder, next_reminder = store.complete(reminder_id)
    if reminder is not None:
        pygame.event.post(pygame.event.Event(ev.REMINDER_COMPLETED, reminder_id=reminder["id"]))
    if next_reminder is not None:
        pygame.event.post(pygame.event.Event(ev.REMINDER_CREATED, reminder=next_reminder))
    return reminder


def create_reminder(store, title, due_at=None, delay_seconds=None, recurrence_seconds=None):
    """Creates a reminder and posts REMINDER_CREATED.
    Raises ValueError on bad input — same validation regardless of caller."""
    title = str(title or "").strip()
    if not title:
        raise ValueError("title is required")

    if delay_seconds is not None:
        resolved_due_at = (utc_now() + timedelta(seconds=float(delay_seconds))).isoformat()
    else:
        resolved_due_at = parse_due_at(due_at)

    if recurrence_seconds is not None:
        recurrence_seconds = int(recurrence_seconds)
        if recurrence_seconds <= 0:
            raise ValueError("recurrence_seconds must be positive")

    reminder = store.create(title, resolved_due_at, recurrence_seconds)
    pygame.event.post(pygame.event.Event(ev.REMINDER_CREATED, reminder=reminder))
    return reminder


def delete_reminder(store, reminder_id):
    """Cancels a not-yet-completed reminder. Returns True if something was deleted."""
    return store.delete(reminder_id)

def run_reminder_scheduler(store, stop_event):
    while not stop_event.wait(1):
        for reminder in store.due():
            print('* Reminder Due: {}'.format(reminder))
            pygame.event.post(pygame.event.Event(ev.REMINDER_DUE, reminder=reminder))


def set_mood(mood, valid_moods):
    """Validates and requests a mood change by posting MOOD_CHANGED.
    Applying the mood itself still happens on the main thread in main.py,
    since robo_eyes can't be touched from here."""
    mood = str(mood or "").strip().lower()
    if mood not in valid_moods:
        raise ValueError(f"mood must be one of {sorted(valid_moods)}")
    pygame.event.post(pygame.event.Event(ev.MOOD_CHANGED, mood=mood))
    return mood