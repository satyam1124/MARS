"""Screenshot skills for MARS."""

import base64
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


def _default_path(prefix: str = "screenshot") -> str:
    """Generate a timestamped screenshot path on the Desktop."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    desktop = Path.home() / "Desktop"
    desktop.mkdir(exist_ok=True)
    return str(desktop / f"{prefix}_{ts}.png")


def take_screenshot(filename: str = "", region: str = "full") -> str:
    """Take a screenshot using screencapture (macOS) or scrot (Linux).

    Args:
        filename: Output file path (default: ~/Desktop/screenshot_<timestamp>.png).
        region: 'full' for the whole screen, or 'selection' for interactive selection.

    Returns:
        Path to the saved screenshot or an error message.
    """
    out_path = filename if filename else _default_path("screenshot")
    out_path = str(Path(out_path).expanduser().resolve())
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        cmd = ["screencapture", "-x"]
        if region == "selection":
            cmd.append("-s")
        cmd.append(out_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return f"screencapture failed: {result.stderr.strip()}"
        if not Path(out_path).exists():
            return "Screenshot file was not created."
        return f"Screenshot saved to: {out_path}"
    except FileNotFoundError:
        # Linux fallback
        try:
            cmd_linux = ["scrot", out_path]
            if region == "selection":
                cmd_linux = ["scrot", "-s", out_path]
            result = subprocess.run(cmd_linux, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and Path(out_path).exists():
                return f"Screenshot saved to: {out_path}"
            return f"scrot failed: {result.stderr.strip()}"
        except FileNotFoundError:
            return "Screenshot tool not found. Need screencapture (macOS) or scrot (Linux)."
        except Exception as e:
            return f"Screenshot failed: {e}"
    except subprocess.TimeoutExpired:
        return "Screenshot timed out."
    except Exception as e:
        return f"Screenshot failed: {e}"


def take_window_screenshot(app_name: str = "") -> str:
    """Take a screenshot of a specific application window.

    On macOS, uses screencapture with -l and AppleScript to get the window ID.
    If app_name is empty, captures the frontmost window.

    Args:
        app_name: Application name (e.g., 'Safari', 'Terminal'). Empty for frontmost.

    Returns:
        Path to the saved screenshot or an error message.
    """
    out_path = _default_path("window")

    try:
        if app_name:
            # Bring the app to the foreground and get its window ID
            activate_script = f'tell application "{app_name}" to activate'
            subprocess.run(["osascript", "-e", activate_script], timeout=5)
            import time
            time.sleep(0.5)

        # screencapture -l requires a window ID; use -w (interactive) as a simpler approach
        result = subprocess.run(
            ["screencapture", "-x", "-o", "-w", out_path],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0 or not Path(out_path).exists():
            # Fallback: full screenshot
            return take_screenshot(out_path)
        return f"Window screenshot saved to: {out_path}"
    except FileNotFoundError:
        return take_screenshot(out_path)
    except Exception as e:
        return f"Window screenshot failed: {e}"


def screenshot_and_describe() -> str:
    """Take a screenshot and describe its contents using GPT-4 Vision.

    Returns:
        A natural language description of the screenshot.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return "OPENAI_API_KEY is not set. Cannot use GPT-4 Vision."

    tmp_path = str(Path(tempfile.gettempdir()) / f"mars_describe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    capture_result = take_screenshot(tmp_path)
    if "saved to" not in capture_result.lower() and "screenshot" not in capture_result.lower():
        return f"Screenshot failed: {capture_result}"

    if not Path(tmp_path).exists():
        return f"Screenshot was not saved: {capture_result}"

    try:
        with open(tmp_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return f"Failed to read screenshot: {e}"
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        },
                        {
                            "type": "text",
                            "text": "Describe what is visible on this computer screen in detail.",
                        },
                    ],
                }
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content or "No description returned."
    except Exception as e:
        return f"GPT-4 Vision description failed: {e}"
