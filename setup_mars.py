#!/usr/bin/env python3
"""
setup_mars.py — Interactive setup wizard for MARS (My Automated Response System).

Guides the user through:
  - Python version check
  - API key collection (.env creation)
  - config/settings.yaml generation
  - voice_profiles/ directory creation
  - next-step instructions

Usage:
    python setup_mars.py
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANNER = r"""
 ███╗   ███╗ █████╗ ██████╗ ███████╗
 ████╗ ████║██╔══██╗██╔══██╗██╔════╝
 ██╔████╔██║███████║██████╔╝███████╗
 ██║╚██╔╝██║██╔══██║██╔══██╗╚════██║
 ██║ ╚═╝ ██║██║  ██║██║  ██║███████║
 ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
   My Automated Response System — Setup Wizard
"""

REQUIRED_PYTHON = (3, 11)

ENV_FIELDS: list[tuple[str, str, bool]] = [
    # (env key, human-readable prompt, is_required)
    ("OPENAI_API_KEY",          "OpenAI API key (required for GPT-4o + Whisper)", True),
    ("ELEVENLABS_API_KEY",      "ElevenLabs API key (optional, leave blank to use pyttsx3)", False),
    ("ELEVENLABS_VOICE_ID",     "ElevenLabs Voice ID (optional)", False),
    ("OPENWEATHERMAP_API_KEY",  "OpenWeatherMap API key (optional)", False),
    ("NEWS_API_KEY",            "NewsAPI.org key (optional)", False),
    ("SPOTIFY_CLIENT_ID",       "Spotify Client ID (optional)", False),
    ("SPOTIFY_CLIENT_SECRET",   "Spotify Client Secret (optional)", False),
    ("SPOTIFY_REDIRECT_URI",    "Spotify Redirect URI", False),
    ("GOOGLE_CREDENTIALS_PATH", "Path to Google OAuth2 credentials JSON", False),
    ("GMAIL_ADDRESS",           "Gmail address (optional)", False),
    ("GMAIL_APP_PASSWORD",      "Gmail app password (optional)", False),
    ("HOME_ASSISTANT_URL",      "Home Assistant URL (optional)", False),
    ("HOME_ASSISTANT_TOKEN",    "Home Assistant long-lived access token (optional)", False),
    ("PICOVOICE_ACCESS_KEY",    "Picovoice access key (optional, for wake-word detection)", False),
    ("OWNER_NAME",              "Your name (used to personalise responses)", False),
]

SETTINGS_TEMPLATE = """\
assistant:
  name: MARS
  wake_word: "hey mars"
  owner: "{owner}"

voice:
  tts_engine: {tts_engine}        # elevenlabs | pyttsx3
  whisper_model: base             # tiny | base | small | medium | large
  speaker_verification: true
  verification_threshold: 0.75

logging:
  level: INFO
  file: logs/mars.log
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_banner() -> None:
    print(BANNER)


def _check_python_version() -> None:
    """Abort if the Python version is below the required minimum."""
    major, minor = sys.version_info[:2]
    required_major, required_minor = REQUIRED_PYTHON
    if (major, minor) < (required_major, required_minor):
        print(
            f"  ✗  Python {required_major}.{required_minor}+ is required. "
            f"You are running Python {major}.{minor}."
        )
        sys.exit(1)
    print(f"  ✓  Python {major}.{minor} detected — OK\n")


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    """Prompt the user for input, optionally hiding the input."""
    if default:
        display_default = "****" if secret else default
        prompt_str = f"  {label} [{display_default}]: "
    else:
        prompt_str = f"  {label}: "

    if secret:
        import getpass
        value = getpass.getpass(prompt_str)
    else:
        value = input(prompt_str).strip()

    return value or default


def _collect_env_values() -> dict[str, str]:
    """Interactively collect values for every ENV_FIELDS entry."""
    print("─" * 60)
    print("  Step 1 of 3 — API Keys & Credentials")
    print("  (Press Enter to skip optional fields)")
    print("─" * 60 + "\n")

    values: dict[str, str] = {}
    for key, prompt_label, required in ENV_FIELDS:
        is_secret = "key" in key.lower() or "password" in key.lower() or "secret" in key.lower() or "token" in key.lower()
        while True:
            value = _prompt(prompt_label, secret=is_secret)
            if required and not value:
                print(f"    ⚠  '{key}' is required — please enter a value.\n")
            else:
                break
        values[key] = value

    return values


def _write_env_file(values: dict[str, str], path: Path) -> None:
    """Write the collected key/value pairs to a .env file."""
    lines = []
    for key, prompt_label, _ in ENV_FIELDS:
        value = values.get(key, "")
        lines.append(f"{key}={value}\n")

    path.write_text("".join(lines), encoding="utf-8")
    print(f"\n  ✓  Created {path}")


def _write_settings_yaml(values: dict[str, str], path: Path) -> None:
    """Generate config/settings.yaml from template."""
    owner = values.get("OWNER_NAME") or "User"
    tts_engine = "elevenlabs" if values.get("ELEVENLABS_API_KEY") else "pyttsx3"
    content = SETTINGS_TEMPLATE.format(owner=owner, tts_engine=tts_engine)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  ✓  Created {path}")


def _create_directories(base: Path) -> None:
    """Create required runtime directories."""
    dirs = [
        base / "voice_profiles",
        base / "logs",
        base / "config",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓  Directory ready: {d.relative_to(base)}")


def _print_next_steps() -> None:
    print("\n" + "─" * 60)
    print("  Setup complete! 🎉  Next steps:")
    print("─" * 60)
    steps = textwrap.dedent(
        """\

        1. Install dependencies (if you haven't yet):
               pip install -r requirements.txt

        2. Enrol your voice so MARS can recognise you:
               python enroll_voice.py

        3. Launch MARS:
               python main.py

        4. Say  "Hey MARS"  to wake the assistant, then ask
           anything — e.g. "What's the weather today?"

        For more information, see README.md.
        """
    )
    print(steps)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the MARS setup wizard."""
    _print_banner()
    print("  Checking Python version …")
    _check_python_version()

    base_dir = Path(__file__).resolve().parent

    # Step 1 — collect API keys
    values = _collect_env_values()

    print("\n" + "─" * 60)
    print("  Step 2 of 3 — Writing configuration files")
    print("─" * 60 + "\n")

    _write_env_file(values, base_dir / ".env")
    _write_settings_yaml(values, base_dir / "config" / "settings.yaml")

    print("\n" + "─" * 60)
    print("  Step 3 of 3 — Creating runtime directories")
    print("─" * 60 + "\n")

    _create_directories(base_dir)

    _print_next_steps()


if __name__ == "__main__":
    main()
