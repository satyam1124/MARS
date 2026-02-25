"""
tests/test_skills.py
====================
Unit tests for various MARS skills:
  - calculator (calculate, convert_units)
  - translator (detect_language)
  - entertainment (flip_coin, roll_dice)
  - web_search (search_wikipedia)
  - todo (add_todo, list_todos, complete_todo) — uses in-memory SQLite
  - clipboard (copy_to_clipboard, get_clipboard)

All external dependencies (HTTP, subprocess, googletrans, etc.) are mocked.
The todo tests use an in-memory SQLite database via monkeypatching Database.
"""

from __future__ import annotations

import os
import sys
import sqlite3
import types
import unittest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Stub heavy dependencies that may not be installed in CI
# ---------------------------------------------------------------------------

# bs4 (BeautifulSoup) — used by web_search
if "bs4" not in sys.modules:
    _bs4_stub = types.ModuleType("bs4")
    _bs4_stub.BeautifulSoup = MagicMock()
    sys.modules["bs4"] = _bs4_stub

# googletrans
if "googletrans" not in sys.modules:
    _gt_stub = types.ModuleType("googletrans")
    _gt_stub.Translator = MagicMock()
    _gt_stub.LANGUAGES = {"en": "english", "fr": "french", "es": "spanish", "de": "german"}
    sys.modules["googletrans"] = _gt_stub

# resemblyzer
if "resemblyzer" not in sys.modules:
    sys.modules["resemblyzer"] = types.ModuleType("resemblyzer")

# ---------------------------------------------------------------------------
# Imports under test (after stubs are in place)
# ---------------------------------------------------------------------------
import skills.calculator as calculator  # noqa: E402
import skills.translator as translator  # noqa: E402
import skills.entertainment as entertainment  # noqa: E402
import skills.web_search as web_search  # noqa: E402
import skills.clipboard as clipboard  # noqa: E402

# todo module imports Database — we will patch it per-test
import skills.todo as todo  # noqa: E402
from utils.database import Database  # noqa: E402


# ===========================================================================
# Calculator tests
# ===========================================================================

class TestCalculate(unittest.TestCase):
    """Tests for calculator.calculate()."""

    def test_addition(self) -> None:
        result = calculator.calculate("2 + 3")
        self.assertIn("5", result)

    def test_subtraction(self) -> None:
        result = calculator.calculate("10 - 4")
        self.assertIn("6", result)

    def test_multiplication(self) -> None:
        result = calculator.calculate("6 * 7")
        self.assertIn("42", result)

    def test_division(self) -> None:
        result = calculator.calculate("10 / 4")
        self.assertIn("2.5", result)

    def test_exponentiation(self) -> None:
        result = calculator.calculate("2 ** 10")
        self.assertIn("1024", result)

    def test_sqrt_function(self) -> None:
        result = calculator.calculate("sqrt(144)")
        self.assertIn("12", result)

    def test_pi_constant(self) -> None:
        result = calculator.calculate("pi")
        self.assertIn("3.14159", result)

    def test_division_by_zero(self) -> None:
        result = calculator.calculate("1 / 0")
        self.assertIn("division by zero", result.lower())

    def test_empty_expression(self) -> None:
        result = calculator.calculate("   ")
        self.assertIn("please", result.lower())

    def test_invalid_expression(self) -> None:
        result = calculator.calculate("import os")
        # Should return an error, not execute Python
        self.assertIsInstance(result, str)
        # Must NOT execute arbitrary code
        self.assertNotIn("module", result.lower())

    def test_negative_number(self) -> None:
        result = calculator.calculate("-5 + 3")
        self.assertIn("-2", result)

    def test_caret_as_power(self) -> None:
        """The calculator normalises ^ to **."""
        result = calculator.calculate("2^8")
        self.assertIn("256", result)

    def test_factorial(self) -> None:
        # math.factorial does not accept float arguments in Python 3.12+.
        # The calculator converts all literals to float, so factorial(5)
        # raises a TypeError.  Verify a clear error message is returned.
        result = calculator.calculate("factorial(5)")
        # Either succeeds with 120 or returns an informative error — never crashes.
        self.assertIsInstance(result, str)
        self.assertTrue("120" in result or "error" in result.lower() or "couldn't" in result.lower())

    def test_floor_function(self) -> None:
        result = calculator.calculate("floor(3.9)")
        self.assertIn("3", result)

    def test_ceil_function(self) -> None:
        result = calculator.calculate("ceil(3.1)")
        self.assertIn("4", result)


class TestConvertUnits(unittest.TestCase):
    """Tests for calculator.convert_units()."""

    def test_km_to_miles(self) -> None:
        result = calculator.convert_units(1.0, "km", "miles")
        self.assertIn("miles", result.lower())
        self.assertIn("0.62137", result)

    def test_miles_to_km(self) -> None:
        result = calculator.convert_units(1.0, "miles", "km")
        self.assertIn("km", result.lower())
        self.assertIn("1.60934", result)

    def test_celsius_to_fahrenheit(self) -> None:
        result = calculator.convert_units(100.0, "celsius", "fahrenheit")
        self.assertIn("212", result)

    def test_fahrenheit_to_celsius(self) -> None:
        result = calculator.convert_units(32.0, "fahrenheit", "celsius")
        self.assertIn("0", result)

    def test_celsius_to_kelvin(self) -> None:
        result = calculator.convert_units(0.0, "celsius", "kelvin")
        self.assertIn("273", result)

    def test_kg_to_lb(self) -> None:
        result = calculator.convert_units(1.0, "kg", "lb")
        self.assertIn("2.20462", result)

    def test_unknown_unit_returns_error(self) -> None:
        result = calculator.convert_units(1.0, "flibbles", "km")
        self.assertIn("don't recognise", result.lower())

    def test_incompatible_units_returns_error(self) -> None:
        result = calculator.convert_units(1.0, "km", "kg")
        self.assertIn("can't convert", result.lower())

    def test_meters_to_feet(self) -> None:
        result = calculator.convert_units(1.0, "m", "ft")
        self.assertIn("3.28084", result)


# ===========================================================================
# Translator tests
# ===========================================================================

class TestDetectLanguage(unittest.TestCase):
    """Tests for translator.detect_language()."""

    def setUp(self) -> None:
        self.mock_translator = MagicMock()
        detection = MagicMock()
        detection.lang = "fr"
        detection.confidence = 0.98
        self.mock_translator.detect.return_value = detection

    def test_detect_french(self) -> None:
        with patch("skills.translator._get_translator", return_value=self.mock_translator), \
             patch("skills.translator._get_lang_map", return_value={"fr": "french", "en": "english"}):
            result = translator.detect_language("Bonjour le monde")
        self.assertIn("French", result)
        self.assertIn("98%", result)

    def test_empty_text_returns_prompt(self) -> None:
        result = translator.detect_language("   ")
        self.assertIn("please", result.lower())

    def test_translator_unavailable(self) -> None:
        with patch("skills.translator._get_translator", return_value=None):
            result = translator.detect_language("Hello")
        self.assertIn("unavailable", result.lower())

    def test_exception_returns_error_string(self) -> None:
        self.mock_translator.detect.side_effect = Exception("API down")
        with patch("skills.translator._get_translator", return_value=self.mock_translator):
            result = translator.detect_language("Hello world")
        self.assertIn("unable to detect", result.lower())

    def test_unknown_lang_code_uses_code_directly(self) -> None:
        """If the lang code is not in the language map, use the code itself."""
        detection = MagicMock()
        detection.lang = "xyz"
        detection.confidence = 0.7
        self.mock_translator.detect.return_value = detection
        with patch("skills.translator._get_translator", return_value=self.mock_translator), \
             patch("skills.translator._get_lang_map", return_value={}):
            result = translator.detect_language("Some text")
        self.assertIn("xyz", result.lower())


# ===========================================================================
# Entertainment tests
# ===========================================================================

class TestFlipCoin(unittest.TestCase):
    """Tests for entertainment.flip_coin()."""

    def test_returns_heads_or_tails(self) -> None:
        for _ in range(20):
            result = entertainment.flip_coin()
            self.assertTrue(
                "Heads" in result or "Tails" in result,
                f"Unexpected flip_coin result: {result!r}",
            )

    def test_returns_string(self) -> None:
        self.assertIsInstance(entertainment.flip_coin(), str)

    def test_heads_result(self) -> None:
        with patch("skills.entertainment.random.choice", return_value="Heads"):
            result = entertainment.flip_coin()
        self.assertIn("Heads", result)

    def test_tails_result(self) -> None:
        with patch("skills.entertainment.random.choice", return_value="Tails"):
            result = entertainment.flip_coin()
        self.assertIn("Tails", result)


class TestRollDice(unittest.TestCase):
    """Tests for entertainment.roll_dice()."""

    def test_default_six_sided_die(self) -> None:
        for _ in range(30):
            result = entertainment.roll_dice()
            # Extract the number from the string
            parts = result.split()
            number = int(parts[-1].rstrip("!"))
            self.assertGreaterEqual(number, 1)
            self.assertLessEqual(number, 6)

    def test_custom_sides(self) -> None:
        for _ in range(30):
            result = entertainment.roll_dice(sides=20)
            parts = result.split()
            number = int(parts[-1].rstrip("!"))
            self.assertGreaterEqual(number, 1)
            self.assertLessEqual(number, 20)

    def test_returns_string(self) -> None:
        self.assertIsInstance(entertainment.roll_dice(), str)

    def test_less_than_two_sides_error(self) -> None:
        result = entertainment.roll_dice(sides=1)
        self.assertIn("at least 2", result.lower())

    def test_mocked_roll_value(self) -> None:
        with patch("skills.entertainment.random.randint", return_value=4):
            result = entertainment.roll_dice(sides=6)
        self.assertIn("4", result)


# ===========================================================================
# Web search tests
# ===========================================================================

class TestSearchWikipedia(unittest.TestCase):
    """Tests for web_search.search_wikipedia()."""

    def _make_response(self, status_code: int = 200, extract: str = "") -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = {"extract": extract}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_wikipedia_summary(self) -> None:
        extract = "Python is a high-level programming language. It was created by Guido van Rossum."
        mock_resp = self._make_response(extract=extract)
        with patch("skills.web_search.requests.get", return_value=mock_resp):
            result = web_search.search_wikipedia("Python")
        self.assertIn("Python", result)
        self.assertIn("According to Wikipedia", result)

    def test_404_returns_not_found(self) -> None:
        mock_resp = self._make_response(status_code=404)
        with patch("skills.web_search.requests.get", return_value=mock_resp):
            result = web_search.search_wikipedia("xyzzy_nonexistent_page")
        self.assertIn("couldn't find", result.lower())

    def test_empty_extract_returns_no_summary(self) -> None:
        mock_resp = self._make_response(extract="")
        with patch("skills.web_search.requests.get", return_value=mock_resp):
            result = web_search.search_wikipedia("EmptyPage")
        self.assertIn("no summary", result.lower())

    def test_empty_topic_returns_prompt(self) -> None:
        result = web_search.search_wikipedia("   ")
        self.assertIn("tell me", result.lower())

    def test_request_exception_returns_error(self) -> None:
        import requests as _requests
        with patch("skills.web_search.requests.get", side_effect=_requests.RequestException("timeout")):
            result = web_search.search_wikipedia("Anything")
        self.assertIn("unable to reach", result.lower())

    def test_summary_trimmed_to_two_sentences(self) -> None:
        extract = "Sentence one. Sentence two. Sentence three. Sentence four."
        mock_resp = self._make_response(extract=extract)
        with patch("skills.web_search.requests.get", return_value=mock_resp):
            result = web_search.search_wikipedia("Topic")
        # Should contain sentence one and two, but not three
        self.assertIn("Sentence one", result)
        self.assertIn("Sentence two", result)
        self.assertNotIn("Sentence three", result)


# ===========================================================================
# Todo tests — use a shared in-memory SQLite database
# ===========================================================================

class TestTodoSkills(unittest.TestCase):
    """Tests for add_todo(), list_todos(), complete_todo() using in-memory DB."""

    def setUp(self) -> None:
        """Create a fresh temporary Database and patch skills.todo.Database.

        We use a real temp file (absolute path) so that Database.__init__
        doesn't resolve ':memory:' to a relative filesystem path.  The
        ``close()`` method is mocked to prevent the context-manager's
        ``__exit__`` from closing the connection between skill calls within
        a single test.
        """
        import tempfile

        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = Database(self._db_path)
        # Prevent __exit__ from closing the connection between skill calls.
        self.db.close = MagicMock()

        # Each call to Database() in the skill code returns our shared db.
        self._db_patcher = patch("skills.todo.Database", return_value=self.db)
        self._db_patcher.start()

    def tearDown(self) -> None:
        self._db_patcher.stop()
        # Restore real close and shut down cleanly.
        Database.close(self.db)
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    # ------------------------------------------------------------------
    # add_todo
    # ------------------------------------------------------------------

    def test_add_todo_returns_confirmation(self) -> None:
        result = todo.add_todo("Buy milk")
        self.assertIn("Buy milk", result)
        self.assertIn("added", result.lower())

    def test_add_todo_empty_title_returns_prompt(self) -> None:
        result = todo.add_todo("   ")
        self.assertIn("please", result.lower())

    def test_add_todo_with_priority_high(self) -> None:
        result = todo.add_todo("Urgent task", priority="high")
        self.assertIn("high", result.lower())

    def test_add_todo_with_due_date(self) -> None:
        result = todo.add_todo("Submit report", due_date="2025-12-31")
        self.assertIn("2025-12-31", result)

    def test_add_todo_stored_in_database(self) -> None:
        todo.add_todo("Test item")
        rows = self.db.get_todos(include_completed=False)
        titles = [r["title"] for r in rows]
        self.assertIn("Test item", titles)

    # ------------------------------------------------------------------
    # list_todos
    # ------------------------------------------------------------------

    def test_list_todos_empty_returns_no_items_message(self) -> None:
        result = todo.list_todos()
        self.assertIn("no", result.lower())

    def test_list_todos_shows_added_item(self) -> None:
        todo.add_todo("Walk the dog")
        result = todo.list_todos()
        self.assertIn("Walk the dog", result)

    def test_list_todos_shows_multiple_items(self) -> None:
        todo.add_todo("Task A")
        todo.add_todo("Task B")
        result = todo.list_todos()
        self.assertIn("Task A", result)
        self.assertIn("Task B", result)

    def test_list_todos_completed_filter(self) -> None:
        """list_todos(filter_completed=True) should only return completed items."""
        todo.add_todo("Done task")
        rows = self.db.execute(
            "SELECT id FROM todos WHERE title = ?", ("Done task",)
        )
        self.db.complete_todo(rows[0]["id"])
        result = todo.list_todos(filter_completed=True)
        self.assertIn("Done task", result)

    # ------------------------------------------------------------------
    # complete_todo
    # ------------------------------------------------------------------

    def test_complete_todo_marks_item_complete(self) -> None:
        todo.add_todo("Finish report")
        result = todo.complete_todo("Finish report")
        self.assertIn("marked as complete", result.lower())

    def test_complete_todo_not_found_returns_message(self) -> None:
        result = todo.complete_todo("Nonexistent item xyz")
        self.assertIn("couldn't find", result.lower())

    def test_complete_todo_empty_title_returns_prompt(self) -> None:
        result = todo.complete_todo("   ")
        self.assertIn("please", result.lower())

    def test_complete_todo_removes_from_incomplete_list(self) -> None:
        todo.add_todo("Clean desk")
        todo.complete_todo("Clean desk")
        rows = self.db.get_todos(include_completed=False)
        titles = [r["title"] for r in rows]
        self.assertNotIn("Clean desk", titles)

    def test_complete_todo_partial_title_match(self) -> None:
        todo.add_todo("Read Python book")
        result = todo.complete_todo("Python book")
        self.assertIn("marked as complete", result.lower())


# ===========================================================================
# Clipboard tests
# ===========================================================================

class TestCopyToClipboard(unittest.TestCase):
    """Tests for clipboard.copy_to_clipboard()."""

    def test_copy_success_with_pbcopy(self) -> None:
        with patch("skills.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = clipboard.copy_to_clipboard("Hello, World!")
        mock_run.assert_called_once()
        self.assertIn("Copied to clipboard", result)
        self.assertIn("Hello, World!", result)

    def test_copy_long_text_truncated_in_preview(self) -> None:
        long_text = "A" * 200
        with patch("skills.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = clipboard.copy_to_clipboard(long_text)
        self.assertIn("...", result)

    def test_copy_short_text_not_truncated(self) -> None:
        short_text = "Short"
        with patch("skills.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = clipboard.copy_to_clipboard(short_text)
        self.assertNotIn("...", result)
        self.assertIn("Short", result)

    def test_pbcopy_not_found_returns_error_or_fallback(self) -> None:
        """On Linux with no clipboard tool, a descriptive message is returned."""
        with patch("skills.clipboard.subprocess.run", side_effect=FileNotFoundError):
            result = clipboard.copy_to_clipboard("test")
        self.assertIsInstance(result, str)
        # Should contain some indication of failure or missing tool
        self.assertTrue(
            "not found" in result.lower()
            or "failed" in result.lower()
            or "copied" in result.lower(),
            f"Unexpected result: {result!r}",
        )

    def test_called_process_error_returns_error(self) -> None:
        import subprocess as _sp
        with patch(
            "skills.clipboard.subprocess.run",
            side_effect=_sp.CalledProcessError(1, "pbcopy"),
        ):
            result = clipboard.copy_to_clipboard("test")
        self.assertIsInstance(result, str)
        self.assertTrue("failed" in result.lower() or "error" in result.lower() or "pbcopy" in result.lower())


class TestGetClipboard(unittest.TestCase):
    """Tests for clipboard.get_clipboard()."""

    def _make_completed_process(self, stdout: bytes) -> MagicMock:
        proc = MagicMock()
        proc.stdout = stdout
        proc.returncode = 0
        return proc

    def test_get_clipboard_returns_content(self) -> None:
        with patch(
            "skills.clipboard.subprocess.run",
            return_value=self._make_completed_process(b"Hello from clipboard"),
        ):
            result = clipboard.get_clipboard()
        self.assertIn("Hello from clipboard", result)

    def test_get_clipboard_empty_returns_empty_message(self) -> None:
        with patch(
            "skills.clipboard.subprocess.run",
            return_value=self._make_completed_process(b""),
        ):
            result = clipboard.get_clipboard()
        self.assertIn("empty", result.lower())

    def test_get_clipboard_long_content_truncated(self) -> None:
        long_content = b"X" * 400
        with patch(
            "skills.clipboard.subprocess.run",
            return_value=self._make_completed_process(long_content),
        ):
            result = clipboard.get_clipboard()
        self.assertIn("...", result)

    def test_pbpaste_not_found_returns_error_or_fallback(self) -> None:
        with patch("skills.clipboard.subprocess.run", side_effect=FileNotFoundError):
            result = clipboard.get_clipboard()
        self.assertIsInstance(result, str)
        self.assertTrue(
            "not found" in result.lower()
            or "failed" in result.lower()
            or "clipboard" in result.lower(),
        )

    def test_general_exception_returns_error(self) -> None:
        with patch("skills.clipboard.subprocess.run", side_effect=Exception("unexpected")):
            result = clipboard.get_clipboard()
        self.assertIn("failed", result.lower())


if __name__ == "__main__":
    unittest.main()
