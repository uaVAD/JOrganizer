import pytest
from core.renamer import Renamer


class TestRenamer:
    """Test cases for the Renamer module."""

    @pytest.fixture
    def renamer(self):
        return Renamer()

    def test_rename_movie(self, renamer):
        """Test movie renaming with year."""
        result = renamer.rename_movie("Inception", 2010)
        assert result == "Inception (2010)"

    def test_rename_movie_without_year(self, renamer):
        """Test movie renaming without year."""
        result = renamer.rename_movie("The Matrix")
        assert result == "The Matrix"

    def test_rename_tv_show(self, renamer):
        """Test TV show renaming with season/episode."""
        result = renamer.rename_tv("Breaking Bad", 1, 5)
        assert result == "Breaking Bad - S01E05"

    def test_rename_tv_show_with_episode_title(self, renamer):
        """Test TV show renaming with episode title."""
        result = renamer.rename_tv("Breaking Bad", 1, 5, episode_title="Cancer Man")
        assert result == "Breaking Bad - S01E05 - Cancer Man"

    def test_rename_anime(self, renamer):
        """Test anime renaming with season/episode."""
        result = renamer.rename_anime("Attack on Titan", 1, 1)
        assert result == "Attack on Titan - S01E01"

    def test_generate_new_filename_movie(self, renamer):
        """Test generate_new_filename for movie."""
        detection_result = {
            'type': 'movie',
            'title': 'Inception',
            'year': 2010,
            'season': None,
            'episode': None,
        }
        result = renamer.generate_new_filename(detection_result, "test.mp4")
        assert result == "Inception (2010).mp4"

    def test_generate_new_filename_tv(self, renamer):
        """Test generate_new_filename for TV show."""
        detection_result = {
            'type': 'tv',
            'title': 'Breaking Bad',
            'season': 1,
            'episode': 5,
        }
        result = renamer.generate_new_filename(detection_result, "test.avi")
        assert result == "Breaking Bad - S01E05.avi"

    def test_generate_new_filename_unknown(self, renamer):
        """Test generate_new_filename preserves original name for unknown type."""
        detection_result = {
            'type': 'unknown',
            'title': 'Unknown File',
        }
        result = renamer.generate_new_filename(detection_result, "unknown.mkv")
        assert result == "unknown.mkv"

    def test_rename_preserves_extension(self, renamer):
        """Test that generated filename preserves original extension."""
        detection_result = {
            'type': 'movie',
            'title': 'Test Movie',
            'year': 2025,
        }
        for ext in ['.mkv', '.mp4', '.avi', '.mov', '.webm']:
            result = renamer.generate_new_filename(detection_result, f"test{ext}")
            assert result.endswith(ext), f"Extension {ext} should be preserved"
