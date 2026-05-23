import logging
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config.settings import MEDIA_EXTENSIONS

logger = logging.getLogger(__name__)


class FileWatchHandler(FileSystemEventHandler):
    """Handle file system events in watched folders."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.writing_files = {}

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle_file(event.src_path)

    def _handle_file(self, filepath: str):
        """Detect file and wait until download is complete."""
        filepath = Path(filepath)

        if filepath.suffix.lower() not in MEDIA_EXTENSIONS:
            return

        if self._is_writing(filepath):
            return

        # File is stable - trigger callback
        logger.info(f"File ready: {filepath}")
        self.callback(str(filepath))

        # Remove from tracking
        self.writing_files.pop(str(filepath), None)

    def _is_writing(self, filepath: Path) -> bool:
        """Check if file size is still changing."""
        try:
            current_size = filepath.stat().st_size
            filepath_str = str(filepath)

            if filepath_str in self.writing_files:
                prev_size = self.writing_files[filepath_str].get('size', 0)
                if current_size == prev_size:
                    return False
                else:
                    self.writing_files[filepath_str]['size'] = current_size
                    self.writing_files[filepath_str]['time'] = time.time()
                    return True

            # First time seeing this file - track it
            self.writing_files[filepath_str] = {
                'size': current_size,
                'time': time.time(),
            }
            return True

        except OSError:
            return False


class AutoWatcher:
    """Monitor folders for new files."""

    def __init__(self):
        self.observer = Observer()
        self.handlers = []
        self.watched_folders = []

    def add_folder(self, folder_path: str, callback):
        """Add a folder to watch."""
        handler = FileWatchHandler(callback)
        self.observer.schedule(handler, folder_path, recursive=True)
        self.handlers.append(handler)
        self.watched_folders.append(folder_path)
        logger.info(f"Watching: {folder_path}")

    def start(self):
        """Start watching."""
        self.observer.start()
        logger.info("Auto watcher started")

    def stop(self):
        """Stop watching."""
        self.observer.stop()
        logger.info("Auto watcher stopped")

    def join(self, timeout=3):
        """Wait for observer thread to finish."""
        self.observer.join(timeout)

    def is_running(self) -> bool:
        return self.observer.is_running
