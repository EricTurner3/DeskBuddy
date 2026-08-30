import pygame

'''
Robo UI
This module is for additional UI elements that extend beyond the basic roboeyes, such as the energy bar.
'''

def draw_energy_bar(window, robo_eyes, x=24, y=24, segment_w=18, segment_h=10, gap=4):
    tiers = robo_eyes.energy_tiers
    filled_tier = robo_eyes.getEnergyTier()
    for i in range(tiers):
        rect = pygame.Rect(x + i * (segment_w + gap), y, segment_w, segment_h)
        t = i / max(1, tiers - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip((70, 214, 137), (214, 70, 70)))
        if i < filled_tier:
            pygame.draw.rect(window, color, rect, border_radius=3)
        else:
            pygame.draw.rect(window, (40, 44, 46), rect, border_radius=3)
            pygame.draw.rect(window, (70, 74, 76), rect, width=1, border_radius=3)
