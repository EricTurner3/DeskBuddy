import pygame
import threading
import roboeyes as r
import api
import reminder_ui
import sys

MOOD_MAP = {
    "default": r.DEFAULT,
    "tired": r.TIRED,
    "angry": r.ANGRY,
    "happy": r.HAPPY,
}

# Example usage within a Pygame application
def main():
    pygame.init()

    # Screen settings
    screen_width = 1024   # Rotated width
    screen_height = 600  # Rotated height
    window = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("DeskBuddy")

    # Create a separate surface for drawing (unrotated)
    draw_width = 1024
    draw_height = 600
    draw_surface = pygame.Surface((draw_width, draw_height))
    draw_surface.fill(r.BGCOLOR)  # Ensure it's cleared initially

    base_mood = r.DEFAULT   # the mood to return to when no reminder is active

    # Create RoboEyes instance
    robo_eyes = r.RoboEyes(draw_surface, width=draw_width, height=draw_height, frame_rate=60)
    robo_eyes.begin()
    robo_eyes.setMood(base_mood)
    robo_eyes.setAutoblinker(True, interval=6, variation=7)
    robo_eyes.setIdleMode(True, interval=5, variation=5)
    robo_eyes.setCuriosity(True)
    robo_eyes.setWidth(250,250)
    robo_eyes.setHeight(300,300)
    robo_eyes.setSpacebetween(40)
    robo_eyes.setBorderradius(40, 40)
    robo_eyes.setBottomPadding(140)  # Set bottom padding for toast notifications

    clock = pygame.time.Clock()
    store = api.ReminderStore()
    api_server = api.run_reminder_api(store)
    stop_scheduler = threading.Event()
    threading.Thread(
        target=api.run_reminder_scheduler,
        args=(store, stop_scheduler),
        daemon=True,
    ).start()

    # handle state information
    toast_font = pygame.font.Font(None, 30)
    toast_small_font = pygame.font.Font(None, 22)
    active_reminder = None
    pending_reminders = []
    toast_started = 0
    toast_completed = False
    happy_until = 0
    flash_toast = None
    flash_started = 0

    # main game loop
    while True:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_scheduler.set()
                api_server.shutdown()
                pygame.quit()
                sys.exit()

            if event.type == api.REMINDER_DUE:
                if active_reminder is None:
                    active_reminder = event.reminder
                    toast_started = pygame.time.get_ticks()
                    toast_completed = False
                    robo_eyes.setMood(r.ANGRY)
                else:
                    pending_reminders.append(event.reminder)

            # handle reminder created event
            if event.type == api.REMINDER_CREATED:
                flash_toast = event.reminder
                flash_started = pygame.time.get_ticks()

            # handle reminder completed event
            if event.type == api.REMINDER_COMPLETED and active_reminder and event.reminder_id == active_reminder["id"]:
                toast_completed = True
                happy_until = pygame.time.get_ticks() + 2500
                robo_eyes.setMood(r.HAPPY)

            # handle mouse click on the checkmark button in the reminder toast
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and active_reminder and not toast_completed:
                checkmark_rect = reminder_ui.draw_reminder_toast(
                    window,
                    active_reminder,
                    toast_started,
                    toast_completed,
                    screen_width,
                    screen_height,
                    toast_font,
                    toast_small_font,
                )
                if checkmark_rect.collidepoint(event.pos):
                    result = reminder_ui.mark_reminder_complete(store, active_reminder["id"], robo_eyes)
                    toast_completed = result["toast_completed"]
                    happy_until = result["happy_until"]

            # handle mood change event
            if event.type == api.MOOD_CHANGED:
                base_mood = MOOD_MAP[event.mood]
                if active_reminder is None:
                    robo_eyes.setMood(base_mood)

        # Update RoboEyes
        robo_eyes.update()

        # Clear the window before blitting
        window.fill(r.BGCOLOR)

        # Blit the rotated surface onto the main window
        window.blit(draw_surface, (draw_surface.get_rect(center=window.get_rect().center)))

        if active_reminder:
            reminder_ui.draw_reminder_toast(
                window,
                active_reminder["title"],
                toast_started,
                toast_completed,
                screen_width,
                screen_height,
                toast_font,
                toast_small_font,
            )
            if toast_completed and pygame.time.get_ticks() >= happy_until:
                robo_eyes.setMood(base_mood)
                active_reminder = pending_reminders.pop(0) if pending_reminders else None
                if active_reminder:
                    toast_started = pygame.time.get_ticks()
                    toast_completed = False

        # Draw flash toast if active
        if flash_toast:
            elapsed = pygame.time.get_ticks() - flash_started
            if elapsed >= reminder_ui.FLASH_TOAST_DURATION_MS:
                flash_toast = None
            else:
                reminder_ui.draw_flash_toast(
                    window,
                    flash_toast["title"],
                    "New Reminder Scheduled",
                    flash_started,
                    reminder_ui.FLASH_TOAST_DURATION_MS,
                    screen_width,
                    screen_height,
                    toast_font,
                    toast_small_font,
                )

        # Update the display
        pygame.display.flip()

        # Limit to 60 FPS
        clock.tick(60)

if __name__ == "__main__":
    main()
