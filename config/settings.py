import json
import os
import sys
from pathlib import Path

VERSION = "v0.3.4"
APP_NAME = "JOrganizer"

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(os.environ['APPDATA']) / APP_NAME
    MEIPASS = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent.parent
    MEIPASS = BASE_DIR

BASE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE_DIR / "data.db"
_INIT_PATH = MEIPASS / "config" / "init.json"
TMDB_API_KEY = ""
try:
    with open(_INIT_PATH) as f:
        cfg = json.load(f)
    TMDB_API_KEY = cfg.get("tmdb_api_key", "")
except Exception:
    pass

MEDIA_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.rm', '.rmvb', '.3gp', '.ogv', '.m2ts', '.vob'}

COLORS = {
    "background": "#111827",
    "panel": "#1F2937",
    "accent": "#7C3AED",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
}
