from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


class Recorder:
    def __init__(self, output_dir: str, monitor_source: str):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._monitor_source = monitor_source
        self._proc: Optional[subprocess.Popen] = None
        self._path: Optional[Path] = None

    def start(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = self._output_dir / f"call_{timestamp}.wav"
        self._proc = subprocess.Popen(
            ["parecord", "-d", self._monitor_source, "--file-format=wav", str(self._path)],
        )
        return self._path

    def stop(self) -> Optional[Path]:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        return self._path
