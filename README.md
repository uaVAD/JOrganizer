# JOrganizer

Desktop application for automatic media file organization compatible with Jellyfin.

Scan → Detect → Match → Rename → Move → Update Jellyfin

## Features

- Scans source folders and detects media type (movie, TV show, anime, cartoon)
- 3-level detection: regex → TMDB/AniList API → user confirmation
- Renames files according to Jellyfin naming conventions
- Moves files into organized folder structure
- Preview changes before execution
- Undo last operation
- Auto-watch folders for new files
- Duplicate detection (name, size, SHA256 hash)
- Dark modern UI (PyQt6)
- Multi-language support

## Requirements

- Python 3.10+
- PyQt6 >= 6.6.0
- aiohttp >= 3.9.0
- watchdog >= 3.0.0

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

## Building Executable

```bash
pip install pyinstaller
pyinstaller JOrganizer.spec
```

The compiled `.exe` will be in `dist/JOrganizer/`.

## Configuration

Create `config/init.json` with your API keys (optional):

```json
{
    "tmdb_api_key": "your_tmdb_api_key"
}
```

TMDB API key can also be entered through the Settings UI.

## Adding a Language

1. Create `languages/{code}.json` (copy `en.json` as template)
2. Translate all string values
3. Add entry to `languages/languages.json`
4. Restart the app

## License

MIT
