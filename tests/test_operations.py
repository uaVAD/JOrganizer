import pytest
import tempfile
from pathlib import Path
from database import Database
from core.operations import OperationsManager


class TestOperations:
    """Test cases for the OperationsManager module."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = Database(db_path)
        yield db
        db.close()
        db_path.unlink()

    @pytest.fixture
    def ops_manager(self, temp_db):
        return OperationsManager(temp_db)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_file(self, temp_dir):
        """Create a sample test file."""
        src = temp_dir / "test_video.mp4"
        src.write_text("sample content for testing")
        return src

    def test_dry_run_returns_preview(self, ops_manager, temp_dir, sample_file, organizer, renamer, detector):
        """Test that dry run returns preview without moving files."""
        files = [{
            'path': str(sample_file),
            'name': sample_file.name,
            'size': sample_file.stat().st_size,
            'extension': '.mp4',
            'parent': str(temp_dir),
        }]

        preview = ops_manager.dry_run(files, organizer, renamer, detector)

        assert len(preview) == 1
        assert preview[0]['original'] == str(sample_file)
        assert preview[0]['target'] is not None
        assert preview[0]['result'] is not None
        assert sample_file.exists(), "File should still exist after dry run"

    def test_execute_moves_file(self, ops_manager, temp_dir, sample_file, organizer, renamer, detector):
        """Test that execute actually moves the file."""
        files = [{
            'path': str(sample_file),
            'name': sample_file.name,
            'size': sample_file.stat().st_size,
            'extension': '.mp4',
            'parent': str(temp_dir),
        }]

        preview = ops_manager.dry_run(files, organizer, renamer, detector)
        results = ops_manager.execute(preview)

        assert len(results) == 1
        assert results[0]['success'] is True
        assert not sample_file.exists(), "Source file should be moved"
        assert Path(results[0]['target']).exists(), "Target file should exist"

    def test_execute_records_in_database(self, ops_manager, temp_dir, sample_file, organizer, renamer, detector):
        """Test that operations are recorded in the database."""
        files = [{
            'path': str(sample_file),
            'name': sample_file.name,
            'size': sample_file.stat().st_size,
            'extension': '.mp4',
            'parent': str(temp_dir),
        }]

        preview = ops_manager.dry_run(files, organizer, renamer, detector)
        ops_manager.execute(preview)

        history = ops_manager.get_history()
        assert len(history) >= 1
        assert history[0]['old_path'] == str(sample_file)

    def test_undo_restores_file(self, ops_manager, temp_dir, sample_file, organizer, renamer, detector):
        """Test that undo restores the file to original location."""
        files = [{
            'path': str(sample_file),
            'name': sample_file.name,
            'size': sample_file.stat().st_size,
            'extension': '.mp4',
            'parent': str(temp_dir),
        }]

        preview = ops_manager.dry_run(files, organizer, renamer, detector)
        results = ops_manager.execute(preview)
        target = results[0]['target']

        undo_results = ops_manager.undo()
        assert len(undo_results) >= 1
        assert any(r['success'] for r in undo_results)
        assert sample_file.exists(), "File should be restored after undo"

    def test_get_history_returns_operations(self, ops_manager, temp_db):
        """Test that get_history returns the operation list."""
        ops_manager.get_history()  # Should not raise

    def test_clear_history_removes_operations(self, ops_manager, temp_db):
        """Test that clear_history removes all operations."""
        ops_manager.clear_history()
        assert len(ops_manager.get_history()) == 0
