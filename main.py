#!/usr/bin/env python3
"""
main.py — Entry point for MARS (My Automated Response System).

Lifecycle
---------
1. Load .env with python-dotenv and configure logging.
2. Load config/settings.yaml for runtime preferences.
3. Initialise the Whisper STT model and the speaker encoder.
4. Enter the wake-word listener loop.
5. On wake-word detection:
   a. Record a short audio clip.
   b. Transcribe with Whisper.
   c. Verify the speaker identity (optional).
   d. Send the transcript to the AI engine (OpenAI GPT-4o).
   e. Speak the response aloud (ElevenLabs → pyttsx3 fallback).
6. Handle KeyboardInterrupt / SIGTERM gracefully.

Usage:
    python main.py
"""

from __future__ import annotations

import io
import logging
import os
import signal
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# python-dotenv — must come before other project imports
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
except ImportError:
    print("  ✗  python-dotenv is not installed.  Run: pip install python-dotenv")
    sys.exit(1)

load_dotenv()

# ---------------------------------------------------------------------------
# Standard / third-party imports (graceful missing-dependency messages)
# ---------------------------------------------------------------------------
try:
    import numpy as np
except ImportError:
    print("  ✗  NumPy is not installed.  Run: pip install numpy")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("  ✗  PyYAML is not installed.  Run: pip install pyyaml")
    sys.exit(1)

try:
    import pyaudio
except ImportError:
    print("  ✗  PyAudio is not installed.  Run: pip install pyaudio")
    sys.exit(1)

try:
    import whisper
except ImportError:
    print("  ✗  openai-whisper is not installed.  Run: pip install openai-whisper")
    sys.exit(1)

try:
    import openai
except ImportError:
    print("  ✗  openai is not installed.  Run: pip install 'openai>=1.0.0'")
    sys.exit(1)

try:
    from resemblyzer import VoiceEncoder, preprocess_wav

    RESEMBLYZER_AVAILABLE = True
except ImportError:
    RESEMBLYZER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants / paths
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent
SETTINGS_PATH: Path = BASE_DIR / "config" / "settings.yaml"
EMBEDDING_PATH: Path = BASE_DIR / "voice_profiles" / "owner_embedding.npy"
LOG_DIR: Path = BASE_DIR / "logs"

RECORD_SECONDS: int = 5
SAMPLE_RATE: int = 16_000
CHANNELS: int = 1
FRAMES_PER_BUFFER: int = 1024

BANNER = r"""
 ███╗   ███╗ █████╗ ██████╗ ███████╗
 ████╗ ████║██╔══██╗██╔══██╗██╔════╝
 ██╔████╔██║███████║██████╔╝███████╗
 ██║╚██╔╝██║██╔══██║██╔══██╗╚════██║
 ██║ ╚═╝ ██║██║  ██║██║  ██║███████║
 ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
"""


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(level: str = "INFO", log_file: str = "logs/mars.log") -> logging.Logger:
    """Configure the root logger and return the MARS logger."""
    log_path = BASE_DIR / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("MARS")


# ---------------------------------------------------------------------------
# Settings loader
# ---------------------------------------------------------------------------


def _load_settings() -> dict[str, Any]:
    """Load config/settings.yaml; return sensible defaults if the file is absent."""
    defaults: dict[str, Any] = {
        "assistant": {"name": "MARS", "wake_word": "hey mars", "owner": "there"},
        "voice": {
            "tts_engine": "pyttsx3",
            "whisper_model": "base",
            "speaker_verification": False,
            "verification_threshold": 0.75,
        },
        "logging": {"level": "INFO", "file": "logs/mars.log"},
    }
    if not SETTINGS_PATH.exists():
        return defaults
    with SETTINGS_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    # Shallow-merge: let user values override defaults
    for section, values in data.items():
        if isinstance(values, dict):
            defaults.setdefault(section, {}).update(values)
        else:
            defaults[section] = values
    return defaults


# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------


def record_audio(pa: pyaudio.PyAudio, seconds: int = RECORD_SECONDS) -> bytes:
    """
    Record ``seconds`` of audio from the default input device.

    Returns
    -------
    bytes
        Raw 16-bit PCM audio data at ``SAMPLE_RATE`` Hz.
    """
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=FRAMES_PER_BUFFER,
    )
    frames: list[bytes] = []
    num_chunks = int(SAMPLE_RATE / FRAMES_PER_BUFFER * seconds)
    for _ in range(num_chunks):
        frames.append(stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False))
    stream.stop_stream()
    stream.close()
    return b"".join(frames)


def _pcm_to_wav_bytes(pcm: bytes) -> bytes:
    """Wrap raw PCM in a WAV container and return as bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Wake-word detection (keyword-based fallback)
# ---------------------------------------------------------------------------


def _contains_wake_word(text: str, wake_word: str) -> bool:
    """Return True if ``text`` contains the wake word (case-insensitive)."""
    return wake_word.lower() in text.lower()


# ---------------------------------------------------------------------------
# Whisper transcription
# ---------------------------------------------------------------------------


def transcribe(model: Any, pcm: bytes, logger: logging.Logger) -> str:
    """
    Transcribe raw PCM audio using the locally loaded Whisper model.

    Parameters
    ----------
    model:
        A loaded ``whisper`` model instance.
    pcm:
        Raw 16-bit mono PCM at 16 kHz.
    logger:
        Logger for debug output.

    Returns
    -------
    str
        The transcribed text (stripped), or an empty string on failure.
    """
    wav_bytes = _pcm_to_wav_bytes(pcm)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        result = model.transcribe(tmp_path, language="en", fp16=False)
        text: str = result.get("text", "").strip()
        logger.debug("Whisper transcript: %s", text)
        return text
    except Exception as exc:
        logger.warning("Whisper transcription failed: %s", exc)
        return ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Speaker verification
# ---------------------------------------------------------------------------


def verify_speaker(
    encoder: Any,
    pcm: bytes,
    owner_embedding: np.ndarray,
    threshold: float,
    logger: logging.Logger,
) -> bool:
    """
    Verify that the speaker in ``pcm`` matches the enrolled owner embedding.

    Parameters
    ----------
    encoder:
        A loaded ``resemblyzer.VoiceEncoder`` instance.
    pcm:
        Raw 16-bit mono PCM at 16 kHz.
    owner_embedding:
        The pre-computed owner voice embedding (shape ``(256,)``).
    threshold:
        Cosine-similarity threshold (0–1).  Higher → stricter.
    logger:
        Logger for debug output.

    Returns
    -------
    bool
        ``True`` if the speaker is sufficiently similar to the owner.
    """
    audio_int16 = np.frombuffer(pcm, dtype=np.int16)
    audio_float32 = audio_int16.astype(np.float32) / 32768.0

    try:
        processed = preprocess_wav(audio_float32, source_sr=SAMPLE_RATE)
        embedding = encoder.embed_utterance(processed)
        similarity = float(np.dot(embedding, owner_embedding) / (
            np.linalg.norm(embedding) * np.linalg.norm(owner_embedding) + 1e-9
        ))
        logger.debug("Speaker similarity score: %.4f (threshold: %.4f)", similarity, threshold)
        return similarity >= threshold
    except Exception as exc:
        logger.warning("Speaker verification error: %s", exc)
        return True  # fail-open to avoid blocking legitimate use


# ---------------------------------------------------------------------------
# AI engine (OpenAI GPT-4o)
# ---------------------------------------------------------------------------


def get_ai_response(
    client: openai.OpenAI,
    history: list[dict[str, str]],
    user_text: str,
    owner: str,
    logger: logging.Logger,
) -> str:
    """
    Send the conversation history + latest user utterance to GPT-4o.

    Parameters
    ----------
    client:
        Initialised ``openai.OpenAI`` client.
    history:
        Running conversation history (list of ``{"role": …, "content": …}`` dicts).
    user_text:
        The user's transcribed utterance.
    owner:
        The owner's name (for personalisation).
    logger:
        Logger for debug output.

    Returns
    -------
    str
        The assistant's reply text.
    """
    system_message = (
        f"You are MARS, a helpful AI assistant.  "
        f"The owner's name is {owner}.  "
        "Be concise, friendly, and conversational.  "
        "When asked for factual information, be accurate and cite sources where helpful."
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_message}]
    messages.extend(history[-20:])  # keep last 20 turns to stay within context limits
    messages.append({"role": "user", "content": user_text})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,  # type: ignore[arg-type]
            max_tokens=512,
            temperature=0.7,
        )
        reply: str = response.choices[0].message.content or ""
        logger.debug("GPT-4o reply: %s", reply)
        return reply.strip()
    except Exception as exc:
        logger.error("OpenAI API error: %s", exc)
        return "I'm sorry, I ran into a problem reaching the AI service.  Please try again."


# ---------------------------------------------------------------------------
# Text-to-speech
# ---------------------------------------------------------------------------


def speak(text: str, settings: dict[str, Any], logger: logging.Logger) -> None:
    """
    Speak ``text`` aloud using ElevenLabs (preferred) or pyttsx3 (fallback).

    Parameters
    ----------
    text:
        The string to synthesise.
    settings:
        The full settings dict (voice section consulted for engine choice).
    logger:
        Logger for debug output.
    """
    engine_choice: str = settings.get("voice", {}).get("tts_engine", "pyttsx3")

    if engine_choice == "elevenlabs":
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        if api_key and voice_id:
            if _speak_elevenlabs(text, api_key, voice_id, logger):
                return
        logger.warning("ElevenLabs unavailable — falling back to pyttsx3.")

    _speak_pyttsx3(text, logger)


def _speak_elevenlabs(text: str, api_key: str, voice_id: str, logger: logging.Logger) -> bool:
    """
    Synthesise ``text`` via ElevenLabs and play with PyAudio.

    Returns ``True`` on success, ``False`` on failure.
    """
    try:
        import requests

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()

        # Play the MP3 bytes using pydub + pyaudio
        try:
            from pydub import AudioSegment
            from pydub.playback import play

            audio = AudioSegment.from_file(io.BytesIO(resp.content), format="mp3")
            play(audio)
            return True
        except ImportError:
            # pydub not installed — save to a temp file and use system player
            import subprocess

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", tmp_path],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                return False
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    except Exception as exc:
        logger.warning("ElevenLabs TTS error: %s", exc)
        return False


def _speak_pyttsx3(text: str, logger: logging.Logger) -> None:
    """Synthesise ``text`` using the local pyttsx3 engine."""
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 0.9)
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        logger.error("pyttsx3 TTS error: %s", exc)
        print(f"MARS: {text}")  # last-resort fallback — just print it


# ---------------------------------------------------------------------------
# Wake-word listener (simple keyword spotter using Whisper)
# ---------------------------------------------------------------------------


def listen_for_wake_word(
    pa: pyaudio.PyAudio,
    whisper_model: Any,
    wake_word: str,
    logger: logging.Logger,
) -> bool:
    """
    Record a short audio clip and return ``True`` if the wake word is detected.

    Uses Whisper to transcribe a 2-second snippet, then checks for the wake word.

    Parameters
    ----------
    pa:
        Initialised PyAudio instance.
    whisper_model:
        Loaded Whisper model.
    wake_word:
        The phrase to listen for (e.g. ``"hey mars"``).
    logger:
        Logger instance.

    Returns
    -------
    bool
        ``True`` if the wake word was detected.
    """
    pcm = record_audio(pa, seconds=2)
    text = transcribe(whisper_model, pcm, logger)
    detected = _contains_wake_word(text, wake_word)
    if detected:
        logger.info("Wake word detected in: '%s'", text)
    return detected


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run() -> None:
    """
    Initialise all components and enter the main wake-word → respond loop.

    The loop runs until interrupted with Ctrl+C or SIGTERM.
    """
    # ── 1. Settings & logging ─────────────────────────────────────────────
    settings = _load_settings()
    log_cfg = settings.get("logging", {})
    logger = _setup_logging(
        level=log_cfg.get("level", "INFO"),
        log_file=log_cfg.get("file", "logs/mars.log"),
    )

    print(BANNER)
    logger.info("MARS starting up …")

    # ── 2. API key check ──────────────────────────────────────────────────
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        logger.error(
            "OPENAI_API_KEY is not set.  Run python setup_mars.py or edit .env"
        )
        sys.exit(1)

    # ── 3. Whisper model ──────────────────────────────────────────────────
    whisper_model_name: str = settings.get("voice", {}).get("whisper_model", "base")
    logger.info("Loading Whisper model '%s' …", whisper_model_name)
    whisper_model = whisper.load_model(whisper_model_name)
    logger.info("Whisper model loaded.")

    # ── 4. Speaker verification ───────────────────────────────────────────
    voice_cfg = settings.get("voice", {})
    do_verify: bool = voice_cfg.get("speaker_verification", False)
    verify_threshold: float = float(voice_cfg.get("verification_threshold", 0.75))
    voice_encoder: Any = None
    owner_embedding: np.ndarray | None = None

    if do_verify:
        if not RESEMBLYZER_AVAILABLE:
            logger.warning(
                "speaker_verification=true but resemblyzer is not installed — "
                "disabling verification.  Run: pip install resemblyzer"
            )
            do_verify = False
        elif not EMBEDDING_PATH.exists():
            logger.warning(
                "speaker_verification=true but no voice profile found at %s. "
                "Run python enroll_voice.py first — disabling verification.",
                EMBEDDING_PATH,
            )
            do_verify = False
        else:
            from resemblyzer import VoiceEncoder

            voice_encoder = VoiceEncoder()
            owner_embedding = np.load(str(EMBEDDING_PATH))
            logger.info("Speaker verification enabled (threshold=%.2f).", verify_threshold)

    # ── 5. OpenAI client ──────────────────────────────────────────────────
    openai_client = openai.OpenAI(api_key=openai_key)

    # ── 6. PyAudio ────────────────────────────────────────────────────────
    pa = pyaudio.PyAudio()

    # ── 7. Runtime config ─────────────────────────────────────────────────
    assistant_cfg = settings.get("assistant", {})
    wake_word: str = assistant_cfg.get("wake_word", "hey mars")
    owner: str = assistant_cfg.get("owner", "there")
    conversation_history: list[dict[str, str]] = []

    # ── 8. Graceful shutdown ──────────────────────────────────────────────
    _shutdown = False

    def _handle_signal(signum: int, frame: Any) -> None:
        nonlocal _shutdown
        logger.info("Received signal %d — shutting down gracefully.", signum)
        _shutdown = True

    signal.signal(signal.SIGTERM, _handle_signal)

    # ── 9. Greeting ───────────────────────────────────────────────────────
    greeting = f"MARS is online.  Say '{wake_word}' to begin."
    logger.info(greeting)
    print(f"\n  {greeting}\n")
    speak(f"Hello {owner}, MARS is online and ready.", settings, logger)

    # ── 10. Main loop ─────────────────────────────────────────────────────
    try:
        while not _shutdown:
            logger.debug("Listening for wake word …")

            if not listen_for_wake_word(pa, whisper_model, wake_word, logger):
                continue

            # Wake word detected — acknowledge and record the command
            logger.info("Wake word detected.  Listening for command …")
            speak("Yes?", settings, logger)

            command_pcm = record_audio(pa, seconds=RECORD_SECONDS)
            command_text = transcribe(whisper_model, command_pcm, logger)

            if not command_text:
                logger.info("No speech detected after wake word.")
                speak("I didn't catch that.  Please try again.", settings, logger)
                continue

            logger.info("Command received: '%s'", command_text)

            # Speaker verification
            if do_verify and voice_encoder is not None and owner_embedding is not None:
                if not verify_speaker(
                    voice_encoder, command_pcm, owner_embedding, verify_threshold, logger
                ):
                    logger.warning("Speaker verification failed — ignoring command.")
                    speak(
                        "Sorry, I don't recognise your voice.  "
                        "Please re-enrol or adjust the verification threshold.",
                        settings,
                        logger,
                    )
                    continue

            # AI response
            reply = get_ai_response(
                openai_client, conversation_history, command_text, owner, logger
            )

            # Update history
            conversation_history.append({"role": "user", "content": command_text})
            conversation_history.append({"role": "assistant", "content": reply})

            logger.info("MARS reply: %s", reply)
            speak(reply, settings, logger)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received — shutting down.")
    finally:
        pa.terminate()
        logger.info("MARS shut down cleanly.  Goodbye.")
        print("\n  MARS shut down.  Goodbye!\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()
