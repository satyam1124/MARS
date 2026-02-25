"""
todo.py — SQLite-based to-do list skill for MARS.

All functions return a ``str`` response that MARS speaks aloud.
Backed by the shared :class:`utils.database.Database` helper.

Priority mapping
----------------
"high"   → 3
"medium" → 2
"low"    → 1

Functions
---------
add_todo        : Add a new to-do item.
list_todos      : List incomplete (or all) to-do items.
complete_todo   : Mark a to-do item as complete by title.
delete_todo     : Delete a to-do item by title.
get_overdue_todos : List todos that are past their due date.
"""

from __future__ import annotations

import datetime

from utils.database import Database
from utils.logger import get_logger

log = get_logger(__name__)

_PRIORITY_MAP: dict[str, int] = {
    "high": 3,
    "medium": 2,
    "med": 2,
    "low": 1,
}
_PRIORITY_LABEL: dict[int, str] = {3: "high", 2: "medium", 1: "low"}


# ---------------------------------------------------------------------------
# add_todo
# ---------------------------------------------------------------------------


def add_todo(
    title: str,
    description: str = "",
    due_date: str = "",
    priority: str = "medium",
) -> str:
    """Add a new to-do item to the database.

    Parameters
    ----------
    title:
        Short title for the to-do.
    description:
        Optional longer description.
    due_date:
        Optional due date in ``YYYY-MM-DD`` or ISO-8601 format.
    priority:
        Priority level: ``"high"``, ``"medium"``, or ``"low"`` (default).

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    title = title.strip()
    if not title:
        return "Please provide a title for the to-do item."

    priority_int = _PRIORITY_MAP.get(priority.lower(), 2)

    try:
        with Database() as db:
            todo_id = db.add_todo(
                title=title,
                description=description.strip(),
                due_date=due_date.strip(),
                priority=priority_int,
            )
        log.info("add_todo: added '%s' (id=%d, priority=%s)", title, todo_id, priority)
        msg = f"To-do '{title}' added with {_PRIORITY_LABEL[priority_int]} priority."
        if due_date.strip():
            msg += f" Due on {due_date.strip()}."
        return msg
    except Exception as exc:  # noqa: BLE001
        log.error("add_todo failed: %s", exc)
        return f"I couldn't add the to-do item: {exc}"


# ---------------------------------------------------------------------------
# list_todos
# ---------------------------------------------------------------------------


def list_todos(filter_completed: bool = False) -> str:
    """List to-do items.

    Parameters
    ----------
    filter_completed:
        When ``True`` returns only completed items.  When ``False`` (default)
        returns only incomplete items.

    Returns
    -------
    str
        Spoken list of to-do items.
    """
    try:
        with Database() as db:
            if filter_completed:
                rows = db.execute(
                    "SELECT * FROM todos WHERE completed = 1 ORDER BY created_at DESC"
                )
                label = "completed"
            else:
                rows = db.get_todos(include_completed=False)
                label = "incomplete"

        if not rows:
            return f"You have no {label} to-do items."

        items = []
        for row in rows:
            priority_label = _PRIORITY_LABEL.get(row.get("priority", 2), "medium")
            due = row.get("due_date", "")
            entry = f"{row['title']} ({priority_label} priority)"
            if due:
                entry += f", due {due}"
            items.append(entry)

        count = len(items)
        item_word = "item" if count == 1 else "items"
        return f"You have {count} {label} to-do {item_word}: " + "; ".join(items) + "."
    except Exception as exc:  # noqa: BLE001
        log.error("list_todos failed: %s", exc)
        return f"I couldn't retrieve your to-do items: {exc}"


# ---------------------------------------------------------------------------
# complete_todo
# ---------------------------------------------------------------------------


def complete_todo(title: str) -> str:
    """Mark a to-do item as complete by its title.

    Parameters
    ----------
    title:
        The title (or partial title) of the to-do to mark complete.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    title = title.strip()
    if not title:
        return "Please specify the title of the to-do to complete."

    try:
        with Database() as db:
            # Find by partial title match
            rows = db.execute(
                "SELECT id, title FROM todos WHERE completed = 0 AND title LIKE ?",
                (f"%{title}%",),
            )
            if not rows:
                return f"I couldn't find an incomplete to-do matching '{title}'."

            todo = rows[0]
            db.complete_todo(todo["id"])
            log.info("complete_todo: completed '%s' (id=%d)", todo["title"], todo["id"])
            return f"To-do '{todo['title']}' marked as complete."
    except Exception as exc:  # noqa: BLE001
        log.error("complete_todo failed: %s", exc)
        return f"I couldn't complete the to-do: {exc}"


# ---------------------------------------------------------------------------
# delete_todo
# ---------------------------------------------------------------------------


def delete_todo(title: str, confirmed: bool = False) -> str:
    """Delete a to-do item by its title.

    Parameters
    ----------
    title:
        The title (or partial title) of the to-do to delete.
    confirmed:
        When ``False`` (default) a confirmation prompt is returned.  Set to
        ``True`` to actually delete.

    Returns
    -------
    str
        Spoken confirmation or error message.
    """
    title = title.strip()
    if not title:
        return "Please specify the title of the to-do to delete."

    if not confirmed:
        return (
            f"Ready to delete to-do item matching '{title}'. "
            "Please confirm to proceed."
        )

    try:
        with Database() as db:
            rows = db.execute(
                "SELECT id, title FROM todos WHERE title LIKE ?",
                (f"%{title}%",),
            )
            if not rows:
                return f"I couldn't find a to-do item matching '{title}'."

            todo = rows[0]
            db.delete_todo(todo["id"])
            log.info("delete_todo: deleted '%s' (id=%d)", todo["title"], todo["id"])
            return f"To-do '{todo['title']}' has been deleted."
    except Exception as exc:  # noqa: BLE001
        log.error("delete_todo failed: %s", exc)
        return f"I couldn't delete the to-do: {exc}"


# ---------------------------------------------------------------------------
# get_overdue_todos
# ---------------------------------------------------------------------------


def get_overdue_todos() -> str:
    """Return a spoken list of to-do items that are past their due date.

    Returns
    -------
    str
        Spoken list of overdue items, or a confirmation that nothing is overdue.
    """
    today = datetime.date.today().isoformat()

    try:
        with Database() as db:
            rows = db.execute(
                "SELECT * FROM todos WHERE completed = 0 AND due_date != '' AND due_date < ? "
                "ORDER BY due_date ASC",
                (today,),
            )

        if not rows:
            return "You have no overdue to-do items."

        items = []
        for row in rows:
            due = row.get("due_date", "")
            entry = f"{row['title']}, due {due}"
            items.append(entry)

        count = len(items)
        item_word = "item" if count == 1 else "items"
        return f"You have {count} overdue to-do {item_word}: " + "; ".join(items) + "."
    except Exception as exc:  # noqa: BLE001
        log.error("get_overdue_todos failed: %s", exc)
        return f"I couldn't check for overdue to-do items: {exc}"
