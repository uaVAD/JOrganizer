import json
import logging
from pathlib import Path
from configparser import ConfigParser

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, lang_dir: Path):
        self.lang_dir = lang_dir
        self.current_lang = 'en'
        self._data = {}
        self._load('en')

    def _load(self, lang: str):
        json_path = self.lang_dir / f'{lang}.json'
        ini_path = self.lang_dir / f'{lang}.ini'
        self._data = {}

        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            self._data = self._flatten(raw)
        elif ini_path.exists():
            parser = ConfigParser()
            parser.optionxform = str
            parser.read(ini_path, encoding='utf-8')
            for section in parser.sections():
                for key, val in parser.items(section):
                    self._data[f'{section}.{key}'] = val
        else:
            logger.warning(f"No language file found for '{lang}' (tried .json and .ini)")

    def _flatten(self, d: dict, prefix: str = '') -> dict:
        result = {}
        for k, v in d.items():
            key = f'{prefix}.{k}' if prefix else k
            if isinstance(v, dict):
                result.update(self._flatten(v, key))
            else:
                result[key] = v
        return result

    def set_language(self, lang: str):
        self._load(lang)
        self.current_lang = lang

    def tr(self, key: str, default: str = None) -> str:
        return self._data.get(key, default if default is not None else key)

    def available_languages(self) -> list[tuple[str, str]]:
        langs = []
        for f in sorted(self.lang_dir.glob('*.json')):
            if f.stem == 'languages':
                continue
            code = f.stem
            with open(f, 'r', encoding='utf-8') as fh:
                raw = json.load(fh)
            label = raw.get('lang', {}).get('self_name', code)
            langs.append((code, label))
        if not langs:
            for f in sorted(self.lang_dir.glob('*.ini')):
                code = f.stem
                p = ConfigParser()
                p.optionxform = str
                p.read(f, encoding='utf-8')
                label = p.get('lang', 'self_name', fallback=code)
                langs.append((code, label))
        return langs
