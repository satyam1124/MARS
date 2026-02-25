"""
core/ai_engine.py
=================
GPT-4o integration with OpenAI function/tool calling for MARS.

The engine maintains rolling conversation history via
:class:`~core.memory.ConversationMemory`, exposes all registered skills as
OpenAI tools, and automatically dispatches any tool calls returned by the
model back to :class:`~core.skill_registry.SkillRegistry`.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import yaml

from core.memory import ConversationMemory
from core.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

_SETTINGS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "settings.yaml"
)


def _load_settings() -> dict[str, Any]:
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}


class AIEngine:
    """Conversational AI engine backed by GPT-4o with tool/function calling.

    The engine:
    1. Prepends a system prompt describing MARS's persona.
    2. Sends the full (trimmed) conversation history to the model.
    3. Exposes registered skills as OpenAI tools so the model can invoke them.
    4. Executes any tool calls in the model response and feeds results back.
    5. Returns the final natural-language reply.

    Args:
        skill_registry: Registry of callable skills exposed as OpenAI tools.
        model:          OpenAI model name.  Defaults to settings.yaml value.
        max_tokens:     Maximum completion tokens.
        temperature:    Sampling temperature (0–2).
        max_history:    Maximum messages retained in conversation memory.
        system_prompt:  Overrides the system prompt from settings.yaml.

    Example::

        engine = AIEngine(skill_registry=registry)
        reply = engine.chat("What's the weather like in London?")
        print(reply)
    """

    def __init__(
        self,
        skill_registry: SkillRegistry | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        max_history: int | None = None,
        system_prompt: str | None = None,
    ) -> None:
        settings = _load_settings()
        ai_cfg = settings.get("ai", {})

        self.model: str = model or ai_cfg.get("model", "gpt-4o")
        self.max_tokens: int = max_tokens or ai_cfg.get("max_tokens", 1024)
        self.temperature: float = (
            temperature if temperature is not None else ai_cfg.get("temperature", 0.7)
        )
        self.system_prompt: str = system_prompt or ai_cfg.get(
            "system_prompt",
            "You are MARS, a witty and efficient AI assistant. Address your owner as 'sir'.",
        )
        max_hist: int = max_history or ai_cfg.get("max_history", 20)

        self.memory = ConversationMemory(max_messages=max_hist)
        self.registry: SkillRegistry | None = skill_registry

        # Lazy-loaded openai client
        self._client: Any | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_input: str) -> str:
        """Send *user_input* to the model and return the assistant reply.

        The method automatically handles tool calls in a loop until the model
        produces a plain text response (no pending tool calls).

        Args:
            user_input: Raw text from the user (post-STT).

        Returns:
            The assistant's final text response.
        """
        self.memory.add_message("user", user_input)

        messages = self._build_messages()
        tools = self._build_tools()

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI API error: %s", exc)
            return "I'm sorry, sir — I encountered an error reaching the AI service."

        reply = self._process_response(response, messages)
        self.memory.add_message("assistant", reply)
        return reply

    # ------------------------------------------------------------------
    # Tool schema builders
    # ------------------------------------------------------------------

    def _build_tools(self) -> list[dict[str, Any]]:
        """Return the list of OpenAI tool definitions from the skill registry.

        Returns an empty list when no registry is set or no skills are
        registered.
        """
        if self.registry is None:
            return []
        return self.registry.list_skills()

    # ------------------------------------------------------------------
    # Response processing
    # ------------------------------------------------------------------

    def _process_response(
        self,
        response: Any,
        messages: list[dict[str, Any]],
    ) -> str:
        """Process a model response, executing tool calls recursively.

        The model may return one or more tool calls.  Each is dispatched to
        the skill registry, and its result is appended as a ``tool`` message
        before re-calling the model.  This loop continues until the model
        produces a plain ``assistant`` message.

        Args:
            response: The raw OpenAI ``ChatCompletion`` object.
            messages: The message list sent in the last API call (mutated in
                      place to append tool results).

        Returns:
            The final assistant text reply.
        """
        choice = response.choices[0]
        message = choice.message

        # No tool calls — plain text reply
        if not message.tool_calls:
            return message.content or ""

        # Append the assistant's (partially formed) message with tool calls
        messages.append(message.model_dump(exclude_unset=True))

        # Execute each tool call and collect results
        for tool_call in message.tool_calls:
            result = self._execute_tool(
                tool_call.function.name,
                tool_call.function.arguments,
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

        # Re-call the model with tool results included
        try:
            client = self._get_client()
            follow_up = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return self._process_response(follow_up, messages)
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI follow-up call error: %s", exc)
            return "I encountered an issue processing the tool result, sir."

    def _execute_tool(self, name: str, arguments_json: str) -> str:
        """Parse *arguments_json* and dispatch to the skill registry.

        Args:
            name:            Skill / function name.
            arguments_json:  JSON string of keyword arguments.

        Returns:
            String result from the skill, or an error message.
        """
        if self.registry is None:
            return f"No skill registry available to execute '{name}'."

        try:
            kwargs: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse tool arguments for '%s': %s", name, exc)
            kwargs = {}

        logger.info("Executing tool '%s' with args %s.", name, kwargs)
        return self.registry.execute(name, **kwargs)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_messages(self) -> list[dict[str, Any]]:
        """Compose the full message list: system prompt + conversation history."""
        system_message: dict[str, Any] = {
            "role": "system",
            "content": self.system_prompt,
        }
        return [system_message] + self.memory.get_history()

    def _get_client(self) -> Any:
        """Lazy-load and return the OpenAI client.

        Raises:
            ImportError:    If the ``openai`` package is not installed.
            EnvironmentError: If ``OPENAI_API_KEY`` is not set.
        """
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai is not installed. Run: pip install openai"
            ) from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY environment variable is not set."
            )

        self._client = OpenAI(api_key=api_key)
        return self._client

    def reset_memory(self) -> None:
        """Clear the conversation history."""
        self.memory.clear()
        logger.info("Conversation memory cleared.")

    def __repr__(self) -> str:
        return (
            f"AIEngine(model={self.model!r}, "
            f"memory_length={len(self.memory)}, "
            f"skills={len(self.registry) if self.registry else 0})"
        )
