#!/usr/bin/env python3
"""
enroll_voice.py — Voice enrolment script for MARS (My Automated Response System).

Records 5–10 voice samples from the microphone, computes a speaker embedding for
each sample using Resemblyzer, averages the embeddings, and saves the result to
``voice_profiles/owner_embedding.npy``.

Run this script once before launching MARS for the first time, and re-run it
whenever you want to update your voice profile.

Usage:
    python enroll_voice.py [--samples N]

Options:
    --samples N     Number of voice samples to record (default: 7, min: 5, max: 10).
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
import wave
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Optional heavy imports — give the user a clear error if missing
# ---------------------------------------------------------------------------
try:
    import pyaudio
except ImportError:
    print("  ✗  PyAudio is not installed.  Run: pip install pyaudio")
    sys.exit(1)

try:
    from resemblyzer import VoiceEncoder, preprocess_wav
except ImportError:
    print("  ✗  Resemblyzer is not installed.  Run: pip install resemblyzer")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE: int = 16_000
CHANNELS: int = 1
SAMPLE_WIDTH: int = 2          # 16-bit PCM
RECORD_SECONDS: int = 4        # duration of each sample
SILENCE_THRESHOLD: int = 500   # RMS amplitude below which audio is considered silence
PROFILE_DIR: Path = Path("voice_profiles")
EMBEDDING_PATH: Path = PROFILE_DIR / "owner_embedding.npy"

BANNER = """
  ╔══════════════════════════════════════╗
  ║   MARS — Voice Enrolment Wizard      ║
  ╚══════════════════════════════════════╝
"""

PROMPTS: list[str] = [
    "Say: 'Hey MARS, what's the weather today?'",
    "Say: 'Hey MARS, play some music.'",
    "Say: 'Hey MARS, read my emails.'",
    "Say: 'Hey MARS, turn off the lights.'",
    "Say: 'Hey MARS, set a reminder for tomorrow.'",
    "Say: 'Hey MARS, what's the news today?'",
    "Say: 'Hey MARS, how are you?'",
    "Say: 'Hey MARS, tell me a joke.'",
    "Say: 'Hey MARS, what time is it?'",
    "Say: 'Hey MARS, open Spotify.'",
]


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------


def _compute_rms(data: bytes) -> float:
    """Return the root-mean-square amplitude of a raw PCM byte buffer."""
    count = len(data) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", data)
    sum_sq = sum(s * s for s in shorts)
    return (sum_sq / count) ** 0.5


def record_sample(pa: pyaudio.PyAudio, index: int, total: int) -> np.ndarray | None:
    """
    Record a single voice sample from the default microphone.

    Parameters
    ----------
    pa:
        An initialised PyAudio instance.
    index:
        1-based sample index (for display purposes).
    total:
        Total number of samples being recorded (for display purposes).

    Returns
    -------
    numpy.ndarray or None
        Mono float32 waveform at ``SAMPLE_RATE`` Hz, or *None* if the
        recording was silent (likely a false trigger).
    """
    frames_per_buffer = 1024
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=frames_per_buffer,
    )

    print(f"\n  [{index}/{total}]  Recording in 3 … ", end="", flush=True)
    time.sleep(1)
    print("2 … ", end="", flush=True)
    time.sleep(1)
    print("1 … ", end="", flush=True)
    time.sleep(1)
    print("🎙  Speak now!", flush=True)

    frames: list[bytes] = []
    num_frames = int(SAMPLE_RATE / frames_per_buffer * RECORD_SECONDS)
    for _ in range(num_frames):
        frames.append(stream.read(frames_per_buffer, exception_on_overflow=False))

    stream.stop_stream()
    stream.close()

    raw = b"".join(frames)
    rms = _compute_rms(raw)
    if rms < SILENCE_THRESHOLD:
        print("  ⚠  Recording appears silent — skipping this sample.")
        return None

    # Convert int16 PCM → float32 in [-1, 1]
    audio_int16 = np.frombuffer(raw, dtype=np.int16)
    audio_float32 = audio_int16.astype(np.float32) / 32768.0
    print("  ✓  Sample captured.")
    return audio_float32


def _save_wav(audio: np.ndarray, path: Path) -> None:
    """Save a float32 mono waveform to a WAV file (for debugging / inspection)."""
    int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(int16.tobytes())


# ---------------------------------------------------------------------------
# Enrolment pipeline
# ---------------------------------------------------------------------------


def enroll(num_samples: int) -> None:
    """
    Record ``num_samples`` voice samples, compute and average their embeddings,
    then persist the result to ``EMBEDDING_PATH``.

    Parameters
    ----------
    num_samples:
        How many samples to record (5–10).
    """
    print(BANNER)
    print(
        f"  MARS will record {num_samples} short voice samples to build your\n"
        "  voice profile.  Please speak clearly in your normal voice.\n"
    )
    print("  Follow the on-screen prompt for each sample.")
    print("  ─" * 30)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    pa = pyaudio.PyAudio()
    encoder = VoiceEncoder()

    embeddings: list[np.ndarray] = []
    sample_index = 0

    while len(embeddings) < num_samples and sample_index < len(PROMPTS) * 2:
        prompt = PROMPTS[len(embeddings) % len(PROMPTS)]
        print(f"\n  {prompt}")

        audio = record_sample(pa, len(embeddings) + 1, num_samples)
        sample_index += 1

        if audio is None:
            continue

        # Resemblyzer preprocessing expects float32 at 16 kHz
        processed = preprocess_wav(audio, source_sr=SAMPLE_RATE)
        embedding = encoder.embed_utterance(processed)
        embeddings.append(embedding)

    pa.terminate()

    if len(embeddings) < 3:
        print(
            "\n  ✗  Not enough valid samples collected (need at least 3).  "
            "Please re-run enroll_voice.py in a quieter environment."
        )
        sys.exit(1)

    # Average all embeddings → single representative voice vector
    mean_embedding = np.mean(embeddings, axis=0)
    np.save(str(EMBEDDING_PATH), mean_embedding)

    print("\n" + "  ─" * 30)
    print(f"  ✓  Voice profile saved to: {EMBEDDING_PATH}")
    print(f"  ✓  Built from {len(embeddings)} samples (embedding dim: {mean_embedding.shape[0]})")
    print("\n  You can now launch MARS with:  python main.py\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrol the owner's voice for MARS speaker verification."
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=7,
        metavar="N",
        help="Number of voice samples to record (default: 7, range: 5–10).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = _parse_args()
    num_samples = max(5, min(10, args.samples))
    enroll(num_samples)


if __name__ == "__main__":
    main()
