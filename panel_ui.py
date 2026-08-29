import pygame
import helper

PANEL_WIDTH = 340
TAB_WIDTH = 28
TAB_HEIGHT = 90
ROW_HEIGHT = 64
ANIMATION_MS = 280
MAX_VISIBLE_ROWS = 7


def get_tab_rect(screen_width, screen_height):
    return pygame.Rect(screen_width - TAB_WIDTH, (screen_height - TAB_HEIGHT) // 2, TAB_WIDTH, TAB_HEIGHT)


def get_panel_rect(screen_width, screen_height, is_open, toggle_started):
    elapsed = pygame.time.get_ticks() - toggle_started
    progress = min(1.0, elapsed / ANIMATION_MS)
    start_x = screen_width if is_open else screen_width - PANEL_WIDTH
    end_x = screen_width - PANEL_WIDTH if is_open else screen_width
    x = int(start_x + (end_x - start_x) * progress)
    return pygame.Rect(x, 0, PANEL_WIDTH, screen_height)


def draw_reminder_panel(window, reminders, screen_width, screen_height, is_open, toggle_started, title_font, meta_font):
    panel_rect = get_panel_rect(screen_width, screen_height, is_open, toggle_started)
    if panel_rect.x >= screen_width:
        return  # fully closed, nothing to draw

    panel = pygame.Surface((PANEL_WIDTH, screen_height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (14, 18, 21, 235), panel.get_rect())
    panel.blit(title_font.render("Upcoming Reminders", True, (245, 250, 248)), (20, 20))
    pygame.draw.line(panel, (45, 55, 58), (20, 56), (PANEL_WIDTH - 20, 56), 1)

    if not reminders:
        panel.blit(meta_font.render("Nothing scheduled", True, (140, 150, 155)), (20, 76))
    else:
        y = 70
        for reminder in reminders[:MAX_VISIBLE_ROWS]:
            panel.blit(title_font.render(reminder["title"], True, (235, 240, 238)), (20, y))
            meta_text = helper.format_relative_due(reminder["due_at"])
            recurring = bool(reminder.get("recurrence_seconds"))
            if recurring:
                meta_text += "  •  recurring"
            color = (150, 200, 235) if recurring else (170, 185, 190)
            panel.blit(meta_font.render(meta_text, True, color), (20, y + 26))
            y += ROW_HEIGHT
        if len(reminders) > MAX_VISIBLE_ROWS:
            panel.blit(meta_font.render(f"+{len(reminders) - MAX_VISIBLE_ROWS} more", True, (140, 150, 155)), (20, y))

    window.blit(panel, (panel_rect.x, 0))


def draw_panel_tab(window, screen_width, screen_height, is_open):
    tab_rect = get_tab_rect(screen_width, screen_height)
    tab = pygame.Surface((TAB_WIDTH, TAB_HEIGHT), pygame.SRCALPHA)
    color = (57, 190, 116) if is_open else (38, 62, 58)
    pygame.draw.rect(tab, color, tab.get_rect(), border_top_left_radius=10, border_bottom_left_radius=10)
    for i in range(3):
        y = 30 + i * 14
        pygame.draw.line(tab, (230, 235, 232), (8, y), (TAB_WIDTH - 8, y), 3)
    window.blit(tab, (tab_rect.x, tab_rect.y))