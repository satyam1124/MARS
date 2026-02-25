"""
core/intent_router.py
=====================
Routes parsed intents to registered MARS skills and returns a spoken response.

The router holds a simple mapping of intent name → skill name (which in turn
is looked up in the :class:`~core.skill_registry.SkillRegistry`).  It can be
extended at runtime via :meth:`register_intent`.

For intents that do not map to an explicit skill the AI engine should be used
directly; the router simply returns ``None`` in that case.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class IntentRouter:
    """Maps intent strings to skills in a :class:`~core.skill_registry.SkillRegistry`.

    Args:
        skill_registry: A populated :class:`~core.skill_registry.SkillRegistry`
                        instance.  May also be set (or swapped) later via the
                        ``registry`` attribute.

    Example::

        router = IntentRouter(registry)
        router.register_intent("get_weather", "get_weather")
        response = router.route("get_weather", {"location": "London"})
    """

    # Default intent → skill mappings (intent name == skill name for simplicity)
    _DEFAULT_MAPPINGS: dict[str, str] = {
        # Weather
        "get_weather": "get_weather",
        "weather": "get_weather",
        # Time / date
        "get_time": "get_time",
        "what_time": "get_time",
        "get_date": "get_date",
        # Web search
        "search": "web_search",
        "web_search": "web_search",
        "google": "web_search",
        # News
        "news": "get_news",
        "get_news": "get_news",
        # Music
        "play_music": "play_music",
        "music": "play_music",
        # Reminders / timers
        "set_reminder": "set_reminder",
        "set_timer": "set_timer",
        # System
        "open_app": "open_app",
        "system_info": "system_info",
        # Email
        "send_email": "send_email",
        "read_email": "read_email",
        # Calendar
        "add_event": "add_calendar_event",
        "get_events": "get_calendar_events",
        # General
        "joke": "tell_joke",
        "stop": "stop",
        "exit": "stop",
    }

    def __init__(self, skill_registry: Any | None = None) -> None:
        self.registry = skill_registry
        self._mappings: dict[str, str] = dict(self._DEFAULT_MAPPINGS)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def register_intent(self, intent: str, skill_name: str) -> None:
        """Map an intent string to a registered skill name.

        Args:
            intent:     The intent identifier (e.g. ``"play_music"``).
            skill_name: The name under which the target skill is registered in
                        the ``SkillRegistry``.
        """
        self._mappings[intent.lower()] = skill_name
        logger.debug("Intent '%s' → skill '%s' registered.", intent, skill_name)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(self, intent: str, entities: dict[str, Any]) -> str | None:
        """Dispatch *intent* to the appropriate skill and return its response.

        Args:
            intent:   Intent name as a string (case-insensitive).
            entities: Key-value pairs extracted from the user utterance
                      (e.g. ``{"location": "London", "unit": "celsius"}``).
                      These are forwarded as keyword arguments to the skill.

        Returns:
            The string response from the skill, or ``None`` if no mapping
            exists for the intent or the registry is not set.
        """
        key = intent.lower().strip()
        skill_name = self._mappings.get(key)

        if skill_name is None:
            logger.debug("No skill mapping found for intent '%s'.", intent)
            return None

        if self.registry is None:
            logger.error("SkillRegistry is not set on IntentRouter.")
            return None

        logger.info("Routing intent '%s' → skill '%s' (entities=%s).", intent, skill_name, entities)
        return self.registry.execute(skill_name, **entities)

    def list_intents(self) -> list[str]:
        """Return a sorted list of all registered intent names.

        Returns:
            Sorted list of intent name strings.
        """
        return sorted(self._mappings.keys())

    def __repr__(self) -> str:
        return (
            f"IntentRouter(intents={len(self._mappings)}, "
            f"registry={'set' if self.registry else 'unset'})"
        )
