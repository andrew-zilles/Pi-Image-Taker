from __future__ import annotations

import subprocess
import threading
from typing import Callable, Optional

# baresip's log wording has drifted a bit between releases. Run
# `baresip -f <config_dir> -v -e "/dial sip:..."` by hand once and check what your
# installed version actually prints for "answered" and "call ended" -- adjust these
# substrings to match if your calls aren't being detected.
ANSWERED_MARKERS = ("call answered", "session progress: 200", "call established")
ENDED_MARKERS = ("call closed", "session closed", "ua: call closed")


class SipClient:
    """Places one outbound call at a time via a per-call baresip subprocess.

    baresip must already be set up with a working SIP trunk account (see
    scripts/baresip_accounts.example) capable of terminating calls to real phone
    numbers, and configured to use pulseaudio (module aupulse) so our audio routing
    scripts can get at its playback/capture streams.
    """

    def __init__(self, baresip_config_dir: str, destination_uri_template: str):
        self._config_dir = baresip_config_dir
        self._uri_template = destination_uri_template
        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._local_hangup = False

    def place_call(
        self,
        number: str,
        on_answered: Callable[[], None],
        on_ended: Callable[[], None],
    ) -> None:
        if self._proc is not None:
            raise RuntimeError("a call is already in progress")

        self._local_hangup = False
        uri = self._uri_template.format(number=number)
        self._proc = subprocess.Popen(
            ["baresip", "-f", self._config_dir, "-e", f"/dial {uri}"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def _read_output():
            answered = False
            for line in self._proc.stdout:
                lowered = line.lower()
                if not answered and any(m in lowered for m in ANSWERED_MARKERS):
                    answered = True
                    on_answered()
                if any(m in lowered for m in ENDED_MARKERS):
                    break
            self._proc = None
            if not self._local_hangup:
                on_ended()

        self._reader_thread = threading.Thread(target=_read_output, daemon=True)
        self._reader_thread.start()

    def hangup(self) -> None:
        if self._proc is None:
            return
        self._local_hangup = True
        proc = self._proc
        try:
            proc.stdin.write("/hangup\n")
            proc.stdin.flush()
            proc.stdin.write("/quit\n")
            proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        self._proc = None

    @property
    def in_call(self) -> bool:
        return self._proc is not None
