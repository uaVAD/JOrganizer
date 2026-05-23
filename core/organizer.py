from pathlib import Path


class Organizer:
    """Organize files into proper folder structure by media category."""

    def __init__(self, category_dirs: dict):
        self.category_dirs = {k: Path(v) if v else None for k, v in category_dirs.items()}

    def get_target_path(self, detection_result: dict, new_filename: str) -> Path:
        mtype = detection_result.get('type', 'unknown')
        destination = self.category_dirs.get(mtype)
        if not destination:
            destination = next(
                (d for d in self.category_dirs.values() if d),
                Path()
            )
        title = detection_result.get('title', 'Unknown')
        season = detection_result.get('season')
        year = detection_result.get('year')

        show_folder = f"{title} ({year})" if year else title

        if season is not None:
            return destination / show_folder / f"Season {season:02d}" / new_filename

        return destination / show_folder / new_filename
