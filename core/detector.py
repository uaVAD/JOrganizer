import re
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


class MediaDetector:
    """Detect media type from filename using multiple levels."""

    # Regex patterns for detection
    TV_PATTERN = re.compile(
        r'(?:s|season)\s*(\d{1,2})\s*[xe]\s*(\d{1,2})'
        r'|(\d{1,2})[x](\d{1,2})'
        r'|(?:season\s*\d{1,2}\s+episode\s*\d{1,2})',
        re.IGNORECASE
    )

    SEASON_ONLY = re.compile(r'(?:s|season)\s*(\d{1,2})(?:\s|$|[.\-])', re.IGNORECASE)

    ANIME_EPISODE = re.compile(r'[-_\s]+(\d{1,3})(?=\s*(?:\[|\.|$))', re.IGNORECASE)
    ANIME_PATTERN = re.compile(
        r'\.anime\.'
        r'|(?:attack[\s._-]+on[\s._-]+titan|one[\s._-]+piece|naruto|bleach|dragon[\s._-]+ball|death[\s._-]+note|hunter[\s._-]+x[\s._-]+hunter|my[\s._-]+hero[\s._-]+academia|demon[\s._-]+slayer|one[\s._-]+punch[\s._-]+man|steins[\s._-]+gate|code[\s._-]+geass|fullmetal[\s._-]+alchemist|cowboy[\s._-]+bebop|sailor[\s._-]+moon|pocket[\s._-]+monsters|pokemon|fairy[\s._-]+tail|boku[\s._-]+no[\s._-]+hero[\s._-]+academia|shingeki[\s._-]+no[\s._-]+kyojin|boku[\s._-]+no[\s._-]+psycho[\s._-]+denda|jojo)',
        re.IGNORECASE
    )

    QUALITY_PATTERN = re.compile(r'\b(2160p|1080p|720p|480p|4k|3d)\b', re.IGNORECASE)
    SOURCE_PATTERN = re.compile(r'\b(WEBRip|BluRay|WEB-DL|HDTV|DVDRip|HDRip|CAM|TS|R5|DVD|BD|REMUX|IMAX)\b', re.IGNORECASE)

    def __init__(self):
        from api.metadata import MetadataAPI
        self.api_detector = MetadataAPI()

    NON_LATIN = re.compile(r'[^\x00-\x7F]')

    def _needs_enrichment(self, filename: str) -> bool:
        return bool(self.NON_LATIN.search(filename))

    @staticmethod
    def _parent_info(filepath: str) -> dict:
        parent = Path(filepath).parent.name
        m = re.search(r'\s(\d{1,2})$', parent)
        if m:
            return {'base': parent[:m.start()], 'season': int(m.group(1))}
        return {'base': parent, 'season': None}

    def detect(self, filepath: str | Path, quick: bool = False) -> dict:
        """Detect media type using all levels. Returns result dict."""
        path = Path(filepath)
        filename = path.stem
        parent = self._parent_info(filepath)

        # Level 1: Regex matching
        level1_result = self._level1_regex(filename, filepath, parent)

        # Inject parent folder season if file level 1 didn't get a real season
        if level1_result and parent['season'] is not None:
            has_explicit = 'season' in filename.lower() or re.search(r'[sS]\d{1,2}[eEx]', filename)
            if level1_result.get('season') is None or (
                level1_result['season'] == 1 and not has_explicit
            ):
                level1_result['season'] = parent['season']
            if parent['base'].lower() in level1_result['title'].lower():
                level1_result['title'] = re.sub(
                    rf'\s{parent["season"]}$', '', level1_result['title']
                )

        # Level 2: API lookup for English title enrichment
        api_result = None
        if not quick and self._needs_enrichment(filename):
            api_result = self._level2_api_lookup(filename, filepath)

        if level1_result and api_result and api_result.get('title'):
            level1_result['title'] = api_result['title']
            level1_result['year'] = api_result.get('year', level1_result.get('year'))
            level1_result['confidence'] = max(
                level1_result.get('confidence', 0),
                api_result.get('confidence', 0)
            )
            level1_result['level'] = 2
            level1_result['method'] = 'regex+api'
            logger.debug(f"Level 1+API enriched: {api_result['title']} for {filename}")
            return level1_result

        if level1_result:
            logger.debug(f"Level 1 detected: {level1_result['type']} for {filename}")
            return level1_result

        if api_result:
            logger.debug(f"Level 2 detected: {api_result['type']} for {filename}")
            return api_result

        # Level 3: Ask user
        return {
            'type': 'unknown',
            'title': path.stem,
            'season': None,
            'episode': None,
            'year': None,
            'quality': None,
            'source': None,
            'confidence': 0,
            'level': 3,
            'method': 'user_confirmation',
        }

    def _level1_regex(self, filename: str, filepath: str, parent: dict | None = None) -> dict | None:
        """Level 1: Regex pattern matching."""
        has_episode_num = self.ANIME_EPISODE.search(filename)
        is_anime = bool(self.ANIME_PATTERN.search(filename) or has_episode_num)
        
        # Check for TV show pattern
        tv_match = self.TV_PATTERN.search(filename)
        if tv_match:
            season = episode = None
            if tv_match.group(1):
                season, episode = tv_match.group(1), tv_match.group(2)
            elif tv_match.group(3):
                season, episode = tv_match.group(3), tv_match.group(4)

            quality = self.QUALITY_PATTERN.search(filename)
            source = self.SOURCE_PATTERN.search(filename)

            return {
                'type': 'tv',
                'title': self._clean_title(filename, season, episode),
                'season': int(season) if season else None,
                'episode': int(episode) if episode else None,
                'year': self._extract_year(filename),
                'quality': quality.group(1) if quality else None,
                'source': source.group(1) if source else None,
                'confidence': 0.85,
                'level': 1,
                'method': 'regex',
            }

        # Check for anime pattern (standalone, no TV season/episode)
        if is_anime:
            season = episode = None
            season_only = self.SEASON_ONLY.search(filename)
            if season_only:
                season = season_only.group(1)
            episode_match = self.ANIME_EPISODE.search(filename)
            if episode_match:
                episode = episode_match.group(1)
                filename = filename[:episode_match.start()] + filename[episode_match.end():]
            if episode and not season:
                season = parent['season'] if (parent and parent['season'] is not None) else 1
                if parent and parent['season'] is not None:
                    filename = re.sub(rf'\s{parent["season"]}$', '', filename)

            quality = self.QUALITY_PATTERN.search(filename)
            source = self.SOURCE_PATTERN.search(filename)

            return {
                'type': 'anime',
                'title': self._clean_title(filename, season, episode),
                'season': int(season) if season else None,
                'episode': int(episode) if episode else None,
                'year': self._extract_year(filename),
                'quality': quality.group(1) if quality else None,
                'source': source.group(1) if source else None,
                'confidence': 0.7,
                'level': 1,
                'method': 'regex',
            }

        # Check if movie (has year or looks like movie name)
        year = self._extract_year(filename)
        if year:
            quality = self.QUALITY_PATTERN.search(filename)
            source = self.SOURCE_PATTERN.search(filename)

            return {
                'type': 'movie',
                'title': self._clean_title(filename, None, None),
                'season': None,
                'episode': None,
                'year': year,
                'quality': quality.group(1) if quality else None,
                'source': source.group(1) if source else None,
                'confidence': 0.75,
                'level': 1,
                'method': 'regex',
            }

        return None

    def _level2_api_lookup(self, filename: str, filepath: str) -> dict | None:
        """Level 2: Metadata API lookup (TMDB/TVDB/OMDb)."""
        try:
            import asyncio
            clean = self._clean_for_api(filename)
            if not clean:
                return None
            result = asyncio.run(self.api_detector.search(clean))
            if result:
                return {
                    'type': result['type'],
                    'title': result['title'],
                    'season': result.get('season'),
                    'episode': result.get('episode'),
                    'year': result.get('year'),
                    'quality': None,
                    'source': None,
                    'confidence': result.get('confidence', 0.9),
                    'level': 2,
                    'method': 'api',
                    'tmdb_id': result.get('tmdb_id'),
 
                }
        except Exception as e:
            logger.warning(f"API lookup failed for '{filename}': {e}")

        return None

    def _clean_for_api(self, filename: str) -> str:
        cleaned = re.sub(r'[sS]\d{1,2}[eEx]\d{1,2}', '', filename)
        cleaned = re.sub(r'\d{1,2}x\d{1,2}', '', cleaned)
        cleaned = re.sub(r'season\s*\d+\s*episode\s*\d+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'[-_\s]+\d{1,3}$', '', cleaned)
        cleaned = re.sub(r'(2160p|1080p|720p|480p|4k|3d|WEBRip|BluRay|WEB-DL|HDTV|DVDRip|HDRip|CAM|TS|R5|DVD|BD|REMUX|IMAX|Complete|Batch)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[.*?\]', '', cleaned)
        cleaned = re.sub(r'\(.*?\)', '', cleaned)
        cleaned = re.sub(r'[-_.\s]+', ' ', cleaned).strip()
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        cleaned = re.sub(r'\b(19|20)\d{2}\b', '', cleaned).strip()
        cleaned = re.sub(r'\s+\d{1,2}$', '', cleaned).strip()
        return cleaned if cleaned else filename

    def _clean_title(self, filename: str, season: str | None, episode: str | None) -> str:
        """Clean filename to extract title."""
        cleaned = re.sub(r'[sx]\d{1,2}[xe]\d{1,2}', '', filename, flags=re.IGNORECASE)
        cleaned = re.sub(r'\d{1,2}x\d{1,2}', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'season\s*\d+\s*episode\s*\d+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(2160p|1080p|720p|480p|WEBRip|BluRay|WEB-DL|HDTV|\d{4})', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[.*?\]', '', cleaned)
        cleaned = re.sub(r'\(.*?\)', '', cleaned)
        cleaned = re.sub(r'[-_\.\s]+', ' ', cleaned).strip()
        cleaned = cleaned.title().strip()
        return cleaned

    def _extract_year(self, filename: str) -> int | None:
        """Extract year from filename."""
        match = re.search(r'(19|20)\d{2}', filename)
        if match:
            return int(match.group(0))
        return None
