"""
core/listener.py
================
Microphone input and OpenAI Whisper speech-to-text for MARS.

Audio is captured via PyAudio with simple energy-based silence detection.
Transcription is performed locally using the ``openai-whisper`` library.
"""

from __future__ import annotations

import io
import logging
import os
import wave
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


class Listener:
    """Records audio from the default microphone and transcribes it.

    Audio recording uses energy-based voice activity detection (VAD): the
    microphone is read in chunks; recording stops when the audio energy
    stays below ``silence_threshold`` for ``silence_duration`` seconds.

    Transcription is performed with `openai-whisper
    <https://github.com/openai/whisper>`_ running entirely on-device.

    Args:
        sample_rate:        PCM sample rate in Hz.
        channels:           Number of audio channels (1 = mono).
        chunk_size:         PyAudio read chunk size in frames.
        silence_threshold:  RMS energy below which a chunk is considered
                            silent.
        silence_duration:   Seconds of consecutive silence that trigger end
                            of recording.
        max_recording_duration: Hard upper limit on recording length in
                            seconds.
        whisper_model:      Whisper model size (``"tiny"``, ``"base"``,
                            ``"small"``, ``"medium"``, ``"large"``).

    Example::

        listener = Listener()
        text = listener.listen_once()
        print(text)
    """

    def __init__(
        self,
        sample_rate: int | None = None,
        channels: int | None = None,
        chunk_size: int | None = None,
        silence_threshold: int | None = None,
        silence_duration: float | None = None,
        max_recording_duration: float | None = None,
        whisper_model: str | None = None,
    ) -> None:
        settings = _load_settings()
        audio_cfg = settings.get("audio", {})
        mars_cfg = settings.get("mars", {})

        self.sample_rate: int = sample_rate or audio_cfg.get("sample_rate", 16_000)
        self.channels: int = channels or audio_cfg.get("channels", 1)
        self.chunk_size: int = chunk_size or audio_cfg.get("chunk_size", 1024)
        self.silence_threshold: int = silence_threshold or audio_cfg.get(
            "silence_threshold", 500
        )
        self.silence_duration: float = silence_duration or audio_cfg.get(
            "silence_duration", 1.5
        )
        self.max_recording_duration: float = max_recording_duration or audio_cfg.get(
            "max_recording_duration", 30
        )
        self._whisper_model_name: str = whisper_model or mars_cfg.get(
            "whisper_model", "base"
        )

        self._whisper_model: Any | None = None  # lazy-loaded
        self._pyaudio: Any | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_audio(self) -> np.ndarray:
        """Capture audio from the microphone until silence is detected.

        Recording begins immediately.  It ends when either:
        * ``silence_duration`` seconds of consecutive silence have elapsed, or
        * ``max_recording_duration`` seconds have been recorded.

        Returns:
            1-D float32 NumPy array of normalised PCM samples (range –1 … 1)
            at ``self.sample_rate`` Hz.

        Raises:
            ImportError: If PyAudio is not installed.
            OSError:     If no input device is available.
        """
        import pyaudio  # type: ignore[import]

        pa = self._get_pyaudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        logger.debug("Recording started.")
        frames: list[bytes] = []
        silent_chunks = 0
        max_chunks = int(
            self.max_recording_duration * self.sample_rate / self.chunk_size
        )
        silence_chunks_needed = int(
            self.silence_duration * self.sample_rate / self.chunk_size
        )

        try:
            for _ in range(max_chunks):
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                rms = _compute_rms(data)
                if rms < self.silence_threshold:
                    silent_chunks += 1
                else:
                    silent_chunks = 0
                if silent_chunks >= silence_chunks_needed and len(frames) > silence_chunks_needed:
                    break
        finally:
            stream.stop_stream()
            stream.close()

        logger.debug("Recording stopped. Captured %d chunks.", len(frames))

        # Convert raw bytes → float32 array
        raw = b"".join(frames)
        audio_int16 = np.frombuffer(raw, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        return audio_float32

    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe a float32 audio array using Whisper.

        Args:
            audio_data: 1-D float32 NumPy array at ``self.sample_rate`` Hz.

        Returns:
            Transcribed text string (empty string on failure).

        Raises:
            ImportError: If openai-whisper is not installed.
        """
        self._ensure_whisper()
        assert self._whisper_model is not None  # noqa: S101

        try:
            result = self._whisper_model.transcribe(
                audio_data,
                language="en",
                fp16=False,
            )
            text: str = result.get("text", "").strip()
            logger.debug("Whisper transcription: %r", text)
            return text
        except Exception as exc:  # noqa: BLE001
            logger.error("Whisper transcription error: %s", exc)
            return ""

    def listen_once(self) -> str:
        """Record one utterance and return its transcription.

        Convenience wrapper that calls :meth:`record_audio` followed by
        :meth:`transcribe`.

        Returns:
            Transcribed text or an empty string if nothing was captured.
        """
        audio = self.record_audio()
        if audio.size == 0:
            return ""
        return self.transcribe(audio)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_whisper(self) -> None:
        """Lazy-load the Whisper model (downloads weights on first use)."""
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
        """Return a shared PyAudio instance, initialising it on first call."""
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


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _compute_rms(data: bytes) -> float:
    """Compute the root-mean-square energy of a raw int16 PCM buffer."""
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))
