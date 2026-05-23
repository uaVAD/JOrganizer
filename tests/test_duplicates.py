import pytest
import tempfile
from pathlib import Path
from core.duplicates import DuplicateDetector


class TestDuplicateDetector:
    """Test cases for the DuplicateDetector module."""

    @pytest.fixture
    def detector(self):
        return DuplicateDetector()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_detect_duplicate_by_name(self, detector, temp_dir):
        """Test duplicate detection by filename."""
        existing = temp_dir / "test.mp4"
        existing.write_text("content")

        files = [{
            'name': 'test.mp4',
            'path': str(temp_dir / 'source' / 'test.mp4'),
            'size': 100,
            'extension': '.mp4',
            'parent': str(temp_dir / 'source'),
        }]

        duplicates = detector.check_duplicates(files, temp_dir)
        assert len(duplicates) >= 1

    def test_no_duplicate_different_names(self, detector, temp_dir):
        """Test that different filenames are not flagged as duplicates."""
        existing = temp_dir / "movie.mp4"
        existing.write_text("content")

        files = [{
            'name': 'movie2.mp4',
            'path': str(temp_dir / 'source' / 'movie2.mp4'),
            'size': 100000000,
            'extension': '.mp4',
            'parent': str(temp_dir / 'source'),
        }]

        duplicates = detector.check_duplicates(files, temp_dir)
        assert len(duplicates) == 0

    def test_hash_computes_sha256(self, detector, temp_dir):
        """Test that compute_hash generates valid SHA256 hash."""
        file_path = temp_dir / "test_file.txt"
        file_path.write_text("test content")

        hash_result = detector.compute_hash(str(file_path))
        assert len(hash_result) == 64  # SHA256 hex digest length
        assert hash_result != ''

    def test_hash_incompatible_file(self, detector):
        """Test hash returns empty string for nonexistent file."""
        hash_result = detector.compute_hash("/nonexistent/file.txt")
        assert hash_result == ''

    def test_mode_replace_resolves_as_replace(self, detector):
        """Test replace mode returns 'replace' resolution."""
        detector.mode = 'replace'
        result = detector._resolve({}, mode='replace')
        assert result == 'replace'

    def test_mode_skip_resolves_as_skip(self, detector):
        """Test skip mode returns 'skip' resolution."""
        detector.mode = 'skip'
        result = detector._resolve({}, mode='skip')
        assert result == 'skip'

    def test_mode_keep_both_resolves_as_keep_both(self, detector):
        """Test keep_both mode returns 'keep_both' resolution."""
        detector.mode = 'keep_both'
        result = detector._resolve({}, mode='keep_both')
        assert result == 'keep_both'
