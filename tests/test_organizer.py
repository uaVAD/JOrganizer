import pytest
import tempfile
from pathlib import Path
from core.organizer import Organizer


class TestOrganizer:
    """Test cases for the Organizer module."""

    @pytest.fixture
    def dest_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def organizer(self, dest_dir):
        return Organizer({
            'movie': dest_dir / 'Movies',
            'tv': dest_dir / 'TV Shows',
            'anime': dest_dir / 'Anime',
            'cartoon': dest_dir / 'Cartoons',
        })

    def test_organizer_stores_category_dirs(self, organizer):
        assert organizer.category_dirs['movie'].name == 'Movies'
        assert organizer.category_dirs['tv'].name == 'TV Shows'
        assert organizer.category_dirs['anime'].name == 'Anime'
        assert organizer.category_dirs['cartoon'].name == 'Cartoons'

    def test_get_target_path_movie(self, organizer):
        detection = {
            'type': 'movie',
            'title': 'Inception',
            'year': 2010,
        }
        result = organizer.get_target_path(detection, "Inception (2010).mp4")

        expected = organizer.category_dirs['movie'] / "Inception (2010)" / "Inception (2010).mp4"
        assert str(result) == str(expected)

    def test_get_target_path_tv_show(self, organizer):
        detection = {
            'type': 'tv',
            'title': 'Breaking Bad',
            'season': 1,
            'episode': 5,
        }
        result = organizer.get_target_path(detection, "Breaking Bad - S01E05.mp4")

        expected = organizer.category_dirs['tv'] / "Breaking Bad" / "Season 01" / "Breaking Bad - S01E05.mp4"
        assert str(result) == str(expected)

    def test_get_target_path_anime(self, organizer):
        detection = {
            'type': 'anime',
            'title': 'Attack on Titan',
            'season': 1,
            'episode': 1,
        }
        result = organizer.get_target_path(detection, "Attack on Titan - S01E01.mkv")

        expected = organizer.category_dirs['anime'] / "Attack on Titan" / "Season 01" / "Attack on Titan - S01E01.mkv"
        assert str(result) == str(expected)

    def test_get_target_path_unknown_falls_back(self, organizer):
        detection = {
            'type': 'unknown',
            'title': 'Mystery Video',
        }
        result = organizer.get_target_path(detection, "mystery.mkv")

        expected = organizer.category_dirs['movie'] / "Mystery Video" / "mystery.mkv"
        assert str(result) == str(expected)

    def test_get_target_path_movie_without_year(self, organizer):
        detection = {
            'type': 'movie',
            'title': 'The Matrix',
            'year': None,
        }
        result = organizer.get_target_path(detection, "The Matrix.mp4")

        expected = organizer.category_dirs['movie'] / "The Matrix" / "The Matrix.mp4"
        assert str(result) == str(expected)
