import pygame
import threading
import core.api as api
import sys
import core.state as state
import core.actions as actions
import core.attention as a
import core.weather as w
import ui.status_bar as status_bar
import ui.panel as panel
import ui.blurb as blurb
import ui.robo as robo
import ui.roboeyes as r
import ui.toast as toast

def advance_toast_queue(toast_state, mood_state, robo_eyes, attention, base_mood, mood_change):
    """Fires once the happy-period timer elapses after a completion: dismiss
    the current toast, pop the next pending reminder if any, and update
    mood/energy/attention accordingly. Pure state mutation, no drawing."""
    if not (toast_state.active_reminder and toast_state.toast_completed
            and pygame.time.get_ticks() >= toast_state.happy_until):
        return

    mood_state.set(base_mood, sound=mood_change)
    toast_state.active_reminder = toast_state.pending_reminders.pop(0) if toast_state.pending_reminders else None
    if toast_state.active_reminder:
        toast_state.toast_started = pygame.time.get_ticks()
        toast_state.toast_completed = False
        robo_eyes.startDraining()
        attention.focus("bottom-right")
    else:
        robo_eyes.stopDraining()
        robo_eyes.gainEnergy()
        if not toast_state.flash_toast:
            attention.release()


def expire_flash_toast(toast_state, attention):
    """Fires once the flash toast's display duration elapses."""
    if not toast_state.flash_toast:
        return
    elapsed = pygame.time.get_ticks() - toast_state.flash_started
    if elapsed >= toast.FLASH_TOAST_DURATION_MS:
        toast_state.flash_toast = None
        if not toast_state.active_reminder:
            attention.release()



# Example usage within a Pygame application
def main():
    pygame.init()

    pygame.mixer.init()  # Initialize the mixer module for sound playback
    # ui sounds
    new_toast = pygame.mixer.Sound("sounds/new_toast.mp3") # for new reminder created event
    toast_due = pygame.mixer.Sound("sounds/reminder_due.mp3") # for reminder due event
    completed_toast = pygame.mixer.Sound("sounds/completed.mp3")
    ui_open = pygame.mixer.Sound("sounds/ui_open.mp3")
    ui_open.set_volume(0.15)
    ui_close = pygame.mixer.Sound("sounds/ui_close.mp3")
    ui_close.set_volume(0.15)
    blurb_tick = pygame.mixer.Sound("sounds/keyboard_7.wav")
    blurb_tick.set_volume(0.12)

    # robo sounds
    mood_change = pygame.mixer.Sound("sounds/focus_7.wav")
    mood_change.set_volume(0.5)
    movement = pygame.mixer.Sound("sounds/focus_12.wav")
    movement.set_volume(0.15)
    blink = pygame.mixer.Sound("sounds/shutter_dial.wav")
    blink.set_volume(0.15)
    wobble = pygame.mixer.Sound("sounds/metal_wobble_25.wav")
    wobble.set_volume(0.25)

    

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
    robo_eyes.setWidth(220,220)
    robo_eyes.setHeight(300,300)
    robo_eyes.setSpacebetween(40)
    robo_eyes.setBorderradius(40, 40)
    robo_eyes.setBottomPadding(140)  # Set bottom padding for toast notifications
    robo_eyes.on_move = lambda x, y: movement.play()
    robo_eyes.on_blink = lambda: blink.play()
    mood_state = state.MoodState(robo_eyes=robo_eyes, initial=base_mood)

    attention = a.AttentionController(robo_eyes)

    clock = pygame.time.Clock()
    store = state.ReminderStore()
    api_server = api.run_api(store, mood_state)
    stop_scheduler = threading.Event()
    threading.Thread(
        target=actions.run_reminder_scheduler,
        args=(store, stop_scheduler),
        daemon=True,
    ).start()

    # handle weather & time information
    LAT, LON = 39.7684, -86.1581
    weather_state = state.WeatherState()
    stop_weather = threading.Event()
    threading.Thread(
        target=w.run_weather_poller,
        args=(weather_state, LAT, LON, stop_weather),
        daemon=True,
    ).start()
    time_font = pygame.font.Font(None, 28)
    temp_font = pygame.font.Font(None, 24)

    # handle state information
    toast_state = state.ToastState()
    toast_font = pygame.font.Font(None, 30)
    toast_small_font = pygame.font.Font(None, 22)

    #pending_reminders = []  # queue to hold pending reminders when a toast is already active
    panel_state = state.PanelState()
    panel_title_font = pygame.font.Font(None, 26)
    panel_meta_font = pygame.font.Font(None, 20)

    blurb_state = state.BlurbState()
    blurb_font = pygame.font.Font(None, 22)

    # main game loop
    while True:
        '''
        Event Handling — discrete triggers (pygame events, user input)
        '''
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_scheduler.set()
                stop_weather.set()
                api_server.shutdown()
                pygame.quit()
                sys.exit()

            if event.type == api.REMINDER_DUE:
                if toast_state.active_reminder is None:
                    toast_state.active_reminder = event.reminder
                    toast_state.toast_started = pygame.time.get_ticks()
                    toast_state.toast_completed = False
                    toast_due.play()
                    robo_eyes.startDraining()
                    attention.focus("bottom-right")
                else:
                    toast_state.pending_reminders.append(event.reminder)

            # handle reminder created event
            if event.type == api.REMINDER_CREATED:
                new_toast.play()
                toast_state.flash_toast = event.reminder
                toast_state.flash_started = pygame.time.get_ticks()
                attention.focus("bottom-left") 
                panel_state.reminders = store.list()

            # handle reminder completed event from api
            if event.type == api.REMINDER_COMPLETED and toast_state.active_reminder and event.reminder_id == toast_state.active_reminder["id"]:
                toast_state.toast_completed = True
                completed_toast.play()
                toast_state.happy_until = pygame.time.get_ticks() + 2500
                mood_state.set("happy", sound=mood_change)
                panel_state.reminders = store.list() # refresh the panel reminders list
                robo_eyes.gainEnergy() # refill energy on completion of a reminder

            if event.type == r.ROBO_TIER_DROPPED:
                looking_right = attention.target_fraction and attention.target_fraction[0] >= 0.5
                corner = "top-left" if looking_right else "top-right"
                blurb.start_blurb(blurb_state, corner=corner)

            # handle UI click
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # handle panel tab click
                if not panel_state.open and panel.get_tab_rect(screen_width, screen_height).collidepoint(event.pos):
                    panel_state.open = not panel_state.open
                    panel_state.toggle_started = pygame.time.get_ticks()
                    ui_open.play()
                    attention.focus("center-left")
                    if panel_state.open:
                        panel_state.reminders = store.list()
                # handle click outside the panel to close it
                elif panel_state.open:
                    if not panel.get_panel_rect(screen_width, screen_height, panel_state.open, panel_state.toggle_started).collidepoint(event.pos):
                        panel_state.open = False
                        ui_close.play()
                        attention.release()
                        panel_state.toggle_started = pygame.time.get_ticks()
                # handle click on robo eyes to trigger wobble animation
                elif robo_eyes.get_eyes_rect().collidepoint(event.pos):
                    robo_eyes.anim_wobble()
                    wobble.play()

            # handle mouse click on the checkmark button in the reminder toast
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and toast_state.active_reminder and not toast_state.toast_completed:
                checkmark_rect = toast.get_checkmark_rect(screen_width, screen_height)
                if checkmark_rect.collidepoint(event.pos):
                    # post an REMINDER_COMPLETED event to handle the completion of the active reminder
                    actions.complete_reminder(store, toast_state.active_reminder["id"])

            # handle mood change event
            if event.type == api.MOOD_CHANGED:
                base_mood = event.mood
                # this allows for the API to change the default idle mood (no active reminder is present)
                if toast_state.active_reminder is None:
                    mood_state.set(base_mood, sound=mood_change)

        '''
        State Transitions — timer-driven mutations (not tied to a discrete
        pygame event, but not drawing either; runs once per frame)
        '''
        advance_toast_queue(toast_state, mood_state, robo_eyes, attention, base_mood, mood_change)
        expire_flash_toast(toast_state, attention)

        '''
        Update & Draw — no state mutation below this point, only system
        ticks (robo_eyes/attention) and rendering
        '''
        robo_eyes.update()
        attention.update()

        window.fill(r.BGCOLOR)
        window.blit(draw_surface, (draw_surface.get_rect(center=window.get_rect().center)))
        status_bar.draw_status_bar(window, weather_state.get(), screen_width, screen_height, time_font, temp_font)

        if toast_state.active_reminder:
            toast.draw_persistent_toast(
                window,
                toast_state.active_reminder["title"],
                toast_state.toast_started,
                toast_state.toast_completed,
                screen_width,
                screen_height,
                toast_font,
                toast_small_font,
            )

        if toast_state.flash_toast:
            toast.draw_flash_toast(
                window,
                toast_state.flash_toast["title"],
                "New Reminder Scheduled",
                toast_state.flash_started,
                toast.FLASH_TOAST_DURATION_MS,
                screen_width,
                screen_height,
                toast_font,
                toast_small_font,
            )

        panel.draw_reminder_panel(
            window, panel_state.reminders, screen_width, screen_height,
            panel_state.open, panel_state.toggle_started, panel_title_font, panel_meta_font,
        )
        panel.draw_panel_tab(window, screen_width, screen_height, panel_state.open)

        robo.draw_energy_bar(window, robo_eyes)

        blurb.update_blurb(blurb_state, char_sound=blurb_tick)
        blurb.draw_blurb(window, blurb_state, robo_eyes, screen_width, screen_height, blurb_font)

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
