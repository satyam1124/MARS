"""
database.py — SQLite database helper for MARS.

Provides :class:`Database`, a lightweight wrapper around :mod:`sqlite3` that
supports parameterised queries, automatic table creation, and Python context
manager (``with`` statement) usage.

A default ``todos`` table is created automatically with the schema::

    id          INTEGER PRIMARY KEY AUTOINCREMENT
    title       TEXT    NOT NULL
    description TEXT
    due_date    TEXT
    priority    INTEGER DEFAULT 1
    completed   INTEGER DEFAULT 0   -- boolean: 0 = false, 1 = true
    created_at  TEXT    DEFAULT (datetime('now'))
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

# Default schema for the built-in todos table
_TODOS_COLUMNS: dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "title": "TEXT NOT NULL",
    "description": "TEXT",
    "due_date": "TEXT",
    "priority": "INTEGER DEFAULT 1",
    "completed": "INTEGER DEFAULT 0",
    "created_at": "TEXT DEFAULT (datetime('now'))",
}


class Database:
    """Lightweight SQLite wrapper used throughout MARS.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  The parent directory is created
        automatically if it does not exist.  Defaults to ``"todo.db"`` in
        the project root (parent of the ``utils/`` package).

    Examples
    --------
    Direct usage::

        db = Database()
        db.execute_write(
            "INSERT INTO todos (title) VALUES (?)", ("Buy groceries",)
        )
        rows = db.execute("SELECT * FROM todos WHERE completed = 0")

    Context manager::

        with Database() as db:
            rows = db.execute("SELECT * FROM todos")
    """

    def __init__(self, db_path: str = "todo.db") -> None:
        path = Path(db_path)
        if not path.is_absolute():
            # Resolve relative to project root (one level above utils/)
            path = Path(__file__).resolve().parents[1] / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path: Path = path
        self._conn: sqlite3.Connection | None = None
        self._connect()
        self._bootstrap()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Open the SQLite connection with sensible pragmas."""
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        log.debug("Database connected: %s", self._db_path)

    def close(self) -> None:
        """Close the underlying database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            log.debug("Database connection closed.")

    # ------------------------------------------------------------------
    # Bootstrap — create default tables
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        """Create the built-in ``todos`` table if it does not already exist."""
        self.create_table("todos", _TODOS_COLUMNS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Execute a *read* SQL statement and return all rows as plain dicts.

        Parameters
        ----------
        query:
            SQL SELECT (or any statement that returns rows).
        params:
            Positional parameters bound to ``?`` placeholders.

        Returns
        -------
        list[dict[str, Any]]
            List of rows, each represented as a ``{column: value}`` dict.
            Returns an empty list if no rows are found.

        Raises
        ------
        sqlite3.DatabaseError
            On any SQL error.

        Examples
        --------
        >>> db = Database(":memory:")
        >>> db.execute("SELECT 1 AS val")
        [{'val': 1}]
        """
        assert self._conn is not None, "Database connection is closed."
        try:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.DatabaseError:
            log.exception("execute() failed: %s | params=%s", query, params)
            raise

    def execute_write(self, query: str, params: tuple[Any, ...] = ()) -> int:
        """Execute a *write* SQL statement (INSERT / UPDATE / DELETE / DDL).

        The transaction is committed automatically on success and rolled back
        on failure.

        Parameters
        ----------
        query:
            SQL statement to execute.
        params:
            Positional parameters bound to ``?`` placeholders.

        Returns
        -------
        int
            For INSERT statements, the ``lastrowid`` of the new row.
            For UPDATE / DELETE, the number of rows affected
            (``rowcount``).  Returns ``-1`` for DDL statements.

        Raises
        ------
        sqlite3.DatabaseError
            On any SQL error.

        Examples
        --------
        >>> db = Database(":memory:")
        >>> db.execute_write("INSERT INTO todos (title) VALUES (?)", ("Test",))
        1
        """
        assert self._conn is not None, "Database connection is closed."
        try:
            cursor = self._conn.execute(query, params)
            self._conn.commit()
            stripped = query.lstrip().upper()
            if stripped.startswith("INSERT"):
                return cursor.lastrowid or -1
            return cursor.rowcount
        except sqlite3.DatabaseError:
            self._conn.rollback()
            log.exception("execute_write() failed: %s | params=%s", query, params)
            raise

    def create_table(self, name: str, columns: dict[str, str]) -> None:
        """Create a table named *name* if it does not already exist.

        Parameters
        ----------
        name:
            Table name (must be a valid SQLite identifier).
        columns:
            Ordered mapping of ``{column_name: column_definition}`` where the
            definition is a SQL type and optional constraints string, e.g.
            ``"TEXT NOT NULL"`` or ``"INTEGER PRIMARY KEY AUTOINCREMENT"``.

        Examples
        --------
        >>> db = Database(":memory:")
        >>> db.create_table("notes", {"id": "INTEGER PRIMARY KEY", "body": "TEXT"})
        """
        if not columns:
            raise ValueError("columns dict must not be empty.")
        col_defs = ", ".join(f'"{col}" {defn}' for col, defn in columns.items())
        ddl = f'CREATE TABLE IF NOT EXISTS "{name}" ({col_defs});'
        self.execute_write(ddl)
        log.debug("Table ready: %s", name)

    # ------------------------------------------------------------------
    # Convenience todo helpers
    # ------------------------------------------------------------------

    def add_todo(
        self,
        title: str,
        description: str = "",
        due_date: str = "",
        priority: int = 1,
    ) -> int:
        """Insert a new todo item and return its ``id``.

        Parameters
        ----------
        title:
            Short title for the todo.
        description:
            Optional longer description.
        due_date:
            Optional ISO-8601 date/datetime string.
        priority:
            Integer priority level (1 = low, 3 = high).

        Returns
        -------
        int
            The auto-assigned row id.
        """
        return self.execute_write(
            "INSERT INTO todos (title, description, due_date, priority) VALUES (?, ?, ?, ?)",
            (title, description, due_date, priority),
        )

    def get_todos(self, include_completed: bool = False) -> list[dict[str, Any]]:
        """Return all (optionally: only incomplete) todo items.

        Parameters
        ----------
        include_completed:
            When ``False`` (default) only incomplete items are returned.

        Returns
        -------
        list[dict[str, Any]]
        """
        if include_completed:
            return self.execute("SELECT * FROM todos ORDER BY priority DESC, created_at ASC")
        return self.execute(
            "SELECT * FROM todos WHERE completed = 0 ORDER BY priority DESC, created_at ASC"
        )

    def complete_todo(self, todo_id: int) -> int:
        """Mark a todo as completed.

        Parameters
        ----------
        todo_id:
            The ``id`` of the todo to mark complete.

        Returns
        -------
        int
            Number of rows updated (1 on success, 0 if not found).
        """
        return self.execute_write(
            "UPDATE todos SET completed = 1 WHERE id = ?", (todo_id,)
        )

    def delete_todo(self, todo_id: int) -> int:
        """Permanently delete a todo.

        Parameters
        ----------
        todo_id:
            The ``id`` of the todo to remove.

        Returns
        -------
        int
            Number of rows deleted.
        """
        return self.execute_write("DELETE FROM todos WHERE id = ?", (todo_id,))

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Database":
        """Return *self* — the connection is already open from ``__init__``."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Close the database connection on exiting the ``with`` block."""
        self.close()

    def __repr__(self) -> str:
        return f"Database(path={str(self._db_path)!r}, open={self._conn is not None})"
