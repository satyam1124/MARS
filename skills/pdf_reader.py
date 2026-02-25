"""PDF reading and summarization skills for MARS."""

import os
from pathlib import Path


def _expand(path: str) -> str:
    """Expand ~ and environment variables in a path."""
    return str(Path(path).expanduser().resolve())


def read_pdf(path: str, pages: int = 3) -> str:
    """Extract and return text from a PDF file.

    Args:
        path: Path to the PDF file.
        pages: Maximum number of pages to read (default: 3).

    Returns:
        Extracted text as a string.
    """
    try:
        import pypdf
    except ImportError:
        return "pypdf is not installed. Run: pip install pypdf"

    pdf_path = _expand(path)
    if not Path(pdf_path).exists():
        return f"PDF not found: {pdf_path}"

    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        read_up_to = min(pages, total_pages)
        texts: list[str] = []
        for i in range(read_up_to):
            text = reader.pages[i].extract_text() or ""
            if text.strip():
                texts.append(f"[Page {i + 1}]\n{text.strip()}")
        if not texts:
            return "No readable text found in the PDF."
        content = "\n\n".join(texts)
        note = f"\n\n(Showing {read_up_to} of {total_pages} page(s).)" if total_pages > pages else ""
        return content + note
    except Exception as e:
        return f"Failed to read PDF: {e}"


def summarize_pdf(path: str) -> str:
    """Extract text from a PDF and summarize it using OpenAI.

    Args:
        path: Path to the PDF file.

    Returns:
        A summary of the PDF contents.
    """
    try:
        import pypdf
    except ImportError:
        return "pypdf is not installed. Run: pip install pypdf"

    pdf_path = _expand(path)
    if not Path(pdf_path).exists():
        return f"PDF not found: {pdf_path}"

    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        texts: list[str] = []
        for i in range(min(10, total_pages)):
            text = reader.pages[i].extract_text() or ""
            if text.strip():
                texts.append(text.strip())
        full_text = "\n\n".join(texts)
    except Exception as e:
        return f"Failed to read PDF: {e}"

    if not full_text.strip():
        return "No readable text found in the PDF to summarize."

    # Truncate to ~4000 chars to stay within token limits
    truncated = full_text[:4000]
    if len(full_text) > 4000:
        truncated += "\n...[truncated]"

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Return a naive extractive summary
        sentences = [s.strip() for s in full_text.replace("\n", " ").split(".") if len(s.strip()) > 40]
        summary = ". ".join(sentences[:5]) + "."
        return f"(No OpenAI key — extractive summary):\n{summary}"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes documents concisely."},
                {"role": "user", "content": f"Please summarize the following PDF content:\n\n{truncated}"},
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content or "Summary could not be generated."
    except Exception as e:
        return f"OpenAI summarization failed: {e}"


def get_pdf_info(path: str) -> str:
    """Return metadata and page count for a PDF file.

    Args:
        path: Path to the PDF file.

    Returns:
        PDF metadata as a string.
    """
    try:
        import pypdf
    except ImportError:
        return "pypdf is not installed. Run: pip install pypdf"

    pdf_path = _expand(path)
    if not Path(pdf_path).exists():
        return f"PDF not found: {pdf_path}"

    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        meta = reader.metadata or {}
        file_size = Path(pdf_path).stat().st_size
        for unit in ["B", "KB", "MB", "GB"]:
            if file_size < 1024:
                size_str = f"{file_size:.1f} {unit}"
                break
            file_size /= 1024
        else:
            size_str = f"{file_size:.1f} GB"

        info_lines = [
            f"File: {pdf_path}",
            f"Pages: {total_pages}",
            f"File size: {size_str}",
        ]
        fields = {
            "Title": meta.get("/Title"),
            "Author": meta.get("/Author"),
            "Subject": meta.get("/Subject"),
            "Creator": meta.get("/Creator"),
            "Producer": meta.get("/Producer"),
            "Created": meta.get("/CreationDate"),
            "Modified": meta.get("/ModDate"),
        }
        for label, value in fields.items():
            if value:
                info_lines.append(f"{label}: {value}")

        return "\n".join(info_lines)
    except Exception as e:
        return f"Failed to read PDF info: {e}"
