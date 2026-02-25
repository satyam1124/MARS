"""
tests/test_ai_engine.py
=======================
Unit tests for core/ai_engine.py.

The OpenAI client and all network calls are mocked so no real API key or
network connection is required.
"""

from __future__ import annotations

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Stub resemblyzer before any core import
# ---------------------------------------------------------------------------
_resemblyzer_stub = types.ModuleType("resemblyzer")
sys.modules.setdefault("resemblyzer", _resemblyzer_stub)

from core.ai_engine import AIEngine  # noqa: E402
from core.memory import ConversationMemory  # noqa: E402
from core.skill_registry import SkillRegistry  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chat_response(content: str, tool_calls: list | None = None) -> MagicMock:
    """Build a minimal mock resembling an OpenAI ChatCompletion object."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls or []

    choice = MagicMock()
    choice.message = message

    # model_dump is called on message when there are tool calls
    message.model_dump = MagicMock(
        return_value={
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls or [],
        }
    )

    response = MagicMock()
    response.choices = [choice]
    return response


def _make_tool_call(call_id: str, name: str, args: dict) -> MagicMock:
    """Build a mock resembling an OpenAI ToolCall object."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAIEngineInit(unittest.TestCase):
    """Tests for AIEngine.__init__()."""

    def test_default_initialisation(self) -> None:
        engine = AIEngine()
        self.assertIsInstance(engine.memory, ConversationMemory)
        self.assertIsNone(engine.registry)
        self.assertIsInstance(engine.model, str)
        self.assertGreater(engine.max_tokens, 0)
        self.assertIsInstance(engine.temperature, float)
        self.assertIsInstance(engine.system_prompt, str)

    def test_custom_model_and_tokens(self) -> None:
        engine = AIEngine(model="gpt-4-turbo", max_tokens=512, temperature=0.3)
        self.assertEqual(engine.model, "gpt-4-turbo")
        self.assertEqual(engine.max_tokens, 512)
        self.assertAlmostEqual(engine.temperature, 0.3)

    def test_custom_system_prompt(self) -> None:
        prompt = "You are a test bot."
        engine = AIEngine(system_prompt=prompt)
        self.assertEqual(engine.system_prompt, prompt)

    def test_skill_registry_stored(self) -> None:
        registry = SkillRegistry()
        engine = AIEngine(skill_registry=registry)
        self.assertIs(engine.registry, registry)

    def test_repr(self) -> None:
        engine = AIEngine()
        r = repr(engine)
        self.assertIn("AIEngine", r)
        self.assertIn("model=", r)

    def test_no_client_before_chat(self) -> None:
        engine = AIEngine()
        self.assertIsNone(engine._client)


class TestAIEngineChat(unittest.TestCase):
    """Tests for AIEngine.chat()."""

    def setUp(self) -> None:
        self.engine = AIEngine(
            system_prompt="You are MARS.",
            model="gpt-4o",
            max_history=10,
        )
        # Provide a pre-built mock client so _get_client() doesn't hit OpenAI
        self.mock_client = MagicMock()
        self.engine._client = self.mock_client

    def _configure_response(self, content: str) -> None:
        self.mock_client.chat.completions.create.return_value = _make_chat_response(content)

    def test_chat_returns_string(self) -> None:
        self._configure_response("Hello, sir.")
        result = self.engine.chat("Hello")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "Hello, sir.")

    def test_user_message_added_to_memory(self) -> None:
        self._configure_response("Noted.")
        self.engine.chat("Remember this.")
        history = self.engine.memory.get_history()
        self.assertTrue(any(m["role"] == "user" and "Remember" in m["content"] for m in history))

    def test_assistant_reply_added_to_memory(self) -> None:
        self._configure_response("Done, sir.")
        self.engine.chat("Do something.")
        history = self.engine.memory.get_history()
        self.assertTrue(any(m["role"] == "assistant" and "Done" in m["content"] for m in history))

    def test_system_prompt_included_in_api_call(self) -> None:
        self._configure_response("OK.")
        self.engine.chat("Test.")
        call_kwargs = self.mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0] if call_kwargs.args else []
        if not messages:
            messages = call_kwargs[1].get("messages", [])
        system_msgs = [m for m in messages if m.get("role") == "system"]
        self.assertTrue(len(system_msgs) >= 1)
        self.assertIn("MARS", system_msgs[0]["content"])

    def test_chat_accumulates_history(self) -> None:
        self._configure_response("Reply 1.")
        self.engine.chat("Message 1.")
        self._configure_response("Reply 2.")
        self.engine.chat("Message 2.")
        history = self.engine.memory.get_history()
        self.assertEqual(len(history), 4)  # 2 user + 2 assistant


class TestAIEngineToolCalling(unittest.TestCase):
    """Tests for tool-call handling in AIEngine."""

    def setUp(self) -> None:
        self.registry = SkillRegistry()
        self.registry.register(
            name="get_time",
            func=lambda: "It is 12:00 PM.",
            description="Return the current time.",
        )
        self.engine = AIEngine(skill_registry=self.registry, system_prompt="You are MARS.")
        self.mock_client = MagicMock()
        self.engine._client = self.mock_client

    def test_tool_call_dispatched_to_registry(self) -> None:
        tool_call = _make_tool_call("call_1", "get_time", {})
        first_response = _make_chat_response("", tool_calls=[tool_call])
        second_response = _make_chat_response("It is 12:00 PM, sir.")
        self.mock_client.chat.completions.create.side_effect = [first_response, second_response]

        result = self.engine.chat("What time is it?")
        self.assertEqual(result, "It is 12:00 PM, sir.")
        self.assertEqual(self.mock_client.chat.completions.create.call_count, 2)

    def test_tool_result_message_appended(self) -> None:
        """The tool result should appear as a 'tool' role message in follow-up call."""
        tool_call = _make_tool_call("call_abc", "get_time", {})
        first_response = _make_chat_response("", tool_calls=[tool_call])
        second_response = _make_chat_response("Done.")
        self.mock_client.chat.completions.create.side_effect = [first_response, second_response]

        self.engine.chat("Time please.")
        second_call_kwargs = self.mock_client.chat.completions.create.call_args_list[1]
        messages = second_call_kwargs.kwargs.get("messages", [])
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        self.assertTrue(len(tool_msgs) >= 1)
        self.assertEqual(tool_msgs[0]["tool_call_id"], "call_abc")

    def test_unknown_tool_returns_error_string(self) -> None:
        result = self.engine._execute_tool("nonexistent_skill", "{}")
        self.assertIn("Unknown skill", result)

    def test_build_tools_returns_list(self) -> None:
        tools = self.engine._build_tools()
        self.assertIsInstance(tools, list)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["function"]["name"], "get_time")

    def test_build_tools_empty_without_registry(self) -> None:
        engine_no_reg = AIEngine()
        self.assertEqual(engine_no_reg._build_tools(), [])


class TestAIEngineErrorHandling(unittest.TestCase):
    """Tests for error cases in AIEngine."""

    def setUp(self) -> None:
        self.engine = AIEngine(system_prompt="You are MARS.")
        self.mock_client = MagicMock()
        self.engine._client = self.mock_client

    def test_openai_api_error_returns_graceful_message(self) -> None:
        self.mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        result = self.engine.chat("Hello")
        self.assertIsInstance(result, str)
        self.assertIn("error", result.lower())

    def test_get_client_raises_without_api_key(self) -> None:
        engine = AIEngine()
        engine._client = None  # force lazy init
        with patch.dict(os.environ, {}, clear=True):
            # Remove OPENAI_API_KEY if set
            os.environ.pop("OPENAI_API_KEY", None)
            # Patch the OpenAI import to succeed but key missing
            mock_openai_cls = MagicMock()
            with patch.dict(sys.modules, {"openai": MagicMock(OpenAI=mock_openai_cls)}):
                with self.assertRaises(EnvironmentError):
                    engine._get_client()

    def test_reset_memory_clears_history(self) -> None:
        self.mock_client.chat.completions.create.return_value = _make_chat_response("Hi.")
        self.engine.chat("Hello")
        self.assertGreater(len(self.engine.memory), 0)
        self.engine.reset_memory()
        self.assertEqual(len(self.engine.memory), 0)

    def test_execute_tool_with_invalid_json_args(self) -> None:
        registry = SkillRegistry()
        registry.register("dummy", lambda: "ok", "A dummy skill.")
        engine = AIEngine(skill_registry=registry)
        # Invalid JSON should not crash; args default to {}
        result = engine._execute_tool("dummy", "not-valid-json{{{")
        self.assertIsInstance(result, str)

    def test_follow_up_api_error_returns_graceful_message(self) -> None:
        tool_call = _make_tool_call("call_err", "get_time", {})
        first_response = _make_chat_response("", tool_calls=[tool_call])
        self.mock_client.chat.completions.create.side_effect = [
            first_response,
            Exception("follow-up failure"),
        ]
        registry = SkillRegistry()
        registry.register("get_time", lambda: "12:00", "Time skill.")
        self.engine.registry = registry
        result = self.engine.chat("What time?")
        self.assertIsInstance(result, str)
        self.assertIn("issue", result.lower())


class TestConversationMemoryIntegration(unittest.TestCase):
    """Integration tests: AIEngine × ConversationMemory."""

    def test_memory_trimmed_to_max_history(self) -> None:
        engine = AIEngine(max_history=4, system_prompt="MARS")
        mock_client = MagicMock()
        engine._client = mock_client
        mock_client.chat.completions.create.return_value = _make_chat_response("OK")

        for i in range(5):
            engine.chat(f"Message {i}")

        # Memory should hold at most max_history=4 messages
        self.assertLessEqual(len(engine.memory), 4)

    def test_build_messages_starts_with_system(self) -> None:
        engine = AIEngine(system_prompt="Be helpful.")
        msgs = engine._build_messages()
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[0]["content"], "Be helpful.")


if __name__ == "__main__":
    unittest.main()
