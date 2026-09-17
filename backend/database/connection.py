"""SQLite database connection management."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator

# Default database location in the backend folder
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "meetings.db"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection.
    
    Enforces foreign key constraints and sets row factory to sqlite3.Row
    for column-name based access.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), timeout=10.0)
    # Crucial for SQLite: Foreign keys are disabled by default
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db(db_path: str | Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connection.

    Commits on clean exit, rolls back on any exception, and always closes
    the connection. Use this for write operations that should be atomic.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
