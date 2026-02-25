"""
core/speaker_verify.py
======================
Speaker verification for MARS using resemblyzer voice embeddings.

The owner's voice embedding is pre-computed once via ``enroll_voice.py``
and stored at ``voice_profiles/owner_embedding.npy``.  At runtime each
audio buffer is embedded and its cosine similarity to the stored profile
is compared against the configured threshold.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np
import yaml

logger = logging.getLogger(__name__)

_SETTINGS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "settings.yaml"
)
_PROFILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "voice_profiles", "owner_embedding.npy"
)


def _load_settings() -> dict[str, Any]:
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}


class SpeakerVerifier:
    """Verifies that audio was produced by the registered owner.

    Resemblyzer produces a 256-dimensional d-vector (speaker embedding) for
    each audio clip.  Cosine similarity between two embeddings indicates how
    likely they are from the same speaker.

    Args:
        threshold: Similarity score (0–1) above which a speaker is accepted
                   as the owner.  Overrides the value in settings.yaml when
                   provided.
        profile_path: Path to the owner's ``.npy`` embedding file.

    Example::

        verifier = SpeakerVerifier()
        verifier.load_profile()
        is_owner = verifier.verify(audio_array)
    """

    def __init__(
        self,
        threshold: float | None = None,
        profile_path: str = _PROFILE_PATH,
    ) -> None:
        settings = _load_settings()
        self.threshold: float = threshold or settings.get("mars", {}).get(
            "voice_threshold", 0.75
        )
        self.profile_path = profile_path
        self._owner_embedding: np.ndarray | None = None
        self._encoder: Any | None = None  # resemblyzer.VoiceEncoder

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_profile(self) -> bool:
        """Load the owner's voice embedding from disk.

        Returns:
            ``True`` if the profile was loaded successfully, ``False`` if the
            file does not exist.

        Raises:
            ValueError: If the stored array has an unexpected shape.
        """
        if not os.path.exists(self.profile_path):
            logger.warning(
                "Owner embedding not found at '%s'. "
                "Run enroll_voice.py to create it.",
                self.profile_path,
            )
            return False

        embedding = np.load(self.profile_path)
        if embedding.ndim != 1:
            raise ValueError(
                f"Expected a 1-D embedding array, got shape {embedding.shape}."
            )
        self._owner_embedding = embedding
        logger.info("Owner voice profile loaded (%d dims).", embedding.shape[0])
        return True

    def get_embedding(self, audio_data: np.ndarray) -> np.ndarray:
        """Compute a speaker embedding for *audio_data*.

        Args:
            audio_data: 1-D float32 NumPy array of raw audio samples at
                        16 000 Hz (as produced by
                        :class:`~core.listener.Listener`).

        Returns:
            256-dimensional float32 d-vector.

        Raises:
            ImportError: If resemblyzer is not installed.
        """
        self._ensure_encoder()
        assert self._encoder is not None  # noqa: S101 – for type narrowing

        from resemblyzer import preprocess_wav  # type: ignore[import]

        wav = preprocess_wav(audio_data, source_sr=16_000)
        embedding: np.ndarray = self._encoder.embed_utterance(wav)
        return embedding

    def verify(self, audio_data: np.ndarray) -> bool:
        """Return ``True`` if *audio_data* matches the owner's voice profile.

        If no owner profile has been loaded yet, :meth:`load_profile` is
        called automatically.  If the profile file is missing, verification
        defaults to ``True`` (fail-open) so MARS remains usable without
        enrolment.

        Args:
            audio_data: 1-D float32 NumPy array of raw PCM samples at 16 kHz.

        Returns:
            ``True`` when the cosine similarity exceeds ``self.threshold``.
        """
        if self._owner_embedding is None:
            loaded = self.load_profile()
            if not loaded:
                logger.warning(
                    "No owner profile available — verification skipped (fail-open)."
                )
                return True

        try:
            embedding = self.get_embedding(audio_data)
            similarity = float(_cosine_similarity(embedding, self._owner_embedding))
            logger.debug("Speaker similarity: %.4f (threshold %.2f)", similarity, self.threshold)
            return similarity >= self.threshold
        except Exception as exc:  # noqa: BLE001
            logger.error("Speaker verification failed: %s — defaulting to True.", exc)
            return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_encoder(self) -> None:
        """Lazy-load the resemblyzer VoiceEncoder (downloads model on first use)."""
        if self._encoder is not None:
            return
        try:
            from resemblyzer import VoiceEncoder  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "resemblyzer is not installed. Run: pip install resemblyzer"
            ) from exc

        self._encoder = VoiceEncoder()
        logger.debug("VoiceEncoder loaded.")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two 1-D vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
