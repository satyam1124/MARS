"""
translator.py — Text translation and language detection skills for MARS.

All functions return a ``str`` response that MARS speaks aloud.
Uses the ``googletrans`` library (googletrans==4.0.0-rc1).

Functions
---------
translate_text          : Translate text into a target language.
detect_language         : Detect the language of a given text.
list_supported_languages: List all languages supported by googletrans.
"""

from __future__ import annotations

from utils.logger import get_logger

log = get_logger(__name__)


def _get_translator():
    """Return a cached :class:`googletrans.Translator` instance."""
    try:
        from googletrans import Translator
        return Translator()
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Language name helpers
# ---------------------------------------------------------------------------

def _get_lang_map() -> dict[str, str]:
    """Return the googletrans LANGUAGES dict (code → name), or empty dict."""
    try:
        from googletrans import LANGUAGES
        return LANGUAGES
    except ImportError:
        return {}


def _resolve_lang_code(language: str) -> str | None:
    """Return a BCP-47 language code for *language* (name or code).

    Accepts both language codes (``"fr"``) and full names (``"French"``).
    Returns ``None`` if the language is not found.
    """
    lang_map = _get_lang_map()
    lang_lower = language.lower().strip()

    # Direct code match
    if lang_lower in lang_map:
        return lang_lower

    # Match by name
    for code, name in lang_map.items():
        if name.lower() == lang_lower:
            return code

    return None


# ---------------------------------------------------------------------------
# translate_text
# ---------------------------------------------------------------------------


def translate_text(
    text: str,
    target_language: str,
    source_language: str = "auto",
) -> str:
    """Translate *text* into *target_language*.

    Parameters
    ----------
    text:
        The text to translate.
    target_language:
        Target language name or BCP-47 code (e.g. ``"French"`` or ``"fr"``).
    source_language:
        Source language name or code.  Pass ``"auto"`` (default) to
        detect automatically.

    Returns
    -------
    str
        Spoken translation result or error message.
    """
    if not text.strip():
        return "Please provide some text to translate."
    if not target_language.strip():
        return "Please specify a target language."

    translator = _get_translator()
    if translator is None:
        return "Translation is unavailable. Please install the googletrans library."

    # Resolve target language code
    target_code = _resolve_lang_code(target_language)
    if target_code is None:
        return f"I don't recognise the language '{target_language}'."

    # Resolve source language code
    if source_language.lower().strip() in ("auto", "detect", ""):
        src_code = "auto"
    else:
        src_code = _resolve_lang_code(source_language)
        if src_code is None:
            return f"I don't recognise the source language '{source_language}'."

    try:
        kwargs: dict = {"dest": target_code}
        if src_code != "auto":
            kwargs["src"] = src_code

        result = translator.translate(text, **kwargs)
        translated: str = result.text
        detected_src: str = result.src

        lang_map = _get_lang_map()
        src_name = lang_map.get(detected_src, detected_src).capitalize()
        tgt_name = lang_map.get(target_code, target_code).capitalize()

        spoken = (
            f"Translated from {src_name} to {tgt_name}: {translated}"
        )
        log.info(
            "translate_text: %r → %r (%s→%s)",
            text[:50], translated[:50], detected_src, target_code,
        )
        return spoken
    except Exception as exc:
        log.error("translate_text failed: %s", exc)
        return f"I was unable to translate that text: {exc}"


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    """Detect the language of *text* and return a spoken result.

    Parameters
    ----------
    text:
        The text whose language should be identified.

    Returns
    -------
    str
        Spoken language detection result or error message.
    """
    if not text.strip():
        return "Please provide some text for language detection."

    translator = _get_translator()
    if translator is None:
        return "Language detection is unavailable. Please install the googletrans library."

    try:
        detection = translator.detect(text)
        lang_code: str = detection.lang
        confidence: float = detection.confidence or 0.0

        lang_map = _get_lang_map()
        lang_name = lang_map.get(lang_code, lang_code).capitalize()
        confidence_pct = int(confidence * 100)

        spoken = (
            f"The detected language is {lang_name} "
            f"with {confidence_pct}% confidence."
        )
        log.info("detect_language(%r): %s (%.0f%%)", text[:50], lang_name, confidence * 100)
        return spoken
    except Exception as exc:
        log.error("detect_language failed: %s", exc)
        return f"I was unable to detect the language: {exc}"


# ---------------------------------------------------------------------------
# list_supported_languages
# ---------------------------------------------------------------------------


def list_supported_languages() -> str:
    """Return a spoken list of languages supported by googletrans.

    Returns
    -------
    str
        A spoken statement with the total count and a sample of language names.
    """
    lang_map = _get_lang_map()
    if not lang_map:
        return "Language list is unavailable. Please install the googletrans library."

    names = sorted(name.capitalize() for name in lang_map.values())
    total = len(names)

    # Speak a sample to avoid an extremely long list
    sample_size = 10
    sample = names[:sample_size]
    sample_str = ", ".join(sample)

    spoken = (
        f"I support {total} languages. "
        f"A few examples include: {sample_str}, and many more."
    )
    log.info("list_supported_languages: %d languages", total)
    return spoken
