import pygame
import threading
import roboeyes as r
import api
import reminder_ui
import sys
import state
import attention as a


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

    base_mood = "default"   # the mood to return to when no reminder is active
    

    # Create RoboEyes instance
    robo_eyes = r.RoboEyes(draw_surface, width=draw_width, height=draw_height, frame_rate=60)
    robo_eyes.begin()
    robo_eyes.setAutoblinker(True, interval=6, variation=7)
    robo_eyes.setIdleMode(True, interval=5, variation=5)
    robo_eyes.setCuriosity(True)
    robo_eyes.setWidth(250,250)
    robo_eyes.setHeight(300,300)
    robo_eyes.setSpacebetween(40)
    robo_eyes.setBorderradius(40, 40)
    robo_eyes.setBottomPadding(140)  # Set bottom padding for toast notifications
    mood_state = state.MoodState(robo_eyes=robo_eyes, initial=base_mood)

    attention = a.AttentionController(robo_eyes)

    clock = pygame.time.Clock()
    store = state.ReminderStore()
    api_server = api.run_reminder_api(store, mood_state)
    stop_scheduler = threading.Event()
    threading.Thread(
        target=api.run_reminder_scheduler,
        args=(store, stop_scheduler),
        daemon=True,
    ).start()

    # handle state information
    toast_state = state.ToastState()
    toast_font = pygame.font.Font(None, 30)
    toast_small_font = pygame.font.Font(None, 22)

    #pending_reminders = []  # queue to hold pending reminders when a toast is already active
    

    # main game loop
    while True:
        '''
        Events Handling
        '''
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_scheduler.set()
                api_server.shutdown()
                pygame.quit()
                sys.exit()

            if event.type == api.REMINDER_DUE:
                if toast_state.active_reminder is None:
                    toast_state.active_reminder = event.reminder
                    toast_state.toast_started = pygame.time.get_ticks()
                    toast_state.toast_completed = False
                    mood_state.set("angry")
                    attention.focus("bottom-right")
                else:
                    toast_state.pending_reminders.append(event.reminder)

            # handle reminder created event
            if event.type == api.REMINDER_CREATED:
                toast_state.flash_toast = event.reminder
                toast_state.flash_started = pygame.time.get_ticks()
                attention.focus("bottom-left") 

            # handle reminder completed event
            if event.type == api.REMINDER_COMPLETED and toast_state.active_reminder and event.reminder_id == toast_state.active_reminder["id"]:
                toast_state.toast_completed = True
                toast_state.happy_until = pygame.time.get_ticks() + 2500
                mood_state.set("happy")

            # handle mouse click on the checkmark button in the reminder toast
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and toast_state.active_reminder and not toast_state.toast_completed:
                checkmark_rect = reminder_ui.get_checkmark_rect(screen_width, screen_height)
                if checkmark_rect.collidepoint(event.pos):
                    result = reminder_ui.mark_reminder_complete(store, toast_state.active_reminder["id"], robo_eyes)
                    toast_state.toast_completed = result["toast_completed"]
                    toast_state.happy_until = result["happy_until"]

            # handle mood change event
            if event.type == api.MOOD_CHANGED:
                base_mood = event.mood
                # this allows for the API to change the default idle mood (no active reminder is present)
                if toast_state.active_reminder is None:
                    mood_state.set(base_mood)

        '''
        Draw UI
        '''
        # Update RoboEyes
        robo_eyes.update()
        # Update AttentionController
        attention.update()

        # Clear the window before blitting
        window.fill(r.BGCOLOR)

        # Blit the draw surface onto the main window
        window.blit(draw_surface, (draw_surface.get_rect(center=window.get_rect().center)))

        # Draw active reminder toast if any
        if toast_state.active_reminder:
            reminder_ui.draw_reminder_toast(
                window,
                toast_state.active_reminder["title"],
                toast_state.toast_started,
                toast_state.toast_completed,
                screen_width,
                screen_height,
                toast_font,
                toast_small_font,
            )
            if toast_state.toast_completed and pygame.time.get_ticks() >= toast_state.happy_until:
                mood_state.set(base_mood)
                # this is what removes the active toast and moves on to the next reminder if there is one
                toast_state.active_reminder = toast_state.pending_reminders.pop(0) if toast_state.pending_reminders else None
                if toast_state.active_reminder:
                    toast_state.toast_started = pygame.time.get_ticks()
                    toast_state.toast_completed = False
                    attention.focus("bottom-right")
                elif not toast_state.flash_toast:
                    attention.release()

        # Draw flash toast if active
        if toast_state.flash_toast:
            elapsed = pygame.time.get_ticks() - toast_state.flash_started
            if elapsed >= reminder_ui.FLASH_TOAST_DURATION_MS:
                toast_state.flash_toast = None
                if not toast_state.active_reminder:
                    attention.release()
            else:
                reminder_ui.draw_flash_toast(
                    window,
                    toast_state.flash_toast["title"],
                    "New Reminder Scheduled",
                    toast_state.flash_started,
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
