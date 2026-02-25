"""
MARS Core Package
=================
Core components for MARS (My Automated Response System).

Modules:
    listener        - Microphone input and Whisper-based speech-to-text
    speaker         - Text-to-speech output (macOS / pyttsx3 / ElevenLabs)
    speaker_verify  - Speaker verification via resemblyzer embeddings
    wake_word       - Continuous wake-word detection
    ai_engine       - GPT-4o integration with function/tool calling
    intent_router   - Maps parsed intents to registered skills
    memory          - Conversation history and context management
    skill_registry  - Dynamic skill registration and discovery
"""
