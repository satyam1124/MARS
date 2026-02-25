"""
core/speaker.py
===============
Text-to-speech output for MARS.

Supports three TTS engines:
  * ``macos``      – macOS ``say`` command (zero-dependency, default).
  * ``pyttsx3``    – Cross-platform offline TTS via the pyttsx3 library.
  * ``elevenlabs`` – High-quality cloud TTS via the ElevenLabs REST API.

The engine is selected from ``config/settings.yaml`` (``mars.tts_engine``).
If the selected engine is unavailable the class falls back automatically.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any

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


class Speaker:
    """Converts text to audible speech using the configured TTS engine.

    Args:
        engine: Override the engine specified in settings.yaml.
                One of ``"macos"``, ``"pyttsx3"``, or ``"elevenlabs"``.

    Example::

        speaker = Speaker()
        speaker.speak("All systems nominal, sir.")
    """

    _SUPPORTED_ENGINES = ("macos", "pyttsx3", "elevenlabs")

    def __init__(self, engine: str | None = None) -> None:
        settings = _load_settings()
        self._engine: str = (
            engine
            or settings.get("mars", {}).get("tts_engine", "macos")
        ).lower()

        # ElevenLabs config (only used when engine == "elevenlabs")
        self._xi_api_key: str = os.environ.get("ELEVENLABS_API_KEY", "")
        self._xi_voice_id: str = os.environ.get(
            "ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"
        )

        # pyttsx3 engine instance (lazy-loaded)
        self._pyttsx3_engine: Any | None = None

        if self._engine not in self._SUPPORTED_ENGINES:
            logger.warning(
                "Unknown TTS engine '%s'. Falling back to 'macos'.", self._engine
            )
            self._engine = "macos"

        logger.debug("Speaker initialised with engine: %s", self._engine)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """Convert *text* to speech using the configured engine.

        Falls back to the next available engine if the primary one fails.

        Args:
            text: The text string to be spoken aloud.
        """
        if not text or not text.strip():
            return

        text = text.strip()
        engines_to_try = [self._engine] + [
            e for e in self._SUPPORTED_ENGINES if e != self._engine
        ]

        for engine in engines_to_try:
            try:
                if engine == "macos":
                    self._speak_macos(text)
                elif engine == "pyttsx3":
                    self._speak_pyttsx3(text)
                elif engine == "elevenlabs":
                    self._speak_elevenlabs(text)
                return  # success — stop trying fallbacks
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TTS engine '%s' failed: %s. Trying next fallback.", engine, exc
                )

        # Last resort: print to stdout so output is never lost
        print(f"[MARS] {text}")

    # ------------------------------------------------------------------
    # Engine implementations
    # ------------------------------------------------------------------

    def _speak_macos(self, text: str) -> None:
        """Use the macOS ``say`` command-line tool.

        Raises:
            RuntimeError: If ``say`` is not available or returns a non-zero
                exit code.
        """
        result = subprocess.run(
            ["say", text],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"'say' exited with code {result.returncode}: {result.stderr.strip()}"
            )

    def _speak_pyttsx3(self, text: str) -> None:
        """Use the pyttsx3 offline TTS engine.

        Raises:
            ImportError: If pyttsx3 is not installed.
            RuntimeError: On any pyttsx3 runtime error.
        """
        try:
            import pyttsx3  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

        if self._pyttsx3_engine is None:
            self._pyttsx3_engine = pyttsx3.init()

        engine = self._pyttsx3_engine
        engine.say(text)
        engine.runAndWait()

    def _speak_elevenlabs(self, text: str) -> None:
        """Stream audio from the ElevenLabs TTS API and play it.

        Requires the ``ELEVENLABS_API_KEY`` environment variable.

        Raises:
            EnvironmentError: If the API key is missing.
            RuntimeError:     On a non-200 HTTP response.
        """
        import requests  # type: ignore[import]

        if not self._xi_api_key:
            raise EnvironmentError(
                "ELEVENLABS_API_KEY environment variable is not set."
            )

        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{self._xi_voice_id}"
        )
        headers = {
            "xi-api-key": self._xi_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs API error {response.status_code}: {response.text[:200]}"
            )

        # Write audio to a temp file and play it
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        try:
            # Try mpg123 → afplay (macOS) → ffplay in that order
            for player in ("mpg123", "afplay", "ffplay"):
                res = subprocess.run(
                    [player, tmp_path],
                    check=False,
                    capture_output=True,
                )
                if res.returncode == 0:
                    break
            else:
                raise RuntimeError("No supported audio player found (mpg123/afplay/ffplay).")
        finally:
            os.unlink(tmp_path)
