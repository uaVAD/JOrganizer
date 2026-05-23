from pathlib import Path


class Renamer:
    """Generate new filenames based on media type."""

    def rename_movie(self, title: str, year: int | None = None) -> str:
        name = f"{title}"
        if year:
            name += f" ({year})"
        return f"{name}"

    def rename_tv(self, show_name: str, season: int | None, episode: int | None, year: int | None = None, episode_title: str | None = None) -> str:
        s = f"{season or 1:02d}"
        e = f"{episode or 1:02d}"
        name = f"{show_name} - S{s}E{e}" if not year else f"{show_name} ({year}) - S{s}E{e}"
        if episode_title:
            name += f" - {episode_title}"
        return f"{name}"

    def rename_anime(self, title: str, season: int | None, episode: int | None, year: int | None = None, episode_title: str | None = None) -> str:
        return self.rename_tv(title, season, episode, year, episode_title)

    def generate_new_filename(self, detection_result: dict, filepath: str) -> str:
        p = Path(filepath)
        ext = p.suffix

        media_type = detection_result.get('type', 'unknown')
        title = detection_result.get('title', p.stem)
        year = detection_result.get('year')
        season = detection_result.get('season')
        episode = detection_result.get('episode')

        if media_type in ('movie', 'cartoon'):
            name = self.rename_movie(title, year)
        elif season is not None and episode is not None:
            name = self.rename_tv(title, season, episode, year)
        elif media_type in ('tv', 'anime'):
            name = self.rename_tv(title, season or 1, episode or 1, year)
        else:
            name = p.stem

        return f"{name}{ext}"
