"""
system_control.py — macOS system operations for MARS.

All functions return a ``str`` response that MARS speaks aloud.
Heavy lifting is delegated to :mod:`utils.macos_utils`; this module adds
spoken-friendly wording and safety guards (e.g. ``confirmed`` flags).
"""

from __future__ import annotations

import datetime
import time

import psutil

from utils.logger import get_logger
from utils.macos_utils import (
    empty_trash as _empty_trash,
    get_battery_info,
    get_volume as _get_volume,
    lock_screen as _lock_screen,
    open_app,
    quit_app,
    run_command,
    set_brightness as _set_brightness,
    set_volume as _set_volume,
    sleep_system as _sleep_system,
    toggle_do_not_disturb as _toggle_dnd,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------


def get_system_info() -> str:
    """Return a spoken summary of CPU, RAM, and disk usage.

    Uses :mod:`psutil` to gather live metrics.

    Returns
    -------
    str
        Human-readable system status string.

    Examples
    --------
    >>> get_system_info()
    'CPU usage is 12%, RAM usage is 45% with 7.20 GB free, and disk usage is 60% with 200.00 GB free.'
    """
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        ram_free_gb = ram.available / (1024 ** 3)
        disk_free_gb = disk.free / (1024 ** 3)

        result = (
            f"CPU usage is {cpu:.0f}%, "
            f"RAM usage is {ram.percent:.0f}% with {ram_free_gb:.2f} GB free, "
            f"and disk usage is {disk.percent:.0f}% with {disk_free_gb:.2f} GB free."
        )
        log.info("System info retrieved: %s", result)
        return result
    except Exception as exc:
        log.error("get_system_info failed: %s", exc)
        return f"I was unable to retrieve system info: {exc}"


# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------


def get_battery_status() -> str:
    """Return a spoken description of battery level and charging state.

    Returns
    -------
    str
        E.g. ``"Battery is at 82%, currently charging."``
    """
    try:
        info = get_battery_info()
        if not info.get("present"):
            # psutil fallback for non-macOS or desktops
            battery = psutil.sensors_battery()
            if battery is None:
                return "No battery detected on this system."
            pct = battery.percent
            charging = battery.power_plugged
            secs = battery.secsleft
            if secs not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN) and not charging:
                hours, remainder = divmod(int(secs), 3600)
                mins = remainder // 60
                time_str = f" About {hours} hours and {mins} minutes remaining."
            else:
                time_str = ""
            status = "charging" if charging else "discharging"
            return f"Battery is at {pct:.0f}%, currently {status}.{time_str}"

        pct = info["percentage"]
        charging = info["charging"]
        time_remaining = info.get("time_remaining")

        status = "charging" if charging else "discharging"
        time_str = f" About {time_remaining} remaining." if time_remaining and not charging else ""
        result = f"Battery is at {pct}%, currently {status}.{time_str}"
        log.info("Battery status: %s", result)
        return result
    except Exception as exc:
        log.error("get_battery_status failed: %s", exc)
        return f"I couldn't check the battery status: {exc}"


# ---------------------------------------------------------------------------
# Application control
# ---------------------------------------------------------------------------


def open_application(app_name: str) -> str:
    """Open a macOS application by name.

    Parameters
    ----------
    app_name:
        Application name as recognised by the macOS ``open -a`` command.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        result = open_app(app_name)
        log.info("open_application: %s", result)
        return result
    except Exception as exc:
        log.error("open_application(%r) failed: %s", app_name, exc)
        return f"I couldn't open {app_name}: {exc}"


def close_application(app_name: str) -> str:
    """Quit a running macOS application by name.

    Parameters
    ----------
    app_name:
        Application name as recognised by AppleScript.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        result = quit_app(app_name)
        log.info("close_application: %s", result)
        return result
    except Exception as exc:
        log.error("close_application(%r) failed: %s", app_name, exc)
        return f"I couldn't close {app_name}: {exc}"


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------


def set_volume(level: int) -> str:
    """Set the system output volume.

    Parameters
    ----------
    level:
        Desired volume percentage (0–100). Values outside this range are
        clamped automatically.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        level = max(0, min(100, level))
        result = _set_volume(level)
        log.info("set_volume: %s", result)
        return result
    except Exception as exc:
        log.error("set_volume(%d) failed: %s", level, exc)
        return f"I couldn't set the volume: {exc}"


def get_volume() -> str:
    """Return the current system output volume as a spoken string.

    Returns
    -------
    str
        E.g. ``"The current volume is 50%."``
    """
    try:
        level = _get_volume()
        if level == -1:
            return "I was unable to read the current volume level."
        result = f"The current volume is {level}%."
        log.info("get_volume: %s", result)
        return result
    except Exception as exc:
        log.error("get_volume failed: %s", exc)
        return f"I couldn't get the volume: {exc}"


# ---------------------------------------------------------------------------
# Brightness
# ---------------------------------------------------------------------------


def set_brightness(level: int) -> str:
    """Set the display brightness.

    Parameters
    ----------
    level:
        Desired brightness percentage (0–100).

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        level = max(0, min(100, level))
        result = _set_brightness(level)
        log.info("set_brightness: %s", result)
        return result
    except Exception as exc:
        log.error("set_brightness(%d) failed: %s", level, exc)
        return f"I couldn't set the brightness: {exc}"


# ---------------------------------------------------------------------------
# Lock / Sleep / Restart / Shutdown
# ---------------------------------------------------------------------------


def lock_screen() -> str:
    """Lock the current user session.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        result = _lock_screen()
        log.info("lock_screen: %s", result)
        return result
    except Exception as exc:
        log.error("lock_screen failed: %s", exc)
        return f"I couldn't lock the screen: {exc}"


def sleep_system() -> str:
    """Put the system to sleep immediately.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        result = _sleep_system()
        log.info("sleep_system: %s", result)
        return result
    except Exception as exc:
        log.error("sleep_system failed: %s", exc)
        return f"I couldn't put the system to sleep: {exc}"


def restart_system(confirmed: bool = False) -> str:
    """Restart the system.

    Parameters
    ----------
    confirmed:
        Must be ``True`` to proceed.  Acts as a safety guard against
        accidental restarts.

    Returns
    -------
    str
        Spoken confirmation or safety warning.
    """
    if not confirmed:
        return "Restart requires confirmation. Please confirm that you want to restart the system."
    try:
        log.warning("Restarting system as requested.")
        run_command(["osascript", "-e", 'tell application "Finder" to restart'])
        return "Restarting the system now. See you on the other side, sir."
    except Exception as exc:
        log.error("restart_system failed: %s", exc)
        return f"I couldn't restart the system: {exc}"


def shutdown_system(confirmed: bool = False) -> str:
    """Shut down the system.

    Parameters
    ----------
    confirmed:
        Must be ``True`` to proceed.  Acts as a safety guard.

    Returns
    -------
    str
        Spoken confirmation or safety warning.
    """
    if not confirmed:
        return "Shutdown requires confirmation. Please confirm that you want to shut down the system."
    try:
        log.warning("Shutting down system as requested.")
        run_command(["osascript", "-e", 'tell application "Finder" to shut down'])
        return "Shutting down the system. Goodbye, sir."
    except Exception as exc:
        log.error("shutdown_system failed: %s", exc)
        return f"I couldn't shut down the system: {exc}"


# ---------------------------------------------------------------------------
# Trash
# ---------------------------------------------------------------------------


def empty_trash(confirmed: bool = False) -> str:
    """Empty the macOS Trash.

    Parameters
    ----------
    confirmed:
        Must be ``True`` to proceed.

    Returns
    -------
    str
        Spoken confirmation or safety warning.
    """
    if not confirmed:
        return "Emptying the trash requires confirmation. Please confirm to proceed."
    try:
        result = _empty_trash()
        log.info("empty_trash: %s", result)
        return result
    except Exception as exc:
        log.error("empty_trash failed: %s", exc)
        return f"I couldn't empty the trash: {exc}"


# ---------------------------------------------------------------------------
# Do Not Disturb
# ---------------------------------------------------------------------------


def toggle_do_not_disturb(enable: bool) -> str:
    """Enable or disable Do Not Disturb / Focus mode.

    Parameters
    ----------
    enable:
        ``True`` to enable, ``False`` to disable.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    try:
        result = _toggle_dnd(enable)
        log.info("toggle_do_not_disturb(enable=%s): %s", enable, result)
        return result
    except Exception as exc:
        log.error("toggle_do_not_disturb failed: %s", exc)
        return f"I couldn't toggle Do Not Disturb: {exc}"


# ---------------------------------------------------------------------------
# Uptime
# ---------------------------------------------------------------------------


def get_uptime() -> str:
    """Return the system uptime as a human-readable spoken string.

    Returns
    -------
    str
        E.g. ``"The system has been running for 3 hours and 27 minutes."``
    """
    try:
        boot_timestamp = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_timestamp)
        uptime_delta = datetime.timedelta(seconds=uptime_seconds)

        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes = remainder // 60

        parts: list[str] = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes or not parts:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

        uptime_str = " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + f", and {parts[-1]}"
        result = f"The system has been running for {uptime_str}."
        log.info("get_uptime: %s", result)
        return result
    except Exception as exc:
        log.error("get_uptime failed: %s", exc)
        return f"I couldn't determine the system uptime: {exc}"
