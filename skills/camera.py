"""Camera skills for MARS — photo capture and image description."""

import base64
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


def _default_filename() -> str:
    """Generate a timestamped filename for a captured photo."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path.home() / "Pictures" / f"mars_photo_{ts}.jpg")


def capture_photo(filename: str = "") -> str:
    """Capture a photo from the default camera.

    Uses `imagesnap` (macOS) if available, otherwise falls back to
    AVFoundation via a Python helper.

    Args:
        filename: Output file path (default: ~/Pictures/mars_photo_<timestamp>.jpg).

    Returns:
        Path to the saved photo or an error message.
    """
    out_path = filename if filename else _default_filename()
    out_path = str(Path(out_path).expanduser().resolve())

    # Ensure directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # Try imagesnap (macOS, install with `brew install imagesnap`)
    try:
        result = subprocess.run(
            ["imagesnap", "-w", "1", out_path],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and Path(out_path).exists():
            return f"Photo captured and saved to: {out_path}"
        err = result.stderr.strip() or result.stdout.strip()
        return f"imagesnap failed: {err}"
    except FileNotFoundError:
        pass
    except Exception as e:
        return f"imagesnap error: {e}"

    # Fallback: OpenCV
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Could not open camera. Make sure a camera is connected and not in use."
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "Failed to capture frame from camera."
        cv2.imwrite(out_path, frame)
        return f"Photo captured and saved to: {out_path}"
    except ImportError:
        return (
            "Camera capture requires 'imagesnap' (macOS: brew install imagesnap) "
            "or 'opencv-python' (pip install opencv-python)."
        )
    except Exception as e:
        return f"Failed to capture photo: {e}"


def describe_image(image_path: str) -> str:
    """Describe an image using GPT-4 Vision.

    Args:
        image_path: Path to the image file (JPEG, PNG, etc.).

    Returns:
        A natural language description of the image.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return "OPENAI_API_KEY is not set. Cannot use GPT-4 Vision."

    resolved = str(Path(image_path).expanduser().resolve())
    if not Path(resolved).exists():
        return f"Image not found: {resolved}"

    # Read and base64-encode the image
    try:
        with open(resolved, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return f"Failed to read image: {e}"

    suffix = Path(resolved).suffix.lower().lstrip(".")
    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
    mime_type = f"image/{mime_map.get(suffix, 'jpeg')}"

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
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                        },
                        {"type": "text", "text": "Describe what you see in this image in detail."},
                    ],
                }
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content or "No description returned."
    except Exception as e:
        return f"GPT-4 Vision error: {e}"
