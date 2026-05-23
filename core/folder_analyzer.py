import re
import logging
from pathlib import Path
from collections import defaultdict
from core.detector import MediaDetector
from core.scanner import Scanner

logger = logging.getLogger(__name__)


class FolderAnalyzer:
    """Analyze folder structure to identify media content."""

    def __init__(self):
        self.detector = MediaDetector()
        self.scanner = Scanner()
        self._tmdb_api = None
        self._anilist_api = None

    def _get_tmdb_api(self):
        if self._tmdb_api is None:
            from api.metadata import MetadataAPI
            self._tmdb_api = MetadataAPI()
        return self._tmdb_api

    def _get_anilist_api(self):
        if self._anilist_api is None:
            from api.anilist import AniListAPI
            self._anilist_api = AniListAPI()
        return self._anilist_api

    def analyze(self, source_path: Path, progress_callback=None) -> dict:
        """Scan and analyze a source folder. Returns structured tree:
        {
            'path': Path,
            'name': str,
            'type': 'root',
            'children': [CategoryNode | FolderNode, ...],
        }
        CategoryNode (intermediate level for first-level subdirs):
        {
            'path': Path,
            'name': str,
            'media_type': str,
            'children': [FolderNode, ...],
            'files': [],
        }
        FolderNode:
        {
            'path': Path,
            'name': str,
            'media_type': str,
            'tmdb_title': str | None,
            'tmdb_id': int | None,
            'year': int | None,
            'confidence': float,
            'files': [FileNode, ...],
        }
        FileNode:
        {
            'path': Path,
            'name': str,
            'size': int,
            'type': str,
            'title': str,
            'season': int | None,
            'episode': int | None,
            'quality': str | None,
            'confidence': float,
        }
        """
        raw_files = self.scanner.scan_folder(source_path)
        grouped = self._group_by_parent(raw_files)
        folders = []
        total = max(len(grouped), 1)

        for i, (parent_str, file_infos) in enumerate(grouped.items()):
            parent = Path(parent_str)
            folder_result = self._analyze_folder(parent, file_infos)

            if file_infos:
                folders.append(folder_result)

            if progress_callback:
                progress_callback(int((i + 1) / total * 100), folder_result['name'])

        # Group folders by first-level subfolder of source (category)
        category_map = defaultdict(list)
        for f in folders:
            try:
                rel = f['path'].relative_to(source_path)
                cat = rel.parts[0] if rel.parts else None
            except ValueError:
                cat = None
            if cat:
                category_map[cat].append(f)
            else:
                category_map['__flat__'].append(f)

        if len(category_map) <= 1:
            children = folders
        else:
            children = []
            flat_items = category_map.pop('__flat__', [])
            children.extend(flat_items)
            for cat_name in sorted(category_map):
                cat_folders = category_map[cat_name]
                cat_path = source_path / cat_name
                # Flatten single-child categories (no redundant wrapping)
                if len(cat_folders) == 1:
                    children.append(cat_folders[0])
                    continue
                from collections import Counter
                type_counts = Counter(f['media_type'] for f in cat_folders)
                cat_type = type_counts.most_common(1)[0][0]
                children.append({
                    'path': cat_path,
                    'name': cat_name,
                    'media_type': cat_type,
                    'children': cat_folders,
                    'files': [],
                })

        return {
            'path': source_path,
            'name': source_path.name,
            'type': 'root',
            'children': children,
        }

    SUBFOLDER = re.compile(r'^(?:Season|Saison|Temporada|Volume|Vol)\s*\d{1,2}$|^Specials?$', re.IGNORECASE)

    def _group_by_parent(self, file_infos: list[dict]) -> dict[str, list[dict]]:
        grouped = defaultdict(list)
        for fi in file_infos:
            parent = Path(fi.get('parent', str(Path(fi['path']).parent)))
            if self.SUBFOLDER.match(parent.name):
                parent = parent.parent
            grouped[str(parent)].append(fi)
        return dict(grouped)

    def _analyze_folder(self, folder_path: Path, file_infos: list[dict]) -> dict:
        folder_name = folder_path.name
        files = []
        media_types_in_files = set()

        for fi in file_infos:
            fp = Path(fi['path'])
            result = self.detector.detect(str(fp), quick=True)
            media_types_in_files.add(result['type'])
            files.append({
                'path': fp,
                'name': fp.name,
                'size': fi.get('size', 0),
                'type': result['type'],
                'title': result.get('title', ''),
                'season': result.get('season'),
                'episode': result.get('episode'),
                'quality': result.get('quality'),
                'confidence': result.get('confidence', 0),
            })

        # Determine folder-level media type
        folder_result = self._detect_folder_type(folder_name, files, media_types_in_files)

        return {
            'path': folder_path,
            'name': folder_name,
            'media_type': folder_result['type'],
            'tmdb_title': folder_result.get('tmdb_title'),
            'tmdb_id': folder_result.get('tmdb_id'),
            'year': folder_result.get('year'),
            'confidence': folder_result.get('confidence', 0),
            'files': files,
        }

    def _detect_folder_type(self, folder_name: str, files: list, file_types: set) -> dict:
        """Determine folder media type: TMDB first, then AniList strict fallback."""
        year_match = re.search(r'\b(19\d\d|20\d\d)\b', folder_name)
        year = int(year_match.group(1)) if year_match else None
        cleaned = self._clean_for_tmdb(folder_name, year)

        # 1. TMDB with original + year
        api_result = self._try_tmdb(cleaned, year)
        if api_result:
            return api_result

        # 2. TMDB with original, no year
        api_result = self._try_tmdb(cleaned, None)
        if api_result:
            return api_result

        # 3. AniList fallback (exact title match only)
        api_result = self._try_anilist(cleaned)
        if api_result:
            return api_result

        return {'type': 'unknown', 'tmdb_title': None, 'tmdb_id': None, 'year': None, 'confidence': 0.0}

    def _clean_for_tmdb(self, name: str, year: int | None = None) -> str:
        """Clean folder name for TMDB search."""
        cleaned = re.sub(r'\b(2160p|1080p|720p|480p|4k|3d|WEBRip|BluRay|WEB-DL|HDTV|DVDRip|HDRip|CAM|TS|R5|DVD|BD|REMUX|IMAX|Complete|Batch)\b', '', name, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[.*?\]', '', cleaned)
        cleaned = re.sub(r'\(.*?\)', '', cleaned)
        cleaned = re.sub(r'[-_.\s]+', ' ', cleaned).strip()
        cleaned = re.sub(r'\s+(Season|Saison|Temporada)\s*\d+$', '', cleaned, flags=re.IGNORECASE).strip()
        if year:
            cleaned = re.sub(rf'\b{year}\b', '', cleaned).strip()
        return cleaned if cleaned else name

    def _try_tmdb(self, title: str, year: int | None = None) -> dict | None:
        """Try TMDB lookup for a title."""
        if not title:
            return None
        try:
            import asyncio
            api = self._get_tmdb_api()
            result = asyncio.run(api.search(title, year))
            if result:
                return {
                    'type': result['type'],
                    'tmdb_title': result['title'],
                    'tmdb_id': result.get('tmdb_id'),
                    'year': result.get('year'),
                    'confidence': result.get('confidence', 0.9),
                }
        except Exception as e:
            logger.warning(f"TMDB lookup failed for '{title}': {e}")
        return None

    def _try_anilist(self, title: str) -> dict | None:
        """Try AniList lookup for anime titles."""
        if not title:
            return None
        try:
            import asyncio
            api = self._get_anilist_api()
            result = asyncio.run(api.search(title))
            if result:
                return {
                    'type': result['type'],
                    'tmdb_title': result['title'],
                    'tmdb_id': None,
                    'year': result.get('year'),
                    'confidence': result.get('confidence', 0.8),
                }
        except Exception as e:
            logger.warning(f"AniList lookup failed for '{title}': {e}")
        return None
