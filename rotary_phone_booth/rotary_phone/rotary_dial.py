from __future__ import annotations

from threading import Timer
from typing import Callable, Optional

from gpiozero import Button


class RotaryDial:
    """Decodes a Western Electric rotary dial into digits.

    The dial has "pulse" (impulse) contacts that are normally closed and open once per
    pulse as the dial spins back to rest -- the pulse count is the digit, except that
    0 is sent as 10 pulses. Some dials also have "off-normal" contacts that close as
    soon as the dial is pulled away from rest and stay closed until it returns; wiring
    that pin lets us detect "digit finished" the instant the dial settles rather than
    guessing from a timeout, which is more reliable at low pulse rates.

    Both pins should be wired through opto-isolators, same rationale as HookSwitch.
    """

    PULSE_DEBOUNCE = 0.02      # WE dial contacts bounce for a few ms per make/break
    NO_OFFNORMAL_DIGIT_TIMEOUT = 0.35  # fallback digit boundary when off-normal isn't wired

    def __init__(
        self,
        pulse_pin: int,
        on_digit: Callable[[int], None],
        offnormal_pin: Optional[int] = None,
    ):
        self._on_digit = on_digit
        self._pulse_count = 0
        self._digit_timer: Optional[Timer] = None

        self._pulse_button = Button(pulse_pin, pull_up=True, bounce_time=self.PULSE_DEBOUNCE)
        self._pulse_button.when_pressed = self._on_pulse

        self._offnormal_button: Optional[Button] = None
        if offnormal_pin is not None:
            self._offnormal_button = Button(offnormal_pin, pull_up=True, bounce_time=0.02)
            self._offnormal_button.when_released = self._on_dial_settled

    def _on_pulse(self) -> None:
        self._pulse_count += 1
        if self._offnormal_button is None:
            # No off-normal signal available: treat a gap in pulses as end-of-digit.
            if self._digit_timer is not None:
                self._digit_timer.cancel()
            self._digit_timer = Timer(self.NO_OFFNORMAL_DIGIT_TIMEOUT, self._on_dial_settled)
            self._digit_timer.daemon = True
            self._digit_timer.start()

    def _on_dial_settled(self) -> None:
        if self._pulse_count == 0:
            return
        digit = 0 if self._pulse_count == 10 else self._pulse_count
        self._pulse_count = 0
        self._on_digit(digit)

    def close(self) -> None:
        if self._digit_timer is not None:
            self._digit_timer.cancel()
        self._pulse_button.close()
        if self._offnormal_button is not None:
            self._offnormal_button.close()
