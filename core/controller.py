import logging
from pathlib import Path
from core.detector import MediaDetector
from core.renamer import Renamer
from core.organizer import Organizer
from core.operations import OperationsManager
from core.folder_analyzer import FolderAnalyzer
from monitoring.watcher import AutoWatcher

logger = logging.getLogger(__name__)


class AppController:
    """Coordinates business logic between core modules. UI-agnostic."""

    def __init__(self, db):
        self.detector = MediaDetector()
        self.renamer = Renamer()
        self.organizer = None
        self.operations_manager = OperationsManager(db)
        self.analyzer = FolderAnalyzer()
        self.watcher = AutoWatcher()
        self.watcher_running = False

    def set_category_dirs(self, dirs: dict[str, Path]):
        if dirs:
            self.organizer = Organizer(dirs)
            self.operations_manager.set_pipeline(self.detector, self.renamer, self.organizer)
        else:
            self.organizer = None
        return self.organizer is not None

    def analyze_folder(self, source_path: Path, progress_callback=None) -> dict:
        return self.analyzer.analyze(source_path, progress_callback)

    def preview(self, files: list, dest: Path) -> list[dict]:
        return self.operations_manager.preview(files, dest)

    def execute_preview(self, preview: list) -> list[dict]:
        return self.operations_manager.execute(preview)

    def undo(self, operation_id: int | None = None) -> list[dict]:
        return self.operations_manager.undo(operation_id)

    def undo_last(self):
        return self.operations_manager.undo_last()

    def get_history(self) -> list[dict]:
        return self.operations_manager.get_history()

    def clear_history(self):
        self.operations_manager.clear_history()

    def start_watch(self, folder_path: str, callback):
        self.watcher.add_folder(folder_path, callback)
        self.watcher.start()
        self.watcher_running = True
        logger.info(f"Auto watch started for: {folder_path}")

    def stop_watch(self):
        if self.watcher_running:
            self.watcher.stop()
            self.watcher_running = False
            logger.info("Auto watch stopped")
            self.watcher.join(timeout=3)

    def detect_file(self, filepath: str, quick: bool = False) -> dict:
        return self.detector.detect(filepath, quick=quick)
