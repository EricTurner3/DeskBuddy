import pygame

FLASH_TOAST_DURATION_MS = 4000
TOAST_WIDTH = 440
TOAST_HEIGHT = 100
TOAST_MARGIN = 24


# human readable location on screen
def location(screen_width, screen_height,position, toast_width=TOAST_WIDTH, toast_height=TOAST_HEIGHT):
    if position == "top-left":
        return TOAST_MARGIN, TOAST_MARGIN
    elif position == "top-right":
        return screen_width - toast_width - TOAST_MARGIN, TOAST_MARGIN
    elif position == "bottom-left":
        return TOAST_MARGIN, screen_height - toast_height - TOAST_MARGIN
    elif position == "bottom-right":
        return screen_width - toast_width - TOAST_MARGIN, screen_height - toast_height - TOAST_MARGIN
    else:
        raise ValueError(f"Invalid position: {position}")

# button for the checkmark in the reminder toast, used for click detection
def get_checkmark_rect(screen_width, screen_height, toast_width=TOAST_WIDTH, toast_height=TOAST_HEIGHT, toast_location="bottom-right"):
    target_x, target_y = location(screen_width, screen_height, toast_location, toast_width, toast_height)
    button_rect = pygame.Rect(toast_width - 76, 22, 52, 52)
    return pygame.Rect(target_x + button_rect.x, target_y + button_rect.y,
                        button_rect.width, button_rect.height)


# persistent toast which remains on screen until the user clicks the checkmark
def draw_persistent_toast(window, title, started, completed, screen_width, screen_height, toast_font, toast_small_font, toast_location="bottom-right"):
    elapsed = pygame.time.get_ticks() - started
    progress = min(1.0, elapsed / 350.0)
    toast_width, toast_height = TOAST_WIDTH, TOAST_HEIGHT
    target_x, target_y = location(screen_width, screen_height, toast_location, toast_width, toast_height)
    toast_y = screen_height + 8 - int((toast_height + 32) * progress)
    toast = pygame.Surface((toast_width, toast_height), pygame.SRCALPHA)
    pygame.draw.rect(toast, (18, 24, 28, 245), toast.get_rect(), border_radius=14)
    pygame.draw.rect(toast, (70, 214, 137), (0, 0, 6, toast_height), border_radius=3)
    toast_title = toast_font.render(title, True, (245, 250, 248))
    toast.blit(toast_title, (24, 18))
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

# disappearing toast with progress bar
def draw_flash_toast(window, title, subtitle, started, duration_ms, screen_width, screen_height, toast_font, toast_small_font, toast_location="bottom-left"):
    elapsed = pygame.time.get_ticks() - started
    slide_progress = min(1.0, elapsed / 250.0) # slide in over 250ms
    remaining_fraction = max(0.0, 1.0 - (elapsed / duration_ms))
    toast_width, toast_height = TOAST_WIDTH, TOAST_HEIGHT
    target_x, target_y = location(screen_width, screen_height, toast_location, toast_width, toast_height)
    toast_x = screen_width + 8 - int((toast_width + 32) * slide_progress)

    toast = pygame.Surface((toast_width, toast_height), pygame.SRCALPHA)
    pygame.draw.rect(toast, (18, 24, 28, 245), toast.get_rect(), border_radius=14)
    pygame.draw.rect(toast, (125, 200, 255), (0, 0, 6, toast_height), border_radius=3)

    toast_title = toast_font.render(title, True, (245, 250, 248))
    toast.blit(toast_title, (24, 16))
    toast.blit(toast_small_font.render(subtitle, True, (174, 190, 194)), (24, 48))

    # Countdown progress bar along the bottom
    bar_margin = 16
    bar_height = 4
    bar_full_width = toast_width - (bar_margin * 2)
    bar_y = toast_height - bar_height - 10
    pygame.draw.rect(toast, (45, 55, 58), (bar_margin, bar_y, bar_full_width, bar_height), border_radius=2)
    pygame.draw.rect(toast, (125, 200, 255), (bar_margin, bar_y, int(bar_full_width * remaining_fraction), bar_height), border_radius=2)

    window.blit(toast, (toast_x if slide_progress < 1 else target_x, target_y))