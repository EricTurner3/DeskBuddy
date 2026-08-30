import pygame
import random
from dataclasses import dataclass

CHARS_PER_SECOND = 24
HOLD_MS = 1800          # how long it stays fully visible after typing finishes
FADE_MS = 250

BUBBLE_WIDTH = 300
BUBBLE_PADDING = 16
BUBBLE_MIN_HEIGHT = 60
TAIL_SIZE = 14

REINFORCEMENT_BLURBS = [
    "You can do this!",
    "No rush — you've got this.",
    "Small steps still count.",
]


def start_blurb(blurb_state, text=random.choice(REINFORCEMENT_BLURBS), corner="top-left"):
    blurb_state.text = text
    blurb_state.corner = corner
    blurb_state.started = pygame.time.get_ticks()
    blurb_state.revealed_chars = 0
    blurb_state.finished_typing_at = None
    blurb_state.active = True


def update_blurb(blurb_state, char_sound=None):
    """Call once per frame. Advances the typewriter reveal and plays a tick
    sound for each newly revealed character. No-op when inactive."""
    if not blurb_state.active:
        return
    now = pygame.time.get_ticks()
    elapsed = now - blurb_state.started
    total_chars = len(blurb_state.text)
    target_revealed = min(total_chars, int(elapsed / 1000.0 * CHARS_PER_SECOND))

    if target_revealed > blurb_state.revealed_chars:
        blurb_state.revealed_chars = target_revealed
        if char_sound and blurb_state.text[blurb_state.revealed_chars - 1] != " ":
            char_sound.play()

    if blurb_state.revealed_chars >= total_chars and blurb_state.finished_typing_at is None:
        blurb_state.finished_typing_at = now

    if blurb_state.finished_typing_at is not None:
        if now - blurb_state.finished_typing_at >= HOLD_MS + FADE_MS:
            blurb_state.active = False


def _wrap_text(text, font, max_width):
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_blurb(window, blurb_state, robo_eyes, screen_width, screen_height, font):
    if not blurb_state.active:
        return

    now = pygame.time.get_ticks()
    alpha = 255
    if blurb_state.finished_typing_at is not None:
        fade_elapsed = now - blurb_state.finished_typing_at - HOLD_MS
        if fade_elapsed > 0:
            alpha = max(0, 255 - int(255 * (fade_elapsed / FADE_MS)))

    visible_text = blurb_state.text[:blurb_state.revealed_chars]
    max_text_width = BUBBLE_WIDTH - BUBBLE_PADDING * 2
    lines = _wrap_text(visible_text, font, max_text_width) or [""]
    line_height = font.get_height() + 4
    bubble_height = max(BUBBLE_MIN_HEIGHT, BUBBLE_PADDING * 2 + line_height * len(lines))

    eyes_rect = robo_eyes.get_eyes_rect()
    bubble_y = max(12, eyes_rect.top - bubble_height - TAIL_SIZE - 16)

    if blurb_state.corner == "top-right":
        bubble_x = eyes_rect.right - BUBBLE_WIDTH
        tail_x_frac = 0.82
    else:  # top-left
        bubble_x = eyes_rect.left
        tail_x_frac = 0.18
    bubble_x = max(12, min(bubble_x, screen_width - BUBBLE_WIDTH - 12))

    bubble = pygame.Surface((BUBBLE_WIDTH, bubble_height + TAIL_SIZE), pygame.SRCALPHA)
    pygame.draw.rect(bubble, (18, 24, 28, min(245, alpha)), (0, 0, BUBBLE_WIDTH, bubble_height), border_radius=16)
    pygame.draw.rect(bubble, (70, 214, 137, alpha), (0, 0, 6, bubble_height), border_radius=3)

    tail_x = int(BUBBLE_WIDTH * tail_x_frac)
    pygame.draw.polygon(bubble, (18, 24, 28, min(245, alpha)), [
        (tail_x - TAIL_SIZE, bubble_height - 1),
        (tail_x + TAIL_SIZE, bubble_height - 1),
        (tail_x, bubble_height + TAIL_SIZE - 1),
    ])

    for i, line in enumerate(lines):
        text_surface = font.render(line, True, (245, 250, 248))
        text_surface.set_alpha(alpha)
        bubble.blit(text_surface, (BUBBLE_PADDING, BUBBLE_PADDING + i * line_height))

    window.blit(bubble, (bubble_x, bubble_y))