"""
tests/test_system_control.py
============================
Unit tests for skills/system_control.py.

All psutil and macos_utils calls are mocked so no real hardware or
macOS-specific tooling is required.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path
# ---------------------------------------------------------------------------
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Stub heavy / macOS-only dependencies before importing the module under test
# ---------------------------------------------------------------------------

# Stub macos_utils so the import of system_control doesn't require macOS
_macos_stub = types.ModuleType("utils.macos_utils")
_macos_stub.get_battery_info = MagicMock(return_value={"present": False})
_macos_stub.get_volume = MagicMock(return_value=50)
_macos_stub.open_app = MagicMock(return_value="Safari opened.")
_macos_stub.quit_app = MagicMock(return_value="Safari closed.")
_macos_stub.run_command = MagicMock(return_value=(0, "", ""))
_macos_stub.set_brightness = MagicMock(return_value="Brightness set to 80%.")
_macos_stub.set_volume = MagicMock(return_value="Volume set to 50%.")
_macos_stub.lock_screen = MagicMock(return_value="Screen locked.")
_macos_stub.sleep_system = MagicMock(return_value="Going to sleep.")
_macos_stub.toggle_do_not_disturb = MagicMock(return_value="Do Not Disturb enabled.")
_macos_stub.empty_trash = MagicMock(return_value="Trash emptied.")
sys.modules.setdefault("utils.macos_utils", _macos_stub)

# Stub resemblyzer (used transitively by some modules)
_resemblyzer_stub = types.ModuleType("resemblyzer")
sys.modules.setdefault("resemblyzer", _resemblyzer_stub)

import skills.system_control as sc  # noqa: E402  (import after path setup)


class TestGetSystemInfo(unittest.TestCase):
    """Tests for get_system_info()."""

    def setUp(self) -> None:
        self.cpu_patcher = patch("skills.system_control.psutil.cpu_percent", return_value=12.0)
        self.vm_patcher = patch(
            "skills.system_control.psutil.virtual_memory",
            return_value=MagicMock(percent=45.0, available=7 * 1024 ** 3),
        )
        self.disk_patcher = patch(
            "skills.system_control.psutil.disk_usage",
            return_value=MagicMock(percent=60.0, free=200 * 1024 ** 3),
        )
        self.mock_cpu = self.cpu_patcher.start()
        self.mock_vm = self.vm_patcher.start()
        self.mock_disk = self.disk_patcher.start()

    def tearDown(self) -> None:
        self.cpu_patcher.stop()
        self.vm_patcher.stop()
        self.disk_patcher.stop()

    def test_returns_string(self) -> None:
        result = sc.get_system_info()
        self.assertIsInstance(result, str)

    def test_contains_cpu_info(self) -> None:
        result = sc.get_system_info()
        self.assertIn("CPU", result)
        self.assertIn("12%", result)

    def test_contains_ram_info(self) -> None:
        result = sc.get_system_info()
        self.assertIn("RAM", result)
        self.assertIn("45%", result)
        self.assertIn("7.00 GB", result)

    def test_contains_disk_info(self) -> None:
        result = sc.get_system_info()
        self.assertIn("disk", result.lower())
        self.assertIn("60%", result)
        self.assertIn("200.00 GB", result)

    def test_exception_returns_error_string(self) -> None:
        with patch("skills.system_control.psutil.cpu_percent", side_effect=RuntimeError("fail")):
            result = sc.get_system_info()
        self.assertIn("unable to retrieve", result.lower())


class TestGetBatteryStatus(unittest.TestCase):
    """Tests for get_battery_status()."""

    def _make_battery(
        self,
        percent: float = 82.0,
        power_plugged: bool = True,
        secsleft: int = -1,
    ) -> MagicMock:
        import psutil as _psutil

        battery = MagicMock()
        battery.percent = percent
        battery.power_plugged = power_plugged
        battery.secsleft = secsleft if secsleft >= 0 else _psutil.POWER_TIME_UNLIMITED
        return battery

    def test_charging(self) -> None:
        battery = self._make_battery(percent=82.0, power_plugged=True)
        # Patch the name bound inside system_control (post-import local reference)
        with patch("skills.system_control.get_battery_info", return_value={"present": False}), \
             patch("skills.system_control.psutil.sensors_battery", return_value=battery):
            result = sc.get_battery_status()
        self.assertIn("82%", result)
        self.assertIn("charging", result.lower())

    def test_discharging_with_time_remaining(self) -> None:
        battery = self._make_battery(percent=55.0, power_plugged=False, secsleft=5400)
        battery.secsleft = 5400  # 1h 30m
        with patch("skills.system_control.get_battery_info", return_value={"present": False}), \
             patch("skills.system_control.psutil.sensors_battery", return_value=battery):
            result = sc.get_battery_status()
        self.assertIn("55%", result)
        self.assertIn("discharging", result.lower())
        self.assertIn("1 hours", result)
        self.assertIn("30 minutes", result)

    def test_no_battery_detected(self) -> None:
        with patch("skills.system_control.get_battery_info", return_value={"present": False}), \
             patch("skills.system_control.psutil.sensors_battery", return_value=None):
            result = sc.get_battery_status()
        self.assertIn("no battery", result.lower())

    def test_exception_returns_error_string(self) -> None:
        with patch("skills.system_control.get_battery_info", side_effect=Exception("boom")):
            result = sc.get_battery_status()
        self.assertIn("couldn't check", result.lower())

    def test_macos_battery_present(self) -> None:
        mac_info = {
            "present": True,
            "percentage": 90,
            "charging": True,
            "time_remaining": None,
        }
        with patch("skills.system_control.get_battery_info", return_value=mac_info):
            result = sc.get_battery_status()
        self.assertIn("90%", result)
        self.assertIn("charging", result.lower())


class TestOpenApplication(unittest.TestCase):
    """Tests for open_application()."""

    def test_calls_open_app_and_returns_result(self) -> None:
        with patch("skills.system_control.open_app", return_value="Safari opened.") as mock_open:
            result = sc.open_application("Safari")
        mock_open.assert_called_once_with("Safari")
        self.assertEqual(result, "Safari opened.")

    def test_exception_returns_error_string(self) -> None:
        with patch("skills.system_control.open_app", side_effect=RuntimeError("not macOS")):
            result = sc.open_application("Safari")
        self.assertIn("couldn't open", result.lower())
        self.assertIn("Safari", result)


class TestSetVolume(unittest.TestCase):
    """Tests for set_volume()."""

    def test_normal_value(self) -> None:
        with patch("skills.system_control._set_volume", return_value="Volume set to 50%.") as mock_sv:
            result = sc.set_volume(50)
        mock_sv.assert_called_once_with(50)
        self.assertIn("50%", result)

    def test_clamps_below_zero(self) -> None:
        with patch("skills.system_control._set_volume", return_value="Volume set to 0%.") as mock_sv:
            sc.set_volume(-10)
        mock_sv.assert_called_once_with(0)

    def test_clamps_above_100(self) -> None:
        with patch("skills.system_control._set_volume", return_value="Volume set to 100%.") as mock_sv:
            sc.set_volume(150)
        mock_sv.assert_called_once_with(100)

    def test_boundary_zero(self) -> None:
        with patch("skills.system_control._set_volume", return_value="Volume set to 0%.") as mock_sv:
            sc.set_volume(0)
        mock_sv.assert_called_once_with(0)

    def test_boundary_100(self) -> None:
        with patch("skills.system_control._set_volume", return_value="Volume set to 100%.") as mock_sv:
            sc.set_volume(100)
        mock_sv.assert_called_once_with(100)

    def test_exception_returns_error_string(self) -> None:
        with patch("skills.system_control._set_volume", side_effect=OSError("no audio")):
            result = sc.set_volume(50)
        self.assertIn("couldn't set the volume", result.lower())


class TestRestartSystem(unittest.TestCase):
    """Tests for restart_system()."""

    def test_without_confirmation_returns_warning(self) -> None:
        result = sc.restart_system()
        self.assertIn("confirmation", result.lower())
        self.assertNotIn("restarting", result.lower())

    def test_confirmed_calls_run_command(self) -> None:
        with patch("skills.system_control.run_command", return_value=(0, "", "")) as mock_rc:
            result = sc.restart_system(confirmed=True)
        mock_rc.assert_called_once()
        self.assertIn("restarting", result.lower())

    def test_confirmed_false_explicitly(self) -> None:
        result = sc.restart_system(confirmed=False)
        self.assertIn("confirmation", result.lower())

    def test_exception_on_confirmed_returns_error(self) -> None:
        with patch("skills.system_control.run_command", side_effect=OSError("no osascript")):
            result = sc.restart_system(confirmed=True)
        self.assertIn("couldn't restart", result.lower())


class TestGetUptime(unittest.TestCase):
    """Tests for get_uptime()."""

    def test_returns_string_with_uptime(self) -> None:
        import time

        # Mock boot time to 3 hours and 27 minutes ago
        seconds_ago = 3 * 3600 + 27 * 60
        fake_boot_time = time.time() - seconds_ago
        with patch("skills.system_control.psutil.boot_time", return_value=fake_boot_time):
            result = sc.get_uptime()
        self.assertIsInstance(result, str)
        self.assertIn("3 hours", result)
        self.assertIn("27 minutes", result)

    def test_uptime_with_days(self) -> None:
        import time

        seconds_ago = 2 * 86400 + 5 * 3600 + 10 * 60  # 2 days, 5 hours, 10 min
        fake_boot_time = time.time() - seconds_ago
        with patch("skills.system_control.psutil.boot_time", return_value=fake_boot_time):
            result = sc.get_uptime()
        self.assertIn("2 days", result)
        self.assertIn("5 hours", result)
        self.assertIn("10 minutes", result)

    def test_uptime_singular_forms(self) -> None:
        import time

        seconds_ago = 1 * 3600 + 1 * 60  # 1 hour 1 min
        fake_boot_time = time.time() - seconds_ago
        with patch("skills.system_control.psutil.boot_time", return_value=fake_boot_time):
            result = sc.get_uptime()
        # Should use singular "hour" and "minute"
        self.assertIn("1 hour", result)
        self.assertIn("1 minute", result)
        # Ensure no accidental pluralisation
        self.assertNotIn("1 hours", result)
        self.assertNotIn("1 minutes", result)

    def test_exception_returns_error_string(self) -> None:
        with patch("skills.system_control.psutil.boot_time", side_effect=RuntimeError("fail")):
            result = sc.get_uptime()
        self.assertIn("couldn't determine", result.lower())


class TestToggleDoNotDisturb(unittest.TestCase):
    """Tests for toggle_do_not_disturb()."""

    def test_enable_calls_toggle_dnd_true(self) -> None:
        with patch("skills.system_control._toggle_dnd", return_value="Do Not Disturb enabled.") as mock_dnd:
            result = sc.toggle_do_not_disturb(enable=True)
        mock_dnd.assert_called_once_with(True)
        self.assertEqual(result, "Do Not Disturb enabled.")

    def test_disable_calls_toggle_dnd_false(self) -> None:
        with patch("skills.system_control._toggle_dnd", return_value="Do Not Disturb disabled.") as mock_dnd:
            result = sc.toggle_do_not_disturb(enable=False)
        mock_dnd.assert_called_once_with(False)
        self.assertEqual(result, "Do Not Disturb disabled.")

    def test_exception_returns_error_string(self) -> None:
        with patch("skills.system_control._toggle_dnd", side_effect=RuntimeError("not macOS")):
            result = sc.toggle_do_not_disturb(enable=True)
        self.assertIn("couldn't toggle", result.lower())


if __name__ == "__main__":
    unittest.main()
