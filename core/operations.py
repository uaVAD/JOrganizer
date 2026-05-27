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

    def preview(self, files: list, destination: Path | str = None) -> list[dict]:
        """Simulate operations without making changes. Returns preview."""
        file_list = self._normalize_files(files)
        preview = []

        for file_info in file_list:
            try:
                src_path = Path(file_info['path'])
                new_name = src_path.name
                target = Path(destination) / src_path.parent.name / new_name if destination else None

                if self.detector and self.renamer and self.organizer:
                    result = self.detector.detect(file_info['path'])
                    new_name = self.renamer.generate_new_filename(result, file_info['path'])
                    target = self.organizer.get_target_path(result, new_name)

                det_result = result if self.detector else None

                preview.append({
                    'source': str(src_path),
                    'dest': str(target) if target else None,
                    'name': src_path.name,
                    'type': det_result.get('type', 'unknown') if det_result else 'unknown',
                    'detection': det_result,
                    'original': str(src_path),
                    'target': str(target) if target else None,
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
                    'original': file_info.get('path', ''),
                    'target': None,
                })

        preview = self._assign_special_numbers(preview)
        return preview

    def _assign_special_numbers(self, preview: list[dict]) -> list[dict]:
        """Assign sequential episode numbers to specials to avoid overwrites."""
        from collections import defaultdict
        from pathlib import Path
        import re

        specials_by_dir = defaultdict(list)
        for item in preview:
            det = item.get('detection')
            if det and det.get('season') == 0 and det.get('episode') is None:
                target_dir = Path(item['target']).parent if item.get('target') else None
                if target_dir:
                    specials_by_dir[str(target_dir)].append(item)

        for dir_path, items in specials_by_dir.items():
            target_dir = Path(dir_path)
            used = set()
            if target_dir.exists():
                for f in target_dir.iterdir():
                    if f.is_file():
                        m = re.search(r'S00E(\d+)', f.stem, re.IGNORECASE)
                        if m:
                            used.add(int(m.group(1)))
            next_ep = 1
            for item in items:
                while next_ep in used:
                    next_ep += 1
                det = item['detection']
                det['episode'] = next_ep
                used.add(next_ep)
                next_ep += 1
                if self.renamer and self.organizer:
                    new_name = self.renamer.generate_new_filename(det, item['original'])
                    target = self.organizer.get_target_path(det, new_name)
                    item['target'] = str(target)
                    item['dest'] = str(target)
        return preview

    def execute(self, preview: list[dict], force: bool = False) -> list[dict]:
        """Execute operations from preview. Returns results."""
        results = []
        now = datetime.now()
        timestamp = now.isoformat()
        action_id = int(now.timestamp() * 1000)

        for item in preview:
            original = item.get('source', item.get('original'))
            target = item.get('dest', item.get('target'))

            if not target:
                results.append({'original': original, 'success': False, 'error': item.get('error', 'No target path')})
                continue

            try:
                self.db.add_operation(original, target, timestamp, action_id)

                target_path = Path(target)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(original), str(target))

                src_parent = Path(original).parent
                for _ in range(5):
                    try:
                        src_parent.rmdir()
                        src_parent = src_parent.parent
                    except OSError:
                        break

                results.append({'original': original, 'target': target, 'success': True})
                logger.info(f"Moved: {original} -> {target}")

            except Exception as e:
                logger.error(f"Failed to move {original}: {e}")
                try:
                    Path(target).parent.rmdir()
                except OSError:
                    pass
                results.append({'original': original, 'target': target, 'success': False, 'error': str(e)})

        return results

    def undo_last(self):
        """Undo the last action (all files from the most recent execute)."""
        max_id = self.db.get_max_action_id()
        if max_id is None:
            return []
        operations = self.db.get_operations_by_action(max_id)
        if not operations:
            return []
        return [self._undo_operation(op) for op in operations]

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
