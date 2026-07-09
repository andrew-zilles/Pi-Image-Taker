from __future__ import annotations

import logging
import threading
from enum import Enum, auto
from threading import Timer
from typing import Optional

from .audio_routing import AudioRouting
from .config import Config
from .hookswitch import HookSwitch
from .mailer import send_call_recording
from .recorder import Recorder
from .rotary_dial import RotaryDial
from .sip_client import SipClient
from .transcriber import Transcriber

log = logging.getLogger("rotary_phone")


class State(Enum):
    IDLE = auto()        # on-hook, nothing happening
    DIALING = auto()     # off-hook, collecting digits
    CALLING = auto()     # number complete, waiting for the far end to answer
    IN_CALL = auto()     # answered: recording + transcribing
    POST_CALL = auto()   # far end hung up but caller hasn't put the handset down yet


class PhoneController:
    def __init__(self, config: Config):
        self._config = config
        self._lock = threading.RLock()
        self._state = State.IDLE
        self._digits: list[str] = []
        self._abandon_timer: Optional[Timer] = None

        self._sip = SipClient(
            config["sip"]["baresip_config_dir"],
            config["sip"]["destination_uri_template"],
        )
        self._audio_routing = AudioRouting(
            config["audio"]["mic_source"],
            config["audio"]["speaker_sink"],
            config["audio"]["call_record_sink"],
        )
        self._recorder = Recorder(config["recording"]["output_dir"], self._audio_routing.monitor_source)
        self._transcriber = Transcriber(
            self._audio_routing.monitor_source,
            config["transcription"]["model_size"],
            config["transcription"]["device"],
            config["transcription"]["chunk_seconds"],
        )

        self._current_number: Optional[str] = None
        self._recording_path = None
        self._transcript_path = None

        self._hookswitch = HookSwitch(
            config["gpio"]["hookswitch_pin"], self._on_off_hook, self._on_on_hook
        )
        self._dial = RotaryDial(
            config["gpio"]["dial_pulse_pin"],
            self._on_digit,
            config["gpio"].get("dial_offnormal_pin"),
        )

    # -- hookswitch / dial callbacks (run on gpiozero's own threads) -----------------

    def _on_off_hook(self) -> None:
        with self._lock:
            if self._state != State.IDLE:
                return
            log.info("off-hook: waiting for digits")
            self._digits = []
            self._state = State.DIALING
            self._reset_abandon_timer()

    def _on_digit(self, digit: int) -> None:
        with self._lock:
            if self._state != State.DIALING:
                return
            self._digits.append(str(digit))
            log.info("dialed digit %s (%s so far)", digit, "".join(self._digits))
            self._reset_abandon_timer()
            expected_length = self._config["dialing"]["expected_number_length"]
            if len(self._digits) >= expected_length:
                self._place_call()

    def _on_on_hook(self) -> None:
        with self._lock:
            if self._abandon_timer is not None:
                self._abandon_timer.cancel()
                self._abandon_timer = None
            if self._state in (State.IDLE,):
                return
            log.info("on-hook: tearing down (was %s)", self._state)
            self._teardown_call()
            self._state = State.IDLE

    # -- call lifecycle ---------------------------------------------------------------

    def _reset_abandon_timer(self) -> None:
        if self._abandon_timer is not None:
            self._abandon_timer.cancel()
        timeout = self._config["dialing"]["abandon_timeout_seconds"]
        self._abandon_timer = Timer(timeout, self._on_dial_abandoned)
        self._abandon_timer.daemon = True
        self._abandon_timer.start()

    def _on_dial_abandoned(self) -> None:
        with self._lock:
            if self._state == State.DIALING:
                log.info("dial abandoned (no digits / incomplete number in time)")
                self._state = State.IDLE
                self._digits = []

    def _place_call(self) -> None:
        self._current_number = "".join(self._digits)
        self._state = State.CALLING
        log.info("placing call to %s", self._current_number)
        self._sip.place_call(self._current_number, self._on_call_answered, self._on_call_ended)

    def _on_call_answered(self) -> None:
        with self._lock:
            if self._state != State.CALLING:
                return
            log.info("call answered, starting recording + transcription")
            self._state = State.IN_CALL
            self._audio_routing.setup()
            self._recording_path = self._recorder.start()
            self._transcript_path = self._transcriber.start(self._config["recording"]["output_dir"])

    def _on_call_ended(self) -> None:
        """Far end hung up (or the call failed) while our caller is still off-hook."""
        with self._lock:
            if self._state not in (State.CALLING, State.IN_CALL):
                return
            log.info("far end ended the call")
            self._finish_call_artifacts()
            self._state = State.POST_CALL

    def _teardown_call(self) -> None:
        if self._state in (State.CALLING, State.IN_CALL):
            self._sip.hangup()
            self._finish_call_artifacts()
        self._digits = []
        self._current_number = None

    def _finish_call_artifacts(self) -> None:
        if self._state == State.IN_CALL:
            self._recording_path = self._recorder.stop()
            self._transcript_path = self._transcriber.stop()
            self._audio_routing.teardown()
            self._send_email()
        self._recording_path = None
        self._transcript_path = None

    def _send_email(self) -> None:
        try:
            send_call_recording(
                smtp_host=self._config["email"]["smtp_host"],
                smtp_port=self._config["email"]["smtp_port"],
                smtp_user=self._config["email"]["smtp_user"],
                smtp_password=self._config.smtp_app_password,
                recipient=self._config["email"]["recipient"],
                number_dialed=self._current_number or "unknown",
                recording_path=self._recording_path,
                transcript_path=self._transcript_path,
            )
            log.info("emailed recording + transcript to %s", self._config["email"]["recipient"])
        except Exception:
            log.exception("failed to send call recording email")

    def close(self) -> None:
        self._hookswitch.close()
        self._dial.close()
