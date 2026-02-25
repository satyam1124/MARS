"""File management skills for MARS."""

import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


def _expand(path: str) -> str:
    """Expand ~ and environment variables in a path."""
    return str(Path(path).expanduser().resolve())


def search_files(query: str, directory: str = "~") -> str:
    """Search for files matching a query using mdfind (macOS Spotlight).

    Args:
        query: The search term.
        directory: Directory to search in (default: home directory).

    Returns:
        Search results as a string.
    """
    dir_path = _expand(directory)
    try:
        result = subprocess.run(
            ["mdfind", "-onlyin", dir_path, query],
            capture_output=True, text=True, timeout=10
        )
        lines = [l for l in result.stdout.strip().splitlines() if l]
        if not lines:
            return f"No files found matching '{query}' in {dir_path}."
        top = lines[:15]
        summary = "\n".join(top)
        extra = f"\n...and {len(lines) - 15} more." if len(lines) > 15 else ""
        return f"Found {len(lines)} file(s) matching '{query}':\n{summary}{extra}"
    except FileNotFoundError:
        # fallback to find
        try:
            result = subprocess.run(
                ["find", dir_path, "-iname", f"*{query}*", "-maxdepth", "5"],
                capture_output=True, text=True, timeout=15
            )
            lines = [l for l in result.stdout.strip().splitlines() if l]
            if not lines:
                return f"No files found matching '{query}' in {dir_path}."
            top = lines[:15]
            return f"Found {len(lines)} file(s):\n" + "\n".join(top)
        except Exception as e:
            return f"Search failed: {e}"
    except Exception as e:
        return f"Search failed: {e}"


def list_directory(path: str = "~") -> str:
    """List the contents of a directory.

    Args:
        path: Directory path (default: home directory).

    Returns:
        Directory listing as a string.
    """
    dir_path = _expand(path)
    try:
        entries = sorted(Path(dir_path).iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        if not entries:
            return f"Directory '{dir_path}' is empty."
        lines: list[str] = []
        for entry in entries[:50]:
            kind = "📁" if entry.is_dir() else "📄"
            lines.append(f"{kind} {entry.name}")
        extra = f"\n...and {len(entries) - 50} more items." if len(entries) > 50 else ""
        return f"Contents of {dir_path} ({len(entries)} items):\n" + "\n".join(lines) + extra
    except PermissionError:
        return f"Permission denied to access '{dir_path}'."
    except Exception as e:
        return f"Failed to list directory: {e}"


def create_directory(path: str) -> str:
    """Create a new directory (including intermediate directories).

    Args:
        path: Path of the directory to create.

    Returns:
        Confirmation or error message.
    """
    dir_path = _expand(path)
    try:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        return f"Directory created: {dir_path}"
    except Exception as e:
        return f"Failed to create directory: {e}"


def delete_file(path: str, confirmed: bool = False) -> str:
    """Delete a file or directory.

    Args:
        path: Path to the file or directory.
        confirmed: Must be True to actually delete.

    Returns:
        Confirmation or error message.
    """
    target = _expand(path)
    if not confirmed:
        return (
            f"Are you sure you want to delete '{target}'? "
            "Call delete_file again with confirmed=True to proceed."
        )
    try:
        p = Path(target)
        if not p.exists():
            return f"Path not found: {target}"
        if p.is_dir():
            shutil.rmtree(target)
        else:
            p.unlink()
        return f"Deleted: {target}"
    except Exception as e:
        return f"Failed to delete: {e}"


def move_file(source: str, destination: str) -> str:
    """Move a file or directory to a new location.

    Args:
        source: Source path.
        destination: Destination path.

    Returns:
        Confirmation or error message.
    """
    src = _expand(source)
    dst = _expand(destination)
    try:
        shutil.move(src, dst)
        return f"Moved '{src}' to '{dst}'."
    except Exception as e:
        return f"Failed to move file: {e}"


def copy_file(source: str, destination: str) -> str:
    """Copy a file or directory to a new location.

    Args:
        source: Source path.
        destination: Destination path.

    Returns:
        Confirmation or error message.
    """
    src = _expand(source)
    dst = _expand(destination)
    try:
        if Path(src).is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return f"Copied '{src}' to '{dst}'."
    except Exception as e:
        return f"Failed to copy: {e}"


def get_file_info(path: str) -> str:
    """Get detailed information about a file or directory.

    Args:
        path: Path to the file or directory.

    Returns:
        File information as a string.
    """
    target = _expand(path)
    try:
        p = Path(target)
        if not p.exists():
            return f"Path not found: {target}"
        stat = p.stat()
        size_bytes = stat.st_size
        # Human-readable size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                size_str = f"{size_bytes:.1f} {unit}"
                break
            size_bytes /= 1024
        else:
            size_str = f"{size_bytes:.1f} PB"

        created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        permissions = oct(stat.st_mode)[-3:]
        kind = "Directory" if p.is_dir() else "File"
        return (
            f"{kind}: {target}\n"
            f"Size: {size_str}\n"
            f"Created: {created}\n"
            f"Modified: {modified}\n"
            f"Permissions: {permissions}"
        )
    except Exception as e:
        return f"Failed to get file info: {e}"


def organize_downloads(confirmed: bool = False) -> str:
    """Organize ~/Downloads by moving files into subfolders by type.

    Args:
        confirmed: Must be True to actually move files.

    Returns:
        Summary of actions taken or a confirmation prompt.
    """
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return "Downloads folder not found."

    type_map: dict[str, list[str]] = {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".tiff"],
        "Videos": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v"],
        "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"],
        "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"],
        "Archives": [".zip", ".tar", ".gz", ".rar", ".7z", ".dmg", ".pkg"],
        "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".sh", ".rb", ".java"],
    }

    files = [f for f in downloads.iterdir() if f.is_file()]
    if not files:
        return "Downloads folder is already empty or has no files to organize."

    plan: list[tuple[Path, Path]] = []
    for f in files:
        suffix = f.suffix.lower()
        dest_folder = "Misc"
        for folder, exts in type_map.items():
            if suffix in exts:
                dest_folder = folder
                break
        plan.append((f, downloads / dest_folder / f.name))

    if not confirmed:
        preview = "\n".join(f"  {src.name} → {dst.parent.name}/" for src, dst in plan[:10])
        extra = f"\n  ...and {len(plan) - 10} more files." if len(plan) > 10 else ""
        return (
            f"Ready to organize {len(plan)} file(s) in Downloads:\n{preview}{extra}\n"
            "Call organize_downloads(confirmed=True) to proceed."
        )

    moved = 0
    errors: list[str] = []
    for src, dst in plan:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            moved += 1
        except Exception as e:
            errors.append(f"{src.name}: {e}")

    msg = f"Organized {moved} file(s) in Downloads."
    if errors:
        msg += f" Errors ({len(errors)}): " + "; ".join(errors[:3])
    return msg


def zip_files(files: list[str], output: str) -> str:
    """Create a ZIP archive from a list of files.

    Args:
        files: List of file paths to include.
        output: Output ZIP file path.

    Returns:
        Confirmation or error message.
    """
    out_path = _expand(output)
    if not out_path.endswith(".zip"):
        out_path += ".zip"
    try:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                fp = _expand(f)
                if Path(fp).is_file():
                    zf.write(fp, Path(fp).name)
                elif Path(fp).is_dir():
                    for child in Path(fp).rglob("*"):
                        if child.is_file():
                            zf.write(str(child), str(child.relative_to(Path(fp).parent)))
                else:
                    return f"File not found: {fp}"
        return f"Created ZIP archive: {out_path}"
    except Exception as e:
        return f"Failed to create ZIP: {e}"


def unzip_file(path: str, destination: str = "") -> str:
    """Extract a ZIP archive.

    Args:
        path: Path to the ZIP file.
        destination: Extraction directory (defaults to same directory as ZIP).

    Returns:
        Confirmation or error message.
    """
    zip_path = _expand(path)
    dest = _expand(destination) if destination else str(Path(zip_path).parent)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
            names = zf.namelist()
        return f"Extracted {len(names)} file(s) to '{dest}'."
    except FileNotFoundError:
        return f"ZIP file not found: {zip_path}"
    except zipfile.BadZipFile:
        return f"'{zip_path}' is not a valid ZIP file."
    except Exception as e:
        return f"Failed to extract ZIP: {e}"


def open_file(path: str) -> str:
    """Open a file with its default application.

    Args:
        path: Path to the file to open.

    Returns:
        Confirmation or error message.
    """
    target = _expand(path)
    if not Path(target).exists():
        return f"File not found: {target}"
    try:
        # macOS
        subprocess.Popen(["open", target])
        return f"Opening '{target}'."
    except FileNotFoundError:
        try:
            # Linux
            subprocess.Popen(["xdg-open", target])
            return f"Opening '{target}'."
        except Exception as e:
            return f"Failed to open file: {e}"
    except Exception as e:
        return f"Failed to open file: {e}"
