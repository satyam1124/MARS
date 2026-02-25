"""
core/skill_registry.py
======================
Dynamic skill registration and discovery for MARS.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Central registry for MARS skills (callable capabilities).

    Skills are registered with a name, a callable, a human-readable
    description, and an optional JSON-Schema-style parameters dict that is
    surfaced to the AI engine for function-calling.

    Example::

        registry = SkillRegistry()

        def get_weather(location: str) -> str:
            return f"It's sunny in {location}, sir."

        registry.register(
            name="get_weather",
            func=get_weather,
            description="Get the current weather for a location.",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"],
            },
        )

        result = registry.execute("get_weather", location="London")
    """

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        func: Callable[..., str],
        description: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Register a new skill.

        Args:
            name:        Unique skill identifier (used as the function name in
                         OpenAI tool schemas).
            func:        Callable that implements the skill. Should return a
                         ``str`` suitable for text-to-speech output.
            description: Short, human-readable description used in the tool
                         schema sent to the AI.
            parameters:  Optional JSON-Schema-style object describing the
                         arguments accepted by *func*.  Defaults to an empty
                         object schema.
        """
        if name in self._skills:
            logger.warning("Skill '%s' is already registered — overwriting.", name)

        self._skills[name] = {
            "func": func,
            "description": description,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        logger.debug("Skill registered: %s", name)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_skill(self, name: str) -> dict[str, Any] | None:
        """Retrieve the skill entry for *name*, or ``None`` if not found.

        Args:
            name: The skill identifier.

        Returns:
            A dict with keys ``func``, ``description``, and ``parameters``,
            or ``None`` when the skill does not exist.
        """
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        """Return a list of tool-schema dicts for all registered skills.

        Each entry follows the OpenAI function-calling schema::

            {
                "type": "function",
                "function": {
                    "name": "<name>",
                    "description": "<description>",
                    "parameters": { ... }
                }
            }

        Returns:
            List of OpenAI-compatible tool definitions.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": entry["description"],
                    "parameters": entry["parameters"],
                },
            }
            for name, entry in self._skills.items()
        ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, name: str, **kwargs: Any) -> str:
        """Execute the skill identified by *name* with *kwargs*.

        Args:
            name:   The registered skill name.
            **kwargs: Arguments forwarded verbatim to the skill callable.

        Returns:
            The string returned by the skill callable, or an error message
            if the skill is not found or raises an exception.
        """
        entry = self._skills.get(name)
        if entry is None:
            msg = f"Unknown skill: '{name}'"
            logger.error(msg)
            return msg

        try:
            result: str = entry["func"](**kwargs)
            logger.debug("Skill '%s' executed successfully.", name)
            return result
        except Exception as exc:  # noqa: BLE001
            msg = f"Skill '{name}' raised an error: {exc}"
            logger.exception(msg)
            return f"I encountered an error while executing '{name}', sir."

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def __repr__(self) -> str:
        return f"SkillRegistry(skills={list(self._skills.keys())})"
