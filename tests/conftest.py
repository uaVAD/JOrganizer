import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def organizer(temp_dir):
    """Create Organizer instance with temp destinations for all categories."""
    from core.organizer import Organizer
    return Organizer({
        'movie': temp_dir / 'Movies',
        'tv': temp_dir / 'TV Shows',
        'anime': temp_dir / 'Anime',
        'cartoon': temp_dir / 'Cartoons',
    })


@pytest.fixture
def renamer():
    """Create Renamer instance."""
    from core.renamer import Renamer
    return Renamer()


@pytest.fixture
def detector():
    """Create MediaDetector instance."""
    from core.detector import MediaDetector
    return MediaDetector()


@pytest.fixture
def scanner():
    """Create Scanner instance."""
    from core.scanner import Scanner
    return Scanner()
