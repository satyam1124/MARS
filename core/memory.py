"""
core/memory.py
==============
Conversation history and context management for MARS.
"""

from __future__ import annotations


class ConversationMemory:
    """Stores and manages the rolling conversation history between the user
    and the AI engine.

    Each message is represented as a dict conforming to the OpenAI Chat
    Completions message format::

        {"role": "user" | "assistant" | "system", "content": "<text>"}

    Args:
        max_messages: Maximum number of messages to retain before the oldest
            messages are automatically trimmed. Defaults to 20.

    Example::

        memory = ConversationMemory(max_messages=10)
        memory.add_message("user", "Hello!")
        memory.add_message("assistant", "Good day, sir.")
        history = memory.get_history()
    """

    def __init__(self, max_messages: int = 20) -> None:
        self._history: list[dict[str, str]] = []
        self.max_messages = max_messages

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str) -> None:
        """Append a message to the conversation history.

        After appending, the history is trimmed to *max_messages* if needed.

        Args:
            role:    Message role — one of ``"user"``, ``"assistant"``, or
                     ``"system"``.
            content: The text content of the message.
        """
        self._history.append({"role": role, "content": content})
        self.trim_history(self.max_messages)

    def get_history(self) -> list[dict[str, str]]:
        """Return a shallow copy of the current conversation history.

        Returns:
            A list of message dicts ordered from oldest to newest.
        """
        return list(self._history)

    def trim_history(self, max_messages: int) -> None:
        """Trim the history so that it contains at most *max_messages* entries.

        The most recent messages are kept; the oldest are discarded.

        Args:
            max_messages: The maximum number of messages to retain. If the
                current history length is already within the limit nothing
                happens.
        """
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

    def clear(self) -> None:
        """Erase all stored conversation history."""
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)

    def __repr__(self) -> str:
        return (
            f"ConversationMemory(max_messages={self.max_messages}, "
            f"current_length={len(self._history)})"
        )
