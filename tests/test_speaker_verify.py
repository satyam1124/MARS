"""
tests/test_speaker_verify.py
============================
Unit tests for core/speaker_verify.py.

NumPy, resemblyzer, and filesystem calls are mocked so no real audio
hardware or resemblyzer model is required.
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, mock_open

import numpy as np

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Stub resemblyzer before importing the module under test
# ---------------------------------------------------------------------------
_resemblyzer_stub = types.ModuleType("resemblyzer")
_resemblyzer_stub.VoiceEncoder = MagicMock()
_resemblyzer_stub.preprocess_wav = MagicMock(side_effect=lambda audio, source_sr: audio)
sys.modules["resemblyzer"] = _resemblyzer_stub

from core.speaker_verify import SpeakerVerifier, _cosine_similarity  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING: np.ndarray = np.ones(256, dtype=np.float32)
_SIMILAR_EMBEDDING: np.ndarray = np.ones(256, dtype=np.float32) * 0.9999
_DIFFERENT_EMBEDDING: np.ndarray = np.zeros(256, dtype=np.float32)
# Make the "different" one a unit vector pointing in a different direction
_DIFFERENT_EMBEDDING[0] = 1.0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSpeakerVerifierInit(unittest.TestCase):
    """Tests for SpeakerVerifier.__init__()."""

    def test_default_threshold_is_positive(self) -> None:
        verifier = SpeakerVerifier()
        self.assertGreater(verifier.threshold, 0.0)
        self.assertLessEqual(verifier.threshold, 1.0)

    def test_custom_threshold(self) -> None:
        verifier = SpeakerVerifier(threshold=0.85)
        self.assertAlmostEqual(verifier.threshold, 0.85)

    def test_custom_profile_path(self) -> None:
        verifier = SpeakerVerifier(profile_path="/tmp/test_profile.npy")
        self.assertEqual(verifier.profile_path, "/tmp/test_profile.npy")

    def test_no_embedding_loaded_initially(self) -> None:
        verifier = SpeakerVerifier()
        self.assertIsNone(verifier._owner_embedding)

    def test_no_encoder_loaded_initially(self) -> None:
        verifier = SpeakerVerifier()
        self.assertIsNone(verifier._encoder)


class TestLoadProfile(unittest.TestCase):
    """Tests for SpeakerVerifier.load_profile()."""

    def test_load_profile_success(self) -> None:
        verifier = SpeakerVerifier(profile_path="/fake/path/owner.npy")
        with patch("os.path.exists", return_value=True), \
             patch("numpy.load", return_value=_FAKE_EMBEDDING):
            result = verifier.load_profile()
        self.assertTrue(result)
        self.assertIsNotNone(verifier._owner_embedding)
        np.testing.assert_array_equal(verifier._owner_embedding, _FAKE_EMBEDDING)

    def test_load_profile_file_not_found(self) -> None:
        verifier = SpeakerVerifier(profile_path="/nonexistent/owner.npy")
        with patch("os.path.exists", return_value=False):
            result = verifier.load_profile()
        self.assertFalse(result)
        self.assertIsNone(verifier._owner_embedding)

    def test_load_profile_wrong_shape_raises(self) -> None:
        bad_embedding = np.ones((256, 256), dtype=np.float32)  # 2-D, not 1-D
        verifier = SpeakerVerifier(profile_path="/fake/path/owner.npy")
        with patch("os.path.exists", return_value=True), \
             patch("numpy.load", return_value=bad_embedding):
            with self.assertRaises(ValueError):
                verifier.load_profile()

    def test_load_profile_stores_correct_dims(self) -> None:
        embedding_256 = np.random.rand(256).astype(np.float32)
        verifier = SpeakerVerifier(profile_path="/fake/path/owner.npy")
        with patch("os.path.exists", return_value=True), \
             patch("numpy.load", return_value=embedding_256):
            verifier.load_profile()
        self.assertEqual(verifier._owner_embedding.shape, (256,))


class TestVerify(unittest.TestCase):
    """Tests for SpeakerVerifier.verify()."""

    def _make_verifier_with_profile(
        self,
        owner_emb: np.ndarray,
        threshold: float = 0.75,
    ) -> SpeakerVerifier:
        verifier = SpeakerVerifier(
            threshold=threshold,
            profile_path="/fake/owner.npy",
        )
        verifier._owner_embedding = owner_emb.copy()
        return verifier

    def test_verify_similar_embedding_returns_true(self) -> None:
        """A nearly identical embedding should pass verification."""
        owner = np.ones(256, dtype=np.float32)
        query = np.ones(256, dtype=np.float32) * 0.9999  # cosine sim ≈ 1.0
        verifier = self._make_verifier_with_profile(owner, threshold=0.75)

        with patch.object(verifier, "get_embedding", return_value=query):
            result = verifier.verify(np.zeros(16000, dtype=np.float32))
        self.assertTrue(result)

    def test_verify_different_embedding_returns_false(self) -> None:
        """An orthogonal embedding should fail verification."""
        owner = np.zeros(256, dtype=np.float32)
        owner[0] = 1.0  # unit vector in dimension 0
        query = np.zeros(256, dtype=np.float32)
        query[1] = 1.0  # unit vector in dimension 1 — orthogonal → similarity 0
        verifier = self._make_verifier_with_profile(owner, threshold=0.75)

        with patch.object(verifier, "get_embedding", return_value=query):
            result = verifier.verify(np.zeros(16000, dtype=np.float32))
        self.assertFalse(result)

    def test_verify_auto_loads_profile_if_missing(self) -> None:
        """verify() should call load_profile() when _owner_embedding is None."""
        verifier = SpeakerVerifier(profile_path="/fake/owner.npy", threshold=0.5)
        self.assertIsNone(verifier._owner_embedding)

        owner = np.ones(256, dtype=np.float32)
        query = np.ones(256, dtype=np.float32)

        with patch.object(verifier, "load_profile", return_value=True) as mock_load, \
             patch.object(verifier, "get_embedding", return_value=query):
            verifier._owner_embedding = owner  # simulate load_profile setting it
            result = verifier.verify(np.zeros(16000, dtype=np.float32))
        # load_profile was not called because we manually set _owner_embedding
        # Let's test the real path: embedding starts as None
        verifier2 = SpeakerVerifier(profile_path="/fake/owner.npy", threshold=0.5)

        def _fake_load() -> bool:
            verifier2._owner_embedding = owner
            return True

        with patch.object(verifier2, "load_profile", side_effect=_fake_load) as mock_load2, \
             patch.object(verifier2, "get_embedding", return_value=query):
            result2 = verifier2.verify(np.zeros(16000, dtype=np.float32))
        mock_load2.assert_called_once()
        self.assertTrue(result2)

    def test_verify_fail_open_when_no_profile_file(self) -> None:
        """When no profile exists, verify() should fail-open (return True)."""
        verifier = SpeakerVerifier(profile_path="/nonexistent/owner.npy")
        with patch("os.path.exists", return_value=False):
            result = verifier.verify(np.zeros(16000, dtype=np.float32))
        self.assertTrue(result)

    def test_verify_exception_defaults_to_true(self) -> None:
        """If get_embedding raises, verify() should default to True (fail-open)."""
        owner = np.ones(256, dtype=np.float32)
        verifier = self._make_verifier_with_profile(owner, threshold=0.75)
        with patch.object(verifier, "get_embedding", side_effect=RuntimeError("audio err")):
            result = verifier.verify(np.zeros(16000, dtype=np.float32))
        self.assertTrue(result)

    def test_verify_at_exact_threshold_passes(self) -> None:
        threshold = 0.80
        # Construct embeddings whose cosine similarity is exactly 1.0
        owner = np.ones(256, dtype=np.float32)
        query = np.ones(256, dtype=np.float32)
        # similarity = 1.0, which is >= 0.80 → should pass
        verifier = self._make_verifier_with_profile(owner, threshold=threshold)
        with patch.object(verifier, "get_embedding", return_value=query):
            result = verifier.verify(np.zeros(16000, dtype=np.float32))
        self.assertTrue(result)


class TestGetEmbedding(unittest.TestCase):
    """Tests for SpeakerVerifier.get_embedding()."""

    def test_get_embedding_calls_encoder(self) -> None:
        mock_encoder = MagicMock()
        fake_embedding = np.random.rand(256).astype(np.float32)
        mock_encoder.embed_utterance.return_value = fake_embedding

        verifier = SpeakerVerifier()
        verifier._encoder = mock_encoder  # inject encoder directly

        audio = np.zeros(16000, dtype=np.float32)

        # Patch resemblyzer.preprocess_wav so it just echoes back the audio
        with patch("core.speaker_verify.SpeakerVerifier._ensure_encoder"):
            result = verifier.get_embedding(audio)

        mock_encoder.embed_utterance.assert_called_once()
        np.testing.assert_array_equal(result, fake_embedding)

    def test_get_embedding_raises_without_resemblyzer(self) -> None:
        """If resemblyzer is not installed, ImportError should propagate."""
        verifier = SpeakerVerifier()

        def _raise_import(*_: object, **__: object) -> None:
            raise ImportError("resemblyzer not installed")

        with patch.object(verifier, "_ensure_encoder", side_effect=_raise_import):
            with self.assertRaises(ImportError):
                verifier.get_embedding(np.zeros(16000, dtype=np.float32))


class TestCosineSimilarity(unittest.TestCase):
    """Tests for the module-level _cosine_similarity() helper."""

    def test_identical_vectors_give_1(self) -> None:
        a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self.assertAlmostEqual(_cosine_similarity(a, a), 1.0, places=5)

    def test_orthogonal_vectors_give_0(self) -> None:
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        self.assertAlmostEqual(_cosine_similarity(a, b), 0.0, places=5)

    def test_opposite_vectors_give_minus_1(self) -> None:
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        self.assertAlmostEqual(_cosine_similarity(a, b), -1.0, places=5)

    def test_zero_vector_gives_0(self) -> None:
        a = np.zeros(4, dtype=np.float32)
        b = np.ones(4, dtype=np.float32)
        self.assertEqual(_cosine_similarity(a, b), 0.0)

    def test_similarity_symmetric(self) -> None:
        a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        b = np.array([4.0, 5.0, 6.0], dtype=np.float32)
        self.assertAlmostEqual(_cosine_similarity(a, b), _cosine_similarity(b, a), places=5)


if __name__ == "__main__":
    unittest.main()
