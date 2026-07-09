from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


class AudioRouting:
    def __init__(self, mic_source: str, speaker_sink: str, call_record_sink: str = "call_record"):
        self._mic_source = mic_source
        self._speaker_sink = speaker_sink
        self._call_record_sink = call_record_sink

    def setup(self) -> None:
        subprocess.run(
            [str(SCRIPTS_DIR / "setup_pulse_routing.sh"), self._mic_source, self._speaker_sink, self._call_record_sink],
            check=True,
        )

    def teardown(self) -> None:
        subprocess.run(
            [str(SCRIPTS_DIR / "teardown_pulse_routing.sh"), self._call_record_sink],
            check=False,
        )

    @property
    def monitor_source(self) -> str:
        return f"{self._call_record_sink}.monitor"
