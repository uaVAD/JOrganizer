import pytest
from core.detector import MediaDetector


class TestDetector:
    """Test cases for the MediaDetector module."""

    @pytest.fixture
    def detector(self):
        return MediaDetector()

    def test_detect_tv_show_with_season_episode(self, detector):
        """Test detection of TV show with season/episode pattern."""
        result = detector.detect("My.Show.S01E05.1080p.BluRay.mp4", quick=True)

        assert result['type'] == 'tv'
        assert result['season'] == 1
        assert result['episode'] == 5
        assert result['confidence'] == 0.85
        assert result['level'] == 1
        assert result['method'] == 'regex'
        assert result['title'] == 'My Show'
        assert result['quality'] == '1080p'
        assert result['source'] == 'BluRay'

    def test_detect_tv_show_with_x_format(self, detector):
        """Test detection using X format (e.g., S01X05)."""
        result = detector.detect("Show.Name.S01X05.WEBRip.mp4", quick=True)

        assert result['type'] == 'tv'
        assert result['season'] == 1
        assert result['episode'] == 5

    def test_detect_movie_with_year(self, detector):
        """Test detection of movie by year."""
        result = detector.detect("Movie.Title.2025.1080p.WEB-DL.mkv", quick=True)

        assert result['type'] == 'movie'
        assert result['year'] == 2025
        assert result['title'] == 'Movie Title'
        assert result['season'] is None
        assert result['episode'] is None

    def test_detect_anime_by_keyword(self, detector):
        """TV pattern wins over anime keyword at file level; TMDB corrects at folder level."""
        result = detector.detect("Attack.on.Titan.S01E01.720p.mp4", quick=True)

        assert result['type'] == 'tv'
        assert result['season'] == 1
        assert result['episode'] == 1

    def test_detect_unknown_media_type(self, detector):
        """Test that unknown media returns type='unknown' with level=3."""
        result = detector.detect("Mystery.File.Name.mp4", quick=True)

        assert result['type'] == 'unknown'
        assert result['level'] == 3
        assert result['method'] == 'user_confirmation'
        assert result['confidence'] == 0

    def test_detect_anime_with_brackets(self, detector):
        """TV pattern wins over bracket patterns at file level; TMDB corrects at folder level."""
        result = detector.detect("[SubGroup] Anime.Name - S02E03 [1080p].mkv", quick=True)

        assert result['type'] == 'tv'
        assert result['season'] == 2
        assert result['episode'] == 3
