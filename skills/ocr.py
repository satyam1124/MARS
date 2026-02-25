"""OCR and QR code skills for MARS."""

import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


def _expand(path: str) -> str:
    """Expand ~ and environment variables in a path."""
    return str(Path(path).expanduser().resolve())


def read_text_from_image(image_path: str) -> str:
    """Extract text from an image using pytesseract (OCR).

    Args:
        image_path: Path to the image file.

    Returns:
        Extracted text or an error message.
    """
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return "pytesseract or Pillow is not installed. Run: pip install pytesseract Pillow"

    resolved = _expand(image_path)
    if not Path(resolved).exists():
        return f"Image not found: {resolved}"

    try:
        img = Image.open(resolved)
        text = pytesseract.image_to_string(img).strip()
        if not text:
            return "No text detected in the image."
        return text
    except Exception as e:
        return f"OCR failed: {e}"


def read_qr_code(image_path: str) -> str:
    """Decode a QR code from an image file.

    Args:
        image_path: Path to the image containing a QR code.

    Returns:
        Decoded QR code data or an error message.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return "opencv-python is not installed. Run: pip install opencv-python"

    resolved = _expand(image_path)
    if not Path(resolved).exists():
        return f"Image not found: {resolved}"

    try:
        img = cv2.imread(resolved)
        if img is None:
            return f"Could not read image: {resolved}"
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if not data:
            return "No QR code detected in the image."
        return f"QR code data: {data}"
    except Exception as e:
        return f"QR code reading failed: {e}"


def generate_qr_code(data: str, output_path: str = "") -> str:
    """Generate a QR code image from data.

    Args:
        data: The text or URL to encode in the QR code.
        output_path: Output file path (default: ~/Pictures/qr_<timestamp>.png).

    Returns:
        Path to the generated QR code image or an error message.
    """
    try:
        import qrcode  # type: ignore
    except ImportError:
        return "qrcode is not installed. Run: pip install qrcode[pil]"

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(Path.home() / "Pictures" / f"qr_{ts}.png")

    out = _expand(output_path)
    Path(out).parent.mkdir(parents=True, exist_ok=True)

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(out)
        return f"QR code generated and saved to: {out}"
    except Exception as e:
        return f"Failed to generate QR code: {e}"


def ocr_screenshot() -> str:
    """Take a screenshot and extract text from it using OCR.

    Returns:
        Extracted text from the screenshot or an error message.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_path = str(Path(tempfile.gettempdir()) / f"mars_ocr_{ts}.png")

    # Capture screenshot
    try:
        result = subprocess.run(
            ["screencapture", "-x", tmp_path], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return f"Screenshot failed: {result.stderr.strip()}"
    except FileNotFoundError:
        # Linux fallback
        try:
            subprocess.run(
                ["scrot", tmp_path], capture_output=True, text=True, timeout=10, check=True
            )
        except Exception as e:
            return f"Screenshot tool not found (need screencapture or scrot): {e}"
    except Exception as e:
        return f"Screenshot failed: {e}"

    if not Path(tmp_path).exists():
        return "Screenshot file was not created."

    text = read_text_from_image(tmp_path)

    # Clean up temp file
    try:
        Path(tmp_path).unlink()
    except Exception:
        pass

    return text if text else "No text found in screenshot."
