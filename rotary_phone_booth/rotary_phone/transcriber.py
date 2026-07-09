from __future__ import annotations

import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import webrtcvad
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_BYTES = int(SAMPLE_RATE * FRAME_MS / 1000) * 2  # 16-bit mono
SILENCE_FLUSH_SECONDS = 0.6


class Transcriber:
    """Live-ish transcription: VAD-segments the call audio into utterances and runs
    faster-whisper on each one as soon as a pause is detected (or a max chunk length
    is hit), rather than waiting for the whole call. Expect a few seconds of lag per
    utterance, not sub-second latency -- that's the tradeoff for running free/local on
    Pi-class hardware instead of a paid cloud streaming ASR API.
    """

    def __init__(self, monitor_source: str, model_size: str, device: str, chunk_seconds: float):
        self._monitor_source = monitor_source
        self._model = WhisperModel(model_size, device=device, compute_type="int8" if device == "cpu" else "float16")
        self._vad = webrtcvad.Vad(2)
        self._max_bytes = int(chunk_seconds * SAMPLE_RATE * 2)
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._transcript_path: Optional[Path] = None

    def start(self, output_dir: str) -> Path:
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._transcript_path = output_dir_path / f"transcript_{timestamp}.txt"

        self._proc = subprocess.Popen(
            ["parec", "-d", self._monitor_source, "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1"],
            stdout=subprocess.PIPE,
        )
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self._transcript_path

    def _run(self) -> None:
        speech_buffer = bytearray()
        silence_frames = 0
        with open(self._transcript_path, "w") as f:
            while not self._stop_event.is_set():
                frame = self._proc.stdout.read(FRAME_BYTES)
                if len(frame) < FRAME_BYTES:
                    if self._proc.poll() is not None:
                        break
                    continue

                if self._vad.is_speech(frame, SAMPLE_RATE):
                    speech_buffer.extend(frame)
                    silence_frames = 0
                elif speech_buffer:
                    speech_buffer.extend(frame)  # keep trailing silence for natural cadence
                    silence_frames += 1

                silence_seconds = silence_frames * FRAME_MS / 1000
                if speech_buffer and (silence_seconds >= SILENCE_FLUSH_SECONDS or len(speech_buffer) >= self._max_bytes):
                    self._transcribe_and_write(bytes(speech_buffer), f)
                    speech_buffer = bytearray()
                    silence_frames = 0

            if speech_buffer:
                self._transcribe_and_write(bytes(speech_buffer), f)

    def _transcribe_and_write(self, pcm_bytes: bytes, f) -> None:
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(audio, language="en")
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if not text:
            return
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n"
        f.write(line)
        f.flush()
        print(line, end="")

    def stop(self) -> Optional[Path]:
        self._stop_event.set()
        if self._proc is not None:
            self._proc.terminate()
        if self._thread is not None:
            self._thread.join(timeout=10)
        self._proc = None
        return self._transcript_path
