import pygame
from datetime import datetime
import platform

BAR_WIDTH = 280
BAR_HEIGHT = 64
ICON_SIZE = 40
BAR_MARGIN = 24


def _draw_icon(surface, condition, cx, cy):
    """Draw a small vector weather icon centered at (cx, cy)."""
    if condition == "clear":
        pygame.draw.circle(surface, (255, 205, 90), (cx, cy), 14)
    elif condition == "cloudy":
        pygame.draw.circle(surface, (180, 190, 195), (cx - 6, cy + 3), 11)
        pygame.draw.circle(surface, (180, 190, 195), (cx + 7, cy), 13)
    elif condition == "rain":
        pygame.draw.circle(surface, (180, 190, 195), (cx, cy - 4), 12)
        for dx in (-8, 0, 8):
            pygame.draw.line(surface, (110, 180, 235), (cx + dx, cy + 8), (cx + dx - 3, cy + 16), 3)
    elif condition == "snow":
        pygame.draw.circle(surface, (180, 190, 195), (cx, cy - 4), 12)
        for dx in (-8, 0, 8):
            pygame.draw.circle(surface, (235, 245, 250), (cx + dx, cy + 12), 2)
    elif condition == "storm":
        pygame.draw.circle(surface, (140, 150, 158), (cx, cy - 4), 12)
        pygame.draw.polygon(surface, (255, 210, 60),
                             [(cx - 2, cy + 4), (cx + 6, cy + 4), (cx - 1, cy + 18),
                              (cx + 8, cy + 8), (cx, cy + 8)])
    else:
        # unknown / not yet loaded
        pygame.draw.circle(surface, (90, 100, 105), (cx, cy), 4)


def draw_status_bar(window, weather, screen_width, screen_height, time_font, temp_font):
    bar = pygame.Surface((BAR_WIDTH, BAR_HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(bar, (18, 24, 28, 200), bar.get_rect(), border_radius=14)

    if platform.system() == "Windows":
        now_text = datetime.now().strftime("%#I:%M %p")
    else:
        now_text = datetime.now().strftime("%-I:%M %p")

    time_surface = time_font.render(now_text, True, (245, 250, 248))
    bar.blit(time_surface, (18, (BAR_HEIGHT - time_surface.get_height()) // 2))

    _draw_icon(bar, weather["condition"], BAR_WIDTH - 66, BAR_HEIGHT // 2)

    temp_text = f'{weather["temp_f"]}°F' if weather["temp_f"] is not None else "--"
    temp_surface = temp_font.render(temp_text, True, (174, 190, 194))
    bar.blit(temp_surface, (BAR_WIDTH - 40, (BAR_HEIGHT - temp_surface.get_height()) // 2))

    target_x = (screen_width - BAR_WIDTH) // 2
    target_y = (screen_height - BAR_HEIGHT - BAR_MARGIN)
    window.blit(bar, (target_x, target_y))