import shutil
import logging
from datetime import datetime
from pathlib import Path
from database import Database

logger = logging.getLogger(__name__)


class OperationsManager:
    """Manage file operations with dry run and undo support."""

    def __init__(self, db: Database):
        self.db = db
        self.detector = None
        self.renamer = None
        self.organizer = None

    def set_pipeline(self, detector, renamer, organizer):
        """Set the core pipeline components for preview and execution."""
        self.detector = detector
        self.renamer = renamer
        self.organizer = organizer

    def _normalize_files(self, files: list) -> list[dict]:
        """Convert mixed file inputs (Path or dict) to uniform dicts."""
        result = []
        for f in files:
            if isinstance(f, Path):
                result.append({'path': str(f), 'name': f.name})
            elif isinstance(f, str):
                p = Path(f)
                result.append({'path': f, 'name': p.name})
            elif isinstance(f, dict):
                result.append(f)
        return result

    def preview(self, files: list, destination: Path | str) -> list[dict]:
        """Simulate operations without making changes. Returns preview."""
        file_list = self._normalize_files(files)
        dest = Path(destination)
        preview = []

        for file_info in file_list:
            try:
                src_path = Path(file_info['path'])
                new_name = src_path.name
                target = dest / src_path.parent.name / new_name

                if self.detector and self.renamer and self.organizer:
                    result = self.detector.detect(file_info['path'])
                    new_name = self.renamer.generate_new_filename(result, file_info['path'])
                    target = self.organizer.get_target_path(result, new_name)

                det_result = result if self.detector else None

                preview.append({
                    'source': str(src_path),
                    'dest': str(target),
                    'name': src_path.name,
                    'type': det_result.get('type', 'unknown') if det_result else 'unknown',
                    'detection': det_result,
                })
            except Exception as e:
                logger.error(f"Preview failed for {file_info['path']}: {e}")
                preview.append({
                    'source': file_info.get('path', ''),
                    'dest': None,
                    'name': Path(file_info.get('path', '')).name,
                    'type': 'unknown',
                    'detection': None,
                    'error': str(e),
                })

        return preview

    def dry_run(self, files: list[dict], organizer, renamer, detector) -> list[dict]:
        """Simulate operations using explicit pipeline. Delegates to preview()."""
        old_detector = self.detector
        old_renamer = self.renamer
        old_organizer = self.organizer
        self.set_pipeline(detector, renamer, organizer)

        results = self.preview(files, Path())

        self.set_pipeline(old_detector, old_renamer, old_organizer)

        return [{
            'original': r['source'],
            'target': r['dest'],
            'name': r['name'],
            'type': r['type'],
            'result': r['detection'],
            'new_filename': Path(r['dest']).name if r['dest'] else None,
        } for r in results]

    def execute(self, preview: list[dict], force: bool = False) -> list[dict]:
        """Execute operations from preview. Returns results."""
        results = []

        for item in preview:
            original = item.get('source', item.get('original'))
            target = item.get('dest', item.get('target'))

            if not target:
                results.append({'original': original, 'success': False, 'error': item.get('error', 'No target path')})
                continue

            try:
                timestamp = datetime.now().isoformat()
                self.db.add_operation(original, target, timestamp)

                target_path = Path(target)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(original), str(target))

                results.append({'original': original, 'target': target, 'success': True})
                logger.info(f"Moved: {original} -> {target}")

            except Exception as e:
                logger.error(f"Failed to move {original}: {e}")
                results.append({'original': original, 'target': target, 'success': False, 'error': str(e)})

        return results

    def undo_last(self):
        """Undo the last operation."""
        operations = self.db.get_all_operations()
        if not operations:
            return None
        last_op = operations[0]
        return self._undo_operation(last_op)

    def undo(self, operation_id: int | None = None) -> list[dict]:
        """Undo operations. If operation_id is None, undo all."""
        results = []

        if operation_id:
            operations = [self.db.get_operation(operation_id)]
            operations = [op for op in operations if op is not None]
        else:
            operations = self.db.get_all_operations()

        for op in operations:
            results.append(self._undo_operation(op))

        return results

    def _undo_operation(self, op: dict) -> dict:
        """Undo a single operation."""
        op_id = op['id']
        old_path = op['old_path']
        new_path = op['new_path']

        try:
            old_p = Path(old_path)
            new_p = Path(new_path)

            if new_p.exists():
                old_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(new_p), str(old_p))
                self.db.delete_operation(op_id)
                return {'operation_id': op_id, 'success': True, 'restored': old_path}
            else:
                return {'operation_id': op_id, 'success': False, 'error': f"File not found: {new_path}"}

        except Exception as e:
            logger.error(f"Undo failed for operation {op_id}: {e}")
            return {'operation_id': op_id, 'success': False, 'error': str(e)}

    def get_history(self) -> list[dict]:
        """Get all operations history."""
        return self.db.get_all_operations()

    def clear_history(self):
        """Clear all operations history."""
        self.db.clear_operations()
