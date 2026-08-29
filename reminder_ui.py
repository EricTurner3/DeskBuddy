import pygame

import roboeyes as r


def mark_reminder_complete(store, reminder_id, robo_eyes):
    store.complete(reminder_id)
    robo_eyes.setMood(r.HAPPY)
    return {
        "toast_completed": True,
        "happy_until": pygame.time.get_ticks() + 2500,
    }


def draw_reminder_toast(window, reminder, started, completed, screen_width, screen_height, toast_font=pygame.font.Font(None, 30), toast_small_font=pygame.font.Font(None, 22)):
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
