import pytest
import tempfile
from pathlib import Path
from core.scanner import Scanner


class TestScanner:
    """Test cases for the Scanner module."""

    @pytest.fixture
    def scanner(self):
        return Scanner()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def media_files_dir(self, temp_dir):
        """Create a temp directory with sample media files."""
        # Create movie file
        movie = temp_dir / "Movie.2025.1080p.BluRay.mkv"
        movie.write_text("dummy content")

        # Create TV show file
        tv = temp_dir / "Show.Name.S01E05.720p.WEBRip.mp4"
        tv.write_text("dummy content")

        # Create non-media file
        text_file = temp_dir / "readme.txt"
        text_file.write_text("not media")

        # Create subdirectory with another media file
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        anime = subdir / "Anime.Title.S02E03.BluRay.mp4"
        anime.write_text("dummy content")

        return temp_dir

    def test_scan_returns_media_files_only(self, scanner, media_files_dir):
        """Test that scanner returns only media files, not text files."""
        results = scanner.scan_folder(str(media_files_dir))

        assert len(results) == 3  # 2 .mp4 + 1 .mkv
        for file_info in results:
            assert file_info['extension'].lower() in ['.mkv', '.mp4']
            assert Path(file_info['path']).exists()

    def test_scan_recursively_scans_subdirectories(self, scanner, media_files_dir):
        """Test that scanner finds files in subdirectories."""
        results = scanner.scan_folder(str(media_files_dir))

        subpath = str(media_files_dir / "subdir")
        found_in_subdir = any(subpath in file['path'] for file in results)
        assert found_in_subdir, "Scanner should find files in subdirectories"

    def test_scan_returns_correct_file_metadata(self, scanner, media_files_dir):
        """Test that scanner returns correct metadata for each file."""
        results = scanner.scan_folder(str(media_files_dir))

        first_file = next(f for f in results if f['name'] == "Movie.2025.1080p.BluRay.mkv")
        assert first_file['name'] == "Movie.2025.1080p.BluRay.mkv"
        assert first_file['extension'] == ".mkv"
        assert first_file['size'] > 0
        assert first_file['parent'] == str(media_files_dir)

    def test_scan_invalid_path_raises_error(self, scanner):
        """Test that scanner raises ValueError for invalid paths."""
        with pytest.raises(ValueError, match="Invalid path"):
            scanner.scan_folder("/nonexistent/path/that/does/not/exist")

    def test_scan_empty_directory(self, scanner, temp_dir):
        """Test that scanner returns empty list for empty directory."""
        results = scanner.scan_folder(str(temp_dir))
        assert results == []

    def test_scan_ignores_hidden_files(self, scanner, temp_dir):
        """Test that scanner ignores files starting with '.'."""
        hidden = temp_dir / ".hidden_movie.mp4"
        hidden.write_text("dummy")

        normal = temp_dir / "normal.mp4"
        normal.write_text("dummy")

        results = scanner.scan_folder(str(temp_dir))
        assert len(results) == 1
        assert results[0]['name'] == "normal.mp4"
