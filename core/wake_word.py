"""
core/wake_word.py
=================
Continuous wake-word detection for MARS.

The detector combines energy-based voice activity detection (VAD) with
Whisper transcription.  The microphone is polled in short windows; when a
window contains enough energy the audio is transcribed and the transcript is
checked for the configured wake word (default ``"hey mars"``).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import numpy as np
import yaml

logger = logging.getLogger(__name__)

_SETTINGS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "settings.yaml"
)


def _load_settings() -> dict[str, Any]:
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}


class WakeWordDetector:
    """Listens continuously for the owner's wake word.

    Audio is captured in short rolling windows.  Each window is checked for
    energy; if sufficient energy is found the window is transcribed with
    Whisper and the transcript is searched for the wake word.

    Args:
        wake_word:        The phrase to listen for (case-insensitive).
        sample_rate:      PCM sample rate in Hz.
        chunk_size:       PyAudio read chunk size in frames.
        energy_threshold: RMS energy floor for a chunk to be considered
                          voice activity.
        window_seconds:   Duration (s) of audio to accumulate before each
                          transcription pass.
        whisper_model:    Whisper model name to use for transcription.

    Example::

        detector = WakeWordDetector()
        print("Waiting for wake word…")
        if detector.listen_for_wake_word():
            print("Wake word detected!")
    """

    def __init__(
        self,
        wake_word: str | None = None,
        sample_rate: int | None = None,
        chunk_size: int | None = None,
        energy_threshold: int | None = None,
        window_seconds: float = 2.0,
        whisper_model: str | None = None,
    ) -> None:
        settings = _load_settings()
        audio_cfg = settings.get("audio", {})
        mars_cfg = settings.get("mars", {})

        self.wake_word: str = (
            wake_word or mars_cfg.get("wake_word", "hey mars")
        ).lower().strip()
        self.sample_rate: int = sample_rate or audio_cfg.get("sample_rate", 16_000)
        self.chunk_size: int = chunk_size or audio_cfg.get("chunk_size", 1024)
        self.energy_threshold: int = energy_threshold or audio_cfg.get(
            "silence_threshold", 500
        )
        self.window_seconds: float = window_seconds
        self._whisper_model_name: str = whisper_model or mars_cfg.get(
            "whisper_model", "base"
        )

        self._whisper_model: Any | None = None
        self._pyaudio: Any | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def listen_for_wake_word(self, timeout: float | None = None) -> bool:
        """Block until the wake word is detected or *timeout* seconds elapse.

        The method streams audio from the microphone, accumulates chunks into
        short windows, and runs Whisper on each window that has sufficient
        energy.  It returns as soon as the wake phrase appears in any
        transcript.

        Args:
            timeout: Optional maximum number of seconds to wait.  ``None``
                     means wait indefinitely.

        Returns:
            ``True`` when the wake word is detected within the timeout,
            ``False`` if the timeout expires first.

        Raises:
            ImportError: If PyAudio or openai-whisper are not installed.
        """
        import pyaudio  # type: ignore[import]

        self._ensure_whisper()
        pa = self._get_pyaudio()

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        chunks_per_window = int(
            self.window_seconds * self.sample_rate / self.chunk_size
        )
        start_time = time.monotonic()

        logger.debug(
            "Wake-word detector active — listening for '%s'.", self.wake_word
        )

        try:
            window_frames: list[bytes] = []
            while True:
                if timeout is not None and (time.monotonic() - start_time) > timeout:
                    logger.debug("Wake-word detector timed out.")
                    return False

                data = stream.read(self.chunk_size, exception_on_overflow=False)
                window_frames.append(data)

                if len(window_frames) >= chunks_per_window:
                    detected = self._process_window(window_frames)
                    if detected:
                        logger.info("Wake word '%s' detected!", self.wake_word)
                        return True
                    # Slide the window forward by half its length
                    window_frames = window_frames[chunks_per_window // 2 :]
        finally:
            stream.stop_stream()
            stream.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_window(self, frames: list[bytes]) -> bool:
        """Transcribe *frames* and check for the wake word.

        Returns ``True`` if the wake word appears in the transcript.
        """
        raw = b"".join(frames)
        audio_int16 = np.frombuffer(raw, dtype=np.int16)
        rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))

        if rms < self.energy_threshold:
            return False  # silence — skip transcription

        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        try:
            assert self._whisper_model is not None  # noqa: S101
            result = self._whisper_model.transcribe(
                audio_float32,
                language="en",
                fp16=False,
            )
            transcript: str = result.get("text", "").lower().strip()
            logger.debug("Wake-word window transcript: %r", transcript)
            return self.wake_word in transcript
        except Exception as exc:  # noqa: BLE001
            logger.error("Wake-word transcription error: %s", exc)
            return False

    def _ensure_whisper(self) -> None:
        """Lazy-load the Whisper model."""
        if self._whisper_model is not None:
            return
        try:
            import whisper  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            ) from exc

        logger.info("Loading Whisper model '%s'…", self._whisper_model_name)
        self._whisper_model = whisper.load_model(self._whisper_model_name)
        logger.info("Whisper model loaded.")

    def _get_pyaudio(self) -> Any:
        if self._pyaudio is not None:
            return self._pyaudio
        try:
            import pyaudio  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "PyAudio is not installed. Run: pip install pyaudio"
            ) from exc
        self._pyaudio = pyaudio.PyAudio()
        return self._pyaudio

    def __del__(self) -> None:
        if self._pyaudio is not None:
            try:
                self._pyaudio.terminate()
            except Exception:  # noqa: BLE001
                pass
