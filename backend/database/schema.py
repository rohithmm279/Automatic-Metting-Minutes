"""SQLite database schema definitions and migrations."""

from pathlib import Path
import sqlite3
from backend.database.connection import get_connection

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    task TEXT NOT NULL,
    owner TEXT,
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    confidence REAL NOT NULL DEFAULT 1.0,
    evidence TEXT,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    decision TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS unresolved_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    issue TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_action_items_meeting_id ON action_items(meeting_id);
CREATE INDEX IF NOT EXISTS idx_decisions_meeting_id ON decisions(meeting_id);
CREATE INDEX IF NOT EXISTS idx_unresolved_issues_meeting_id ON unresolved_issues(meeting_id);
"""

# Additive migrations applied after CREATE TABLE IF NOT EXISTS.
# Each is guarded so it silently no-ops on databases that already have the column.
_MIGRATIONS = [
    # v1.1: add evidence column to action_items for agentic pipeline output
    "ALTER TABLE action_items ADD COLUMN evidence TEXT;",
]


def init_db(conn: sqlite3.Connection | None = None, db_path: str | Path | None = None) -> None:
    """Initialize database tables, indexes, and apply additive column migrations."""
    should_close = False
    if conn is None:
        conn = get_connection(db_path)
        should_close = True

    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        # Run additive migrations — each is a no-op if the column already exists
        for migration_sql in _MIGRATIONS:
            try:
                conn.execute(migration_sql)
                conn.commit()
            except sqlite3.OperationalError as exc:
                # "duplicate column name" means migration already applied — safe to ignore
                if "duplicate column" not in str(exc).lower():
                    raise
    finally:
        if should_close:
            conn.close()

