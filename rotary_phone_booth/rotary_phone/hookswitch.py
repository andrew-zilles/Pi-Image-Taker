from __future__ import annotations

from typing import Callable

from gpiozero import Button


class HookSwitch:
    """Wraps the phone's switchhook contact.

    Wire the switchhook through an opto-isolator (e.g. PC817) into the GPIO pin so the
    Pi is never directly connected to anything the handset weight or spring mechanism
    switches. Configure the isolator so the GPIO reads LOW when the handset is lifted
    (off-hook) -- gpiozero's Button defaults (pull_up=True, active when pulled low) match that.
    """

    def __init__(self, pin: int, on_off_hook: Callable[[], None], on_on_hook: Callable[[], None]):
        self._button = Button(pin, pull_up=True, bounce_time=0.05)
        self._button.when_pressed = on_off_hook   # contact closes -> handset lifted
        self._button.when_released = on_on_hook   # contact opens -> handset replaced

    @property
    def is_off_hook(self) -> bool:
        return self._button.is_pressed

    def close(self) -> None:
        self._button.close()
