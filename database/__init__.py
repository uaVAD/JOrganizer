import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS user_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_name TEXT NOT NULL,
                    matched_name TEXT NOT NULL,
                    media_type TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    old_path TEXT NOT NULL,
                    new_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL
                );
            """)

    # --- Operations ---

    def add_operation(self, old_path: str, new_path: str, timestamp: str) -> int:
        """Record a file operation. Returns operation id."""
        cur = self.conn.execute(
            "INSERT INTO operations (old_path, new_path, timestamp) VALUES (?, ?, ?)",
            (old_path, new_path, timestamp),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_operation(self, operation_id: int) -> dict | None:
        """Get single operation by id."""
        row = self.conn.execute(
            "SELECT id, old_path, new_path, timestamp FROM operations WHERE id = ?",
            (operation_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_all_operations(self) -> list[dict]:
        """Get all operations ordered by timestamp DESC."""
        rows = self.conn.execute(
            "SELECT id, old_path, new_path, timestamp FROM operations ORDER BY timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_operation(self, operation_id: int):
        """Delete an operation record."""
        with self.conn:
            self.conn.execute("DELETE FROM operations WHERE id = ?", (operation_id,))

    def clear_operations(self):
        """Clear all operations history."""
        with self.conn:
            self.conn.execute("DELETE FROM operations")

    # --- User Matches ---

    def add_user_match(self, original_name: str, matched_name: str, media_type: str) -> int:
        """Save a user-confirmed match. Returns id."""
        cur = self.conn.execute(
            "INSERT INTO user_matches (original_name, matched_name, media_type) VALUES (?, ?, ?)",
            (original_name, matched_name, media_type),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_user_match(self, original_name: str) -> dict | None:
        """Get cached match for a filename."""
        row = self.conn.execute(
            "SELECT id, original_name, matched_name, media_type FROM user_matches WHERE original_name = ?",
            (original_name,),
        ).fetchone()
        return dict(row) if row else None

    def get_all_user_matches(self) -> list[dict]:
        """Get all cached matches."""
        rows = self.conn.execute(
            "SELECT id, original_name, matched_name, media_type FROM user_matches"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_user_match(self, match_id: int):
        """Delete a cached match."""
        with self.conn:
            self.conn.execute("DELETE FROM user_matches WHERE id = ?", (match_id,))

    # --- Settings ---

    def set_setting(self, key: str, value: str):
        """Save or update a setting."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (setting, value) VALUES (?, ?) "
                "ON CONFLICT(setting) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get a setting value."""
        row = self.conn.execute(
            "SELECT value FROM settings WHERE setting = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def get_all_settings(self) -> dict[str, str]:
        """Get all settings as dict."""
        rows = self.conn.execute("SELECT setting, value FROM settings").fetchall()
        return {r["setting"]: r["value"] for r in rows}

    def delete_setting(self, key: str):
        """Delete a setting."""
        with self.conn:
            self.conn.execute("DELETE FROM settings WHERE setting = ?", (key,))

    # --- General ---

    def close(self):
        self.conn.close()
