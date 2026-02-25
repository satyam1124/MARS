"""
macos_utils.py — macOS-specific system utilities for MARS.

All functions target macOS and rely on ``osascript`` / ``AppleScript``,
standard UNIX tools, and ``system_profiler``.  They degrade gracefully on
non-macOS platforms by raising :class:`RuntimeError` where appropriate.

Functions
---------
run_applescript        : Execute an AppleScript snippet and return stdout.
run_command            : Run an arbitrary shell command, optionally capturing output.
get_running_apps       : List names of currently running macOS applications.
is_app_running         : Check whether a named application is currently running.
open_app               : Launch an application by name.
quit_app               : Quit an application by name.
set_volume             : Set the system output volume (0–100).
get_volume             : Return the current system output volume.
set_brightness         : Set display brightness (0–100) via osascript.
lock_screen            : Lock the current user session.
sleep_system           : Put the system to sleep immediately.
get_battery_info       : Return a dict with battery status information.
toggle_do_not_disturb  : Enable or disable Focus / Do Not Disturb mode.
empty_trash            : Empty the macOS Trash.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Union

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_macos(func_name: str) -> None:
    """Raise :class:`RuntimeError` when not running on macOS."""
    if sys.platform != "darwin":
        raise RuntimeError(
            f"{func_name}() is only supported on macOS (detected platform: {sys.platform!r})"
        )


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------


def run_command(
    cmd: Union[str, list[str]],
    capture: bool = True,
) -> tuple[int, str, str]:
    """Execute a shell command and return *(returncode, stdout, stderr)*.

    Parameters
    ----------
    cmd:
        Command string (run via ``shell=True``) **or** a list of tokens
        (run directly without a shell).
    capture:
        When ``True`` (default) stdout and stderr are captured and returned
        as strings.  When ``False`` they inherit the parent process's streams
        and empty strings are returned.

    Returns
    -------
    tuple[int, str, str]
        *(returncode, stdout, stderr)* — all whitespace is stripped from the
        captured strings.

    Examples
    --------
    >>> rc, out, err = run_command(["echo", "hello"])
    >>> rc, out
    (0, 'hello')
    """
    use_shell = isinstance(cmd, str)
    if capture:
        result = subprocess.run(
            cmd,
            shell=use_shell,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    else:
        result = subprocess.run(cmd, shell=use_shell)
        return result.returncode, "", ""


# ---------------------------------------------------------------------------
# run_applescript
# ---------------------------------------------------------------------------


def run_applescript(script: str) -> str:
    """Execute an AppleScript *script* via ``osascript`` and return its output.

    Parameters
    ----------
    script:
        Multi-line AppleScript source code.

    Returns
    -------
    str
        Standard output produced by the script (whitespace-stripped).

    Raises
    ------
    RuntimeError
        If ``osascript`` exits with a non-zero return code.

    Examples
    --------
    >>> run_applescript('return "hello from AppleScript"')
    'hello from AppleScript'
    """
    _require_macos("run_applescript")
    rc, stdout, stderr = run_command(["osascript", "-e", script])
    if rc != 0:
        raise RuntimeError(f"AppleScript error (rc={rc}): {stderr}")
    return stdout


# ---------------------------------------------------------------------------
# get_running_apps / is_app_running
# ---------------------------------------------------------------------------


def get_running_apps() -> list[str]:
    """Return a list of names of all currently running macOS applications.

    Uses AppleScript to query the ``System Events`` process list so that
    both GUI apps and background agents are included.

    Returns
    -------
    list[str]
        Sorted list of application names (may include background agents).
    """
    _require_macos("get_running_apps")
    script = (
        'tell application "System Events" to '
        "get name of every process whose background only is false"
    )
    try:
        output = run_applescript(script)
    except RuntimeError:
        # Fallback: use ps to list processes
        _, output, _ = run_command("ps -A -o comm= | xargs -I{} basename {}", capture=True)
        return sorted(set(line.strip() for line in output.splitlines() if line.strip()))

    # AppleScript returns a comma-separated list
    apps = [a.strip() for a in output.split(",") if a.strip()]
    return sorted(apps)


def is_app_running(app_name: str) -> bool:
    """Return ``True`` if the application *app_name* is currently running.

    Parameters
    ----------
    app_name:
        Application name as it would appear in Activity Monitor
        (e.g. ``"Safari"``).

    Returns
    -------
    bool
    """
    _require_macos("is_app_running")
    script = (
        f'tell application "System Events" to '
        f'(name of processes) contains "{app_name}"'
    )
    try:
        result = run_applescript(script)
        return result.lower() == "true"
    except RuntimeError:
        return False


# ---------------------------------------------------------------------------
# open_app / quit_app
# ---------------------------------------------------------------------------


def open_app(app_name: str) -> str:
    """Launch *app_name* using the macOS ``open`` command.

    Parameters
    ----------
    app_name:
        Application name (e.g. ``"Safari"``).

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("open_app")
    rc, _, stderr = run_command(["open", "-a", app_name])
    if rc != 0:
        return f"Failed to open {app_name!r}: {stderr}"
    return f"Opening {app_name}."


def quit_app(app_name: str) -> str:
    """Gracefully quit *app_name* via AppleScript.

    Parameters
    ----------
    app_name:
        Application name (e.g. ``"Safari"``).

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("quit_app")
    script = f'tell application "{app_name}" to quit'
    try:
        run_applescript(script)
        return f"Quitting {app_name}."
    except RuntimeError as exc:
        return f"Could not quit {app_name!r}: {exc}"


# ---------------------------------------------------------------------------
# set_volume / get_volume
# ---------------------------------------------------------------------------


def set_volume(level: int) -> str:
    """Set the system output volume to *level* (0–100).

    Parameters
    ----------
    level:
        Desired volume percentage.  Clamped to [0, 100].

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("set_volume")
    level = max(0, min(100, level))
    # osascript expects a 0–7 scale; we map 0–100 → 0–7
    applescript_level = round(level * 7 / 100)
    script = f"set volume output volume {level}"
    try:
        run_applescript(script)
        return f"Volume set to {level}%."
    except RuntimeError as exc:
        return f"Failed to set volume: {exc}"


def get_volume() -> int:
    """Return the current system output volume as an integer (0–100).

    Returns
    -------
    int
        Current volume level.  Returns ``-1`` on failure.
    """
    _require_macos("get_volume")
    script = "output volume of (get volume settings)"
    try:
        result = run_applescript(script)
        return int(result)
    except (RuntimeError, ValueError):
        return -1


# ---------------------------------------------------------------------------
# set_brightness
# ---------------------------------------------------------------------------


def set_brightness(level: int) -> str:
    """Set the built-in display brightness to *level* (0–100) via ``osascript``.

    Parameters
    ----------
    level:
        Desired brightness percentage.  Clamped to [0, 100].

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("set_brightness")
    level = max(0, min(100, level))
    # osascript brightness property is 0.0–1.0
    brightness = level / 100.0
    brightness_str = f"{brightness:.2f}"
    applescript = f'tell application "System Events" to set brightness to {brightness_str}'
    rc, _, stderr = run_command(["osascript", "-e", applescript])
    if rc == 0:
        return f"Brightness set to {level}%."
    # Fallback: use the standalone 'brightness' CLI tool if installed
    rc2, _, _ = run_command(["which", "brightness"])
    if rc2 == 0:
        run_command(["brightness", brightness_str])
        return f"Brightness set to {level}%."
    return f"Brightness adjustment not supported on this system (rc={rc}): {stderr}"


# ---------------------------------------------------------------------------
# lock_screen
# ---------------------------------------------------------------------------


def lock_screen() -> str:
    """Lock the current user's screen.

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("lock_screen")
    rc, _, stderr = run_command(
        [
            "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
            "-suspend",
        ]
    )
    if rc == 0:
        return "Screen locked."
    # Fallback: use pmset to assert the screensaver
    rc2, _, _ = run_command(
        ["osascript", "-e",
         'tell application "System Events" to keystroke "q" using {command down, control down}']
    )
    return "Screen locked." if rc2 == 0 else f"Failed to lock screen: {stderr}"


# ---------------------------------------------------------------------------
# sleep_system
# ---------------------------------------------------------------------------


def sleep_system() -> str:
    """Put the system to sleep immediately using ``pmset``.

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("sleep_system")
    rc, _, stderr = run_command(["pmset", "sleepnow"])
    if rc == 0:
        return "Going to sleep now."
    # Fallback via AppleScript
    try:
        run_applescript('tell application "Finder" to sleep')
        return "Going to sleep now."
    except RuntimeError:
        return f"Failed to sleep: {stderr}"


# ---------------------------------------------------------------------------
# get_battery_info
# ---------------------------------------------------------------------------


def get_battery_info() -> dict:
    """Return a dictionary with battery status information.

    Keys
    ----
    percentage : int | None
        Current charge level (0–100).
    charging : bool | None
        ``True`` if the AC adapter is connected.
    time_remaining : str | None
        Estimated time remaining (e.g. ``"2:30"``), or ``None``.
    present : bool
        ``False`` if no battery was detected (e.g. desktop Mac).

    Returns
    -------
    dict
    """
    _require_macos("get_battery_info")
    rc, stdout, _ = run_command(["pmset", "-g", "batt"])
    if rc != 0 or not stdout:
        return {"present": False, "percentage": None, "charging": None, "time_remaining": None}

    # Example line: "Now drawing from 'AC Power'"
    # "  -InternalBattery-0 (id=...)	100%; charged; 0:00 remaining present: true"
    info: dict = {"present": False, "percentage": None, "charging": None, "time_remaining": None}

    pct_match = re.search(r"(\d{1,3})%", stdout)
    if pct_match:
        info["percentage"] = int(pct_match.group(1))
        info["present"] = True

    if "charging" in stdout.lower() or "ac power" in stdout.lower():
        info["charging"] = True
    elif "discharging" in stdout.lower() or "battery power" in stdout.lower():
        info["charging"] = False

    time_match = re.search(r"(\d+:\d{2})\s+remaining", stdout)
    if time_match:
        info["time_remaining"] = time_match.group(1)

    return info


# ---------------------------------------------------------------------------
# toggle_do_not_disturb
# ---------------------------------------------------------------------------


def toggle_do_not_disturb(enable: bool) -> str:
    """Enable or disable Focus (Do Not Disturb) mode via ``osascript``.

    On macOS 12+ Focus mode replaced the older DND toggle.  This function
    attempts the modern shortcut first and falls back to the legacy approach.

    Parameters
    ----------
    enable:
        ``True`` to enable, ``False`` to disable Do Not Disturb / Focus.

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("toggle_do_not_disturb")
    state = "on" if enable else "off"
    action = "enabled" if enable else "disabled"

    # macOS 12+ shortcut: Control+Option click on menu bar clock triggers Focus
    # Use defaults domain for legacy DND toggle
    dnd_value = "1" if enable else "0"
    rc, _, stderr = run_command(
        ["defaults", "-currentHost", "write",
         "com.apple.notificationcenterui", "doNotDisturb", "-boolean", dnd_value]
    )
    # Restart NotificationCenter to pick up the change
    run_command(["killall", "NotificationCenter"])

    if rc == 0:
        return f"Do Not Disturb {action}."
    return f"Could not toggle Do Not Disturb (rc={rc}): {stderr}"


# ---------------------------------------------------------------------------
# empty_trash
# ---------------------------------------------------------------------------


def empty_trash() -> str:
    """Empty the macOS Trash via AppleScript.

    Returns
    -------
    str
        Human-readable status message.
    """
    _require_macos("empty_trash")
    script = 'tell application "Finder" to empty trash'
    try:
        run_applescript(script)
        return "Trash emptied."
    except RuntimeError as exc:
        return f"Failed to empty trash: {exc}"
