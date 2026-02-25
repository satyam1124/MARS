"""
utils package — shared utilities for the MARS assistant.

Submodules
----------
logger      : Configures rotating-file + coloured-console logging via get_logger().
helpers     : General-purpose helper functions (formatting, parsing, CLI prompts).
macos_utils : macOS-specific system utilities (AppleScript, volume, brightness, …).
database    : Lightweight SQLite wrapper with context-manager support.
"""

from utils.logger import get_logger
from utils.helpers import (
    format_size,
    truncate_text,
    sanitize_filename,
    parse_duration,
    confirm_action,
    format_list,
    extract_number,
)
from utils.macos_utils import (
    run_applescript,
    run_command,
    get_running_apps,
    is_app_running,
    open_app,
    quit_app,
    set_volume,
    get_volume,
    set_brightness,
    lock_screen,
    sleep_system,
    get_battery_info,
    toggle_do_not_disturb,
    empty_trash,
)
from utils.database import Database

__all__ = [
    "get_logger",
    "format_size",
    "truncate_text",
    "sanitize_filename",
    "parse_duration",
    "confirm_action",
    "format_list",
    "extract_number",
    "run_applescript",
    "run_command",
    "get_running_apps",
    "is_app_running",
    "open_app",
    "quit_app",
    "set_volume",
    "get_volume",
    "set_brightness",
    "lock_screen",
    "sleep_system",
    "get_battery_info",
    "toggle_do_not_disturb",
    "empty_trash",
    "Database",
]
