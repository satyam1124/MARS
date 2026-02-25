"""Clipboard management skills for MARS (macOS pbcopy/pbpaste)."""

import subprocess


def copy_to_clipboard(text: str) -> str:
    """Copy text to the system clipboard using pbcopy.

    Args:
        text: Text to copy.

    Returns:
        Confirmation or error message.
    """
    try:
        subprocess.run(
            ["pbcopy"],
            input=text.encode("utf-8"),
            check=True,
            timeout=5,
        )
        preview = text[:60] + ("..." if len(text) > 60 else "")
        return f"Copied to clipboard: \"{preview}\""
    except FileNotFoundError:
        # Linux fallback using xclip or xsel
        for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5)
                return f"Copied to clipboard: \"{text[:60]}\""
            except FileNotFoundError:
                continue
            except Exception as e:
                return f"Clipboard copy failed: {e}"
        return "Clipboard tool not found. Install pbcopy (macOS) or xclip/xsel (Linux)."
    except subprocess.CalledProcessError as e:
        return f"pbcopy failed: {e}"
    except Exception as e:
        return f"Failed to copy to clipboard: {e}"


def get_clipboard() -> str:
    """Read the current contents of the system clipboard.

    Returns:
        Clipboard contents or an error message.
    """
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            timeout=5,
        )
        text = result.stdout.decode("utf-8", errors="replace").strip()
        if not text:
            return "Clipboard is empty."
        preview = text[:300] + ("..." if len(text) > 300 else "")
        return f"Clipboard contents:\n{preview}"
    except FileNotFoundError:
        # Linux fallback
        for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=5, check=True)
                text = result.stdout.decode("utf-8", errors="replace").strip()
                return text if text else "Clipboard is empty."
            except FileNotFoundError:
                continue
            except Exception as e:
                return f"Clipboard read failed: {e}"
        return "Clipboard tool not found. Install pbpaste (macOS) or xclip/xsel (Linux)."
    except Exception as e:
        return f"Failed to read clipboard: {e}"


def clear_clipboard() -> str:
    """Clear the system clipboard.

    Returns:
        Confirmation or error message.
    """
    try:
        subprocess.run(
            ["pbcopy"],
            input=b"",
            check=True,
            timeout=5,
        )
        return "Clipboard cleared."
    except FileNotFoundError:
        for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
            try:
                subprocess.run(cmd, input=b"", check=True, timeout=5)
                return "Clipboard cleared."
            except FileNotFoundError:
                continue
            except Exception as e:
                return f"Failed to clear clipboard: {e}"
        return "Clipboard tool not found. Install pbcopy (macOS) or xclip/xsel (Linux)."
    except Exception as e:
        return f"Failed to clear clipboard: {e}"
