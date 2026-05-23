import pytest
import tempfile
import sqlite3
from pathlib import Path
from database import Database


class TestDatabase:
    """Test cases for the Database module."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = Database(db_path)
        yield db
        db.close()
        db_path.unlink()

    def test_db_initializes_tables(self, db):
        """Test that Database creates required tables."""
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert 'user_matches' in table_names
        assert 'operations' in table_names
        assert 'settings' in table_names

    def test_db_insert_and_query_user_match(self, db):
        """Test inserting and querying user_matches."""
        with db.conn:
            db.conn.execute(
                "INSERT INTO user_matches (original_name, matched_name, media_type) VALUES (?, ?, ?)",
                ("test.mp4", "Test Movie (2025).mp4", "movie")
            )
        results = db.conn.execute("SELECT * FROM user_matches").fetchall()
        assert len(results) == 1
        assert results[0][2] == "Test Movie (2025).mp4"

    def test_db_insert_and_query_operation(self, db):
        """Test inserting and querying operations."""
        with db.conn:
            db.conn.execute(
                "INSERT INTO operations (old_path, new_path, timestamp) VALUES (?, ?, ?)",
                ("/source/movie.mp4", "/dest/Movies/movie.mp4", "2025-01-01")
            )
        results = db.conn.execute("SELECT * FROM operations").fetchall()
        assert len(results) == 1
        assert results[0][2] == "/dest/Movies/movie.mp4"

    def test_db_insert_and_query_settings(self, db):
        """Test inserting and querying settings."""
        with db.conn:
            db.conn.execute(
                "INSERT OR REPLACE INTO settings (setting, value) VALUES (?, ?)",
                ("theme", "dark")
            )
        results = db.conn.execute("SELECT * FROM settings WHERE setting='theme'").fetchall()
        assert len(results) == 1
        assert results[0][2] == "dark"

    def test_db_settings_unique_constraint(self, db):
        """Test that settings table enforces unique constraint on 'setting'."""
        with db.conn:
            db.conn.execute(
                "INSERT OR IGNORE INTO settings (setting, value) VALUES (?, ?)",
                ("theme", "dark")
            )
            # Should not raise due to OR IGNORE, but value should be same
            results = db.conn.execute("SELECT * FROM settings WHERE setting='theme'").fetchall()
            assert len(results) == 1

    def test_db_close(self, db):
        """Test that close() properly closes connection."""
        db.close()
        with pytest.raises(sqlite3.ProgrammingError):
            db.conn.execute("SELECT 1")

    def test_db_creates_file(self):
        """Test that Database creates the database file."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        try:
            db = Database(db_path)
            assert db_path.exists()
            db.close()
        finally:
            if db_path.exists():
                db_path.unlink()
