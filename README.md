# MARS — My Automated Response System

```
 ███╗   ███╗ █████╗ ██████╗ ███████╗
 ████╗ ████║██╔══██╗██╔══██╗██╔════╝
 ██╔████╔██║███████║██████╔╝███████╗
 ██║╚██╔╝██║██╔══██║██╔══██╗╚════██║
 ██║ ╚═╝ ██║██║  ██║██║  ██║███████║
 ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
   My Automated Response System
```

> A privacy-aware, voice-authenticated AI assistant that runs locally and connects to the services you already use.

---

## Features

| Category | Capability |
|---|---|
| 🎙️ Voice | Wake-word detection, speaker verification, Whisper STT, ElevenLabs / pyttsx3 TTS |
| 🤖 AI | GPT-4o chat, conversation memory, persona customisation |
| 🌤️ Info | Weather, news headlines, stock quotes, Wikipedia lookups |
| 🎵 Media | Spotify playback, YouTube audio via yt-dlp |
| 📅 Productivity | Google Calendar events, Gmail compose & read, to-do list |
| 🏠 Smart Home | Home Assistant control via REST API, MQTT publish |
| 🖥️ System | CPU / RAM / disk stats, process management, SSH remote commands |
| 🌐 Web | Google search, web scraping, QR code generation, speed test |
| 📄 Files | PDF text extraction, OCR on images via Tesseract |
| 🌍 Translation | Real-time language translation (googletrans) |

---

## Prerequisites

- **Python 3.11+**
- **PortAudio** (for PyAudio)
  - macOS: `brew install portaudio`
  - Ubuntu/Debian: `sudo apt install portaudio19-dev`
  - Windows: included in the PyAudio wheel
- **Tesseract OCR** (optional, for OCR skill)
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`
- **ffmpeg** (required by openai-whisper and yt-dlp)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
- API keys — see [Configuration](#configuration)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/MARS.git
cd MARS

# 2. Create and activate a virtual environment
python3.11 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Run the interactive setup wizard
python setup_mars.py

# 5. Enroll your voice (one-time)
python enroll_voice.py

# 6. Launch MARS
python main.py
```

---

## Usage Examples

Once MARS is running, say the wake word (default **"Hey MARS"**) followed by a command:

```
"Hey MARS, what's the weather in London?"
"Hey MARS, play Bohemian Rhapsody on Spotify."
"Hey MARS, add milk to my shopping list."
"Hey MARS, what are today's top news headlines?"
"Hey MARS, set a reminder for my 3 PM meeting."
"Hey MARS, what's the stock price of Apple?"
"Hey MARS, turn off the living room lights."
"Hey MARS, translate 'good morning' to French."
"Hey MARS, how much RAM is my computer using?"
"Hey MARS, read my latest emails."
```

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key (GPT-4o + Whisper) | ✅ |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS key | Optional |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID | Optional |
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap key | For weather |
| `NEWS_API_KEY` | NewsAPI.org key | For news |
| `SPOTIFY_CLIENT_ID` | Spotify app client ID | For Spotify |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret | For Spotify |
| `SPOTIFY_REDIRECT_URI` | OAuth redirect URI | For Spotify |
| `GOOGLE_CREDENTIALS_PATH` | Path to Google OAuth JSON | For Calendar/Gmail |
| `GMAIL_ADDRESS` | Gmail address | For Gmail |
| `GMAIL_APP_PASSWORD` | Gmail app password | For Gmail |
| `HOME_ASSISTANT_URL` | Home Assistant base URL | For smart home |
| `HOME_ASSISTANT_TOKEN` | Long-lived access token | For smart home |
| `PICOVOICE_ACCESS_KEY` | Picovoice key (wake word) | Optional |
| `OWNER_NAME` | Your name (personalises responses) | Optional |

### config/settings.yaml

The setup wizard creates `config/settings.yaml`. Edit it to customise behaviour:

```yaml
assistant:
  name: MARS
  wake_word: "hey mars"
  owner: Satyam

voice:
  tts_engine: elevenlabs      # elevenlabs | pyttsx3
  whisper_model: base         # tiny | base | small | medium | large
  speaker_verification: true
  verification_threshold: 0.75

logging:
  level: INFO
  file: logs/mars.log
```

---

## Skill List

| Skill | Trigger phrases |
|---|---|
| Weather | "weather in …", "forecast for …" |
| News | "news headlines", "latest news" |
| Stocks | "stock price of …", "how is … doing" |
| Wikipedia | "who is …", "what is …", "tell me about …" |
| Spotify | "play … on Spotify", "pause music", "next song" |
| YouTube | "play … on YouTube" |
| Calendar | "my schedule", "add event …", "next appointment" |
| Gmail | "read my emails", "send email to …" |
| To-Do | "add … to my list", "what's on my list" |
| Home Assistant | "turn on/off …", "set … to …" |
| System | "CPU usage", "memory usage", "disk space" |
| Translation | "translate … to …" |
| QR Code | "generate QR code for …" |
| Speed Test | "run a speed test", "check internet speed" |
| PDF | "read PDF …", "summarise document …" |
| OCR | "read text in image …" |
| SSH | "run … on server …" |

---

## Troubleshooting

**Microphone not detected**
```bash
python -c "import pyaudio; p = pyaudio.PyAudio(); print(p.get_device_count())"
```
Ensure PortAudio is installed and your microphone is selected as the default input device.

**`ModuleNotFoundError: No module named 'whisper'`**
```bash
pip install openai-whisper
```

**Wake word not triggering**
- Check your `PICOVOICE_ACCESS_KEY` in `.env`.
- Or set `wake_word_engine: keyword` in `settings.yaml` to use the fallback keyword spotter.

**Speaker verification always fails**
- Re-enroll: `python enroll_voice.py`
- Lower `verification_threshold` in `settings.yaml` (e.g. `0.65`).

**ElevenLabs TTS silent**
- Verify `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` are correct.
- MARS will automatically fall back to pyttsx3 if ElevenLabs fails.

---

## License

```
MIT License

Copyright (c) 2024 MARS Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```