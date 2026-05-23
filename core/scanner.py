from pathlib import Path
from config.settings import MEDIA_EXTENSIONS


class Scanner:
    """Recursively scan folders for media files."""

    def scan_folder(self, folder_path: Path | str, progress_callback=None) -> list[dict]:
        """Scan a folder recursively for media files with optional progress callback."""
        path = Path(folder_path)

        if not path.is_dir():
            raise ValueError(f"Invalid path: {folder_path}")

        scanned_files = []
        self._scan_directory(path, scanned_files, progress_callback)

        return scanned_files

    def _scan_directory(self, directory: Path, scanned_files: list, progress_callback=None):
        """Recursively scan a directory."""
        try:
            for entry in directory.iterdir():
                if entry.name.startswith('.') or entry.name.startswith('~'):
                    continue

                if entry.is_file() and entry.suffix.lower() in MEDIA_EXTENSIONS:
                    file_info = {
                        'path': str(entry),
                        'name': entry.name,
                        'size': entry.stat().st_size,
                        'extension': entry.suffix.lower(),
                        'parent': str(entry.parent),
                    }
                    scanned_files.append(file_info)

                    if progress_callback:
                        try:
                            progress_callback(entry, None)
                        except Exception:
                            pass

                elif entry.is_dir():
                    self._scan_directory(entry, scanned_files, progress_callback)

        except PermissionError:
            pass
        except Exception:
            pass
