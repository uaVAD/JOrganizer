import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detect duplicates using name, size, and optional hash."""

    def __init__(self, mode: str = 'ask'):
        self.mode = mode

    def check_duplicates(self, files: list[dict], destination: Path) -> list[dict]:
        """Check for duplicates. Returns list of duplicates with resolution."""
        duplicates = []
        existing_files = []

        if destination.exists():
            for f in destination.rglob('*'):
                if f.is_file():
                    existing_files.append(f)

        existing_names = {f.name.lower(): f for f in existing_files}

        for file_info in files:
            filename = file_info['name']

            if filename.lower() in existing_names:
                resolution = self._resolve(file_info, mode=self.mode)
                duplicates.append({
                    'file': file_info,
                    'resolution': resolution,
                })
                continue

            for existing_path in existing_files:
                try:
                    existing_size = existing_path.stat().st_size
                    if abs(existing_size - file_info['size']) < 1024:
                        resolution = self._resolve(file_info, mode='ask')
                        duplicates.append({
                            'file': file_info,
                            'resolution': resolution,
                        })
                        break
                except OSError:
                    pass

        return duplicates

    def _resolve(self, file_info: dict, mode: str = 'ask') -> str:
        """Resolve duplicate conflict."""
        if mode == 'replace':
            return 'replace'
        elif mode == 'skip':
            return 'skip'
        elif mode == 'keep_both':
            return 'keep_both'
        else:  # ask
            # Default to ask user
            return 'ask'

    def compute_hash(self, filepath: str, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash for file content comparison."""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    sha256.update(chunk)
            return sha256.hexdigest()
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot hash file {filepath}: {e}")
            return ''
