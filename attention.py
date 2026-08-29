# attention.py
from random import random

import pygame

# Maps a toast's on-screen corner to a fraction of the eyes' movement range.
# (0,0) = eyes fully toward top-left of their range, (1,1) = fully bottom-right.
LOCATION_FRACTIONS = {
    "top-left": (0.0, 0.0),
    "top-right": (1.0, 0.0),
    "bottom-left": (0.0, 1.0),
    "bottom-right": (1.0, 1.0),
}


class AttentionController:
    """Layers toast-aware 'look at' behavior on top of a RoboEyes instance.

    roboeyes.py stays generic and toast-agnostic; this module is the glue
    that knows a toast happened and translates that into eye movement.
    Call update() once per frame alongside robo_eyes.update().
    """

    BOUNCE_INTERVAL_MS = 900
    BOUNCE_INTERVAL_VARIATION_MS = 300

    def __init__(self, robo_eyes):
        self.robo_eyes = robo_eyes
        self.target_fraction = None   # (frac_x, frac_y) or None when not focused
        self.looking_at_target = False
        self.bounce_timer = 0
        self._idle_before_focus = False

    def focus(self, toast_location):
        """Start bouncing eye attention toward a toast location (e.g. 'bottom-right').

        Safe to call repeatedly while a toast is active/changes -- re-targets
        without re-suspending idle mode.
        """
        fraction = LOCATION_FRACTIONS[toast_location]
        if self.target_fraction is None:
            self._idle_before_focus = self.robo_eyes.idle
            self.robo_eyes.setIdleMode(False)
        self.target_fraction = fraction
        self.bounce_timer = pygame.time.get_ticks()
        self.looking_at_target = True
        self._apply()

    def release(self):
        """Stop focusing, recenter, and restore idle mode if it was on before."""
        if self.target_fraction is None:
            return
        self.target_fraction = None
        max_x = self.robo_eyes.getScreenConstraint_X()
        max_y = self.robo_eyes.getScreenConstraint_Y()
        self.robo_eyes.eyeLx_next = max_x // 2
        self.robo_eyes.eyeLy_next = max_y // 2
        if self._idle_before_focus:
            self.robo_eyes.setIdleMode(True)

    def update(self):
        """Call once per frame. No-op when not focused on anything."""
        if self.target_fraction is None:
            return
        now = pygame.time.get_ticks()
        if now - self.bounce_timer >= (self.BOUNCE_INTERVAL_MS + random.randint(0, self.BOUNCE_INTERVAL_VARIATION_MS)):
            self.looking_at_target = not self.looking_at_target
            self.bounce_timer = now
            self._apply()

    def _apply(self):
        max_x = self.robo_eyes.getScreenConstraint_X()
        max_y = self.robo_eyes.getScreenConstraint_Y()
        if self.looking_at_target:
            frac_x, frac_y = self.target_fraction
            self.robo_eyes.eyeLx_next = int(max_x * frac_x)
            self.robo_eyes.eyeLy_next = int(max_y * frac_y)
        else:
            self.robo_eyes.eyeLx_next = max_x // 2
            self.robo_eyes.eyeLy_next = max_y // 2